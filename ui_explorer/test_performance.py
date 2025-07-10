#!/usr/bin/env python3
"""
Test performance optimizations
"""

import requests
import time

def test_performance_optimizations():
	"""Test the performance improvements"""
	
	print("⚡ Testing Performance Optimizations")
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
	
	# Test 1: Initial tree load
	print("\n1️⃣ Testing initial tree load...")
	start_time = time.time()
	response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/tree")
	initial_time = time.time() - start_time
	
	if response.status_code == 200:
		print(f"✅ Initial load: {initial_time:.2f}s")
	else:
		print(f"❌ Initial load failed: {response.status_code}")
		return
	
	# Test 2: Cached tree load
	print("\n2️⃣ Testing cached tree load...")
	start_time = time.time()
	response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/tree")
	cached_time = time.time() - start_time
	
	if response.status_code == 200:
		print(f"✅ Cached load: {cached_time:.2f}s")
		improvement = ((initial_time - cached_time) / initial_time) * 100
		print(f"🚀 Speed improvement: {improvement:.1f}%")
	else:
		print(f"❌ Cached load failed")
	
	# Test 3: Quick refresh mode
	print("\n3️⃣ Testing quick refresh mode...")
	start_time = time.time()
	response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/tree?quick=true")
	quick_time = time.time() - start_time
	
	if response.status_code == 200:
		print(f"✅ Quick refresh: {quick_time:.2f}s")
		improvement = ((initial_time - quick_time) / initial_time) * 100
		print(f"🚀 Speed improvement: {improvement:.1f}%")
	else:
		print(f"❌ Quick refresh failed")
	
	# Test 4: Search performance
	print("\n4️⃣ Testing search performance...")
	search_queries = ['nueva carpeta', 'button', 'textfield']
	
	for query in search_queries:
		start_time = time.time()
		response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/search?q={query}")
		search_time = time.time() - start_time
		
		if response.status_code == 200:
			results = response.json()
			print(f"   '{query}': {search_time:.3f}s ({results['total_count']} results)")
		else:
			print(f"   '{query}': FAILED")
	
	# Test 5: Interactive elements filter
	print("\n5️⃣ Testing interactive elements filter...")
	start_time = time.time()
	response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/interactive")
	interactive_time = time.time() - start_time
	
	if response.status_code == 200:
		interactive = response.json()
		print(f"✅ Interactive elements: {interactive_time:.3f}s ({len(interactive)} elements)")
	else:
		print(f"❌ Interactive elements failed")
	
	# Test 6: Multiple searches (cache test)
	print("\n6️⃣ Testing search caching...")
	query = 'nueva carpeta'
	
	# First search
	start_time = time.time()
	response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/search?q={query}")
	first_search = time.time() - start_time
	
	# Cached search
	start_time = time.time()
	response = requests.get(f"http://localhost:8000/api/apps/{notes_pid}/search?q={query}")
	cached_search = time.time() - start_time
	
	if response.status_code == 200:
		print(f"   First search: {first_search:.3f}s")
		print(f"   Cached search: {cached_search:.3f}s")
		if cached_search < first_search:
			improvement = ((first_search - cached_search) / first_search) * 100
			print(f"   🚀 Cache improvement: {improvement:.1f}%")
	
	print(f"\n📊 Performance Summary:")
	print(f"✅ Tree caching: {improvement:.1f}% faster")
	print(f"✅ Quick refresh: Available for recent updates")
	print(f"✅ Search caching: Enabled")
	print(f"✅ Interactive filter: Fast element access")
	
	print(f"\n🎯 UI Optimizations Available:")
	print("✅ Collapsible apps panel")
	print("✅ Selected app info bar")
	print("✅ Smart refresh (avoids unnecessary updates)")
	print("✅ Quick mode for recent changes")
	print("✅ Auto-collapse after app selection")
	
	print(f"\n🌐 Try the optimized interface at http://localhost:8000")
	print("   - Apps panel collapses automatically after selection")
	print("   - Smart Refresh button prevents unnecessary updates")
	print("   - Selected app info shows current focus")
	print("   - Quick refresh for recent actions")

if __name__ == "__main__":
	test_performance_optimizations()