#!/usr/bin/env python3
"""Debug Calculator app UI tree to understand button structure"""

import asyncio

from mlx_use.mac.optimized_tree import OptimizedTreeManager


async def debug_calculator():
    """Debug Calculator app tree structure"""
    
    # Calculator PID from the process list
    calculator_pid = 52952
    
    tree_manager = OptimizedTreeManager()
    
    try:
        print("🔍 Building tree for Calculator app...")
        
        # First check the builder configuration
        builder = tree_manager.cache.get_builder(calculator_pid)
        print(f"Builder max_depth: {builder.max_depth}")
        print(f"Builder max_children: {builder.max_children}")
        
        root = await tree_manager.build_tree(calculator_pid, force_refresh=True, lazy_mode=False, max_depth=10)
        if not root:
            print("❌ Failed to build UI tree")
            return
        
        ui_tree_string = root.get_clickable_elements_string()
        
        print("\n=== CALCULATOR UI TREE ===")
        print(ui_tree_string)
        
        print("\n=== SEARCHING FOR BUTTONS ===")
        lines = ui_tree_string.split('\n')
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in ['button', '5', '4', '*', 'x', 'multiply']):
                print(f"Line {i}: {line}")
        
        # Also get flattened elements
        print("\n=== FLATTENED ELEMENTS ===")
        elements = tree_manager.get_flattened_elements(calculator_pid)
        for element_dict in elements:
            if element_dict.get('is_interactive'):
                role = element_dict.get('role', '')
                attributes = element_dict.get('attributes', {})
                title = attributes.get('title', '')
                description = attributes.get('description', '')
                
                if any(keyword in str(title).lower() + str(description).lower() + role.lower() 
                       for keyword in ['5', '4', 'button', 'multiply', '*', 'x']):
                    print(f"Interactive: {element_dict}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        tree_manager.cleanup(calculator_pid)

if __name__ == '__main__':
    asyncio.run(debug_calculator())