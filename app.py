import os
import json
import uuid
import base64 
import requests 
from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory, render_template 
from flask_cors import CORS
from dotenv import load_dotenv
from llm_factory import create_llm_service 
from llm_service import LLMService 
import time 
import logging

# Load environment variables from .env file
load_dotenv()

# Debug environment variables
print(f"\n=== ENVIRONMENT VARIABLES DEBUG ===")
print(f"ELEVENLABS_API_KEY: {'*' * 20 + os.getenv('ELEVENLABS_API_KEY')[-4:] if os.getenv('ELEVENLABS_API_KEY') else 'Not set'}")
print(f"ELEVENLABS_AGENT_ID: {os.getenv('ELEVENLABS_AGENT_ID') or 'Not set'}")
print(f"LLM_PROVIDER: {os.getenv('LLM_PROVIDER') or 'Not set'}")
print(f"DEFAULT_MODEL: {os.getenv('DEFAULT_MODEL') or 'Not set'}")
print(f"=== END ENVIRONMENT VARIABLES DEBUG ===\n")

app = Flask(__name__)

# --- Configure CORS --- #
# Allow requests from the Vite dev server origin to all routes
# In production, you might want to restrict this to your deployed frontend URL
# Using a more flexible pattern for local development as Vite port changes
CORS(app, origins=["*"], methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type", "Authorization", "X-Api-Key", "*"], expose_headers=["*"])
# --- End CORS Configuration ---

# --- Image Context Storage --- 
# Simple in-memory dictionary to store the mapping between a conversation identifier
# (e.g., user_id from ElevenLabs) and the filename of the image uploaded for that session.
# This is a basic implementation; a more robust solution (Redis, DB) might be needed for production.
image_context = {} 
session_map = {}
pending_session_id = None

# Define required configuration keys
app.config['UPLOAD_FOLDER'] = os.path.abspath('./uploads')

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
# --- End Image Context Storage ---

# Simple in-memory session storage (kept for potential other uses)
sessions = {}

# Configure logging
logging.basicConfig(level=logging.INFO) 
app.logger.setLevel(logging.INFO) 

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

@app.route('/v1/chat/completions', methods=['POST', 'OPTIONS'])
def chat_completions():
    """
    OpenAI-compatible chat completions endpoint for ElevenLabs integration.
    Handles image injection based on session mapping.
    """
    # --- BEGIN ADDED LOGGING ---
    app.logger.info(f"====================\n NEW REQUEST at /v1/chat/completions ====================")
    app.logger.info(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    app.logger.info(f"Remote Address: {request.remote_addr}")
    app.logger.info(f"Method: {request.method}")
    app.logger.info(f"URLs: REQUEST_URI={request.environ.get('REQUEST_URI', 'Not in environ')}, PATH_INFO={request.environ.get('PATH_INFO', 'Not in environ')}")
    app.logger.info(f"Headers:\n{'-'*50}")
    for name, value in request.headers.items():
        app.logger.info(f"{name}: {value}")
    app.logger.info(f"{'-'*50}")
    
    try:
        # Log raw body for debugging non-JSON requests or unexpected formats
        raw_body = request.get_data()
        app.logger.info(f"Raw Body (hex): {raw_body[:100].hex()}")
        try:
            text_body = request.get_data(as_text=True)
            app.logger.info(f"Raw Body (text): {text_body[:500]}...")
        except UnicodeDecodeError:
            app.logger.info("Raw body is not valid UTF-8 text")
            
        # Attempt to log JSON if possible
        if request.is_json:
            try:
                app.logger.info(f"JSON Payload: {request.json}")
            except Exception as json_err:
                app.logger.error(f"Error parsing JSON: {json_err}")
        else:
            app.logger.info("Request body is not JSON.")
    except Exception as e:
        app.logger.error(f"Error inspecting request body: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
    app.logger.info(f"==================== End Request Details ====================")
    # --- END ADDED LOGGING ---

    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        # You might need to customize these headers based on what ElevenLabs requires
        headers = {
            'Access-Control-Allow-Origin': '*', # Or specific origin
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Api-Key', # Add any other headers ElevenLabs might send
            'Access-Control-Max-Age': '3600' # Cache preflight response for 1 hour
        }
        return ('', 204, headers)

    # Existing logic continues below...
    app.logger.info("Processing POST request for /v1/chat/completions...")

    # Retrieve the API key from headers or environment variables
    api_key = request.headers.get('Authorization')
    
    global pending_session_id, session_map, image_context 
    # Log request headers and body for debugging
    app.logger.info("\n=== INCOMING /v1/chat/completions REQUEST ===\n")
    app.logger.info(f"Headers: {dict(request.headers)}")
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
        model = data.get('model', os.getenv('DEFAULT_MODEL', 'gpt-4o')) 
        messages = data.get('messages', [])
        temperature = data.get('temperature') 
        max_tokens = data.get('max_tokens')
        stream = data.get('stream', False) 
        
        # Validate messages format
        if not isinstance(messages, list) or not messages:
            return jsonify({
                "error": {
                    "message": "'messages' must be an array",
                    "type": "invalid_request_error",
                    "code": 400
                }
            }), 400
        
        # --- EXTENSIVE DEBUGGING for ElevenLabs Request ---
        app.logger.info(f"=== FULL REQUEST DATA IN /v1/chat/completions ===\n{json.dumps(data, indent=2)}")
        
        # --- Attempt to get ElevenLabs User ID --- 
        # IMPORTANT: Requires 'user_id' to be sent by ElevenLabs (enable 'Custom LLM extra body')
        elevenlabs_user_id = data.get('user_id')
        
        # Try alternative user ID fields (could be named differently)
        possible_user_id_fields = ['user_id', 'userId', 'user', 'id', 'conversation_id', 'conversationId']
        for field in possible_user_id_fields:
            if field in data and data[field]:
                elevenlabs_user_id = data[field]
                app.logger.info(f"Found user ID in field '{field}': {elevenlabs_user_id}")
                break
                
        app.logger.info(f"Received elevenlabs_user_id: {elevenlabs_user_id}")
        
        # --- Dump Current System State for Debugging ---
        app.logger.info(f"Current pending_session_id: {pending_session_id}")
        app.logger.info(f"Current session_map: {session_map}")
        app.logger.info(f"Current image_context: {image_context}")
        
        # --- Session Linking Logic --- 
        session_id = None
        if elevenlabs_user_id:
            if elevenlabs_user_id not in session_map:
                # If this elevenlabs_user_id is new, link it to the pending session_id
                if pending_session_id:
                    app.logger.info(f"⭐ Linking new elevenlabs_user_id '{elevenlabs_user_id}' to pending session_id '{pending_session_id}'")
                    session_map[elevenlabs_user_id] = pending_session_id
                    session_id = pending_session_id
                    pending_session_id = None 
                else:
                    app.logger.warning(f"⚠️ Received new elevenlabs_user_id '{elevenlabs_user_id}' but no pending_session_id was found.")
                    # FALLBACK: Check if there's only one session in image_context, use that
                    if len(image_context) == 1:
                        only_session_id = list(image_context.keys())[0]
                        app.logger.info(f"📌 FALLBACK: Only one session found in image_context, using: {only_session_id}")
                        session_map[elevenlabs_user_id] = only_session_id
                        session_id = only_session_id
            else:
                # Existing elevenlabs_user_id, retrieve the mapped session_id
                session_id = session_map.get(elevenlabs_user_id)
                app.logger.info(f"🔄 Found existing mapping: elevenlabs_user_id '{elevenlabs_user_id}' maps to session_id '{session_id}'")
        else:
            app.logger.warning("⛔ No elevenlabs_user_id received in the request.")
            # FALLBACK: If no user_id but we have a pending session and there's only one image, use it
            if pending_session_id and len(image_context) == 1:
                app.logger.info(f"📌 FALLBACK: No user_id, but we have pending_session_id: {pending_session_id}")
                session_id = pending_session_id
        # --- End Session Linking --- 

        # --- LLM Service Integration --- 
        # Get LLM configuration from environment variables
        llm_provider = os.getenv('LLM_PROVIDER', 'openai').lower()
        api_key = os.getenv(f"{llm_provider.upper()}_API_KEY")

        if not api_key:
            app.logger.error(f"Error: API key for provider '{llm_provider}' not found in environment variables.")
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
            app.logger.error(f"Error creating LLM service: {str(e)}")
            return jsonify({
                "error": {
                    "message": f"Failed to initialize LLM provider: {str(e)}",
                    "type": "server_error",
                    "code": 500
                }
            }), 500
        # --- End LLM Service Integration ---

        # --- Image URL Injection Logic --- 
        # Check if an image is associated with this session_id and inject its URL
        
        # Log the conversation identifier for debugging
        app.logger.info(f"📝 Processing request linked to session_id: {session_id}")
        
        # FALLBACK: If still no session_id but we have images, use the most recent one
        if not session_id and image_context:
            newest_session_id = list(image_context.keys())[-1]  # Last key added
            app.logger.info(f"🔍 FALLBACK: No session_id match, using newest one: {newest_session_id}")
            session_id = newest_session_id
            
            # Also create a mapping if we have a user_id
            if elevenlabs_user_id:
                session_map[elevenlabs_user_id] = session_id
                app.logger.info(f"🔄 Created FALLBACK mapping for elevenlabs_user_id: {elevenlabs_user_id}")
        
        if session_id: 
            # Check if there's an image associated with this session
            image_filename = image_context.get(session_id)
            app.logger.info(f"🖼️ Looking for image with session_id: {session_id}, found: {image_filename}")
            
            if image_filename:
                # Use the request's host URL instead of relying on environment variable
                base_url = request.host_url.rstrip('/')
                
                # Construct the full public URL for the image
                public_image_url = f"{base_url}/serve_image/{image_filename}"
                app.logger.info(f"Injecting image URL: {public_image_url} for session: {session_id}")

                # Create the OpenAI-compatible message structure for the image
                image_message = {
                    "role": "user", 
                    "content": [
                        {
                            "type": "text",
                            "text": "(System note: The user has shared an image. Please analyze this image in the context of our conversation.)" 
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": public_image_url,
                                "detail": "auto" 
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
                # Use session_id for lookup
                image_context.pop(session_id, None)
                app.logger.info(f"Removed image {image_filename} from context for session {session_id}")
            else:
                app.logger.info(f"No image found for session {session_id}")
        else:
            # Handle case where session linking failed or no elevenlabs_user_id was provided
            app.logger.warning("Could not determine session_id for image lookup.")
            
        # --- End Image URL Injection Logic ---

        # Log the request for debugging (moved down slightly)
        print(f"Received request for /v1/chat/completions using {llm_provider} model {model}")
        print(f"Request headers: {dict(request.headers)}")
        safe_data = data.copy() if data else {}
        if 'api_key' in safe_data:
            safe_data['api_key'] = '[REDACTED]'
        print(f"Request data keys: {list(safe_data.keys())}")
        
        # --- Call LLM Service --- 
        try:
            # Pass the potentially modified messages list to the LLM service
            llm_response = llm_service.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream 
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
                            
                            if content_delta: 
                                # Format as Server-Sent Event (SSE)
                                # Example: data: {"id": "...", "choices": [...]} 

                                # Simple approach: just yield the content delta
                                # yield f"data: {json.dumps({'delta': content_delta})}\n\n"
                                
                                # More complete approach: yield OpenAI-like chunk structure
                                chunk_dict = chunk.model_dump() 
                                yield f"data: {json.dumps(chunk_dict)}\n\n"
                                
                    except Exception as e:
                        print(f"Error during streaming: {str(e)}")
                        # Optionally yield an error event
                        yield f"data: {json.dumps({'error': str(e)})}\n\n"
                
                # Return a streaming response with additional headers for CORS
                response = Response(stream_with_context(generate_chunks()), mimetype='text/event-stream')
                # Add headers that might help with cross-origin streaming
                response.headers['Cache-Control'] = 'no-cache'
                response.headers['X-Accel-Buffering'] = 'no'  
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
        traceback.print_exc() 
        return jsonify({
            "error": {
                "message": f"Internal server error: {str(e)}",
                "type": "server_error",
                "code": 500
            }
        }), 500

@app.route('/upload_image_get_url', methods=['POST'])
def upload_image_get_url():
    """Receive an image file and a session_id, save the image, and return a public URL.
    This endpoint:
    1. Receives the image file and session_id
    2. Validates the file
    3. Saves it with a unique filename
    4. Stores the mapping in image_context using session_id
    5. Returns the public URL
    """
    global image_context 
    try:
        # Validate request contains necessary data
        if 'image' not in request.files:
            app.logger.error("Upload error: No image file provided")
            return jsonify({"error": "No image file provided"}), 400
        
        # Get the image file
        image_file = request.files['image']
        if image_file.filename == '':
            app.logger.error("Upload error: Empty filename")
            return jsonify({"error": "Empty filename"}), 400
            
        # Get session_id from form data (ensure frontend sends 'session_id')
        session_id = request.form.get('session_id')
            
        if not session_id:
            app.logger.error("Upload error: No session_id provided")
            return jsonify({"error": "No session_id provided"}), 400
        
        # Generate a unique filename (to prevent overwrites/collisions)
        file_extension = os.path.splitext(image_file.filename)[1].lower()
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        # Save the image file
        image_file.save(file_path)
        
        # Store mapping in image_context using session_id
        image_context[session_id] = unique_filename
        app.logger.info(f"Saved image for session {session_id}: {unique_filename}")
        
        # Construct public URL for the image 
        # Use request.host_url to get the base URL dynamically
        base_url = request.host_url.rstrip('/')
        public_image_url = f"{base_url}/serve_image/{unique_filename}"
        
        return jsonify({
            "status": "success",
            "message": "Image uploaded successfully",
            "public_image_url": public_image_url,
            "session_id": session_id 
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

@app.route('/api/elevenlabs/get-signed-url', methods=['GET'])
def get_elevenlabs_signed_url():
    """Generate a temporary signed URL and a unique session ID.

    1. Calls ElevenLabs API to get a signed URL.
    2. Generates a unique session ID (UUID).
    3. Stores the session ID temporarily as pending.
    4. Returns both the signed URL and the session ID to the frontend.
    """
    global pending_session_id 
    load_dotenv() 
    api_key = os.getenv('ELEVENLABS_API_KEY')
    app.logger.info(f"[ElevenLabs URL Gen] Retrieved API Key: {'********' + api_key[-4:] if api_key else 'Not Found'}")
    # Force using the correct agent ID from .env - this overrides any cached value
    agent_id = "al0xrBMlL3qchebAFV9N"  # Directly use the correct agent ID
    app.logger.info(f"[ElevenLabs URL Gen] Using Agent ID: {agent_id}")

    if not api_key or not agent_id:
        app.logger.error("[ElevenLabs URL Gen] Error: API Key or Agent ID missing.")
        return jsonify({"error": "Server configuration error: Missing ElevenLabs credentials."}), 500

    elevenlabs_api_endpoint = f"https://api.elevenlabs.io/v1/convai/conversation/get_signed_url?agent_id={agent_id}"
    headers = {
        "xi-api-key": api_key
    }

    try:
        # Use GET method as per the ElevenLabs documentation
        response = requests.get(elevenlabs_api_endpoint, headers=headers)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        
        signed_url_data = response.json()
        # Log the full response to see its structure
        app.logger.info(f"[ElevenLabs URL Gen] Response received: {signed_url_data}")
        
        # Check for common field names in the response
        signed_url = None
        for field in ['url', 'signed_url', 'signedUrl']:
            if field in signed_url_data:
                signed_url = signed_url_data.get(field)
                app.logger.info(f"[ElevenLabs URL Gen] Found URL in field: {field}")
                break

        if not signed_url:
            app.logger.error("[ElevenLabs URL Gen] Error: 'url' not found in ElevenLabs response.")
            return jsonify({"error": "Failed to get signed URL from ElevenLabs."}), 500
            
        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        pending_session_id = session_id 
        app.logger.info(f"[ElevenLabs URL Gen] Generated Session ID: {session_id}")

        return jsonify({
            "signedUrl": signed_url, 
            "sessionId": session_id, 
            "agentId": agent_id 
        })

    except requests.exceptions.RequestException as e:
        app.logger.error(f"[ElevenLabs URL Gen] HTTP Request failed: {str(e)}")
        return jsonify({"error": f"Failed to communicate with ElevenLabs API: {str(e)}"}), 502
    except Exception as e:
        app.logger.error(f"[ElevenLabs URL Gen] Unexpected error: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

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
            app.logger.error("Error: ELEVENLABS_API_KEY not found in environment variables")
            return None
            
        # Check if we have an agent ID
        agent_id = os.getenv('ELEVENLABS_AGENT_ID', 'r7QeXEUadxgIchsAQYax')  
        
        if agent_id:
            # Send to ElevenLabs agent
            return send_to_elevenlabs_agent(text, agent_id, api_key)
        else:
            # Fall back to regular TTS if no agent ID
            return generate_elevenlabs_audio(text, api_key)
            
    except Exception as e:
        app.logger.error(f"Error sending to ElevenLabs: {str(e)}")
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
            app.logger.error(f"Error from ElevenLabs Agent API: {response.status_code} - {response.text}")
            return {
                "status": "error",
                "message": f"ElevenLabs Agent API error: {response.status_code}",
                "details": response.text
            }
    except Exception as e:
        app.logger.error(f"Error sending to ElevenLabs agent: {str(e)}")
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
        voice_id = os.getenv('ELEVENLABS_VOICE_ID', 'pNInz6obpgDQGcFmaJgB')  
        
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
        app.logger.error(f"Error generating ElevenLabs audio: {str(e)}")
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
            app.logger.error(f"Error from ElevenLabs TTS API: {response.status_code} - {response.text}")
            return {
                "status": "error",
                "message": f"ElevenLabs TTS API error: {response.status_code}",
                "details": response.text
            }
    except Exception as e:
        app.logger.error(f"Error generating ElevenLabs audio: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Error: {str(e)}"
        }

@app.route('/static/<path:filename>')
def serve_static(filename):
    static_folder = os.path.join(os.path.dirname(__file__), 'static')
    os.makedirs(static_folder, exist_ok=True) 
    return send_from_directory(static_folder, filename)

@app.route('/v1/test', methods=['GET', 'POST', 'OPTIONS'])
def test_endpoint():
    """Simple endpoint to test if connections from ElevenLabs are working."""
    app.logger.info(f"===== TEST ENDPOINT HIT =====")
    app.logger.info(f"Method: {request.method}")
    app.logger.info(f"Headers: {dict(request.headers)}")
    app.logger.info(f"Remote: {request.remote_addr}")
    
    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Api-Key, *',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)
        
    # Return a simple JSON response
    return jsonify({
        "status": "success", 
        "message": "Connection to custom LLM endpoint successful!",
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/v1/test/chat/completions', methods=['POST', 'OPTIONS'])
def test_chat_completions():
    """Handle the chat/completions requests that ElevenLabs appends to our test endpoint."""
    app.logger.info(f"===== TEST CHAT COMPLETIONS ENDPOINT HIT =====")
    app.logger.info(f"Method: {request.method}")
    app.logger.info(f"Headers: {dict(request.headers)}")
    
    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Api-Key, *',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)
    
    # Log the request body
    try:
        if request.is_json:
            app.logger.info(f"Request JSON: {request.json}")
    except Exception as e:
        app.logger.error(f"Error parsing request JSON: {e}")
    
    # Return a simple OpenAI-compatible response
    return jsonify({
        "id": f"test-{uuid.uuid4()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello! This is a test response from your custom LLM endpoint. The connection is working correctly!"
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    })

if __name__ == '__main__':
    # Ensure environment variables are loaded once at startup
    load_dotenv()
    # Run the app
    # Use host='0.0.0.0' to make it accessible on the network if needed
    app.run(debug=True, port=5003) 
