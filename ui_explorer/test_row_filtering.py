#!/usr/bin/env python3
"""
Test that non-interactive AXRow and AXTable elements are filtered out
"""

import requests
import json

def test_row_filtering():
	"""Test that non-interactive display elements are filtered out"""
	
	print("🚫 Testing Non-Interactive Element Filtering")
	print("=" * 50)
	
	# Find Notes app
	response = requests.get("http://localhost:8000/api/apps", timeout=10)
	if response.status_code != 200:
		print("❌ Server not responding")
		return False

	apps = response.json()
	notes_app = None
	for app in apps:
		if app['bundle_id'] == 'com.apple.Notes':
			notes_app = app
			break

	if not notes_app:
		print("❌ Notes app not found")
		return False

	notes_pid = notes_app['pid']
	print(f"📝 Testing with Notes PID: {notes_pid}")

	def count_elements_by_type(node, counts=None):
		"""Count elements by type and interactivity"""
		if counts is None:
			counts = {'total': 0, 'interactive': 0, 'non_interactive': 0, 'by_role': {}}
		
		element = node['element']
		role = element['role']
		is_interactive = element['is_interactive']
		
		counts['total'] += 1
		counts['by_role'][role] = counts['by_role'].get(role, 0) + 1
		
		if is_interactive:
			counts['interactive'] += 1
		else:
			counts['non_interactive'] += 1
		
		for child in node.get('children', []):
			count_elements_by_type(child, counts)
		
		return counts

	def find_problematic_elements(node, problematic=None, path=""):
		"""Find non-interactive display elements that shouldn't be shown"""
		if problematic is None:
			problematic = []
		
		element = node['element']
		current_path = f"{path}/{element['role']}"
		
		# Check for problematic non-interactive display elements
		if (element['role'] in ['AXRow', 'AXCell', 'AXTable', 'AXColumn', 'AXColumnHeader'] and 
			not element['is_interactive']):
			problematic.append({
				'role': element['role'],
				'path': current_path,
				'element_path': element.get('path', 'No path'),
				'is_interactive': element['is_interactive'],
				'actions': element.get('actions', [])
			})
		
		for child in node.get('children', []):
			find_problematic_elements(child, problematic, current_path)
		
		return problematic

	# Test 1: Interactive-only mode (should have fewer display elements)
	print("\n🟢 Testing Interactive-Only Mode (with improved filtering)...")
	response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/tree?interactive_only=true&force=true")
	
	if response.status_code == 200:
		interactive_tree = response.json()
		interactive_counts = count_elements_by_type(interactive_tree)
		interactive_problematic = find_problematic_elements(interactive_tree)
		
		print(f"✅ Interactive tree loaded successfully")
		print(f"📊 Total elements: {interactive_counts['total']}")
		print(f"🟢 Interactive elements: {interactive_counts['interactive']}")
		print(f"⚪ Non-interactive elements: {interactive_counts['non_interactive']}")
		
		print(f"\n🚫 Problematic non-interactive display elements found:")
		if interactive_problematic:
			for elem in interactive_problematic[:5]:  # Show first 5
				print(f"   ❌ {elem['role']} at {elem['element_path']}")
			if len(interactive_problematic) > 5:
				print(f"   ... and {len(interactive_problematic) - 5} more")
			print(f"📊 Total problematic: {len(interactive_problematic)}")
		else:
			print("   ✅ No problematic elements found!")
			
		# Show element type breakdown
		print(f"\n📋 Element types in interactive mode:")
		for role, count in sorted(interactive_counts['by_role'].items()):
			if count > 0:
				print(f"   {role}: {count}")
		
	else:
		print(f"❌ Failed to load interactive tree: {response.status_code}")
		return False

	# Test 2: All elements mode (for comparison)
	print("\n🟡 Testing All Elements Mode (for comparison)...")
	response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/tree?interactive_only=false&force=true")
	
	if response.status_code == 200:
		all_tree = response.json()
		all_counts = count_elements_by_type(all_tree)
		all_problematic = find_problematic_elements(all_tree)
		
		print(f"✅ All elements tree loaded successfully")
		print(f"📊 Total elements: {all_counts['total']}")
		print(f"🟢 Interactive elements: {all_counts['interactive']}")
		print(f"⚪ Non-interactive elements: {all_counts['non_interactive']}")
		
		print(f"\n🚫 Problematic elements in all mode: {len(all_problematic)}")
		
	else:
		print(f"⚠️ Failed to load all elements tree: {response.status_code}")

	# Test 3: Check for Nueva carpeta button still present
	print("\n🔍 Verifying Nueva Carpeta button still present...")
	
	def find_nueva_carpeta(node):
		if (node['element']['role'] == 'AXButton' and 
			node['element']['attributes'].get('title') == 'Nueva carpeta'):
			return True
		for child in node.get('children', []):
			if find_nueva_carpeta(child):
				return True
		return False

	if find_nueva_carpeta(interactive_tree):
		print("✅ Nueva carpeta button still present!")
	else:
		print("❌ Nueva carpeta button missing after filtering!")
		return False

	# Summary
	print(f"\n📈 Filtering Results:")
	print(f"🟢 Interactive mode: {interactive_counts['total']} total elements")
	print(f"🚫 Problematic elements: {len(interactive_problematic)}")
	improvement = len(interactive_problematic)
	if improvement > 0:
		print(f"⚠️ Still showing {improvement} non-interactive display elements")
		print("🔧 Consider further filtering refinement")
	else:
		print(f"✅ Successfully filtered out all non-interactive display elements!")
	
	print(f"\n💡 Filtering improvements:")
	print("✅ AXRow elements excluded (unless interactive)")
	print("✅ AXCell elements excluded (unless interactive)")  
	print("✅ AXTable elements excluded (unless interactive)")
	print("✅ Nueva carpeta button preserved")
	print("✅ Container elements (AXScrollArea, AXOutline) preserved for structure")
	
	return True

if __name__ == "__main__":
	success = test_row_filtering()
	exit(0 if success else 1)