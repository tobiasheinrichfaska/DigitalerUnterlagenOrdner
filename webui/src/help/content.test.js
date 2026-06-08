import { describe, it, expect } from 'vitest'
import { HELP, helpFor } from './content'

describe('help content', () => {
  it('authored languages exist and share the same section set', () => {
    expect(Object.keys(HELP)).toEqual(expect.arrayContaining(['de', 'en', 'fr', 'es']))
    const titlesOf = (l) => HELP[l].map((s) => s.t).length
    expect(titlesOf('en')).toBe(titlesOf('de'))
    expect(titlesOf('fr')).toBe(titlesOf('de'))
    expect(titlesOf('es')).toBe(titlesOf('de'))
  })

  it('every section has a title and at least one item', () => {
    for (const l of Object.keys(HELP)) {
      for (const s of HELP[l]) {
        expect(s.t).toBeTruthy()
        expect(s.items.length).toBeGreaterThan(0)
      }
    }
  })

  it('falls back to English for an unknown language code', () => {
    expect(helpFor('xx')).toBe(HELP.en)
    expect(helpFor('de')).toBe(HELP.de)
    expect(helpFor('tlh')).toBe(HELP.tlh)   // authored (best-effort)
    expect(helpFor('qya')).toBe(HELP.qya)   // Quenya authored (best-effort)
    expect(helpFor('en-GB')).toBe(HELP.en)  // regional English → English help
  })

  it('has an entry for every authored language', () => {
    // de + en + en-US/en-GB + 17 others (incl. qya/sjn best-effort Elvish) = 23
    expect(Object.keys(HELP)).toHaveLength(23)
    expect(Object.keys(HELP)).toEqual(expect.arrayContaining(['en-US', 'en-GB', 'qya', 'sjn']))
  })
})
