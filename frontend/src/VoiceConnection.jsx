import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useConversation } from '@11labs/react';

// This custom hook is responsible just for managing the WebSocket connection
// It provides stable connection management that won't be affected by parent component re-renders
function useVoiceConnection({ 
  onConnectionChange, 
  onMessageReceived, 
  onError,
  debugMode = false
}) {
  // Connection state
  const [connectionState, setConnectionState] = useState('disconnected');
  const [conversationId, setConversationId] = useState(null);
  const [micPermission, setMicPermission] = useState('unknown');
  
  // Keep track of component mounting state
  const isMounted = useRef(true);
  const connectionAttemptCount = useRef(0);
  
  // Backend URL
  const backendUrl = 'http://localhost:5003';

  // Initialize the hook with callbacks
  const conversation = useConversation({
    autoPlayAudio: true,
    enableAudio: true,
    
    onConnect: () => {
      console.log('Conversation connected.');
      if (isMounted.current) {
        setConnectionState('connected');
        onConnectionChange?.('connected');
      }
    },
    
    onDisconnect: () => {
      console.log('Conversation disconnected.');
      if (isMounted.current) {
        setConnectionState('disconnected');
        setConversationId(null);
        onConnectionChange?.('disconnected');
      }
    },
    
    onMessage: (message) => {
      console.log('Received message:', message);
      if (!isMounted.current) return;
      
      // Forward the message to parent component
      onMessageReceived?.(message);
      
      // Update connection state for specific messages
      if (message?.type === 'connecting') {
        setConnectionState('establishing');
        onConnectionChange?.('establishing');
      } else if (message?.type === 'connected') {
        setConnectionState('active');
        onConnectionChange?.('active');
      }
    },
    
    onError: (err) => {
      console.error('Conversation error:', err);
      if (isMounted.current) {
        setConnectionState('error');
        onConnectionChange?.('error');
        onError?.(err.message || 'Unknown error');
      }
    },
  });

  // Function to fetch the signed URL from backend
  const getSignedUrl = async () => {
    try {
      console.log(`Fetching signed URL from ${backendUrl}/api/elevenlabs/get-signed-url`);
      const response = await fetch(`${backendUrl}/api/elevenlabs/get-signed-url`); 
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(`Failed to fetch signed URL: ${response.status} ${errorData.error || errorData.detail}`);
      }
      
      const data = await response.json();
      if (!data.signedUrl) {
        throw new Error('Signed URL not found in backend response.');
      }
      
      // Add detailed debugging of the signed URL format
      console.log("DEBUG - Received Signed URL:", data.signedUrl);
      console.log("DEBUG - URL Components:", {
        protocol: data.signedUrl.split("://")[0],
        host: data.signedUrl.split("://")[1]?.split("/")[0],
        path: "/" + (data.signedUrl.split("://")[1]?.split("/").slice(1).join("/") || ""),
        params: data.signedUrl.includes("?") ? data.signedUrl.split("?")[1] : "none"
      });
      
      console.log("Successfully obtained signed URL.");
      return data.signedUrl;
    } catch (fetchError) {
      console.error('Error fetching signed URL:', fetchError);
      onError?.(`Error fetching signed URL: ${fetchError.message}`);
      throw fetchError;
    }
  };

  // Function to check microphone permission
  const checkMicrophonePermission = useCallback(async () => {
    try {
      console.log('Requesting microphone permissions...');
      await navigator.mediaDevices.getUserMedia({ audio: true });
      console.log("Microphone access granted.");
      setMicPermission('granted');
      return true;
    } catch (err) {
      console.error('Microphone permission error:', err);
      setMicPermission('denied');
      onError?.(`Microphone access denied: ${err.message}`);
      return false;
    }
  }, [onError]);

  // Function to start conversation
  const startConversation = useCallback(async () => {
    // Guard against redundant connections
    if (conversation.status === 'connected' || connectionState === 'connecting') {
      console.log('Already connected or connecting, aborting start.');
      return;
    }
    
    connectionAttemptCount.current++;
    const currentAttempt = connectionAttemptCount.current;
    
    console.log(`Attempt #${currentAttempt}: Starting conversation...`);
    setConnectionState('initializing');
    onConnectionChange?.('initializing');
    
    try {
      // Check mic permissions first
      const micAllowed = await checkMicrophonePermission();
      if (!micAllowed || currentAttempt !== connectionAttemptCount.current) {
        console.log(`Attempt #${currentAttempt} aborted: mic permission failed or new attempt started`);
        return;
      }

      // Get the signed URL
      setConnectionState('fetching_url');
      onConnectionChange?.('fetching_url');
      const signedUrl = await getSignedUrl();
      
      // Check if a newer connection attempt has started
      if (currentAttempt !== connectionAttemptCount.current) {
        console.log(`Attempt #${currentAttempt} aborted: new attempt started`);
        return;
      }

      // Start WebSocket session
      setConnectionState('connecting');
      onConnectionChange?.('connecting');
      
      // Extract agent ID from URL
      const urlParams = new URLSearchParams(signedUrl.split('?')[1]);
      const agentId = urlParams.get('agent_id');
      
      // Start session
      const startParams = { 
        url: signedUrl,
        agentId: agentId || 'r7QeXEUadxgIchsAQYax' // Fallback to hardcoded ID if extraction fails
      };
      
      console.log(`Attempt #${currentAttempt}: Starting session with params:`, debugMode ? startParams : 'hidden');
      const id = await conversation.startSession(startParams);
      
      if (currentAttempt !== connectionAttemptCount.current) {
        console.log(`Attempt #${currentAttempt} successful but outdated - cleaning up`);
        conversation.endSession().catch(e => console.error("Error ending outdated session:", e));
        return;
      }
      
      console.log(`Attempt #${currentAttempt}: Conversation started with ID:`, id);
      setConversationId(id);
      setConnectionState('established');
      onConnectionChange?.('established');
      
    } catch (error) {
      if (currentAttempt === connectionAttemptCount.current && isMounted.current) {
        console.error(`Attempt #${currentAttempt} failed:`, error);
        setConnectionState('error');
        onConnectionChange?.('error');
        onError?.(error.message || 'Unknown connection error');
      }
    }
  }, [conversation, connectionState, checkMicrophonePermission, onConnectionChange, onError, debugMode]);

  // Function to stop conversation
  const stopConversation = useCallback(async () => {
    if (conversation.status !== 'connected') {
      console.log('Not connected, nothing to stop.');
      return;
    }
    
    console.log('Stopping conversation...');
    setConnectionState('disconnecting');
    onConnectionChange?.('disconnecting');
    
    try {
      await conversation.endSession();
      console.log('Conversation ended successfully.');
      setConnectionState('disconnected');
      onConnectionChange?.('disconnected');
    } catch (error) {
      console.error('Error stopping conversation:', error);
      setConnectionState('error');
      onConnectionChange?.('error');
      onError?.(error.message || 'Error stopping conversation');
    }
  }, [conversation, onConnectionChange, onError]);

  // Track mounted state
  useEffect(() => {
    isMounted.current = true;
    console.log('VoiceConnection component mounted');
    
    return () => {
      console.log('VoiceConnection component unmounting - this should not happen during normal operation');
      isMounted.current = false;
      
      // Cleanup any active connection
      if (conversation.status === 'connected' || conversation.status === 'connecting') {
        console.log('Cleaning up active connection on unmount');
        conversation.endSession().catch(err => 
          console.error("Error during unmount cleanup:", err)
        );
      }
    };
  }, [conversation]);

  // Expose the connection control functions and state
  return {
    conversation,
    connectionState,
    micPermission,
    conversationId,
    startConversation,
    stopConversation
  };
}

export default useVoiceConnection;
