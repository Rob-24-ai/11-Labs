Review the mobile build guide. ⁠# Mobile Build Guide: Key Technical Points for Multimodal Conversational Web App

This guide summarizes critical technical considerations based on the provided expert document for building a mobile-first multimodal (camera, voice, captions) conversational web app using React and Vite.

## I. Mobile-First & Responsive Design

*   **Strategy:** Design for mobile first, enhance progressively for larger screens.
*   **CSS:** Use `min-width` media queries (prefer `em` units).
*   **Viewport:** Essential tag: `<meta name="viewport" content="width=device-width, initial-scale=1.0">`.
*   **Layout:**
    *   **Fluid Grids:** Use relative units (`%`, `vw`, `vh`, `rem`, `em`, `fr`).
    *   **CSS Grid:** For overall page structure (macro-layout).
    *   **CSS Flexbox:** For component layout and alignment (micro-layout).
    *   **Avoid Fixed Layouts:** **Crucially, avoid fixed pixel widths for main containers or elements that should adapt.** Rely on fluid units and techniques like `max-width` to ensure content reflows naturally across screen sizes. Fixed layouts (as sometimes seen in initial CSS drafts) break responsiveness on smaller devices.
*   **Media:** Use `max-width: 100%; height: auto;` for basic flexibility. Combine with responsive image techniques (Section IV) for performance.
*   **Breakpoints:** Choose based on content, not specific devices. Use browser dev tools to find natural breaking points.

## II. Mobile UI/UX Best Practices

*   **Navigation:** Consider Bottom Tabs, Hamburger/Off-Canvas, or Priority+. Design for Thumb Zones.
*   **Touch Targets:** Minimum `44x44` CSS pixels (aim for `48x48`). Ensure sufficient spacing (>= `32px`).
*   **Voice Input (Eleven Labs):**
    *   Provide clear visual (listening/processing indicators) and audio feedback.
    *   Design conversational prompts and graceful error handling.
*   **Camera Input:**
    *   Use `navigator.mediaDevices.getUserMedia`.
    *   Maximize viewfinder space; use simple, high-contrast controls.
    *   Request permissions contextually.
    *   Consider libraries like `react-webcam` or custom hooks.
*   **Real-Time Captions:**
    *   **Readability:** Clear sans-serif font, adequate size (test!), high contrast (WCAG AA 4.5:1), bottom-center position (usually), short lines (~32-40 chars).
    *   **Accessibility:** Use ARIA live regions (`aria-live="polite"` or `"assertive"`) if captions are outside a native `<video>` element.
    *   **Performance:** Efficiently render incoming text chunks (see Section IV).

## III. Performance Optimization (React/Vite)

*   **Code Splitting:**
    *   Use `React.lazy` and `<Suspense>` for component-level splitting.
    *   Implement route-based splitting (e.g., with React Router).
    *   Vite handles splitting automatically via dynamic `import()` in production builds.
*   **Image Optimization:**
    *   **Responsive Images:** `srcset` and `sizes` attributes, `<picture>` element.
    *   **Modern Formats:** WebP, AVIF (with JPG/PNG fallbacks via `<picture>`).
    *   **Compression:** Apply appropriate lossy/lossless compression.
    *   **Lazy Loading:** Use `loading="lazy"` on `<img>` tags (specify `width`/`height`).
    *   **CDNs:** Consider for delivery and optimization.
*   **JavaScript Bundle Size & Execution:**
    *   **Tree Shaking:** Enabled by default in Vite prod builds; ensure modular imports.
    *   **Bundle Analysis:** Use `rollup-plugin-visualizer` (for Vite) to inspect bundle contents.
    *   **Dependencies:** Audit regularly, choose lightweight options, remove unused (`depcheck`).
    *   **Minification/Compression:** Handled by Vite; ensure server uses Gzip/Brotli.
    *   **Web Workers:** Offload heavy computations from the main thread.
*   **Efficient State Management:**
    *   Prefer local state (`useState`, `useReducer`) over global.
    *   Prevent unnecessary re-renders: `React.memo`, `useCallback`, `useMemo`.
    *   Choose global state libraries carefully (Context API, Redux Toolkit, Zustand, Recoil) based on frequency/complexity of updates. Zustand/Recoil often better for high-frequency streams than Context.
    *   Optimize state updates for real-time streams to minimize renders.
    *   **Structure for Concurrency:** Consider dedicated state slices/stores (e.g., using Zustand or Redux Toolkit) for each major stream (Camera Input, Mic Input/Processing, Eleven Labs Output, Captions). Manage status (idle, active, processing, error) and associated data independently to prevent unnecessary coupling and re-renders.

## IV. Integrating Real-Time Features

*   **Protocols:**
    *   **WebSockets:** Recommended for Eleven Labs streaming (low latency, bidirectional). Suitable for captions.
    *   **Server-Sent Events (SSE):** Simpler alternative for unidirectional server-to-client push (e.g., captions).
    *   **WebRTC:** Likely overkill unless P2P is needed. Requires signaling.
*   **Media Streams:**
    *   **Display:** Assign `MediaStream` to `videoElement.srcObject`.
    *   **Video Attributes:** Use `autoplay muted playsinline controls preload` appropriately.
    *   **Audio (Eleven Labs):** Use **Web Audio API** (`AudioContext`, `AudioBufferSourceNode`) for seamless decoding and playback of incoming audio chunks from streaming API. Handle user interaction requirement for `AudioContext`. Use `optimize_streaming_latency` parameter.
*   **Dynamic Captions:** Render efficiently, apply UI/UX best practices (Section II), ensure accessibility (ARIA).
*   **State Management:** Crucial for handling multiple streams without UI jank (see Section III).

## V. Leveraging Web APIs

*   **Core:** `navigator.mediaDevices.getUserMedia` (Camera/Mic), `Web Audio API` (Playback/Processing).
*   **Potentially Useful:** `Web Speech API` (fallback/alternative), `Geolocation`, `Device Orientation/Motion`, `Vibration`, `Web Storage`, `Service Workers`/`Cache API` (Offline support).

## VI. Testing & Debugging

*   **Tools:** Browser DevTools (Responsive Mode, Network Throttling), Remote Debugging (Chrome/Safari).
*   **Methods:** Emulators/Simulators AND **Real Device Testing** (essential!), Cross-Browser Testing, Performance Profiling, Accessibility Audits.

## VII. Accessibility (a11y)

*   **Fundamentals:** Semantic HTML, ARIA roles/attributes (esp. live regions), Keyboard Navigation, Focus Management.
*   **Mobile Specific:** Sufficient Touch Target size/spacing, Color Contrast.
*   **Multimodal:** Provide captions/transcripts for audio/video.

## VIII. Consistent Error Handling

*   **Strategy:** Design a unified approach for handling errors across all multimodal interactions.
*   **Sources:** Plan for API errors (network issues, rate limits, invalid responses from Eleven Labs, etc.), permission denials (`getUserMedia`), stream interruptions, and unexpected client-side issues.
*   **User Feedback:** Provide clear, non-technical feedback to the user (visual cues, messages) indicating what went wrong and potential next steps.
*   **Logging:** Implement client-side logging (potentially sending to a backend service) to capture technical details for debugging.

## IX. Security Considerations

*   **API Keys:** **Never embed sensitive API keys (like Eleven Labs) directly in the frontend JavaScript.** Use a backend proxy or serverless function to handle API requests, keeping keys secure on the server-side.
*   **Permissions:** Request user permissions (camera, microphone) contextually, clearly explaining why they are needed. Handle denials gracefully.
*   **Input Validation:** If user input is used to construct API requests, ensure proper validation and sanitization to prevent injection or abuse.

## X. Build & Deployment Considerations

*   **Build Optimization:** Leverage Vite's production build features (tree shaking, code splitting, minification). Analyze the bundle if needed (`rollup-plugin-visualizer`).
*   **Hosting:** Suitable for static hosting platforms (Netlify, Vercel, Cloudflare Pages, AWS S3/CloudFront) if API keys are handled via a separate backend/proxy.
*   **Backend/Proxy:** A simple backend service or serverless function is often necessary for secure API key management and potentially other server-side logic.
