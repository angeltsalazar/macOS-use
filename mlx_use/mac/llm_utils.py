"""
LLM utilities for macOS-use project.

This module provides common LLM configuration and setup functions
that can be shared across different examples and components.
"""

import os

from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import SecretStr


def set_llm(llm_provider: str = None):
    """
    Configure and return an LLM instance based on the provider.
    
    Args:
        llm_provider: The LLM provider to use. Options:
            - "OAI": OpenAI GPT-4o
            - "github": GitHub Models (OpenAI-compatible API)
            - "grok": xAI Grok-2
            - "google": Google Gemini 2.5 Pro
            - "google-pro": Google Gemini 2.5 Pro (lower token limit)
            - "anthropic": Anthropic Claude 3.5 Sonnet
            - "lmstudio": LM Studio local server
    
    Returns:
        LLM instance configured for the specified provider
        
    Raises:
        ValueError: If no provider is specified or provider is invalid
    """
    if not llm_provider:
        raise ValueError("No llm provider was set")
    
    if llm_provider == "OAI":
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for OAI provider")
        return ChatOpenAI(model='gpt-4o', api_key=SecretStr(api_key))

    if llm_provider == "github":
        api_key = os.getenv('GITHUB_TOKEN')
        if not api_key:
            raise ValueError("GITHUB_TOKEN environment variable is required for github provider")
        return ChatOpenAI(
            model='gpt-4o', 
            base_url="https://models.inference.ai.azure.com", 
            api_key=SecretStr(api_key)
        )

    if llm_provider == "grok":
        api_key = os.getenv('XAI_API_KEY')
        if not api_key:
            raise ValueError("XAI_API_KEY environment variable is required for grok provider")
        return ChatOpenAI(
            model='grok-2', 
            base_url="https://api.x.ai/v1", 
            api_key=SecretStr(api_key)
        )

    valid_models = [
        'gemini-2.5-pro', # Newer, more powerful model
        'gemini-2.5-flash-preview-04-17', 
        'gemini-2.5-flash'  # Flash model for agentic tasks
    ]
    if llm_provider == "google":
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required for google provider")
        return ChatGoogleGenerativeAI(
            model=valid_models[2],  
            api_key=SecretStr(api_key),
            temperature=0.1,  # Lower temperature for more consistent responses
            max_tokens=200000,   # High token limit for better reasoning
        )
    
    if llm_provider == "google-pro":
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required for google-pro provider")
        return ChatGoogleGenerativeAI(
            model=valid_models[0],  
            api_key=SecretStr(api_key),
            temperature=0.1,  # Lower temperature for more consistent responses
            max_tokens=30000,   # Lower token limit for cost efficiency
        )

    if llm_provider == "anthropic":
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required for anthropic provider")
        return ChatAnthropic(
            model='claude-3-5-sonnet-20241022', 
            api_key=SecretStr(api_key)
        )

    if llm_provider == "lmstudio":
        base_url = os.getenv('LMSTUDIO_BASE_URL', 'http://localhost:1234/v1')
        api_key = os.getenv('LMSTUDIO_API_KEY', 'lm-studio')  # LM Studio uses any non-empty key
        model = os.getenv('LMSTUDIO_MODEL', 'local-model')  # Default model name
        return ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=SecretStr(api_key),
            temperature=0.1
        )
    
    raise ValueError(f"Unknown LLM provider: {llm_provider}. "
                     f"Supported providers: OAI, github, grok, google, google-pro, anthropic, lmstudio")


def get_available_providers():
    """
    Get a list of available LLM providers based on environment variables.
    
    Returns:
        List of provider names that have the required API keys set
    """
    providers = []
    
    if os.getenv('OPENAI_API_KEY'):
        providers.append('OAI')
    
    if os.getenv('GITHUB_TOKEN'):
        providers.append('github')
    
    if os.getenv('XAI_API_KEY'):
        providers.append('grok')
    
    if os.getenv('GEMINI_API_KEY'):
        providers.extend(['google', 'google-pro'])
    
    if os.getenv('ANTHROPIC_API_KEY'):
        providers.append('anthropic')
    
    # LM Studio is always available as it runs locally
    providers.append('lmstudio')
    
    return providers


def get_default_provider():
    """
    Get the default LLM provider based on available API keys.
    
    Returns:
        Default provider name, or None if no API keys are available
    """
    # Preference order: google > anthropic > OAI > github > grok
    if os.getenv('GEMINI_API_KEY'):
        return 'google'
    if os.getenv('ANTHROPIC_API_KEY'):
        return 'anthropic'
    if os.getenv('OPENAI_API_KEY'):
        return 'OAI'
    if os.getenv('GITHUB_TOKEN'):
        return 'github'
    if os.getenv('XAI_API_KEY'):
        return 'grok'
    
    return None