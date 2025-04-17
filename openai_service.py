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
            from llm_config import DEFAULT_MODEL
            model_name = model if model is not None else DEFAULT_MODEL
            # Prepare parameters for the API call
            params = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "stream": stream
            }
            
            # Add max_tokens if provided
            if max_tokens is not None:
                params["max_tokens"] = max_tokens
                
            response = self.client.chat.completions.create(**params)
            return response
        except APIError as e:
            # Log the error and re-raise
            print(f"OpenAI API Error: {str(e)}")
            raise
    
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
