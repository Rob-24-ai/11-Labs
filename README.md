# Multimodal Image Analysis Service (Image Reader Module)

## Project Overview

This project implements a Python/Flask backend service designed to act as a **Custom LLM provider for ElevenLabs Conversational AI**. Its primary goal is to enable voice-driven conversations that can understand and discuss images provided by the user.

The service accepts image data (uploads or URLs), uses a Vision Language Model (like GPT-4o) to analyze them based on conversational context, and integrates seamlessly with an ElevenLabs agent via the standard `/v1/chat/completions` endpoint.

## Current Status & Context (As of 2025-04-12)

**IMPORTANT:** The codebase in this directory has been manually reverted to a specific prior state. This was done to establish a stable baseline that aligns with a previous code review and to address challenges encountered in integrating image URL handling correctly within the voice conversation flow.

The current state of the code corresponds roughly to the completion of **Phase 2.1** outlined in the `PLAN.md` file. Key features implemented at this stage include:

*   The core Flask application (`app.py`).
*   The `/v1/chat/completions` endpoint, structured to mimic OpenAI's API.
*   Integration logic for handling `messages` arrays, including basic image data extraction.
*   An LLM abstraction layer (`llm_factory.py`, `llm_service.py`, etc.) supporting multiple providers (OpenAI, Gemini, Anthropic).
*   Successful local testing and temporary public exposure (via ngrok) for connection testing with the ElevenLabs platform.

**The primary reason for reverting was to correctly implement the insertion of image URLs into the payload sent to the underlying LLM, based on specific guidance (from Kyle).** The previous implementation path had diverged and encountered issues with the voice interaction component.

## Next Steps

Development should proceed based on the detailed steps outlined in the **`PLAN.md`** file.

The immediate next step is to **modify the `/v1/chat/completions` endpoint** within `app.py` to correctly format the `messages` payload according to the provided guidance for including `image_url` objects when calling the VLLM service. This is crucial for enabling the agent to "see" and discuss images within the voice conversation.

Refer to `PLAN.md` for the full development roadmap, including subsequent frontend integration, containerization, and deployment tasks.

## Setup & Running

(Instructions to be added - typically includes setting up a virtual environment, installing requirements, setting environment variables for API keys, and running the Flask app).
