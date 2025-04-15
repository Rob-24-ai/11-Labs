import os
import json
import uuid
import base64 # Add base64 for potential image decoding
import requests # Add requests for making API calls to ElevenLabs
from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory, render_template # Add send_from_directory and render_template
from flask_cors import CORS
from dotenv import load_dotenv
from llm_factory import create_llm_service # Import the factory
from llm_service import LLMService # Import base class for type hinting
import time # Add time import for response formatting

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- Configure CORS --- #
# Allow requests specifically from the Vite dev server origin
# In production, you might want to restrict this to your deployed frontend URL
# Using a more flexible pattern for local development as Vite port changes
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:*", "https://localhost:*"]}}) 
# --- End CORS Configuration ---

# --- Image Context Storage --- 
# Simple in-memory dictionary to store the mapping between a conversation identifier
# (e.g., user_id from ElevenLabs) and the filename of the image uploaded for that session.
# This is a basic implementation; a more robust solution (Redis, DB) might be needed for production.
image_context = {}
# Define required configuration keys
app.config['UPLOAD_FOLDER'] = os.path.abspath('./uploads')

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
# --- End Image Context Storage ---

# Simple in-memory session storage (kept for potential other uses)
sessions = {}

# Define the root route to serve the test form
@app.route('/')
def index():
    """Serve the main voice interaction interface."""
    return render_template('voice_interface.html')

@app.route('/analyze', methods=['POST'])
def analyze_image():
    """
    Endpoint for image analysis that sends results to ElevenLabs for vocalization.
    Accepts image data as file upload or URL and returns analysis.
    """
    try:
        # Check if we have image data
        image_data = None
        image_url = None
        
        # Check for file upload
        if 'image' in request.files:
            image_file = request.files['image']
            image_data = image_file.read()
        # Check for URL in JSON body
        elif request.is_json and 'image_url' in request.json:
            image_url = request.json['image_url']
        else:
            return jsonify({
                "error": "No image provided. Please upload an image file or provide an image_url."
            }), 400
            
        # Get prompt from request or use default
        prompt = "Describe this image in detail."
        if request.is_json and 'prompt' in request.json:
            prompt = request.json['prompt']
            
        # Get LLM configuration from environment variables
        llm_provider = os.getenv('LLM_PROVIDER', 'openai').lower()
        api_key = os.getenv(f"{llm_provider.upper()}_API_KEY")

        if not api_key:
            return jsonify({
                "error": f"API key for '{llm_provider}' not configured."
            }), 500

        # Create LLM service
        llm_service = create_llm_service(provider=llm_provider, api_key=api_key)
        
        # Prepare message with image
        messages = [
            {"role": "system", "content": "You are an expert at analyzing and describing images in detail."},
            {"role": "user", "content": [
                {"type": "text", "text": prompt}
            ]}
        ]
        
        # Add image to the user message content
        if image_url:
            # Add image URL to message
            messages[1]["content"].append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })
        elif image_data:
            # Process image dataa
            base64_image = base64.b64encode(image_data).decode('utf-8')
            data_url = f"data:image/jpeg;base64,{base64_image}"
            messages[1]["content"].append({
                "type": "image_url",
                "image_url": {"url": data_url}
            })
            
        # Call LLM for analysis
        response = llm_service.chat_completion(
            messages=messages,
            model=os.getenv('DEFAULT_MODEL', 'gpt-4o')
        )
        
        # Extract the analysis text
        analysis_text = response.choices[0].message.content
        
        # Check if we should send to ElevenLabs
        send_to_elevenlabs = request.args.get('voice', 'false').lower() == 'true'
        elevenlabs_response = None
        
        if send_to_elevenlabs:
            # Send to ElevenLabs for vocalization
            elevenlabs_response = send_to_elevenlabs_tts(analysis_text)
            
        # Return the analysis and optional ElevenLabs response
        result = {
            "status": "success",
            "analysis": analysis_text
        }
        
        if elevenlabs_response:
            result["elevenlabs"] = elevenlabs_response
            
        return jsonify(result), 200
            
    except Exception as e:
        print(f"Error in analyze_image: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "error": f"Error analyzing image: {str(e)}"
        }), 500

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    """
    OpenAI-compatible chat completions endpoint for ElevenLabs integration.
    Accepts messages in OpenAI format and returns a compatible response.
    Handles image data in messages for multimodal analysis.
    """
    # Log request headers and body for debugging
    print("\n=== INCOMING REQUEST ===\n")
    print(f"Headers: {dict(request.headers)}")
    print(f"Request Method: {request.method}")
    print(f"Content-Type: {request.content_type}")
    # Don't log the full body as it might contain sensitive data
    print(f"Request Body Keys: {request.json.keys() if request.is_json else 'Not JSON'}")
    if request.is_json and 'messages' in request.json:
        print(f"Message Count: {len(request.json.get('messages', []))}")
        print(f"Stream Mode: {request.json.get('stream', False)}")
    print("\n=== END REQUEST INFO ===\n")
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

        # --- Image URL Injection Logic --- 
        # Check if an image is associated with this conversation and inject its URL
        
        # Attempt to get a conversation identifier from the request
        # IMPORTANT: Requires 'user_id' to be sent by ElevenLabs (enable 'Custom LLM extra body')
        conversation_identifier = data.get('user_id')
        
        # Log the conversation identifier for debugging
        app.logger.info(f"Processing request with conversation_identifier: {conversation_identifier}")
        
        if conversation_identifier:
            # Check if there's an image associated with this conversation
            image_filename = image_context.get(conversation_identifier)
            
            if image_filename:
                # Use the request's host URL instead of relying on environment variable
                base_url = request.host_url.rstrip('/')
                
                # Construct the full public URL for the image
                public_image_url = f"{base_url}/serve_image/{image_filename}"
                app.logger.info(f"Injecting image URL: {public_image_url} for conversation: {conversation_identifier}")

                # Create the OpenAI-compatible message structure for the image
                image_message = {
                    "role": "user", # Image is typically associated with the user's turn
                    "content": [
                        {
                            "type": "text",
                            "text": "(System note: The user has shared an image. Please analyze this image in the context of our conversation.)" 
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": public_image_url,
                                "detail": "auto" # Using auto to let the LLM determine appropriate detail level
                            }
                        }
                    ]
                }
                
                # Insert the image message into the list at position 1 (after system prompt)
                # This ensures the image is analyzed in the context of the system prompt
                if messages and len(messages) > 0: 
                    # If the first message is a system message, insert after it
                    if messages[0].get('role') == 'system':
                        messages.insert(1, image_message)
                        app.logger.info("Inserted image after system message")
                    else:
                        # Otherwise insert at the beginning
                        messages.insert(0, image_message)
                        app.logger.info("Inserted image at beginning of messages")
                else:
                    # Handle edge case: If message list is empty
                    messages.append(image_message)
                    app.logger.info("Added image to empty messages list")
                
                # Remove the image from context AFTER successful injection
                # This prevents the same image from being injected multiple times
                image_context.pop(conversation_identifier, None)
                app.logger.info(f"Removed image {image_filename} from context for conversation {conversation_identifier}")
            else:
                app.logger.debug(f"No image found for conversation {conversation_identifier}")
        # --- End Image URL Injection Logic --- 

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
            # Pass the potentially modified messages list to the LLM service
            llm_response = llm_service.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream # Pass stream parameter
            )
            
            # Handle streaming response if stream=True
            if stream:
                # Define a generator function to yield chunks
                def generate_chunks():
                    try:
                        for chunk in llm_response:
                            # Process the chunk (convert to string, format as SSE, etc.)
                            # Assuming the chunk object has a structure we can serialize
                            # Check common OpenAI streaming chunk structures
                            content_delta = ""
                            if chunk.choices and chunk.choices[0].delta:
                                content_delta = chunk.choices[0].delta.content or ""
                            
                            if content_delta: # Only yield if there's content
                                # Format as Server-Sent Event (SSE)
                                # Example: data: {"id": "...", "choices": [...]} 

                                # Simple approach: just yield the content delta
                                # yield f"data: {json.dumps({'delta': content_delta})}\n\n"
                                
                                # More complete approach: yield OpenAI-like chunk structure
                                chunk_dict = chunk.model_dump() # Convert Pydantic model to dict
                                yield f"data: {json.dumps(chunk_dict)}\n\n"
                                
                    except Exception as e:
                        print(f"Error during streaming: {str(e)}")
                        # Optionally yield an error event
                        yield f"data: {json.dumps({'error': str(e)})}\n\n"
                
                # Return a streaming response with additional headers for CORS
                response = Response(stream_with_context(generate_chunks()), mimetype='text/event-stream')
                # Add headers that might help with cross-origin streaming
                response.headers['Cache-Control'] = 'no-cache'
                response.headers['X-Accel-Buffering'] = 'no'  # Helps with nginx proxy buffering
                return response
            else:
                # Non-streaming: Convert the ChatCompletion object to a dictionary before jsonify
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
        traceback.print_exc() # Log full traceback for unexpected errors
        return jsonify({
            "error": {
                "message": f"Internal server error: {str(e)}",
                "type": "server_error",
                "code": 500
            }
        }), 500

# --- Supporting Endpoints for Image Handling (To Be Implemented per INTEGRATION_PLAN.md) ---

@app.route('/upload_image_get_url', methods=['POST'])
def upload_image_get_url():
    """Receive an image file and a conversation_id, save the image, and return a public URL.
    Following INTEGRATION_PLAN.md, this endpoint:
    1. Receives the image file and conversation_id
    2. Validates the file
    3. Saves it with a unique filename
    4. Stores the mapping in image_context
    5. Returns the public URL
    """
    try:
        # Validate request contains necessary data
        if 'image' not in request.files:
            return jsonify({"error": "No image file provided"}), 400
        
        # Get the image file
        image_file = request.files['image']
        if image_file.filename == '':
            return jsonify({"error": "Empty filename"}), 400
            
        # Get conversation_id from form or JSON
        conversation_id = None
        if request.form and 'conversation_id' in request.form:
            conversation_id = request.form['conversation_id']
        elif request.is_json and 'conversation_id' in request.json:
            conversation_id = request.json['conversation_id']
            
        if not conversation_id:
            return jsonify({"error": "No conversation_id provided"}), 400
        
        # Generate a unique filename (to prevent overwrites/collisions)
        file_extension = os.path.splitext(image_file.filename)[1].lower()
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        # Save the image file
        image_file.save(file_path)
        
        # Store mapping in image_context
        image_context[conversation_id] = unique_filename
        app.logger.info(f"Saved image for conversation {conversation_id}: {unique_filename}")
        
        # Construct public URL for the image 
        # Use request.host_url to get the base URL dynamically
        base_url = request.host_url.rstrip('/')
        public_image_url = f"{base_url}/serve_image/{unique_filename}"
        
        return jsonify({
            "status": "success",
            "message": "Image uploaded successfully",
            "public_image_url": public_image_url,
            "conversation_id": conversation_id
        })
    except Exception as e:
        app.logger.error(f"Error in upload_image_get_url: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/serve_image/<filename>')
def serve_image(filename):
    """Securely serve an image file from the UPLOAD_FOLDER.
    This uses Flask's send_from_directory which handles security concerns
    like path traversal attacks.
    """
    try:
        app.logger.debug(f"Serving image: {filename}")
        # Sanitize filename (extra security on top of send_from_directory)
        safe_filename = os.path.basename(filename)
        
        # Use Flask's secure file serving function
        return send_from_directory(app.config['UPLOAD_FOLDER'], safe_filename)
    except FileNotFoundError:
        app.logger.warning(f"Image not found: {filename}")
        return jsonify({"error": "Image not found"}), 404
    except Exception as e:
        app.logger.error(f"Error serving image {filename}: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

# --- End Supporting Endpoints ---


# Add a route for '/chat/completions' to handle ElevenLabs requests without the v1 prefix
@app.route('/chat/completions', methods=['POST'])
def chat_completions_no_v1():
    """Alias for the /v1/chat/completions endpoint to handle ElevenLabs requests."""
    print("Received request for /chat/completions - forwarding to /v1/chat/completions handler")
    return chat_completions()

# --- ElevenLabs Integration Endpoints ---

@app.route('/api/elevenlabs/get-signed-url', methods=['GET'])
def get_elevenlabs_signed_url():
    """Generate a temporary signed URL for the ElevenLabs Conversational WebSocket.

    This endpoint securely uses the backend API key to request a signed URL
    from ElevenLabs, which the frontend can then use to connect without
    exposing the secret key.
    """
    load_dotenv() # Ensure environment variables are loaded
    api_key = os.getenv('ELEVENLABS_API_KEY')
    print(f"[ElevenLabs URL Gen] Retrieved API Key: {'********' + api_key[-4:] if api_key else 'Not Found'}")
    agent_id = os.getenv('ELEVENLABS_AGENT_ID')
    print(f"[ElevenLabs URL Gen] Retrieved Agent ID: {agent_id}")

    if not api_key or not agent_id:
        print("[ElevenLabs URL Gen] Error: API Key or Agent ID missing in environment.")
        return jsonify({"error": "Server configuration error: Missing ElevenLabs credentials."}), 500

    elevenlabs_url = f"https://api.elevenlabs.io/v1/convai/conversation/get_signed_url?agent_id={agent_id}"
    headers = {
        "xi-api-key": api_key
    }

    try:
        response = requests.get(elevenlabs_url, headers=headers)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

        data = response.json()
        signed_url = data.get('signed_url')

        if not signed_url:
            print(f"[ElevenLabs URL Gen] Error: 'signed_url' key not found in response: {data}")
            return jsonify({"error": "Failed to retrieve signed URL from ElevenLabs."}), 502 # Bad Gateway

        # Return both the signed URL and the agent ID used to generate it
        return jsonify({"signedUrl": signed_url, "agentId": agent_id})

    except requests.exceptions.RequestException as e:
        print(f"[ElevenLabs URL Gen] Error contacting ElevenLabs API: {e}")
        # Check if response exists to provide more detail
        error_detail = str(e)
        if e.response is not None:
            try:
                error_detail = e.response.json() or e.response.text
            except json.JSONDecodeError:
                error_detail = e.response.text
        return jsonify({"error": "Failed to communicate with ElevenLabs API.", "details": error_detail}), 502 # Bad Gateway
    except Exception as e:
        print(f"[ElevenLabs URL Gen] Unexpected error generating signed URL: {e}")
        import traceback
        traceback.print_exc() # Log full traceback for unexpected errors
        return jsonify({"error": "An unexpected server error occurred."}), 500


@app.route('/elevenlabs/tts', methods=['POST'])
def send_to_elevenlabs_tts(text):
    """
    Send text to ElevenLabs for text-to-speech conversion or to a specific agent.
    
    Args:
        text: The text to convert to speech or send to an agent
        
    Returns:
        Dictionary with response information or None if failed
    """
    try:
        # Get ElevenLabs API key from environment variables
        api_key = os.getenv('ELEVENLABS_API_KEY')
        if not api_key:
            print("Error: ELEVENLABS_API_KEY not found in environment variables")
            return None
            
        # Check if we have an agent ID
        agent_id = os.getenv('ELEVENLABS_AGENT_ID', 'r7QeXEUadxgIchsAQYax')  # Use the provided agent ID
        
        if agent_id:
            # Send to ElevenLabs agent
            return send_to_elevenlabs_agent(text, agent_id, api_key)
        else:
            # Fall back to regular TTS if no agent ID
            return generate_elevenlabs_audio(text, api_key)
            
    except Exception as e:
        print(f"Error sending to ElevenLabs: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Error: {str(e)}"
        }

def send_to_elevenlabs_agent(text, agent_id, api_key):
    """
    Send a message to a specific ElevenLabs agent.
    
    Args:
        text: The text to send to the agent
        agent_id: The ID of the ElevenLabs agent
        api_key: ElevenLabs API key
        
    Returns:
        Dictionary with response information
    """
    try:
        # ElevenLabs API endpoint for agent messages
        url = f"https://api.elevenlabs.io/v1/agents/{agent_id}/chat"
        
        # Headers with API key
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        
        # Create a new conversation or use existing one
        conversation_id = os.getenv('ELEVENLABS_CONVERSATION_ID')
        
        # Request body
        data = {
            "text": text,
            "conversation_id": conversation_id
        }
        
        # Make the request
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 200 or response.status_code == 201:
            response_data = response.json()
            
            # Store conversation ID for future use if it's new
            if not conversation_id and 'conversation_id' in response_data:
                os.environ['ELEVENLABS_CONVERSATION_ID'] = response_data['conversation_id']
                
            return {
                "status": "success",
                "agent_response": response_data,
                "message": "Message sent to ElevenLabs agent successfully"
            }
        else:
            print(f"Error from ElevenLabs Agent API: {response.status_code} - {response.text}")
            return {
                "status": "error",
                "message": f"ElevenLabs Agent API error: {response.status_code}",
                "details": response.text
            }
    except Exception as e:
        print(f"Error sending to ElevenLabs agent: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Error: {str(e)}"
        }

def generate_elevenlabs_audio(text, api_key):
    """
    Generate audio from text using ElevenLabs TTS API.
    
    Args:
        text: The text to convert to speech
        api_key: ElevenLabs API key
        
    Returns:
        Dictionary with response information
    """
    try:
        # Get voice ID from environment variables or use default
        voice_id = os.getenv('ELEVENLABS_VOICE_ID', 'pNInz6obpgDQGcFmaJgB')  # Default to Adam voice
        
        if voice_id:
            # Send to ElevenLabs agent
            return generate_elevenlabs_audio_with_voice(text, voice_id, api_key)
        else:
            # Fall back to regular TTS if no voice ID
            return {
                "status": "error",
                "message": "No voice ID provided"
            }
            
    except Exception as e:
        print(f"Error generating ElevenLabs audio: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Error: {str(e)}"
        }

def generate_elevenlabs_audio_with_voice(text, voice_id, api_key):
    """
    Generate audio from text using ElevenLabs TTS API.
    
    Args:
        text: The text to convert to speech
        voice_id: The ID of the ElevenLabs voice
        api_key: ElevenLabs API key
        
    Returns:
        Dictionary with response information
    """
    try:
        # ElevenLabs API endpoint for text-to-speech
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        
        # Headers with API key
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        
        # Request body
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
        
        # Make the request
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 200:
            # Save the audio file
            filename = f"speech_{uuid.uuid4()}.mp3"
            filepath = os.path.join(os.path.dirname(__file__), 'static', filename)
            
            # Create static directory if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Write the audio file
            with open(filepath, 'wb') as f:
                f.write(response.content)
                
            # Return the URL to the audio file
            return {
                "status": "success",
                "audio_url": f"/static/{filename}"
            }
        else:
            print(f"Error from ElevenLabs TTS API: {response.status_code} - {response.text}")
            return {
                "status": "error",
                "message": f"ElevenLabs TTS API error: {response.status_code}",
                "details": response.text
            }
    except Exception as e:
        print(f"Error generating ElevenLabs audio: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Error: {str(e)}"
        }

# Add a route to serve static files
@app.route('/static/<path:filename>')
def serve_static(filename):
    static_folder = os.path.join(os.path.dirname(__file__), 'static')
    os.makedirs(static_folder, exist_ok=True) # Ensure static exists
    return send_from_directory(static_folder, filename)

if __name__ == '__main__':
    # Ensure environment variables are loaded once at startup
    load_dotenv()
    # Run the app
    # Use host='0.0.0.0' to make it accessible on the network if needed
    app.run(debug=True, port=5003) # Change port here
