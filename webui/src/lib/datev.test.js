import { describe, it, expect } from 'vitest'
import { isDatevConnected, datevVerdictKey, DATEV_VERDICT_KEY } from './datev'

describe('isDatevConnected', () => {
  it('true only with both doc_guid and file_id', () => {
    expect(isDatevConnected({ doc_guid: 'g', file_id: 12 })).toBe(true)
    expect(isDatevConnected({ doc_guid: 'g', file_id: 0 })).toBe(true) // 0 is a valid id
  })
  it('false when provenance is missing or incomplete', () => {
    expect(isDatevConnected(null)).toBe(false)
    expect(isDatevConnected(undefined)).toBe(false)
    expect(isDatevConnected({ doc_guid: 'g' })).toBe(false)         // no file_id
    expect(isDatevConnected({ file_id: 12 })).toBe(false)           // no doc_guid
    expect(isDatevConnected({ doc_guid: 'g', file_id: null })).toBe(false)
  })
})

describe('datevVerdictKey', () => {
  it('maps each non-ok verdict to its own message key', () => {
    for (const v of ['locked', 'conflict_changed', 'conflict_content', 'no_structure_item']) {
      expect(datevVerdictKey(v)).toBe(DATEV_VERDICT_KEY[v])
      expect(datevVerdictKey(v)).toContain('DATEV')
    }
  })
  it('falls back to a generic failure for unknown/undefined verdicts', () => {
    expect(datevVerdictKey('weird')).toBe('DATEV-Rückschreiben fehlgeschlagen.')
    expect(datevVerdictKey(undefined)).toBe('DATEV-Rückschreiben fehlgeschlagen.')
  })
})
