# --- START OF FILE examples/basic_agent.py ---
import asyncio
import json
import time
import logging
import os
import datetime
import Cocoa
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr

from mlx_use.mac.actions import click, type_into
from mlx_use.mac.tree import MacUITreeBuilder

NOTES_BUNDLE_ID = 'com.apple.Notes'
NOTES_APP_NAME = 'Notes'


def set_llm(llm_provider:str = None):
	if not llm_provider:
		raise ValueError("No llm provider was set")
	
	if llm_provider == "OAI":
		api_key = os.getenv('OPENAI_API_KEY')
		return ChatOpenAI(model='gpt-4o', api_key=SecretStr(api_key))

	if llm_provider == "github":
		api_key = os.getenv('GITHUB_TOKEN')
		return ChatOpenAI(model='gpt-4o', base_url="https://models.inference.ai.azure.com", api_key=SecretStr(api_key))

	if llm_provider == "grok":
		api_key = os.getenv('XAI_API_KEY')
		return ChatOpenAI(model='grok-2', base_url="https://api.x.ai/v1", api_key=SecretStr(api_key))

	if llm_provider == "google":
		api_key = os.getenv('GEMINI_API_KEY')
		return ChatGoogleGenerativeAI(
			model='gemini-2.0-flash-exp',  # Use Flash model for more reliability
			api_key=SecretStr(api_key),
			temperature=0.1,  # Lower temperature for more consistent responses
			max_tokens=200,   # Increased for better reasoning
		)

	if llm_provider == "anthropic":
		api_key = os.getenv('ANTHROPIC_API_KEY')
		return ChatAnthropic(model='claude-3-5-sonnet-20241022', api_key=SecretStr(api_key))
	
llm = set_llm('google')
# llm = set_llm('OAI')	# NOSONAR
# llm = set_llm('github')	# NOSONAR
# llm = set_llm('grok')	# NOSONAR
# llm = set_llm('anthropic')	# NOSONAR



async def wait_for_app_ready(app, max_attempts=10, delay=2.5) -> bool:
	"""Wait for app to be ready with detailed status checking"""
	for i in range(max_attempts):
		try:
			if not app:
				print(f'Attempt {i + 1}/{max_attempts}: App object is None')
				await asyncio.sleep(delay)
				continue

			if app:
				app.activateWithOptions_(Cocoa.NSApplicationActivateIgnoringOtherApps)
				await asyncio.sleep(1)
				print('✅ App is running and ready')
				return True

			await asyncio.sleep(delay)

		except Exception as e:
			print(f'Error checking app status: {e}')
			await asyncio.sleep(delay)

	return False


class FolderCreationState:
	def __init__(self):
		self.new_folder_clicked = False
		self.folder_name_entered = False
		self.ok_clicked = False
		self.last_action = None
		self.action_history = []  # Track recent actions to prevent loops
		self.last_clicked_indices = []  # Track last clicked indices

	def get_context(self) -> str:
		context = ""
		if not self.new_folder_clicked:
			context = "Find and click the 'New Folder' button."
		elif not self.folder_name_entered:
			context = "The 'New Folder' button has been clicked. Look for the newly appeared text field to type the folder name."
		elif not self.ok_clicked:
			context = 'Folder name has been entered. Now find and click the "OK" button to confirm folder creation.'
		else:
			context = 'Folder creation process completed.'
		
		# Add recent action history to prevent loops
		if self.last_clicked_indices:
			context += f"\nRECENT CLICKS: {self.last_clicked_indices[-3:]} - AVOID REPEATING THESE!"
		
		# Add guidance based on current state
		if self.new_folder_clicked and not self.folder_name_entered:
			context += "\nLOOK FOR: Text field (AXTextField) to enter folder name"
		elif self.folder_name_entered and not self.ok_clicked:
			context += "\nLOOK FOR: OK button, Aceptar button, or any button to confirm"
		
		return context

	def update(self, action_name: str, success: bool = True, element_info: str = '', clicked_index: int = None) -> None:
		if not success:
			return

		# Track action history
		self.action_history.append(f"{action_name}:{element_info[:50]}")
		if len(self.action_history) > 5:
			self.action_history.pop(0)  # Keep only last 5 actions
		
		# Track clicked indices
		if action_name == 'click' and clicked_index is not None:
			self.last_clicked_indices.append(clicked_index)
			if len(self.last_clicked_indices) > 5:
				self.last_clicked_indices.pop(0)  # Keep only last 5 indices

		if action_name == 'click' and 'New Folder' in element_info:
			self.new_folder_clicked = True
			self.last_action = 'clicked_new_folder'
		elif action_name == 'type' and self.new_folder_clicked and 'Ofir folder' in element_info:
			self.folder_name_entered = True
			self.last_action = 'entered_folder_name'
		elif action_name == 'click' and self.folder_name_entered and ('OK' in element_info or 'button' in element_info.lower()):
			self.ok_clicked = True
			self.last_action = 'clicked_ok'


def process_action(action_json, builder, state):
	"""Process a single action from the LLM response"""
	action_name = action_json.get('action')
	parameters = action_json.get('parameters', {})
	
	success = False
	if action_name == 'click':
		index_to_click = parameters.get('index')
		print(f'🔍 Attempting to click index: {index_to_click}')
		if isinstance(index_to_click, int) and index_to_click in builder._element_cache:
			element_to_click = builder._element_cache[index_to_click]
			print(f'🎯 Clicking element: {element_to_click}')
			success = click(element_to_click, 'AXPress')
			print(f'✅ Click successful: {success}')
			state.update(action_name, success, str(element_to_click), index_to_click)
		else:
			print(f'❌ Invalid index {index_to_click} for click action. Available indices: {list(builder._element_cache.keys())[:10]}...')
	elif action_name == 'type':
		index_to_type = parameters.get('index')
		text_to_type = parameters.get('text')
		print(f'🔍 Attempting to type "{text_to_type}" into index: {index_to_type}')
		if isinstance(index_to_type, int) and text_to_type is not None and index_to_type in builder._element_cache:
			element_to_type_into = builder._element_cache[index_to_type]
			print(f'🎯 Typing into element: {element_to_type_into}')
			success = type_into(element_to_type_into, text_to_type)
			print(f'✅ Typing successful: {success}')
			state.update(action_name, success)
		else:
			print(f'❌ Invalid index {index_to_type} or text for type action. Available indices: {list(builder._element_cache.keys())[:10]}...')
	else:
		print(f'❌ Unknown action: {action_name}')
	
	state.update(action_name, success)
	return success


async def launch_notes_app():
	"""Launch and find the Notes app"""
	workspace = Cocoa.NSWorkspace.sharedWorkspace()
	
	print(f'\nLaunching {NOTES_APP_NAME} app...')
	success = workspace.launchApplication_(NOTES_APP_NAME)
	
	if not success:
		print(f'❌ Failed to launch {NOTES_APP_NAME} app')
		return None
	
	# Find Notes app
	await asyncio.sleep(2)
	notes_app = None
	for app in workspace.runningApplications():
		if app.bundleIdentifier() and NOTES_BUNDLE_ID.lower() in app.bundleIdentifier().lower():
			notes_app = app
			print(f'\nFound {NOTES_APP_NAME} app!')
			print(f'Bundle ID: {app.bundleIdentifier()}')
			print(f'PID: {app.processIdentifier()}')
			break
	
	if not notes_app:
		print(f'❌ Could not find {NOTES_APP_NAME} app')
		return None
	
	is_ready = await wait_for_app_ready(notes_app)
	if not is_ready:
		print('❌ App failed to become ready')
		return None
	
	return notes_app


def create_prompt(state_context, ui_tree_string):
	"""Create the prompt for the LLM"""
	return f"""You are an intelligent agent designed to automate tasks within the macOS "Notes" application.

Current Goal: Create a new folder in the notes app called 'Ofir folder'.
Current Step: {state_context}

To create a new folder, you need to:
1. Click the "New Folder" button.
2. After clicking "New Folder", a **new text field will appear**. This is where you should type the folder name. **Do not type into the search bar.**
3. Type "Ofir folder" into the new text field.
4. Click the "OK" button to create the folder.

You can interact with the application by performing the following actions:

- **click**: Simulate a click on an interactive element. To perform this action, you need to specify the `index` of the element to click.
- **type**: Simulate typing text into a text field. To perform this action, you need to specify the `index` of the text field and the `text` to type.

Here is the current state of the "Notes" application's user interface, represented as a tree structure. Each interactive element is marked with a `highlight` index that you can use to target it for an action:

{ui_tree_string}

Based on the current UI and your goal, choose the next action you want to perform. Respond with a JSON object in the following format:

RESPONSE FORMAT: You must ALWAYS respond with valid JSON in this exact format:
{{
  "action": "click" or "type",
  "parameters": {{
    "index": <element_index>
    }} // OR
    "index": <element_index>,
    "text": "<text_to_type>"
  }}
}}

For example, to click the element with highlight: 1, you would respond with:

{{
  "action": "click",
  "parameters": {{
    "index": 1
  }}
}}

To type "Hello" into the text field with highlight: 5, you would respond with:

{{
  "action": "type",
  "parameters": {{
    "index": 5,
    "text": "Hello"
  }}
}}

After each action, you will receive feedback on whether the action was successful. Use this feedback to adjust your strategy and achieve the goal.

Remember your goal: "Create a new folder in the notes app called 'Ofir folder'". Analyze the current UI and available actions carefully to determine the most effective next step."""


def process_llm_response(llm_response, builder, state):
	"""Process the LLM response and execute the action"""
	try:
		response_content = llm_response.content.strip()
		
		# Handle empty response
		if not response_content:
			print('❌ Empty response from LLM - may be due to safety filtering')
			print('💡 Trying fallback action...')
			# Fallback: click the first available element
			if builder._element_cache:
				first_index = min(builder._element_cache.keys())
				fallback_action = {"action": "click", "parameters": {"index": first_index}}
				process_action(fallback_action, builder, state)
			return
		
		# Clean up the response by removing markdown code blocks
		if response_content.startswith('```') and response_content.endswith('```'):
			lines = response_content.split('\n')
			response_content = '\n'.join(lines[1:-1])  # Remove first and last lines

		# Additional cleaning for common issues
		response_content = response_content.strip()
		
		if not response_content:
			print('❌ Empty response after cleaning')
			return
			
		action_json = json.loads(response_content)
		
		# Handle case where LLM returns an array instead of object
		if isinstance(action_json, list) and len(action_json) > 0:
			action_json = action_json[0]  # Take the first element
		
		process_action(action_json, builder, state)

	except json.JSONDecodeError as e:
		print(f'❌ Could not decode LLM response as JSON: {e}')
		print(f'Raw response: "{llm_response.content}"')
	except Exception as e:
		print(f'❌ An error occurred: {e}')


def optimize_ui_tree_string(ui_tree_string):
	"""Optimize UI tree string to reduce token count while keeping essential elements"""
	lines = ui_tree_string.split('\n')
	optimized_lines = []
	
	# Focus on most essential elements - prioritize dialog elements
	essential_keywords = [
		'button', 'textfield', 'field', 'ok', 'create', 'done', 'confirm', 'cancel', 'highlight:', 
		'nueva carpeta', 'new folder', 'dialog', 'window', 'sheet', 'popup', 'modal',
		'aceptar', 'accept', 'save', 'guardar', 'aplicar', 'apply', 'axconfirm', 'axpress'
	]
	
	# Count elements for debugging
	button_count = 0
	textfield_count = 0
	
	for line in lines:
		line_lower = line.lower()
		
		# Keep lines with essential keywords
		if any(keyword in line_lower for keyword in essential_keywords):
			# Count specific elements
			if 'button' in line_lower:
				button_count += 1
			elif 'textfield' in line_lower or 'field' in line_lower:
				textfield_count += 1
			
			# Keep the line but truncate if too long
			if len(line) > 150:
				if 'highlight:' in line:
					# Keep the highlight part
					parts = line.split('highlight:')
					if len(parts) > 1:
						line = parts[0][:80] + '... highlight:' + parts[1]
				else:
					line = line[:150] + '...'
			optimized_lines.append(line)
		
		# Keep minimal structural lines
		elif len(line.strip()) < 15 and ('│' in line or '├' in line or '└' in line):
			optimized_lines.append(line)
	
	# Limit for performance
	if len(optimized_lines) > 60:
		optimized_lines = optimized_lines[:60]
		optimized_lines.append('... (UI tree truncated)')
	
	# Add debug info
	optimized_lines.append(f'\n[DEBUG] Found {button_count} buttons, {textfield_count} text fields')
	
	return '\n'.join(optimized_lines)


async def main():
	try:
		state = FolderCreationState()
		
		notes_app = await launch_notes_app()
		if not notes_app:
			return

		builder = MacUITreeBuilder()
		# Prioritize performance over completeness
		builder.max_children = 50   # Reduced drastically for performance
		builder.max_depth = 10      # Reduced for performance
		max_steps = 10  # Limit the number of interaction steps
		goal_achieved = False
		last_step_time = time.time()
		
		for step in range(max_steps):
			if goal_achieved:
				print('✅ Goal already achieved, stopping further actions')
				break

			step_start_time = time.time()
			timestamp = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
			time_since_last = step_start_time - last_step_time if step > 0 else 0
			
			print(f'\n--- Step {step + 1}/{max_steps} [{timestamp}] (Time since last: {time_since_last:.2f}s) ---')
			
			tree_build_start = time.time()
			root = await builder.build_tree(notes_app.processIdentifier())
			tree_build_time = time.time() - tree_build_start
			print(f'UI tree build time: {tree_build_time:.2f}s')

			if not root:
				print(f'❌ Failed to build UI tree for {NOTES_APP_NAME}')
				break

			ui_tree_string = root.get_clickable_elements_string()
			
			# Optimize UI tree to reduce tokens
			optimized_ui_tree = optimize_ui_tree_string(ui_tree_string)
			original_length = len(ui_tree_string)
			optimized_length = len(optimized_ui_tree)
			print(f'UI tree optimized: {original_length} -> {optimized_length} chars ({((original_length - optimized_length) / original_length * 100):.1f}% reduction)')

			# Add state context to the prompt
			state_context = state.get_context()
			prompt = create_prompt(state_context, optimized_ui_tree)

			llm_start_time = time.time()
			llm_response = llm.invoke(prompt)
			llm_time = time.time() - llm_start_time
			print(f'LLM response time: {llm_time:.2f}s')
			print(f'LLM Response.content is: {llm_response.content}\n\n')

			process_llm_response(llm_response, builder, state)

			# Check for typing loops - if typing into the same element repeatedly
			if len(state.action_history) >= 3:
				recent_actions = state.action_history[-3:]
				if all('type:' in action and 'Ofir folder' in action for action in recent_actions):
					print("🔄 TYPING LOOP DETECTED! Typing 'Ofir folder' repeatedly.")
					print("💡 Text already entered, looking for OK button...")
					state.folder_name_entered = True
					
					# First try AXConfirm on the text field itself (it has AXConfirm action)
					text_field_index = 132  # The text field index from the logs
					if text_field_index in builder._element_cache:
						text_field = builder._element_cache[text_field_index]
						if 'AXConfirm' in text_field.actions:
							print(f"🎯 Using AXConfirm on text field: {text_field}")
							try:
								from mlx_use.mac.actions import perform_action
								success = perform_action(text_field, 'AXConfirm')
								if success:
									state.update('click', True, str(text_field), text_field_index)
									state.ok_clicked = True
									print("✅ Successfully used AXConfirm on text field")
								else:
									print("❌ AXConfirm failed on text field")
							except Exception as e:
								print(f"❌ Error with AXConfirm: {e}")
					
					# If that fails, look for buttons that might confirm the action
					for index, element in builder._element_cache.items():
						element_str = str(element).lower()
						if 'button' in element_str and ('ok' in element_str or 'accept' in element_str or 'confirm' in element_str):
							print(f"🎯 Found potential OK button: {element}")
							try:
								success = click(element, 'AXPress')
								if success:
									state.update('click', True, str(element), index)
									state.ok_clicked = True
									print("✅ Successfully clicked OK button")
									break
							except Exception as e:
								print(f"❌ Error with button {index}: {e}")
								continue

			# Check for loops - if clicking the same element repeatedly
			if len(state.last_clicked_indices) >= 3:
				recent_clicks = state.last_clicked_indices[-3:]
				if len(set(recent_clicks)) == 1:  # All same index
					print(f"🔄 LOOP DETECTED! Clicking same element {recent_clicks[0]} repeatedly.")
					print("💡 Forcing different action to break loop...")
					# Force a different action - look for text fields or other buttons
					available_indices = list(builder._element_cache.keys())
					different_indices = [i for i in available_indices if i not in recent_clicks]
					if different_indices:
						print(f"🎯 Trying alternative element: {different_indices[0]}")
						# Try to click a different element
						try:
							alt_element = builder._element_cache[different_indices[0]]
							click(alt_element, 'AXPress')
							state.update('click', True, str(alt_element), different_indices[0])
						except:
							pass

			# Check if goal has been achieved
			if state.ok_clicked and 'Ofir folder' in ui_tree_string:
				print("✅ Goal achieved! 'Ofir folder' created and confirmed.")
				goal_achieved = True
				continue

			# Update last step time
			last_step_time = time.time()
			step_total_time = last_step_time - step_start_time
			print(f'Step {step + 1} total time: {step_total_time:.2f}s')

			# Reduced sleep time for better performance
			await asyncio.sleep(0.5)  # Give time for the UI to update

	except Exception as e:
		print(f'❌ Error: {e}')
		import traceback

		traceback.print_exc()
	finally:
		if 'builder' in locals():
			builder.cleanup()


if __name__ == '__main__':
	asyncio.run(main())
