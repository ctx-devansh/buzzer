import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  base: mode === 'production' ? '/host/' : '/',
  server: {
    // frontend/theme/ (shared tokens and preset) lives outside this app's root.
    fs: { allow: ['..'] },
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/socket.io': { target: 'http://localhost:8000', ws: true, changeOrigin: true },
    },
  },
}));
