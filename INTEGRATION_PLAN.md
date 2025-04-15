# ElevenLabs Custom LLM Backend Integration Plan

## 1. Overview

This plan outlines the necessary steps to configure and modify the existing Flask backend (`app.py`) to function correctly as a **Custom LLM provider** for an ElevenLabs Conversational AI agent. The goal is to enable the agent to leverage our backend's image analysis capabilities within a voice conversation.

This plan details the backend modifications required for our Flask application to serve as the **Custom LLM endpoint** for an ElevenLabs Conversational AI agent.

**Key Architectural Points:**
*   The backend exposes an OpenAI-compatible `/v1/chat/completions` endpoint.
*   ElevenLabs sends conversation history (including potentially user-provided context or instructions) to this endpoint.
*   Our backend intercepts this request, identifies if image context is relevant (based on a mechanism like conversation ID), injects the image data (e.g., URL) into the `messages` array, and then forwards the modified request to the *actual* LLM (e.g., GPT-4o).
*   The response from the actual LLM is streamed back through our backend to the ElevenLabs service.

**Note on Voice Handling:** The actual handling of microphone input (Speech-to-Text) and speaker output (Text-to-Speech) occurs between the **frontend client (using an ElevenLabs SDK)** and the **ElevenLabs service**. This backend component focuses solely on receiving transcribed text from ElevenLabs, processing it (potentially adding image context), interacting with the target LLM (OpenAI/Gemini), and streaming the text response back to ElevenLabs.

**Simplified Data Flow:**
```
1. User Speaks -> Frontend (ElevenLabs SDK)
2. Frontend (SDK) -> Streams Audio to ElevenLabs Service (STT)
3. ElevenLabs Service -> Sends Transcribed Text (+ context) to Our Backend (`/v1/chat/completions`)
4. Our Backend -> Processes text, injects image URL (if applicable), calls OpenAI/Gemini
5. OpenAI/Gemini -> Streams Text Response back to Our Backend
6. Our Backend -> Streams Text Response back to ElevenLabs Service
7. ElevenLabs Service -> Synthesizes Text to Audio (TTS) Stream
8. ElevenLabs Service -> Streams Audio back to Frontend (SDK)
9. Frontend (SDK) -> Plays Audio to User
```

## 2. Frontend Changes (`frontend/src/App.jsx`)

*   **Configuration:** Continue using the `useConversation` hook pointing to the custom backend URL (`/v1/chat/completions`), proxied through Vite. No changes needed here.
*   **Image Upload UI:** Retain the existing `<input type="file">` element for user image uploads.
*   **Upload Logic:**
    *   When an image is selected by the user, send this image file via a `POST` request to a *new* backend endpoint (e.g., `/upload_image_get_url`).
    *   Include a conversation identifier (e.g., the `temporaryId` from `useConversation` if available and stable, or generate a unique session ID) in the upload request payload. This is critical for the backend to associate the image with the correct voice session.
    *   Receive the publicly accessible URL for the uploaded image from the backend's response.
*   **User Feedback (Optional but Recommended):** Display a thumbnail of the uploaded image to confirm successful upload.
*   **Signaling Backend (Crucial):** After a successful upload and URL retrieval, the frontend must inform the backend that an image is ready to be discussed in the *current* voice session. Options:
    *   **Option A (Simplest):** Instruct the user to mention the image (e.g., "Let's talk about the image I uploaded"). The backend can detect this phrase.
    *   **Option B (More Robust):** Make a separate, small API call to the backend (e.g., `POST /signal_image_ready`) including the conversation identifier. This tells the backend to inject the image on the *next* user turn in that specific conversation.

## 3. Backend Changes (`app.py`)

*   **Configuration:**
    *   Define a configuration variable for the image upload directory (e.g., `app.config['UPLOAD_FOLDER'] = './uploads'`).
    *   Ensure this directory exists and the Flask application has read/write permissions.
    *   Define or dynamically determine the public base URL of the server (e.g., ngrok URL, deployed domain) for constructing image URLs.
*   **New Endpoint: Image Upload & Storage (`/upload_image_get_url`):
    *   Method: `POST`.
    *   Receives the image file and the conversation identifier from the frontend request.
    *   Validate file type/size if necessary.
    *   Generate a unique filename (e.g., using `uuid.uuid4()`) to prevent collisions.
    *   Save the image to the `UPLOAD_FOLDER` using the unique filename.
    *   Store the mapping between the `conversation_identifier` and the `unique_filename` in a server-side store (e.g., the `image_context` dictionary or a more robust cache/database for production).
        ```python
        # Example using a dictionary
        image_context[conversation_id] = unique_filename
        ```
    *   Construct the full public URL for the image (e.g., `f"{base_url}/serve_image/{unique_filename}"`).
    *   Return a JSON response to the frontend containing the `public_image_url`.
*   **New Endpoint: Image Serving (`/serve_image/<filename>`):
    *   Method: `GET`.
    *   Uses Flask's `send_from_directory` to securely serve the image specified by `<filename>` from the `UPLOAD_FOLDER`.
        ```python
        @app.route('/serve_image/<filename>')
        def serve_image(filename):
            return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
        ```
    *   This endpoint allows the LLM (e.g., OpenAI) to fetch the image directly via the URL provided.
*   **Modified Endpoint: Chat Completions (`/v1/chat/completions`):
    *   **ElevenLabs Protocol:** This endpoint **must** strictly adhere to the OpenAI Chat Completions API specification for both requests and responses (especially SSE format for streaming). See [ElevenLabs Custom LLM Docs](https://elevenlabs.io/docs/conversational-ai/customization/custom-llm#custom-llm-server).
    *   Receives the request from ElevenLabs.
    *   **`user_id` Mapping:** Extract the `user_id` field from the incoming request and map it to the `user` field when forwarding the request to the actual LLM (e.g., OpenAI). This is required by the protocol.
    *   Extract the `messages` list from `request.json`.
    *   **Identify Conversation:** Determine the current `conversation_identifier`. 
        *   **Option A (Investigate):** Check if the `user_id` provided by ElevenLabs is unique per conversation session. If so, it can be used as the `conversation_identifier`.
        *   **Option B (Fallback):** If `user_id` is not session-unique, rely on the frontend signaling mechanism (Option 2.B under Frontend Changes) using an ID provided by the frontend (e.g., `temporaryId`).
        *   **(Note:** Ensure the "Custom LLM extra body" setting is enabled in ElevenLabs to receive fields like `user_id`).
    *   **Check for Pending Image:** Look up the `conversation_identifier` in the `image_context` store.
    *   **Inject Image URL (Conditional Logic):**
        *   If an image filename is associated with this conversation *and* the condition for injection is met (e.g., this is the first user message after the frontend signaled `image_ready` or the first message of a session where `user_id` is the identifier and an image exists for it):
            *   Retrieve the `unique_filename` from `image_context`.
            *   Construct the `public_image_url`.
            *   Create the OpenAI-compatible image message payload:
                ```python
                image_message = {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "(System note: The user has uploaded an image. Analyze the following image and the user's subsequent query.)" # Adjust text as needed
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": public_image_url,
                                "detail": "auto" # or "low"/"high"
                            }
                        }
                    ]
                }
                ```
            *   **Insert** this `image_message` into the `messages` list. Recommended position: index 1 (immediately after the system prompt at index 0).
                ```python
                messages_list = request.json.get('messages', [])
                if should_inject_image(conversation_identifier): # Your logic here
                    filename = image_context.pop(conversation_identifier) # Remove after use
                    public_image_url = f"{base_url}/serve_image/{filename}"
                    # ... create image_message ...
                    messages_list.insert(1, image_message)
                ```
            *   **(Important):** Remove the filename from `image_context` after successful injection (`image_context.pop(conversation_identifier)`) to prevent it from being added to every subsequent message in the same turn.
    *   **Forward to LLM:** Pass the (potentially modified) `messages_list` to the `llm_service.generate_completion` or `llm_service.generate_completion_stream` function.

## 4. Testing Strategy

1.  **Unit Test Backend:** Test `/upload_image_get_url` and `/serve_image/<filename>` endpoints independently.
2.  **Integration Test (Manual):**
    *   Run frontend and backend (with ngrok for public URL).
    *   Configure ElevenLabs Custom LLM with the ngrok URL for `/v1/chat/completions`.
    *   Upload an image using the frontend UI.
    *   Verify the image is saved on the server and the `/serve_image` URL works in a browser.
    *   Start a voice conversation via ElevenLabs.
    *   Signal the backend (e.g., say "Look at my image").
    *   Check backend logs to confirm the `image_message` is correctly created and inserted into the `messages` list sent to OpenAI.
    *   Verify the LLM's response indicates it has 'seen' and considered the image.
    *   Continue the conversation and verify the image is *not* re-injected unless a new image is uploaded.

## 5. Future Considerations & Improvements

*   **Robust Conversation Identification:** Find a reliable way to get a unique ID for each ElevenLabs session to manage `image_context`.
*   **Multi-Image Handling:** Extend `image_context` to support multiple images per conversation.
*   **State Management:** Consider a more robust store than a simple dictionary for `image_context` (e.g., Redis, database) for scalability and persistence.
*   **Error Handling:** Add try/except blocks for file operations, network requests, and potential KeyErrors in `image_context`.
*   **Security:** Implement authentication/authorization for upload and serving endpoints if needed.
*   **Image Optimization:** Consider resizing/compressing images on upload if bandwidth/storage is a concern, balancing with analysis quality (`detail` parameter in `image_url`).
*   **LLM Choice:** Implement logic to easily switch between OpenAI and Gemini (via compatibility endpoint) as discussed with Kyle.

## Revised ElevenLabs Integration Strategy (Post-Research)

Based on detailed research into integrating the `@11labs/react` SDK with Vite/React, the following changes are required:

1.  **Backend for Signed URLs:** Direct client-side API key usage (`VITE_ELEVENLABS_API_KEY`) is insecure and must be removed. A backend endpoint (e.g., Node.js/Express or Python/Flask) is **mandatory** to securely generate temporary Signed URLs using the server-stored API key. The frontend will fetch this URL before initiating the connection.
2.  **Frontend Refactor:** The React component (`App.jsx` or a dedicated component) must be updated to:
    *   Fetch the Signed URL from the backend.
    *   Request microphone permissions (`navigator.mediaDevices.getUserMedia`) *before* starting the session.
    *   Use the `useConversation` hook with the `url` option (`startSession({ url: signedUrl })`).
    *   Implement essential callbacks (`onConnect`, `onDisconnect`, `onMessage`, `onError`).
    *   **Crucially, implement `useEffect` cleanup to call `conversation.endSession()` on component unmount.**
3.  **HTTPS for Development:** Microphone access requires a secure context. The Vite development server must be configured to use HTTPS (`vite.config.js` or `vite --https`).
4.  **Troubleshooting Note:** Console errors like "A listener indicated an asynchronous response..." are likely caused by browser extensions, not the primary integration logic.

## 6. ElevenLabs Voice Integration Testing Results

After extensive testing of the ElevenLabs voice integration, we have confirmed several key findings and implementation approaches:

1. **SDK and Browser Compatibility:**
   * The ElevenLabs SDK works correctly when properly initialized and managed.
   * React's StrictMode can cause issues with WebSocket connections due to double-mounting of components - disabling it resolves connection issues.
   * Browser-based WebSocket connections require proper cleanup to avoid lingering connections.

2. **Testing Methodologies:**
   * Created a minimalist test approach using vanilla HTML/JavaScript to isolate and confirm WebSocket functionality.
   * `test_eleven_voice.html`: A basic test page that isolates ElevenLabs voice functionality without React's lifecycle interference.
   * `minimal_voice_test.html`: An even more simplified test that directly connects to the ElevenLabs WebSocket API, allowing step-by-step verification of the connection, microphone access, message sending, and audio playback.

3. **Key Implementation Requirements:**
   * WebSocket connections must be properly terminated on component unmount.
   * Microphone permissions must be requested before attempting to establish WebSocket connections.
   * UI should clearly indicate connection status to users.
   * Connection management should be separated from conversation interaction in the UI.

4. **Confirmed Working Approach:**
   * Flask backend providing signed URLs works reliably.
   * Direct WebSocket connections to ElevenLabs work when properly initialized and managed.
   * Audio playback functions correctly when the connection is stable.
   * Separating connection management from conversation logic improves reliability and user experience.

These findings provide a solid foundation for implementing the voice functionality in the main React application, with particular focus on proper lifecycle management and connection handling.

This approach aligns with ElevenLabs' security recommendations and best practices for robust real-time voice integration.
