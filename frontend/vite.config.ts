import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'
import { frontmanPlugin } from '@frontman-ai/vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    frontmanPlugin({ host: 'api.frontman.sh' }),react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
