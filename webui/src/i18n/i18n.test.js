import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'
import { translate, resolveInitialLang, SUPPORTED, LANGUAGE_NAMES, DEFAULT_LANG, TRANSLATIONS } from './index'
import { en } from './en'

// Lookup maps that use variable-keyed t(MAP[x]) — the literal scanner misses these.
// Import them here and assert each value is a valid en.js key.
import { DOT_LABEL } from '../lib/status'
// STATUS_DE and METHOD_DE are not exported, but their values are known constants:
const STATUS_DE_VALUES = ['Kein Status', 'Erfasst', 'Zu erfassen', 'Vorjahr']
// METHOD_DE values (from PreviewControls.jsx):
const METHOD_DE_VALUES = ['JPEG (Graustufen)', 'JPEG (Farbe)', 'PNG (Graustufen)', 'Struktur (Farbe erhalten)']
// Count plural keys (from App.jsx doExport):
const COUNT_KEYS = ['Eintrag', 'Einträge']

describe('translate (source-string keys)', () => {
  it('returns the German source for the default language', () => {
    expect(translate('de', 'Öffnen')).toBe('Öffnen')
    expect(translate('de', 'Seite {page} / {total}', { page: 2, total: 9 })).toBe('Seite 2 / 9')
  })

  it('translates into another language', () => {
    expect(translate('en-US', 'Öffnen')).toBe('Open')
    expect(translate('en-US', 'Seite {page} / {total}', { page: 2, total: 9 })).toBe('Page 2 / 9')
  })

  it('uses the right regional English spelling', () => {
    expect(translate('en-US', 'JPEG (Graustufen)')).toBe('JPEG (grayscale)')
    expect(translate('en-GB', 'JPEG (Graustufen)')).toBe('JPEG (greyscale)')
    expect(translate('en-US', 'Zu Favoriten')).toBe('Add to favorites')
    expect(translate('en-GB', 'Zu Favoriten')).toBe('Add to favourites')
  })

  it('falls back to the German source when a translation is missing', () => {
    expect(translate('en-US', 'Unübersetzt')).toBe('Unübersetzt') // unknown key → source
    expect(translate('xx', 'Öffnen')).toBe('Öffnen')              // unknown lang → source
  })

  it('leaves unknown placeholders untouched', () => {
    expect(translate('en-US', 'PDF exportiert ({count} {entries})', { count: 3 })).toContain('{entries}')
  })

  it('the en base has the full, fixed key set (lock against silent drift)', () => {
    // Canonical key count = 125 UI strings (incl. the 3 Tree.jsx drag-ghost keys
    // and the ContextMenu aria-label) + 13 backend command-error messages + 14
    // host-level error/warning strings (host.py + core/api.py + lib/messages.js). If
    // a string is added, bump this deliberately — and add it to every full-coverage
    // language file.
    expect(Object.keys(en).length).toBe(152)
  })
})

describe('full-coverage languages', () => {
  // Intentional partials (only attested words; the rest falls back to German).
  const PARTIAL = ['tlh', 'qya', 'sjn']
  const FULL = Object.keys(TRANSLATIONS).filter((c) => !PARTIAL.includes(c))

  // Batch-translate policy (CLAUDE.md i18n): a NEW UI string ships in de + en only;
  // the other full-coverage languages are translated later in one batch. A key listed
  // here MUST exist in en.js (still enforced below) but is exempt from the
  // full-coverage assertion until translated. It falls back to German meanwhile.
  // Empty = nothing pending. Add new UI keys here; the batch pass empties the set.
  const PENDING_TRANSLATIONS = new Set([])

  it.each(FULL)('"%s" has the en key set (minus pending-translation keys)', (code) => {
    // Locks the "n languages = full key set" claim per language — a key silently
    // missing from one map would otherwise just fall back to German unnoticed.
    const keys = new Set(Object.keys(TRANSLATIONS[code]))
    const missing = Object.keys(en).filter((k) => !keys.has(k) && !PENDING_TRANSLATIONS.has(k))
    const extra = [...keys].filter((k) => !(k in en))
    expect(missing, `missing in ${code}`).toEqual([])
    expect(extra, `extra in ${code} (not in en)`).toEqual([])
  })

  it('every PENDING_TRANSLATIONS key still exists in the en base', () => {
    // A pending key may skip the other languages, but must never be untranslated in en
    // (that would ship a raw German t() string in English) — guards misuse of the set.
    const notInEn = [...PENDING_TRANSLATIONS].filter((k) => !(k in en))
    expect(notInEn, 'pending keys must be present in en.js').toEqual([])
  })
})

describe('language registry', () => {
  it('supports de + regional English with display names', () => {
    expect(SUPPORTED).toContain('de')
    expect(SUPPORTED).toContain('en-US')
    expect(SUPPORTED).toContain('en-GB')
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
  const files = ['App.jsx', 'Tree.jsx', 'ContextMenu.jsx', 'PreviewControls.jsx', 'Preview.jsx',
                 'Toolbar.jsx', 'TagEditor.jsx', 'TagViewBar.jsx', 'ExportDialog.jsx', 'HelpModal.jsx',
                 'PreviewPane.jsx', 'SaveDialog.jsx', 'StatusBar.jsx', 'lib/status.js']
  const re = /\bt\(\s*(['"])((?:\\.|(?!\1).)*)\1/g

  // Resolve from THIS file's location (src/i18n/) → src/, not process.cwd(), so the
  // scan is invocation-independent (F-6).
  const srcDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')
  const used = new Set()
  for (const f of files) {
    try {
      const src = readFileSync(resolve(srcDir, f), 'utf8')
      let m
      while ((m = re.exec(src))) used.add(m[2])
    } catch {
      // file not found — skip silently (keeps the list optional)
    }
  }

  it('found a meaningful number of literal t() calls', () => {
    expect(used.size).toBeGreaterThan(30)
  })

  it('every t("German") literal has an English translation', () => {
    const missing = [...used].filter((g) => !(g in en))
    expect(missing).toEqual([])
  })
})

describe('i18n — variable-keyed lookup maps are fully covered', () => {
  // DOT_LABEL values (Tree.jsx uses t(DOT_LABEL[c]))
  it('every DOT_LABEL value is a key in en.js', () => {
    const missing = Object.values(DOT_LABEL).filter((v) => !(v in en))
    expect(missing, 'DOT_LABEL values missing from en.js').toEqual([])
  })

  // STATUS_DE values (ContextMenu.jsx uses t(STATUS_DE[key]))
  it('every STATUS_DE display value is a key in en.js', () => {
    const missing = STATUS_DE_VALUES.filter((v) => !(v in en))
    expect(missing, 'STATUS_DE values missing from en.js').toEqual([])
  })

  // METHOD_DE values (PreviewControls.jsx uses t(METHOD_DE[m]))
  it('every METHOD_DE display value is a key in en.js', () => {
    const missing = METHOD_DE_VALUES.filter((v) => !(v in en))
    expect(missing, 'METHOD_DE values missing from en.js').toEqual([])
  })

  // Count plural keys (App.jsx uses t(resp.count === 1 ? 'Eintrag' : 'Einträge'))
  it('count plural keys (Eintrag / Einträge) are present in en.js', () => {
    const missing = COUNT_KEYS.filter((v) => !(v in en))
    expect(missing, 'count plural keys missing from en.js').toEqual([])
  })
})

describe('resolveInitialLang', () => {
  it('prefers a valid stored choice', () => expect(resolveInitialLang('en-GB', 'de-DE')).toBe('en-GB'))
  it('maps a legacy/generic English choice to en-US', () => {
    expect(resolveInitialLang('en', 'de-DE')).toBe('en-US')
    expect(resolveInitialLang(null, 'en')).toBe('en-US')
  })
  it('matches the exact browser locale, else the 2-letter language', () => {
    expect(resolveInitialLang(null, 'en-US')).toBe('en-US')
    expect(resolveInitialLang(null, 'en-GB')).toBe('en-GB')
    expect(resolveInitialLang('xx', 'de-AT')).toBe('de')
  })
  it('defaults when nothing matches', () => expect(resolveInitialLang(null, 'it-IT')).toBe(DEFAULT_LANG))
})
