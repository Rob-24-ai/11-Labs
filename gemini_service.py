import os
import base64
from typing import Dict, List, Optional, Union, Any
import google.generativeai as genai
from io import BytesIO
from PIL import Image

from llm_service import LLMService

class GeminiService(LLMService):
    """
    Google Gemini implementation of the LLMService interface.
    Handles communication with Google's Generative AI API for chat completions and image processing.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Gemini service with an API key.
        
        Args:
            api_key: Google API key (will use environment variable if not provided)
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        genai.configure(api_key=self.api_key)
    
    def chat_completion(self, 
                       messages: List[Dict[str, Any]], 
                       model: Optional[str] = None,
                       temperature: Optional[float] = 0.7,
                       max_tokens: Optional[int] = None,
                       stream: bool = False) -> Union[Dict[str, Any], Any]:
        """
        Generate a chat completion using Google's Gemini API.
        
        Args:
            messages: List of message objects with role and content (OpenAI format)
            model: Gemini model to use (default: gemini-1.5-pro)
            temperature: Temperature parameter (default: 0.7)
            max_tokens: Maximum number of tokens to generate
            stream: Whether to stream the response
            
        Returns:
            Either a completion response object or a stream
        """
        # Convert OpenAI format messages to Gemini format
        gemini_messages = self._convert_to_gemini_format(messages)
        
        # Initialize the model with a default if not specified
        model_name = model if model is not None else "gemini-1.5-pro"
        model_obj = genai.GenerativeModel(model_name=model_name)
        
        # Create a chat session
        chat = model_obj.start_chat(history=gemini_messages)
        
        # Prepare generation config
        generation_config = {"temperature": temperature}
        
        # Add max_tokens if provided (Gemini uses 'max_output_tokens' instead of 'max_tokens')
        if max_tokens is not None:
            generation_config["max_output_tokens"] = max_tokens
        
        # Generate response
        response = chat.send_message(
            gemini_messages[-1]["parts"] if gemini_messages else "",
            generation_config=generation_config
        )
        
        # Format the response to match OpenAI's format for consistency
        if stream:
            # Gemini doesn't have a direct streaming equivalent to OpenAI's
            # This is a simplified version that doesn't actually stream
            return self._format_gemini_response(response, stream=True)
        else:
            return self._format_gemini_response(response)
    
    def process_image(self, image_data: Union[str, bytes, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process an image for inclusion in a Gemini message.
        
        Args:
            image_data: Either a URL string, raw image bytes, or a dictionary with image data
            
        Returns:
            Processed image data in the format expected by Gemini (always a dict with mime_type and data)
        """
        print(f"Gemini process_image received data of type: {type(image_data)}")
        
        try:
            # Handle dictionary input (likely from OpenAI format)
            if isinstance(image_data, dict):
                print(f"Processing dictionary image data with keys: {list(image_data.keys())}")
                # If it already has the format Gemini expects, return it directly
                if "mime_type" in image_data and "data" in image_data:
                    print("Image data already in Gemini format (mime_type + data)")
                    return image_data
                # If it has a URL field, extract and process the URL
                elif "url" in image_data:
                    url = image_data["url"]
                    print(f"Extracted URL from dictionary: {url[:30] if isinstance(url, str) else type(url)}...")
                    # Process the URL (could be a string URL or base64 data)
                    return self._process_url_or_base64(url)
                else:
                    print(f"Unsupported dictionary format: {list(image_data.keys())}")
            
            # If image_data is a string (URL or base64)
            elif isinstance(image_data, str):
                print(f"Processing string image data: {image_data[:30]}...")
                return self._process_url_or_base64(image_data)
            
            # If image_data is bytes, use it directly
            elif isinstance(image_data, bytes):
                print(f"Processing bytes image data of length: {len(image_data)}")
                return {"mime_type": "image/jpeg", "data": image_data}
            
            else:
                print(f"Unsupported image data type: {type(image_data)}")
                
        except Exception as e:
            print(f"Error processing image: {str(e)}")
        
        # If we get here, something went wrong - return a default empty image
        print("WARNING: Could not process image data, returning empty image")
        return {"mime_type": "image/jpeg", "data": b""}
    
    def _process_url_or_base64(self, data: str) -> Dict[str, Any]:
        """
        Helper method to process a string that could be a URL or base64 data.
        
        Args:
            data: String that could be a URL or base64 data
            
        Returns:
            Processed image data in Gemini format
        """
        # Handle HTTP/HTTPS URLs
        if data.startswith('http://') or data.startswith('https://'):
            try:
                import requests
                print(f"Downloading image from URL: {data[:30]}...")
                response = requests.get(data)
                response.raise_for_status()
                return {"mime_type": "image/jpeg", "data": response.content}
            except Exception as e:
                print(f"Error downloading image from URL: {str(e)}")
                raise
        
        # Handle base64 data URLs
        elif data.startswith('data:'):
            try:
                # Extract MIME type and base64 data
                mime_type = data.split(';')[0].split(':')[1]
                base64_str = data.split(',')[1]
                image_bytes = base64.b64decode(base64_str)
                return {"mime_type": mime_type, "data": image_bytes}
            except Exception as e:
                print(f"Error processing base64 data URL: {str(e)}")
                raise
        
        # Handle raw base64 strings (without data URI prefix)
        else:
            try:
                # Assume it's a base64 string without prefix
                image_bytes = base64.b64decode(data)
                return {"mime_type": "image/jpeg", "data": image_bytes}
            except Exception as e:
                print(f"Error decoding base64 string: {str(e)}")
                raise
    
    def _convert_to_gemini_format(self, openai_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert messages from OpenAI format to Gemini format.
        
        Args:
            openai_messages: Messages in OpenAI format
            
        Returns:
            Messages in Gemini format
        """
        print(f"Converting {len(openai_messages)} messages to Gemini format")
        gemini_messages = []
        
        for i, msg in enumerate(openai_messages):
            print(f"Processing message {i+1}/{len(openai_messages)} with role: {msg['role']}")
            role = msg["role"]
            
            # Map OpenAI roles to Gemini roles
            if role == "system":
                # Add as a user message with a prefix for system instructions
                gemini_messages.append({
                    "role": "user",
                    "parts": [f"System instruction: {msg['content']}"]
                })
            elif role == "user" or role == "assistant":
                # Convert content to Gemini's format
                parts = []
                
                # Handle string content
                if isinstance(msg["content"], str):
                    parts.append(msg["content"])
                # Handle array content (for multimodal)
                elif isinstance(msg["content"], list):
                    print(f"Processing list content with {len(msg['content'])} items")
                    for j, item in enumerate(msg["content"]):
                        print(f"  Item {j+1} type: {item.get('type', 'unknown')}")
                        if item.get("type") == "text":
                            parts.append(item["text"])
                        elif item.get("type") == "image_url":
                            # Process image URL using our helper method
                            try:
                                print(f"Processing image_url using process_image method")
                                processed_image = self.process_image(item["image_url"])
                                parts.append(processed_image)
                            except Exception as e:
                                print(f"Error processing image_url: {str(e)}")
                                # Skip this image
                                continue
                        elif item.get("type") == "image_data":
                            # Process image data using our helper method
                            try:
                                print(f"Processing image_data using process_image method")
                                processed_image = self.process_image(item["image_data"])
                                parts.append(processed_image)
                            except Exception as e:
                                print(f"Error processing image_data: {str(e)}")
                                # Skip this image
                                continue
                
                # Map the role and add the content
                gemini_role = "user" if role == "user" else "model"
                gemini_messages.append({
                    "role": gemini_role,
                    "parts": parts
                })
        
        return gemini_messages
    
    def _format_gemini_response(self, gemini_response: Any, stream: bool = False) -> Dict[str, Any]:
        """
        Format Gemini response to match OpenAI's format for consistency.
        
        Args:
            gemini_response: Response from Gemini API
            stream: Whether this is a streaming response
            
        Returns:
            Response formatted to match OpenAI's structure
        """
        # Extract the text content from the Gemini response
        response_text = ""
        try:
            response_text = gemini_response.text
        except AttributeError:
            # Try different ways to access the content based on response structure
            try:
                response_text = gemini_response.candidates[0].content.parts[0].text
            except (AttributeError, IndexError):
                try:
                    response_text = str(gemini_response)
                except:
                    response_text = "Unable to extract response text"
        
        if stream:
            # This is a simplified version that doesn't actually stream
            # In a real implementation, you'd need to handle the streaming differently
            return {
                "id": "gemini-" + os.urandom(8).hex(),
                "object": "chat.completion.chunk",
                "created": int(import_time()),
                "model": "gemini-1.5-pro",  # Hardcoded since we can't reliably get it from response
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "content": response_text
                        },
                        "finish_reason": "stop"
                    }
                ]
            }
        else:
            return {
                "id": "gemini-" + os.urandom(8).hex(),
                "object": "chat.completion",
                "created": int(import_time()),
                "model": "gemini-1.5-pro",  # Hardcoded since we can't reliably get it from response
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": response_text
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": -1,  # Not available from Gemini
                    "completion_tokens": -1,  # Not available from Gemini
                    "total_tokens": -1  # Not available from Gemini
                }
            }

def import_time():
    """Import time module and return current time as Unix timestamp."""
    import time
    return time.time()
