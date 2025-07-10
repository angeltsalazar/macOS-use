#!/usr/bin/env python3
"""
Test script to verify Notes app search functionality
"""

import asyncio
import requests
import time
import Cocoa

def find_notes_app():
	"""Find Notes app PID"""
	workspace = Cocoa.NSWorkspace.sharedWorkspace()
	
	for app in workspace.runningApplications():
		if app.localizedName() and 'notes' in app.localizedName().lower():
			return app.processIdentifier(), app.localizedName()
	
	return None, None

async def test_simple_server():
	"""Test the simple server functionality"""
	
	print("🔍 Testing Simple UI Tree Explorer...")
	
	# Wait for server to be ready
	time.sleep(2)
	
	try:
		# Test apps endpoint
		print("📱 Testing /api/apps...")
		response = requests.get("http://localhost:8001/api/apps", timeout=10)
		if response.status_code == 200:
			apps = response.json()
			print(f"✅ Found {len(apps)} applications")
			
			# Find Notes app
			notes_pid = None
			for app in apps:
				if 'notes' in app['name'].lower():
					notes_pid = app['pid']
					print(f"📝 Found Notes app: PID {notes_pid}")
					break
			
			if not notes_pid:
				print("❌ Notes app not found. Please open Notes app.")
				return
			
			# Test elements endpoint
			print(f"🌳 Testing /api/apps/{notes_pid}/elements...")
			response = requests.get(f"http://localhost:8001/api/apps/{notes_pid}/elements", timeout=30)
			if response.status_code == 200:
				elements = response.json()
				print(f"✅ Found {len(elements)} elements")
				
				# Count interactive elements
				interactive = [e for e in elements if e['is_interactive']]
				print(f"⚡ Interactive elements: {len(interactive)}")
				
				# Test search
				print("🔍 Testing search for 'Nueva Carpeta'...")
				response = requests.get(f"http://localhost:8001/api/apps/{notes_pid}/search?q=Nueva%20Carpeta", timeout=10)
				if response.status_code == 200:
					results = response.json()
					print(f"🎯 Search results: {len(results)} elements found")
					for result in results:
						print(f"   - {result['role']} {result['title']} [{result.get('highlight_index', 'N/A')}]")
				else:
					print(f"❌ Search failed: {response.status_code}")
			else:
				print(f"❌ Elements request failed: {response.status_code} - {response.text}")
		else:
			print(f"❌ Apps request failed: {response.status_code}")
			
	except requests.exceptions.RequestException as e:
		print(f"❌ Connection error: {e}")
		print("Make sure the simple server is running on port 8001")

if __name__ == "__main__":
	asyncio.run(test_simple_server())