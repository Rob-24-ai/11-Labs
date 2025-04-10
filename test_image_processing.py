import os
import sys
import argparse
import base64
from dotenv import load_dotenv
from llm_factory import create_llm_service

def main():
    """
    Test script for the LLM service image processing capabilities.
    Tests multimodal functionality with different providers.
    """
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Test LLM service image processing")
    parser.add_argument("--provider", type=str, default="openai", 
                        choices=["openai", "gemini"],
                        help="LLM provider to test (openai or gemini)")
    parser.add_argument("--model", type=str, 
                        help="Model to use (defaults to provider's default)")
    parser.add_argument("--image", type=str, required=True,
                        help="Path to an image file or URL to analyze")
    parser.add_argument("--prompt", type=str, default="What's in this image?",
                        help="Prompt to send to the LLM about the image")
    args = parser.parse_args()
    
    # Create the LLM service based on the specified provider
    try:
        llm_service = create_llm_service(provider=args.provider)
        print(f"Created {args.provider} service successfully")
    except Exception as e:
        print(f"Error creating LLM service: {str(e)}")
        sys.exit(1)
    
    # Process the image
    try:
        # Check if the image is a URL or a file path
        if args.image.startswith(('http://', 'https://')):
            # It's a URL
            image_data = args.image
            print(f"Using image URL: {image_data}")
        else:
            # It's a file path
            try:
                with open(args.image, 'rb') as f:
                    image_data = f.read()
                print(f"Loaded image from file: {args.image}")
            except Exception as e:
                print(f"Error reading image file: {str(e)}")
                sys.exit(1)
        
        # Process the image for the specific provider
        processed_image = llm_service.process_image(image_data)
        print("Image processed successfully")
        
        # Prepare the messages
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that analyzes images."
            }
        ]
        
        # Add the message with the image
        if args.provider == "openai":
            # OpenAI format for multimodal messages
            if isinstance(processed_image, str) and processed_image.startswith(('http://', 'https://')):
                # URL - OpenAI expects an object with a url field
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": args.prompt},
                        {"type": "image_url", "image_url": {"url": processed_image}}
                    ]
                })
            else:
                # Base64
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": args.prompt},
                        {"type": "image_url", "image_url": {"url": processed_image}}
                    ]
                })
        elif args.provider == "gemini":
            # For Gemini, we need to download the image if it's a URL
            if args.image.startswith(('http://', 'https://')):
                # Download the image first
                try:
                    import requests
                    response = requests.get(args.image)
                    response.raise_for_status()
                    image_bytes = response.content
                    
                    # Use the raw bytes for Gemini
                    messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": args.prompt},
                            {"type": "image_data", "image_data": {"mime_type": "image/jpeg", "data": image_bytes}}
                        ]
                    })
                except Exception as e:
                    print(f"Error downloading image for Gemini: {str(e)}")
                    sys.exit(1)
            elif isinstance(processed_image, dict) and "data" in processed_image:
                # It's already in Gemini format
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": args.prompt},
                        {"type": "image_data", "image_data": processed_image}
                    ]
                })
            else:
                # Handle file or base64 string
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": args.prompt},
                        {"type": "image_url", "image_url": processed_image}
                    ]
                })
        
        # Send the request to the LLM
        model = args.model if args.model else None
        response = llm_service.chat_completion(messages=messages, model=model)
        
        # Print the response
        print("\nLLM Response:")
        print("-------------")
        
        if args.provider == "openai":
            print(response.choices[0].message.content)
        elif args.provider == "gemini":
            # Our Gemini service formats responses to match OpenAI's structure
            print(response["choices"][0]["message"]["content"])
        
    except Exception as e:
        print(f"Error processing image or getting LLM response: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
