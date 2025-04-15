# Mobile Testing Guide for ArtSensei Image Reader Module

This guide will help you test the application on your mobile device while developing locally.

## Prerequisites

- Your computer and mobile device must be on the same local network
- Both frontend and backend servers must be running
- Your mobile device must have a modern browser (Safari on iOS or Chrome on Android)

## Setup Instructions

### 1. Start the Backend Server

```bash
# From the project root directory
cd /Users/robcolvin/ArtSensei/Image Reader Module
python app.py
```

The Flask server will run on port 5001 and listen on all network interfaces.

### 2. Start the Frontend Server

```bash
# From the frontend directory
cd /Users/robcolvin/ArtSensei/Image Reader Module/frontend
npm run dev
```

The Vite dev server will run on port 5173 and listen on all network interfaces.

### 3. Access from Mobile Device

On your mobile device:

1. Open your browser (Safari on iOS, Chrome on Android)
2. Navigate to: `http://192.168.1.219:5173`
   - This is your computer's local IP address with the frontend port

### 4. Testing Tips

- Allow microphone permissions when prompted
- Test image uploads from your mobile device's camera or photo library
- Test voice interactions to ensure they work properly on mobile
- Check the responsive layout on different screen sizes

## Troubleshooting

### Cannot Connect to Server

- Ensure both devices are on the same WiFi network
- Check if any firewall is blocking the connections
- Try restarting the servers with the correct host configuration

### Microphone Not Working

- Ensure you've granted microphone permissions in your mobile browser
- Some browsers require HTTPS for microphone access - consider setting up a local HTTPS certificate or using a tool like ngrok

### Image Upload Issues

- Check if your mobile browser supports the file input type
- Ensure the camera permissions are granted if accessing the camera directly

## Network Configuration

- Your computer's local IP address: `192.168.1.219`
- Frontend server: `http://192.168.1.219:5174`
- Backend server: `http://192.168.1.219:5001`
