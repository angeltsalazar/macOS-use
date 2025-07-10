#!/usr/bin/env python3
"""
Optimized macOS UI Tree Management Module

This module provides enhanced UI tree handling with caching, incremental loading,
and performance optimizations for macOS UI automation.
"""

import hashlib
import json
import logging
import threading
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional

from mlx_use.mac.element import MacElementNode
from mlx_use.mac.tree import MacUITreeBuilder

# Configure logging
logger = logging.getLogger(__name__)

# Constants for error messages
ELEMENT_NOT_FOUND_ERROR = "Element not found"
TREE_NOT_AVAILABLE_ERROR = "Tree not available"


class AppTreeCache:
    """Enhanced global state with caching and optimization"""
    
    def __init__(self):
        self.trees: Dict[int, MacElementNode] = {}
        self.elements_flat: Dict[int, List[Dict[str, Any]]] = {}
        self.search_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.last_updated: Dict[int, float] = {}
        self.builders: Dict[int, MacUITreeBuilder] = {}
        # New: Incremental loading cache
        self.partial_trees: Dict[str, MacElementNode] = {}  # key: f"{pid}:{path}"
        self.element_checksums: Dict[str, str] = {}  # For differential updates
        self.lock = threading.Lock()
    
    def get_builder(self, pid: int) -> MacUITreeBuilder:
        """Get or create builder for PID with aggressive performance optimizations"""
        if pid not in self.builders:
            self.builders[pid] = MacUITreeBuilder()
            # Aggressive performance optimizations based on research
            self.builders[pid].max_children = 50   # Reduced from 100
            self.builders[pid].max_depth = 4       # Reduced from 8 for initial load
        return self.builders[pid]
    
    def invalidate(self, pid: int):
        """Invalidate cache for specific PID"""
        with self.lock:
            self.trees.pop(pid, None)
            self.elements_flat.pop(pid, None)
            self.last_updated.pop(pid, None)
            # Clear search cache entries for this PID
            keys_to_remove = [k for k in self.search_cache.keys() if k.startswith(f"{pid}:")]
            for key in keys_to_remove:
                del self.search_cache[key]
    
    def cleanup_builder(self, pid: int):
        """Cleanup builder resources"""
        if pid in self.builders:
            self.builders[pid].cleanup()
            del self.builders[pid]
    
    def get_element_key(self, pid: int, element_path: str) -> str:
        """Generate cache key for partial tree element"""
        return f"{pid}:{element_path}"
    
    def should_load_children(self, element: 'MacElementNode', current_depth: int, max_depth: int) -> bool:
        """Determine if children should be loaded based on performance heuristics"""
        # Always load interactive elements and important containers
        if element.is_interactive:
            return current_depth < max_depth
        
        # Load children for structural containers up to limited depth
        if element.role in ['AXWindow', 'AXGroup', 'AXScrollArea', 'AXSplitGroup', 'AXTabGroup', 'AXToolbar']:
            return current_depth < min(max_depth, 3)  # Limit structural depth
        
        # Skip loading children for display-only elements
        if element.role in ['AXRow', 'AXCell', 'AXTable', 'AXStaticText']:
            return False
        
        return current_depth < 2  # Very conservative for other elements


# Constants for filtering
EXCLUDE_ROLES = ['AXRow', 'AXCell', 'AXTable', 'AXColumn', 'AXColumnHeader']
CONTAINER_ROLES = ['AXWindow', 'AXGroup', 'AXScrollArea', 'AXSplitGroup', 'AXTabGroup', 'AXToolbar', 'AXPopUpButton', 'AXMenuBar', 'AXOutline']


def _sanitize_value(value: Any) -> Any:
    """Sanitize a single value for JSON serialization"""
    if value is None:
        return None
    elif isinstance(value, (str, int, float, bool)):
        return value
    elif isinstance(value, (list, tuple)):
        return [_sanitize_value(item) for item in value]
    elif isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    else:
        # Convert any other type to string
        return str(value)


def _sanitize_attributes(attributes: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize attributes to ensure JSON serializability"""
    sanitized = {}
    for key, value in attributes.items():
        try:
            # Test JSON serializability
            json.dumps(value)
            sanitized[key] = value
        except (TypeError, ValueError):
            # Use our sanitization function
            sanitized[key] = _sanitize_value(value)
    return sanitized


def _convert_element_to_info(element: MacElementNode, parent_path: str = None) -> Dict[str, Any]:
    """Convert MacElementNode to dictionary with parent context"""
    # Sanitize attributes to ensure JSON serializability
    clean_attributes = _sanitize_attributes(element.attributes)
    
    return {
        "role": element.role,
        "identifier": element.identifier,
        "attributes": clean_attributes,
        "is_visible": element.is_visible,
        "is_interactive": element.is_interactive,
        "highlight_index": element.highlight_index,
        "actions": element.actions,
        "children_count": len(element.children),
        "path": element.accessibility_path,
        "parent_path": parent_path
    }


def _has_interactive_descendants(node: MacElementNode, max_depth: int = 2, current_depth: int = 0) -> bool:
    """Check if node has interactive descendants within depth limit"""
    if current_depth >= max_depth:
        return False
    
    for grandchild in node.children:
        # Skip checking excluded display elements
        if grandchild.role in EXCLUDE_ROLES and not grandchild.is_interactive:
            continue
        if grandchild.is_interactive:
            return True
        if grandchild.children and _has_interactive_descendants(grandchild, max_depth, current_depth + 1):
            return True
    return False


def _should_include_child(child: MacElementNode) -> bool:
    """Determine if a child element should be included in interactive filtering"""
    # EXCLUDE display-only elements that are not interactive
    if child.role in EXCLUDE_ROLES and not child.is_interactive:
        return False
    
    # Include if child is directly interactive
    if child.is_interactive:
        return True
    
    # Include important container roles
    if child.role in CONTAINER_ROLES:
        return True
    
    # Include if has interactive descendants
    if child.children and _has_interactive_descendants(child):
        return True
    
    return False


def _filter_children_for_interactive(children: list) -> list:
    """Filter children to include only interactive or structurally important elements"""
    filtered_children = []
    for child in children:
        if _should_include_child(child):
            filtered_children.append(child)
    return filtered_children[:50]  # Limit for performance


def _find_element_by_path(node: MacElementNode, target_path: str) -> Optional[MacElementNode]:
    """Recursively find element by accessibility path"""
    if node.accessibility_path == target_path:
        return node
    for child in node.children:
        result = _find_element_by_path(child, target_path)
        if result:
            return result
    return None


async def _expand_element_with_builder(builder, element: MacElementNode, pid: int) -> Optional[MacElementNode]:
    """Expand element using builder with deeper traversal"""
    original_max_depth = builder.max_depth
    builder.max_depth = 8  # Allow deeper expansion
    
    try:
        return await builder._process_element(element._element_ref, pid, element.parent, 0)
    finally:
        builder.max_depth = original_max_depth


def _convert_tree_to_json_incremental(element: MacElementNode, max_depth: int = 2, current_depth: int = 0, parent_path: str = None, interactive_only: bool = True) -> Dict[str, Any]:
    """Convert tree with incremental loading support and interactive filtering"""
    element_info = _convert_element_to_info(element, parent_path)
    
    children = []
    is_expanded = current_depth < max_depth
    
    if is_expanded and element.children:
        if interactive_only:
            filtered_children = _filter_children_for_interactive(element.children)
            children = [_convert_tree_to_json_incremental(child, max_depth, current_depth + 1, element.accessibility_path, interactive_only) 
                       for child in filtered_children]
        else:
            # Show all elements (original behavior)
            children = [_convert_tree_to_json_incremental(child, max_depth, current_depth + 1, element.accessibility_path, interactive_only) 
                       for child in element.children[:20]]
    
    return {
        "element": element_info,
        "children": children,
        "is_expanded": is_expanded
    }


@lru_cache(maxsize=128)
def _get_cached_search_key(pid: int, query: str, case_sensitive: bool) -> str:
    """Generate cache key for search results"""
    return f"{pid}:{hashlib.md5(f'{query}:{case_sensitive}'.encode()).hexdigest()}"


async def _build_tree_cached(cache: AppTreeCache, pid: int, force_refresh: bool = False, lazy_mode: bool = True, max_depth: Optional[int] = None) -> Optional[MacElementNode]:
    """Build tree with caching and lazy loading optimization"""
    current_time = time.time()
    
    # Check if we have a recent cached version
    if not force_refresh and pid in cache.trees:
        last_update = cache.last_updated.get(pid, 0)
        cache_age = current_time - last_update
        if cache_age < 5:  # 5 second cache for faster UI updates
            logger.info(f"Using cached tree for PID {pid} (age: {cache_age:.1f}s)")
            return cache.trees[pid]
    
    # Build new tree with performance optimizations
    start_time = time.time()
    logger.info(f"Building {'lazy' if lazy_mode else 'full'} tree for PID {pid}")
    builder = cache.get_builder(pid)
    
    # Store original settings
    original_max_depth = builder.max_depth
    original_max_children = builder.max_children
    
    # Apply custom max_depth if provided
    if max_depth is not None:
        builder.max_depth = max_depth
    elif lazy_mode:
        # Ultra-aggressive settings for initial load
        builder.max_depth = 3      # Very shallow initial load
        builder.max_children = 25  # Limit children per level
    
    try:
        tree = await builder.build_tree(pid)
        build_time = time.time() - start_time
        
        if tree:
            with cache.lock:
                cache.trees[pid] = tree
                cache.last_updated[pid] = current_time
                # Invalidate elements cache to force rebuild
                cache.elements_flat.pop(pid, None)
            
            logger.info(f"Tree built successfully for PID {pid} in {build_time:.2f}s ({'lazy' if lazy_mode else 'full'} mode)")
        return tree
        
    except Exception as e:
        logger.error(f"Error building tree for PID {pid}: {e}")
        return None
    finally:
        # Restore original settings
        builder.max_depth = original_max_depth
        builder.max_children = original_max_children


def _flatten_tree_cached(cache: AppTreeCache, pid: int) -> List[Dict[str, Any]]:
    """Get flattened elements with caching"""
    if pid in cache.elements_flat:
        return cache.elements_flat[pid]
    
    if pid not in cache.trees:
        return []
    
    elements = []
    def collect_elements(node: MacElementNode, parent_path: str = None):
        elements.append(_convert_element_to_info(node, parent_path))
        for child in node.children:
            collect_elements(child, node.accessibility_path)
    
    collect_elements(cache.trees[pid])
    
    with cache.lock:
        cache.elements_flat[pid] = elements
    
    return elements


# Search helper functions
def _normalize_search_query(query: str, case_sensitive: bool) -> str:
    """Normalize search query for comparison"""
    query = query.strip()
    return query if case_sensitive else query.lower()


def _extract_searchable_text(element: Dict[str, Any], case_sensitive: bool) -> str:
    """Extract searchable text from element"""
    searchable_parts = []
    
    # Add role
    if element.get("role"):
        searchable_parts.append(str(element["role"]))
    
    # Add relevant attributes
    for attr_key in ['title', 'value', 'description', 'label', 'placeholder']:
        attr_value = element.get("attributes", {}).get(attr_key)
        if attr_value:
            sanitized = _sanitize_value(attr_value)
            if sanitized and str(sanitized).strip():
                searchable_parts.append(str(sanitized))
    
    # Add actions
    if element.get("actions"):
        searchable_parts.extend(element["actions"])
    
    # Join and normalize
    searchable_text = " ".join(searchable_parts)
    return searchable_text if case_sensitive else searchable_text.lower()


def _should_log_debug_info(element: Dict[str, Any], debug_count: int) -> bool:
    """Check if element should be logged for debugging"""
    return element.get("role") == 'AXButton' and debug_count < 5


def _create_search_result(matching_elements: List[Dict[str, Any]], search_time: float) -> Dict[str, Any]:
    """Create search result response"""
    return {
        "elements": matching_elements,
        "total_count": len(matching_elements),
        "search_time": search_time
    }


class OptimizedTreeManager:
    """Manager class for optimized macOS UI tree operations"""
    
    def __init__(self):
        self.cache = AppTreeCache()
    
    async def build_tree(self, pid: int, force_refresh: bool = False, lazy_mode: bool = True, max_depth: Optional[int] = None) -> Optional[MacElementNode]:
        """Build tree with caching and lazy loading optimization"""
        return await _build_tree_cached(self.cache, pid, force_refresh, lazy_mode, max_depth)
    
    def get_tree_json(self, pid: int, max_depth: int = 2, interactive_only: bool = True) -> Optional[Dict[str, Any]]:
        """Get tree in JSON format with interactive filtering"""
        if pid not in self.cache.trees:
            return None
        
        tree = self.cache.trees[pid]
        return _convert_tree_to_json_incremental(tree, max_depth, interactive_only=interactive_only)
    
    def get_flattened_elements(self, pid: int) -> List[Dict[str, Any]]:
        """Get flattened elements with caching"""
        return _flatten_tree_cached(self.cache, pid)
    
    async def search_elements(self, pid: int, query: str, case_sensitive: bool = False) -> Dict[str, Any]:
        """Optimized search with caching"""
        start_time = time.time()
        
        # Normalize query for better matching
        original_query = query
        normalized_query = _normalize_search_query(query, case_sensitive)
        
        logger.info(f"Search request: '{original_query}' -> normalized: '{normalized_query}' (case_sensitive: {case_sensitive})")
        
        # Check cache first
        cache_key = _get_cached_search_key(pid, normalized_query, case_sensitive)
        if cache_key in self.cache.search_cache:
            cached_results = self.cache.search_cache[cache_key]
            search_time = time.time() - start_time
            logger.info(f"Cache hit for search '{normalized_query}': {len(cached_results)} results")
            return _create_search_result(cached_results, search_time)
        
        # Ensure we have tree data
        await self.build_tree(pid)
        elements = self.get_flattened_elements(pid)
        
        logger.info(f"Searching through {len(elements)} elements for '{normalized_query}'")
        
        matching_elements = []
        debug_count = 0
        
        for element in elements:
            # Extract searchable text from element
            searchable_text = _extract_searchable_text(element, case_sensitive)
            
            # Debug logging for buttons
            if _should_log_debug_info(element, debug_count):
                logger.info(f"Button {debug_count}: '{searchable_text}' (searching for: '{normalized_query}')")
                debug_count += 1
            
            # Check for match
            if normalized_query in searchable_text:
                matching_elements.append(element)
                logger.info(f"MATCH found: {element.get('role')} - '{element.get('attributes', {}).get('title', 'No title')}'")
        
        logger.info(f"Search completed: {len(matching_elements)} matches for '{normalized_query}'")
        
        # Cache results
        with self.cache.lock:
            self.cache.search_cache[cache_key] = matching_elements
        
        search_time = time.time() - start_time
        return _create_search_result(matching_elements, search_time)
    
    def find_element_by_path(self, pid: int, element_path: str) -> Optional[MacElementNode]:
        """Find element by accessibility path"""
        if pid not in self.cache.trees:
            return None
        
        return _find_element_by_path(self.cache.trees[pid], element_path)
    
    async def expand_element(self, pid: int, element_path: str) -> Optional[Dict[str, Any]]:
        """Expand a specific element to load its children on-demand"""
        if pid not in self.cache.trees:
            return None
        
        tree = self.cache.trees[pid]
        element = _find_element_by_path(tree, element_path)
        if not element:
            return None
        
        # Build deeper tree for this element using full depth
        builder = self.cache.get_builder(pid)
        expanded_element = await _expand_element_with_builder(builder, element, pid)
        
        if expanded_element:
            # Replace the element in the tree
            element.children = expanded_element.children
            element_info = _convert_element_to_info(element)
            children = [_convert_tree_to_json_incremental(child, 3, interactive_only=True) 
                       for child in element.children]
            
            return {
                "element": element_info,
                "children": children,
                "expanded": True
            }
        
        return None
    
    def get_interactive_elements(self, pid: int) -> List[Dict[str, Any]]:
        """Get interactive elements with caching"""
        elements = self.get_flattened_elements(pid)
        return [el for el in elements if el.get("is_interactive")]
    
    def invalidate_cache(self, pid: int):
        """Invalidate cache for specific PID"""
        self.cache.invalidate(pid)
    
    def cleanup(self, pid: int):
        """Cleanup resources for specific PID"""
        self.cache.cleanup_builder(pid)
        self.cache.invalidate(pid)
    
    @property
    def _element_cache(self) -> Dict[int, 'MacElementNode']:
        """
        Compatibility property to provide element cache similar to MacUITreeBuilder.
        This creates a flattened cache on-demand for the last built tree.
        """
        # Find the most recent PID (this is a simple implementation for compatibility)
        if not self.cache.trees:
            return {}
        
        # Get the last PID that was built
        latest_pid = max(self.cache.trees.keys())
        elements = self.get_flattened_elements(latest_pid)
        
        # Create a cache mapping highlight_index to element
        element_cache = {}
        for element_dict in elements:
            highlight_index = element_dict.get('highlight_index')
            if highlight_index is not None:
                # Find the actual MacElementNode from the tree
                element = self.find_element_by_path(latest_pid, element_dict['path'])
                if element:
                    element_cache[highlight_index] = element
        
        return element_cache
    
    def clear_all_caches(self):
        """Clear all caches"""
        # Cleanup all builders
        for pid in self.cache.builders.keys():
            self.cache.cleanup_builder(pid)
        
        # Clear all caches
        with self.cache.lock:
            self.cache.trees.clear()
            self.cache.elements_flat.clear()
            self.cache.search_cache.clear()
            self.cache.last_updated.clear()
            self.cache.partial_trees.clear()
            self.cache.element_checksums.clear()
        
        # Clear LRU cache
        _get_cached_search_key.cache_clear()
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics and cache information"""
        with self.cache.lock:
            current_time = time.time()
            stats = {
                "cache_stats": {
                    "trees_cached": len(self.cache.trees),
                    "search_cache_size": len(self.cache.search_cache),
                    "elements_flat_cached": len(self.cache.elements_flat),
                    "partial_trees_cached": len(self.cache.partial_trees)
                },
                "tree_ages": {
                    str(pid): round(current_time - last_updated, 1)
                    for pid, last_updated in self.cache.last_updated.items()
                },
                "optimization_settings": {
                    "default_max_depth_interactive": 5,
                    "default_max_depth_all": 3,
                    "lazy_load_max_depth": 3,
                    "lazy_load_max_children": 25,
                    "cache_expiry_seconds": 5
                },
                "memory_optimization": {
                    "interactive_filtering": True,
                    "lazy_loading": True,
                    "differential_updates": False,  # Not implemented yet
                    "async_processing": False      # Not implemented yet
                }
            }
        
        return stats