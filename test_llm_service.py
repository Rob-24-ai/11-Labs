import os
import sys
import argparse
from dotenv import load_dotenv
from llm_factory import create_llm_service

def main():
    """
    Test script for the LLM service abstraction layer.
    Tests basic chat completion functionality with different providers.
    """
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Test LLM service abstraction layer")
    parser.add_argument("--provider", type=str, default="openai", 
                        choices=["openai", "gemini"],
                        help="LLM provider to test (openai or gemini)")
    parser.add_argument("--model", type=str, 
                        help="Model to use (defaults to provider's default)")
    parser.add_argument("--prompt", type=str, default="Tell me a short joke about programming.",
                        help="Prompt to send to the LLM")
    parser.add_argument("--image", type=str, 
                        help="Optional path to an image file or URL to include")
    args = parser.parse_args()
    
    # Create the LLM service based on the specified provider
    try:
        llm_service = create_llm_service(provider=args.provider)
        print(f"Created {args.provider} service successfully")
    except Exception as e:
        print(f"Error creating LLM service: {str(e)}")
        sys.exit(1)
    
    # Prepare the messages
    messages = []
    
    # Add a system message
    messages.append({
        "role": "system",
        "content": "You are a helpful assistant that provides concise responses."
    })
    
    # Add a user message with the prompt
    if args.image:
        # Check if the image is a URL or a file path
        if args.image.startswith(('http://', 'https://')):
            # It's a URL
            image_data = args.image
        else:
            # It's a file path
            try:
                with open(args.image, 'rb') as f:
                    image_data = f.read()
            except Exception as e:
                print(f"Error reading image file: {str(e)}")
                sys.exit(1)
        
        # Process the image for the specific provider
        processed_image = llm_service.process_image(image_data)
        
        # Add the message with the image
        if args.provider == "openai":
            # OpenAI format for multimodal messages
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": args.prompt},
                    {"type": "image_url", "image_url": {"url": processed_image}}
                ]
            })
        elif args.provider == "gemini":
            # For Gemini, we'll handle this in the service implementation
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": args.prompt},
                    {"type": "image_url", "image_url": processed_image}
                ]
            })
    else:
        # Text-only message
        messages.append({
            "role": "user",
            "content": args.prompt
        })
    
    # Send the request to the LLM
    try:
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
        
        print("\nFull Response Object:")
        print("---------------------")
        print(response)
        
    except Exception as e:
        print(f"Error getting LLM response: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
