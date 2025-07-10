#!/usr/bin/env python3
"""
Test the optimized server with Notes app
"""

import time

import requests


def test_optimized_server():
	"""Test the optimized server functionality"""
	
	print("🚀 Testing Optimized UI Tree Explorer...")
	
	# Wait for server to be ready
	time.sleep(2)
	
	try:
		# Test apps endpoint
		print("📱 Testing /api/apps...")
		response = requests.get("http://localhost:8000/api/apps", timeout=10)
		if response.status_code == 200:
			apps = response.json()
			print(f"✅ Found {len(apps)} applications")
			
			# Find Notes app - should be first now
			notes_app = None
			for app in apps:
				if app['bundle_id'] == 'com.apple.Notes':
					notes_app = app
					break
			
			if not notes_app:
				print("❌ Notes app not found in API response")
				print("Available apps:")
				for app in apps[:5]:
					print(f"  - {app['name']} ({app['bundle_id']})")
				return
			
			notes_pid = notes_app['pid']
			print(f"📝 Found Notes app: PID {notes_pid} - {notes_app['name']}")
			
			# Test tree endpoint
			print(f"🌳 Testing /api/apps/{notes_pid}/tree...")
			response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/tree", timeout=60)
			if response.status_code == 200:
				tree_data = response.json()
				print("✅ Tree loaded successfully")
				print(f"    Root: {tree_data['element']['role']}")
				print(f"    Children: {len(tree_data['children'])}")
				
				# Test search for "Nueva Carpeta"
				print("🔍 Testing search for 'Nueva Carpeta'...")
				response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/search?q=Nueva%20Carpeta", timeout=30)
				if response.status_code == 200:
					results = response.json()
					print(f"🎯 Search results: {results['total_count']} elements found in {results['search_time']:.2f}s")
					
					for i, result in enumerate(results['elements'][:3]):  # Show first 3
						title = result['attributes'].get('title', 'No title')
						print(f"   {i+1}. {result['role']} - '{title}' [Index: {result['highlight_index']}]")
						print(f"      Actions: {', '.join(result['actions'])}")
				else:
					print(f"❌ Search failed: {response.status_code} - {response.text}")
					
				# Test query builder
				print("🎯 Testing query by title...")
				query_data = {
					"query_type": "title",
					"query_value": "Nueva carpeta",
					"case_sensitive": False
				}
				response = requests.post(
					f"http://localhost:8000/api/apps/{notes_pid}/query",
					json=query_data,
					timeout=30
				)
				if response.status_code == 200:
					results = response.json()
					print(f"📊 Query results: {results['total_count']} elements found")
					for result in results['elements']:
						title = result['attributes'].get('title', 'No title')
						print(f"   - {result['role']} - '{title}' [Index: {result['highlight_index']}]")
				else:
					print(f"❌ Query failed: {response.status_code}")
					
				# Test interactive elements
				print("⚡ Testing interactive elements...")
				response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/interactive", timeout=30)
				if response.status_code == 200:
					interactive = response.json()
					print(f"🎮 Interactive elements: {len(interactive)}")
					
					# Look for Nueva Carpeta button specifically
					nueva_carpeta_buttons = [
						el for el in interactive 
						if 'nueva carpeta' in str(el['attributes'].get('title', '')).lower()
					]
					print(f"🔘 'Nueva Carpeta' buttons found: {len(nueva_carpeta_buttons)}")
					for button in nueva_carpeta_buttons:
						print(f"   - {button['role']} [Index: {button['highlight_index']}]")
						print(f"     Title: {button['attributes'].get('title')}")
						print(f"     Actions: {', '.join(button['actions'])}")
						
				else:
					print(f"❌ Interactive elements failed: {response.status_code}")
					
			else:
				print(f"❌ Tree request failed: {response.status_code}")
				if response.text:
					print(f"Error: {response.text[:500]}")
		else:
			print(f"❌ Apps request failed: {response.status_code}")
			
	except requests.exceptions.RequestException as e:
		print(f"❌ Connection error: {e}")
		print("Make sure the optimized server is running on port 8000")
	except Exception as e:
		print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
	test_optimized_server()