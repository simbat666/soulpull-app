import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Built assets are served by Django under /static/
  base: '/static/',
  build: {
    manifest: true,
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    // When running `npm run dev`, proxy API to Django runserver.
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/tonconnect-manifest.json': 'http://127.0.0.1:8000',
    },
  },
})
