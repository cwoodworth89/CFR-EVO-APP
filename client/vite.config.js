import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // IMPORTANT: Replace 'coquitlam-fire-trainer' with your EXACT repo name
  base: '/coquitlam-fire-trainer/', 
  define: {
    __BUILD_DATE__: JSON.stringify(new Date().toLocaleString('en-CA', { 
      timeZone: 'America/Vancouver', 
      hour12: true 
    }))
  }
})