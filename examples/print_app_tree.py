# print_app_tree.py
# --- START OF FILE examples/basic_agent.py ---
import asyncio
import os
import sys

import Cocoa

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mlx_use.controller.service import Controller
from mlx_use.mac.optimized_tree import OptimizedTreeManager


async def print_app_tree(app_name: str):
	try:
		controller = Controller()
		# Initialize the optimized tree manager
		tree_manager = OptimizedTreeManager()
		
		# Get the workspace to launch app directly
		workspace = Cocoa.NSWorkspace.sharedWorkspace()
		
		# Format app name and bundle ID
		formatted_app_name = app_name.capitalize()
		bundle_id = f'com.apple.{app_name.lower()}'
		
		print(f'\nLaunching {formatted_app_name} app...')
		success = workspace.launchApplication_(formatted_app_name)
		
		if not success:
			print(f'❌ Failed to launch {formatted_app_name} app')
			return
			
		# Give the app a moment to launch
		await asyncio.sleep(1)
		
		# Find the app's PID
		app_pid = None
		for app in workspace.runningApplications():
			if app.bundleIdentifier() and bundle_id.lower() in app.bundleIdentifier().lower():
				print(f'Found {formatted_app_name}!')
				print(f'Bundle ID: {app.bundleIdentifier()}')
				app_pid = app.processIdentifier()
				print(f'PID: {app_pid}')
				break
				
		if not app_pid:
			print(f'❌ Could not find {formatted_app_name} app')
			return
			
		# Activate the app
		for app in workspace.runningApplications():
			if app.processIdentifier() == app_pid:
				app.activateWithOptions_(Cocoa.NSApplicationActivateIgnoringOtherApps)
				break
				
		await asyncio.sleep(1)  # Give it a moment to activate
		
		# Build the UI tree using the optimized tree manager
		root = await tree_manager.build_tree(app_pid)
		
		if root:
			print(f'\n✅ Successfully built UI tree for {formatted_app_name}!')
			print(f'Number of root children: {len(root.children)}')

			def print_tree(node, indent=0):
				print('  ' * indent + repr(node))
				for child in node.children:
					print_tree(child, indent + 1)

			print(f'\nAll elements in the tree for {formatted_app_name}:')
			print_tree(root)

			print(f'\nInteractive elements found in {formatted_app_name}:')
			print(root.get_clickable_elements_string())
			
			# Display performance stats
			print('\nPerformance Stats:')
			stats = tree_manager.get_performance_stats()
			print(f'Trees cached: {stats["cache_stats"]["trees_cached"]}')
			print(f'Search cache size: {stats["cache_stats"]["search_cache_size"]}')
			print(f'Elements cached: {stats["cache_stats"]["elements_flat_cached"]}')
		else:
			print(f'❌ Failed to build UI tree for {formatted_app_name}')

	except Exception as e:
		print(f'❌ Error: {e}')
		import traceback
		traceback.print_exc()
	finally:
		if 'tree_manager' in locals():
			tree_manager.cleanup(app_pid if 'app_pid' in locals() else 0)


if __name__ == '__main__':
	app = input('What app should I analyze? ')
	asyncio.run(print_app_tree(app))
