import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base: './' makes built asset paths relative, so the bundle loads from
// file:// inside the pywebview window (prod). Dev uses the Vite server.
export default defineConfig({
  base: './',
  plugins: [react()],
  test: {
    // core.js touches window + the pywebviewready event; jsdom provides them.
    environment: 'jsdom',
    setupFiles: './src/test-setup.js',
  },
})
