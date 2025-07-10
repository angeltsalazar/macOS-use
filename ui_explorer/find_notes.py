#!/usr/bin/env python3
"""
Find the correct Notes app process
"""

import Cocoa


def find_all_notes_processes():
	"""Find all Notes-related processes"""
	
	workspace = Cocoa.NSWorkspace.sharedWorkspace()
	notes_processes = []
	
	print("🔍 Looking for Notes-related processes...")
	
	for app in workspace.runningApplications():
		name = app.localizedName() or "Unknown"
		bundle_id = app.bundleIdentifier() or "Unknown"
		
		# Look for Notes-related processes
		if ('notes' in name.lower() or 
		    'notes' in bundle_id.lower() or
		    bundle_id == 'com.apple.Notes'):
			
			notes_processes.append({
				'pid': app.processIdentifier(),
				'name': name,
				'bundle_id': bundle_id,
				'is_active': app.isActive(),
				'is_hidden': app.isHidden()
			})
	
	print(f"\n📝 Found {len(notes_processes)} Notes-related processes:")
	for i, proc in enumerate(notes_processes):
		print(f"  {i+1}. PID {proc['pid']}: {proc['name']}")
		print(f"     Bundle: {proc['bundle_id']}")
		print(f"     Active: {proc['is_active']}, Hidden: {proc['is_hidden']}")
		print()
	
	# Try to find the main Notes app
	main_notes = None
	for proc in notes_processes:
		if proc['bundle_id'] == 'com.apple.Notes':
			main_notes = proc
			break
	
	if not main_notes:
		# Fallback: look for the most likely candidate
		for proc in notes_processes:
			if proc['is_active'] and 'notes' in proc['name'].lower():
				main_notes = proc
				break
	
	if main_notes:
		print(f"🎯 Main Notes app identified: PID {main_notes['pid']} - {main_notes['name']}")
		return main_notes['pid']
	else:
		print("❌ Could not identify main Notes app")
		if notes_processes:
			print(f"💡 Try using PID {notes_processes[0]['pid']} manually")
		return None

def check_accessibility(pid):
	"""Check if we can access the app's accessibility info"""
	print(f"\n🔐 Checking accessibility for PID {pid}...")
	
	try:
		from ApplicationServices import (
			AXUIElementCopyAttributeValue,
			AXUIElementCreateApplication,
			kAXErrorSuccess,
			kAXRoleAttribute,
		)
		
		app_ref = AXUIElementCreateApplication(pid)
		error, role_attr = AXUIElementCopyAttributeValue(app_ref, kAXRoleAttribute, None)
		
		if error == kAXErrorSuccess:
			print("✅ Accessibility access working")
			return True
		else:
			print(f"❌ Accessibility error: {error}")
			return False
			
	except Exception as e:
		print(f"❌ Exception checking accessibility: {e}")
		return False

if __name__ == "__main__":
	print("🔍 Notes App Process Finder")
	print("=" * 50)
	
	notes_pid = find_all_notes_processes()
	
	if notes_pid:
		check_accessibility(notes_pid)
		print("\n💡 To test with this PID, run:")
		print(f"   python diagnose.py  # (modify the script to use PID {notes_pid})")
	else:
		print("\n❌ No suitable Notes process found.")
		print("💡 Make sure Notes app is open and try again.")