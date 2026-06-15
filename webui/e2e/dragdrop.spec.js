// Real-Chromium test for HTML5 drag-and-drop in the tree. jsdom carries no drag
// geometry (clientY / bounding rects are 0), so the dropZone math and the
// dragstart→dragover→drop handshake can only be exercised in a real engine.
// We dispatch the native DragEvents with a shared DataTransfer (Playwright's mouse
// API does NOT trigger HTML5 dnd), with a clientY inside the target row.
import { test, expect } from '@playwright/test'
import { installBridge } from './bridge.js'

const row = (page, name) => page.getByRole('treeitem').filter({ hasText: name })

const movesDispatched = (page) =>
  page.evaluate(() =>
    window.__beleg.calls.filter((c) => ['Move', 'MoveMany'].includes(c.args?.[1]?.type)).map((c) => c.args[1]))

test.describe('tree drag-and-drop', () => {
  test('dragging a row onto another dispatches a Move', async ({ page }) => {
    await installBridge(page)
    await page.goto('/')
    await expect(row(page, 'alpha')).toBeVisible()

    const src = row(page, 'alpha')
    const dst = row(page, 'gamma')
    const box = await dst.boundingBox()
    const opts = { clientX: box.x + box.width / 2, clientY: box.y + 4 } // near the top → "before"

    const dt = await page.evaluateHandle(() => new DataTransfer())
    await src.dispatchEvent('dragstart', { dataTransfer: dt })
    await dst.dispatchEvent('dragover', { dataTransfer: dt, ...opts })
    await dst.dispatchEvent('drop', { dataTransfer: dt, ...opts })

    await expect.poll(async () => (await movesDispatched(page)).length).toBeGreaterThan(0)
    const move = (await movesDispatched(page))[0]
    expect(move.node_id ?? move.node_ids).toBeTruthy() // a single Move (node_id) here
  })
})
