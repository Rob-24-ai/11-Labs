# Multimodal Image Analysis Service - Build Plan

This plan outlines the development phases for building an interchangeable multimodal LLM image analysis service, following a structured approach.

## Project Goal & Context

The primary goal of this project is to create a backend API service (this "Image Reader Module") using Python and Flask. This service will:

1.  Accept image data via API calls (supporting both direct file uploads and image URLs).
2.  Process the received image data.
3.  Utilize a configurable Vision Large Language Model (VLLM), such as OpenAI's GPT-4o or Anthropic's Claude Sonnet, to perform analysis or answer questions about the image based on a provided prompt.
4.  Return the textual analysis results via the API.

This module is intended to function as an external tool, specifically designed to be called via a **Webhook** from an **ElevenLabs Conversational AI agent**. The ElevenLabs agent will handle the primary voice/text conversation with the end-user. When the conversation requires image understanding, the ElevenLabs agent will call the API endpoint provided by this module. This creates an architecture where two distinct AI systems collaborate: the ElevenLabs agent manages the conversation, and this module provides specialized image analysis capabilities on demand.

The plan below details the steps to build this standalone Image Reader Module API.

## Phase 1: Core Functionality (Minimal Viable Product)

**Goal:** Establish a basic API endpoint that can accept an image (upload or URL) and analyze it using *one* predefined LLM provider.

**Status:** [Not Started]

**Sub-steps:**

- [ ] **Project Setup & Core API:**
  - [ ] **Technology Stack:** Confirm Python, Flask (or FastAPI).
  - [ ] **Initialize Project:** Set up project directory, virtual environment.
  - [ ] **Flask App:** Create basic Flask application structure (`app.py` or similar).
  - [ ] **API Endpoint:** Define initial `/analyze` endpoint accepting `POST` requests.
  - [ ] **Configuration:** Basic logging, error handling.
  - [ ] **CORS:** Implement CORS middleware.

- [ ] **Image Input Handling:**
  - [ ] Modify `/analyze` to accept image file uploads (e.g., via `request.files`).
  - [ ] Modify `/analyze` to accept an image URL (e.g., via form data or JSON payload).
  - [ ] **Security (Basic):**
    - [ ] Implement server-side file size limits.
    - [ ] Validate MIME type using `python-magic` against a whitelist (`image/jpeg`, `image/png`). Reject invalid types/sizes.

- [ ] **Image Processing:**
  - [ ] **Library:** Add `Pillow` (PIL) dependency.
  - [ ] Implement logic to open/validate image data from both file uploads and fetched URLs.
  - [ ] Implement `base64` encoding function for the initial LLM's required format.

- [ ] **LLM Integration (Initial - Single Provider):**
  - [ ] **Provider:** Select one initial provider (e.g., OpenAI GPT-4o).
  - [ ] **API Call:** Add `requests` library dependency and implement direct API interaction logic.
  - [ ] **Authentication:** Load API key securely from an environment variable (add `python-dotenv` dependency).
  - [ ] **Request/Response:** Format the request payload, send the request, parse the response to extract the text analysis.
  - [ ] **Endpoint Logic:** Integrate LLM call into the `/analyze` endpoint and return the analysis.

- [ ] **Dependency Management:**
  - [ ] Create/update `requirements.txt` (or `pyproject.toml`) with dependencies (Flask, Pillow, requests, python-magic, python-dotenv).

- [ ] **Testing Checkpoint:**
  - [ ] Verify `/analyze` endpoint with `curl` or Postman (file uploads and URLs).
  - [ ] Confirm basic analysis text is returned.
  - [ ] Ensure basic security checks reject invalid inputs.

## Phase 2: LLM Interchangeability & Enhanced Image Handling

**Goal:** Refactor the LLM integration to support multiple providers using an abstraction layer and enhance image handling security/flexibility.

**Status:** [Not Started]

**Sub-steps:**

- [ ] **LLM Abstraction (Adapter Pattern):**
  - [ ] Define abstract base class/interface `LLMService` with `analyze_image(...)` method.
  - [ ] Define custom exception `LLMIntegrationError`.
  - [ ] Create concrete adapter class for Provider 1 (e.g., `OpenAIAdapter`).
  - [ ] Implement provider-specific auth, request formatting, response parsing in Adapter 1.
  - [ ] Create concrete adapter class for Provider 2 (e.g., `AnthropicAdapter`).
  - [ ] Implement provider-specific logic in Adapter 2.
  - [ ] (Optional) Create adapter for Provider 3 (e.g., `GeminiAdapter`).

- [ ] **Factory & Configuration:**
  - [ ] Implement factory function `get_llm_service()` reading environment variables (`LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL_ID`).
  - [ ] Update `/analyze` endpoint:
    - [ ] Optionally accept `llm_provider` and `prompt` parameters.
    - [ ] Use factory function to get `LLMService` instance.
    - [ ] Call `analyze_image` via the interface.

- [ ] **Enhanced Image Security & Handling:**
  - [ ] **Filename Sanitization:** Generate unique, secure filenames for uploads (e.g., using `uuid`).
  - [ ] **(Optional) Temporary Storage:** Implement if needed for scanning.
  - [ ] **URL Validation:** Add basic SSRF prevention checks.
  - [ ] Refine existing validation logic.

- [ ] **Prompt Management:**
  - [ ] Ensure custom `prompt` is passed to `analyze_image`.
  - [ ] Define a default prompt if none provided.

- [ ] **Testing Checkpoint:**
  - [ ] Verify switching between *at least two* LLM providers via config/parameter.
  - [ ] Confirm consistent analysis initiation across providers.
  - [ ] Test enhanced security measures.
  - [ ] Test custom prompt functionality.

## Phase 3: Deployment & Refinements

**Goal:** Package the application for deployment and add optional refinements for robustness and usability.

**Status:** [Not Started]

**Sub-steps:**

- [ ] **Containerization:**
  - [ ] Create `Dockerfile`.
  - [ ] Build and test Docker image locally.

- [ ] **Configuration Management:**
  - [ ] Ensure all configuration is via environment variables.
  - [ ] Document required environment variables (`.env.example`, README).

- [ ] **Deployment:**
  - [ ] Select cloud deployment target (PaaS, Container Service, IaaS).
  - [ ] Configure deployment environment.
  - [ ] Deploy the containerized application.
  - [ ] Test the deployed service.

- [ ] **Refinements (Optional/As Needed):**
  - [ ] **Advanced Prompting:** Implement template system if needed.
  - [ ] **Image Resizing:** Add resizing options if needed.
  - [ ] **Asynchronous Tasks:** Implement task queue (e.g., Celery) if needed for long calls.
  - [ ] **Caching:** Implement response caching if applicable.
  - [ ] **Scalability:** Configure auto-scaling, load balancing.
  - [ ] **Monitoring & Logging:** Integrate with cloud platform services.

- [ ] **Testing Checkpoint:**
  - [ ] Verify successful deployment.
  - [ ] Perform integration tests in the deployed environment.
  - [ ] (If applicable) Test optional refinement features.
