#!/usr/bin/env python3
"""
Simple macOS UI Tree Explorer Server

Minimal version for testing and debugging serialization issues.
"""

import asyncio
import logging
import json
from typing import Optional, List, Dict, Any

import Cocoa
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from mlx_use.mac.tree import MacUITreeBuilder
from mlx_use.mac.element import MacElementNode

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Simple macOS UI Tree Explorer", version="1.0.0")

# Global state
current_builder = None
current_tree = None

class AppInfo(BaseModel):
	pid: int
	name: str
	bundle_id: str

class SimpleElementInfo(BaseModel):
	role: str
	title: str
	is_interactive: bool
	highlight_index: Optional[int]
	actions: List[str]
	children_count: int

def safe_serialize(obj) -> Any:
	"""Safely serialize any object to JSON-compatible format"""
	if obj is None:
		return None
	elif isinstance(obj, (str, int, float, bool)):
		return obj
	elif isinstance(obj, (list, tuple)):
		return [safe_serialize(item) for item in obj]
	elif isinstance(obj, dict):
		return {key: safe_serialize(value) for key, value in obj.items()}
	else:
		# Convert anything else to string
		return str(obj)

def convert_element_simple(element: MacElementNode) -> SimpleElementInfo:
	"""Convert element to simple, safe format"""
	title = ""
	if element.attributes:
		title = safe_serialize(element.attributes.get('title', '')) or ""
		if not title:
			title = safe_serialize(element.attributes.get('value', '')) or ""
	
	return SimpleElementInfo(
		role=element.role,
		title=title,
		is_interactive=element.is_interactive,
		highlight_index=element.highlight_index,
		actions=element.actions or [],
		children_count=len(element.children)
	)

@app.get("/")
async def read_root():
	return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
	<title>Simple macOS UI Tree Explorer</title>
	<style>
		body { font-family: Arial, sans-serif; margin: 20px; }
		.app { border: 1px solid #ccc; padding: 10px; margin: 10px; cursor: pointer; }
		.app:hover { background: #f0f0f0; }
		.element { margin: 5px 0; padding: 5px; border-left: 3px solid #ccc; }
		.interactive { border-left-color: #4CAF50; background: #f0f8f0; }
		.search { margin: 20px 0; }
		input { padding: 8px; width: 300px; }
		button { padding: 8px 16px; }
	</style>
</head>
<body>
	<h1>🌳 Simple macOS UI Tree Explorer</h1>
	
	<h2>Applications</h2>
	<button onclick="loadApps()">Load Apps</button>
	<div id="apps"></div>
	
	<h2>UI Tree</h2>
	<div class="search">
		<input type="text" id="searchInput" placeholder="Search for elements...">
		<button onclick="searchElements()">Search</button>
	</div>
	<div id="tree"></div>
	
	<script>
		let currentPid = null;
		
		async function loadApps() {
			const response = await fetch('/api/apps');
			const apps = await response.json();
			
			document.getElementById('apps').innerHTML = apps.map(app => 
				`<div class="app" onclick="selectApp(${app.pid})">
					<strong>${app.name}</strong> (PID: ${app.pid})
				</div>`
			).join('');
		}
		
		async function selectApp(pid) {
			currentPid = pid;
			document.getElementById('tree').innerHTML = 'Loading...';
			
			try {
				const response = await fetch(`/api/apps/${pid}/elements`);
				const elements = await response.json();
				
				document.getElementById('tree').innerHTML = elements.map(el => 
					`<div class="element ${el.is_interactive ? 'interactive' : ''}">
						<strong>${el.role}</strong> ${el.highlight_index !== null ? `[${el.highlight_index}]` : ''} 
						${el.title} ${el.actions.length > 0 ? `(${el.actions.join(', ')})` : ''}
					</div>`
				).join('');
			} catch (error) {
				document.getElementById('tree').innerHTML = 'Error: ' + error.message;
			}
		}
		
		async function searchElements() {
			const query = document.getElementById('searchInput').value;
			if (!query || !currentPid) return;
			
			try {
				const response = await fetch(`/api/apps/${currentPid}/search?q=${encodeURIComponent(query)}`);
				const results = await response.json();
				
				document.getElementById('tree').innerHTML = 
					`<h3>Search Results (${results.length}):</h3>` +
					results.map(el => 
						`<div class="element ${el.is_interactive ? 'interactive' : ''}">
							<strong>${el.role}</strong> ${el.highlight_index !== null ? `[${el.highlight_index}]` : ''} 
							${el.title} ${el.actions.length > 0 ? `(${el.actions.join(', ')})` : ''}
						</div>`
					).join('');
			} catch (error) {
				document.getElementById('tree').innerHTML = 'Search error: ' + error.message;
			}
		}
		
		loadApps();
	</script>
</body>
</html>
	""")

@app.get("/api/apps")
async def get_apps():
	"""Get running applications"""
	try:
		workspace = Cocoa.NSWorkspace.sharedWorkspace()
		apps = []
		
		for app in workspace.runningApplications():
			if app.localizedName():
				apps.append(AppInfo(
					pid=app.processIdentifier(),
					name=app.localizedName(),
					bundle_id=app.bundleIdentifier() or "Unknown"
				))
		
		return sorted(apps, key=lambda x: x.name.lower())
	except Exception as e:
		logger.error(f"Error getting apps: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/apps/{pid}/elements")
async def get_elements(pid: int):
	"""Get all elements for an app"""
	global current_builder, current_tree
	
	try:
		# Create fresh builder
		if current_builder:
			current_builder.cleanup()
		
		current_builder = MacUITreeBuilder()
		current_builder.max_children = 100  # Increased
		current_builder.max_depth = 15     # Increased
		
		logger.info(f"Building tree for PID {pid}")
		
		# Build tree
		current_tree = await current_builder.build_tree(pid)
		if not current_tree:
			logger.error(f"Failed to build tree for PID {pid}")
			raise HTTPException(status_code=404, detail="Could not build tree")
		
		logger.info(f"Tree root: {current_tree.role}, children: {len(current_tree.children)}")
		
		# Flatten tree
		elements = []
		def collect_elements(node, depth=0):
			try:
				elements.append(convert_element_simple(node))
				logger.debug(f"{'  ' * depth}{node.role} ({len(node.children)} children)")
				for child in node.children:
					collect_elements(child, depth + 1)
			except Exception as e:
				logger.warning(f"Error processing element at depth {depth}: {e}")
		
		collect_elements(current_tree)
		logger.info(f"Collected {len(elements)} total elements")
		
		# Count interactive elements
		interactive_count = sum(1 for e in elements if e.is_interactive)
		logger.info(f"Interactive elements: {interactive_count}")
		
		return elements
		
	except Exception as e:
		logger.error(f"Error getting elements for PID {pid}: {e}")
		import traceback
		traceback.print_exc()
		raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/apps/{pid}/search")
async def search_elements(pid: int, q: str):
	"""Search elements"""
	try:
		# Get elements first
		elements = await get_elements(pid)
		
		query = q.lower()
		results = []
		
		logger.info(f"Searching {len(elements)} elements for '{query}'")
		
		for element in elements:
			searchable = f"{element.role} {element.title} {' '.join(element.actions)}".lower()
			if query in searchable:
				results.append(element)
				logger.info(f"Match found: {element.role} - {element.title}")
		
		logger.info(f"Search completed: {len(results)} results")
		return results
		
	except Exception as e:
		logger.error(f"Search error: {e}")
		raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/apps/{pid}/debug")
async def debug_tree(pid: int):
	"""Debug tree structure"""
	global current_tree
	
	if not current_tree:
		# Build tree first
		await get_elements(pid)
	
	def tree_to_dict(node, depth=0):
		if depth > 10:  # Prevent infinite recursion
			return {"role": node.role, "title": "...", "truncated": True}
		
		title = ""
		if node.attributes:
			title = safe_serialize(node.attributes.get('title', '')) or ""
			if not title:
				title = safe_serialize(node.attributes.get('value', '')) or ""
		
		return {
			"role": node.role,
			"title": title,
			"is_interactive": node.is_interactive,
			"highlight_index": node.highlight_index,
			"actions": node.actions or [],
			"children_count": len(node.children),
			"children": [tree_to_dict(child, depth + 1) for child in node.children[:5]]  # Limit to first 5 children
		}
	
	return tree_to_dict(current_tree)

@app.on_event("shutdown")
async def shutdown():
	global current_builder
	if current_builder:
		current_builder.cleanup()

if __name__ == "__main__":
	import uvicorn
	
	print("🌳 Starting Simple macOS UI Tree Explorer...")
	print("📖 Open http://localhost:8001 in your browser")
	
	uvicorn.run(
		"simple_server:app", 
		host="0.0.0.0", 
		port=8001, 
		reload=False,
		log_level="info"
	)