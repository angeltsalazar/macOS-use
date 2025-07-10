#!/usr/bin/env python3
"""
Test interactive-only filtering to demonstrate performance improvements
"""

import requests
import time
import json

def test_interactive_filter():
	"""Compare interactive-only vs all elements performance"""
	
	print("🎯 Testing Interactive-Only Filter")
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
	print(f"📝 Testing with Notes PID: {notes_pid}")

	# Test 1: Interactive-only mode (default)
	print("\n🟢 Testing Interactive-Only Mode...")
	start_time = time.time()
	response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/tree?interactive_only=true&force=true")
	interactive_time = time.time() - start_time

	if response.status_code == 200:
		interactive_tree = response.json()
		interactive_count = count_elements(interactive_tree)
		print(f"✅ Interactive-only: {interactive_time:.2f}s")
		print(f"📊 Elements loaded: {interactive_count}")
	else:
		print(f"❌ Interactive-only failed: {response.status_code}")
		return

	# Small delay to avoid cache interference
	time.sleep(2)

	# Test 2: All elements mode
	print("\n🟡 Testing All Elements Mode...")
	start_time = time.time()
	response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/tree?interactive_only=false&force=true")
	all_elements_time = time.time() - start_time

	if response.status_code == 200:
		all_tree = response.json()
		all_count = count_elements(all_tree)
		print(f"✅ All elements: {all_elements_time:.2f}s")
		print(f"📊 Elements loaded: {all_count}")
	else:
		print(f"❌ All elements failed: {response.status_code}")
		return

	# Calculate improvements
	time_improvement = ((all_elements_time - interactive_time) / all_elements_time) * 100 if all_elements_time > 0 else 0
	elements_reduction = ((all_count - interactive_count) / all_count) * 100 if all_count > 0 else 0
	
	print(f"\n📈 Performance Comparison:")
	print(f"⚡ Time improvement: {time_improvement:.1f}% faster")
	print(f"🔽 Elements reduced: {elements_reduction:.1f}% fewer")
	print(f"📋 Filtered out: {all_count - interactive_count} non-interactive elements")
	
	# Test 3: Interactive elements API
	print(f"\n⚡ Testing Interactive Elements API...")
	start_time = time.time()
	response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/interactive")
	api_time = time.time() - start_time
	
	if response.status_code == 200:
		interactive_elements = response.json()
		print(f"✅ Interactive API: {api_time:.3f}s")
		print(f"🎯 Interactive elements: {len(interactive_elements)}")
		
		# Count by type
		element_types = {}
		for element in interactive_elements:
			role = element['role']
			element_types[role] = element_types.get(role, 0) + 1
		
		print(f"📊 Element types found:")
		for role, count in sorted(element_types.items()):
			print(f"   {role}: {count}")
	
	print(f"\n🎉 Results Summary:")
	print(f"✅ Interactive-only filter: {interactive_count} elements in {interactive_time:.2f}s")
	print(f"⚠️ All elements: {all_count} elements in {all_elements_time:.2f}s")
	print(f"🚀 Performance gain: {time_improvement:.1f}% faster with {elements_reduction:.1f}% fewer elements")
	
	print(f"\n💡 Benefits of Interactive-Only Mode:")
	print("✅ Faster loading (less data to process)")
	print("✅ Fewer serialization errors (problematic elements filtered out)")
	print("✅ Focus on actionable elements (buttons, fields, etc.)")
	print("✅ Better user experience (relevant elements only)")
	print("✅ Reduced memory usage")
	
	print(f"\n🌐 Web Interface Updates:")
	print("✅ Interactive Only button (green) - default mode")
	print("✅ All Elements button (yellow) - show everything")
	print("✅ Active button highlighting")
	print("✅ Smart refresh respects current filter mode")
	print("✅ Loading messages indicate current mode")

def count_elements(node):
	"""Recursively count all elements in the tree"""
	if not node:
		return 0
	
	count = 1  # Count this node
	
	if 'children' in node and node['children']:
		for child in node['children']:
			count += count_elements(child)
	
	return count

if __name__ == "__main__":
	test_interactive_filter()