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
      update_pdf_bytes: (s) => { calls.push(['update_pdf_bytes', s]); return { ok: true } },  // session-only bake
      save_pdf_bytes: (s) => { calls.push(['save_pdf_bytes', s]); return window.__localResult || { ok: true, local_saved: 'C:/x/1085411.pdf', local_kind: 'pdf' } },
      save_to_datev: (s) => { calls.push(['save_to_datev', s]); return window.__sbResult || { ok: true, verdict: 'ok', local_saved: 'C:/x/1085411.pdf' } },
      datev_file: (s, c, num) => { calls.push(['datev_file', s, num]); return window.__fileResult || { ok: true, provenance: { doc_guid: 'g', file_id: 1 }, local_saved: 'C:/x/1085411.pdf' } },
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
    // the edit was baked into the SESSION ONLY (update_pdf_bytes) BEFORE the guarded write-back
    // (save_to_datev) — the on-disk .pdf is written only after a successful verdict
    const calls = await page.evaluate(() => window.__calls.map((c) => c[0]))
    expect(calls).toEqual(['update_pdf_bytes', 'save_to_datev'])
  })

  test('a refused write-back shows the LOCALIZED conflict AND falls back to a local save', async ({ page }) => {
    // Regression (round 10): a guard verdict must show its localized German message (datevVerdictKey),
    // NOT the raw internal code 'conflict_changed' — mirrors the organizer (App.jsx).
    await installBridge(page, { connected: true, datevMode: true })
    await page.addInitScript(() => { window.__sbResult = { ok: false, verdict: 'conflict_changed' } })
    await page.goto('/pdf-tool.html')
    const btn = page.locator('#btn-datev')
    await expect(btn).toBeVisible({ timeout: 20000 })
    await btn.click()
    const status = page.locator('#pdf-status')
    await expect(status).toHaveText(/zwischenzeitlich geändert/, { timeout: 20000 })  // localized message
    await expect(status).not.toHaveText(/conflict_changed/)  // never the raw code
    await expect(status).toHaveText(/lokal gesichert/)        // the edit was NOT lost
    await expect(status).not.toHaveText(/zurückgeschrieben ✓/)
    // session bake → guarded write-back refused → local save_pdf_bytes fallback persists the edit
    const calls = await page.evaluate(() => window.__calls.map((c) => c[0]))
    expect(calls).toEqual(['update_pdf_bytes', 'save_to_datev', 'save_pdf_bytes'])
  })

  test('a refused write-back whose local fallback ALSO fails surfaces the local error, not false success', async ({ page }) => {
    // Regression (round 9): save_pdf_bytes returns ok:true once the session bake succeeds even if
    // the on-disk write inside _datev_local_persist failed (local_error set, local_saved null).
    // The fallback must NOT claim "lokal gesichert" then — it must surface the disk error so the
    // user never closes the window believing a lost edit is safe.
    await installBridge(page, { connected: true, datevMode: true })
    await page.addInitScript(() => {
      window.__sbResult = { ok: false, verdict: 'conflict_changed' }
      window.__localResult = { ok: true, local_saved: null, local_error: 'Datenträger voll', local_kind: 'pdf' }
    })
    await page.goto('/pdf-tool.html')
    const btn = page.locator('#btn-datev')
    await expect(btn).toBeVisible({ timeout: 20000 })
    await btn.click()
    const status = page.locator('#pdf-status')
    await expect(status).toHaveText(/zwischenzeitlich geändert/, { timeout: 20000 })  // localized verdict
    await expect(status).toHaveText(/lokal: Datenträger voll/)   // the disk failure is surfaced
    await expect(status).not.toHaveText(/lokal gesichert/)       // NOT a false success
    const calls = await page.evaluate(() => window.__calls.map((c) => c[0]))
    expect(calls).toEqual(['update_pdf_bytes', 'save_to_datev', 'save_pdf_bytes'])
  })

  test('a declined write-back is NOT persisted locally (no save_pdf_bytes call)', async ({ page }) => {
    // Coverage (round 10, Low): the user said no in the native confirm → status says "Abgebrochen"
    // and the edit stays session-only — save_pdf_bytes must NOT be called.
    await installBridge(page, { connected: true, datevMode: true })
    await page.addInitScript(() => { window.__sbResult = { ok: false, verdict: 'declined' } })
    await page.goto('/pdf-tool.html')
    const btn = page.locator('#btn-datev')
    await expect(btn).toBeVisible({ timeout: 20000 })
    await btn.click()
    await expect(page.locator('#pdf-status')).toHaveText(/Abgebrochen/, { timeout: 20000 })
    const calls = await page.evaluate(() => window.__calls.map((c) => c[0]))
    expect(calls).toEqual(['update_pdf_bytes', 'save_to_datev'])  // no save_pdf_bytes
  })

  test('an error verdict shows the raw cause prefixed DATEV and still saves locally', async ({ page }) => {
    // Coverage (round 11, Low): the verdict:'error' branch (a mid-write network/HTTP failure)
    // shows "DATEV: <res.error>" verbatim — NOT a guard message — and the fallback save still runs.
    await installBridge(page, { connected: true, datevMode: true })
    await page.addInitScript(() => { window.__sbResult = { ok: false, verdict: 'error', error: 'Netzwerk nicht erreichbar' } })
    await page.goto('/pdf-tool.html')
    const btn = page.locator('#btn-datev')
    await expect(btn).toBeVisible({ timeout: 20000 })
    await btn.click()
    const status = page.locator('#pdf-status')
    await expect(status).toHaveText(/DATEV: Netzwerk nicht erreichbar/, { timeout: 20000 })  // raw cause, prefixed
    await expect(status).toHaveText(/lokal gesichert/)  // the edit was NOT lost
    const calls = await page.evaluate(() => window.__calls.map((c) => c[0]))
    expect(calls).toEqual(['update_pdf_bytes', 'save_to_datev', 'save_pdf_bytes'])
  })

  test('a not-connected pdf shows file-anew; click files via datev_file with the Mandant', async ({ page }) => {
    await installBridge(page, { connected: false, datevMode: true })
    page.on('dialog', (d) => d.accept('10001'))  // the Mandant prompt
    await page.goto('/pdf-tool.html')
    const btn = page.locator('#btn-datev')
    await expect(btn).toBeVisible({ timeout: 20000 })
    await expect(btn).toHaveText(/Nach DATEV ablegen/)
    await btn.click()
    // names the saved file (format-clarity) and bakes session-only first
    await expect(page.locator('#pdf-status'))
      .toHaveText(/In DATEV abgelegt ✓ · 1085411\.pdf/, { timeout: 20000 })
    const calls = await page.evaluate(() => window.__calls.map((c) => c[0]))
    expect(calls).toEqual(['update_pdf_bytes', 'datev_file'])
    const filed = await page.evaluate(() => window.__calls.find((c) => c[0] === 'datev_file'))
    expect(filed && filed[2]).toBe('10001')
  })

  test('file-anew that succeeds in DATEV but fails the local save surfaces the local error', async ({ page }) => {
    // Regression (round 10): datev_file merges {local_error, local_saved:null} when the parallel
    // local write fails. datevFileNew must surface it, never a bare "In DATEV abgelegt ✓" — else
    // the on-disk .pdf is silently stale vs DATEV. Mirrors App.jsx fileToDatev.
    await installBridge(page, { connected: false, datevMode: true })
    await page.addInitScript(() => {
      window.__fileResult = { ok: true, provenance: { doc_guid: 'g', file_id: 1 }, local_saved: null, local_error: 'Kein lokaler Speicherort gebunden' }
    })
    page.on('dialog', (d) => d.accept('10001'))
    await page.goto('/pdf-tool.html')
    const btn = page.locator('#btn-datev')
    await expect(btn).toBeVisible({ timeout: 20000 })
    await btn.click()
    const status = page.locator('#pdf-status')
    await expect(status).toHaveText(/In DATEV abgelegt ✓/, { timeout: 20000 })
    await expect(status).toHaveText(/lokal: Kein lokaler Speicherort gebunden/)  // the disk failure is surfaced
  })

  test('file-anew that DATEV rejects surfaces the error', async ({ page }) => {
    // Coverage (round 10, Low): the datev_file error branch in datevFileNew.
    await installBridge(page, { connected: false, datevMode: true })
    await page.addInitScript(() => { window.__fileResult = { ok: false, error: 'Mandant 999 unbekannt' } })
    page.on('dialog', (d) => d.accept('999'))
    await page.goto('/pdf-tool.html')
    const btn = page.locator('#btn-datev')
    await expect(btn).toBeVisible({ timeout: 20000 })
    await btn.click()
    await expect(page.locator('#pdf-status')).toHaveText(/DATEV: Mandant 999 unbekannt/, { timeout: 20000 })
  })

  test('DATEV mode off shows no DATEV button', async ({ page }) => {
    await installBridge(page, { connected: true, datevMode: false })
    await page.goto('/pdf-tool.html')
    await expect(page.locator('.textLayer')).toContainText('SPIKE', { timeout: 20000 })  // doc loaded
    await expect(page.locator('#btn-datev')).toBeHidden()
  })
})
