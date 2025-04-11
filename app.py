import os
import json
import uuid
import base64 # Add base64 for potential image decoding
import requests # Add requests for making API calls to ElevenLabs
from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory # Add send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import openai # Add OpenAI library import
import logging # <-- ADD LOGGING IMPORT
from llm_factory import create_llm_service # Import the factory
from llm_service import LLMService # Import base class for type hinting

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- ADD LOGGING CONFIG ---
logging.basicConfig(level=logging.INFO) # Or DEBUG for more detail
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)
# --- END LOGGING CONFIG ---

# Configure CORS to allow requests from the frontend
cors = CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:5173", 
            "http://localhost:5174", 
            "http://127.0.0.1:5174",
            "https://231d-2600-6c65-727f-8221-79fc-7cd5-73f8-1f3c.ngrok-free.app"  # Add ngrok URL
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Simple in-memory session storage
sessions = {}

# Add a global variable to store the latest image context
latest_image_context = None

@app.route('/')
def home():
    """Simple route to check if the server is running."""
    return "Image Reader Module API is running!"

# New endpoint to receive and store image context
@app.route('/register_image_context', methods=['POST'])
def register_image_context():
    global latest_image_context
    if not request.is_json:
        app.logger.warning("'/register_image_context' received non-JSON request")
        return jsonify({"error": "Request must be JSON"}), 400
    data = request.get_json()
    description = data.get('description')
    if not description:
        app.logger.warning("'/register_image_context' missing 'description' field")
        return jsonify({"error": "'description' field is required"}), 400

    latest_image_context = description
    app.logger.info(f"Stored image context: {description[:100]}...") # Log truncated context
    return jsonify({"message": "Context registered successfully"}), 200

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
            # Process image data
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
    global latest_image_context # Access the global context
    # Log raw request body first
    raw_data = request.get_data(as_text=True)
    app.logger.debug(f"RAW Request Body for /v1/chat/completions: {raw_data[:500]}...") # Log truncated raw data

    try:
        # Attempt to parse JSON after logging raw data
        if not request.is_json:
             app.logger.warning("Request to /v1/chat/completions is not JSON")
             app.logger.warning(f"Request Content-Type: {request.content_type}")
             return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json()
        app.logger.info(f"Parsed Request Body Keys for /v1/chat/completions: {list(data.keys())}")

        messages = data.get('messages', [])
        stream = data.get('stream', False)
        model = data.get('model', os.getenv('DEFAULT_MODEL', 'gpt-4o')) # Use model from request or default

        # --- INJECT CONTEXT IF AVAILABLE --- 
        # Check if this request is likely from the SDK (e.g., has 'stream' key)
        # and if we have stored context.
        is_sdk_request = 'stream' in data # Heuristic: SDK usually streams
        # Also check that the request doesn't ALREADY contain an image
        has_image_in_request = any(
            isinstance(item, dict) and item.get('type') == 'image_url'
            for msg in messages
            for item in (msg.get('content') if isinstance(msg.get('content'), list) else [])
        )

        if is_sdk_request and not has_image_in_request and latest_image_context:
            app.logger.info("Injecting stored image context into messages for SDK request.")
            context_message = {
                "role": "system",
                "content": f"CONTEXT: The user previously uploaded an image. Its description is: {latest_image_context}"
            }
            # Find the first non-system message index to insert before it
            insert_index = 0
            for i, msg in enumerate(messages):
                if msg.get('role') != 'system':
                    insert_index = i
                    break
            else: # If only system messages exist, append after them
                 insert_index = len(messages)
            
            messages.insert(insert_index, context_message)
            # Option to clear context after use:
            # latest_image_context = None 
            app.logger.info(f"Messages after injection: {messages}") # Log messages after injection
        elif not is_sdk_request:
             app.logger.info("Request seems to be direct analysis (no 'stream' key), not injecting context.")
        elif has_image_in_request:
            app.logger.info("Request already contains image data, not injecting stored context.")
        elif not latest_image_context:
            app.logger.info("No stored image context to inject.")
        # --- END CONTEXT INJECTION ---

        # Check again if the request contains image data (might have been injected)
        has_image_data = any(
            isinstance(item, dict) and item.get('type') == 'image_url'
            for msg in messages
            for item in (msg.get('content') if isinstance(msg.get('content'), list) else [])
        )
        
        # Log request details (Moved the function definition lower) 
        # log_request_info(request, data, messages, stream, has_image_data)

        # Get LLM configuration
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
                temperature=data.get('temperature'),
                max_tokens=data.get('max_tokens'),
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
        traceback.print_exc()
        
        return jsonify({
            "error": {
                "message": f"Internal server error: {str(e)}",
                "type": "server_error",
                "code": 500
            }
        }), 500

# Add a route for '/chat/completions' to handle ElevenLabs requests without the v1 prefix
@app.route('/chat/completions', methods=['POST'])
def chat_completions_no_v1():
    """Alias for the /v1/chat/completions endpoint to handle ElevenLabs requests."""
    print("Received request for /chat/completions - forwarding to /v1/chat/completions handler")
    return chat_completions()

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
    return send_from_directory('static', filename)

# Endpoint for Text-to-Speech using ElevenLabs
@app.route('/v1/voice/speak', methods=['POST'])
def speak_text():
    """Accepts text and returns URL to ElevenLabs generated audio."""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
        
    data = request.get_json()
    text = data.get('text')
    
    if not text:
        return jsonify({"error": "'text' field is required"}), 400
        
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        return jsonify({"error": "ELEVENLABS_API_KEY not configured."}), 500
        
    result = generate_elevenlabs_audio(text, api_key)
    
    if result and result.get("status") == "success":
        # Construct the full URL for the client
        # Using request.host_url as a base assumes the server is accessible
        # If behind ngrok, this might need adjustment or rely on frontend knowing the base
        audio_url = request.host_url.strip('/') + result["audio_url"]
        return jsonify({"audio_url": audio_url})
    else:
        error_message = result.get("message", "Failed to generate audio")
        error_details = result.get("details", "")
        return jsonify({"error": error_message, "details": error_details}), 500

# Endpoint for Speech-to-Text using OpenAI Whisper
@app.route('/v1/voice/transcribe', methods=['POST'])
def transcribe_audio():
    """Accepts audio file and returns transcription from OpenAI Whisper."""
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided in the 'audio' field."}), 400
        
    audio_file = request.files['audio']
    
    # Basic check for filename or content type if needed, but Whisper handles various formats
    # filename = audio_file.filename
    # print(f"Received audio file: {filename}, type: {audio_file.mimetype}")
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        return jsonify({"error": "OPENAI_API_KEY not configured."}), 500
        
    try:
        client = openai.OpenAI(api_key=api_key)
        
        # Note: Whisper API needs the file object directly, 
        # along with a hint about the filename for format detection.
        # We need to pass the file stream and a name.
        # Using a generic name like 'audio.webm' as the frontend sends a webm blob.
        transcription_response = client.audio.transcriptions.create(
            model="whisper-1", 
            file=(audio_file.filename or "audio.webm", audio_file.stream, audio_file.mimetype),
            response_format="json"
        )
        
        transcribed_text = transcription_response.text
        
        print(f"Whisper transcription successful: {transcribed_text[:50]}...")
        return jsonify({"transcription": transcribed_text})
        
    except openai.APIError as e:
        print(f"OpenAI API Error during transcription: {e}")
        return jsonify({"error": f"OpenAI API Error: {e.status_code} - {e.message}"}), 500
    except Exception as e:
        print(f"Error during transcription: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Transcription failed: {str(e)}"}), 500

if __name__ == '__main__':
    # Read port from environment variable or default to 5001
    # Using a port other than 5000 to avoid potential conflicts with other Flask apps
    port = int(os.environ.get('PORT', 5001))
    # Run the app in debug mode for development (auto-reloads on code changes)
    # Set debug=False for production
    app.run(host='0.0.0.0', port=port, debug=True)
