// LY-1/4/5 (layout audit): the organizer header must not overflow horizontally at narrow widths
// even with a long DATEV-linked document name; the PDF-Tool link badge carries a full-text tooltip.
import { test, expect } from '@playwright/test'

const LONG = 'Steuerunterlagen 2024 Mandant Müller & Söhne Maschinenbau Verwaltungsgesellschaft mbH und Co KG'

async function bridge(page) {
  await page.addInitScript((LONG) => {
    const tree = { id: 'root', name: LONG, is_folder: true, children: [], datev: { doc_guid: 'g', file_id: 1, source_name: 'x.belegtool', connected: true } }
    const ok = (e = {}) => ({ ok: true, session: 's', tree, can_undo: false, can_redo: false, ...e })
    const base = {
      config: () => ({ ok: true, dev: false, default_dpi: 150, app_name: 'BelegTool', datev_mode: true, startup_path: 'C:/x.belegtool' }),
      open: () => ok({ datev: tree.datev }),
      get_state: () => ok(),
      datev_status: () => ({ ok: true, datev_mode: true, connected: true }),
      page_count: () => ({ ok: true, count: 0 }),
    }
    window.pywebview = { api: new Proxy({}, { get: (_t, p) => (typeof p !== 'string' || p === 'then') ? undefined : (...a) => (base[p] || (() => ({ ok: true })))(...a) }) }
  }, LONG)
}

test.describe('header layout', () => {
  for (const w of [800, 1024]) {
    test(`no horizontal page scroll at ${w}px with a long linked document name`, async ({ page }) => {
      await page.setViewportSize({ width: w, height: 700 })
      await bridge(page)
      await page.goto('/')
      await expect(page.locator('header h1')).toBeVisible()
      await expect(page.locator('header h1')).toHaveAttribute('title', LONG)
      const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
      expect(over).toBeLessThanOrEqual(0)
    })
  }

  test('PDF-Tool link badge has a tooltip with its full text', async ({ page }) => {
    await page.addInitScript(() => {
      window.pywebview = { api: {
        config: () => ({ ok: true, dev: false, default_dpi: 150, startup_kind: 'pdf', startup_path: 'C:/x.pdf' }),
        open: () => ({ ok: true, session: 's1', datev: { connected: true, source_name: 'A_very_long_name.pdf', checked_out_at_open: true } }),
        get_pdf_bytes: async () => { const b = new Uint8Array(await (await fetch('/spike-form.pdf')).arrayBuffer()); let s = ''; b.forEach((c) => { s += String.fromCharCode(c) }); return { ok: true, data_b64: btoa(s) } },
        datev_status: () => ({ ok: true, datev_mode: true, connected: true }),
      } }
    })
    await page.goto('/pdf-tool.html')
    const link = page.locator('#datev-link')
    await expect(link).toHaveText(/Mit DATEV verknüpft/, { timeout: 20000 })
    await expect(link).toHaveAttribute('title', /A_very_long_name\.pdf/)
  })
})
