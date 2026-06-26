// SPIKE proof (step 1 of the two-surface design, docs/pdf-tool.md):
// the PDF-Tool surface renders a SELECTABLE text layer and an INTERACTIVE AcroForm
// field in real Chromium (the same engine as the pywebview WebView2 host). If this
// passes, the rich-interaction features the raster organizer can't do are confirmed
// feasible in this app's runtime.
import { test, expect } from '@playwright/test'

test.describe('PDF-Tool surface (spike)', () => {
  test('renders a selectable text layer and a fillable AcroForm field', async ({ page }) => {
    const errors = []
    page.on('pageerror', (e) => errors.push(String(e)))
    await page.goto('/pdf-tool.html')

    // 1) Text layer renders with the sample's known text.
    const textLayer = page.locator('.textLayer')
    await expect(textLayer).toContainText('SPIKE-SELECTABLE-TEXT', { timeout: 20000 })

    // 2) Selection works: triple-click the line, read the live DOM selection.
    await page.locator('.textLayer span', { hasText: 'SPIKE' }).first().click({ clickCount: 3 })
    const selected = await page.evaluate(() => window.getSelection().toString())
    expect(selected).toContain('SPIKE-SELECTABLE-TEXT')

    // 3) AcroForm field renders as an interactive input and accepts a value.
    const field = page.locator('.annotationLayer input').first()
    await expect(field).toBeVisible({ timeout: 20000 })
    await field.fill('filled-by-spike')
    await expect(field).toHaveValue('filled-by-spike')

    expect(errors, `page errors: ${errors.join('; ')}`).toEqual([])
  })
})
