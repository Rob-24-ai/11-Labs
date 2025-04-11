import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: { 
    host: '0.0.0.0', // Allow access from local network
    cors: true, // Enable CORS for all origins
    allowedHosts: ['3d8f-2600-6c65-727f-8221-523-7b63-31ae-7078.ngrok-free.app', '.ngrok-free.app'], // Allow ngrok domains
    proxy: {
      '/v1': {
        target: 'http://localhost:5000', 
        changeOrigin: true, 
        // rewrite: (path) => path.replace(/^/api/, '') 
      }
    }
  }
})
