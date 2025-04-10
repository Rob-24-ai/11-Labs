# Multimodal Image Analysis Service - Build Plan

## Project Goal & Context

The primary goal of this project is to create a backend API service (this "Image Reader Module") using Python and Flask. This service will:

1.  Accept image data via API calls (supporting both direct file uploads and image URLs).
2.  Process the received image data.
3.  Utilize a configurable Vision Large Language Model (VLLM), such as OpenAI's GPT-4o or Anthropic's Claude Sonnet, to perform analysis or answer questions about the image based on a provided prompt.
4.  Return the textual analysis results via the API.

This module is intended to function as a **Custom LLM provider for ElevenLabs Conversational AI**. Instead of using the webhook approach (where ElevenLabs' built-in LLM calls our API as a separate tool), we'll implement a Custom LLM server that handles both the conversation and image analysis in a unified system. This creates a more seamless architecture where a single AI system handles both the conversation flow and image understanding capabilities.

**Implementation Approach:** The final implementation will include a custom UI that handles both image uploads (file uploads and camera captures) and integrates with ElevenLabs Conversational AI agent for real-time live voice-to-voice interaction. We'll implement the **Custom LLM approach** rather than the webhook approach, allowing a single LLM to handle both conversation and image analysis. This provides full control over the user experience and creates a more cohesive system. Note that this specifically uses the Conversational AI agent capability with our custom LLM backend, not separate text-to-speech or speech-to-text services.

The plan below details the steps to build this standalone Image Reader Module API.

---

## Stage 1: Backend Development

**Goal:** Build the core Flask API service capable of image analysis and serving as a Custom LLM for ElevenLabs.

*   **Phase 1.1: Core API Foundation**
    *   [X] Project Setup (Directory, venv)
    *   [X] Basic Flask App (`app.py`)
    *   [X] Initial `/analyze` endpoint (POST) - *Evolved into `/v1/chat/completions`*
    *   [X] CORS Middleware
    *   [X] Basic Config & Logging

*   **Phase 1.2: Image Handling & Basic Analysis**
    *   [X] Modify API for Image Uploads (`request.files`) - *Handled within chat endpoint*
    *   [X] Modify API for Image URLs - *Handled within chat endpoint*
    *   [X] Basic Security: File Size & MIME Type Validation (`python-magic`)
    *   [X] Image Processing: Open/Validate Image (`Pillow`), Base64 Encoding
    *   [X] Initial LLM Integration (OpenAI GPT-4o)
    *   [X] Secure API Key Management (`.env`, `python-dotenv`)
    *   [X] Update API to return LLM analysis
    *   [X] Dependency Management (`requirements.txt`) - *Implicitly managed*

*   **Phase 1.3: LLM Abstraction & Flexibility**
    *   [X] Define `LLMService` Abstract Base Class/Interface - *Implemented in `llm_service.py`*
    *   [X] Implement `OpenAIService` (concrete class) - *Implemented in `openai_service.py`*
    *   [X] Implement *at least one* other provider - *Implemented `GeminiService` in `gemini_service.py` and `AnthropicService` in `anthropic_service.py`*
    *   [X] Create LLM Service Factory Function - *Implemented in `llm_factory.py`*
    *   [X] Update API to use the abstraction layer (accept `llm_provider` param) - *Model is configurable via environment variables*

*   **Phase 1.4: Security & Prompting Refinements**
    *   [ ] Filename Sanitization (UUID) - *Less critical with direct processing*
    *   [ ] URL Validation (Basic SSRF checks) - *Basic checks in place*
    *   [X] Prompt Management (Accept custom `prompt`, provide default) - *Handled via messages*

*   **Phase 1.5: Custom LLM Endpoint for ElevenLabs**
    *   [X] Implement `/v1/chat/completions` endpoint (OpenAI format)
    *   [X] Handle `messages` array (including image URLs/data)
    *   [X] Implement Session State Management (In-memory currently)
    *   [X] Integrate Image Analysis logic within the chat completion flow

---

## Stage 2: Integration & Deployment

**Goal:** Connect the backend to ElevenLabs, containerize, and deploy it.

*   **Phase 2.1: ElevenLabs Integration & Testing**
    *   [X] **Step 1: Implement Custom LLM Endpoint (`/v1/chat/completions`)** - *Completed in `app.py`*
        *   [X] Ensure endpoint adheres strictly to OpenAI chat completion format (request & response).
        *   [ ] Handle streaming responses if `stream: true` is received.
        *   [X] Implement basic session management (in-memory initially).
        *   [X] Integrate image extraction logic (base64/URL) from messages.
    *   [X] **Step 2: Testing the Custom LLM Endpoint**
        *   [X] Use `curl` to send test requests (including text and image data).
        *   [X] Verify correct response format and content.
        *   [X] Test session handling.
        *   [X] **Note:** Used `ngrok` to expose local server at `https://231d-2600-6c65-727f-8221-79fc-7cd5-73f8-1f3c.ngrok-free.app`.
        *   [X] Added detailed request logging for troubleshooting ElevenLabs integration.

*   **Phase 2.2: ElevenLabs Platform Configuration**
    *   [X] Create/Configure an ElevenLabs Conversational AI Agent.
    *   [X] In the ElevenLabs dashboard (Secrets page), configure the agent to use our Custom LLM.
        *   [X] Provided the public URL: `https://231d-2600-6c65-727f-8221-79fc-7cd5-73f8-1f3c.ngrok-free.app/v1/chat/completions`
        *   [X] Specified the model name: `gpt-4o`
        *   [X] Confirmed "Custom LLM extra body" setting is enabled to allow passing image data.
        *   [ ] **Security Note:** Consider setting up an allowlist for production to restrict which domains can connect to the agent.
    *   [ ] Obtain necessary credentials/IDs from ElevenLabs for frontend integration (e.g., Agent ID).

*   **Phase 2.3: Containerization & Configuration**
    *   [ ] Create `Dockerfile`
    *   [ ] Build and test Docker image locally
    *   [ ] Ensure all configuration is via environment variables
    *   [ ] Document required environment variables (`.env.example`, README)

*   **Phase 2.4: Cloud Deployment**
    *   [ ] Select cloud deployment target (PaaS, Container Service, IaaS)
    *   [ ] Configure deployment environment (secrets, scaling)
    *   [ ] Deploy the containerized application
    *   [ ] Test the deployed service endpoint

---

## Stage 3: Frontend Development

**Goal:** Create a web interface using React or Next.js to interact with the ElevenLabs agent (powered by our backend).

*   **Phase 3.1: Basic UI Setup**
    *   [ ] Initialize Frontend project (React with Vite or Next.js)
    *   [ ] Basic component structure for chat/interaction

*   **Phase 3.2: ElevenLabs SDK Integration**
    *   [ ] Install relevant SDK (`@11labs/react` or adjust for Next.js)
    *   [ ] Implement `useConversation` hook or equivalent client-side logic
    *   [ ] Connect UI to the configured ElevenLabs Agent ID
    *   [ ] Handle voice input/output streaming
    *   [ ] Reference:
        *   [ElevenLabs React SDK Docs](https://elevenlabs.io/docs/conversational-ai/libraries/react)
        *   [ElevenLabs Next.js Quickstart](https://elevenlabs.io/docs/conversational-ai/guides/quickstarts/next-js)

*   **Phase 3.3: Image Input Integration**
    *   [ ] Add UI elements for image file upload
    *   [ ] (Optional) Add UI elements for camera capture
    *   [ ] Modify frontend logic to send image data (likely as base64 or a URL) as part of the conversation context to ElevenLabs/backend.

---

## Stage 4: Testing & Refinement

**Goal:** Ensure end-to-end functionality and apply optional improvements.from flask import Flask
import os

# --- Start Minimal App Code ---
app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Minimal App Works!'

@app.route('/test')
def test_route():
    return 'Test Route Works!'

if __name__ == '__main__':
    # Ensure PORT is correctly loaded or hardcoded for test
    # Default to 64677 if PORT env var is not set
    port = int(os.environ.get("PORT", 64677))
    # Run with debug=False initially to rule out reloader issues
    print(f"--- Starting Minimal App on 0.0.0.0:{port} ---")
    app.run(host='0.0.0.0', port=port, debug=False)
# --- End Minimal App Code ---

# You can optionally paste your original code below, commented out,
# or simply delete the original content before pasting this.

*   **Phase 4.1: End-to-End Testing**
    *   [X] Test Backend API Standalone (Phases 1.1-1.5) - *Initial tests done*
    *   [ ] Test ElevenLabs <-> Backend Integration (Phase 2.1)
    *   [ ] Test Frontend <-> ElevenLabs Integration (Phase 3.2)
    *   [ ] Test Full Flow: Frontend Image Upload -> ElevenLabs -> Backend Analysis -> Frontend Response (Voice/Text)

*   **Phase 4.2: Optional Refinements**
    *   [ ] Advanced Prompting Techniques (Backend/Frontend)
    *   [ ] Image Resizing (Backend)
    *   [ ] Asynchronous Task Handling (Backend - Celery, etc.)
    *   [ ] Response Caching (Backend)
    *   [ ] Scalability Configuration (Deployment)
    *   [ ] Monitoring & Logging Integration (Deployment)
