import os
import base64
from typing import Dict, List, Optional, Union, Any
from openai import OpenAI, APIError
import requests
from io import BytesIO
from PIL import Image

from llm_service import LLMService

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
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
    
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
            # Ensure we always have a model parameter
            model_name = model if model is not None else "gpt-4o"
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
