import { describe, it, expect, vi, afterEach } from 'vitest'
import { core } from './core.js'

// Build a fake pywebview API that records every call, so we can assert the
// JS-side method names map to the right snake_case host methods with the right
// arguments. Each method echoes a tagged result so we can check the value flows
// back through core.*.
function fakeApi() {
  const calls = []
  return new Proxy(
    { calls },
    {
      get(target, prop) {
        if (prop === 'calls') return calls
        // Return undefined for `then` (and any symbol prop) so the Proxy is not
        // mistaken for a thenable when a Promise resolves with it — otherwise the
        // resolution would try to adopt it and never settle.
        if (typeof prop !== 'string' || prop === 'then') return undefined
        return (...args) => {
          calls.push({ method: prop, args })
          return { ok: true, method: prop, args }
        }
      },
    },
  )
}

afterEach(() => {
  delete window.pywebview
  vi.useRealTimers()
})

describe('core.js → window.pywebview.api mapping', () => {
  it('maps camelCase methods to snake_case host methods and forwards args', async () => {
    const api = fakeApi()
    window.pywebview = { api }

    expect((await core.config()).method).toBe('config')
    expect((await core.newWindow()).method).toBe('new_window')
    expect((await core.setDirty(true)).args).toEqual([true])
    expect((await core.exportPdf('s1', ['a', 'b'])).method).toBe('export_dialog')
    expect((await core.renderCompressedWindow('s1', 'n1', 150, 'jpg')).method).toBe('render_compressed_window')
    expect((await core.importBytes('s1', 'f.pdf', 'data', 'p1', 2)).args)
      .toEqual(['s1', 'f.pdf', 'data', 'p1', 2])

    // export_dialog forwarded session + node ids + options (null by default)
    expect(api.calls.find((c) => c.method === 'export_dialog').args).toEqual(['s1', ['a', 'b'], null])
  })

  it('resolves with the host method return value', async () => {
    window.pywebview = { api: fakeApi() }
    const r = await core.dispatch('s1', { type: 'AddFolder' })
    expect(r.ok).toBe(true)
    expect(r.args).toEqual(['s1', { type: 'AddFolder' }])
  })
})

describe('core.js api readiness', () => {
  it('waits for the pywebviewready event when the api is not yet injected', async () => {
    // No api at call time → core registers a one-shot pywebviewready listener.
    const pending = core.config()
    window.pywebview = { api: fakeApi() }
    window.dispatchEvent(new Event('pywebviewready'))
    expect((await pending).method).toBe('config')
  })

  it('rejects when not running inside the host (timeout, no api)', async () => {
    vi.useFakeTimers()
    const pending = core.config()
    vi.advanceTimersByTime(4000)
    await expect(pending).rejects.toThrow(/not running in the host/)
  })
})
