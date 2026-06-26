import { describe, it, expect } from 'vitest'
import { chooseSource, base64ToUint8 } from './source.js'

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
})

describe('base64ToUint8', () => {
  it('decodes base64 to the original bytes', () => {
    const b64 = btoa('PDFdata')
    expect(Array.from(base64ToUint8(b64)))
      .toEqual(Array.from(new TextEncoder().encode('PDFdata')))
  })
})
