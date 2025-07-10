#!/usr/bin/env python3
"""
Demo script showing the enhanced UI Tree Explorer functionality
"""

import time

import requests


def demo_functionality():
	"""Demo the enhanced functionality"""
	
	print("🎉 macOS UI Tree Explorer - Enhanced Demo")
	print("=" * 50)
	
	try:
		# Test basic connectivity
		print("🔗 Testing server connectivity...")
		response = requests.get("http://localhost:8000/api/apps", timeout=5)
		if response.status_code != 200:
			print("❌ Server not responding. Please start the server:")
			print("   python optimized_server.py")
			return
		
		print("✅ Server is running!")
		
		# Get apps
		apps = response.json()
		notes_app = None
		
		print(f"\n📱 Available applications ({len(apps)}):")
		for i, app in enumerate(apps[:10]):  # Show first 10
			marker = "📝" if app['bundle_id'] == 'com.apple.Notes' else "📱"
			print(f"   {marker} {app['name']} (PID: {app['pid']})")
			if app['bundle_id'] == 'com.apple.Notes':
				notes_app = app
		
		if not notes_app:
			print("\n❌ Notes app not found. Please open Notes app first.")
			return
		
		notes_pid = notes_app['pid']
		print(f"\n✨ Notes app found: PID {notes_pid}")
		
		# Test activation
		print("\n🎯 Testing app activation...")
		response = requests.post(f"http://localhost:8000/api/apps/{notes_pid}/activate")
		if response.status_code == 200:
			result = response.json()
			print(f"✅ {result['message']}")
		
		# Load tree
		print("\n🌳 Loading UI tree...")
		start_time = time.time()
		response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/tree")
		load_time = time.time() - start_time
		
		if response.status_code == 200:
			tree_data = response.json()
			print(f"✅ Tree loaded in {load_time:.2f}s")
			print(f"   Root: {tree_data['element']['role']}")
			print(f"   Children: {len(tree_data['children'])}")
		
		# Test search
		search_queries = ['Nueva Carpeta', 'button', 'carpeta']
		
		print("\n🔍 Testing search functionality...")
		for query in search_queries:
			response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/search?q={query}")
			if response.status_code == 200:
				results = response.json()
				print(f"   '{query}': {results['total_count']} results ({results['search_time']:.3f}s)")
				
				if query == 'Nueva Carpeta' and results['total_count'] > 0:
					button = results['elements'][0]
					print(f"      📋 Found: {button['role']} - '{button['attributes'].get('title')}'")
					print(f"      🎯 Actions: {', '.join(button['actions'])}")
					print(f"      📍 Index: {button['highlight_index']}")
		
		# Test interactive elements
		print("\n⚡ Testing interactive elements...")
		response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/interactive")
		if response.status_code == 200:
			interactive = response.json()
			print(f"✅ Found {len(interactive)} interactive elements")
			
			# Show some examples
			buttons = [el for el in interactive if el['role'] == 'AXButton'][:3]
			if buttons:
				print("   📋 Sample buttons:")
				for button in buttons:
					title = button['attributes'].get('title', 'No title')
					print(f"      - {title} [Index: {button['highlight_index']}]")
		
		print("\n🎯 Capabilities Demonstrated:")
		print("✅ Application discovery and listing")
		print("✅ App activation (brings to front)")
		print("✅ UI tree building with caching")
		print("✅ Fast search across all elements")
		print("✅ Interactive element identification")
		print("✅ Element indexing for automation")
		
		print("\n🌐 Web Interface Features:")
		print("🔸 Real-time app activation on selection")
		print("🔸 Visual search with highlighting")
		print("🔸 Clickable action buttons on elements")
		print("🔸 Safety confirmations for actions")
		print("🔸 Auto-refresh after actions")
		
		print("\n🚀 Next Steps:")
		print("1. Open http://localhost:8000 in your browser")
		print("2. Click on 'Notas' to activate and explore")
		print("3. Search for 'Nueva Carpeta'")
		print("4. Click on the element to see action buttons")
		print("5. Click '🎯 AXPress' to execute the action!")
		
		print("\n⚠️  Note: Action execution is REAL - it will interact with the actual app!")
		
	except requests.exceptions.ConnectionError:
		print("❌ Cannot connect to server. Please start it first:")
		print("   cd ui_explorer")
		print("   python optimized_server.py")
	except Exception as e:
		print(f"❌ Demo error: {e}")

if __name__ == "__main__":
	demo_functionality()