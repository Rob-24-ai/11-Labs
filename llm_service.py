from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union, Any

class LLMService(ABC):
    """
    Abstract base class for LLM service providers.
    Implementations should handle different LLM APIs with a consistent interface.
    """
    
    @abstractmethod
    def chat_completion(self, 
                        messages: List[Dict[str, Any]], 
                        model: Optional[str] = None,
                        temperature: Optional[float] = None,
                        max_tokens: Optional[int] = None,
                        stream: bool = False) -> Union[Dict[str, Any], Any]:
        """
        Generate a chat completion response.
        
        Args:
            messages: List of message objects with role and content
            model: Optional model identifier
            temperature: Optional temperature parameter for response randomness
            max_tokens: Optional maximum number of tokens to generate
            stream: Whether to stream the response
            
        Returns:
            Either a completion response object or a stream
        """
        pass
    
    @abstractmethod
    def process_image(self, image_data: Union[str, bytes]) -> str:
        """
        Process an image and prepare it for inclusion in a message.
        
        Args:
            image_data: Either a URL string or raw image bytes
            
        Returns:
            Processed image data in the format expected by the LLM
        """
        pass
