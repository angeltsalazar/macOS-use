#!/usr/bin/env python3
"""Debug script to examine Notes app tree structure"""

import asyncio

import Cocoa

from mlx_use.mac.optimized_tree import OptimizedTreeManager

NOTES_BUNDLE_ID = 'com.apple.Notes'
FOLDER_NAME = 'Ofir folder'

async def debug_notes_tree():
    """Debug Notes app tree structure"""
    workspace = Cocoa.NSWorkspace.sharedWorkspace()
    
    # Find Notes app
    notes_app = None
    for app in workspace.runningApplications():
        if app.bundleIdentifier() and NOTES_BUNDLE_ID.lower() in app.bundleIdentifier().lower():
            notes_app = app
            break
    
    if not notes_app:
        print("❌ Notes app not found")
        return
    
    print(f"📱 Found Notes app, PID: {notes_app.processIdentifier()}")
    
    # Build UI tree
    tree_manager = OptimizedTreeManager()
    pid = notes_app.processIdentifier()
    
    try:
        root = await tree_manager.build_tree(pid, force_refresh=True)
        if not root:
            print("❌ Failed to build UI tree")
            return
        
        ui_tree_string = root.get_clickable_elements_string()
        
        print("\n=== FULL UI TREE ===")
        print(ui_tree_string)
        
        print(f"\n=== SEARCHING FOR '{FOLDER_NAME}' ===")
        lines = ui_tree_string.split('\n')
        found_any = False
        for i, line in enumerate(lines):
            if FOLDER_NAME.lower() in line.lower():
                found_any = True
                start = max(0, i-3)
                end = min(len(lines), i+4)
                context = '\n'.join(lines[start:end])
                print(f"Found at line {i}: {line}")
                print(f"Context:\n{context}")
                print("---")
        
        if not found_any:
            print(f"❌ '{FOLDER_NAME}' not found anywhere in UI tree")
            
            # Look for any folder-related elements
            print("\n=== FOLDER-RELATED ELEMENTS ===")
            for i, line in enumerate(lines):
                if any(keyword in line.lower() for keyword in ['folder', 'carpeta', 'outline', 'axstatictext']):
                    print(f"Line {i}: {line}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        tree_manager.cleanup(pid)

if __name__ == '__main__':
    asyncio.run(debug_notes_tree())