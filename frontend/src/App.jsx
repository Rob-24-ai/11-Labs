import React, { useState, useEffect, useRef } from 'react';
import { useConversation } from '@11labs/react';
import './App.css';

function App() {
  // Basic state
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState('disconnected');
  const [error, setError] = useState(null);
  const [selectedImage, setSelectedImage] = useState(null); // State for selected image file
  const [isUploading, setIsUploading] = useState(false); // State for upload loading indicator
  const [sessionId, setSessionId] = useState(null); // State for sessionId
  
  // Reference to track component mounting status
  const isMounted = useRef(true);
  

  // Backend URL for fetching signed URL
  const backendUrl = 'http://localhost:5003';
  
  // Initialize the ElevenLabs conversation hook
  const conversation = useConversation({
    autoPlayAudio: true,
    enableAudio: true,
    
    onConnect: () => {
      console.log('Successfully connected');
      if (isMounted.current) {
        setStatus('connected');
        setError(null);
      }
    },
    
    onDisconnect: () => {
      console.log('Disconnected');
      if (isMounted.current) {
        setStatus('disconnected');
      }
    },
    
    onMessage: (message) => {
      console.log('Received message:', message);
      if (!isMounted.current) return;
      
      // Handle user speech transcripts
      if (message?.type === 'user_transcript' && message.user_transcription_event?.is_final) {
        const transcript = message.user_transcription_event.user_transcript;
        console.log('User said:', transcript);
        
        setMessages(prev => [...prev, { 
          type: 'user', 
          text: transcript,
          timestamp: new Date().toISOString()
        }]);
      } 
      // Handle agent responses
      else if (message?.type === 'agent_response') {
        let messageText = '';
        
        if (message.message) {
          messageText = message.message;
        } else if (message.agent_response_event?.text) {
          messageText = message.agent_response_event.text;
        }
        
        if (messageText) {
          console.log('Agent said:', messageText);
          setMessages(prev => [...prev, { 
            type: 'agent', 
            text: messageText,
            timestamp: new Date().toISOString()
          }]);
        }
      }
    },
    
    onError: (err) => {
      console.error('Conversation error:', err);
      if (isMounted.current) {
        setError(`Error: ${err.message || 'Unknown error'}`);
        setStatus('error');
      }
    },
  });
  
  // Fetch signed URL from the backend
  const fetchSignedUrl = async () => {
    console.log(`Fetching signed URL from ${backendUrl}/api/elevenlabs/get-signed-url`);
    setStatus('Fetching URL...');
    try {
      const response = await fetch(`${backendUrl}/api/elevenlabs/get-signed-url`);
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`HTTP error! status: ${response.status}, message: ${errorData.error || 'Unknown error'}`);
      }
      const data = await response.json();
      // Expecting { signedUrl: '...', agentId: '...', sessionId: '...' }
      if (!data.signedUrl || !data.agentId || !data.sessionId) {
        throw new Error('Invalid response format from backend: missing signedUrl, agentId, or sessionId');
      }
      console.log('Successfully obtained signed URL, Agent ID, and Session ID');
      return data; // Return the whole object { signedUrl, agentId, sessionId }
    } catch (error) {
      console.error('Failed to fetch signed URL:', error);
      setStatus(`Error fetching URL: ${error.message}`);
      throw error; // Re-throw to be caught by handleConnect
    }
  };

  // Function to start the conversation
  const startConversation = async (signedUrl, agentId, sessionId) => { // Accept agentId and sessionId
    console.log('Starting conversation with signed URL, Agent ID, and Session ID');
    setStatus('Connecting...');
    try {
      console.log('[Diag] Attempting conversation.startSession...');
      // Use the URL, agentId, and sessionId directly
      await conversation.startSession({ url: signedUrl, agentId: agentId, sessionId: sessionId });
      console.log('Conversation started successfully via startSession');
      setSessionId(sessionId); // Store the sessionId
    } catch (error) {
      console.error('Failed to start conversation:', error);
      setStatus(`Error connecting: ${error.message || error.reason || 'Unknown connection error'}`);
      // Detailed error logging
      if (error instanceof CloseEvent) {
        console.error(`WebSocket closed with code: ${error.code}, reason: ${error.reason}, wasClean: ${error.wasClean}`);
      }
    }
  };

  // Function to stop the conversation
  const stopConversation = async () => {
    if (status !== 'connected') {
      console.log('Not connected, nothing to stop');
      return;
    }
    
    try {
      console.log('Stopping conversation...');
      await conversation.endSession();
      console.log('Conversation stopped successfully');
    } catch (error) {
      console.error('Error stopping conversation:', error);
      setError(`Error stopping conversation: ${error.message}`);
    }
  };
  
  // Handler for the connect button
  const handleConnect = async () => {
    if (conversation.status === 'connected') {
      console.log('Already connected');
      return;
    }
    
    setStatus('connecting');
    setError(null);
    
    try {
      // 1. Request microphone permission
      console.log('Requesting microphone permissions...');
      await navigator.mediaDevices.getUserMedia({ audio: true });
      console.log('Microphone access granted');
      
      // 2. Get the signed URL from backend
      const { signedUrl, agentId, sessionId } = await fetchSignedUrl(); // Destructure response
      if (signedUrl && agentId && sessionId) {
        await startConversation(signedUrl, agentId, sessionId); // Pass all to startConversation
      }
    } catch (error) {
      // Errors from permission or fetch are already handled and status set
      console.error('Failed to start conversation:', error);
      setError(`Connection failed: ${error.message}`);
      setStatus('error');
    }
  };
  
  // --- Debugging: Log temporaryId changes --- 
  useEffect(() => {
    console.log(`[Debug] Conversation Status: ${status}, Temporary ID: ${conversation?.temporaryId}`);
    // Log the whole conversation object when status changes, especially when connected
    if (status) { // Log whenever status is not null/undefined
        try {
            // Attempt to stringify. Might fail on circular refs, but good first step.
            console.log(`[Debug] Conversation Object (Status: ${status}):`, JSON.stringify(conversation, null, 2)); 
        } catch (e) {
            console.log(`[Debug] Conversation Object (Status: ${status}):`, conversation); // Log raw object if stringify fails
        }
        
        // Add detailed information requested by 11Labs support
        console.log('[11Labs Support] Connection state change:', {
            status,
            timestamp: new Date().toISOString(),
            conversationId: conversation?.id || 'unknown',
            sessionId: conversation?.sessionId || sessionId || 'unknown',
            connectionState: conversation?.status || 'unknown'
        });
    }
  }, [conversation, status, sessionId]); // Re-run when conversation object reference or status changes
  // --- End Debugging ---
  
  // Cleanup on unmount
  useEffect(() => {
    isMounted.current = true;
    console.log("App component mounted");

    return () => {
      isMounted.current = false;
      console.log("App component unmounting - Attempting cleanup...");
      // Ensure we only attempt to stop if the conversation object exists and might be active
      if (conversation && typeof conversation.endSession === 'function') {
         console.log("Calling stopConversation during unmount cleanup");
         stopConversation(); // Attempt to clean up the session
      } else {
         console.log("Conversation object not available or endSession not function during unmount");
      }
    };
  }, []); // Empty dependency array to prevent re-execution on conversation changes

  // Handler for file input change
  const handleImageChange = (event) => {
    if (event.target.files && event.target.files[0]) {
      setSelectedImage(event.target.files[0]);
      console.log("Image selected:", event.target.files[0].name);
    } else {
      setSelectedImage(null);
    }
  };

  // Handler for image upload button
  const handleImageUpload = async () => {
    if (!selectedImage) {
      setError("Please select an image first.");
      return;
    }
    // Ensure connection is established AND a sessionId is available
    if (status !== 'connected' || !sessionId) {
      setError("Please ensure you are connected to the voice agent and the connection is ready.");
      console.warn("Upload prevented: Status is", status, "and sessionId is", sessionId);
      return;
    }

    setIsUploading(true);
    setError(null);
    console.log("Uploading image:", selectedImage.name);

    // Get the sessionId (it should be valid now)
    console.log("Using VALID sessionId for image upload:", sessionId); // Log the actual ID
    
    const formData = new FormData();
    formData.append('image', selectedImage);
    formData.append('session_id', sessionId);

    try {
      // Use the upload_image_get_url endpoint instead of analyze-image
      console.log(`Sending image to backend: ${backendUrl}/upload_image_get_url`);
      console.log('FormData contents:', {
        'session_id': sessionId,
        'image filename': selectedImage.name,
        'image size': selectedImage.size,
        'image type': selectedImage.type
      });
      
      const response = await fetch(`${backendUrl}/upload_image_get_url`, {
        method: 'POST',
        body: formData, // FormData includes the image file and sessionId
      });

      if (!response.ok) {
        let errorData;
        try {
          errorData = await response.json(); // Try to parse JSON error response
        } catch (parseError) {
          // If response is not JSON, use text
          errorData = { error: await response.text() };
        }
        console.error("Backend error response:", errorData);
        throw new Error(`Image upload failed: ${errorData.error || response.statusText}`);
      }

      // Parse the successful JSON response
      const result = await response.json();
      if (!result.public_image_url) {
         throw new Error("Invalid response format from backend: 'public_image_url' field missing.");
      }
      
      const imageUrl = result.public_image_url;
      console.log("Image uploaded successfully. URL:", imageUrl);
      
      // Add a success message to the conversation
      setMessages(prev => [...prev, {
        type: 'system',
        text: '✅ Image uploaded successfully!',
        timestamp: new Date().toISOString()
      }]);
      
      // Add instructions for the user
      setMessages(prev => [...prev, {
        type: 'system',
        text: `Now you can ask the voice agent about the image. Try saying "What do you see in this image?" or "Can you describe this image?"`,
        timestamp: new Date().toISOString()
      }]);

    } catch (err) {
      console.error("Image upload failed:", err);
      setError(`Image upload failed: ${err.message}`);
    } finally {
      setIsUploading(false);
      // Don't clear the image after upload in case user wants to try again
      // Leave both the selectedImage state and the file input value as is
      console.log('Upload process completed. Image selection preserved for debugging.');
    }
  };


  return (
    <div className="App" style={{ maxWidth: '600px', margin: '0 auto', padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1>ArtSensei Image Discussion</h1>
      
      {/* Status Banner */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        padding: '12px',
        border: '1px solid #ddd',
        borderRadius: '4px',
        marginBottom: '15px',
        backgroundColor: '#f8f9fa'
      }}>
        {/* Status indicator light */}
        <div style={{ 
          width: '12px', 
          height: '12px', 
          borderRadius: '50%', 
          backgroundColor: 
            status === 'connected' ? '#4CAF50' : // Green for connected
            status === 'connecting' ? '#FFC107' : // Yellow for connecting
            status === 'error' ? '#F44336' : // Red for error
            '#9E9E9E', // Grey for disconnected
          marginRight: '10px',
          transition: 'background-color 0.3s'
        }}></div>
        
        {/* Status text */}
        <div style={{ flex: 1 }}>
          <strong>Status:</strong> {
            status === 'connected' ? 'Connected' :
            status === 'connecting' ? 'Connecting...' :
            status === 'error' ? 'Error' : 'Disconnected'
          }
        </div>
      </div>
      
      {/* Controls */}
      <div style={{ display: 'flex', gap: '15px', marginBottom: '20px' }}>
        <button 
          onClick={status === 'connected' ? stopConversation : handleConnect}
          disabled={status === 'connecting'}
          style={{ 
            flex: 1,
            padding: '10px 16px',
            // Red when disconnected/idle/error (Connect), Green when connected (Disconnect)
            backgroundColor: status === 'connected' ? '#4CAF50' : '#f44336', 
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: status === 'connecting' ? 'not-allowed' : 'pointer',
            fontWeight: 'bold'
          }}
        >
          {status === 'connecting' ? 'Connecting...' :
           status === 'connected' ? 'Disconnect' : 'Connect'}
        </button>
        <button onClick={fetchSignedUrl} disabled={status === 'connecting' || status === 'connected'}>
          Connect to Agent
        </button>
      </div>

      {/* Image Upload Section */}
      {status === 'connected' && (
        <div style={{
          border: '1px dashed #ccc',
          borderRadius: '4px',
          padding: '15px',
          marginBottom: '20px',
          backgroundColor: '#f0f4f8'
        }}>
          <h3 style={{ marginTop: 0, marginBottom: '10px' }}>Upload Image for Discussion</h3>
          <input
            type="file"
            id="imageInput"
            accept="image/*"
            onChange={handleImageChange}
            disabled={isUploading}
            style={{ marginBottom: '10px', display: 'block' }}
          />
          <button
            onClick={handleImageUpload}
            // Disable if no image OR uploading OR not connected OR sessionId is missing
            disabled={!selectedImage || isUploading || status !== 'connected' || !sessionId}
            style={{
              padding: '10px 16px',
              // Update style based on the comprehensive disabled state
              backgroundColor: (!selectedImage || isUploading || status !== 'connected' || !sessionId) ? '#bdbdbd' : '#2196F3',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              // Update cursor based on the comprehensive disabled state
              cursor: (!selectedImage || isUploading || status !== 'connected' || !sessionId) ? 'not-allowed' : 'pointer',
              fontWeight: 'bold',
              width: '100%'
            }}
          >
            {isUploading ? 'Uploading Image...' : 'Upload Image'}
          </button>
        </div>
      )}
      
      {/* Conversation Area */}
      <div style={{ 
        border: '1px solid #ddd', 
        borderRadius: '4px',
        padding: '15px',
        marginBottom: '20px',
        minHeight: '200px',
        maxHeight: '400px',
        overflowY: 'auto',
        backgroundColor: '#f9f9f9'
      }}>
        <h3 style={{ marginTop: 0 }}>Conversation</h3>
        {messages.length === 0 ? (
          <p style={{ color: '#888', fontStyle: 'italic' }}>No messages yet</p>
        ) : (
          <div>
            {messages.map((msg, index) => (
              <div key={index} style={{ 
                padding: '8px 12px', 
                marginBottom: '8px',
                backgroundColor: 
                  msg.type === 'agent' ? '#e3f2fd' : 
                  msg.type === 'image_description' ? '#fff3e0' : 
                  '#f1f8e9',
                borderRadius: '4px',
                wordBreak: 'break-word', // Ensure long text wraps
                border: msg.type === 'image_description' ? '2px dashed #ff9800' : 'none'
              }}>
                <strong>{
                  msg.type === 'agent' ? 'Agent:' :
                  msg.type === 'user' ? 'You:' :
                  'System:' // Handle system messages
                }</strong> {msg.text}
                {msg.timestamp && (
                  <div style={{ fontSize: '0.7em', color: '#757575', marginTop: '4px' }}>
                    {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      
      {/* Error Display */}
      {error && (
        <div style={{ 
          color: 'white', 
          backgroundColor: '#F44336',
          padding: '10px', 
          borderRadius: '4px',
          marginBottom: '15px'
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}
      
      {/* Help Text */}
      {conversation.status !== 'connected' && (
        <div style={{ 
          backgroundColor: '#e8f5e9', 
          padding: '12px', 
          borderRadius: '4px',
          marginTop: '15px'
        }}>
          <p style={{ margin: 0 }}>
            <strong>Getting Started:</strong> Click the Connect button to start a voice conversation.
          </p>
        </div>
      )}
    </div>
  );
}

export default App;
