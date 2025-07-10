#!/usr/bin/env python3
"""
Test typing functionality
"""

import requests
import time

def test_typing_functionality():
	"""Test the text input functionality"""
	
	print("✏️ Testing Text Input Functionality")
	print("=" * 40)
	
	# Find Notes app
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
	print(f"📝 Notes app found: PID {notes_pid}")
	
	# Get fresh tree to see dialog
	print("\n🔄 Getting fresh tree...")
	response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/tree?force=true", timeout=60)
	if response.status_code != 200:
		print("❌ Failed to get tree")
		return
	
	print("✅ Tree loaded")
	
	# Search for text fields
	print("\n🔍 Searching for text fields...")
	response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/search?q=textfield")
	if response.status_code == 200:
		results = response.json()
		print(f"📄 Found {results['total_count']} text fields")
		
		for i, element in enumerate(results['elements'][:3]):
			title = element['attributes'].get('title', 'No title')
			value = element['attributes'].get('value', 'No value')
			print(f"   {i+1}. {element['role']} - Title: '{title}', Value: '{value}'")
			print(f"      Actions: {element['actions']}")
			print(f"      Path: {element['path']}")
			
			if 'AXSetValue' in element['actions']:
				print(f"      ✅ This field supports text input!")
				
				# Test typing
				test_text = "Mi Nueva Carpeta"
				print(f"\n✏️ Testing typing '{test_text}' into this field...")
				
				type_data = {
					"element_path": element['path'],
					"text": test_text,
					"confirm": True
				}
				
				response = requests.post(
					f"http://localhost:8000/api/apps/{notes_pid}/type",
					json=type_data,
					timeout=30
				)
				
				if response.status_code == 200:
					result = response.json()
					print(f"✅ Typing result: {result['message']}")
					print(f"   Status: {result['status']}")
					
					if result['status'] == 'success':
						print("🎉 Text input successful!")
						
						# Now look for OK button
						print("\n🔍 Looking for OK button...")
						time.sleep(1)  # Give UI time to update
						
						response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/search?q=ok")
						if response.status_code == 200:
							ok_results = response.json()
							print(f"🔘 Found {ok_results['total_count']} elements matching 'ok'")
							
							for j, ok_element in enumerate(ok_results['elements'][:3]):
								ok_title = ok_element['attributes'].get('title', 'No title')
								print(f"   {j+1}. {ok_element['role']} - '{ok_title}'")
								print(f"      Actions: {ok_element['actions']}")
								
								if ok_element['role'] == 'AXButton' and 'AXPress' in ok_element['actions']:
									print(f"      ✅ This looks like a clickable OK button!")
									print(f"      💡 You can click this in the web interface!")
									break
						
						break  # Stop after first successful text input
				else:
					print(f"❌ Typing failed: {response.status_code} - {response.text}")
			print()
	else:
		print("❌ Search for text fields failed")
	
	# Search for buttons that might be OK
	print("\n🔍 Searching for OK/Accept buttons...")
	button_queries = ['ok', 'aceptar', 'accept', 'button']
	
	for query in button_queries:
		response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/search?q={query}")
		if response.status_code == 200:
			results = response.json()
			if results['total_count'] > 0:
				print(f"🔘 '{query}': {results['total_count']} results")
				for element in results['elements'][:2]:
					title = element['attributes'].get('title', 'No title')
					if element['role'] == 'AXButton':
						print(f"   - Button: '{title}' [Index: {element['highlight_index']}]")
	
	print(f"\n📋 Instructions to complete folder creation:")
	print("1. 🔄 Click 'Refresh' in the web interface")
	print("2. 🔍 Search for 'textfield' to find the name input")
	print("3. ✏️ Click the green '✏️ AXSetValue (Type Text)' button")
	print("4. 📝 Enter your folder name when prompted")
	print("5. 🔍 Search for 'ok' or 'button' to find the OK button")
	print("6. 🎯 Click '🎯 AXPress' on the OK button")
	print("7. 🎉 Folder created!")

if __name__ == "__main__":
	test_typing_functionality()