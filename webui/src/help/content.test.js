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

  it('falls back to English for an unauthored language', () => {
    expect(helpFor('tlh')).toBe(HELP.en)
    expect(helpFor('de')).toBe(HELP.de)
  })
})
