import { describe, it, expect } from 'vitest'
import { chooseSource, readyBridge, base64ToUint8, uint8ToBase64, datevAction } from './source.js'

describe('chooseSource', () => {
  it('uses the bridge when a .pdf is bound in the host', () => {
    expect(chooseSource({
      hasBridge: true,
      cfg: { startup_kind: 'pdf', startup_path: 'C:/x.pdf' },
      fileParam: null,
    })).toEqual({ mode: 'bridge', path: 'C:/x.pdf' })
  })

  it('falls back to the sample URL with no bridge', () => {
    expect(chooseSource({ hasBridge: false, cfg: null, fileParam: null }))
      .toEqual({ mode: 'url', url: '/spike-form.pdf' })
  })

  it('honours the ?file= param', () => {
    expect(chooseSource({ hasBridge: false, cfg: null, fileParam: '/other.pdf' }))
      .toEqual({ mode: 'url', url: '/other.pdf' })
  })

  it('ignores the bridge for a non-pdf startup kind (organizer route)', () => {
    expect(chooseSource({
      hasBridge: true,
      cfg: { startup_kind: 'belegtool', startup_path: 'C:/x.belegtool' },
      fileParam: null,
    })).toEqual({ mode: 'url', url: '/spike-form.pdf' })
  })

  it('ignores the bridge when a pdf kind has no path', () => {
    expect(chooseSource({ hasBridge: true, cfg: { startup_kind: 'pdf' }, fileParam: null }))
      .toEqual({ mode: 'url', url: '/spike-form.pdf' })
  })

  it('uses the pre-bound session for a node binding', () => {
    expect(chooseSource({
      hasBridge: true,
      cfg: { startup_kind: 'node', startup_session: 'sess-123' },
      fileParam: null,
    })).toEqual({ mode: 'session', session: 'sess-123' })
  })
})

describe('readyBridge', () => {
  const METHODS = ['config', 'get_pdf_bytes', 'open']
  const fn = () => {}

  it('returns null when there is no host at all (plain browser / e2e)', () => {
    expect(readyBridge({}, METHODS)).toBeNull()
    expect(readyBridge({ pywebview: {} }, METHODS)).toBeNull()
  })

  it('returns null while a 2nd window has .api but its methods are NOT bound yet', () => {
    // The spike-form regression: the old guard returned the api the instant it existed,
    // so a startup call hit "api.config is not a function" and fell through to the sample.
    const win = { pywebview: { api: { config: fn } } }  // get_pdf_bytes/open not bound yet
    expect(readyBridge(win, METHODS)).toBeNull()
  })

  it('returns the api once every needed method is bound', () => {
    const api = { config: fn, get_pdf_bytes: fn, open: fn }
    expect(readyBridge({ pywebview: { api } }, METHODS)).toBe(api)
  })
})

describe('datevAction', () => {
  it('offers write-back for a connected checkout that is NOT checked out', () => {
    expect(datevAction({ datevMode: true, connected: true, checkedOut: false })).toBe('writeback')
    expect(datevAction({ datevMode: true, connected: true })).toBe('writeback')  // default not-checked-out
  })
  it('offers NO write-back for a connected doc that IS checked out (use 💾 Speichern + check in)', () => {
    expect(datevAction({ datevMode: true, connected: true, checkedOut: true })).toBeNull()
  })
  it('offers file-anew for a not-connected pdf in DATEV mode (checkout state irrelevant)', () => {
    expect(datevAction({ datevMode: true, connected: false })).toBe('file')
    expect(datevAction({ datevMode: true, connected: false, checkedOut: true })).toBe('file')
  })
  it('offers nothing when DATEV mode is off', () => {
    expect(datevAction({ datevMode: false, connected: true })).toBeNull()
    expect(datevAction({ datevMode: false, connected: false })).toBeNull()
  })
})

describe('base64ToUint8', () => {
  it('decodes base64 to the original bytes', () => {
    const b64 = btoa('PDFdata')
    expect(Array.from(base64ToUint8(b64)))
      .toEqual(Array.from(new TextEncoder().encode('PDFdata')))
  })
})

describe('uint8ToBase64', () => {
  it('round-trips with base64ToUint8', () => {
    const bytes = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0, 255, 128, 1, 2, 3])  // %PDF + edges
    expect(Array.from(base64ToUint8(uint8ToBase64(bytes)))).toEqual(Array.from(bytes))
  })

  it('handles a payload larger than the 0x8000 chunk size', () => {
    const big = new Uint8Array(0x8000 * 2 + 17).map((_, i) => i % 256)
    expect(Array.from(base64ToUint8(uint8ToBase64(big)))).toEqual(Array.from(big))
  })
})
