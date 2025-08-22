#!/usr/bin/env python3
"""
Minimal script to validate OpenAI API key.

Usage:
    python3 tests/test_openai_key.py
    python3 -m pytest tests/test_openai_key.py -v
"""

import os
import sys
from typing import Optional

import openai
from dotenv import load_dotenv


def get_openai_key() -> Optional[str]:
    """
    Get OpenAI API key from environment.
    
    Returns:
        str: API key if found, None otherwise.
    """
    # Load from .env file if exists
    load_dotenv()
    
    # Try multiple environment variable names
    for key_name in ["OPENAI_API_KEY", "OPENAI_KEY", "API_KEY"]:
        key = os.getenv(key_name)
        if key and key.strip():
            return key.strip()
    
    return None


def validate_openai_key(api_key: str) -> tuple[bool, str]:
    """
    Validate OpenAI API key by making a minimal API call.
    
    Args:
        api_key (str): The API key to validate.
        
    Returns:
        tuple[bool, str]: (is_valid, message)
    """
    if not api_key:
        return False, "API key is empty"
    
    if not api_key.startswith("sk-"):
        return False, "API key format invalid (should start with 'sk-')"
    
    try:
        # Create client
        client = openai.OpenAI(api_key=api_key)
        
        # Make minimal API call to validate key
        response = client.models.list()
        
        # Check if we got models back
        if hasattr(response, 'data') and len(response.data) > 0:
            return True, f"✅ Valid key - {len(response.data)} models available"
        else:
            return False, "❌ Key valid but no models accessible"
            
    except openai.AuthenticationError:
        return False, "❌ Invalid API key - authentication failed"
    except openai.RateLimitError:
        return True, "✅ Key valid but rate limited"
    except openai.APIError as e:
        return False, f"❌ API error: {e}"
    except Exception as e:
        return False, f"❌ Unexpected error: {e}"


def main():
    """Main validation function."""
    print("🔑 OpenAI API Key Validator")
    print("=" * 30)
    
    # Get API key
    api_key = get_openai_key()
    
    if not api_key:
        print("❌ No OpenAI API key found in environment")
        print("Set OPENAI_API_KEY in .env file or environment")
        sys.exit(1)
    
    # Mask key for display
    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "sk-***"
    print(f"🔍 Testing key: {masked_key}")
    
    # Validate key
    is_valid, message = validate_openai_key(api_key)
    
    print(f"📊 Result: {message}")
    
    if is_valid:
        print("🎉 OpenAI API key is valid!")
        sys.exit(0)
    else:
        print("💥 OpenAI API key validation failed!")
        sys.exit(1)


# Pytest test function
def test_openai_key_validation():
    """Pytest test for OpenAI API key validation."""
    api_key = get_openai_key()
    
    # Skip test if no key available
    if not api_key:
        import pytest
        pytest.skip("No OpenAI API key found in environment")
    
    is_valid, message = validate_openai_key(api_key)
    
    assert is_valid, f"OpenAI API key validation failed: {message}"
    print(f"✅ Key validation passed: {message}")


if __name__ == "__main__":
    main()