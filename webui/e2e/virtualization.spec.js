// Real-Chromium test for the windowed preview's scroll virtualization — the one
// thing jsdom cannot exercise (it has no layout, so offsetTop/scrollTop are 0 and
// the binary-search visibleRange never advances). Here, scrolling the container
// must fetch and render pages that were NOT in the initial window.
import { test, expect } from '@playwright/test'
import { installBridge } from './bridge.js'

const renderedFirsts = (page) =>
  page.evaluate(() =>
    window.__beleg.calls.filter((c) => c.method === 'render_window').map((c) => c.args[2])) // `first` page index

test.describe('windowed preview virtualization', () => {
  test('initially fetches only the top pages, not the whole document', async ({ page }) => {
    await installBridge(page, { pageCount: 60 })
    await page.goto('/')
    await page.getByText('alpha').click()
    await expect(page.locator('.win-preview')).toBeVisible()
    // it must NOT have requested all 60 pages up front
    await expect.poll(async () => (await renderedFirsts(page)).length).toBeGreaterThan(0)
    const firsts = await renderedFirsts(page)
    expect(Math.max(...firsts)).toBeLessThan(20) // only near the top
    // and only a handful of page placeholders carry a real <img> so far
    expect(await page.locator('.win-preview img').count()).toBeLessThan(60)
  })

  test('scrolling to the bottom fetches and renders later pages', async ({ page }) => {
    await installBridge(page, { pageCount: 60 })
    await page.goto('/')
    await page.getByText('alpha').click()
    const scroller = page.locator('.win-preview')
    await expect(scroller).toBeVisible()

    await scroller.evaluate((el) => { el.scrollTop = el.scrollHeight })

    // a high page index gets requested only because real layout put it in view
    await expect.poll(async () => Math.max(0, ...(await renderedFirsts(page)))).toBeGreaterThan(30)
    // the last page box now shows a rendered image (was a skeleton before)
    await expect(page.locator('.win-preview .win-page').last().locator('img')).toBeVisible()
  })
})
