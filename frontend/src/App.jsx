import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useConversation } from '@11labs/react';
import './App.css';

function App() {
  // Basic state
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState('disconnected');
  const [error, setError] = useState(null);
  
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
      // Expecting { signedUrl: '...', agentId: '...' }
      if (!data.signedUrl || !data.agentId) {
        throw new Error('Invalid response format from backend: missing signedUrl or agentId');
      }
      console.log('Successfully obtained signed URL and Agent ID');
      return data; // Return the whole object { signedUrl, agentId }
    } catch (error) {
      console.error('Failed to fetch signed URL:', error);
      setStatus(`Error fetching URL: ${error.message}`);
      throw error; // Re-throw to be caught by handleConnect
    }
  };

  // Function to start the conversation
  const startConversation = async (signedUrl, agentId) => { // Accept agentId
    console.log('Starting conversation with signed URL and Agent ID');
    setStatus('Connecting...');
    try {
      // Use the URL and agentId directly
      await conversation.startSession({ url: signedUrl, agentId: agentId });
      console.log('Conversation started successfully via startSession');
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
    if (conversation.status !== 'connected') {
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
      const { signedUrl, agentId } = await fetchSignedUrl(); // Destructure response
      if (signedUrl && agentId) {
        await startConversation(signedUrl, agentId); // Pass both to startConversation
      }
    } catch (error) {
      // Errors from permission or fetch are already handled and status set
      console.error('Failed to start conversation:', error);
      setError(`Connection failed: ${error.message}`);
      setStatus('error');
    }
  };
  
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
  }, []);

  return (
    <div className="App" style={{ maxWidth: '600px', margin: '0 auto', padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1>Voice Interaction</h1>
      
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
          onClick={conversation.status === 'connected' ? stopConversation : handleConnect}
          disabled={status === 'connecting'}
          style={{ 
            flex: 1,
            padding: '10px 16px',
            backgroundColor: conversation.status === 'connected' ? '#f44336' : '#4CAF50',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: status === 'connecting' ? 'not-allowed' : 'pointer',
            fontWeight: 'bold'
          }}
        >
          {status === 'connecting' ? 'Connecting...' : 
           conversation.status === 'connected' ? 'Disconnect' : 'Connect'}
        </button>
      </div>
      
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
                backgroundColor: msg.type === 'agent' ? '#e3f2fd' : '#f1f8e9',
                borderRadius: '4px'
              }}>
                <strong>{msg.type === 'agent' ? 'Agent:' : 'You:'}</strong> {msg.text}
                {msg.timestamp && (
                  <div style={{ fontSize: '0.7em', color: '#757575', marginTop: '5px' }}>
                    {new Date(msg.timestamp).toLocaleTimeString()}
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
