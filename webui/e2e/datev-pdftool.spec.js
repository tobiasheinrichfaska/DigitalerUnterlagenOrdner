// The PDF-Tool's DATEV wiring (vanilla-JS DOM) can only be exercised end-to-end: inject a stub
// pywebview bridge BEFORE the page loads so the 'bridge' (.pdf) path runs in real Chromium with
// no Python host. get_pdf_bytes serves the sample form PDF so PDF.js loads and setupDatevUi runs.
import { test, expect } from '@playwright/test'

function installBridge(page, { connected, datevMode }) {
  return page.addInitScript(({ connected, datevMode }) => {
    const calls = []
    window.__calls = calls
    const toB64 = (bytes) => {
      let s = ''
      for (let i = 0; i < bytes.length; i += 1) s += String.fromCharCode(bytes[i])
      return btoa(s)
    }
    const api = {
      config: () => ({ ok: true, dev: false, default_dpi: 150, startup_kind: 'pdf', startup_path: 'C:/x.pdf' }),
      open: () => ({ ok: true, session: 's1', datev: { connected, source_name: '1085411.pdf' } }),
      get_pdf_bytes: async () => {
        const buf = await (await fetch('/spike-form.pdf')).arrayBuffer()
        return { ok: true, data_b64: toB64(new Uint8Array(buf)) }
      },
      datev_status: () => ({ ok: true, datev_mode: datevMode, connected }),
      save_pdf_bytes: (s) => { calls.push(['save_pdf_bytes', s]); return { ok: true, local_saved: 'C:/x/1085411.pdf', local_kind: 'pdf' } },
      save_to_datev: (s) => { calls.push(['save_to_datev', s]); return { ok: true, verdict: 'ok', local_saved: 'C:/x/1085411.pdf' } },
      datev_file: (s, c, num) => { calls.push(['datev_file', s, num]); return { ok: true, provenance: { doc_guid: 'g', file_id: 1 }, local_saved: 'C:/x/Beleg.belegtool' } },
    }
    window.pywebview = { api }
  }, { connected, datevMode })
}

test.describe('PDF-Tool DATEV', () => {
  test('a connected checkout shows write-back; click bakes edits THEN writes back', async ({ page }) => {
    await installBridge(page, { connected: true, datevMode: true })
    await page.goto('/pdf-tool.html')
    const btn = page.locator('#btn-datev')
    await expect(btn).toBeVisible({ timeout: 20000 })
    await expect(btn).toHaveText(/Nach DATEV zurückschreiben/)
    await btn.click()
    await expect(page.locator('#pdf-status'))
      .toHaveText(/Nach DATEV zurückgeschrieben ✓ · 1085411\.pdf/, { timeout: 20000 })
    // the edit was baked (save_pdf_bytes) BEFORE the write-back (save_to_datev)
    const calls = await page.evaluate(() => window.__calls.map((c) => c[0]))
    expect(calls).toEqual(['save_pdf_bytes', 'save_to_datev'])
  })

  test('a not-connected pdf shows file-anew; click files via datev_file with the Mandant', async ({ page }) => {
    await installBridge(page, { connected: false, datevMode: true })
    page.on('dialog', (d) => d.accept('10001'))  // the Mandant prompt
    await page.goto('/pdf-tool.html')
    const btn = page.locator('#btn-datev')
    await expect(btn).toBeVisible({ timeout: 20000 })
    await expect(btn).toHaveText(/Nach DATEV ablegen/)
    await btn.click()
    await expect(page.locator('#pdf-status')).toHaveText(/In DATEV abgelegt ✓/, { timeout: 20000 })
    const filed = await page.evaluate(() => window.__calls.find((c) => c[0] === 'datev_file'))
    expect(filed && filed[2]).toBe('10001')
  })

  test('DATEV mode off shows no DATEV button', async ({ page }) => {
    await installBridge(page, { connected: true, datevMode: false })
    await page.goto('/pdf-tool.html')
    await expect(page.locator('.textLayer')).toContainText('SPIKE', { timeout: 20000 })  // doc loaded
    await expect(page.locator('#btn-datev')).toBeHidden()
  })
})
