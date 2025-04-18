import os
import base64
from typing import Dict, List, Optional, Union, Any
from openai import OpenAI, APIError
import requests
from io import BytesIO
from PIL import Image

from llm_service import LLMService
# Import central configuration
from llm_config import API_KEY, BASE_URL

class OpenAIService(LLMService):
    """
    OpenAI implementation of the LLMService interface.
    Handles communication with OpenAI's API for chat completions and image processing.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the OpenAI service with an API key.
        
        Args:
            api_key: OpenAI API key (will use environment variable if not provided)
        """
        # Use provided API key or the one from central config
        self.api_key = api_key or API_KEY
        
        # Create client with conditional parameters based on provider
        client_params = {"api_key": self.api_key}
        
        # Add base_url for Gemini if specified in config
        if BASE_URL:
            client_params["base_url"] = BASE_URL
            print(f"Using custom base URL: {BASE_URL}")
        
        # Initialize the OpenAI client with the appropriate parameters
        self.client = OpenAI(**client_params)
    
    def chat_completion(self, 
                       messages: List[Dict[str, Any]], 
                       model: Optional[str] = None,
                       temperature: Optional[float] = 0.7,
                       max_tokens: Optional[int] = None,
                       stream: bool = False) -> Union[Dict[str, Any], Any]:
        """
        Generate a chat completion using OpenAI's API.
        
        Args:
            messages: List of message objects with role and content
            model: OpenAI model to use (default: gpt-4o)
            temperature: Temperature parameter (default: 0.7)
            max_tokens: Maximum number of tokens to generate
            stream: Whether to stream the response
            
        Returns:
            Either a completion response object or a stream
        """
        try:
            # Use provided model or default from config
            from llm_config import DEFAULT_MODEL, LLM_PROVIDER
            model_name = model if model is not None else DEFAULT_MODEL
            
            # Log request details for debugging
            print(f"Making LLM request with provider: {LLM_PROVIDER}, model: {model_name}")
            print(f"Stream mode: {stream}")
            
            # Prepare parameters for the API call with detailed logging
            print(f"\n=== MODEL DEBUG INFO ===\n")
            print(f"Using provider: {LLM_PROVIDER}")
            print(f"Raw model_name: {model_name}")
            
            # CRITICAL FIX: When using Gemini, ensure model name is correctly formatted
            if LLM_PROVIDER == 'gemini':
                # For Gemini API compatibility
                if not model_name.startswith('gemini-'):
                    print(f"WARNING: Model name {model_name} doesn't look like a Gemini model, forcing use of gemini-1.5-pro")
                    model_name = 'gemini-1.5-pro'
            
            print(f"Final model_name: {model_name}")
            
            params = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "stream": stream
            }
            
            print(f"Full params: {params}")
            print(f"=== END MODEL DEBUG INFO ===\n")
            
            # Add max_tokens if provided
            if max_tokens is not None:
                params["max_tokens"] = max_tokens
                
            response = self.client.chat.completions.create(**params)
            
            # Ensure a valid response is always returned, even if response structure differs
            if stream:
                return response  # Return the stream iterator directly
            else:
                # For non-streaming responses, ensure we return a valid object
                # that can be converted to JSON by app.py
                try:
                    # Try model_dump if available (typical for OpenAI responses)
                    return response
                except (AttributeError, TypeError) as e:
                    # If model_dump fails, attempt to handle as a dict-like structure
                    print(f"Warning: Could not use model_dump on response: {e}")
                    # If it's a dict or dict-like, return it directly
                    if hasattr(response, '__getitem__') and hasattr(response, 'keys'):
                        return response
                    # Otherwise, try to convert to a dict
                    return {
                        "id": getattr(response, "id", "gemini-response"),
                        "object": "chat.completion",
                        "created": getattr(response, "created", 0),
                        "model": model_name,
                        "choices": [{
                            "index": 0, 
                            "message": {
                                "role": "assistant",
                                "content": str(getattr(response, "content", str(response)))
                            },
                            "finish_reason": "stop"
                        }]
                    }
                    
        except Exception as e:
            # Log the error and re-raise with more details
            print(f"LLM API Error with {LLM_PROVIDER} model {model_name}: {str(e)}")
            import traceback
            print(traceback.format_exc())
            # Return a valid error response that can be converted to JSON
            return {
                "error": {
                    "message": f"Error in chat completion: {str(e)}",
                    "type": "api_error"
                }
            }
    
    def process_image(self, image_data: Union[str, bytes]) -> str:
        """
        Process an image for inclusion in an OpenAI message.
        
        Args:
            image_data: Either a URL string or raw image bytes
            
        Returns:
            Processed image data in the format expected by OpenAI
        """
        # If image_data is a URL, return it directly as OpenAI supports image URLs
        if isinstance(image_data, str) and (image_data.startswith('http://') or image_data.startswith('https://')):
            return image_data
        
        # If image_data is bytes, encode as base64
        if isinstance(image_data, bytes):
            # Convert to base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            return f"data:image/jpeg;base64,{base64_image}"
        
        # If it's a string but not a URL, assume it's already base64 encoded
        return image_data
