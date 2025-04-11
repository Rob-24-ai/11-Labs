import React, { useState, useRef, useEffect } from 'react';
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
  
  // Refs
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  
  // Initialize ElevenLabs conversation hook
  const {
    startSession,
    endSession,
    status, // 'connected' or 'disconnected'
    isSpeaking // boolean
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
    }
  });

  // Function to scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

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

        // --- SEND IMAGE DIRECTLY TO BACKEND --- 
        console.log('Sending image directly to backend for analysis.');
        const payload = {
            model: 'gpt-4o', // Or your desired model
            messages: [
              {
                role: 'user',
                content: [
                  { type: 'text', text: 'Describe this image objectively in one or two sentences.' }, // Fixed prompt
                  { 
                    type: 'image_url',
                    image_url: { url: base64Image } 
                  }
                ]
              }
            ]
        };

        try {
            const response = await fetch('http://localhost:5001/v1/chat/completions', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json'
              },
              body: JSON.stringify(payload)
            });

            if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            const aiText = result?.choices?.[0]?.message?.content || 'No description received.';
            
            // Add AI description to chat
            const descriptionMessage = {
              content: `Image Analysis: ${aiText}`,
              sender: 'ai', // Or 'system'
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            };
            setMessages(prev => [...prev, descriptionMessage]);

            // --- REGISTER CONTEXT WITH BACKEND --- 
            try {
                console.log('Registering image context with backend...');
                const contextResponse = await fetch('http://localhost:5001/register_image_context', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ description: aiText }),
                });
                if (!contextResponse.ok) {
                     const errorText = await contextResponse.text();
                     throw new Error(`Failed to register context: ${contextResponse.status} ${errorText}`);
                }
                console.log('Image context registered successfully.');
                // Add a system message (optional)
                const contextRegMessage = {
                  content: `Context registered for image: ${file.name}`,
                  sender: 'system',
                  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                };
                setMessages(prev => [...prev, contextRegMessage]);

            } catch (contextError) {
                 console.error('Error registering image context:', contextError);
                 const errorContextMessage = {
                    content: `Error registering context: ${contextError.message}`,
                    sender: 'system',
                    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                    isError: true
                  };
                setMessages(prev => [...prev, errorContextMessage]);
            }
            // --- END CONTEXT REGISTRATION ---

        } catch (error) {
            console.error('Direct image analysis error:', error);
            const errorMessage = {
              content: `Error analyzing image: ${error.message}`,
              sender: 'system',
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              isError: true
            };
            setMessages(prev => [...prev, errorMessage]);
        } finally {
            setIsLoading(false);
            // Don't clear previewUrl here, keep it visible
        }
        // --- END DIRECT IMAGE SEND ---
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
        const conversationId = await startSession({ 
          agentId: 'r7QeXEUadxgIchsAQYax',
        });
        console.log('Session started, ID:', conversationId);
        setTranscript('');
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

  return (
    <div className="app-container">
      <h1>ArtSensei Voice & Image Module</h1>
      
      {/* Status display */}
      <div className="status-bar">
        <div className="status-indicator">
          Status: {status || 'disconnected'} | AI Speaking: {isSpeaking ? 'Yes' : 'No'}
        </div>
        {transcript && (
          <div className="transcript-display">
            Live Transcript: {transcript}
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
