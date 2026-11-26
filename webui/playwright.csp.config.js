// CSP smoke: runs against the PRODUCTION build served by `vite preview` (the dev server
// has no CSP). Run: npm run test:csp  (builds first). Optional PW_CHROMIUM=<path> picks a browser.
import { defineConfig, devices } from '@playwright/test'

const PORT = 5179

export default defineConfig({
  testDir: './e2e',
  testMatch: 'csp.spec.js',
  reporter: 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    launchOptions: process.env.PW_CHROMIUM
      ? { executablePath: process.env.PW_CHROMIUM, args: ['--no-sandbox'] }
      : {},
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npm run preview -- --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
