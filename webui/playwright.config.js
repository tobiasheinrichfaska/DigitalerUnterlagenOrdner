// Playwright e2e config. These tests run the REAL Vite build in REAL Chromium to
// cover what jsdom can't see: layout-dependent scroll virtualization (Preview.jsx)
// and HTML5 drag-and-drop geometry (Tree.jsx). The Python backend is absent in a
// browser, so each test injects a stub `window.pywebview.api` (see e2e/bridge.js).
//
// Run: npm run test:e2e   (first time: npx playwright install chromium)
import { defineConfig, devices } from '@playwright/test'

const PORT = 5178 // workspace-standard web dev port

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npm run dev -- --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
