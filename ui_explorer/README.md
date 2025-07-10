# macOS UI Tree Explorer

A web-based tool for exploring and understanding the macOS UI Tree System used by the mlx-use framework. This server provides an interactive interface to browse applications, explore their UI structure, and query specific elements.

## 🚀 Quick Start

**For the optimized version:**
```bash
cd ui_explorer
python optimized_server.py
```

Then open: http://localhost:8000

## Features

### ✨ **Optimized Version (optimized_server.py)**
- 🚀 **Intelligent Caching**: Memoization of tree builds and search results
- ⚡ **Incremental Loading**: Load tree sections on-demand for better performance
- 🎯 **Enhanced Search**: Visual highlighting and improved result feedback
- 📊 **Performance Metrics**: Real-time timing and statistics
- 🔄 **Auto-refresh**: Smart cache invalidation and tree updates
- 💡 **Interactive-only View**: Quick access to clickable elements

### 🌳 **Core Features**
- 🌳 **UI Tree Visualization**: Browse the complete accessibility tree of any macOS application
- 🔍 **Element Search**: Search elements by role, title, actions, or custom queries  
- 📋 **Element Details**: View comprehensive information about each UI element
- ⚡ **Interactive Elements**: Identify clickable and interactive elements with highlight indices
- 🎯 **Query Builder**: Build structured queries to find specific elements
- 🖥️ **Application Browser**: View all running applications with their details

## Installation

1. Ensure you have the mlx-use project environment activated:
```bash
conda activate macos-use
```

2. Install additional dependencies:
```bash
pip install -r ui_explorer/requirements.txt
```

## Usage

1. Start the server:
```bash
cd ui_explorer
python server.py
```

2. Open your browser and navigate to: http://localhost:8000

3. The web interface will show:
   - **Running Applications**: List of all macOS applications you can explore
   - **UI Tree Explorer**: Interactive tree view of the selected application's UI
   - **Query Builder**: Tools to search and filter elements

## API Endpoints

The server provides a REST API with the following endpoints:

### Applications
- `GET /api/apps` - List all running applications
- `GET /api/apps/{pid}/tree` - Get complete UI tree for application
- `GET /api/apps/{pid}/elements` - Get flat list of all elements

### Element Queries
- `GET /api/apps/{pid}/search?q={query}` - Text search across elements
- `POST /api/apps/{pid}/query` - Structured query with specific criteria
- `GET /api/apps/{pid}/interactive` - Get only interactive elements
- `GET /api/apps/{pid}/element/{id}` - Get details for specific element

### Query Types
- **role**: Search by element role (AXButton, AXTextField, etc.)
- **title**: Search by element title or label
- **action**: Search by available actions (AXPress, AXConfirm, etc.)
- **path**: Search by accessibility path
- **custom**: Free-form search across all attributes

## Understanding the UI Tree

The macOS UI Tree System represents applications as hierarchical structures:

- **Elements**: Individual UI components (buttons, text fields, windows, etc.)
- **Roles**: Element types defined by macOS accessibility API (AXButton, AXTextField, AXWindow)
- **Actions**: Operations possible on elements (AXPress, AXConfirm, AXSetValue)
- **Attributes**: Properties like title, value, position, enabled state
- **Highlight Indices**: Sequential numbers assigned to interactive elements for automation

### Interactive vs Context Elements

- **Interactive Elements**: Can be clicked, typed into, or manipulated (shown with ✓)
- **Context Elements**: Provide information but aren't interactive (labels, static text)

## Examples

### Finding All Buttons
```python
# Use Query Builder with:
# Type: "By Role"
# Value: "AXButton"
```

### Finding Elements by Text
```python
# Use search box with:
# "Save" - finds elements containing "Save" in any attribute
```

### Finding Clickable Elements
```python
# Use Query Builder with:
# Type: "By Action" 
# Value: "AXPress"
```

## Troubleshooting

### Accessibility Permissions
If you get accessibility errors:
1. Go to System Settings > Privacy & Security > Accessibility
2. Add Terminal (or your IDE) to the allowed applications
3. Restart the server

### Empty Trees
If an application shows no elements:
- The app might not have accessibility support
- Try refreshing the tree after the app finishes loading
- Some apps require user interaction before UI elements appear

### Performance
For large applications:
- The tree depth is limited to prevent infinite recursion
- Child count is limited to 250 per element
- Use queries to find specific elements instead of browsing the full tree

## Integration with mlx-use

This explorer helps you understand how the mlx-use framework sees macOS applications:

1. **Element Discovery**: See exactly what elements the framework can interact with
2. **Highlight Indices**: Understand the numbering system used for automation
3. **Action Planning**: Identify which actions are available on each element
4. **Debugging**: Troubleshoot why automation scripts might fail to find elements

The server uses the same `MacUITreeBuilder` and `MacElementNode` classes as the main framework, ensuring consistency between exploration and automation.