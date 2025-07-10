#!/usr/bin/env python3
"""
Final comprehensive test of the UI Tree Explorer
"""

import requests
import time

def final_test():
	"""Comprehensive test of all functionality"""
	
	print("🎯 Final Test - macOS UI Tree Explorer")
	print("=" * 50)
	
	try:
		# Test server connectivity
		print("🔗 Testing server connectivity...")
		response = requests.get("http://localhost:8000/api/apps", timeout=5)
		if response.status_code != 200:
			print("❌ Server not responding. Please start the server:")
			print("   python optimized_server.py")
			return False
		
		print("✅ Server is running!")
		
		# Find Notes app
		apps = response.json()
		notes_app = None
		for app in apps:
			if app['bundle_id'] == 'com.apple.Notes':
				notes_app = app
				break
		
		if not notes_app:
			print("❌ Notes app not found. Please open Notes first.")
			return False
		
		notes_pid = notes_app['pid']
		print(f"📝 Notes app found: PID {notes_pid}")
		
		# Test 1: App activation
		print("\n1️⃣  Testing app activation...")
		response = requests.post(f"http://localhost:8000/api/apps/{notes_pid}/activate")
		if response.status_code == 200:
			result = response.json()
			print(f"✅ {result['message']}")
		else:
			print(f"❌ Activation failed: {response.status_code}")
			return False
		
		# Test 2: Tree loading
		print("\n2️⃣  Testing tree loading...")
		start_time = time.time()
		response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/tree")
		load_time = time.time() - start_time
		
		if response.status_code == 200:
			tree_data = response.json()
			print(f"✅ Tree loaded in {load_time:.2f}s")
		else:
			print(f"❌ Tree loading failed: {response.status_code}")
			return False
		
		# Test 3: Case insensitive search variations
		print("\n3️⃣  Testing case-insensitive search...")
		test_queries = [
			'nueva carpeta',    # lowercase
			'Nueva Carpeta',    # mixed case
			'NUEVA CARPETA',    # uppercase
			'nueva',            # partial
		]
		
		all_passed = True
		for query in test_queries:
			response = requests.get(
				f"http://localhost:8000/api/apps/{notes_pid}/search",
				params={'q': query, 'case_sensitive': False}
			)
			
			if response.status_code == 200:
				results = response.json()
				if results['total_count'] > 0:
					print(f"   ✅ '{query}': {results['total_count']} results")
				else:
					print(f"   ❌ '{query}': No results found")
					all_passed = False
			else:
				print(f"   ❌ '{query}': Search failed")
				all_passed = False
		
		if not all_passed:
			print("❌ Some search tests failed")
			return False
		
		# Test 4: Element lookup by index
		print("\n4️⃣  Testing element lookup...")
		response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/element/1")
		if response.status_code == 200:
			element = response.json()
			print(f"✅ Element 1: {element['role']} - '{element['attributes'].get('title', 'No title')}'")
		else:
			print(f"❌ Element lookup failed: {response.status_code}")
			return False
		
		# Test 5: Interactive elements
		print("\n5️⃣  Testing interactive elements filter...")
		response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/interactive")
		if response.status_code == 200:
			interactive = response.json()
			buttons = [el for el in interactive if el['role'] == 'AXButton']
			print(f"✅ Found {len(interactive)} interactive elements ({len(buttons)} buttons)")
		else:
			print(f"❌ Interactive elements failed: {response.status_code}")
			return False
		
		# Test 6: Cache clearing
		print("\n6️⃣  Testing cache management...")
		response = requests.post(f"http://localhost:8000/api/cache/clear")
		if response.status_code == 200:
			result = response.json()
			print(f"✅ Cache cleared: {result['message']}")
		else:
			print(f"❌ Cache clearing failed: {response.status_code}")
			return False
		
		# Test 7: Web interface availability
		print("\n7️⃣  Testing web interface...")
		response = requests.get("http://localhost:8000/")
		if response.status_code == 200:
			content = response.text
			if 'macOS UI Tree Explorer' in content:
				print("✅ Web interface is accessible")
			else:
				print("❌ Web interface content issue")
				return False
		else:
			print(f"❌ Web interface failed: {response.status_code}")
			return False
		
		print("\n🎉 ALL TESTS PASSED!")
		print("\n📋 Test Summary:")
		print("✅ Server connectivity")
		print("✅ App activation")  
		print("✅ Tree loading")
		print("✅ Case-insensitive search")
		print("✅ Element lookup")
		print("✅ Interactive elements")
		print("✅ Cache management")
		print("✅ Web interface")
		
		print("\n🌐 Ready to use!")
		print("1. Open http://localhost:8000 in your browser")
		print("2. Click 'Notas' to activate and explore")
		print("3. Search 'nueva carpeta' (any case)")
		print("4. Click the element to see action buttons")
		print("5. Execute real actions with '🎯 AXPress'")
		
		return True
		
	except Exception as e:
		print(f"❌ Test error: {e}")
		return False

if __name__ == "__main__":
	success = final_test()
	exit(0 if success else 1)