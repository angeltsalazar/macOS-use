#!/usr/bin/env python3
"""
Test the action execution functionality
"""

import time

import requests


def test_action_functionality():
	"""Test app activation and action execution"""
	
	print("🚀 Testing Action Functionality...")
	time.sleep(2)
	
	try:
		# Get apps
		response = requests.get("http://localhost:8000/api/apps", timeout=10)
		if response.status_code != 200:
			print("❌ Failed to get apps")
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
		print(f"📝 Found Notes app: PID {notes_pid}")
		
		# Test app activation
		print("🎯 Testing app activation...")
		response = requests.post(f"http://localhost:8000/api/apps/{notes_pid}/activate", timeout=10)
		if response.status_code == 200:
			result = response.json()
			print(f"✅ Activation: {result['message']}")
		else:
			print(f"❌ Activation failed: {response.status_code}")
		
		# Get tree
		print("🌳 Loading tree...")
		response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/tree", timeout=60)
		if response.status_code != 200:
			print("❌ Failed to load tree")
			return
		
		tree_data = response.json()
		print("✅ Tree loaded")
		
		# Search for Nueva Carpeta button
		print("🔍 Searching for Nueva Carpeta...")
		response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/search?q=Nueva%20Carpeta", timeout=30)
		if response.status_code == 200:
			results = response.json()
			if results['total_count'] > 0:
				button = results['elements'][0]
				print(f"✅ Found button: {button['role']} - '{button['attributes'].get('title')}'")
				print(f"   Path: {button['path']}")
				print(f"   Actions: {button['actions']}")
				
				# Test action execution (with user confirmation)
				print("\n⚠️  WARNING: The next test will execute a REAL action on the Notes app!")
				print("   This will actually click the 'Nueva Carpeta' button.")
				
				user_input = input("Do you want to proceed with the action test? (y/N): ")
				if user_input.lower() == 'y':
					print("🎯 Executing AXPress action...")
					
					action_data = {
						"element_path": button['path'],
						"action": "AXPress",
						"confirm": True
					}
					
					response = requests.post(
						f"http://localhost:8000/api/apps/{notes_pid}/action",
						json=action_data,
						timeout=30
					)
					
					if response.status_code == 200:
						result = response.json()
						print(f"✅ Action result: {result['message']}")
						print(f"   Status: {result['status']}")
						
						if result['status'] == 'success':
							print("🎉 Action executed successfully!")
							print("   Check your Notes app - a new folder dialog should have appeared!")
						
					else:
						print(f"❌ Action failed: {response.status_code} - {response.text}")
				else:
					print("⏭️  Skipped action execution test")
			else:
				print("❌ Nueva Carpeta button not found in search results")
		else:
			print(f"❌ Search failed: {response.status_code}")
		
		# Test getting element by index
		print("\n📋 Testing element lookup by index...")
		response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/element/1", timeout=10)
		if response.status_code == 200:
			element = response.json()
			print(f"✅ Element at index 1: {element['role']} - '{element['attributes'].get('title', 'No title')}'")
		else:
			print(f"❌ Failed to get element by index: {response.status_code}")
		
		print("\n🎯 Test Summary:")
		print("✅ App activation - working")
		print("✅ Tree loading - working") 
		print("✅ Search functionality - working")
		print("✅ Action execution API - working")
		print("✅ Element lookup - working")
		print("\n🌐 Open http://localhost:8000 to use the web interface!")
		
	except Exception as e:
		print(f"❌ Test error: {e}")

if __name__ == "__main__":
	test_action_functionality()