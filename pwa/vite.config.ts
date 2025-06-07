import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxy API requests to the backend server
      '/api': {
        target: 'http://127.0.0.1:8000', // Your backend server address
        changeOrigin: true, // Needed for virtual hosted sites
        rewrite: path => path.replace(/^\/api/, '/api'), // Optional: if your backend API routes also start with /api
      },
    },
    host: '0.0.0.0',
    port: 3000, // Change to your desired port
  },
});
