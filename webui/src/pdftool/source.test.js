import { describe, it, expect } from 'vitest'
import { chooseSource, base64ToUint8, uint8ToBase64, datevAction } from './source.js'

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

describe('datevAction', () => {
  it('offers write-back for a connected checkout in DATEV mode', () => {
    expect(datevAction({ datevMode: true, connected: true })).toBe('writeback')
  })
  it('offers file-anew for a not-connected pdf in DATEV mode', () => {
    expect(datevAction({ datevMode: true, connected: false })).toBe('file')
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
