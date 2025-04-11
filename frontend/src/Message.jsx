import React from 'react';

// Simple Message component for displaying messages
const Message = ({ content, sender, timestamp, isError }) => {
  return (
    <div className={`message ${sender === 'ai' ? 'ai-message' : 'user-message'} ${isError ? 'error-message' : ''}`}>
      <div className="message-content">{content}</div>
      <div className="message-info">
        <span className="message-sender">{sender === 'ai' ? 'AI' : sender === 'system' ? 'System' : 'You'}</span>
        <span className="message-time">{timestamp}</span>
      </div>
    </div>
  );
};

export default Message;
