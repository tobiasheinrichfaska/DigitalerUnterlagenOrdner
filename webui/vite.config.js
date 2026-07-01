import { cpSync, createReadStream, existsSync } from 'node:fs'
import { resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// PDF.js v6 keeps its image decoders + font/cmap data OUT of the main bundle: JBIG2/JPEG2000
// (the encodings DATEV scans use) decode via wasm/openjpeg.wasm + wasm/jbig2.wasm, and CJK /
// substitute fonts need cmaps + standard_fonts. Without these served, a scanned PDF parses
// (page count is right) but every page renders BLANK. The worker is wired via ?url; these are
// whole directories, so copy them next to the build (prod) and serve them from node_modules in
// dev. main.js points getDocument at /pdfjs/* (see PDFJS_ASSET_BASE there).
const PDFJS_ASSET_DIRS = ['cmaps', 'standard_fonts', 'wasm', 'iccs']
function pdfjsAssets() {
  const srcRoot = fileURLToPath(new URL('./node_modules/pdfjs-dist', import.meta.url))
  return {
    name: 'pdfjs-assets',
    // dev: serve /pdfjs/<dir>/<file> straight from node_modules/pdfjs-dist
    configureServer(server) {
      server.middlewares.use('/pdfjs', (req, res, next) => {
        const rel = decodeURIComponent((req.url || '').split('?')[0]).replace(/^\/+/, '')
        const file = resolve(srcRoot, rel)
        const allowed = PDFJS_ASSET_DIRS.some((d) => rel.startsWith(`${d}/`))
        if (!allowed || !file.startsWith(srcRoot + sep) || !existsSync(file)) return next()
        if (file.endsWith('.wasm')) res.setHeader('Content-Type', 'application/wasm')
        createReadStream(file).pipe(res)
      })
    },
    // build: copy the dirs into dist/pdfjs/ so the packaged app serves them
    closeBundle() {
      for (const d of PDFJS_ASSET_DIRS) {
        const s = resolve(srcRoot, d)
        if (existsSync(s)) cpSync(s, fileURLToPath(new URL(`./dist/pdfjs/${d}`, import.meta.url)), { recursive: true })
      }
    },
  }
}

// base: './' makes built asset paths relative, so the bundle loads from
// file:// inside the pywebview window (prod). Dev uses the Vite server.
export default defineConfig({
  base: './',
  plugins: [react(), pdfjsAssets()],
  build: {
    // Two front-end surfaces share one app (see docs/pdf-viewer-surface.md):
    // index.html = organizer, pdf-tool.html = PDF-Tool (PDF.js).
    rollupOptions: {
      input: {
        main: fileURLToPath(new URL('./index.html', import.meta.url)),
        pdftool: fileURLToPath(new URL('./pdf-tool.html', import.meta.url)),
      },
    },
  },
  test: {
    // core.js touches window + the pywebviewready event; jsdom provides them.
    environment: 'jsdom',
    setupFiles: './src/test-setup.js',
    // Only the jsdom unit/component tests under src/. The Playwright e2e specs live
    // in e2e/ (real Chromium, run via `npm run test:e2e`) — keep them out of Vitest,
    // whose default glob would otherwise pick up their *.spec.js files.
    include: ['src/**/*.{test,spec}.{js,jsx}'],
    // vitest 4.1.8's default 'forks'/'threads' pools hit a hook-context bug on this
    // toolchain (vite 8 / node 22+24): every file dies with "failed to find the
    // current suite" (0 tests). 'vmThreads' runs the suites; 'globals' lets
    // @testing-library/react register its cleanup() in-test-context (the setup-file
    // afterEach doesn't fire under the broken hook path). Together → 281 green.
    // Revisit (drop both) once vitest ships a fix. See reports/2026-06-13_18-22-24.
    pool: 'vmThreads',
    globals: true,
  },
})
