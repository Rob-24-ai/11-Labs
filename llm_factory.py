from typing import Optional
from llm_service import LLMService
from openai_service import OpenAIService
from gemini_service import GeminiService

def create_llm_service(provider: str = "openai", api_key: Optional[str] = None) -> LLMService:
    """
    Factory function to create an LLM service based on the specified provider.
    
    Args:
        provider: The LLM provider to use ('openai' or 'gemini')
        api_key: Optional API key for the provider
        
    Returns:
        An instance of the appropriate LLMService implementation
        
    Raises:
        ValueError: If the provider is not supported
    """
    if provider.lower() == "openai":
        return OpenAIService(api_key=api_key)
    elif provider.lower() == "gemini":
        return GeminiService(api_key=api_key)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}. Supported providers are: openai, gemini")
