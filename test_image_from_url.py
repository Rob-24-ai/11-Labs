import os
import sys
import requests
from dotenv import load_dotenv
from llm_factory import create_llm_service

def main():
    """
    Test script for the LLM service image processing capabilities with a specific URL.
    """
    load_dotenv()
    
    # Read the URL from the file
    with open('temp_url.txt', 'r') as f:
        image_url = f.read().strip()
    
    # Define the prompt
    prompt = "Describe this artwork in detail, including style, medium, and possible artist or period."
    
    # Test with OpenAI
    print("Testing with OpenAI...")
    test_with_provider("openai", image_url, prompt)
    
    # Test with Gemini
    print("\n\nTesting with Gemini...")
    test_with_provider("gemini", image_url, prompt)

def test_with_provider(provider, image_url, prompt):
    """Test the image processing with a specific provider."""
    try:
        # Create the LLM service
        llm_service = create_llm_service(provider=provider)
        print(f"Created {provider} service successfully")
        
        # Process the image
        print(f"Using image URL: {image_url}")
        
        # Download the image first (for better reliability)
        response = requests.get(image_url)
        response.raise_for_status()
        image_data = response.content
        print("Downloaded image successfully")
        
        # Process the image with the LLM service
        processed_image = llm_service.process_image(image_data)
        print("Image processed successfully")
        
        # Prepare the messages
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that analyzes images of artwork."
            }
        ]
        
        # Add the message with the image
        if provider == "openai":
            # For OpenAI, we need to encode the image as base64
            import base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            })
        elif provider == "gemini":
            # For Gemini, we use the raw bytes
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_data", "image_data": {"mime_type": "image/jpeg", "data": image_data}}
                ]
            })
        
        # Send the request to the LLM
        response = llm_service.chat_completion(messages=messages)
        
        # Print the response
        print("\nLLM Response:")
        print("-------------")
        
        if provider == "openai":
            print(response.choices[0].message.content)
        elif provider == "gemini":
            # Our Gemini service formats responses to match OpenAI's structure
            print(response["choices"][0]["message"]["content"])
        
    except Exception as e:
        print(f"Error with {provider}: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
