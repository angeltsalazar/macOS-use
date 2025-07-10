# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

macOS-use is an AI agent framework that enables AI models to control macOS applications through accessibility APIs. The project uses Python with macOS-specific libraries like PyObjC and Cocoa to interact with UI elements.

## Development Setup

### Environment Setup

This project uses conda environment named `macos-use`:

```bash
# Activate the conda environment
conda activate macos-use

# Install project in editable mode
pip install --editable .

# Install dev dependencies
pip install -e ".[dev]"
```

#### Alternative Setup with uv (if preferred)
```bash
# Set up development environment with uv
brew install uv && uv venv && source .venv/bin/activate

# Install project in editable mode
uv pip install --editable .

# Install dev dependencies
uv pip install -e ".[dev]"
```

### Environment Variables
Copy `.env.example` to `.env` and configure API keys:
- `OPENAI_API_KEY` - OpenAI API key (recommended)
- `ANTHROPIC_API_KEY` - Anthropic API key (recommended)
- `GEMINI_API_KEY` - Google Gemini API key (works but less reliable)

### Running Examples
```bash
# Basic interaction test
python examples/try.py

# Calculator demo
python examples/calculate.py

# Other examples
python examples/check_time_online.py
python examples/login_to_auth0.py
```

## Testing

### Test Commands
```bash
# Run all tests
pytest

# Run specific test markers
pytest -m "not slow"    # Skip slow tests
pytest -m integration   # Run integration tests only
pytest -m unit         # Run unit tests only

# Run with verbose output
pytest -v

# Run tests in specific directory
pytest tests/
```

### Test Configuration
- Tests are configured in `pytest.ini`
- Test discovery looks for `test_*.py` and `*_test.py` files
- Async tests are supported with `asyncio_mode = auto`

## Code Quality

### Linting and Formatting
```bash
# The project uses ruff for linting and formatting
# Configuration is in pyproject.toml under [tool.ruff]
# - Line length: 130 characters
# - Quote style: single quotes
# - Indentation: tabs
# - Auto-fix enabled

# Run ruff (if available)
ruff check .
ruff format .
```

## Architecture

### Core Components Structure
The codebase follows a service-oriented architecture inspired by Netflix's Dispatch:

```
mlx_use/
├── agent/                 # Core AI agent logic
│   ├── service.py        # Main Agent class - orchestrates UI interaction
│   ├── prompts.py        # System and agent prompts
│   ├── views.py          # Data models for agent operations
│   └── message_manager/  # Manages conversation history and context
├── controller/           # Action execution system
│   ├── service.py        # Controller class - manages action registry
│   ├── registry/         # Action registration and management
│   └── views.py          # Action parameter models
├── mac/                  # macOS-specific functionality
│   ├── actions.py        # Core UI actions (click, type, scroll)
│   ├── element.py        # UI element representation
│   ├── tree.py           # UI tree building and caching
│   └── context.py        # UI context management
└── telemetry/           # Usage analytics and monitoring
```

### Key Classes

#### Agent (`mlx_use/agent/service.py`)
- Main orchestration class that runs AI agent tasks
- Manages conversation history, state, and action execution
- Handles retries, failures, and telemetry
- Supports multiple LLM providers (OpenAI, Anthropic, Google)

#### Controller (`mlx_use/controller/service.py`)
- Executes actions received from the agent
- Manages action registry and validation
- Handles macOS app launching and UI interaction
- Supports custom action registration via decorators

#### MacUITreeBuilder (`mlx_use/mac/tree.py`)
- Builds accessibility tree from macOS applications
- Caches UI elements for efficient access
- Provides element discovery and interaction capabilities

### Action System
Actions are registered in the Controller's registry:
- `done` - Complete task with result text
- `input_text` - Type text into UI elements
- `click_element` - Click UI elements with specific actions
- `right_click_element` - Right-click UI elements
- `scroll_element` - Scroll elements in specified directions
- `open_app` - Launch macOS applications
- `run_apple_script` - Execute AppleScript commands

### LLM Integration
The system supports multiple LLM providers:
- **OpenAI**: Recommended, uses function calling
- **Anthropic**: Recommended, uses function calling
- **Google Gemini**: Works but less reliable, uses structured output

## Development Guidelines

### Code Organization
- Each service follows the pattern: `models.py`, `service.py`, `views.py`, `prompts.py`
- Services > 500 lines should be split into subservices
- Views should be organized as: All models, Request models, Response models
- Single `prompts.py` file per service (split if too long)
- Never split `routers.py` into multiple files

### Error Handling
- All actions should return `ActionResult` objects
- Include helpful error messages for debugging
- Use appropriate logging levels (DEBUG, INFO, WARNING, ERROR)
- Handle macOS accessibility permission issues gracefully

### Testing Patterns
- Use pytest fixtures for common setup
- Mock external dependencies (LLM calls, system APIs)
- Test both success and failure scenarios
- Use async test patterns for async functions

## Package Management

### Dependencies
Core dependencies include:
- `langchain` and provider-specific packages for LLM integration
- `pyobjc` and `pycocoa` for macOS system integration
- `pydantic` for data validation
- `gradio` for web UI components
- `playwright` for browser automation (if needed)

### Build System
- Uses `hatchling` as build backend
- Version managed in `pyproject.toml`
- Package distributed as `mlx-use` on PyPI

## Gradio Application

The project includes a Gradio web interface in `gradio_app/`:
- Provides web-based interaction with the agent
- Separate requirements file: `gradio_app/requirements.txt`
- Run with: `python gradio_app/app.py`

## Platform Considerations

### macOS Specific
- Requires macOS for full functionality
- Uses Accessibility APIs that may need user permissions
- Some features require specific macOS versions
- PIDs are used to track running applications

### Security
- Be cautious with AppleScript execution
- Never commit API keys to the repository
- The agent can interact with ANY macOS application
- Use appropriate access controls in production environments