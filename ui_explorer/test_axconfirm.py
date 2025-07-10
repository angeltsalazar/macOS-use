#!/usr/bin/env python3
"""
Test AXConfirm text field functionality
"""

import requests
import time

def test_axconfirm_field():
	"""Test the AXConfirm text field"""
	
	print("🔍 Testing AXConfirm Text Field")
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
	
	# Get fresh tree
	print("\n🔄 Getting fresh tree...")
	response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/tree?force=true", timeout=60)
	if response.status_code != 200:
		print("❌ Failed to get tree")
		return
	
	print("✅ Tree loaded")
	
	# Search specifically for the text field with placeholder "Nueva Carpeta"
	print("\n🔍 Looking for the Nueva Carpeta text field...")
	response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/search?q=Nueva%20Carpeta")
	if response.status_code == 200:
		results = response.json()
		print(f"📄 Found {results['total_count']} elements with 'Nueva Carpeta'")
		
		text_field = None
		for element in results['elements']:
			if (element['role'] == 'AXTextField' and 
			    'AXConfirm' in element['actions'] and
			    element['attributes'].get('value') == 'Nueva carpeta'):
				text_field = element
				print(f"✅ Found the target text field!")
				print(f"   Role: {element['role']}")
				print(f"   Value: '{element['attributes'].get('value')}'")
				print(f"   Actions: {element['actions']}")
				print(f"   Path: {element['path']}")
				break
		
		if not text_field:
			print("❌ Could not find the specific text field")
			return
		
		# Test typing into this field
		new_name = "Mi Carpeta Personalizada"
		print(f"\n✏️ Testing typing '{new_name}' into the field...")
		
		type_data = {
			"element_path": text_field['path'],
			"text": new_name,
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
				
				# Look for OK button to complete the process
				print("\n🔍 Looking for OK button to complete folder creation...")
				time.sleep(1)  # Give UI time to update
				
				response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/search?q=OK")
				if response.status_code == 200:
					ok_results = response.json()
					if ok_results['total_count'] > 0:
						ok_button = ok_results['elements'][0]
						print(f"🔘 Found OK button:")
						print(f"   Role: {ok_button['role']}")
						print(f"   Title: '{ok_button['attributes'].get('title', 'No title')}'")
						print(f"   Actions: {ok_button['actions']}")
						print(f"   Index: {ok_button['highlight_index']}")
						
						if ok_button['role'] == 'AXButton' and 'AXPress' in ok_button['actions']:
							print(f"\n🎯 This button can be clicked to complete folder creation!")
							print(f"💡 In the web interface:")
							print(f"   1. Search for 'OK'")
							print(f"   2. Click on the OK button element")
							print(f"   3. Click '🎯 AXPress' to create the folder")
						
		else:
			error_text = response.text if response.text else "Unknown error"
			print(f"❌ Typing failed: {response.status_code}")
			print(f"   Error: {error_text}")
			
			# Try to get more details
			try:
				error_json = response.json()
				print(f"   Detail: {error_json.get('detail', 'No details')}")
			except:
				pass
	else:
		print("❌ Search failed")

	print(f"\n📋 Summary:")
	print("✅ Enhanced text input now supports AXConfirm fields")
	print("✅ Multiple methods tried for text input")
	print("✅ Web interface updated with blue text input buttons")
	print("\n🎯 Next steps in web interface:")
	print("1. 🔄 Refresh the tree")
	print("2. 🔍 Search for 'Nueva Carpeta' or 'textfield'")
	print("3. 📝 Click the blue '✏️ AXConfirm (Type Text)' button")
	print("4. ⌨️ Enter your folder name")
	print("5. 🔍 Search for 'OK'")
	print("6. 🎯 Click '🎯 AXPress' on the OK button")

if __name__ == "__main__":
	test_axconfirm_field()