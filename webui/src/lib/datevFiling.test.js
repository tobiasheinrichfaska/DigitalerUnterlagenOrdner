import { describe, it, expect } from 'vitest'
import { filterClients, registersFor, yearChoices, validateFiling, dateToIso, buildFileOpts, MONTHS, soleClientGuid }
  from './datevFiling'

const CLIENTS = [
  { guid: 'g1', number: '10001', name: 'Alpha AG' },
  { guid: 'g2', number: '10002', name: 'Beta GmbH' },
  { guid: 'g3', number: '20015', name: 'Gamma Alpha KG' },
]

describe('filterClients', () => {
  it('returns all for an empty query', () => {
    expect(filterClients(CLIENTS, '')).toHaveLength(3)
    expect(filterClients(CLIENTS, '   ')).toHaveLength(3)
  })
  it('matches on number', () => {
    expect(filterClients(CLIENTS, '1000').map((c) => c.guid)).toEqual(['g1', 'g2'])
  })
  it('matches on name, case-insensitive', () => {
    expect(filterClients(CLIENTS, 'beta').map((c) => c.guid)).toEqual(['g2'])
  })
  it('requires ALL whitespace-separated terms to match', () => {
    expect(filterClients(CLIENTS, 'alpha kg').map((c) => c.guid)).toEqual(['g3'])
    expect(filterClients(CLIENTS, 'alpha').map((c) => c.guid)).toEqual(['g1', 'g3'])
  })
})

describe('soleClientGuid', () => {
  // Regression — "clients can only be selected when there's more than one; one won't activate Save":
  // a single match must auto-select so a 1-option listbox (which doesn't fire change on click in
  // WebView2) still enables Ablegen. 0 or >1 matches stay ambiguous (null).
  it('returns the guid when exactly one client matches', () => {
    expect(soleClientGuid([{ guid: 'g1' }])).toBe('g1')
  })
  it('returns null for zero or multiple matches', () => {
    expect(soleClientGuid([])).toBeNull()
    expect(soleClientGuid([{ guid: 'g1' }, { guid: 'g2' }])).toBeNull()
    expect(soleClientGuid(null)).toBeNull()
  })
})

describe('registersFor', () => {
  const placements = [
    { id: 177, name: 'Stammakte', registers: [{ id: 461, name: 'Korr' }] },
    { id: 178, name: 'Jahresakte', registers: [] },
  ]
  it('returns the chosen folder registers', () => {
    expect(registersFor(placements, 177)).toEqual([{ id: 461, name: 'Korr' }])
    expect(registersFor(placements, '177')).toEqual([{ id: 461, name: 'Korr' }]) // string id from a <select>
  })
  it('empty for no/unknown folder', () => {
    expect(registersFor(placements, '')).toEqual([])
    expect(registersFor(placements, 999)).toEqual([])
  })
})

describe('yearChoices', () => {
  it('current year back N, descending', () => {
    expect(yearChoices(2026, 3)).toEqual([2026, 2025, 2024, 2023])
  })
  it('empty for a non-number', () => expect(yearChoices('nope')).toEqual([]))
})

describe('validateFiling', () => {
  it('requires a client (no client → no safe target)', () => {
    expect(validateFiling({}).ok).toBe(false)
    expect(validateFiling({ clientGuid: 'g1', description: 'Rechnung' }).ok).toBe(true)
  })
  // Regression — the v3.11.0 "pdf lacks Name when saving to datev" bug: a filing with a client
  // but a blank/whitespace Bezeichnung must be REFUSED so DATEV never gets a nameless document.
  it('requires a non-blank Bezeichnung (the DATEV document name)', () => {
    expect(validateFiling({ clientGuid: 'g1' }).ok).toBe(false)
    expect(validateFiling({ clientGuid: 'g1', description: '' }).ok).toBe(false)
    expect(validateFiling({ clientGuid: 'g1', description: '   ' }).ok).toBe(false)
    expect(validateFiling({ clientGuid: 'g1', description: '   ' }).error).toMatch(/Bezeichnung/)
    expect(validateFiling({ clientGuid: 'g1', description: 'Rechnung 2024' }).ok).toBe(true)
  })
  it('rejects a month without a year', () => {
    const v = validateFiling({ clientGuid: 'g1', description: 'X', fiscalMonth: 3 })
    expect(v.ok).toBe(false)
    expect(v.error).toMatch(/Jahr/)
  })
  it('accepts a year without a month', () => {
    expect(validateFiling({ clientGuid: 'g1', description: 'X', fiscalYear: 2025 }).ok).toBe(true)
  })
})

describe('dateToIso', () => {
  it('turns yyyy-mm-dd into local-midnight ISO', () => {
    expect(dateToIso('2025-03-14')).toBe('2025-03-14T00:00:00')
  })
  it('passes through empty/other', () => {
    expect(dateToIso('')).toBeNull()
    expect(dateToIso(null)).toBeNull()
  })
})

describe('buildFileOpts', () => {
  it('includes only the set fields, numbers coerced', () => {
    expect(buildFileOpts({ clientGuid: 'g1', description: 'Rechnung 2024', folderId: '177',
      registerId: '461', documentDate: '2025-03-14', fiscalYear: '2025', fiscalMonth: '3' })).toEqual({
      clientGuid: 'g1', description: 'Rechnung 2024', folderId: 177, registerId: 461,
      documentDate: '2025-03-14T00:00:00', fiscalYear: 2025, fiscalMonth: 3,
    })
  })
  it('carries a trimmed Bezeichnung as description (the DATEV name)', () => {
    expect(buildFileOpts({ clientGuid: 'g1', description: '  Beleg  ' }))
      .toEqual({ clientGuid: 'g1', description: 'Beleg' })
  })
  it('omits empty optionals (blank Bezeichnung dropped — validateFiling already refuses it)', () => {
    expect(buildFileOpts({ clientGuid: 'g1' })).toEqual({ clientGuid: 'g1' })
    expect(buildFileOpts({ clientGuid: 'g1', description: '  ' })).toEqual({ clientGuid: 'g1' })
  })
})

describe('MONTHS', () => {
  it('is 1..12', () => expect(MONTHS).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]))
})
