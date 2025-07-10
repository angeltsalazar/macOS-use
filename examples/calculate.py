import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mlx_use import Agent
from mlx_use.controller.service import Controller
from mlx_use.mac.llm_utils import get_available_providers, get_default_provider, set_llm

# Use default provider or fallback to google
# default_provider = 'lmstudio' 
default_provider = get_default_provider() or 'google'

llm = set_llm(default_provider)

print(f"📊 Using LLM provider: {default_provider}")
print(f"📋 Available providers: {get_available_providers()}")

controller = Controller()

task = 'calculate how much is 5 X 4 and return the result, then call done.'


# Configure agent with higher max_depth for Calculator app
agent = Agent(
	task=task,
	llm=llm,
	controller=controller,
	use_vision=False,
	max_actions_per_step=10,
)

# Monkey-patch the tree builder to use higher depth for Calculator
original_build_tree = agent.mac_tree_builder.build_tree

async def build_tree_with_higher_depth(pid, force_refresh=False, lazy_mode=True):
    # Use higher depth for better element discovery
    return await original_build_tree(pid, force_refresh=force_refresh, lazy_mode=False, max_depth=10)

agent.mac_tree_builder.build_tree = build_tree_with_higher_depth


async def main():
	await agent.run(max_steps=10)


asyncio.run(main())
