#!/usr/bin/env python3
"""
Quick test script to verify the UI Tree Explorer functionality
"""

import asyncio
import sys
import time
from mlx_use.mac.tree import MacUITreeBuilder
import Cocoa

async def test_notes_app():
	"""Test finding 'Nueva Carpeta' button in Notes app"""
	
	# Find Notes app
	workspace = Cocoa.NSWorkspace.sharedWorkspace()
	notes_app = None
	
	for app in workspace.runningApplications():
		if app.localizedName() and 'notes' in app.localizedName().lower():
			notes_app = app
			break
	
	if not notes_app:
		print("❌ Notes app not found. Please open Notes app first.")
		return
	
	print(f"✅ Found Notes app: PID {notes_app.processIdentifier()}")
	
	# Build tree
	builder = MacUITreeBuilder()
	builder.max_children = 50
	builder.max_depth = 8
	
	print("🔍 Building UI tree...")
	start_time = time.time()
	
	tree = await builder.build_tree(notes_app.processIdentifier())
	build_time = time.time() - start_time
	
	if not tree:
		print("❌ Failed to build tree")
		return
	
	print(f"✅ Tree built in {build_time:.2f}s")
	
	# Search for "Nueva Carpeta"
	print("\n🔍 Searching for 'Nueva Carpeta'...")
	
	def search_element(node, query="nueva carpeta"):
		results = []
		
		# Check current node
		searchable = " ".join([
			node.role,
			node.attributes.get('title', ''),
			node.attributes.get('value', ''),
			node.attributes.get('description', ''),
			" ".join(node.actions)
		]).lower()
		
		if query in searchable:
			results.append(node)
		
		# Search children
		for child in node.children:
			results.extend(search_element(child, query))
		
		return results
	
	results = search_element(tree)
	
	print(f"📊 Search Results: {len(results)} elements found")
	for i, element in enumerate(results):
		print(f"  {i+1}. {element.role} - {element.attributes.get('title', 'No title')}")
		print(f"     Interactive: {element.is_interactive}")
		print(f"     Actions: {', '.join(element.actions)}")
		print(f"     Index: {element.highlight_index}")
		print()
	
	# Count all interactive elements
	def count_interactive(node):
		count = 1 if node.is_interactive else 0
		for child in node.children:
			count += count_interactive(child)
		return count
	
	interactive_count = count_interactive(tree)
	print(f"📈 Total interactive elements: {interactive_count}")
	
	builder.cleanup()

if __name__ == "__main__":
	print("🧪 Testing macOS UI Tree Explorer")
	print("Make sure Notes app is open before running this test")
	print()
	
	asyncio.run(test_notes_app())