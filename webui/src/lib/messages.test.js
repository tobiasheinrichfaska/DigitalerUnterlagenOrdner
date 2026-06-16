import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'
import { localizeMessage, MESSAGE_TEMPLATES } from './messages'
import { translate } from '../i18n/index'
import { en } from '../i18n/en'

const t = (key, vars) => translate('en-US', key, vars)

describe('localizeMessage (host-level backend messages)', () => {
  it('localizes static backend strings via the plain t() lookup', () => {
    expect(localizeMessage(t, 'nichts zu exportieren')).toBe('nothing to export')
    expect(localizeMessage(t,
      'Diese Datei wird bereits bearbeitet und kann nur von einer Person gleichzeitig geöffnet werden.'))
      .toBe('This file is already being edited and can only be opened by one person at a time.')
  })

  it('keeps the dynamic part of "ungültige Daten: …"', () => {
    expect(localizeMessage(t, 'ungültige Daten: Incorrect padding'))
      .toBe('invalid data: Incorrect padding')
  })

  it('localizes the per-file import errors, filename and extension surviving', () => {
    expect(localizeMessage(t, 'scan.xyz: Dateityp .xyz wird nicht unterstützt'))
      .toBe('scan.xyz: file type .xyz is not supported')
    expect(localizeMessage(t, 'geheim.pdf: Datei ist passwortgeschützt'))
      .toBe('geheim.pdf: file is password-protected')
    expect(localizeMessage(t, 'kaputt.zip: Archiv/E-Mail konnte nicht gelesen werden (Bad magic number)'))
      .toBe('kaputt.zip: archive/email could not be read (Bad magic number)')
    expect(localizeMessage(t, 'alt.doc: Office-Programm zum Konvertieren nicht verfügbar (Word/Excel/PowerPoint erforderlich)'))
      .toBe('alt.doc: Office program for conversion not available (Word/Excel/PowerPoint required)')
    expect(localizeMessage(t, 'müll.pdf: beschädigte oder ungültige Datei'))
      .toBe('müll.pdf: damaged or invalid file')
    expect(localizeMessage(t, 'brief.docx: Dokument verweist auf eine externe Vorlage/Quelle und wird aus Sicherheitsgründen nicht importiert'))
      .toBe('brief.docx: document references an external template/source and was not imported for security reasons')
  })

  it('localizes a "; "-joined multi-file warning part by part', () => {
    expect(localizeMessage(t, 'a.pdf: Datei ist passwortgeschützt; b.xyz: Dateityp .xyz wird nicht unterstützt'))
      .toBe('a.pdf: file is password-protected; b.xyz: file type .xyz is not supported')
  })

  it('localizes the composite "Teilweise importiert — …" including the nested warning', () => {
    expect(localizeMessage(t, 'Teilweise importiert — geheim.pdf: Datei ist passwortgeschützt'))
      .toBe('Partially imported — geheim.pdf: file is password-protected')
  })

  it('localizes the export skip warning with the names intact', () => {
    expect(localizeMessage(t, 'Ohne Seiten übersprungen: Leer 1, Leer 2'))
      .toBe('Skipped (no pages): Leer 1, Leer 2')
  })

  it('passes unknown messages through unchanged (German source fallback)', () => {
    expect(localizeMessage(t, 'Völlig unbekannter Fehler: xyz')).toBe('Völlig unbekannter Fehler: xyz')
    expect(localizeMessage(t, '')).toBe('')
    expect(localizeMessage(t, null)).toBe(null)
  })

  it('every template is a key in en.js (translation exists)', () => {
    for (const { tpl } of MESSAGE_TEMPLATES) {
      expect(typeof en[tpl], tpl).toBe('string')
    }
  })

  it('templates match what the backend actually formats (drift lock)', () => {
    // The static fragments of each template must appear verbatim in the source
    // that produces the message (core/api.py, or App.jsx for the composite).
    // Resolve from THIS file's location (src/lib/), not process.cwd(), so the test
    // is invocation-independent (F-6).
    const here = dirname(fileURLToPath(import.meta.url))
    const src = readFileSync(resolve(here, '..', '..', '..', 'core', 'api.py'), 'utf8')
      + readFileSync(resolve(here, '..', 'App.jsx'), 'utf8')
    for (const { tpl } of MESSAGE_TEMPLATES) {
      for (const frag of tpl.split(/\{\w+\}/).filter((f) => f.trim().length > 3)) {
        expect(src.includes(frag), `${tpl} :: missing fragment "${frag}"`).toBe(true)
      }
    }
  })
})
