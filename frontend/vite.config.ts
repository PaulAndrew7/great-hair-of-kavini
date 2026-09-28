import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The API runs on 8100 (8000 is commonly taken). Override with PRIOR_API=http://host:port.
const api = process.env.PRIOR_API ?? 'http://127.0.0.1:8100'
const proxy = { '/api': { target: api, changeOrigin: true, rewrite: (p: string) => p.replace(/^\/api/, '') } }

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true, proxy },
  preview: { port: 4173, proxy },
})
