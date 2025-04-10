import os
import json
import uuid
import base64 # Add base64 for potential image decoding
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from llm_factory import create_llm_service # Import the factory
from llm_service import LLMService # Import base class for type hinting

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Simple in-memory session storage
sessions = {}

@app.route('/')
def home():
    """Simple route to check if the server is running."""
    return "Image Reader Module API is running!"

@app.route('/analyze', methods=['POST'])
def analyze_image():
    """
    Placeholder endpoint for image analysis.
    Currently accepts POST requests but does no processing.
    """
    # TODO: Implement image input handling (file upload, URL) - Phase 1
    # TODO: Implement security checks (size, type) - Phase 1
    # TODO: Implement image processing (Pillow) - Phase 1
    # TODO: Implement LLM call (requests) - Phase 1
    # TODO: Implement LLM adapter pattern - Phase 2

    print("Received request for /analyze") # Basic logging

    # Placeholder response
    return jsonify({
        "status": "received",
        "message": "Analysis endpoint called. Implementation pending."
    }), 200

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    """
    OpenAI-compatible chat completions endpoint for ElevenLabs integration.
    Accepts messages in OpenAI format and returns a compatible response.
    Handles image data in messages for multimodal analysis.
    """
    try:
        # Validate request has JSON content
        if not request.is_json:
            return jsonify({
                "error": {
                    "message": "Request must be JSON",
                    "type": "invalid_request_error",
                    "code": 400
                }
            }), 400
            
        data = request.json
        
        # Validate required fields
        if not data:
            return jsonify({
                "error": {
                    "message": "Request body cannot be empty",
                    "type": "invalid_request_error",
                    "code": 400
                }
            }), 400
        
        # Extract key parameters
        model = data.get('model', os.getenv('DEFAULT_MODEL', 'gpt-4o')) # Use env var for default
        messages = data.get('messages', [])
        temperature = data.get('temperature') # Pass optional params
        max_tokens = data.get('max_tokens')
        stream = data.get('stream', False) # Check if streaming is requested
        
        # Validate messages format
        if not isinstance(messages, list) or not messages:
            return jsonify({
                "error": {
                    "message": "'messages' must be an array",
                    "type": "invalid_request_error",
                    "code": 400
                }
            }), 400
        
        # --- LLM Service Integration --- 
        # Get LLM configuration from environment variables
        llm_provider = os.getenv('LLM_PROVIDER', 'openai').lower()
        api_key = os.getenv(f"{llm_provider.upper()}_API_KEY")

        if not api_key:
            print(f"Error: API key for provider '{llm_provider}' not found in environment variables.")
            return jsonify({
                "error": {
                    "message": f"API key for '{llm_provider}' not configured.",
                    "type": "server_error",
                    "code": 500
                }
            }), 500

        try:
            llm_service: LLMService = create_llm_service(provider=llm_provider, api_key=api_key)
        except ValueError as e:
            print(f"Error creating LLM service: {str(e)}")
            return jsonify({
                "error": {
                    "message": f"Failed to initialize LLM provider: {str(e)}",
                    "type": "server_error",
                    "code": 500
                }
            }), 500
        # --- End LLM Service Integration ---

        # Log the request for debugging (moved down slightly)
        print(f"Received request for /v1/chat/completions using {llm_provider} model {model}")
        print(f"Request headers: {dict(request.headers)}")
        safe_data = data.copy() if data else {}
        if 'api_key' in safe_data:
            safe_data['api_key'] = '[REDACTED]'
        print(f"Request data keys: {list(safe_data.keys())}")
        # Optionally log message content if needed for debugging (beware of large base64 strings)
        # print(f"Messages: {json.dumps(messages, indent=2)}")

        # --- Call LLM Service --- 
        try:
            # Pass messages directly - the LLM service implementation should handle image data within
            llm_response = llm_service.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream # Pass stream parameter
            )
            
            # TODO: Handle streaming response if stream=True
            if stream:
                # For now, return error if streaming requested but not implemented
                print("Error: Streaming response requested but not yet implemented.")
                return jsonify({
                    "error": {
                        "message": "Streaming response is not yet supported.",
                        "type": "server_error",
                        "code": 501 # Not Implemented
                    }
                }), 501

            # Assuming non-streaming returns a dict compatible with OpenAI response
            # Convert the ChatCompletion object to a dictionary before jsonify
            return jsonify(llm_response.model_dump())
        
        except Exception as e:
            # Catch errors during the LLM API call
            print(f"Error during LLM API call: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({
                "error": {
                    "message": f"Error communicating with LLM: {str(e)}",
                    "type": "llm_error",
                    "code": 500
                }
            }), 500
        # --- End Call LLM Service ---

    except json.JSONDecodeError:
        print("Error: Invalid JSON in request body")
        return jsonify({
            "error": {
                "message": "Invalid JSON in request body",
                "type": "invalid_request_error",
                "code": 400
            }
        }), 400
    except KeyError as e:
        print(f"Error: Missing required field: {str(e)}")
        return jsonify({
            "error": {
                "message": f"Missing required field: {str(e)}",
                "type": "invalid_request_error",
                "code": 400
            }
        }), 400
    except ValueError as e:
        print(f"Error: Invalid value: {str(e)}")
        return jsonify({
            "error": {
                "message": f"Invalid value: {str(e)}",
                "type": "invalid_request_error",
                "code": 400
            }
        }), 400
    except Exception as e:
        print(f"Error in chat_completions: {str(e)}")
        # Log the full exception traceback for debugging
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "error": {
                "message": f"Internal server error: {str(e)}",
                "type": "server_error",
                "code": 500
            }
        }), 500

if __name__ == '__main__':
    # Read port from environment variable or default to 5001
    # Using a port other than 5000 to avoid potential conflicts with other Flask apps
    port = int(os.environ.get('PORT', 5001))
    # Run the app in debug mode for development (auto-reloads on code changes)
    # Set debug=False for production
    app.run(host='0.0.0.0', port=port, debug=True)
