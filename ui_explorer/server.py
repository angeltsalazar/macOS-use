#!/usr/bin/env python3
"""
macOS UI Tree Explorer Server

A FastAPI server for exploring and querying the macOS UI Tree System.
Provides REST API endpoints to browse applications, explore UI trees,
and query elements interactively.
"""

import asyncio
import logging
import os
import json
from typing import Optional, List, Dict, Any
from dataclasses import asdict

import Cocoa
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from mlx_use.mac.tree import MacUITreeBuilder
from mlx_use.mac.element import MacElementNode

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="macOS UI Tree Explorer", version="1.0.0")

# Global state
ui_builder = MacUITreeBuilder()
current_app_pid: Optional[int] = None
current_tree: Optional[MacElementNode] = None

# Pydantic models for API responses
class AppInfo(BaseModel):
	pid: int
	name: str
	bundle_id: str
	is_active: bool

class ElementInfo(BaseModel):
	role: str
	identifier: str
	attributes: Dict[str, Any]
	is_visible: bool
	is_interactive: bool
	highlight_index: Optional[int]
	actions: List[str]
	children_count: int
	path: str

class TreeNode(BaseModel):
	element: ElementInfo
	children: List['TreeNode'] = []

class QueryRequest(BaseModel):
	query_type: str  # "role", "title", "action", "path", "custom"
	query_value: str
	case_sensitive: bool = False

class ElementSearchResult(BaseModel):
	elements: List[ElementInfo]
	total_count: int

# Update forward references
TreeNode.model_rebuild()

def _sanitize_attributes(attributes: Dict[str, Any]) -> Dict[str, Any]:
	"""Sanitize attributes to ensure JSON serializability"""
	sanitized = {}
	for key, value in attributes.items():
		try:
			# Test JSON serializability
			json.dumps(value)
			sanitized[key] = value
		except (TypeError, ValueError):
			# Convert non-serializable values to string representation
			sanitized[key] = str(value) if value is not None else None
	return sanitized

def _convert_element_to_info(element: MacElementNode) -> ElementInfo:
	"""Convert MacElementNode to ElementInfo for JSON serialization"""
	# Sanitize attributes to ensure JSON serializability
	clean_attributes = _sanitize_attributes(element.attributes)
	
	return ElementInfo(
		role=element.role,
		identifier=element.identifier,
		attributes=clean_attributes,
		is_visible=element.is_visible,
		is_interactive=element.is_interactive,
		highlight_index=element.highlight_index,
		actions=element.actions,
		children_count=len(element.children),
		path=element.accessibility_path
	)

def _convert_tree_to_json(element: MacElementNode, max_depth: int = 10, current_depth: int = 0) -> TreeNode:
	"""Convert MacElementNode tree to JSON-serializable format"""
	element_info = _convert_element_to_info(element)
	
	children = []
	if current_depth < max_depth:
		children = [_convert_tree_to_json(child, max_depth, current_depth + 1) 
				   for child in element.children]
	
	return TreeNode(element=element_info, children=children)

@app.get("/")
async def read_root():
	"""Serve the main HTML interface"""
	return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
	<title>macOS UI Tree Explorer</title>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<style>
		body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
		.container { max-width: 1400px; margin: 0 auto; }
		.header { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
		.section { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
		.apps-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; }
		.app-card { border: 1px solid #ddd; border-radius: 8px; padding: 15px; cursor: pointer; transition: all 0.3s; }
		.app-card:hover { background: #f0f8ff; border-color: #007acc; }
		.app-card.active { background: #e6f3ff; border-color: #007acc; border-width: 2px; }
		.tree-container { display: flex; gap: 20px; }
		.tree-panel { flex: 1; background: #f9f9f9; border-radius: 8px; padding: 15px; }
		.element-details { flex: 1; background: #f9f9f9; border-radius: 8px; padding: 15px; }
		.tree-node { margin-left: 20px; }
		.element-item { 
			padding: 8px; margin: 2px 0; border-radius: 4px; cursor: pointer; 
			border: 1px solid transparent; transition: all 0.2s;
		}
		.element-item:hover { background: #e0e0e0; }
		.element-item.interactive { background: #e8f5e8; border-color: #4CAF50; }
		.element-item.selected { background: #cce5ff; border-color: #007acc; }
		.search-box { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 15px; }
		.btn { padding: 10px 20px; background: #007acc; color: white; border: none; border-radius: 4px; cursor: pointer; }
		.btn:hover { background: #005c99; }
		.btn.secondary { background: #6c757d; }
		.btn.secondary:hover { background: #545b62; }
		.attribute { margin: 5px 0; padding: 5px; background: #f0f0f0; border-radius: 3px; }
		.loading { text-align: center; padding: 20px; color: #666; }
		.error { color: #d32f2f; background: #ffebee; padding: 10px; border-radius: 4px; margin: 10px 0; }
		.success { color: #388e3c; background: #e8f5e8; padding: 10px; border-radius: 4px; margin: 10px 0; }
		pre { background: #f5f5f5; padding: 10px; border-radius: 4px; overflow: auto; max-height: 400px; }
	</style>
</head>
<body>
	<div class="container">
		<div class="header">
			<h1>🌳 macOS UI Tree Explorer</h1>
			<p>Explore macOS application UI trees, query elements, and understand accessibility structures.</p>
		</div>

		<div class="section">
			<h2>Running Applications</h2>
			<button class="btn" onclick="loadApps()">Refresh Apps</button>
			<div id="apps-container" class="apps-grid"></div>
		</div>

		<div class="section">
			<h2>UI Tree Explorer</h2>
			<div id="tree-section" style="display: none;">
				<div style="margin-bottom: 15px;">
					<input type="text" id="search-input" class="search-box" placeholder="Search elements by role, title, or action...">
					<button class="btn" onclick="searchElements()">Search</button>
					<button class="btn secondary" onclick="refreshTree()">Refresh Tree</button>
				</div>
				<div class="tree-container">
					<div class="tree-panel">
						<h3>UI Tree Structure</h3>
						<div id="tree-container"></div>
					</div>
					<div class="element-details">
						<h3>Element Details</h3>
						<div id="element-details">Select an element to view details</div>
					</div>
				</div>
			</div>
		</div>

		<div class="section">
			<h2>Query Builder</h2>
			<div id="query-section">
				<select id="query-type">
					<option value="role">By Role (e.g., AXButton)</option>
					<option value="title">By Title</option>
					<option value="action">By Action (e.g., AXPress)</option>
					<option value="custom">Custom Query</option>
				</select>
				<input type="text" id="query-value" class="search-box" placeholder="Enter query value...">
				<button class="btn" onclick="executeQuery()">Execute Query</button>
				<div id="query-results"></div>
			</div>
		</div>
	</div>

	<script>
		let currentAppPid = null;
		let currentTree = null;
		let selectedElement = null;

		async function loadApps() {
			try {
				const response = await fetch('/api/apps');
				const apps = await response.json();
				
				const container = document.getElementById('apps-container');
				container.innerHTML = apps.map(app => `
					<div class="app-card" onclick="selectApp(${app.pid})" id="app-${app.pid}">
						<h3>${app.name}</h3>
						<p><strong>PID:</strong> ${app.pid}</p>
						<p><strong>Bundle ID:</strong> ${app.bundle_id}</p>
						<p><strong>Status:</strong> ${app.is_active ? 'Active' : 'Background'}</p>
					</div>
				`).join('');
			} catch (error) {
				showError('Failed to load applications: ' + error.message);
			}
		}

		async function selectApp(pid) {
			try {
				// Update UI
				document.querySelectorAll('.app-card').forEach(card => card.classList.remove('active'));
				document.getElementById(`app-${pid}`).classList.add('active');
				
				currentAppPid = pid;
				document.getElementById('tree-section').style.display = 'block';
				
				// Load tree
				await loadTree(pid);
			} catch (error) {
				showError('Failed to select application: ' + error.message);
			}
		}

		async function loadTree(pid) {
			try {
				showLoading('tree-container', 'Loading UI tree...');
				
				const response = await fetch(`/api/apps/${pid}/tree`);
				if (!response.ok) {
					throw new Error(`HTTP ${response.status}: ${response.statusText}`);
				}
				
				const tree = await response.json();
				currentTree = tree;
				renderTree(tree);
			} catch (error) {
				showError('Failed to load UI tree: ' + error.message);
				document.getElementById('tree-container').innerHTML = '';
			}
		}

		function renderTree(node, container = null, depth = 0) {
			if (!container) {
				container = document.getElementById('tree-container');
				container.innerHTML = '';
			}

			const element = node.element;
			const isInteractive = element.is_interactive;
			const highlight = element.highlight_index !== null ? `[${element.highlight_index}]` : '';
			
			const elementDiv = document.createElement('div');
			elementDiv.className = `element-item ${isInteractive ? 'interactive' : ''}`;
			elementDiv.style.marginLeft = `${depth * 20}px`;
			elementDiv.onclick = () => selectElement(element);
			
			const title = element.attributes.title || '';
			const value = element.attributes.value || '';
			const displayText = `${element.role}${highlight} ${title} ${value}`.trim();
			
			elementDiv.innerHTML = `
				<div style="font-weight: ${isInteractive ? 'bold' : 'normal'};">
					${displayText}
					${isInteractive ? '<span style="color: #4CAF50;"> ✓</span>' : ''}
				</div>
			`;
			
			container.appendChild(elementDiv);

			// Render children
			node.children.forEach(child => {
				renderTree(child, container, depth + 1);
			});
		}

		function selectElement(element) {
			selectedElement = element;
			
			// Update visual selection
			document.querySelectorAll('.element-item').forEach(el => el.classList.remove('selected'));
			event.currentTarget.classList.add('selected');
			
			// Show details
			const detailsContainer = document.getElementById('element-details');
			detailsContainer.innerHTML = `
				<h4>${element.role}</h4>
				<div class="attribute"><strong>Interactive:</strong> ${element.is_interactive ? 'Yes' : 'No'}</div>
				<div class="attribute"><strong>Highlight Index:</strong> ${element.highlight_index || 'None'}</div>
				<div class="attribute"><strong>Path:</strong> ${element.path}</div>
				<div class="attribute"><strong>Actions:</strong> ${element.actions.join(', ') || 'None'}</div>
				<div class="attribute"><strong>Children:</strong> ${element.children_count}</div>
				<h5>Attributes:</h5>
				<pre>${JSON.stringify(element.attributes, null, 2)}</pre>
			`;
		}

		async function searchElements() {
			const query = document.getElementById('search-input').value.trim();
			if (!query) return;

			try {
				const response = await fetch(`/api/apps/${currentAppPid}/search?q=${encodeURIComponent(query)}`);
				const results = await response.json();
				
				if (results.elements.length === 0) {
					showError(`No elements found matching "${query}"`);
					return;
				}

				// Highlight matching elements in tree
				highlightSearchResults(results.elements);
				showSuccess(`Found ${results.total_count} matching elements`);
			} catch (error) {
				showError('Search failed: ' + error.message);
			}
		}

		function highlightSearchResults(elements) {
			// Reset previous highlights
			document.querySelectorAll('.element-item').forEach(el => {
				el.style.background = '';
				el.style.borderColor = '';
			});

			// Highlight matching elements
			elements.forEach(element => {
				const elementItems = Array.from(document.querySelectorAll('.element-item'));
				const matchingItem = elementItems.find(item => 
					item.textContent.includes(element.role) && 
					(element.highlight_index === null || item.textContent.includes(`[${element.highlight_index}]`))
				);
				if (matchingItem) {
					matchingItem.style.background = '#fff3cd';
					matchingItem.style.borderColor = '#ffc107';
				}
			});
		}

		async function executeQuery() {
			const queryType = document.getElementById('query-type').value;
			const queryValue = document.getElementById('query-value').value.trim();
			
			if (!queryValue) {
				showError('Please enter a query value');
				return;
			}

			try {
				const response = await fetch(`/api/apps/${currentAppPid}/query`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						query_type: queryType,
						query_value: queryValue,
						case_sensitive: false
					})
				});

				const results = await response.json();
				
				const resultsContainer = document.getElementById('query-results');
				if (results.elements.length === 0) {
					resultsContainer.innerHTML = '<div class="error">No matching elements found</div>';
					return;
				}

				resultsContainer.innerHTML = `
					<div class="success">Found ${results.total_count} matching elements:</div>
					<div style="max-height: 300px; overflow-y: auto;">
						${results.elements.map(el => `
							<div class="attribute" style="cursor: pointer;" onclick="selectElementById('${el.identifier}')">
								<strong>${el.role}</strong> ${el.highlight_index !== null ? `[${el.highlight_index}]` : ''}
								<br><small>${el.path}</small>
								${el.attributes.title ? `<br><em>${el.attributes.title}</em>` : ''}
							</div>
						`).join('')}
					</div>
				`;
			} catch (error) {
				showError('Query failed: ' + error.message);
			}
		}

		async function refreshTree() {
			if (currentAppPid) {
				await loadTree(currentAppPid);
			}
		}

		function showLoading(containerId, message) {
			document.getElementById(containerId).innerHTML = `<div class="loading">${message}</div>`;
		}

		function showError(message) {
			const errorDiv = document.createElement('div');
			errorDiv.className = 'error';
			errorDiv.textContent = message;
			document.body.insertBefore(errorDiv, document.body.firstChild);
			setTimeout(() => errorDiv.remove(), 5000);
		}

		function showSuccess(message) {
			const successDiv = document.createElement('div');
			successDiv.className = 'success';
			successDiv.textContent = message;
			document.body.insertBefore(successDiv, document.body.firstChild);
			setTimeout(() => successDiv.remove(), 3000);
		}

		// Load apps on page load
		loadApps();
	</script>
</body>
</html>
	""")

@app.get("/api/apps", response_model=List[AppInfo])
async def get_running_apps():
	"""Get list of running macOS applications"""
	try:
		workspace = Cocoa.NSWorkspace.sharedWorkspace()
		apps = []
		
		for app in workspace.runningApplications():
			if app.bundleIdentifier() and not app.bundleIdentifier().startswith('com.apple.'):
				# Skip system apps for cleaner list
				continue
			
			apps.append(AppInfo(
				pid=app.processIdentifier(),
				name=app.localizedName() or "Unknown",
				bundle_id=app.bundleIdentifier() or "Unknown",
				is_active=app.isActive()
			))
		
		# Sort by active status and name
		apps.sort(key=lambda x: (not x.is_active, x.name.lower()))
		return apps
		
	except Exception as e:
		logger.error(f"Error getting running apps: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/apps/{pid}/tree", response_model=TreeNode)
async def get_app_tree(pid: int, max_depth: int = 10):
	"""Get UI tree for a specific application"""
	global current_app_pid, current_tree, ui_builder
	
	try:
		# Clean up previous state
		ui_builder.cleanup()
		ui_builder = MacUITreeBuilder()
		
		# Build new tree
		tree = await ui_builder.build_tree(pid)
		if not tree:
			raise HTTPException(status_code=404, detail="Could not build UI tree for application")
		
		current_app_pid = pid
		current_tree = tree
		
		return _convert_tree_to_json(tree, max_depth)
		
	except Exception as e:
		logger.error(f"Error building tree for PID {pid}: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/apps/{pid}/elements", response_model=List[ElementInfo])
async def get_app_elements(pid: int):
	"""Get all elements for a specific application as a flat list"""
	try:
		if current_app_pid != pid or not current_tree:
			# Rebuild tree if needed
			tree = await ui_builder.build_tree(pid)
			if not tree:
				raise HTTPException(status_code=404, detail="Could not build UI tree")
		else:
			tree = current_tree
		
		# Flatten tree to list
		elements = []
		
		def collect_elements(node: MacElementNode):
			elements.append(_convert_element_to_info(node))
			for child in node.children:
				collect_elements(child)
		
		collect_elements(tree)
		return elements
		
	except Exception as e:
		logger.error(f"Error getting elements for PID {pid}: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/apps/{pid}/search", response_model=ElementSearchResult)
async def search_elements(pid: int, q: str, case_sensitive: bool = False):
	"""Search elements by text query across multiple attributes"""
	try:
		elements = await get_app_elements(pid)
		
		query = q if case_sensitive else q.lower()
		matching_elements = []
		
		for element in elements:
			# Search in role, title, value, description
			searchable_text = " ".join([
				element.role,
				element.attributes.get('title', ''),
				element.attributes.get('value', ''),
				element.attributes.get('description', ''),
				" ".join(element.actions)
			])
			
			if not case_sensitive:
				searchable_text = searchable_text.lower()
			
			if query in searchable_text:
				matching_elements.append(element)
		
		return ElementSearchResult(
			elements=matching_elements,
			total_count=len(matching_elements)
		)
		
	except Exception as e:
		logger.error(f"Error searching elements: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/apps/{pid}/query", response_model=ElementSearchResult)
async def query_elements(pid: int, query: QueryRequest):
	"""Execute structured query on elements"""
	try:
		elements = await get_app_elements(pid)
		matching_elements = []
		
		for element in elements:
			match = False
			
			if query.query_type == "role":
				target = element.role
			elif query.query_type == "title":
				target = element.attributes.get('title', '')
			elif query.query_type == "action":
				target = " ".join(element.actions)
			elif query.query_type == "path":
				target = element.path
			else:  # custom
				target = json.dumps(element.dict())
			
			if not query.case_sensitive:
				target = target.lower()
				search_value = query.query_value.lower()
			else:
				search_value = query.query_value
			
			if search_value in target:
				matching_elements.append(element)
		
		return ElementSearchResult(
			elements=matching_elements,
			total_count=len(matching_elements)
		)
		
	except Exception as e:
		logger.error(f"Error querying elements: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/apps/{pid}/element/{element_id}")
async def get_element_details(pid: int, element_id: str):
	"""Get detailed information about a specific element"""
	try:
		elements = await get_app_elements(pid)
		
		for element in elements:
			if element.identifier == element_id:
				return element
		
		raise HTTPException(status_code=404, detail="Element not found")
		
	except Exception as e:
		logger.error(f"Error getting element details: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/apps/{pid}/interactive", response_model=List[ElementInfo])
async def get_interactive_elements(pid: int):
	"""Get only interactive elements for a specific application"""
	try:
		elements = await get_app_elements(pid)
		interactive_elements = [el for el in elements if el.is_interactive]
		return interactive_elements
		
	except Exception as e:
		logger.error(f"Error getting interactive elements: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.on_event("shutdown")
async def shutdown_event():
	"""Cleanup resources on server shutdown"""
	global ui_builder
	if ui_builder:
		ui_builder.cleanup()

if __name__ == "__main__":
	import uvicorn
	
	print("🌳 Starting macOS UI Tree Explorer Server...")
	print("📖 Open http://localhost:8000 in your browser")
	print("🔍 Use the web interface to explore macOS application UI trees")
	
	uvicorn.run(
		"server:app", 
		host="0.0.0.0", 
		port=8000, 
		reload=True,
		log_level="info"
	)