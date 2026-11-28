import { describe, it, expect } from 'vitest'
import { displayName } from './displayName'
import { translate } from '../i18n/index'

const t = (key, vars) => translate('en-US', key, vars)

describe('displayName (TX-4: archive labels baked into node names)', () => {
  it('localizes archive member labels at display time', () => {
    expect(displayName(t, 'a.zip – nicht importierbar')).toBe('a.zip – not importable')
    expect(displayName(t, 'a.zip – nicht importierbar (zu groß)')).toBe('a.zip – not importable (too large)')
    expect(displayName(t, 'x.msg – nicht importierbar (Limit überschritten)')).toContain('not importable (')
    expect(displayName(t, 'x.msg – nicht importierbar (zu tief verschachtelt)')).not.toContain('zu tief')
    expect(displayName(t, 'Weitere Einträge')).toBe('More entries')
    expect(displayName(t, 'Weitere Anhänge')).toBe('More attachments')
    expect(displayName(t, 'Weitere Teile')).toBe('More parts')
  })
  it('leaves ordinary names untouched', () => {
    expect(displayName(t, 'Rechnung.pdf')).toBe('Rechnung.pdf')
    expect(displayName(t, 'Ordner')).toBe('Ordner')
    expect(displayName(t, 'Speichern')).toBe('Speichern')
    expect(displayName(t, '')).toBe('')
    expect(displayName(t, undefined)).toBe(undefined)
  })
  it('is the identity in German', () => {
    const de = (k, v) => translate('de', k, v)
    expect(displayName(de, 'a.zip – nicht importierbar (zu groß)')).toBe('a.zip – nicht importierbar (zu groß)')
  })
})

describe('displayName is linear + memoised (R11-1)', () => {
  it('adversarial long names return unchanged in < 50 ms', () => {
    for (const n of [5000, 50000]) {
      const name = ": 'a' sieht aus wie ".repeat(n / 20) + ', nicht wie '.repeat(n / 12) + ' – nicht importierbar'
      const t0 = performance.now()
      expect(displayName(t, name)).toBe(name)
      expect(performance.now() - t0).toBeLessThan(50)
    }
  })
  it('memoises per (t, name): the translator is not re-run', () => {
    let calls = 0
    const counting = (k, v) => { calls += 1; return t(k, v) }
    const first = displayName(counting, 'b.zip – nicht importierbar')
    const c1 = calls
    expect(displayName(counting, 'b.zip – nicht importierbar')).toBe(first)
    expect(calls).toBe(c1)
  })
})
