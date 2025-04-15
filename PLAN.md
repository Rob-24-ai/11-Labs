# Multimodal Image Analysis Service - Build Plan

## Project Goal & Context

The primary goal of this project is to create a backend API service (this "Image Reader Module") using Python and Flask. This service will:

1.  Accept image data via API calls (supporting both direct file uploads and image URLs).
2.  Process the received image data.
3.  Utilize a configurable Vision Large Language Model (VLLM), such as OpenAI's GPT-4o or Anthropic's Claude Sonnet, to perform analysis or answer questions about the image based on a provided prompt.
4.  Return the textual analysis results via the API.

This module is intended to function as a **Custom LLM provider for ElevenLabs Conversational AI**. Instead of using the webhook approach (where ElevenLabs' built-in LLM calls our API as a separate tool), we'll implement a Custom LLM server that handles both the conversation and image analysis in a unified system. This creates a more seamless architecture where a single AI system handles both the conversation flow and image understanding capabilities. **Crucially, this means our Flask backend acts *only* as the LLM provider endpoint called by ElevenLabs. The real-time voice input (Speech-to-Text) and voice output (Text-to-Speech) are handled directly between the frontend (using the ElevenLabs SDK) and the ElevenLabs Conversational AI service. Our backend does *not* process raw audio streams.**

**Implementation Approach:** The final implementation will include a custom UI that handles both image uploads (file uploads and camera captures) and integrates with ElevenLabs Conversational AI agent for real-time live voice-to-voice interaction. We'll implement the **Custom LLM approach** rather than the webhook approach, allowing a single LLM to handle both conversation and image analysis. This provides full control over the user experience and creates a more cohesive system. Note that this specifically uses the Conversational AI agent capability **with our custom LLM backend**, not separate text-to-speech or speech-to-text services *implemented by us*.

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
    *   [X] **Step 2: Test Endpoint Locally**
        *   [X] Sent test requests (mimicking ElevenLabs) using `curl` or a tool like Postman. Verified image data handling.
    *   [X] **Step 3: Expose Endpoint Publicly (Temporary)**
        *   [X] **Note:** Used `ngrok` to expose local server at `https://231d-2600-6c65-727f-8221-79fc-7cd5-73f8-1f3c.ngrok-free.app`.
        *   [X] Added detailed request logging for troubleshooting ElevenLabs integration.

*   **Phase 2.2: ElevenLabs Platform Configuration**
    *   [X] Create/Configure an ElevenLabs Conversational AI Agent.
    *   [X] In the ElevenLabs dashboard (Secrets page), configure the agent to use our Custom LLM.
        *   [X] Provided the public URL: `https://231d-2600-6c65-727f-8221-79fc-7cd5-73f8-1f3c.ngrok-free.app/v1/chat/completions`
        *   [X] Specified the model name: `gpt-4o`
        *   [X] Confirmed "Custom LLM extra body" setting is enabled to allow passing image data.
        *   [ ] **Security Note:** Consider setting up an allowlist for production to restrict which domains can connect to the agent.
    *   [X] Obtain necessary credentials/IDs from ElevenLabs for frontend integration (e.g., Agent ID). - *Agent ID `r7QeXEUadxgIchsAQYax` confirmed.*

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
**Status:** Ready to Begin

**Architectural Note:** This stage focuses on building the user interface and integrating the **ElevenLabs SDK (e.g., `@11labs/react`)**. This SDK manages the direct interaction with the ElevenLabs service for capturing user speech and playing back synthesized audio responses in real-time.

*   **Phase 3.1: Basic UI Setup**
    *   [ ] Choose Frontend Framework (React/Next.js)
    *   [ ] Basic component structure for chat/interaction *(See: Mobile Build Guide.md - Sec II, III)*
    *   [ ] Implement basic responsive layout *(See: Mobile Build Guide.md - Sec I, II)*
    *   [ ] Ensure touch-friendly navigation and controls *(See: Mobile Build Guide.md - Sec II.A, II.B)*

*   **Phase 3.2: ElevenLabs SDK Integration**
    *   [X] Install relevant SDK (`@11labs/react` for Vite/React)
    *   [X] Test SDK functionality with minimalist implementation (`test_eleven_voice.html` and `minimal_voice_test.html`)
    *   [X] Identify and resolve issues with React's lifecycle management and WebSocket connections
        * Resolved StrictMode interaction (initially removed, now stable with it re-enabled)
        * Implemented proper connection cleanup / fixed useEffect dependency loop
        * Separated connection management logic within App component
    *   [ ] Implement `useConversation` hook with lifecycle-aware cleanup
    *   [ ] Connect UI to the configured ElevenLabs Agent ID
    *   [ ] Handle voice input/output streaming with proper error handling *(See: Mobile Build Guide.md - Sec II.D, IV.A, IV.D)*
    *   [ ] Implement UI feedback for connection status and voice state (connecting, connected, listening, processing) *(See: Mobile Build Guide.md - Sec II.D)*
    *   [ ] Display real-time text captions *(See: Mobile Build Guide.md - Sec II.F, IV.C)*
    *   [ ] References:
        * [ElevenLabs React SDK Docs](https://elevenlabs.io/docs/conversational-ai/libraries/react)
        * [ElevenLabs Next.js Quickstart](https://elevenlabs.io/docs/conversational-ai/guides/quickstarts/next-js)
        * Test implementations: `test_eleven_voice.html` and `minimal_voice_test.html`

*   **Phase 3.3: Image Input Integration**
    *   [ ] Add UI elements for image file upload *(See: Mobile Build Guide.md - Sec II.B)*
    *   [ ] (Optional) Add UI elements for camera capture *(See: Mobile Build Guide.md - Sec II.E, IV.B)*
    *   [ ] Modify frontend logic to send image data (likely as base64 or a URL) as part of the conversation context to ElevenLabs/backend.
    *   [ ] Handle camera permissions and stream display *(See: Mobile Build Guide.md - Sec II.E, IV.B)*

---

## Stage 4: Testing & Refinement

**Goal:** Ensure end-to-end functionality and apply optional improvements.

*   **Phase 4.1: End-to-End Testing**
    *   [X] Test Backend API Standalone (Phases 1.1-1.5) - *Initial tests done*
    *   [X] Test ElevenLabs <-> Backend Integration (Phase 2.1/2.2) - *Confirmed via ElevenLabs playground*
    *   [ ] Test Frontend <-> ElevenLabs Integration (Phase 3.2)
    *   [ ] Test Full Flow: Frontend Image Upload -> ElevenLabs -> Backend Analysis -> Frontend Response (Voice/Text)

*   **Phase 4.2: Optional Refinements**
    *   [ ] Advanced Prompting Techniques (Backend/Frontend)
    *   [ ] Image Resizing (Backend)
    *   [ ] Asynchronous Task Handling (Backend - Celery, etc.)
    *   [ ] Response Caching (Backend)
    *   [ ] Scalability Configuration (Deployment)
    *   [ ] Monitoring & Logging Integration (Deployment)

---

## Stage 6: Modular LLM Provider Implementation

**Goal:** Create a modular system to easily switch between different LLM providers (OpenAI, Gemini) with minimal code changes.

*   **Phase 6.1: Central Configuration**
    *   [ ] Create `llm_config.py` module to centralize provider configuration
    *   [ ] Implement environment-based provider selection (`LLM_PROVIDER` variable)
    *   [ ] Add conditional configuration for base URLs, API keys, and default models
    *   [ ] Add basic validation and error handling for misconfiguration

*   **Phase 6.2: Service Adaptation**
    *   [ ] Modify `openai_service.py` to use the central configuration
    *   [ ] Update client initialization to conditionally include base URL
    *   [ ] Add provider-aware model selection logic
    *   [ ] Implement minimal provider-specific message format adaptations if needed

*   **Phase 6.3: Testing and Verification**
    *   [ ] Test with OpenAI configuration to ensure baseline functionality
    *   [ ] Test with Gemini configuration via compatibility endpoint
    *   [ ] Compare image analysis capabilities between providers
    *   [ ] Document any provider-specific limitations or considerations

*   **Phase 6.4: CI/CD & Deployment Updates**
    *   [ ] Update documentation with provider configuration instructions
    *   [ ] Ensure all provider API keys are properly handled in deployment
    *   [ ] Add provider selection to deployment configuration
    *   [ ] (Optional) Implement provider fallback mechanism for resilience
