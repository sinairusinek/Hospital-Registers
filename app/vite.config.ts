import path from 'path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Served from https://sinairusinek.github.io/Hospital-Registers/ on Pages,
// from the root in local dev.
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/Hospital-Registers/' : '/',
  server: {
    port: 3000,
    host: '0.0.0.0',
  },
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    }
  }
}));
