// Component tests for the bottom status bar.
//
// NOTE: no `vi.mock()` here. This project runs Vitest on the `vmThreads` pool (the
// only pool that doesn't crash on vitest 4.1.8 + Node 24 + Vite 8), and `vi.mock()`
// does NOT take effect under `vmThreads`. So we drive the REAL `./lib/core` against a
// stubbed `window.pywebview.api` bridge — which also makes these genuine integration
// tests of core.js's activity tracking + render-stats polling feeding the bar.
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { StatusBar } from './StatusBar'
import { core } from './lib/core'

const MB = 1024 * 1024
const STATS = {
  ok: true, cache_used: 30 * MB, cache_budget: 200 * MB, cache_free: 170 * MB,
  cache_pages: 12, prefetch_active: false,
}

// In-flight bridge calls used to raise the activity counters. core.js holds those
// counters in module state, so we MUST settle every pending call after each test or
// the count leaks into the next one.
let pending = []
const deferred = () => new Promise((resolve) => pending.push(resolve))

let calls
function installApi(overrides = {}) {
  calls = []
  const base = {
    render_stats: () => STATS,
    set_render_budget: (mb) => ({ ...STATS, cache_budget: mb * MB }),
  }
  const api = new Proxy({}, {
    get(_t, prop) {
      if (typeof prop !== 'string' || prop === 'then') return undefined
      return (...args) => {
        calls.push({ method: prop, args })
        return (overrides[prop] || base[prop] || (() => ({ ok: true })))(...args)
      }
    },
  })
  window.pywebview = { api }
}

beforeEach(() => installApi())
afterEach(() => {
  cleanup()                       // unmount → StatusBar unsubscribes from onActivity
  pending.forEach((r) => r({ ok: true })) // settle in-flight calls → counters back to 0
  pending = []
  delete window.pywebview
})

describe('StatusBar — activity text', () => {
  it('shows "Bereit" when idle', () => {
    render(<StatusBar docPages={20} />)
    expect(screen.getByText('Bereit')).toBeInTheDocument()
  })

  it('reports in-flight compression (counted by distinct node)', async () => {
    installApi({ compress_options: () => deferred() })
    render(<StatusBar docPages={20} />)
    core.compressOptions('s', 'n1', 150) // two DISTINCT nodes in flight → "Komprimiere 2"
    core.compressOptions('s', 'n2', 150)
    await waitFor(() => expect(screen.getByText(/Komprimiere 2/)).toBeInTheDocument())
  })

  it('reports in-flight preview rendering', async () => {
    installApi({ render_window: () => deferred() })
    render(<StatusBar docPages={20} />)
    core.renderWindow('s', 'n1'); core.renderWindow('s', 'n2'); core.renderWindow('s', 'n3')
    await waitFor(() => expect(screen.getByText(/Vorschau lädt 3/)).toBeInTheDocument())
  })
})

describe('StatusBar — cache readout', () => {
  it('shows the polled cache occupancy in MB and the document page total', async () => {
    render(<StatusBar docPages={20} />)
    await waitFor(() => expect(screen.getByText(/Cache 30\/200 MB · 12\/20 Seiten/)).toBeInTheDocument())
  })

  it('surfaces the prefetch-active hint', async () => {
    installApi({ render_stats: () => ({ ...STATS, prefetch_active: true }) })
    render(<StatusBar docPages={20} />)
    await waitFor(() => expect(screen.getByText(/Cache füllt/)).toBeInTheDocument())
  })
})

describe('StatusBar — budget buttons', () => {
  const lastBudgetArg = () => {
    const c = calls.filter((x) => x.method === 'set_render_budget')
    return c.length ? c[c.length - 1].args[0] : undefined
  }

  it('＋ grows and − shrinks the budget by 50 MB', async () => {
    // Keep set_render_budget pending so stats stays at 200 MB → both deltas are
    // computed from the same baseline (250 up, 150 down), not chained.
    installApi({ set_render_budget: () => deferred() })
    render(<StatusBar docPages={20} />)
    await waitFor(() => screen.getByText(/Cache 30\/200 MB/))
    fireEvent.click(screen.getByTitle('Cache vergrößern (+50 MB)'))
    await waitFor(() => expect(lastBudgetArg()).toBe(250))
    fireEvent.click(screen.getByTitle('Cache verkleinern (−50 MB)'))
    await waitFor(() => expect(lastBudgetArg()).toBe(150))
  })
})
