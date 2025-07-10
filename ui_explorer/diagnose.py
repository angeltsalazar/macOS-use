#!/usr/bin/env python3
"""
Diagnostic script to test UI tree building directly
"""

import asyncio
import json

import Cocoa

from mlx_use.mac.tree import MacUITreeBuilder


async def diagnose_notes():
	"""Diagnose Notes app tree building"""
	
	print("🔍 Diagnosing Notes app UI tree...")
	
	# Find Notes app - look for the main Notes app bundle
	workspace = Cocoa.NSWorkspace.sharedWorkspace()
	notes_app = None
	
	for app in workspace.runningApplications():
		if app.bundleIdentifier() == 'com.apple.Notes':
			notes_app = app
			break
	
	if not notes_app:
		print("❌ Notes app not found. Please open Notes first.")
		print("Looking for any Notes-related process...")
		for app in workspace.runningApplications():
			if app.localizedName() and 'notes' in app.localizedName().lower():
				notes_app = app
				print(f"Found: {app.localizedName()} - {app.bundleIdentifier()}")
				break
	
	if not notes_app:
		print("❌ No Notes process found.")
		return
	
	pid = notes_app.processIdentifier()
	print(f"📝 Found Notes app: PID {pid}")
	print(f"    Name: {notes_app.localizedName()}")
	print(f"    Bundle: {notes_app.bundleIdentifier()}")
	print(f"    Active: {notes_app.isActive()}")
	
	# Create builder with verbose logging
	builder = MacUITreeBuilder()
	builder.max_children = 200
	builder.max_depth = 20
	
	print(f"\n🌳 Building tree with limits: depth={builder.max_depth}, children={builder.max_children}")
	
	try:
		tree = await builder.build_tree(pid)
		
		if not tree:
			print("❌ Failed to build tree")
			return
		
		print("✅ Tree built successfully")
		print(f"    Root: {tree.role}")
		print(f"    Root children: {len(tree.children)}")
		
		# Analyze tree structure
		def analyze_tree(node, depth=0, max_depth=5):
			info = {
				'role': node.role,
				'children_count': len(node.children),
				'is_interactive': node.is_interactive,
				'highlight_index': node.highlight_index,
				'actions': node.actions,
				'attributes': {}
			}
			
			# Safe attribute extraction
			if node.attributes:
				for key, value in node.attributes.items():
					try:
						json.dumps(value)  # Test serializability
						info['attributes'][key] = value
					except:
						info['attributes'][key] = str(value)
			
			if depth < max_depth and node.children:
				info['children'] = [analyze_tree(child, depth + 1, max_depth) for child in node.children[:3]]
			
			return info
		
		tree_info = analyze_tree(tree)
		
		print("\n📊 Tree Analysis:")
		print(json.dumps(tree_info, indent=2, default=str)[:2000] + "...")
		
		# Count elements by type
		def count_elements(node, counts=None):
			if counts is None:
				counts = {'total': 0, 'interactive': 0, 'by_role': {}}
			
			counts['total'] += 1
			if node.is_interactive:
				counts['interactive'] += 1
			
			role = node.role
			counts['by_role'][role] = counts['by_role'].get(role, 0) + 1
			
			for child in node.children:
				count_elements(child, counts)
			
			return counts
		
		counts = count_elements(tree)
		
		print("\n📈 Element Counts:")
		print(f"    Total elements: {counts['total']}")
		print(f"    Interactive elements: {counts['interactive']}")
		print("    Top roles:")
		
		sorted_roles = sorted(counts['by_role'].items(), key=lambda x: x[1], reverse=True)
		for role, count in sorted_roles[:10]:
			print(f"      {role}: {count}")
		
		# Search for specific elements
		def search_elements(node, query, results=None):
			if results is None:
				results = []
			
			searchable_text = " ".join([
				node.role,
				node.attributes.get('title', '') if node.attributes else '',
				node.attributes.get('value', '') if node.attributes else '',
				node.attributes.get('description', '') if node.attributes else '',
				" ".join(node.actions) if node.actions else ''
			]).lower()
			
			if query.lower() in searchable_text:
				results.append({
					'role': node.role,
					'title': node.attributes.get('title', '') if node.attributes else '',
					'is_interactive': node.is_interactive,
					'highlight_index': node.highlight_index,
					'actions': node.actions,
					'searchable_text': searchable_text
				})
			
			for child in node.children:
				search_elements(child, query, results)
			
			return results
		
		# Test searches
		queries = ['nueva carpeta', 'folder', 'button', 'carpeta', 'nueva']
		
		print("\n🔍 Search Tests:")
		for query in queries:
			results = search_elements(tree, query)
			print(f"    '{query}': {len(results)} results")
			for result in results[:3]:  # Show first 3 results
				print(f"      - {result['role']} '{result['title']}' interactive={result['is_interactive']}")
		
	except Exception as e:
		print(f"❌ Error: {e}")
		import traceback
		traceback.print_exc()
	finally:
		builder.cleanup()

if __name__ == "__main__":
	asyncio.run(diagnose_notes())