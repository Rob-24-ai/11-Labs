# Switching from OpenAI GPT to Google Gemini using the OpenAI SDK

This document outlines how to modify the Flask backend (specifically the LLM service integration) to use Google's Gemini models instead of OpenAI's GPT models, while still using the familiar OpenAI Python SDK. This is possible due to Google providing an [OpenAI-compatible endpoint](https://ai.google.dev/gemini-api/docs/openai) for their Gemini API.

## Why Switch?

*   **Modularity:** Allows swapping LLM backends without rewriting large parts of the application. This is a common practice for flexibility and resilience.
*   **Leveraging Gemini Strengths:** As Kyle mentioned, specific Gemini models (like Gemini 2.5 Pro) might offer superior performance for certain tasks, such as image understanding.
*   **Experimentation:** Provides an easy way to compare the outputs and capabilities of different state-of-the-art models.

## Modular Design Approach

### Core Strategy: Single Point of Configuration

To implement a truly modular system with minimal code changes, we'll create a central configuration mechanism that allows switching providers by changing just one variable.

```python
# llm_config.py - New central configuration file

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
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-1.5-pro")
else:  # Default to OpenAI
    API_KEY = os.getenv("OPENAI_API_KEY")
    BASE_URL = None  # Use OpenAI's default
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o")
```

### Minimal Implementation Changes

Following the new modular design, here's how the existing code would be minimally modified:

## How to Switch (3 Key Changes and 1 Integration)

Based on the conversation with Kyle and the official Google documentation, three primary changes plus one integration step are needed within the existing codebase structure:

1.  **API Key (in `.env` file):**
    ```
    # Add this variable to control which provider to use
    LLM_PROVIDER=openai  # or "gemini"
    
    # Keep your existing OpenAI key
    OPENAI_API_KEY=sk-...
    
    # Add a Gemini key
    GEMINI_API_KEY=...  # Get from Google AI Studio
    ```

    *   Obtain an API key for the Gemini API from [Google AI Studio](https://aistudio.google.com/app/apikey).
    *   Rather than overwriting your OpenAI key, this approach keeps both keys and uses the appropriate one based on the provider setting.

2.  **Base URL (in OpenAIService):**
    *   Modify the OpenAI client initialization to conditionally include the base_url parameter.
    *   **Example Change (in `openai_service.py`):**
    
        ```python
        # Before:
        self.client = OpenAI(api_key=self.api_key)
        
        # After - with imported configuration
        from llm_config import API_KEY, BASE_URL
        
        # In the __init__ method
        self.api_key = api_key or API_KEY
        
        # Conditionally add base_url based on current provider
        client_params = {"api_key": self.api_key}
        if BASE_URL:  # Only add for Gemini (None for OpenAI)
            client_params["base_url"] = BASE_URL
            
        self.client = OpenAI(**client_params)
        ```

3.  **Model Name (in `app.py`):**
    *   Import the default model from the central configuration rather than reading directly from environment variables.
    *   This ensures the correct default model is used based on the selected provider.
    
    ```python
    # Before:
    model=os.getenv('DEFAULT_MODEL', 'gpt-4o')
    
    # After:
    from llm_config import DEFAULT_MODEL
    model=model or DEFAULT_MODEL  # Use provided model or config default
    ```
    
4.  **Integration Step - Create Configuration Module:**
    *   Create the `llm_config.py` file described above to centralize provider settings
    *   Import this configuration in both `openai_service.py` and `app.py`
    *   This is the key step that ties everything together for modularity

## Summary Example (with modular configuration)

This snippet demonstrates how the modular approach simplifies provider switching:

```python
# 1. Configuration module (llm_config.py)
import os
from dotenv import load_dotenv

load_dotenv()

# Single configuration point
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()

# Provider-specific settings derived from the single configuration
if LLM_PROVIDER == "gemini":
    API_KEY = os.getenv("GEMINI_API_KEY")
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-1.5-pro")
else:  # Default to OpenAI
    API_KEY = os.getenv("OPENAI_API_KEY")
    BASE_URL = None
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o")

# 2. Service module (using the configuration)
from openai import OpenAI
from llm_config import API_KEY, BASE_URL, DEFAULT_MODEL

# Build client with provider-specific configuration
client_params = {"api_key": API_KEY}
if BASE_URL:
    client_params["base_url"] = BASE_URL
    
client = OpenAI(**client_params)

# The API call remains the same regardless of provider
response = client.chat.completions.create(
    model=DEFAULT_MODEL,
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": "Explain AI simply."
        }
    ]
)

print(response.choices[0].message.content)
```

With this approach, to switch providers you only need to change `LLM_PROVIDER=openai` to `LLM_PROVIDER=gemini` in your `.env` file. Everything else adapts automatically.

## Testing and Verification

1. **Test the Configuration Switch:**
   * First, test with `LLM_PROVIDER=openai` to ensure the original functionality works
   * Then, switch to `LLM_PROVIDER=gemini` to verify Gemini integration
   * In both cases, test the `/v1/chat/completions` endpoint without changing any code

2. **Verify Provider Identity:**
   * Add a simple debug log in your Flask app to show which provider is active:
     ```python
     app.logger.info(f"Using LLM provider: {LLM_PROVIDER} with model: {DEFAULT_MODEL}")
     ```
   * This confirms the switch is working as expected

## Caveats and Considerations

* **Beta Support:** As noted in Google's documentation, the OpenAI library compatibility is still in beta - some advanced features might differ slightly between providers
* **Model Capabilities:** While the API format is compatible, capabilities between GPT and Gemini models may differ, especially for specialized tasks
* **Image Handling:** Both providers support image analysis, but may have subtle differences in how they interpret or process images
* **Cost Considerations:** Check the pricing structure for both providers as this may influence which one to use for different scenarios
