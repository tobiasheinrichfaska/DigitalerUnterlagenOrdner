// Content-Security-Policy smoke against the PRODUCTION build (`vite preview`, see
// playwright.csp.config.js). Asserts (1) both built pages carry the CSP meta, (2) the
// organizer and the PDF-Tool (with a real PDF through the bridge stub) load with ZERO CSP
// violations, (3) the policy is really enforced (an injected inline script is blocked).
// Limit: this is Chromium, not the WebView2 host on Windows.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { test, expect } from '@playwright/test'
import { installBridge } from './bridge.js'

const dist = (f) => readFileSync(fileURLToPath(new URL(`../dist/${f}`, import.meta.url)), 'utf8')

// Smallest valid one-page PDF with a text line (offsets computed, so xref is exact).
function tinyPdf() {
  const stream = 'BT /F1 24 Tf 72 700 Td (CSP-SMOKE-TEXT) Tj ET'
  const objs = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
  ]
  let out = '%PDF-1.4\n'
  const offs = []
  objs.forEach((o, i) => { offs.push(out.length); out += `${i + 1} 0 obj\n${o}\nendobj\n` })
  const xref = out.length
  out += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`
  offs.forEach((o) => { out += `${String(o).padStart(10, '0')} 00000 n \n` })
  out += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`
  return Buffer.from(out, 'latin1')
}

function watchViolations(page) {
  const found = []
  page.on('console', (m) => {
    const t = m.text()
    if (/Content Security Policy|Refused to (load|execute|apply|connect|create)/i.test(t)) found.push(t)
  })
  page.on('pageerror', (e) => { if (/Content Security Policy/i.test(String(e))) found.push(String(e)) })
  return found
}

test.describe('Content-Security-Policy (production build)', () => {
  for (const f of ['index.html', 'pdf-tool.html']) {
    test(`dist/${f} carries the CSP meta`, () => {
      const html = dist(f)
      const m = html.match(/<meta http-equiv="Content-Security-Policy" content="([^"]+)"/)
      expect(m, 'CSP meta missing').not.toBeNull()
      for (const d of ["default-src 'self'", "script-src 'self' 'wasm-unsafe-eval'", "object-src 'none'", "base-uri 'none'", "form-action 'none'"]) {
        expect(m[1]).toContain(d)
      }
      expect(m[1]).not.toMatch(/script-src[^;]*'unsafe-inline'/)
    })
  }

  test('organizer loads without CSP violations and blocks injected inline script', async ({ page }) => {
    const violations = watchViolations(page)
    await installBridge(page, { pageCount: 3 })
    await page.goto('/index.html')
    await expect(page.getByText('alpha').first()).toBeVisible({ timeout: 20000 })
    const ran = await page.evaluate(() => {
      const s = document.createElement('script')
      s.textContent = 'window.__injected = true'
      document.head.appendChild(s)
      return !!window.__injected
    })
    expect(ran, 'inline script must be blocked by the CSP').toBe(false)
    // the deliberate inline-script probe above is the only violation allowed
    expect(violations.filter((v) => !/inline script/i.test(v)), violations.join('\n')).toEqual([])
  })

  test('PDF-Tool renders a real PDF (bridge stub) without CSP violations', async ({ page }) => {
    const violations = watchViolations(page)
    const errors = []
    page.on('pageerror', (e) => errors.push(String(e)))
    const b64 = tinyPdf().toString('base64')
    await page.addInitScript((data) => {
      const base = {
        config: () => ({ ok: true, dev: false, startup_kind: 'node', startup_session: 's' }),
        get_pdf_bytes: () => ({ ok: true, data_b64: data }),
      }
      window.pywebview = {
        api: new Proxy({}, {
          get(_t, prop) {
            if (typeof prop !== 'string' || prop === 'then') return undefined
            return (...a) => (base[prop] || (() => ({ ok: true })))(...a)
          },
        }),
      }
    }, b64)
    await page.goto('/pdf-tool.html')
    await expect(page.locator('.textLayer')).toContainText('CSP-SMOKE-TEXT', { timeout: 20000 })
    expect(violations, violations.join('\n')).toEqual([])
    expect(errors, errors.join('\n')).toEqual([])
  })
})
