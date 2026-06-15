// Component tests for the bottom status bar. The core module is mocked so we can
// drive the background-activity callback and the polled render-cache stats, and
// assert the activity text, the cache readout, and the +/- budget buttons.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor, cleanup } from '@testing-library/react'

const h = vi.hoisted(() => ({
  ref: { cb: null },
  renderStats: vi.fn(),
  setCacheBudget: vi.fn(),
}))

vi.mock('./lib/core', () => ({
  onActivity: (fn) => { h.ref.cb = fn; fn({ compress: 0, render: 0 }); return () => {} },
  core: { renderStats: h.renderStats, setCacheBudget: h.setCacheBudget },
}))

import { StatusBar } from './StatusBar'

const MB = 1024 * 1024
const STATS = {
  ok: true, cache_used: 30 * MB, cache_budget: 200 * MB, cache_free: 170 * MB,
  cache_pages: 12, prefetch_active: false,
}

beforeEach(() => {
  h.renderStats.mockResolvedValue(STATS)
  h.setCacheBudget.mockResolvedValue({ ...STATS, cache_budget: 250 * MB })
})
afterEach(() => { vi.clearAllMocks(); cleanup() })

// push a new background-activity snapshot through the registered callback
const setActivity = (snap) => act(() => h.ref.cb?.(snap))

describe('StatusBar — activity text', () => {
  it('shows "Bereit" when idle', () => {
    render(<StatusBar docPages={20} />)
    expect(screen.getByText('Bereit')).toBeInTheDocument()
  })

  it('reports in-flight compression and rendering', () => {
    render(<StatusBar docPages={20} />)
    setActivity({ compress: 2, render: 0 })
    expect(screen.getByText(/Komprimiere 2/)).toBeInTheDocument()
    setActivity({ compress: 0, render: 3 })
    expect(screen.getByText(/Vorschau lädt 3/)).toBeInTheDocument()
  })
})

describe('StatusBar — cache readout', () => {
  it('shows the polled cache occupancy in MB and the document page total', async () => {
    render(<StatusBar docPages={20} />)
    await waitFor(() => expect(screen.getByText(/Cache 30\/200 MB · 12\/20 Seiten/)).toBeInTheDocument())
  })

  it('surfaces the prefetch-active hint', async () => {
    h.renderStats.mockResolvedValue({ ...STATS, prefetch_active: true })
    render(<StatusBar docPages={20} />)
    await waitFor(() => expect(screen.getByText(/Cache füllt/)).toBeInTheDocument())
  })
})

describe('StatusBar — budget buttons', () => {
  it('＋ grows and − shrinks the budget by 50 MB', async () => {
    render(<StatusBar docPages={20} />)
    await waitFor(() => screen.getByText(/Cache 30\/200 MB/))
    fireEvent.click(screen.getByTitle('Cache vergrößern (+50 MB)'))
    expect(h.setCacheBudget).toHaveBeenLastCalledWith(250)
    fireEvent.click(screen.getByTitle('Cache verkleinern (−50 MB)'))
    expect(h.setCacheBudget).toHaveBeenLastCalledWith(150)
  })
})
