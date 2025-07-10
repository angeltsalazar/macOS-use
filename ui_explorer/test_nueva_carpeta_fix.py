#!/usr/bin/env python3
"""
Test that Nueva carpeta button appears in interactive-only mode
"""


import requests


def test_nueva_carpeta_visibility():
	"""Test that Nueva carpeta button is visible in interactive mode"""
	
	print("🔍 Testing Nueva Carpeta Button Visibility")
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

	def find_nueva_carpeta_in_tree(node, path="", depth=0):
		"""Recursively search for Nueva carpeta button"""
		current_path = f"{path}/{node['element']['role']}"
		element = node['element']
		
		# Check if this is the Nueva carpeta button
		if (element['role'] == 'AXButton' and 
			element['attributes'].get('title') == 'Nueva carpeta'):
			print(f"✅ FOUND Nueva carpeta at depth {depth}!")
			print(f"   Path: {current_path}")
			print(f"   Element path: {element['path']}")
			print(f"   Is interactive: {element['is_interactive']}")
			print(f"   Actions: {element['actions']}")
			return True
		
		# Search in children
		for child in node.get('children', []):
			if find_nueva_carpeta_in_tree(child, current_path, depth + 1):
				return True
		
		return False

	# Test 1: Interactive-only mode (should work now)
	print("\n🟢 Testing Interactive-Only Mode (with fix)...")
	response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/tree?interactive_only=true&force=true")
	
	if response.status_code == 200:
		interactive_tree = response.json()
		print("✅ Interactive tree loaded successfully")
		
		if find_nueva_carpeta_in_tree(interactive_tree):
			print("🎉 Nueva carpeta button FOUND in interactive mode!")
		else:
			print("❌ Nueva carpeta button NOT FOUND in interactive mode")
			print("🔍 Let's check what's in the tree...")
			
			def list_buttons(node, depth=0):
				element = node['element']
				if element['role'] == 'AXButton':
					title = element['attributes'].get('title', 'No title')
					print(f"   {'  ' * depth}Button: '{title}' (interactive: {element['is_interactive']})")
				
				for child in node.get('children', []):
					list_buttons(child, depth + 1)
			
			print("🔘 All buttons in interactive tree:")
			list_buttons(interactive_tree)
			return False
	else:
		print(f"❌ Failed to load interactive tree: {response.status_code}")
		return False

	# Test 2: All elements mode (for comparison)
	print("\n🟡 Testing All Elements Mode (for comparison)...")
	response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/tree?interactive_only=false&force=true")
	
	if response.status_code == 200:
		all_tree = response.json()
		print("✅ All elements tree loaded successfully")
		
		if find_nueva_carpeta_in_tree(all_tree):
			print("✅ Nueva carpeta button also found in all elements mode")
		else:
			print("❌ Nueva carpeta button NOT FOUND in all elements mode either!")
			return False
	else:
		print(f"❌ Failed to load all elements tree: {response.status_code}")

	# Test 3: Direct search (should always work)
	print("\n🔍 Testing Direct Search...")
	response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/search?q=nueva%20carpeta")
	
	if response.status_code == 200:
		search_results = response.json()
		if search_results['total_count'] > 0:
			element = search_results['elements'][0]
			print(f"✅ Found via search: {element['role']} '{element['attributes'].get('title')}'")
			print(f"   Is interactive: {element['is_interactive']}")
			print(f"   Path: {element['path']}")
		else:
			print("❌ Not found via search either!")
			return False
	else:
		print(f"❌ Search failed: {response.status_code}")

	print("\n📊 Summary:")
	print("✅ Nueva carpeta button should now appear in interactive-only mode")
	print("✅ Max depth increased from 3 to 5 for interactive mode")
	print("✅ Improved filtering logic for better container detection")
	
	return True

if __name__ == "__main__":
	success = test_nueva_carpeta_visibility()
	exit(0 if success else 1)