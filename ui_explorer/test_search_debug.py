#!/usr/bin/env python3
"""
Debug search functionality with different queries
"""


import requests


def test_search_variations():
	"""Test search with different case variations"""
	
	print("🔍 Testing Search Variations...")
	
	# Find Notes app PID
	response = requests.get("http://localhost:8000/api/apps", timeout=10)
	if response.status_code != 200:
		print("❌ Server not responding")
		return
	
	apps = response.json()
	notes_app = None
	for app in apps:
		if app['bundle_id'] == 'com.apple.Notes':
			notes_app = app
			break
	
	if not notes_app:
		print("❌ Notes app not found")
		return
	
	notes_pid = notes_app['pid']
	print(f"📝 Testing with Notes PID: {notes_pid}")
	
	# Test different search variations
	search_queries = [
		'Nueva Carpeta',      # Original case
		'nueva carpeta',      # All lowercase
		'NUEVA CARPETA',      # All uppercase
		'Nueva',              # Partial
		'Carpeta',            # Partial
		'nueva',              # Partial lowercase
		'carpeta',            # Partial lowercase
		'button',             # Generic
		'AXButton',           # Role name
	]
	
	print(f"\n🧪 Testing {len(search_queries)} search variations:")
	print("-" * 60)
	
	for query in search_queries:
		try:
			print(f"🔍 Testing: '{query}'")
			
			# Test with case_sensitive=False (default)
			response = requests.get(
				f"http://localhost:8000/api/apps/{notes_pid}/search",
				params={'q': query, 'case_sensitive': False},
				timeout=30
			)
			
			if response.status_code == 200:
				results = response.json()
				print(f"   ✅ Found {results['total_count']} results ({results['search_time']:.3f}s)")
				
				# Show first few results
				for i, element in enumerate(results['elements'][:2]):
					title = element['attributes'].get('title', 'No title')
					print(f"      {i+1}. {element['role']} - '{title}' [Index: {element['highlight_index']}]")
			else:
				print(f"   ❌ Search failed: {response.status_code}")
				print(f"      Error: {response.text[:200]}")
			
			print()
			
		except Exception as e:
			print(f"   ❌ Error: {e}")
			print()
	
	# Test specific element lookup
	print("📋 Testing direct element lookup by index...")
	try:
		response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/element/1", timeout=10)
		if response.status_code == 200:
			element = response.json()
			print("✅ Element at index 1:")
			print(f"   Role: {element['role']}")
			print(f"   Title: '{element['attributes'].get('title', 'No title')}'")
			print(f"   Actions: {element['actions']}")
		else:
			print(f"❌ Element lookup failed: {response.status_code}")
	except Exception as e:
		print(f"❌ Element lookup error: {e}")
	
	# Test interactive elements filter
	print("\n⚡ Testing interactive elements filter...")
	try:
		response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/interactive", timeout=30)
		if response.status_code == 200:
			interactive = response.json()
			print(f"✅ Found {len(interactive)} interactive elements")
			
			# Look for buttons specifically
			buttons = [el for el in interactive if el['role'] == 'AXButton']
			print(f"🔘 Buttons found: {len(buttons)}")
			
			for i, button in enumerate(buttons[:5]):
				title = button['attributes'].get('title', 'No title')
				print(f"   {i+1}. '{title}' [Index: {button['highlight_index']}] - Actions: {button['actions']}")
		else:
			print(f"❌ Interactive elements failed: {response.status_code}")
	except Exception as e:
		print(f"❌ Interactive elements error: {e}")

if __name__ == "__main__":
	test_search_variations()