import React, { useState, useEffect, useRef } from 'react';
import { useConversation } from '@11labs/react';
import './App.css';

function App() {
  // Initialize state with a system message to ensure display is working
  const [messages, setMessages] = useState([{
    type: 'system',
    text: 'Conversation started. Messages will appear here.',
    timestamp: new Date().toISOString()
  }]);
  
  // Add messages to conversation UI
  const addMessageToUI = (text, type) => {
    setMessages(prev => [...prev, {
      text,
      type,
      timestamp: new Date().toISOString()
    }]);
  };
  const [status, setStatus] = useState('disconnected');
  const [error, setError] = useState(null);
  const [selectedImage, setSelectedImage] = useState(null); // State for selected image file
  const [isUploading, setIsUploading] = useState(false); // State for upload loading indicator
  const [sessionId, setSessionId] = useState(null); // State for sessionId
  const [uploadError, setUploadError] = useState(null); // State for image upload errors
  
  // Reference to track component mounting status
  const isMounted = useRef(true);
  

  // Backend URL for fetching signed URL - use relative path when served from same domain
  const backendUrl = '';  // Empty string will make fetch use relative paths
  
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
      console.log('Received message:', JSON.stringify(message, null, 2));
      if (!isMounted.current) return;
      
      // MESSAGE HANDLER: Only show AI messages in conversation
      
      // 1. Skip user transcripts completely
      if (message?.type === 'user_transcript') {
        return;
      }
      
      // 2. Handle messages with the source property
      if (message?.message) {
        if (message.source === 'ai') {
          // AI message - display it
          addMessageToUI(message.message, 'agent');
          return;
        } 
        else if (message.source === 'user') {
          // User message - skip it
          return;
        }
      }
      
      // 3. Handle agent_response type messages (always from AI)
      if (message?.type === 'agent_response') {
        const text = message.message || message.agent_response_event?.text || '';
        if (text) {
          addMessageToUI(text, 'agent');
          return;
        }
      }
      
      // 4. Handle received_message objects
      if (message?.received_message) {
        let text = '';
        let source = null;
        
        if (typeof message.received_message === 'object') {
          text = message.received_message.message || '';
          source = message.received_message.source;
        } else if (typeof message.received_message === 'string') {
          text = message.received_message;
        }
        
        // Only show AI messages
        if (text && source === 'ai') {
          addMessageToUI(text, 'agent');
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
      
      // Call the session end API to clean up resources
      if (sessionId) {
        console.log(`Triggering cleanup for session: ${sessionId}`);
        try {
          const response = await fetch(`${backendUrl}/api/session/end`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ session_id: sessionId })
          });
          
          if (response.ok) {
            const data = await response.json();
            console.log('Session cleanup successful:', data);
          } else {
            console.warn('Session cleanup returned error status:', response.status);
          }
        } catch (cleanupError) {
          // Log but don't block on cleanup errors
          console.error('Error during session cleanup:', cleanupError);
        }
      }
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
    
    // Allow upload even if not connected yet - the session ID will be stored
    // and linked when the connection is established
    setIsUploading(true);
    setError(null);
    console.log("Uploading image:", selectedImage.name);

    // Always use the sessionId from the conversation object if available
    // This ensures we're using the same ID that ElevenLabs assigned
    const currentSessionId = conversation?.sessionId || sessionId;
    console.log("Current conversation sessionId:", conversation?.sessionId);
    console.log("Current stored sessionId:", sessionId);
    const formData = new FormData();
    formData.append('image', selectedImage);
    
    // Store the current session_id if we have one
    if (sessionId) {
      formData.append('session_id', sessionId);
    }

    setIsUploading(true);
    setUploadError(null);
    
    try {
      const response = await fetch('/upload_image', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.status}`);
      }
      
      const data = await response.json();
      console.log('Upload response:', data);
      
      // Add a message to the conversation about the image
      setMessages(prev => [...prev, {
        type: 'system',
        text: '✅ Image uploaded successfully. You can now ask the AI about this image.',
        timestamp: new Date().toISOString()
      }]);
      
      // Clear the selected image from state but keep the UI feedback
      setSelectedImage(null);
      return data; // Return data for potential chaining
    } catch (error) {
      setUploadError(error.message);
      return null; // Return null to indicate failure
    } finally {
      setIsUploading(false);
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
            backgroundColor: status === 'connected' ? '#4CAF50' : '#f44336', 
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: status === 'connecting' ? 'not-allowed' : 'pointer',
            transition: 'background-color 0.3s'
          }}>
          {status === 'connecting' ? 'Connecting...' :
           status === 'connected' ? 'Disconnect' : 'Connect'}
        </button>
      </div>

      {/* Image Upload Section */}
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
          style={{ display: 'block', marginBottom: '10px' }}
        />
        <button 
          onClick={handleImageUpload}
          disabled={isUploading || !selectedImage}
          style={{
            padding: '8px 16px',
            backgroundColor: '#2196F3',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: (isUploading || !selectedImage) ? 'not-allowed' : 'pointer',
            width: '100%'
          }}>
          {isUploading ? 'Uploading...' : 'Upload Image'}
        </button>
      </div>
      
      {/* Conversation History */}
      <div style={{ 
        border: '1px solid #ddd', 
        borderRadius: '4px', 
        height: '300px', 
        padding: '15px',
        overflowY: 'auto',
        backgroundColor: '#fff',
        marginBottom: '20px'
      }}>
        <h3 style={{ margin: '0 0 10px 0' }}>Conversation</h3>
        {/* Debug info to help troubleshoot */}
        <div style={{ fontSize: '12px', color: '#666', marginBottom: '10px' }}>
          Message count: {messages.length}
        </div>
        
        <div>
          {messages
            .filter(msg => msg.type === 'agent' || msg.type === 'system') // Only show AI and system messages
            .map((msg, index) => (
            <div key={index} style={{ 
              marginBottom: '12px',
              padding: '8px 12px',
              borderRadius: '4px',
              backgroundColor: msg.type === 'agent' ? '#f1f8e9' : '#f5f5f5'
            }}>
              <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
                {msg.type === 'agent' ? 'AI' : 'System'}:
              </div>
              <div>{msg.text}</div>
            </div>
          ))}
        </div>
      </div>
      
      {/* Error Display */}
      {error && (
        <div style={{ 
          padding: '12px', 
          backgroundColor: '#ffebee', 
          color: '#c62828',
          border: '1px solid #ef9a9a',
          borderRadius: '4px',
          marginBottom: '15px'
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}
    </div>
  );
}

export default App;
