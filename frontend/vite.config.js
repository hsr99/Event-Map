import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  // One .env at the repo root serves both the backend and the frontend.
  envDir: '..',
  plugins: [
    react(),
    tailwindcss(),
  ],
})