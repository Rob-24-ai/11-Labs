"""
Central configuration for LLM provider selection and settings.
This file enables easy switching between different LLM providers.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Single point of configuration - change this one setting to switch providers
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()  # "openai" or "gemini"

# Provider-specific configurations derived from the single setting
if LLM_PROVIDER == "gemini":
    # Gemini configuration
    API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("OPENAI_API_KEY"))  # Fallback support
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
    # Use exact Gemini model version as requested
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-2.5-pro-preview-03-25")  # Using precise model version
else:  # Default to OpenAI
    API_KEY = os.getenv("OPENAI_API_KEY")
    BASE_URL = None  # Use OpenAI's default
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o")

# Print configuration on startup for verification
print(f"LLM Configuration: Provider={LLM_PROVIDER}, Model={DEFAULT_MODEL}")
