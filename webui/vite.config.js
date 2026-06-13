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
    // vitest 4.1.8's default 'forks'/'threads' pools hit a hook-context bug on this
    // toolchain (vite 8 / node 22+24): every file dies with "failed to find the
    // current suite" (0 tests). 'vmThreads' runs the suites; 'globals' lets
    // @testing-library/react register its cleanup() in-test-context (the setup-file
    // afterEach doesn't fire under the broken hook path). Together → 216 green.
    // Revisit (drop both) once vitest ships a fix. See reports/2026-06-13_18-22-24.
    pool: 'vmThreads',
    globals: true,
  },
})
