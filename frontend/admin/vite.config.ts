import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  base: mode === 'production' ? '/admin/' : '/',
  server: {
    // frontend/theme/ (shared tokens and preset) lives outside this app's root.
    fs: { allow: ['..'] },
    port: 5175,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
}));
