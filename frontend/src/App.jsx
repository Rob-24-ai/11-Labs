import React, { useState, useEffect, useRef } from 'react';
import { useConversation } from '@11labs/react';
import Message from './Message';
import './App.css';

function App() {
  // Core state
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  
  // Image handling state
  const [imageFile, setImageFile] = useState(null); // Keep for potential future use
  const [previewUrl, setPreviewUrl] = useState(null); // Keep for display
  
  // ElevenLabs conversation state
  const [transcript, setTranscript] = useState('');
  const [micPermissionGranted, setMicPermissionGranted] = useState(false);
  
  // State for Context Management
  const [temporaryId, setTemporaryId] = useState(null);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  
  // Refs
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  
  // Initialize ElevenLabs conversation hook
  const {
    startSession,
    endSession,
    status, // 'connected' or 'disconnected'
    isSpeaking, // boolean
    isRecording, // boolean
  } = useConversation({
    apiKey: import.meta.env.VITE_ELEVENLABS_API_KEY,
    url: 'http://localhost:5001/v1/chat/completions',
    onConnect: () => {
      console.log('Conversation Connected');
      // Add a system message to show connection status
      const connectMessage = {
        content: 'Connected to ElevenLabs AI. Start speaking to interact.',
        sender: 'system',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, connectMessage]);
    },
    onDisconnect: () => {
      console.log('Conversation Disconnected');
      // Add a system message to show disconnection
      const disconnectMessage = {
        content: 'Disconnected from ElevenLabs AI.',
        sender: 'system',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, disconnectMessage]);
    },
    onMessage: async (message) => {
      console.log('Conversation Message:', message);
      
      // Handle different message types
      if (message.type === 'transcript') {
        // Update the live transcript
        setTranscript(message.text);
        
        // If it's a final transcript...
        if (message.isFinal) {
          const userMessage = {
            content: message.text,
            sender: 'user',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          };
          setMessages(prev => [...prev, userMessage]);
          setTranscript(''); // Clear the transcript for the next utterance
        }
      } else if (message.type === 'ai_response') {
         // Now always add the AI response from the SDK
         const aiMessage = {
            content: message.text,
            sender: 'ai',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
         };
         setMessages(prev => [...prev, aiMessage]);
      }
    },
    onError: (error) => {
      console.error('Conversation Error:', error);
      const errorMessage = {
        content: `Error: ${error.message}`,
        sender: 'system',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isError: true
      };
      setMessages(prev => [...prev, errorMessage]);
      
      // Auto-reconnect logic for certain types of errors
      if (error.name === 'NetworkError' || 
          error.message.includes('connection') || 
          error.message.includes('timeout') || 
          error.message.includes('disconnect')) {
        
        const reconnectMessage = {
          content: 'Connection issue detected. Attempting to reconnect...',
          sender: 'system',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, reconnectMessage]);
        
        // Wait a moment before trying to reconnect
        setTimeout(() => {
          if (status === 'disconnected' && currentConversationId) {
            console.log('Attempting to reconnect after error...');
            handleConnectToggle();
          }
        }, 2000);
      }
    }
  });

  // Function to scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Function to associate image context
  const associateImageContext = async (convId, tempId) => {
    if (!convId || !tempId) {
      console.log('Associate context: Missing conversationId or temporaryId');
      return;
    }
    console.log(`Attempting to associate convId: ${convId} with tempId: ${tempId}`);
    setIsLoading(true);
    try {
      const response = await fetch('http://localhost:5001/associate_context', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ conversationId: convId, temporaryId: tempId }),
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const result = await response.json();
      console.log('Association successful:', result);
      setTemporaryId(null); // Clear temp ID after successful association
    } catch (error) {
      console.error('Error associating image context:', error);
      // Handle error appropriately, maybe notify user
    } finally {
      setIsLoading(false);
    }
  };

  // Image handling functions
  const handleImageUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelected = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    // Reset file input immediately
    event.target.value = null; 

    // Store file for potential future use
    setImageFile(file);

    // Create preview and get base64
    const reader = new FileReader();
    reader.onloadend = async () => {
        const base64Image = reader.result;
        setPreviewUrl(base64Image); // Update preview for UI

        // Add system message indicating upload
        const uploadMessage = {
          content: `Uploading ${file.name} for analysis...`,
          sender: 'system',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, uploadMessage]);
        setIsLoading(true);

        // Call backend to upload image and get temporary ID
        try {
          const uploadResponse = await fetch('http://localhost:5001/upload_image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ imageData: base64Image }),
          });
          if (!uploadResponse.ok) {
            throw new Error(`Upload failed: ${uploadResponse.status}`);
          }
          const uploadResult = await uploadResponse.json();
          console.log('Image upload successful, tempId:', uploadResult.temporaryId);
          setTemporaryId(uploadResult.temporaryId);

          // If a conversation is already active, associate immediately
          if (currentConversationId) {
            associateImageContext(currentConversationId, uploadResult.temporaryId);
          }

        } catch (error) {
          console.error('Error uploading image:', error);
          setMessages(prev => [...prev, { content: `Error uploading image: ${error.message}`, sender: 'system', timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), isError: true }]);
          setPreviewUrl(null); // Clear preview on error
        } finally {
          setIsLoading(false);
        }
    };
    reader.onerror = (error) => {
        console.error('FileReader error:', error);
         const errorMessage = {
            content: `Error reading file: ${error.message}`,
            sender: 'system',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            isError: true
          };
        setMessages(prev => [...prev, errorMessage]);
    };
    reader.readAsDataURL(file);
  };

  // Handle connect/disconnect button
  const handleConnectToggle = async () => {
    if (status === 'connected') {
      console.log('Ending session...');
      await endSession();
      setPreviewUrl(null); // Clear image preview on disconnect
      setImageFile(null);
      setCurrentConversationId(null); // Clear conversation ID on disconnect
      setTemporaryId(null); // Also clear temp ID
    } else if (status === 'disconnected') {
      console.log('Attempting to start session...');
      try {
        // 1. Request Microphone Permission
        if (!micPermissionGranted) {
          console.log('Requesting microphone permission...');
          await navigator.mediaDevices.getUserMedia({ audio: true });
          console.log('Microphone permission granted.');
          setMicPermissionGranted(true);
        }
        
        // 2. Start the session
        setIsLoading(true);
        console.log('Starting session with agent r7QeXEUadxgIchsAQYax...');
        const sessionStartResult = await startSession({ 
          agentId: 'r7QeXEUadxgIchsAQYax',
        });
        console.log('Session started, ID:', sessionStartResult);

        // Store the ID - even if it's null/undefined, this will help us debug
        setCurrentConversationId(sessionStartResult);

        // Immediately try to associate context if both IDs exist
        if (temporaryId && sessionStartResult) {
          console.log('Associating image context...');
          await associateImageContext(sessionStartResult, temporaryId);
        } else {
          console.log('No temporaryId found, skipping immediate association.');
        }

      } catch (error) {
        console.error('Failed to start session:', error);
        const errorType = error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError' 
          ? 'Microphone Permission Denied' 
          : 'Failed to Start Session';
        const errorMessage = {
          content: `${errorType}: ${error.message}`,
          sender: 'system',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          isError: true
        };
        setMessages(prev => [...prev, errorMessage]);
        setMicPermissionGranted(false);
      } finally {
        setIsLoading(false);
      }
    }
  };

  // Add a heartbeat effect to check if the connection is still alive
  useEffect(() => {
    let heartbeatInterval;
    
    if (status === 'connected') {
      // Set up a heartbeat to monitor the connection
      heartbeatInterval = setInterval(() => {
        console.log('Connection heartbeat check:', status);
        // This just logs to keep track of connection status
      }, 5000);
    }
    
    return () => {
      if (heartbeatInterval) clearInterval(heartbeatInterval);
    };
  }, [status]);

  return (
    <div className="app-container">
      <h1>ArtSensei Voice & Image Module</h1>
      
      {/* Status display with improved mobile UI */}
      <div className="status-bar">
        <div className="status-indicator">
          <span className={`status-dot ${status === 'connected' ? 'connected' : ''}`}></span>
          <span className="status-text">{status || 'disconnected'}</span>
          {isSpeaking && <span className="speaking-indicator">AI Speaking</span>}
        </div>
        {transcript && (
          <div className="transcript-display">
            {transcript}
          </div>
        )}
      </div>
      
      {/* Image preview */}
      {previewUrl && (
        <div className="image-preview">
          <img src={previewUrl} alt="Uploaded" />
        </div>
      )}
      
      {/* Messages area */}
      <div className="messages-container">
        {messages.length === 0 ? (
          <div className="empty-state">
            <p>Use the buttons below to start a conversation or upload an image.</p>
          </div>
        ) : (
          messages.map((msg, index) => (
            <Message
              key={index}
              content={msg.content}
              sender={msg.sender}
              timestamp={msg.timestamp || new Date().toLocaleTimeString()}
              isError={msg.isError}
            />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
      
      {/* Control bar */}
      <div className="control-bar">
        <button
          className="image-upload-button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading}
          title="Upload Image"
        >
          📷 Upload Image
        </button>
        
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden-input"
          onChange={handleFileSelected}
          style={{ display: 'none' }}
        />
        
        <button
          className={`connect-button ${status === 'connected' ? 'connected' : ''}`}
          onClick={handleConnectToggle}
          disabled={isLoading || status === 'connecting' || status === 'disconnecting'}
        >
          {status === 'connected' ? 'Disconnect' : 'Connect Mic'}
        </button>
        
        {isLoading && <div className="loading-indicator">Loading...</div>}
      </div>
    </div>
  );
}

export default App;
