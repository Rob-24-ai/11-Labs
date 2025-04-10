import os
import base64
import requests
from typing import Dict, List, Optional, Union, Any
from io import BytesIO

from llm_service import LLMService

class AnthropicService(LLMService):
    """
    Anthropic implementation of the LLMService interface.
    Handles communication with Anthropic's API for chat completions and image processing.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Anthropic service with an API key.
        
        Args:
            api_key: Anthropic API key (will use environment variable if not provided)
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.api_url = "https://api.anthropic.com/v1/messages"
        
    def chat_completion(self, 
                       messages: List[Dict[str, Any]], 
                       model: Optional[str] = "claude-3-opus-20240229",
                       temperature: Optional[float] = 0.7,
                       stream: bool = False) -> Union[Dict[str, Any], Any]:
        """
        Generate a chat completion using Anthropic's API.
        
        Args:
            messages: List of message objects with role and content (OpenAI format)
            model: Anthropic model to use (default: claude-3-opus-20240229)
            temperature: Temperature parameter (default: 0.7)
            stream: Whether to stream the response
            
        Returns:
            Either a completion response object or a stream
        """
        # Convert OpenAI format messages to Anthropic format
        anthropic_messages = self._convert_to_anthropic_format(messages)
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": anthropic_messages,
            "temperature": temperature,
            "stream": stream,
            "max_tokens": 4096
        }
        
        response = requests.post(self.api_url, headers=headers, json=data, stream=stream)
        response.raise_for_status()
        
        if stream:
            return response.iter_lines()
        else:
            return response.json()
    
    def process_image(self, image_data: Union[str, bytes]) -> Dict[str, Any]:
        """
        Process an image for inclusion in an Anthropic message.
        
        Args:
            image_data: Either a URL string or raw image bytes
            
        Returns:
            Processed image data in the format expected by Anthropic
        """
        # If image_data is a URL, return it in Anthropic's format
        if isinstance(image_data, str) and (image_data.startswith('http://') or image_data.startswith('https://')):
            return {
                "type": "image",
                "source": {
                    "type": "url",
                    "url": image_data
                }
            }
        
        # If image_data is bytes, encode as base64
        if isinstance(image_data, bytes):
            base64_image = base64.b64encode(image_data).decode('utf-8')
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64_image
                }
            }
        
        # If it's already a base64 string (without the data URI prefix)
        if isinstance(image_data, str) and not (image_data.startswith('http://') or image_data.startswith('https://')):
            # Remove data URI prefix if present
            if image_data.startswith('data:'):
                # Extract the base64 part
                base64_image = image_data.split(',')[1]
            else:
                base64_image = image_data
                
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64_image
                }
            }
    
    def _convert_to_anthropic_format(self, openai_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert messages from OpenAI format to Anthropic format.
        
        Args:
            openai_messages: Messages in OpenAI format
            
        Returns:
            Messages in Anthropic format
        """
        anthropic_messages = []
        
        for msg in openai_messages:
            role = msg["role"]
            
            # Map OpenAI roles to Anthropic roles
            if role == "system":
                # System messages in Anthropic are handled differently
                # For simplicity, we'll add it as a user message with a prefix
                anthropic_messages.append({
                    "role": "user",
                    "content": [{"type": "text", "text": f"System instruction: {msg['content']}"}]
                })
            elif role == "user" or role == "assistant":
                # Convert content to Anthropic's format
                content = []
                
                # Handle string content
                if isinstance(msg["content"], str):
                    content.append({"type": "text", "text": msg["content"]})
                # Handle array content (for multimodal)
                elif isinstance(msg["content"], list):
                    for item in msg["content"]:
                        if item.get("type") == "text":
                            content.append({"type": "text", "text": item["text"]})
                        elif item.get("type") == "image_url":
                            # Process image URL
                            image_url = item["image_url"]
                            if isinstance(image_url, str):
                                content.append({
                                    "type": "image",
                                    "source": {
                                        "type": "url",
                                        "url": image_url
                                    }
                                })
                            elif isinstance(image_url, dict) and "url" in image_url:
                                # Handle base64 images
                                if image_url["url"].startswith("data:"):
                                    media_type = "image/jpeg"
                                    if ";" in image_url["url"]:
                                        media_type = image_url["url"].split(";")[0].split(":")[1]
                                    
                                    base64_data = image_url["url"].split(",")[1]
                                    content.append({
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": media_type,
                                            "data": base64_data
                                        }
                                    })
                                else:
                                    content.append({
                                        "type": "image",
                                        "source": {
                                            "type": "url",
                                            "url": image_url["url"]
                                        }
                                    })
                
                # Map the role and add the content
                anthropic_role = "user" if role == "user" else "assistant"
                anthropic_messages.append({
                    "role": anthropic_role,
                    "content": content
                })
        
        return anthropic_messages
