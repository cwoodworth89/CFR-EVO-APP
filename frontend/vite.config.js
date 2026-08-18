import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // IMPORTANT: Replace 'coquitlam-fire-trainer' with your EXACT repo name
  base: '/', 
  define: {
    __BUILD_DATE__: JSON.stringify(new Date().toLocaleString('en-CA', { 
      timeZone: 'America/Vancouver', 
      hour12: true 
    }))
  },
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('leaflet') || id.includes('esri-leaflet')) {
              return 'vendor-leaflet';
            }
            if (id.includes('@turf')) {
              return 'vendor-turf';
            }
            if (id.includes('react') || id.includes('react-dom') || id.includes('scheduler')) {
              return 'vendor-react';
            }
            if (id.includes('mqtt') || id.includes('spark-md5') || id.includes('qrcode.react')) {
              return 'vendor-utils';
            }
          }
        }
      }
    }
  }
})