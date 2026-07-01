// The PDF-Tool's DATEV wiring (vanilla-JS DOM) can only be exercised end-to-end: inject a stub
// pywebview bridge BEFORE the page loads so the 'bridge' (.pdf) path runs in real Chromium with
// no Python host. get_pdf_bytes serves the sample form PDF so PDF.js loads and setupDatevUi runs.
import { test, expect } from '@playwright/test'

function installBridge(page, { connected, datevMode, serviceConnected = true, kind = 'pdf' }) {
  return page.addInitScript(({ connected, datevMode, serviceConnected, kind }) => {
    const calls = []
    window.__calls = calls
    const toB64 = (bytes) => {
      let s = ''
      for (let i = 0; i < bytes.length; i += 1) s += String.fromCharCode(bytes[i])
      return btoa(s)
    }
    // kind 'pdf' → a directly-opened .pdf (bridge); kind 'node' → a node opened "in PDF-Tool"
    // (session binding, no startup_path; the surface fetches get_pdf_bytes(startup_session)).
    const cfg = kind === 'node'
      ? { ok: true, dev: false, default_dpi: 150, startup_kind: 'node', startup_session: 's1' }
      : { ok: true, dev: false, default_dpi: 150, startup_kind: 'pdf', startup_path: 'C:/x.pdf' }
    const api = {
      config: () => cfg,
      open: () => ({ ok: true, session: 's1', datev: { connected, source_name: '1085411.pdf' } }),
      get_pdf_bytes: async () => {
        const buf = await (await fetch('/spike-form.pdf')).arrayBuffer()
        return { ok: true, data_b64: toB64(new Uint8Array(buf)) }
      },
      // SERVICE connection is independent of whether the OPEN document is a checkout:
      // a live service (serviceConnected) can still open a not-yet-filed .pdf (connected:false).
      datev_status: () => (window.__statusSeq ? window.__statusSeq()
        : { ok: true, datev_mode: datevMode, connected: serviceConnected }),
      datev_clients: () => window.__clientsResult || ({ ok: true, clients: [{ guid: 'cg-1', number: '10001', name: 'Muster GmbH' }] }),
      datev_placements: () => ({ ok: true, folders: [] }),
      update_pdf_bytes: (s) => { calls.push(['update_pdf_bytes', s]); return { ok: true } },  // session-only bake
      save_pdf_bytes: (s) => { calls.push(['save_pdf_bytes', s]); return window.__localResult || { ok: true, local_saved: 'C:/x/1085411.pdf', local_kind: 'pdf' } },
      save_to_datev: (s) => { calls.push(['save_to_datev', s]); return window.__sbResult || { ok: true, verdict: 'ok', local_saved: 'C:/x/1085411.pdf' } },
      datev_file: (s, c, num) => { calls.push(['datev_file', s, c, num]); return window.__fileResult || { ok: true, provenance: { doc_guid: 'g', file_id: 1 }, local_saved: 'C:/x/1085411.pdf' } },
    }
    window.pywebview = { api }
  }, { connected, datevMode, serviceConnected, kind })
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

  test('a declined write-back ("only the local file") saves the local .pdf, no DATEV push', async ({ page }) => {
    // The "In DATEV aktualisieren?" confirm: "Nein" = only update the local checked-out file →
    // save_pdf_bytes IS called (the edit is persisted to disk), status says "Nur lokal gespeichert".
    await installBridge(page, { connected: true, datevMode: true })
    await page.addInitScript(() => { window.__sbResult = { ok: false, verdict: 'declined' } })
    await page.goto('/pdf-tool.html')
    const btn = page.locator('#btn-datev')
    await expect(btn).toBeVisible({ timeout: 20000 })
    await btn.click()
    await expect(page.locator('#pdf-status')).toHaveText(/Nur lokal gespeichert/, { timeout: 20000 })
    const calls = await page.evaluate(() => window.__calls.map((c) => c[0]))
    expect(calls).toEqual(['update_pdf_bytes', 'save_to_datev', 'save_pdf_bytes'])
  })

  test('a connected checkout shows the "Mit DATEV verknüpft" link badge', async ({ page }) => {
    await installBridge(page, { connected: true, datevMode: true })
    await page.goto('/pdf-tool.html')
    await expect(page.locator('#datev-link')).toHaveText(/Mit DATEV verknüpft/, { timeout: 20000 })
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

  // Pick the (only) client in the filing dialog and confirm. A bridge .pdf prefills the Bezeichnung
  // from the file name (Ablegen already enabled); pass `name` to set it where there is no default
  // (a node binding) — Ablegen is disabled until a Bezeichnung is present (the "pdf lacks Name" fix).
  async function fileViaDialog(page, { name } = {}) {
    await page.locator('#btn-datev').click()
    const dialog = page.locator('.pdftool-modal-backdrop [role="dialog"]')
    await expect(dialog).toBeVisible({ timeout: 20000 })
    await dialog.locator('select[aria-label="Mandant"]').selectOption('cg-1')
    if (name !== undefined) await dialog.locator('input[aria-label="Bezeichnung"]').fill(name)
    await dialog.getByRole('button', { name: 'Ablegen' }).click()
  }

  test('a not-connected pdf shows file-anew; the dialog files via datev_file with the client GUID', async ({ page }) => {
    await installBridge(page, { connected: false, datevMode: true })
    await page.goto('/pdf-tool.html')
    const btn = page.locator('#btn-datev')
    await expect(btn).toBeVisible({ timeout: 20000 })
    await expect(btn).toHaveText(/Nach DATEV ablegen/)
    await fileViaDialog(page)
    // names the saved file (format-clarity) and bakes session-only first
    await expect(page.locator('#pdf-status'))
      .toHaveText(/In DATEV abgelegt ✓ · 1085411\.pdf/, { timeout: 20000 })
    const calls = await page.evaluate(() => window.__calls.map((c) => c[0]))
    expect(calls).toEqual(['update_pdf_bytes', 'datev_file'])
    const filed = await page.evaluate(() => window.__calls.find((c) => c[0] === 'datev_file'))
    expect(filed && filed[2]).toBe('cg-1')   // the dialog passes the chosen client GUID (arg[1] of datev_file)
  })

  test('file-anew that succeeds in DATEV but fails the local save surfaces the local error', async ({ page }) => {
    // Regression (round 10): datev_file merges {local_error, local_saved:null} when the parallel
    // local write fails. datevFileNew must surface it, never a bare "In DATEV abgelegt ✓" — else
    // the on-disk .pdf is silently stale vs DATEV. Mirrors App.jsx fileToDatev.
    await installBridge(page, { connected: false, datevMode: true })
    await page.addInitScript(() => {
      window.__fileResult = { ok: true, provenance: { doc_guid: 'g', file_id: 1 }, local_saved: null, local_error: 'Kein lokaler Speicherort gebunden' }
    })
    await page.goto('/pdf-tool.html')
    await expect(page.locator('#btn-datev')).toBeVisible({ timeout: 20000 })
    await fileViaDialog(page)
    const status = page.locator('#pdf-status')
    await expect(status).toHaveText(/In DATEV abgelegt ✓/, { timeout: 20000 })
    await expect(status).toHaveText(/lokal: Kein lokaler Speicherort gebunden/)  // the disk failure is surfaced
  })

  test('file-anew that DATEV rejects surfaces the error', async ({ page }) => {
    // Coverage (round 10, Low): the datev_file error branch in datevFileNew.
    await installBridge(page, { connected: false, datevMode: true })
    await page.addInitScript(() => { window.__fileResult = { ok: false, error: 'Mandant 999 unbekannt' } })
    await page.goto('/pdf-tool.html')
    await expect(page.locator('#btn-datev')).toBeVisible({ timeout: 20000 })
    await fileViaDialog(page)
    await expect(page.locator('#pdf-status')).toHaveText(/DATEV: Mandant 999 unbekannt/, { timeout: 20000 })
  })

  test('file-anew refuses when the client list is unavailable (no data → no DATEV write)', async ({ page }) => {
    await installBridge(page, { connected: false, datevMode: true })
    await page.addInitScript(() => { window.__clientsResult = { ok: false, error: 'HTTP 404' } })
    await page.goto('/pdf-tool.html')
    const btn = page.locator('#btn-datev')
    await expect(btn).toBeVisible({ timeout: 20000 })
    await btn.click()
    await expect(page.locator('#pdf-status')).toHaveText(/DATEV: HTTP 404/, { timeout: 20000 })
    // no dialog, no datev_file call
    const calls = await page.evaluate(() => window.__calls.map((c) => c[0]))
    expect(calls).not.toContain('datev_file')
  })

  test('no service connection → the DATEV action is DISABLED (never a write without a connection)', async ({ page }) => {
    await installBridge(page, { connected: true, datevMode: true, serviceConnected: false })
    await page.goto('/pdf-tool.html')
    const btn = page.locator('#btn-datev')
    await expect(btn).toBeVisible({ timeout: 20000 })
    await expect(btn).toBeDisabled()
    await expect(btn).toHaveAttribute('title', /Keine Verbindung/)
  })

  test('a still-connecting service re-polls and ENABLES the DATEV action once it settles', async ({ page }) => {
    // REGRESSION (audit): setupDatevUi must re-poll while datev_status reports connecting:true and
    // re-enable the button when it settles — a single read latched it disabled forever.
    await installBridge(page, { connected: false, datevMode: true })
    await page.addInitScript(() => {
      let n = 0
      window.__statusSeq = () => (n++ < 1
        ? { ok: true, datev_mode: true, connected: false, connecting: true }   // first read: connecting
        : { ok: true, datev_mode: true, connected: true })                     // then: connected
    })
    await page.goto('/pdf-tool.html')
    const btn = page.locator('#btn-datev')
    await expect(btn).toBeVisible({ timeout: 20000 })
    await expect(btn).toBeEnabled({ timeout: 20000 })   // re-poll flipped it from disabled→enabled
  })

  test('a node opened "in PDF-Tool" (session binding) ALSO offers file-anew to DATEV', async ({ page }) => {
    // REGRESSION (v3.11.0 "opening in pdf-tool lacks all DATEV capability"): setupDatevUi used to
    // bail unless sourceMode === 'bridge', so a node binding got NO DATEV button. It must now show
    // file-anew (a node binding is never "connected" → always file) and file via datev_file.
    await installBridge(page, { connected: false, datevMode: true, kind: 'node' })
    await page.goto('/pdf-tool.html')
    const btn = page.locator('#btn-datev')
    await expect(btn).toBeVisible({ timeout: 20000 })
    await expect(btn).toHaveText(/Nach DATEV ablegen/)   // file-anew, not write-back
    await fileViaDialog(page, { name: 'Eingangsrechnung' })  // node binding has no prefilled name
    const calls = await page.evaluate(() => window.__calls.map((c) => c[0]))
    expect(calls).toEqual(['update_pdf_bytes', 'datev_file'])
  })

  test('DATEV mode off shows no DATEV button', async ({ page }) => {
    await installBridge(page, { connected: true, datevMode: false })
    await page.goto('/pdf-tool.html')
    await expect(page.locator('.textLayer')).toContainText('SPIKE', { timeout: 20000 })  // doc loaded
    await expect(page.locator('#btn-datev')).toBeHidden()
  })
})
