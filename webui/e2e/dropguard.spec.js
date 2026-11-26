// Security review 2026-11-25 (H-3): a file/link dropped on a window must never NAVIGATE it
// (pywebview would re-inject the JS bridge into the hostile page). src/lib/dropGuard.js is
// installed by both entries; this proves a cancelable dragover/drop with Files ends up
// defaultPrevented on the real page, for the PDF-Tool surface and the organizer.
import { test, expect } from '@playwright/test'
import { installBridge } from './bridge.js'

// Fire a cancelable event carrying dataTransfer.types=['Files'] on window; report defaultPrevented.
async function fire(page, type) {
  return page.evaluate((type) => {
    const e = new Event(type, { bubbles: true, cancelable: true })
    Object.defineProperty(e, 'dataTransfer', { value: { types: ['Files'], files: [] } })
    window.dispatchEvent(e)
    return e.defaultPrevented
  }, type)
}

test.describe('drop guard (no drag-and-drop navigation)', () => {
  test('PDF-Tool window cancels dragover and drop', async ({ page }) => {
    await page.goto('/pdf-tool.html?file=/spike-link.pdf')
    // The guard is installed at module load, independent of PDF rendering.
    await page.waitForLoadState('load')
    expect(await fire(page, 'dragover')).toBe(true)
    expect(await fire(page, 'drop')).toBe(true)
  })

  test('organizer window cancels dragover and drop', async ({ page }) => {
    await installBridge(page)
    await page.goto('/')
    await expect(page.locator('body')).toBeVisible()
    expect(await fire(page, 'dragover')).toBe(true)
    expect(await fire(page, 'drop')).toBe(true)
  })
})
