#!/usr/bin/env python3
"""
Command-line interface for macOS UI Tree Explorer

Provides CLI commands to quickly inspect and query UI trees without the web interface.
Useful for debugging and scripting.
"""

import asyncio
import json
import sys
from typing import Optional, List
import argparse

import Cocoa
from mlx_use.mac.tree import MacUITreeBuilder
from mlx_use.mac.element import MacElementNode

class UITreeCLI:
	def __init__(self):
		self.builder = MacUITreeBuilder()
		self.current_tree: Optional[MacElementNode] = None
		self.current_pid: Optional[int] = None

	def list_apps(self) -> List[dict]:
		"""List all running applications"""
		workspace = Cocoa.NSWorkspace.sharedWorkspace()
		apps = []
		
		for app in workspace.runningApplications():
			apps.append({
				'pid': app.processIdentifier(),
				'name': app.localizedName() or "Unknown",
				'bundle_id': app.bundleIdentifier() or "Unknown",
				'is_active': app.isActive()
			})
		
		return sorted(apps, key=lambda x: (not x['is_active'], x['name'].lower()))

	async def build_tree(self, pid: int) -> Optional[MacElementNode]:
		"""Build UI tree for application"""
		self.builder.cleanup()
		self.current_tree = await self.builder.build_tree(pid)
		self.current_pid = pid
		return self.current_tree

	def find_elements_by_role(self, role: str) -> List[MacElementNode]:
		"""Find all elements with specific role"""
		if not self.current_tree:
			return []
		
		elements = []
		def search(node: MacElementNode):
			if node.role == role:
				elements.append(node)
			for child in node.children:
				search(child)
		
		search(self.current_tree)
		return elements

	def find_elements_by_action(self, action: str) -> List[MacElementNode]:
		"""Find all elements that support specific action"""
		if not self.current_tree:
			return []
		
		return self.current_tree.find_elements_by_action(action)

	def find_interactive_elements(self) -> List[MacElementNode]:
		"""Find all interactive elements"""
		if not self.current_tree:
			return []
		
		elements = []
		def search(node: MacElementNode):
			if node.is_interactive:
				elements.append(node)
			for child in node.children:
				search(child)
		
		search(self.current_tree)
		return elements

	def search_elements(self, query: str, case_sensitive: bool = False) -> List[MacElementNode]:
		"""Search elements by text query"""
		if not self.current_tree:
			return []
		
		query_text = query if case_sensitive else query.lower()
		elements = []
		
		def search(node: MacElementNode):
			# Build searchable text
			searchable = " ".join([
				node.role,
				node.attributes.get('title', ''),
				node.attributes.get('value', ''),
				node.attributes.get('description', ''),
				" ".join(node.actions)
			])
			
			if not case_sensitive:
				searchable = searchable.lower()
			
			if query_text in searchable:
				elements.append(node)
			
			for child in node.children:
				search(child)
		
		search(self.current_tree)
		return elements

	def print_tree(self, node: Optional[MacElementNode] = None, max_depth: int = 10, current_depth: int = 0):
		"""Print UI tree structure"""
		if node is None:
			node = self.current_tree
		
		if not node or current_depth > max_depth:
			return
		
		indent = "  " * current_depth
		highlight = f"[{node.highlight_index}]" if node.highlight_index is not None else ""
		interactive = " ✓" if node.is_interactive else ""
		
		title = node.attributes.get('title', '')
		value = node.attributes.get('value', '')
		display_text = f"{title} {value}".strip()
		
		print(f"{indent}{node.role}{highlight} {display_text}{interactive}")
		
		for child in node.children:
			self.print_tree(child, max_depth, current_depth + 1)

	def print_element_details(self, element: MacElementNode):
		"""Print detailed element information"""
		print(f"Role: {element.role}")
		print(f"Interactive: {element.is_interactive}")
		print(f"Highlight Index: {element.highlight_index}")
		print(f"Path: {element.accessibility_path}")
		print(f"Actions: {', '.join(element.actions)}")
		print(f"Children: {len(element.children)}")
		print("Attributes:")
		for key, value in element.attributes.items():
			print(f"  {key}: {value}")

def main():
	parser = argparse.ArgumentParser(description="macOS UI Tree Explorer CLI")
	subparsers = parser.add_subparsers(dest='command', help='Available commands')

	# List apps command
	list_parser = subparsers.add_parser('apps', help='List running applications')
	list_parser.add_argument('--active-only', action='store_true', help='Show only active apps')

	# Tree command
	tree_parser = subparsers.add_parser('tree', help='Show UI tree for application')
	tree_parser.add_argument('pid', type=int, help='Process ID of application')
	tree_parser.add_argument('--max-depth', type=int, default=10, help='Maximum tree depth')

	# Search command  
	search_parser = subparsers.add_parser('search', help='Search elements in application')
	search_parser.add_argument('pid', type=int, help='Process ID of application')
	search_parser.add_argument('query', help='Search query')
	search_parser.add_argument('--case-sensitive', action='store_true', help='Case sensitive search')

	# Role command
	role_parser = subparsers.add_parser('role', help='Find elements by role')
	role_parser.add_argument('pid', type=int, help='Process ID of application')
	role_parser.add_argument('role', help='Element role (e.g., AXButton)')

	# Action command
	action_parser = subparsers.add_parser('action', help='Find elements by action')
	action_parser.add_argument('pid', type=int, help='Process ID of application')
	action_parser.add_argument('action', help='Action name (e.g., AXPress)')

	# Interactive command
	interactive_parser = subparsers.add_parser('interactive', help='Find interactive elements')
	interactive_parser.add_argument('pid', type=int, help='Process ID of application')

	# Detail command
	detail_parser = subparsers.add_parser('detail', help='Show element details')
	detail_parser.add_argument('pid', type=int, help='Process ID of application')
	detail_parser.add_argument('index', type=int, help='Element highlight index')

	args = parser.parse_args()

	if not args.command:
		parser.print_help()
		return

	cli = UITreeCLI()

	if args.command == 'apps':
		apps = cli.list_apps()
		if args.active_only:
			apps = [app for app in apps if app['is_active']]
		
		print(f"{'PID':<8} {'Active':<8} {'Name':<30} {'Bundle ID'}")
		print("-" * 80)
		for app in apps:
			active = "Yes" if app['is_active'] else "No"
			print(f"{app['pid']:<8} {active:<8} {app['name']:<30} {app['bundle_id']}")

	elif args.command in ['tree', 'search', 'role', 'action', 'interactive', 'detail']:
		async def run_async_command():
			tree = await cli.build_tree(args.pid)
			if not tree:
				print(f"Failed to build UI tree for PID {args.pid}")
				return

			if args.command == 'tree':
				print(f"UI Tree for PID {args.pid}:")
				cli.print_tree(max_depth=args.max_depth)

			elif args.command == 'search':
				elements = cli.search_elements(args.query, args.case_sensitive)
				print(f"Found {len(elements)} elements matching '{args.query}':")
				for element in elements:
					highlight = f"[{element.highlight_index}]" if element.highlight_index is not None else ""
					title = element.attributes.get('title', '')
					print(f"  {element.role}{highlight} {title}")

			elif args.command == 'role':
				elements = cli.find_elements_by_role(args.role)
				print(f"Found {len(elements)} elements with role '{args.role}':")
				for element in elements:
					highlight = f"[{element.highlight_index}]" if element.highlight_index is not None else ""
					title = element.attributes.get('title', '')
					print(f"  {element.role}{highlight} {title}")

			elif args.command == 'action':
				elements = cli.find_elements_by_action(args.action)
				print(f"Found {len(elements)} elements with action '{args.action}':")
				for element in elements:
					highlight = f"[{element.highlight_index}]" if element.highlight_index is not None else ""
					title = element.attributes.get('title', '')
					print(f"  {element.role}{highlight} {title}")

			elif args.command == 'interactive':
				elements = cli.find_interactive_elements()
				print(f"Found {len(elements)} interactive elements:")
				for element in elements:
					highlight = f"[{element.highlight_index}]" if element.highlight_index is not None else ""
					title = element.attributes.get('title', '')
					actions = ', '.join(element.actions[:3])  # Show first 3 actions
					print(f"  {element.role}{highlight} {title} ({actions})")

			elif args.command == 'detail':
				elements = cli.find_interactive_elements()
				target_element = None
				for element in elements:
					if element.highlight_index == args.index:
						target_element = element
						break
				
				if target_element:
					print(f"Element details for index {args.index}:")
					cli.print_element_details(target_element)
				else:
					print(f"No interactive element found with index {args.index}")

		asyncio.run(run_async_command())

if __name__ == "__main__":
	main()