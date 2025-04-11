# Integration Plan: Interactive Image Context with ElevenLabs Voice Sessions

## Goal

To enable users to upload an image and then have an interactive voice conversation with an AI (powered by ElevenLabs Conversational AI and a vision LLM like GPT-4o) about the specific contents of that image. The AI must be able to reference the image data to answer follow-up questions asked via voice.

## Challenge

The primary technical challenge is persisting the context of the uploaded image (specifically, the image data itself, not just an initial description) throughout the entire voice session managed by ElevenLabs. The backend Custom LLM endpoint (`/v1/chat/completions`), which processes the user's voice queries, needs reliable access to this image data for each relevant turn to send it to the underlying vision model.

## Key Research Findings (Based on Analysis of ElevenLabs Documentation)

1.  **OpenAI Compatibility is Strict:** The Custom LLM endpoint *must* adhere strictly to the OpenAI `/chat/completions` API request/response format.
2.  **Modifying `messages` is Risky:** Directly modifying the `messages` array received from ElevenLabs within the Custom LLM endpoint before calling the vision model is technically possible but **not recommended**. It's an undocumented pattern and risks incompatibility with ElevenLabs' internal state management.
3.  **Limited Frontend-to-Backend Context via ElevenLabs:** Mechanisms within the `@11labs/react` SDK (`useConversation`) for passing context directly to the backend via ElevenLabs channels appear unsuitable or unreliable for this use case:
    *   `overrides`: Only for specific, predefined agent parameters at session start.
    *   `clientTools`: Wrong direction (backend calls frontend).
    *   `Custom LLM extra body`: Likely set at agent config time, no clear way documented to set dynamically from React SDK `startSession`.
    *   `sendContextualUpdate`: Purpose is for external context, but documentation is **unclear** if/how its payload directly reaches the Custom LLM backend endpoint.
4.  **`system__conversation_id` is Key:** ElevenLabs provides a system dynamic variable, `system__conversation_id`, which is a unique, stable identifier for the conversation session. This is the most promising way to link external data to a session.
5.  **Recommended Approach: Backend-Centric Context:** The most robust solution involves managing the image context entirely on the backend server, using the `system__conversation_id` as the key to associate the image data with the correct voice session.

## Critical Uncertainty

*   **Location of `system__conversation_id`:** While the ID exists, the documentation reviewed **does not explicitly state *where* this ID appears** in the request payload received by the Custom LLM backend endpoint (`/v1/chat/completions`). Is it in request headers, the main JSON body, or the `elevenlabs_extra_body`? **This must be verified first.**

## Implementation Plan

**Phase 1: Verification (Highest Priority)**

1.  **Action:** Modify the Flask backend (`/v1/chat/completions` in `app.py`) to log the *entire* incoming request object (headers, body, query params) received from ElevenLabs during an active voice session.
2.  **Test:** Upload an image, start a voice session, speak a query.
3.  **Goal:** Identify the precise location of `system__conversation_id` (or an equivalent stable session identifier) in the logs.

**Phase 2: Backend Implementation (Contingent on Verification)**

1.  **Storage:** Implement backend storage for image context.
    *   *Initial:* Simple Python dictionary in `app.py` (e.g., `session_storage = {}` mapping `conversationId` -> `imageData`).
    *   *Future:* Consider Redis, database, or blob storage for scalability/persistence.
2.  **New Endpoint 1 (`/upload_image`):**
    *   Accepts `POST` request with image data (e.g., base64).
    *   Generates a temporary unique ID (e.g., `uuid.uuid4().hex`).
    *   Stores image data keyed by the temporary ID (e.g., in a separate `temp_storage` dict).
    *   Returns the temporary ID to the frontend.
3.  **New Endpoint 2 (`/associate_context`):**
    *   Accepts `POST` request with `conversationId` and `temporaryId` from the frontend.
    *   Retrieves image data from `temp_storage` using `temporaryId`.
    *   Stores image data in main `session_storage` using `conversationId` as the key.
    *   Cleans up the entry in `temp_storage`.
4.  **Modify Endpoint 3 (`/v1/chat/completions` - Custom LLM):**
    *   Extract the `conversationId` from its verified location in the incoming request.
    *   Look up `imageData` from `session_storage` using the `conversationId`.
    *   **If found:** Construct the multimodal payload for the vision LLM (e.g., GPT-4o), adding the `imageData` (e.g., as `{"type": "image_url", "image_url": {"url": "data:image/..."}}`) to the last user message content array.
    *   Call the vision LLM.
    *   Handle cases where the `conversationId` or image data is not found gracefully.
    *   Return the response formatted for ElevenLabs.

**Phase 3: Frontend Implementation (`App.jsx`)**

1.  **Image Upload (`handleFileSelected`):**
    *   Modify the existing `fetch` or create a new one to send the image data to the `/upload_image` backend endpoint.
    *   Receive the `temporaryId` from the response and store it in React state.
2.  **Voice Session Initiation:**
    *   Identify how the `@11labs/react` SDK (`useConversation` hook) makes the `conversationId` available after `startSession()` is successfully called (e.g., via state update, callback).
    *   Once the `conversationId` is obtained, make a `fetch` call to the `/associate_context` backend endpoint, sending both the `conversationId` and the stored `temporaryId`.

**Phase 4: Testing**

1.  Conduct thorough end-to-end testing:
    *   Upload an image.
    *   Verify initial description (if implemented).
    *   Start voice session.
    *   Ask specific questions about the image content.
    *   Verify the AI's responses accurately reflect the image details.
    *   Test edge cases (e.g., starting voice without uploading, errors during association).
