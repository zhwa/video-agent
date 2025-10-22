"""
GraphFlow LLM Utilities

Supports multiple LLM providers:
- OpenAI (GPT models)
- Anthropic (Claude models) 
- Ollama (Local models)
- Any OpenAI-compatible API endpoint

Usage:
    from graphflow import call_llm, configure_llm

    # Configure your preferred provider
    configure_llm("openai", api_key="your-key", model="gpt-4")
    configure_llm("anthropic", api_key="your-key", model="claude-3-sonnet")
    configure_llm("ollama", base_url="http://localhost:11434", model="llama2")

    # Then use in your nodes
    def my_node(state):
        response = call_llm("What is the meaning of life?")
        return Command(update={"response": response}, goto="next")
"""

import os
import json
from typing import List, Dict, Any, Optional, Union
import requests

class LLMConfig:
    """Configuration for LLM providers"""
    def __init__(self):
        self.provider = "openai"  # default
        self.api_key = None
        self.base_url = None
        self.model = "gpt-4"
        self.temperature = 0.7
        self.max_tokens = 1000
        self.timeout = 30

# Global configuration
_llm_config = LLMConfig()

def configure_llm(
    provider: str = "openai",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: str = "gpt-4",
    temperature: float = 0.7,
    max_tokens: int = 1000,
    timeout: int = 30
):
    """
    Configure the LLM provider and settings.

    Args:
        provider: "openai", "anthropic", "ollama", or "custom"
        api_key: API key (not needed for Ollama)
        base_url: Custom base URL (for Ollama or custom endpoints)
        model: Model name to use
        temperature: Sampling temperature (0.0 to 1.0)
        max_tokens: Maximum tokens in response
        timeout: Request timeout in seconds
    """
    global _llm_config

    _llm_config.provider = provider.lower()
    _llm_config.api_key = api_key or os.environ.get(f"{provider.upper()}_API_KEY")
    _llm_config.base_url = base_url
    _llm_config.model = model
    _llm_config.temperature = temperature
    _llm_config.max_tokens = max_tokens
    _llm_config.timeout = timeout

    # Set default base URLs
    if not _llm_config.base_url:
        if provider == "ollama":
            _llm_config.base_url = "http://localhost:11434"
        elif provider == "openai":
            _llm_config.base_url = "https://api.openai.com/v1"
        elif provider == "anthropic":
            _llm_config.base_url = "https://api.anthropic.com"

def call_llm(
    prompt: Union[str, List[Dict[str, str]]],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None
) -> str:
    """
    Call the configured LLM with a prompt.

    Args:
        prompt: Either a string or list of message dicts
        model: Override the configured model
        temperature: Override the configured temperature
        max_tokens: Override the configured max_tokens

    Returns:
        The LLM response as a string

    Raises:
        Exception: If the LLM call fails
    """
    config = _llm_config

    # Use overrides if provided
    model = model or config.model
    temperature = temperature or config.temperature
    max_tokens = max_tokens or config.max_tokens

    # Convert string prompt to messages format
    if isinstance(prompt, str):
        messages = [{"role": "user", "content": prompt}]
    else:
        messages = prompt

    try:
        if config.provider == "openai":
            return _call_openai(messages, model, temperature, max_tokens)
        elif config.provider == "anthropic":
            return _call_anthropic(messages, model, temperature, max_tokens)
        elif config.provider == "ollama":
            return _call_ollama(messages, model, temperature, max_tokens)
        elif config.provider == "custom":
            return _call_custom_openai_compatible(messages, model, temperature, max_tokens)
        else:
            raise ValueError(f"Unsupported provider: {config.provider}")

    except Exception as e:
        raise Exception(f"LLM call failed: {str(e)}")

def _call_openai(messages: List[Dict], model: str, temperature: float, max_tokens: int) -> str:
    """Call OpenAI API"""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("OpenAI package not installed. Run: pip install openai")

    if not _llm_config.api_key:
        raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable or use configure_llm()")

    client = OpenAI(
        api_key=_llm_config.api_key,
        base_url=_llm_config.base_url,
        timeout=_llm_config.timeout
    )

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )

    return response.choices[0].message.content

def _call_anthropic(messages: List[Dict], model: str, temperature: float, max_tokens: int) -> str:
    """Call Anthropic API"""
    try:
        from anthropic import Anthropic
    except ImportError:
        raise ImportError("Anthropic package not installed. Run: pip install anthropic")

    if not _llm_config.api_key:
        raise ValueError("Anthropic API key not provided. Set ANTHROPIC_API_KEY environment variable or use configure_llm()")

    client = Anthropic(
        api_key=_llm_config.api_key,
        timeout=_llm_config.timeout
    )

    # Convert messages format for Anthropic
    if messages[0]["role"] == "system":
        system_message = messages[0]["content"]
        messages = messages[1:]
    else:
        system_message = None

    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages
    }

    if system_message:
        kwargs["system"] = system_message

    response = client.messages.create(**kwargs)
    return response.content[0].text

def _call_ollama(messages: List[Dict], model: str, temperature: float, max_tokens: int) -> str:
    """Call Ollama API (local)"""
    url = f"{_llm_config.base_url}/api/chat"

    payload = {
        "model": model,
        "messages": messages,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens
        },
        "stream": False
    }

    response = requests.post(
        url, 
        json=payload, 
        timeout=_llm_config.timeout
    )

    if response.status_code != 200:
        raise Exception(f"Ollama API error: {response.status_code} - {response.text}")

    result = response.json()
    return result["message"]["content"]

def _call_custom_openai_compatible(messages: List[Dict], model: str, temperature: float, max_tokens: int) -> str:
    """Call custom OpenAI-compatible API"""
    url = f"{_llm_config.base_url}/chat/completions"

    headers = {
        "Content-Type": "application/json"
    }

    if _llm_config.api_key:
        headers["Authorization"] = f"Bearer {_llm_config.api_key}"

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=_llm_config.timeout
    )

    if response.status_code != 200:
        raise Exception(f"API error: {response.status_code} - {response.text}")

    result = response.json()
    return result["choices"][0]["message"]["content"]

# Async versions
async def call_llm_async(
    prompt: Union[str, List[Dict[str, str]]],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None
) -> str:
    """
    Async version of call_llm.

    Note: Currently runs sync calls in thread pool.
    For true async, use provider-specific async clients.
    """
    import asyncio
    import concurrent.futures

    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        return await loop.run_in_executor(
            executor, 
            call_llm, 
            prompt, 
            model, 
            temperature, 
            max_tokens
        )

# Convenience functions for common patterns
def ask_llm(question: str, **kwargs) -> str:
    """Simple question-answer interface"""
    return call_llm(question, **kwargs)

def chat_with_llm(messages: List[Dict[str, str]], **kwargs) -> str:
    """Multi-turn conversation interface"""
    return call_llm(messages, **kwargs)

def get_llm_config() -> Dict[str, Any]:
    """Get current LLM configuration"""
    return {
        "provider": _llm_config.provider,
        "model": _llm_config.model,
        "temperature": _llm_config.temperature,
        "max_tokens": _llm_config.max_tokens,
        "base_url": _llm_config.base_url,
        "timeout": _llm_config.timeout,
        "has_api_key": bool(_llm_config.api_key)
    }

# Auto-configure from environment on import
def _auto_configure():
    """Try to auto-configure from environment variables"""
    try:
        if os.environ.get("OPENAI_API_KEY"):
            configure_llm("openai", api_key=os.environ.get("OPENAI_API_KEY"))
        elif os.environ.get("ANTHROPIC_API_KEY"):
            configure_llm("anthropic", api_key=os.environ.get("ANTHROPIC_API_KEY"))
        elif requests.get("http://localhost:11434/api/tags", timeout=2).status_code == 200:
            # Ollama is running locally
            configure_llm("ollama", model="llama2")
    except:
        pass  # No auto-configuration possible

# Run auto-configuration
try:
    _auto_configure()
except:
    pass  # Silent failure for auto-config

if __name__ == "__main__":
    # Test the LLM utilities
    print("GraphFlow LLM Utilities Test")
    print("=" * 40)

    # Show current config
    config = get_llm_config()
    print(f"Provider: {config['provider']}")
    print(f"Model: {config['model']}")
    print(f"Has API Key: {config['has_api_key']}")
    print()

    # Test call (will use whatever is configured)
    try:
        response = ask_llm("What is 2+2? Answer briefly.")
        print(f"Test question: What is 2+2?")
        print(f"LLM response: {response}")
    except Exception as e:
        print(f"LLM call failed: {e}")
        print("\nTo use LLM utilities, configure a provider:")
        print("1. OpenAI: Set OPENAI_API_KEY environment variable")
        print("2. Anthropic: Set ANTHROPIC_API_KEY environment variable") 
        print("3. Ollama: Start Ollama server (ollama serve)")