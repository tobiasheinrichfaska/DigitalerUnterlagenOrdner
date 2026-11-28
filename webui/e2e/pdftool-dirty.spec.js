// PDF-Tool audit x4: unsaved-edit tracking + close guard feed (PT-2), unedited save is a no-op
// (PT-4), in-flight Save guard + Text tool disabled after a failed load (PT-7), encrypted PDF
// password prompt (PT-1). Stub bridge injected before load; real Chromium + real PDF.js.
import { test, expect } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

test.use({ locale: 'de-DE' })
const HERE = path.dirname(fileURLToPath(import.meta.url))
const ENC_B64 = fs.readFileSync(path.join(HERE, 'fixtures', 'enc-form.pdf')).toString('base64')

function installBridge(page, { enc = false, loadFails = false, saveDelay = 0, pdf = '/spike-form.pdf', saveResults = null } = {}) {
  return page.addInitScript(({ enc, encB64, loadFails, saveDelay, pdf, saveResults }) => {
    const calls = []
    window.__calls = calls
    const toB64 = (bytes) => {
      let s = ''
      for (let i = 0; i < bytes.length; i += 1) s += String.fromCharCode(bytes[i])
      return btoa(s)
    }
    window.pywebview = { api: {
      config: () => ({ ok: true, dev: false, default_dpi: 150, startup_kind: 'node', startup_session: 'pt1' }),
      get_pdf_bytes: async () => {
        if (loadFails) return { ok: false, error: 'kaputt' }
        if (enc) return { ok: true, data_b64: encB64 }
        const buf = await (await fetch(pdf)).arrayBuffer()
        return { ok: true, data_b64: toB64(new Uint8Array(buf)) }
      },
      open: () => ({ ok: false }),
      set_dirty: (v) => { calls.push(['set_dirty', v]); return { ok: true } },
      save_node_back: async (s, b64) => {
        calls.push(['save_node_back', s]); window.__lastSaved = b64
        if (saveDelay) await new Promise((r) => setTimeout(r, saveDelay))
        if (saveResults) return saveResults.shift() || { ok: true }
        return { ok: true }
      },
      datev_status: () => ({ ok: true, datev_mode: false, connected: false }),
    } }
  }, { enc, encB64: ENC_B64, loadFails, saveDelay, pdf, saveResults })
}

const names = (page, n) => page.evaluate((n) => window.__calls.filter((c) => c[0] === n).map((c) => c[1]), n)

async function fillField(page, value = 'edited') {
  const field = page.locator('.annotationLayer input').first()
  await expect(field).toBeVisible({ timeout: 20000 })
  await field.fill(value)
  await field.blur()
}

test.describe('PDF-Tool dirty tracking + save', () => {
  test('not dirty on load; a form edit pushes set_dirty(true); save pushes false', async ({ page }) => {
    await installBridge(page)
    await page.goto('/pdf-tool.html')
    await expect(page.locator('#btn-save')).toBeEnabled({ timeout: 20000 })
    expect(await page.evaluate(() => window.__belegDirty)).toBe(false)
    expect(await names(page, 'set_dirty')).toEqual([])
    await fillField(page)
    await expect.poll(() => page.evaluate(() => window.__belegDirty)).toBe(true)
    expect(await names(page, 'set_dirty')).toEqual([true])
    await page.locator('#btn-save').click()
    await expect(page.locator('#pdf-status')).toHaveText(/Gespeichert/, { timeout: 20000 })
    expect(await names(page, 'save_node_back')).toEqual(['pt1'])
    expect(await page.evaluate(() => window.__belegDirty)).toBe(false)
    expect(await names(page, 'set_dirty')).toEqual([true, false])
  })

  test('a Save without edits never reaches save_node_back', async ({ page }) => {
    await installBridge(page)
    await page.goto('/pdf-tool.html')
    await expect(page.locator('#btn-save')).toBeEnabled({ timeout: 20000 })
    await page.locator('#btn-save').click()
    await expect(page.locator('#pdf-status')).toHaveText(/Keine Änderungen/)
    expect(await names(page, 'save_node_back')).toEqual([])
  })

  test('triple click on Save saves once (in-flight guard)', async ({ page }) => {
    await installBridge(page, { saveDelay: 400 })
    await page.goto('/pdf-tool.html')
    await expect(page.locator('#btn-save')).toBeEnabled({ timeout: 20000 })
    await fillField(page)
    await expect.poll(() => page.evaluate(() => window.__belegDirty)).toBe(true)
    await page.evaluate(() => { const b = document.getElementById('btn-save'); b.click(); b.click(); b.click() })
    await expect(page.locator('#pdf-status')).toHaveText(/Gespeichert/, { timeout: 20000 })
    expect(await names(page, 'save_node_back')).toEqual(['pt1'])
  })

  test('R11-2: a PDF with radio buttons opens clean (no dirty, no set_dirty)', async ({ page }) => {
    await installBridge(page, { pdf: '/spike-radio.pdf' })
    await page.goto('/pdf-tool.html')
    await expect(page.locator('#btn-save')).toBeEnabled({ timeout: 20000 })
    await expect(page.locator('.annotationLayer input[type=radio]').first()).toBeVisible({ timeout: 20000 })
    await page.waitForTimeout(800)
    expect(await page.evaluate(() => window.__belegDirty)).toBe(false)
    expect(await names(page, 'set_dirty')).toEqual([])
    await page.locator('#btn-save').click()
    await expect(page.locator('#pdf-status')).toHaveText(/Keine Änderungen/)
    // a real radio change afterwards still counts
    await page.locator('.annotationLayer input[type=radio]').nth(1).check({ force: true })
    await expect.poll(() => page.evaluate(() => window.__belegDirty)).toBe(true)
  })

  test('R11-3: a failed save keeps dirty; the second Save retries and succeeds', async ({ page }) => {
    await installBridge(page, { saveResults: [{ ok: false, error: 'Platte voll' }] })
    await page.goto('/pdf-tool.html')
    await expect(page.locator('#btn-save')).toBeEnabled({ timeout: 20000 })
    await fillField(page)
    await expect.poll(() => page.evaluate(() => window.__belegDirty)).toBe(true)
    await page.locator('#btn-save').click()
    await expect(page.locator('#pdf-status')).toHaveText(/Platte voll/, { timeout: 20000 })
    expect(await page.evaluate(() => window.__belegDirty)).toBe(true)
    expect(await names(page, 'set_dirty')).toEqual([true])
    await page.locator('#btn-save').click()
    await expect(page.locator('#pdf-status')).toHaveText(/Gespeichert/, { timeout: 20000 })
    expect(await names(page, 'save_node_back')).toEqual(['pt1', 'pt1'])
    expect(await page.evaluate(() => window.__belegDirty)).toBe(false)
  })

  test('R11-3: a local_error result also keeps dirty', async ({ page }) => {
    await installBridge(page, { saveResults: [{ ok: true, local_error: 'gesperrt' }] })
    await page.goto('/pdf-tool.html')
    await expect(page.locator('#btn-save')).toBeEnabled({ timeout: 20000 })
    await fillField(page)
    await page.locator('#btn-save').click()
    await expect(page.locator('#pdf-status')).toHaveText(/gesperrt/, { timeout: 20000 })
    expect(await page.evaluate(() => window.__belegDirty)).toBe(true)
  })

  test('R11-3: an edit made while the save is in flight stays dirty', async ({ page }) => {
    await installBridge(page, { saveDelay: 1200 })
    await page.goto('/pdf-tool.html')
    await expect(page.locator('#btn-save')).toBeEnabled({ timeout: 20000 })
    await fillField(page, 'one')
    await expect.poll(() => page.evaluate(() => window.__belegDirty)).toBe(true)
    await page.locator('#btn-save').click()
    await expect.poll(async () => (await names(page, 'save_node_back')).length).toBe(1)
    await fillField(page, 'two-during-save')
    await expect(page.locator('#pdf-status')).toHaveText(/Gespeichert/, { timeout: 20000 })
    expect(await page.evaluate(() => window.__belegDirty)).toBe(true)
  })

  test('after a failed load the Text tool is disabled too', async ({ page }) => {
    await installBridge(page, { loadFails: true })
    await page.goto('/pdf-tool.html')
    await expect(page.locator('#pdf-status')).toHaveText(/Fehler/, { timeout: 20000 })
    await expect(page.locator('#btn-text')).toBeDisabled()
    await expect(page.locator('#btn-save')).toBeDisabled()
  })
})

test.describe('PDF-Tool encrypted PDF', () => {
  test('asks for the password, retries on a wrong one, then opens', async ({ page }) => {
    await installBridge(page, { enc: true })
    await page.goto('/pdf-tool.html')
    const dlg = page.getByRole('dialog')
    await expect(dlg).toBeVisible({ timeout: 20000 })
    await expect(dlg).toContainText('passwortgeschützt')
    await page.locator('#pw-input').fill('wrong')
    await page.locator('#pw-input').press('Enter')
    await expect(page.locator('#pw-hint')).toContainText('Falsches Passwort', { timeout: 20000 })
    await page.locator('#pw-input').fill('secret')
    await page.locator('#pw-input').press('Enter')
    await expect(dlg).toBeHidden()
    await page.waitForFunction(() => window.__viewerDocReady === true, null, { timeout: 20000 })
    await expect(page.locator('.textLayer')).toContainText('SPIKE-SELECTABLE-TEXT', { timeout: 20000 })
    expect(await page.evaluate(() => JSON.stringify(window.__calls))).not.toContain('secret')
  })

  test('cancel closes the load with a clear message', async ({ page }) => {
    await installBridge(page, { enc: true })
    await page.goto('/pdf-tool.html')
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 20000 })
    await page.getByRole('button', { name: 'Abbrechen' }).click()
    await expect(page.locator('#pdf-status')).toContainText('Passwort-Eingabe abgebrochen', { timeout: 20000 })
    await expect(page.locator('#btn-text')).toBeDisabled()
    await expect(page.locator('#btn-save')).toBeDisabled()
  })

  test('saving an edited encrypted PDF (recorded for the audit log)', async ({ page }) => {
    await installBridge(page, { enc: true })
    await page.goto('/pdf-tool.html')
    await page.locator('#pw-input').fill('secret')
    await page.locator('#pw-input').press('Enter')
    await fillField(page)
    await page.locator('#btn-save').click()
    await expect(page.locator('#pdf-status')).toHaveText(/Gespeichert/, { timeout: 20000 })
    const b64 = await page.evaluate(() => window.__lastSaved)
    if (process.env.PT_DUMP) fs.writeFileSync(process.env.PT_DUMP, Buffer.from(b64, 'base64'))
    expect(b64.length).toBeGreaterThan(100)
  })
})
