import { describe, it, expect } from 'vitest'
import { isDatevConnected, datevVerdictKey, DATEV_VERDICT_KEY,
  localBaseName, datevSavedNotice } from './datev'

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

describe('localBaseName', () => {
  it('takes the file name from a Windows or POSIX path', () => {
    expect(localBaseName('C:\\Kanzlei\\Rechnung.belegtool')).toBe('Rechnung.belegtool')
    expect(localBaseName('/tmp/abc/1085411.pdf')).toBe('1085411.pdf')
  })
  it('is empty for a missing path', () => {
    expect(localBaseName(null)).toBe('')
    expect(localBaseName(undefined)).toBe('')
  })
})

describe('datevSavedNotice', () => {
  it('appends the saved file name so the .belegtool/.pdf format is explicit', () => {
    expect(datevSavedNotice('Nach DATEV zurückgeschrieben',
      { local_saved: 'C:\\K\\Rechnung.belegtool' }))
      .toBe('Nach DATEV zurückgeschrieben · Rechnung.belegtool')
    expect(datevSavedNotice('Nach DATEV zurückgeschrieben', { local_saved: '/t/1085411.pdf' }))
      .toBe('Nach DATEV zurückgeschrieben · 1085411.pdf')
  })
  it('is the bare message when nothing was saved locally', () => {
    expect(datevSavedNotice('In DATEV abgelegt', { local_saved: null })).toBe('In DATEV abgelegt')
    expect(datevSavedNotice('In DATEV abgelegt', {})).toBe('In DATEV abgelegt')
  })
})
