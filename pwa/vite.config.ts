import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Get backend URL from environment variable, fallback to default
const backendUrl = process.env.VITE_API_URL || 'http://127.0.0.1:8000';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxy API requests to the backend server
      '/api': {
        target: backendUrl, // Backend server address from environment
        changeOrigin: true, // Needed for virtual hosted sites
        rewrite: path => path.replace(/^\/api/, '/api'), // Optional: if your backend API routes also start with /api
      },
    },
    host: '0.0.0.0',
    port: parseInt(process.env.FRONTEND_PORT || '3000'), // Port from environment or default
  },
});
