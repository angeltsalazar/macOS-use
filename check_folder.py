#!/usr/bin/env python3
"""Quick script to check if Ofir folder was created in Notes app"""

import asyncio

import Cocoa

from mlx_use.mac.optimized_tree import OptimizedTreeManager

NOTES_BUNDLE_ID = 'com.apple.Notes'
FOLDER_NAME = 'Ofir folder'

async def check_folder_created():
    """Check if the folder was created in Notes app"""
    workspace = Cocoa.NSWorkspace.sharedWorkspace()
    
    # Find Notes app
    notes_app = None
    for app in workspace.runningApplications():
        if app.bundleIdentifier() and NOTES_BUNDLE_ID.lower() in app.bundleIdentifier().lower():
            notes_app = app
            break
    
    if not notes_app:
        print("❌ Notes app not found")
        return False
    
    print(f"📱 Found Notes app, PID: {notes_app.processIdentifier()}")
    
    # Build UI tree
    tree_manager = OptimizedTreeManager()
    pid = notes_app.processIdentifier()
    
    try:
        root = await tree_manager.build_tree(pid)
        if not root:
            print("❌ Failed to build UI tree")
            return False
        
        ui_tree_string = root.get_clickable_elements_string()
        
        # Check if folder exists in the outline/folder list
        lines = ui_tree_string.split('\n')
        for i, line in enumerate(lines):
            if FOLDER_NAME in line:
                # Get context around the folder name
                start = max(0, i-2)
                end = min(len(lines), i+3)
                context = '\n'.join(lines[start:end])
                
                print(f"🔍 Found '{FOLDER_NAME}' in UI tree:")
                print(f"Context:\n{context}")
                
                # Check if it's in a real folder location (outline view)
                if 'outline' in context.lower() or 'axstatictext' in context.lower():
                    if 'axtextfield' not in context.lower():
                        print(f"✅ '{FOLDER_NAME}' found in folder list - folder created successfully!")
                        return True
                    else:
                        print(f"🔍 '{FOLDER_NAME}' found in text field - not a real folder")
                else:
                    print(f"🔍 '{FOLDER_NAME}' found but not in folder list context")
        
        print(f"❌ '{FOLDER_NAME}' not found in folder list")
        return False
        
    except Exception as e:
        print(f"❌ Error checking folder: {e}")
        return False
    finally:
        tree_manager.cleanup(pid)

if __name__ == '__main__':
    asyncio.run(check_folder_created())