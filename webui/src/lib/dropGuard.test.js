import { describe, it, expect, afterEach } from 'vitest'
import { installDropGuard } from './dropGuard'

// jsdom has no DragEvent: a plain cancelable Event with a dataTransfer stand-in is enough,
// the guard only looks at defaultPrevented.
function fire(type, types = ['Files']) {
  const e = new Event(type, { cancelable: true, bubbles: true })
  e.dataTransfer = { types }
  window.dispatchEvent(e)
  return e
}

describe('installDropGuard (security review H-3)', () => {
  let off
  afterEach(() => off && off())

  it('cancels a dropped file so WebView2 cannot navigate the window to it', () => {
    off = installDropGuard(window)
    expect(fire('dragover').defaultPrevented).toBe(true)
    expect(fire('drop').defaultPrevented).toBe(true)
  })

  it('also cancels non-file drops (a dragged link / text/uri-list navigates too)', () => {
    off = installDropGuard(window)
    expect(fire('drop', ['text/uri-list']).defaultPrevented).toBe(true)
  })

  it('stops guarding after uninstall', () => {
    installDropGuard(window)()
    expect(fire('drop').defaultPrevented).toBe(false)
  })
})
