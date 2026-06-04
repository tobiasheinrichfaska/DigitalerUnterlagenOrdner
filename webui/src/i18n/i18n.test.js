import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import { translate, resolveInitialLang, SUPPORTED, LANGUAGE_NAMES, DEFAULT_LANG, TRANSLATIONS } from './index'
import { en } from './en'

describe('translate (source-string keys)', () => {
  it('returns the German source for the default language', () => {
    expect(translate('de', 'Öffnen')).toBe('Öffnen')
    expect(translate('de', 'Seite {page} / {total}', { page: 2, total: 9 })).toBe('Seite 2 / 9')
  })

  it('translates into another language', () => {
    expect(translate('en', 'Öffnen')).toBe('Open')
    expect(translate('en', 'Seite {page} / {total}', { page: 2, total: 9 })).toBe('Page 2 / 9')
  })

  it('falls back to the German source when a translation is missing', () => {
    expect(translate('en', 'Unübersetzt')).toBe('Unübersetzt')   // unknown key → source
    expect(translate('xx', 'Öffnen')).toBe('Öffnen')             // unknown lang → source
  })

  it('leaves unknown placeholders untouched', () => {
    expect(translate('en', 'PDF exportiert ({count} {entries})', { count: 3 })).toContain('{entries}')
  })
})

describe('language registry', () => {
  it('supports de + en with display names', () => {
    expect(SUPPORTED).toContain('de')
    expect(SUPPORTED).toContain('en')
    for (const code of SUPPORTED) expect(typeof LANGUAGE_NAMES[code]).toBe('string')
  })

  it.each(Object.keys(TRANSLATIONS))('"%s" values are non-empty strings with matching {placeholders}', (code) => {
    const ph = (s) => (s.match(/\{(\w+)\}/g) || []).sort().join(',')
    for (const [src, val] of Object.entries(TRANSLATIONS[code])) {
      expect(typeof val, src).toBe('string')
      expect(val.length, src).toBeGreaterThan(0)
      expect(ph(val), src).toBe(ph(src)) // translation keeps the source's placeholders
    }
  })
})

describe('translation coverage', () => {
  // Scan the components for literal t('…') / t("…") calls and require an English
  // entry for each — so a newly-added German string can't ship untranslated.
  const files = ['App.jsx', 'Tree.jsx', 'ContextMenu.jsx', 'PreviewControls.jsx', 'Preview.jsx']
  const re = /\bt\(\s*(['"])((?:\\.|(?!\1).)*)\1/g

  const used = new Set()
  for (const f of files) {
    const src = readFileSync(resolve(process.cwd(), 'src', f), 'utf8')
    let m
    while ((m = re.exec(src))) used.add(m[2])
  }

  it('found a meaningful number of literal t() calls', () => {
    expect(used.size).toBeGreaterThan(30)
  })

  it('every t("German") literal has an English translation', () => {
    const missing = [...used].filter((g) => !(g in en))
    expect(missing).toEqual([])
  })
})

describe('resolveInitialLang', () => {
  it('prefers a valid stored choice', () => expect(resolveInitialLang('en', 'de-DE')).toBe('en'))
  it('uses the browser 2-letter language', () => {
    expect(resolveInitialLang(null, 'en-US')).toBe('en')
    expect(resolveInitialLang('xx', 'de-AT')).toBe('de')
  })
  it('defaults when nothing matches', () => expect(resolveInitialLang(null, 'fr-FR')).toBe(DEFAULT_LANG))
})
