#!/usr/bin/env python3
"""
Optimized macOS UI Tree Explorer Server

Enhanced version with memoization, incremental exploration, better performance,
and improved visual feedback for search results.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

import Cocoa
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from mlx_use.mac.optimized_tree import OptimizedTreeManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants for error messages
ELEMENT_NOT_FOUND_ERROR = "Element not found"
TREE_NOT_AVAILABLE_ERROR = "Tree not available"

app = FastAPI(title="macOS UI Tree Explorer - Optimized", version="0.2.1")

# Global tree manager instance
tree_manager = OptimizedTreeManager()

# Pydantic models
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
	parent_path: Optional[str] = None

class TreeNode(BaseModel):
	element: Dict[str, Any]  # Changed from ElementInfo to Dict since optimized_tree returns dicts
	children: List['TreeNode'] = []
	is_expanded: bool = False

class QueryRequest(BaseModel):
	query_type: str
	query_value: str
	case_sensitive: bool = False

class ElementSearchResult(BaseModel):
	elements: List[Dict[str, Any]]  # Changed from ElementInfo to Dict
	total_count: int
	search_time: float
	highlighted_paths: List[str] = []

class TreeExplorationRequest(BaseModel):
	element_path: str
	max_depth: int = 3

# Update forward references
TreeNode.model_rebuild()


# App filtering helper functions
def _should_include_apple_app(bundle_id: str) -> bool:
	"""Check if an Apple app should be included based on bundle ID"""
	allowed_apple_apps = ['Notes', 'Finder', 'Safari', 'TextEdit', 'Calculator']
	return any(app in bundle_id for app in allowed_apple_apps)

def _should_exclude_system_process(bundle_id: str, name: str) -> bool:
	"""Check if an app should be excluded as a system process"""
	excluded_names = ['loginwindow', 'WindowServer', 'Dock']
	return (not bundle_id or 
			(bundle_id.startswith('com.apple.') and not _should_include_apple_app(bundle_id)) or
			name in excluded_names)

def _create_app_info(app) -> AppInfo:
	"""Create AppInfo object from NSRunningApplication"""
	return AppInfo(
		pid=app.processIdentifier(),
		name=app.localizedName() or "Unknown",
		bundle_id=app.bundleIdentifier() or "",
		is_active=app.isActive()
	)

def _get_app_sort_key(app: AppInfo) -> tuple:
	"""Get sort key for application, prioritizing Notes app"""
	if app.bundle_id == 'com.apple.Notes':
		return (0, app.name.lower())  # Highest priority
	return (1 if not app.is_active else 0, app.name.lower())


# Text input helper functions
def _find_supported_text_input_action(element_actions: List[str]) -> Optional[str]:
	"""Find supported text input action for element"""
	text_input_actions = ['AXSetValue', 'AXConfirm']
	for action in text_input_actions:
		if action in element_actions:
			return action
	return None

def _try_direct_value_setting(element, text: str) -> tuple[bool, str]:
	"""Try direct AXValueAttribute setting"""
	from ApplicationServices import AXUIElementSetAttributeValue, kAXValueAttribute
	from Foundation import NSString
	
	try:
		ns_text = NSString.stringWithString_(text)
		error = AXUIElementSetAttributeValue(element._element, kAXValueAttribute, ns_text)
		if error == 0:  # kAXErrorSuccess
			return True, "Direct AXValueAttribute setting"
	except Exception as e:
		logger.warning(f"Direct value setting failed: {e}")
	return False, ""

async def _try_click_then_set_value(element, text: str) -> tuple[bool, str]:
	"""Try clicking element then setting value"""
	from ApplicationServices import AXUIElementSetAttributeValue, kAXValueAttribute
	from Foundation import NSString

	from mlx_use.mac.actions import click
	
	try:
		click_result = click(element, 'AXConfirm')
		if click_result:
			# Wait for focus
			await asyncio.sleep(0.2)
			ns_text = NSString.stringWithString_(text)
			error = AXUIElementSetAttributeValue(element._element, kAXValueAttribute, ns_text)
			if error == 0:
				return True, "Click + AXValueAttribute setting"
	except Exception as e:
		logger.warning(f"Click then set value failed: {e}")
	return False, ""

def _try_click_then_type_into(element, text: str) -> tuple[bool, str]:
	"""Try clicking element then using type_into"""
	from mlx_use.mac.actions import click, type_into
	
	try:
		click_result = click(element, 'AXConfirm')
		if click_result:
			result = type_into(element, text)
			if result:
				return True, "Click + type_into"
	except Exception as e:
		logger.warning(f"Click then type_into failed: {e}")
	return False, ""

def _try_fallback_type_into(element, text: str) -> tuple[bool, str]:
	"""Try fallback type_into method"""
	from mlx_use.mac.actions import type_into
	
	try:
		result = type_into(element, text)
		if result:
			return True, "Fallback type_into"
	except Exception as e:
		logger.warning(f"Fallback type_into failed: {e}")
	return False, ""

async def _handle_axconfirm_input(element, text: str) -> tuple[bool, str]:
	"""Handle text input for elements with AXConfirm action"""
	# Method 1: Direct attribute setting
	success, method = _try_direct_value_setting(element, text)
	if success:
		return success, method
	
	# Method 2: Click then set value
	success, method = await _try_click_then_set_value(element, text)
	if success:
		return success, method
	
	# Method 3: Click then type_into
	success, method = _try_click_then_type_into(element, text)
	if success:
		return success, method
	
	return False, ""

def _handle_axsetvalue_input(element, text: str) -> tuple[bool, str]:
	"""Handle text input for elements with AXSetValue action"""
	from mlx_use.mac.actions import type_into
	
	try:
		result = type_into(element, text)
		if result:
			return True, "type_into with AXSetValue"
	except Exception as e:
		logger.warning(f"AXSetValue method failed: {e}")
	return False, ""

def _create_text_input_response(success: bool, text: str, element, method_used: str, supported_action: str) -> dict:
	"""Create response for text input operation"""
	if success:
		return {
			"status": "success", 
			"message": f"Typed '{text}' into {element.role} using {method_used}",
			"element": {
				"role": element.role,
				"title": element.attributes.get('title', ''),
				"path": element.accessibility_path
			}
		}
	else:
		return {
			"status": "failed",
			"message": f"Failed to type into {element.role}. Tried methods for {supported_action}."
		}


@app.get("/")
async def read_root():
	"""Enhanced web interface with better UX"""
	return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
	<title>macOS UI Tree Explorer - Optimized</title>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<style>
		body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; background: #f8f9fa; }
		.container { max-width: 1600px; margin: 0 auto; }
		.header { background: white; padding: 20px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
		.section { background: white; padding: 20px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
		.apps-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
		.app-card { border: 2px solid #e9ecef; border-radius: 12px; padding: 16px; cursor: pointer; transition: all 0.3s ease; position: relative; }
		.app-card:hover { background: #f8f9ff; border-color: #007acc; transform: translateY(-2px); }
		.app-card.active { background: #e6f3ff; border-color: #007acc; border-width: 3px; }
		.app-card.loading::after { content: ''; position: absolute; top: 50%; right: 16px; width: 20px; height: 20px; border: 2px solid #007acc; border-top: 2px solid transparent; border-radius: 50%; animation: spin 1s linear infinite; }
		@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
		
		.tree-container { display: flex; gap: 24px; min-height: 600px; }
		.tree-panel { flex: 1.2; background: #f8f9fa; border-radius: 12px; padding: 20px; overflow-y: auto; max-height: 800px; }
		.element-details { flex: 0.8; background: #f8f9fa; border-radius: 12px; padding: 20px; overflow-y: auto; max-height: 800px; }
		
		.tree-node { margin-left: 24px; }
		.element-item { 
			padding: 10px 12px; margin: 3px 0; border-radius: 8px; cursor: pointer; 
			border: 2px solid transparent; transition: all 0.2s ease; position: relative;
			font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace; font-size: 13px;
		}
		.element-item:hover { background: #e3f2fd; }
		.element-item.interactive { background: #e8f5e8; border-color: #4CAF50; font-weight: 600; }
		.element-item.selected { background: #bbdefb; border-color: #1976d2; }
		.element-item.search-match { background: #fff3e0; border-color: #ff9800; box-shadow: 0 0 0 2px rgba(255, 152, 0, 0.3); }
		.element-item.search-highlight { background: #ffecb3; border-color: #ffc107; animation: pulse 2s infinite; }
		@keyframes pulse { 0%, 100% { box-shadow: 0 0 0 2px rgba(255, 193, 7, 0.4); } 50% { box-shadow: 0 0 0 6px rgba(255, 193, 7, 0.1); } }
		
		.search-controls { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; align-items: center; }
		.search-box { flex: 1; min-width: 300px; padding: 12px 16px; border: 2px solid #dee2e6; border-radius: 8px; font-size: 14px; }
		.search-box:focus { outline: none; border-color: #007acc; box-shadow: 0 0 0 3px rgba(0, 122, 204, 0.1); }
		
		.btn { padding: 12px 24px; background: #007acc; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.2s; }
		.btn:hover { background: #0056b3; transform: translateY(-1px); }
		.btn:active { transform: translateY(0); }
		.btn.secondary { background: #6c757d; }
		.btn.secondary:hover { background: #545b62; }
		.btn.success { background: #28a745; }
		.btn.success:hover { background: #1e7e34; }
		.btn.warning { background: #ffc107; color: #212529; }
		.btn.warning:hover { background: #e0a800; }
		.btn.active { background: #007acc !important; color: white !important; transform: scale(0.98); box-shadow: inset 0 2px 4px rgba(0,0,0,0.2); }
		.btn:disabled { background: #adb5bd; cursor: not-allowed; transform: none; }
		
		.status-bar { background: #e9ecef; padding: 8px 16px; border-radius: 6px; margin: 12px 0; font-size: 13px; }
		.status-success { background: #d4edda; color: #155724; }
		.status-error { background: #f8d7da; color: #721c24; }
		.status-info { background: #d1ecf1; color: #0c5460; }
		
		.loading-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
		.loading-spinner { background: white; padding: 40px; border-radius: 12px; text-align: center; }
		.spinner { border: 4px solid #f3f3f3; border-top: 4px solid #007acc; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 16px; }
		
		.attribute { margin: 6px 0; padding: 8px 12px; background: #f1f3f4; border-radius: 6px; border-left: 4px solid #007acc; }
		.expandable { cursor: pointer; user-select: none; }
		.expandable::before { content: '▶ '; transition: transform 0.2s; }
		.expandable.expanded::before { transform: rotate(90deg); }
		
		pre { background: #f8f9fa; padding: 16px; border-radius: 8px; overflow: auto; max-height: 300px; border: 1px solid #e9ecef; }
		.search-stats { font-size: 12px; color: #6c757d; margin-top: 8px; }
		
		.element-path { font-size: 11px; color: #6c757d; margin-top: 4px; font-family: 'SF Mono', monospace; }
		.highlight-index { background: #007acc; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; margin-left: 8px; }
	</style>
</head>
<body>
	<div class="container">
		<div class="header">
			<h1>🌳 macOS UI Tree Explorer</h1>
			<p>Interactive explorer with real automation capabilities. Click apps to activate them, then execute actions on UI elements!</p>
			<div style="font-size: 12px; color: #6c757d; margin-top: 8px;">
				<strong>Keyboard shortcuts:</strong> Cmd+F (search), Cmd+R (refresh), Cmd+A (activate app)
			</div>
		</div>

		<div class="section" id="apps-section">
			<div style="display: flex; justify-content: space-between; align-items: center;">
				<h2>Running Applications</h2>
				<button class="btn secondary" onclick="toggleAppsPanel()" id="toggle-apps-btn">📁 Collapse</button>
			</div>
			<div id="apps-panel" style="transition: all 0.3s ease;">
				<div style="margin-bottom: 16px;">
					<button class="btn" onclick="loadApps()">🔄 Refresh Apps</button>
					<button class="btn secondary" onclick="clearAllCaches()">🗑️ Clear Caches</button>
				</div>
				<div id="apps-container" class="apps-grid"></div>
			</div>
		</div>

		<div class="section">
			<div id="selected-app-info" style="display: none; background: #e6f3ff; border: 2px solid #007acc; border-radius: 8px; padding: 12px; margin-bottom: 16px;">
				<div style="display: flex; justify-content: space-between; align-items: center;">
					<div>
						<strong id="selected-app-name">App Name</strong>
						<span id="selected-app-details" style="color: #666; margin-left: 12px;">PID: 0000</span>
					</div>
					<div>
						<button class="btn secondary" onclick="activateCurrentApp()" style="padding: 6px 12px; font-size: 12px;">🎯 Activate</button>
						<button class="btn secondary" onclick="expandAppsPanel()" style="padding: 6px 12px; font-size: 12px;">📱 Change App</button>
					</div>
				</div>
			</div>
			
			<h2>UI Tree Explorer</h2>
			<div id="tree-section" style="display: none;">
				<div class="search-controls">
					<input type="text" id="search-input" class="search-box" placeholder="Search: 'nueva carpeta', 'button', 'AXPress'... (case-insensitive)" onkeypress="if(event.key==='Enter') searchElements()">
					<button class="btn" onclick="searchElements()" id="search-btn">🔍 Search</button>
					<button class="btn secondary" onclick="smartRefresh()" id="refresh-btn">🔄 Smart Refresh</button>
					<button class="btn success" onclick="loadInteractiveOnly()" id="interactive-btn">⚡ Interactive Only</button>
					<button class="btn warning" onclick="loadAllElements()" id="all-elements-btn">📋 All Elements</button>
					<button class="btn secondary" onclick="clearSearchCache()" id="clear-cache-btn">🗑️ Clear Cache</button>
				</div>
				<div id="status-bar" class="status-bar" style="display: none;"></div>
				<div class="tree-container">
					<div class="tree-panel">
						<h3>UI Tree Structure</h3>
						<div id="tree-container"></div>
					</div>
					<div class="element-details">
						<h3>Element Details</h3>
						<div id="element-details">Select an element to view detailed information</div>
					</div>
				</div>
			</div>
		</div>

		<div class="section">
			<h2>Advanced Query Builder</h2>
			<div id="query-section">
				<div class="search-controls">
					<select id="query-type" style="padding: 12px; border-radius: 8px; border: 2px solid #dee2e6;">
						<option value="role">By Role (AXButton, AXTextField, etc.)</option>
						<option value="title">By Title/Label</option>
						<option value="action">By Action (AXPress, AXConfirm, etc.)</option>
						<option value="text">By Any Text Content</option>
						<option value="custom">Custom Query</option>
					</select>
					<input type="text" id="query-value" class="search-box" placeholder="Enter query value..." onkeypress="if(event.key==='Enter') executeQuery()">
					<button class="btn" onclick="executeQuery()">🚀 Execute</button>
				</div>
				<div id="query-results"></div>
			</div>
		</div>
	</div>

	<!-- Loading overlay -->
	<div id="loading-overlay" class="loading-overlay" style="display: none;">
		<div class="loading-spinner">
			<div class="spinner"></div>
			<div id="loading-text">Loading...</div>
		</div>
	</div>

	<script>
		let currentAppPid = null;
		let currentAppInfo = null;
		let currentTree = null;
		let selectedElement = null;
		let searchResults = [];
		let appsPanelCollapsed = false;
		let lastTreeUpdate = 0;

		function showLoading(text = 'Loading...') {
			document.getElementById('loading-text').textContent = text;
			document.getElementById('loading-overlay').style.display = 'flex';
		}

		function hideLoading() {
			document.getElementById('loading-overlay').style.display = 'none';
		}

		function showStatus(message, type = 'info') {
			const statusBar = document.getElementById('status-bar');
			statusBar.className = `status-bar status-${type}`;
			statusBar.textContent = message;
			statusBar.style.display = 'block';
			setTimeout(() => statusBar.style.display = 'none', type === 'error' ? 8000 : 4000);
		}

		async function loadApps() {
			try {
				showLoading('Loading applications...');
				const response = await fetch('/api/apps');
				const apps = await response.json();
				
				const container = document.getElementById('apps-container');
				container.innerHTML = apps.map(app => `
					<div class="app-card" onclick="selectApp(${app.pid})" id="app-${app.pid}">
						<h3>${app.name}</h3>
						<p><strong>PID:</strong> ${app.pid}</p>
						<p><strong>Bundle ID:</strong> ${app.bundle_id}</p>
						<p><strong>Status:</strong> <span style="color: ${app.is_active ? '#28a745' : '#6c757d'}">${app.is_active ? '🟢 Active' : '⚪ Background'}</span></p>
					</div>
				`).join('');
				
				showStatus(`Loaded ${apps.length} applications`, 'success');
			} catch (error) {
				showStatus('Failed to load applications: ' + error.message, 'error');
			} finally {
				hideLoading();
			}
		}

		function toggleAppsPanel() {
			const panel = document.getElementById('apps-panel');
			const button = document.getElementById('toggle-apps-btn');
			
			if (appsPanelCollapsed) {
				// Expand
				panel.style.display = 'block';
				button.textContent = '📁 Collapse';
				appsPanelCollapsed = false;
			} else {
				// Collapse
				panel.style.display = 'none';
				button.textContent = '📱 Expand Apps';
				appsPanelCollapsed = true;
			}
		}
		
		function expandAppsPanel() {
			if (appsPanelCollapsed) {
				toggleAppsPanel();
			}
		}
		
		function collapseAppsPanel() {
			if (!appsPanelCollapsed) {
				toggleAppsPanel();
			}
		}
		
		function updateSelectedAppInfo(appInfo) {
			currentAppInfo = appInfo;
			document.getElementById('selected-app-name').textContent = appInfo.name;
			document.getElementById('selected-app-details').textContent = `PID: ${appInfo.pid} | Bundle: ${appInfo.bundle_id}`;
			document.getElementById('selected-app-info').style.display = 'block';
		}
		
		async function activateCurrentApp() {
			if (!currentAppPid) return;
			
			try {
				const response = await fetch(`/api/apps/${currentAppPid}/activate`, { method: 'POST' });
				if (response.ok) {
					const result = await response.json();
					showStatus(result.message, 'success');
				}
			} catch (error) {
				showStatus('Failed to activate app: ' + error.message, 'error');
			}
		}

		async function selectApp(pid) {
			if (currentAppPid === pid) return; // Already selected
			
			try {
				// Find app info
				const appsResponse = await fetch('/api/apps');
				const apps = await appsResponse.json();
				const appInfo = apps.find(app => app.pid === pid);
				
				if (!appInfo) {
					showStatus('Application not found', 'error');
					return;
				}
				
				// Update UI immediately
				document.querySelectorAll('.app-card').forEach(card => {
					card.classList.remove('active', 'loading');
				});
				const selectedCard = document.getElementById(`app-${pid}`);
				selectedCard.classList.add('active', 'loading');
				
				// Update selected app info
				updateSelectedAppInfo(appInfo);
				
				// Activate the app first
				showStatus(`Activating ${appInfo.name}...`, 'info');
				try {
					const activateResponse = await fetch(`/api/apps/${pid}/activate`, { method: 'POST' });
					if (activateResponse.ok) {
						const activateResult = await activateResponse.json();
						showStatus(activateResult.message, 'success');
					}
				} catch (error) {
					console.warn('Failed to activate app:', error);
				}
				
				currentAppPid = pid;
				document.getElementById('tree-section').style.display = 'block';
				
				// Auto-collapse apps panel for better focus
				setTimeout(() => {
					collapseAppsPanel();
				}, 1000);
				
				// Set default filter mode to interactive
				currentFilterMode = 'interactive';
				document.getElementById('interactive-btn').classList.add('active');
				document.getElementById('all-elements-btn').classList.remove('active');
				
				showStatus(`Loading UI tree for ${appInfo.name} (interactive elements only)...`, 'info');
				await loadTree(pid, false, true); // Load with interactive filter by default
				selectedCard.classList.remove('loading');
				
				showStatus(`${appInfo.name} ready! Interactive filter active - fewer errors, faster loading.`, 'success');
				
			} catch (error) {
				showStatus('Failed to select application: ' + error.message, 'error');
				document.getElementById(`app-${pid}`).classList.remove('loading');
			}
		}

		async function loadTree(pid, forceRefresh = false, interactiveOnly = true) {
			try {
				const params = new URLSearchParams();
				if (forceRefresh) params.append('force', 'true');
				params.append('interactive_only', interactiveOnly.toString());
				
				const url = `/api/apps/${pid}/tree${params.toString() ? '?' + params.toString() : ''}`;
				showLoading(`Building UI tree... ${interactiveOnly ? '(Interactive elements only - faster, fewer errors)' : '(All elements - may be slower)'}`);
				
				const startTime = Date.now();
				const response = await fetch(url);
				if (!response.ok) {
					throw new Error(`HTTP ${response.status}: ${response.statusText}`);
				}
				
				const tree = await response.json();
				const loadTime = Date.now() - startTime;
				
				currentTree = tree;
				lastTreeUpdate = Date.now();
				renderTree(tree);
				
				const filterMsg = interactiveOnly ? ' (Interactive only - reduced errors)' : ' (All elements)';
				showStatus(`Tree loaded successfully in ${loadTime}ms${filterMsg}`, 'success');
			} catch (error) {
				showStatus('Failed to load UI tree: ' + error.message, 'error');
				document.getElementById('tree-container').innerHTML = '<p style="color: #dc3545;">Failed to load tree. Check if app is still running.</p>';
			} finally {
				hideLoading();
			}
		}

		function renderTree(node, container = null, depth = 0) {
			if (!container) {
				container = document.getElementById('tree-container');
				container.innerHTML = '';
			}

			const element = node.element;
			const isInteractive = element.is_interactive;
			const highlight = element.highlight_index !== null ? `<span class="highlight-index">${element.highlight_index}</span>` : '';
			
			const elementDiv = document.createElement('div');
			elementDiv.className = `element-item ${isInteractive ? 'interactive' : ''}`;
			elementDiv.style.marginLeft = `${depth * 24}px`;
			elementDiv.onclick = (e) => { e.stopPropagation(); selectElement(element, elementDiv); };
			elementDiv.dataset.elementId = element.identifier;
			elementDiv.dataset.elementPath = element.path;
			
			const title = element.attributes.title || '';
			const value = element.attributes.value || '';
			const displayText = `${title} ${value}`.trim();
			const actions = element.actions.length > 0 ? ` (${element.actions.slice(0, 2).join(', ')})` : '';
			
			elementDiv.innerHTML = `
				<div>
					<strong>${element.role}</strong>${highlight} ${displayText}${actions}
					${isInteractive ? '<span style="color: #4CAF50; margin-left: 8px;">✓</span>' : ''}
				</div>
				<div class="element-path">${element.path}</div>
			`;
			
			container.appendChild(elementDiv);

			// Render children
			node.children.forEach(child => {
				renderTree(child, container, depth + 1);
			});
		}

		function selectElement(element, elementDiv) {
			selectedElement = element;
			
			// Update visual selection
			document.querySelectorAll('.element-item').forEach(el => el.classList.remove('selected'));
			elementDiv.classList.add('selected');
			
			// Show enhanced details
			const detailsContainer = document.getElementById('element-details');
			
			// Create action buttons for interactive elements
			let actionButtonsHtml = '';
			if (element.is_interactive && element.actions.length > 0) {
				actionButtonsHtml = `<div style="margin: 16px 0;">
					<strong>Execute Actions:</strong><br>`;
				
				// Regular action buttons
				element.actions.forEach(action => {
					if (action === 'AXSetValue') {
						// Special text input button
						actionButtonsHtml += `
							<button class="btn" style="margin: 4px 4px 4px 0; padding: 8px 12px; font-size: 12px; background: #28a745;" 
							 onclick="showTextInput('${element.path}')">
							 ✏️ ${action} (Type Text)
							 </button>`;
					} else if (action === 'AXConfirm' && element.role === 'AXTextField') {
						// Special text input button for AXConfirm text fields
						actionButtonsHtml += `
							<button class="btn" style="margin: 4px 4px 4px 0; padding: 8px 12px; font-size: 12px; background: #17a2b8;" 
							 onclick="showTextInput('${element.path}')">
							 ✏️ ${action} (Type Text)
							 </button>`;
					} else {
						actionButtonsHtml += `
							<button class="btn" style="margin: 4px 4px 4px 0; padding: 8px 12px; font-size: 12px;" 
							 onclick="executeElementAction('${element.path}', '${action}')">
							 🎯 ${action}
							 </button>`;
					}
				});
				
				actionButtonsHtml += `</div>`;
			}
			
			const actionsHtml = element.actions.length > 0 ? 
				element.actions.map(action => `<span style="background: #e3f2fd; padding: 4px 8px; border-radius: 4px; margin: 2px; display: inline-block;">${action}</span>`).join('') :
				'<span style="color: #6c757d;">None</span>';
				
			detailsContainer.innerHTML = `
				<div style="border-bottom: 2px solid #e9ecef; padding-bottom: 16px; margin-bottom: 16px;">
					<h4 style="margin: 0; color: #007acc;">${element.role}</h4>
					${element.highlight_index !== null ? `<span class="highlight-index">Index: ${element.highlight_index}</span>` : ''}
				</div>
				
				<div class="attribute"><strong>Interactive:</strong> ${element.is_interactive ? '✅ Yes' : '❌ No'}</div>
				<div class="attribute"><strong>Visible:</strong> ${element.is_visible ? '✅ Yes' : '❌ No'}</div>
				<div class="attribute"><strong>Children:</strong> ${element.children_count}</div>
				
				${actionButtonsHtml}
				
				<div style="margin: 16px 0;">
					<strong>Available Actions:</strong><br>
					${actionsHtml}
				</div>
				
				<div class="attribute">
					<strong>Accessibility Path:</strong><br>
					<code style="font-size: 11px; word-break: break-all;">${element.path}</code>
				</div>
				
				<div style="margin-top: 16px;">
					<div class="expandable" onclick="toggleAttributes(this)">
						<strong>All Attributes</strong>
					</div>
					<pre id="attributes-content" style="display: none; margin-top: 8px;">${JSON.stringify(element.attributes, null, 2)}</pre>
				</div>
			`;
		}

		function toggleAttributes(element) {
			const content = document.getElementById('attributes-content');
			const isVisible = content.style.display !== 'none';
			content.style.display = isVisible ? 'none' : 'block';
			element.classList.toggle('expanded', !isVisible);
		}

		async function searchElements() {
			const query = document.getElementById('search-input').value.trim();
			if (!query || !currentAppPid) {
				showStatus('Please enter a search query and select an application', 'error');
				return;
			}

			try {
				document.getElementById('search-btn').disabled = true;
				showStatus('Searching...', 'info');
				
				const startTime = Date.now();
				
				// Always search case-insensitive by default
				const searchParams = new URLSearchParams({
					q: query,
					case_sensitive: 'false'
				});
				
				const response = await fetch(`/api/apps/${currentAppPid}/search?${searchParams}`);
				
				if (!response.ok) {
					throw new Error(`HTTP ${response.status}: ${response.statusText}`);
				}
				
				const results = await response.json();
				const searchTime = Date.now() - startTime;
				
				searchResults = results.elements;
				
				// Clear previous highlights
				document.querySelectorAll('.element-item').forEach(el => {
					el.classList.remove('search-match', 'search-highlight');
				});

				if (results.elements.length === 0) {
					showStatus(`No elements found matching "${query}" (${searchTime}ms)`, 'error');
					console.log('Search debug: No results found');
					console.log('Query:', query);
					console.log('Response:', results);
					return;
				}

				// Highlight matching elements
				let highlightCount = 0;
				results.elements.forEach((element, index) => {
					const elementDiv = document.querySelector(`[data-element-path="${element.path}"]`);
					if (elementDiv) {
						elementDiv.classList.add('search-match');
						if (index === 0) {
							elementDiv.classList.add('search-highlight');
							elementDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
							// Auto-select first result
							selectElement(element, elementDiv);
						}
						highlightCount++;
					}
				});

				showStatus(`Found ${results.total_count} elements (${highlightCount} visible) in ${Math.round(results.search_time * 1000)}ms`, 'success');
				
				// Log successful search for debugging
				console.log(`Search success: "${query}" -> ${results.total_count} results`);
				
			} catch (error) {
				showStatus('Search failed: ' + error.message, 'error');
				console.error('Search error:', error);
			} finally {
				document.getElementById('search-btn').disabled = false;
			}
		}

		async function executeQuery() {
			const queryType = document.getElementById('query-type').value;
			const queryValue = document.getElementById('query-value').value.trim();
			
			if (!queryValue || !currentAppPid) {
				showStatus('Please enter a query value and select an application', 'error');
				return;
			}

			try {
				showLoading('Executing query...');
				
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
					resultsContainer.innerHTML = '<div class="status-bar status-error">No matching elements found</div>';
					return;
				}

				resultsContainer.innerHTML = `
					<div class="status-bar status-success">Found ${results.total_count} matching elements (${results.search_time.toFixed(1)}ms):</div>
					<div style="max-height: 400px; overflow-y: auto; border: 1px solid #e9ecef; border-radius: 8px; margin-top: 12px;">
						${results.elements.map((el, index) => `
							<div class="attribute" style="cursor: pointer; margin: 0; border-radius: 0; border-bottom: 1px solid #e9ecef;" onclick="highlightAndSelectElement('${el.path}')">
								<div style="display: flex; justify-content: space-between; align-items: center;">
									<div>
										<strong>${el.role}</strong> ${el.highlight_index !== null ? `<span class="highlight-index">${el.highlight_index}</span>` : ''}
										${el.attributes.title ? `<div style="font-size: 12px; color: #495057;">"${el.attributes.title}"</div>` : ''}
									</div>
									<div style="font-size: 11px; color: #6c757d;">${el.actions.slice(0, 2).join(', ')}</div>
								</div>
								<div style="font-size: 10px; color: #6c757d; margin-top: 4px; font-family: monospace;">${el.path}</div>
							</div>
						`).join('')}
					</div>
				`;
			} catch (error) {
				showStatus('Query failed: ' + error.message, 'error');
			} finally {
				hideLoading();
			}
		}

		function highlightAndSelectElement(path) {
			const elementDiv = document.querySelector(`[data-element-path="${path}"]`);
			if (elementDiv) {
				// Clear previous highlights
				document.querySelectorAll('.element-item').forEach(el => {
					el.classList.remove('search-highlight');
				});
				
				elementDiv.classList.add('search-highlight');
				elementDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
				elementDiv.click();
			}
		}

		async function expandInteractiveOnly() {
			if (!currentAppPid) return;
			
			try {
				showLoading('Loading interactive elements...');
				const response = await fetch(`/api/apps/${currentAppPid}/interactive`);
				const elements = await response.json();
				
				const container = document.getElementById('tree-container');
				container.innerHTML = '<h4 style="color: #007acc; margin-bottom: 16px;">Interactive Elements Only</h4>';
				
				elements.forEach(element => {
					const elementDiv = document.createElement('div');
					elementDiv.className = 'element-item interactive';
					elementDiv.onclick = () => selectElement(element, elementDiv);
					elementDiv.dataset.elementPath = element.path;
					
					const title = element.attributes.title || '';
					const actions = element.actions.slice(0, 2).join(', ');
					
					elementDiv.innerHTML = `
						<div>
							<strong>${element.role}</strong> <span class="highlight-index">${element.highlight_index}</span> ${title}
							<div style="font-size: 11px; color: #6c757d; margin-top: 4px;">Actions: ${actions}</div>
						</div>
					`;
					
					container.appendChild(elementDiv);
				});
				
				showStatus(`Showing ${elements.length} interactive elements`, 'success');
			} catch (error) {
				showStatus('Failed to load interactive elements: ' + error.message, 'error');
			} finally {
				hideLoading();
			}
		}

		// Filter mode control
		let currentFilterMode = 'interactive'; // 'interactive' or 'all'
		
		async function loadInteractiveOnly() {
			if (!currentAppPid) return;
			
			currentFilterMode = 'interactive';
			document.getElementById('interactive-btn').classList.add('active');
			document.getElementById('all-elements-btn').classList.remove('active');
			
			showStatus('Loading interactive elements only (faster, fewer errors)...', 'info');
			await loadTree(currentAppPid, false, true); // interactive_only = true
		}
		
		async function loadAllElements() {
			if (!currentAppPid) return;
			
			currentFilterMode = 'all';
			document.getElementById('all-elements-btn').classList.add('active');
			document.getElementById('interactive-btn').classList.remove('active');
			
			showStatus('Loading all elements (may be slower, more errors possible)...', 'warning');
			await loadTree(currentAppPid, true, false); // force refresh with all elements
		}

		async function smartRefresh() {
			if (!currentAppPid) return;
			
			const now = Date.now();
			const timeSinceLastUpdate = now - lastTreeUpdate;
			const interactiveOnly = currentFilterMode === 'interactive';
			
			// Use quick mode for recent updates, force refresh for older ones
			if (timeSinceLastUpdate < 2000) {
				showStatus('Using quick refresh (recent update)', 'info');
				await quickRefresh();
			} else if (timeSinceLastUpdate < 10000) {
				await loadTree(currentAppPid, false, interactiveOnly); // Use cache if available
			} else {
				await loadTree(currentAppPid, true, interactiveOnly); // Force refresh for old data
			}
		}
		
		async function quickRefresh() {
			if (!currentAppPid) return;
			
			try {
				const startTime = Date.now();
				const url = `/api/apps/${currentAppPid}/tree?quick=true`;
				
				const response = await fetch(url);
				if (!response.ok) {
					// Fallback to regular refresh
					await loadTree(currentAppPid, false);
					return;
				}
				
				const tree = await response.json();
				const loadTime = Date.now() - startTime;
				
				currentTree = tree;
				lastTreeUpdate = Date.now();
				renderTree(tree);
				
				showStatus(`Quick refresh completed in ${loadTime}ms`, 'success');
			} catch (error) {
				// Fallback to regular refresh
				await loadTree(currentAppPid, false);
			}
		}

		async function refreshTree() {
			if (currentAppPid) {
				await loadTree(currentAppPid, true);
			}
		}

		async function clearSearchCache() {
			try {
				showLoading('Clearing search cache...');
				await fetch('/api/cache/clear', { method: 'POST' });
				showStatus('Search cache cleared - try your search again!', 'success');
			} catch (error) {
				showStatus('Failed to clear cache: ' + error.message, 'error');
			} finally {
				hideLoading();
			}
		}

		async function clearAllCaches() {
			try {
				showLoading('Clearing caches...');
				await fetch('/api/cache/clear', { method: 'POST' });
				showStatus('Caches cleared successfully', 'success');
			} catch (error) {
				showStatus('Failed to clear caches: ' + error.message, 'error');
			} finally {
				hideLoading();
			}
		}

		async function showTextInput(elementPath) {
			const text = prompt('Enter text to type into this element:');
			if (text === null || text === '') return; // User cancelled or empty
			
			await executeTextInput(elementPath, text);
		}
		
		async function executeTextInput(elementPath, text) {
			if (!currentAppPid) {
				showStatus('No application selected', 'error');
				return;
			}
			
			try {
				showLoading(`Typing "${text}"...`);
				
				const response = await fetch(`/api/apps/${currentAppPid}/type`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						element_path: elementPath,
						text: text,
						confirm: true
					})
				});
				
				const result = await response.json();
				
				if (response.ok && result.status === 'success') {
					showStatus(`✅ ${result.message}`, 'success');
					
					// Smart refresh after typing to show changes
					setTimeout(async () => {
						await smartRefresh();
						showStatus('Tree updated to show text input', 'info');
					}, 800);
				} else {
					showStatus(`❌ ${result.message || 'Text input failed'}`, 'error');
				}
				
			} catch (error) {
				showStatus(`Failed to type text: ${error.message}`, 'error');
			} finally {
				hideLoading();
			}
		}

		async function executeElementAction(elementPath, action) {
			if (!currentAppPid) {
				showStatus('No application selected', 'error');
				return;
			}
			
			// Show confirmation for potentially dangerous actions
			const dangerousActions = ['AXPress', 'AXConfirm', 'AXCancel'];
			if (dangerousActions.includes(action)) {
				const confirmed = confirm(`Are you sure you want to execute "${action}" on this element? This will perform a real action in the application.`);
				if (!confirmed) return;
			}
			
			try {
				showLoading(`Executing ${action}...`);
				
				const response = await fetch(`/api/apps/${currentAppPid}/action`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						element_path: elementPath,
						action: action,
						confirm: true
					})
				});
				
				const result = await response.json();
				
				if (response.ok && result.status === 'success') {
					showStatus(`✅ ${result.message}`, 'success');
					
					// Smart refresh after action to show changes
					setTimeout(async () => {
						await smartRefresh();
						showStatus('Tree updated to show changes', 'info');
					}, 800);
				} else {
					showStatus(`❌ ${result.message || 'Action failed'}`, 'error');
				}
				
			} catch (error) {
				showStatus(`Failed to execute action: ${error.message}`, 'error');
			} finally {
				hideLoading();
			}
		}
		
		function highlightElementInTree(elementPath) {
			// Find and highlight element in tree view
			const elementDiv = document.querySelector(`[data-element-path="${elementPath}"]`);
			if (elementDiv) {
				// Remove previous highlights
				document.querySelectorAll('.element-item').forEach(el => {
					el.classList.remove('search-highlight');
				});
				
				elementDiv.classList.add('search-highlight');
				elementDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
			}
		}

		// Keyboard shortcuts
		document.addEventListener('keydown', (e) => {
			if (e.ctrlKey || e.metaKey) {
				switch (e.key) {
					case 'f':
						e.preventDefault();
						document.getElementById('search-input').focus();
						break;
					case 'r':
						e.preventDefault();
						refreshTree();
						break;
					case 'a':
						e.preventDefault();
						if (currentAppPid) {
							// Activate current app
							fetch(`/api/apps/${currentAppPid}/activate`, { method: 'POST' })
								.then(response => response.json())
								.then(result => showStatus(result.message, 'success'))
								.catch(error => showStatus('Failed to activate app', 'error'));
						}
						break;
				}
			}
		});

		// Load apps on page load
		loadApps();
	</script>
</body>
</html>
	""")

@app.get("/api/apps", response_model=List[AppInfo])
async def get_running_apps():
	"""Get list of running macOS applications with better filtering"""
	try:
		workspace = Cocoa.NSWorkspace.sharedWorkspace()
		apps = []
		
		for app in workspace.runningApplications():
			bundle_id = app.bundleIdentifier() or ""
			name = app.localizedName() or "Unknown"
			
			# Priority for Notes app - always include
			if bundle_id == 'com.apple.Notes':
				apps.append(_create_app_info(app))
				continue
			
			# Skip system processes and hidden apps
			if _should_exclude_system_process(bundle_id, name):
				continue
			
			apps.append(_create_app_info(app))
		
		# Sort by active status and name, but prioritize Notes
		apps.sort(key=_get_app_sort_key)
		return apps
		
	except Exception as e:
		logger.error(f"Error getting running apps: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/apps/{pid}/tree", response_model=TreeNode)
async def get_app_tree(pid: int, max_depth: int = None, force: bool = False, quick: bool = False, interactive_only: bool = True):
	"""Get UI tree with caching and incremental loading, filtered for interactive elements by default"""
	try:
		# Set appropriate default max_depth based on mode
		if max_depth is None:
			max_depth = 5 if interactive_only else 3
		
		# Build tree using the optimized tree manager
		tree = await tree_manager.build_tree(pid, force_refresh=force, lazy_mode=(not force))
		if not tree:
			raise HTTPException(status_code=404, detail="Could not build UI tree for application")
		
		# Get tree in JSON format
		tree_json = tree_manager.get_tree_json(pid, max_depth, interactive_only)
		if not tree_json:
			raise HTTPException(status_code=404, detail="Could not convert tree to JSON")
		
		return TreeNode(**tree_json)
		
	except Exception as e:
		logger.error(f"Error building tree for PID {pid}: {e}")
		# Clean up on error
		tree_manager.cleanup(pid)
		raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/apps/{pid}/expand")
async def expand_element(pid: int, element_path: str):
	"""Expand a specific element to load its children on-demand"""
	try:
		result = await tree_manager.expand_element(pid, element_path)
		if not result:
			raise HTTPException(status_code=404, detail=ELEMENT_NOT_FOUND_ERROR)
		
		return result
		
	except Exception as e:
		logger.error(f"Error expanding element for PID {pid}: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/apps/{pid}/search", response_model=ElementSearchResult)
async def search_elements_optimized(pid: int, q: str, case_sensitive: bool = False):
	"""Optimized search with caching"""
	try:
		result = await tree_manager.search_elements(pid, q, case_sensitive)
		return ElementSearchResult(**result)
		
	except Exception as e:
		logger.error(f"Error searching elements: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/apps/{pid}/query", response_model=ElementSearchResult)
async def query_elements_optimized(pid: int, query: QueryRequest):
	"""Enhanced query with better performance"""
	try:
		start_time = time.time()
		
		await tree_manager.build_tree(pid)
		elements = tree_manager.get_flattened_elements(pid)
		matching_elements = []
		
		for element in elements:
			# Extract target text based on query type
			if query.query_type == "role":
				target = element.get("role", "")
			elif query.query_type == "title":
				target = str(element.get("attributes", {}).get("title", ""))
			elif query.query_type == "action":
				target = " ".join(element.get("actions", []))
			elif query.query_type == "text":
				parts = [
					element.get("role", ""),
					str(element.get("attributes", {}).get("title", "")),
					str(element.get("attributes", {}).get("value", "")),
					str(element.get("attributes", {}).get("description", ""))
				]
				target = " ".join(str(part) for part in parts if part)
			else:  # custom
				target = json.dumps(element)
			
			# Normalize for comparison
			if not query.case_sensitive:
				target = target.lower()
				search_value = query.query_value.lower()
			else:
				search_value = query.query_value
			
			if search_value in target:
				matching_elements.append(element)
		
		search_time = time.time() - start_time
		return ElementSearchResult(
			elements=matching_elements,
			total_count=len(matching_elements),
			search_time=search_time
		)
		
	except Exception as e:
		logger.error(f"Error querying elements: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/apps/{pid}/interactive")
async def get_interactive_elements_cached(pid: int):
	"""Get interactive elements with caching"""
	try:
		await tree_manager.build_tree(pid)
		interactive_elements = tree_manager.get_interactive_elements(pid)
		return interactive_elements
		
	except Exception as e:
		logger.error(f"Error getting interactive elements: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/apps/{pid}/activate")
async def activate_app(pid: int):
	"""Activate and bring app to front"""
	try:
		workspace = Cocoa.NSWorkspace.sharedWorkspace()
		
		# Find the app by PID
		target_app = None
		for app in workspace.runningApplications():
			if app.processIdentifier() == pid:
				target_app = app
				break
		
		if not target_app:
			raise HTTPException(status_code=404, detail=f"App with PID {pid} not found")
		
		# Activate the app
		success = target_app.activateWithOptions_(Cocoa.NSApplicationActivateIgnoringOtherApps)
		
		if success:
			# Wait a moment for activation
			await asyncio.sleep(0.5)
			return {"status": "success", "message": f"App {target_app.localizedName()} activated"}
		else:
			raise HTTPException(status_code=500, detail="Failed to activate app")
			
	except Exception as e:
		logger.error(f"Error activating app {pid}: {e}")
		raise HTTPException(status_code=500, detail=str(e))

class ActionRequest(BaseModel):
	element_path: str
	action: str
	confirm: bool = False

class TypeRequest(BaseModel):
	element_path: str
	text: str
	confirm: bool = False

@app.post("/api/apps/{pid}/action")
async def execute_action(pid: int, request: ActionRequest):
	"""Execute an action on a UI element"""
	try:
		# Ensure we have current tree
		await tree_manager.build_tree(pid)
		
		# Find element by path
		target_element = tree_manager.find_element_by_path(pid, request.element_path)
		if not target_element:
			raise HTTPException(status_code=404, detail=ELEMENT_NOT_FOUND_ERROR)
		
		# Check if element supports the action
		if request.action not in target_element.actions:
			raise HTTPException(
				status_code=400, 
				detail=f"Element does not support action '{request.action}'. Available: {target_element.actions}"
			)
		
		# Import action functions
		from mlx_use.mac.actions import click
		
		# Execute the action
		result = False
		if request.action == 'AXPress':
			result = click(target_element, 'AXPress')
		elif request.action == 'AXConfirm':
			result = click(target_element, 'AXConfirm')
		elif request.action == 'AXCancel':
			result = click(target_element, 'AXCancel')
		# Add more actions as needed
		
		if result:
			# Invalidate cache after action to get fresh tree
			tree_manager.invalidate_cache(pid)
			return {
				"status": "success", 
				"message": f"Action '{request.action}' executed on {target_element.role}",
				"element": {
					"role": target_element.role,
					"title": target_element.attributes.get('title', ''),
					"path": target_element.accessibility_path
				}
			}
		else:
			return {
				"status": "failed",
				"message": f"Action '{request.action}' failed on {target_element.role}"
			}
			
	except Exception as e:
		logger.error(f"Error executing action: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/apps/{pid}/type")
async def type_text(pid: int, request: TypeRequest):
	"""Type text into a UI element"""
	try:
		# Ensure we have current tree
		await tree_manager.build_tree(pid)
		
		# Find element by path
		target_element = tree_manager.find_element_by_path(pid, request.element_path)
		if not target_element:
			raise HTTPException(status_code=404, detail=ELEMENT_NOT_FOUND_ERROR)
		
		# Check if element supports text input
		supported_action = _find_supported_text_input_action(target_element.actions)
		if not supported_action:
			raise HTTPException(
				status_code=400, 
				detail=f"Element does not support text input. Available actions: {target_element.actions}"
			)
		
		# Execute text input based on supported action
		result = False
		method_used = ""
		
		try:
			if supported_action == 'AXSetValue':
				result, method_used = _handle_axsetvalue_input(target_element, request.text)
			elif supported_action == 'AXConfirm':
				result, method_used = await _handle_axconfirm_input(target_element, request.text)
				# Try fallback if all methods failed
				if not result:
					result, method_used = _try_fallback_type_into(target_element, request.text)
			
		except Exception as e:
			logger.error(f"All text input methods failed: {e}")
		
		if result:
			# Invalidate cache after typing to get fresh tree
			tree_manager.invalidate_cache(pid)
		
		return _create_text_input_response(result, request.text, target_element, method_used, supported_action)
			
	except Exception as e:
		logger.error(f"Error typing text: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/apps/{pid}/element/{highlight_index}")
async def get_element_by_index(pid: int, highlight_index: int):
	"""Get element details by highlight index"""
	try:
		# Ensure we have current tree
		await tree_manager.build_tree(pid)
		
		# Find element by highlight index from flattened elements
		elements = tree_manager.get_flattened_elements(pid)
		for element in elements:
			if element.get("highlight_index") == highlight_index:
				return element
		
		raise HTTPException(status_code=404, detail=f"Element with index {highlight_index} not found")
		
	except Exception as e:
		logger.error(f"Error getting element by index: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/performance/stats")
async def get_performance_stats():
	"""Get performance statistics and cache information"""
	try:
		return tree_manager.get_performance_stats()
	except Exception as e:
		logger.error(f"Error getting performance stats: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cache/clear")
async def clear_caches():
	"""Clear all caches"""
	try:
		tree_manager.clear_all_caches()
		return {"status": "success", "message": "All caches cleared"}
		
	except Exception as e:
		logger.error(f"Error clearing caches: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.on_event("shutdown")
async def shutdown_event():
	"""Enhanced cleanup on server shutdown"""
	# Cleanup will be handled by the tree_manager
	pass

if __name__ == "__main__":
	import uvicorn
	
	print("🚀 Starting Optimized macOS UI Tree Explorer...")
	print("📖 Open http://localhost:8000 in your browser")
	print("⚡ Features: Intelligent caching, incremental loading, enhanced search")
	print("🔍 Try searching for 'Nueva Carpeta' in Notes app")
	
	uvicorn.run(
		"optimized_server:app", 
		host="0.0.0.0", 
		port=8000, 
		reload=True,
		log_level="info"
	)