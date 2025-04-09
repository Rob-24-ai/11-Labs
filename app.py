import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

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

if __name__ == '__main__':
    # Read port from environment variable or default to 5001
    # Using a port other than 5000 to avoid potential conflicts with other Flask apps
    port = int(os.environ.get('PORT', 5001))
    # Run the app in debug mode for development (auto-reloads on code changes)
    # Set debug=False for production
    app.run(host='0.0.0.0', port=port, debug=True)
