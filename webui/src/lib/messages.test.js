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

  it('W-9: localizes the PDF-Tool open/lock errors', () => {
    for (const de of [
      'Dieser Knoten ist bereits im PDF-Tool geöffnet.',
      'Dieser Knoten wird gerade im PDF-Tool bearbeitet und kann nicht gleichzeitig geändert werden.',
      'Ordner können nicht im PDF-Tool geöffnet werden.',
      'Knoten hat keine PDF-Daten.',
      'PDF-Tool konnte nicht geöffnet werden.',
    ]) expect(localizeMessage(t, de), de).not.toBe(de)
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
    // that produces the message (core/api.py, formats/pdf_storage.py and
    // formats/toc_export.py for the load/export degradations, or App.jsx for the
    // composites). Resolve from THIS file's location (src/lib/), not process.cwd(),
    // so the test is invocation-independent (F-6).
    const here = dirname(fileURLToPath(import.meta.url))
    const src = readFileSync(resolve(here, '..', '..', '..', 'core', 'api.py'), 'utf8')
      + readFileSync(resolve(here, '..', '..', '..', 'formats', 'pdf_storage.py'), 'utf8')
      + readFileSync(resolve(here, '..', '..', '..', 'formats', 'toc_export.py'), 'utf8')
      + readFileSync(resolve(here, '..', 'App.jsx'), 'utf8')
      + readFileSync(resolve(here, '..', '..', '..', 'universal_importer', 'converters.py'), 'utf8')
      + readFileSync(resolve(here, '..', '..', '..', 'universal_importer', 'importer.py'), 'utf8')
      + readFileSync(resolve(here, '..', '..', '..', 'infra', 'file_lock.py'), 'utf8')
    const joined = src.replace(/"\s*\n\s*(f?)"/g, '')  // implicit Python string concatenation
    for (const { tpl } of MESSAGE_TEMPLATES) {
      // produced by the separate belegtool-archives package (not in this repo's sources)
      if (tpl.startsWith('{name} – nicht importierbar')) continue
      for (const frag of tpl.split(/\{\w+\}/).filter((f) => f.trim().length > 3).map((f) => f.replace(/^: /, ''))) {
        expect(joined.includes(frag) || src.includes(frag), `${tpl} :: missing fragment "${frag}"`).toBe(true)
      }
    }
  })
})

describe('TX-1..4: previously uncovered backend messages localize', () => {
  const CASES = [
    ['a.txt: Textdatei zu groß', 'a.txt: text file too large'],
    ['a.html: HTML-Datei zu groß', 'a.html: HTML file too large'],
    ['a.html: HTML-Datei zu komplex (zu groß)', 'a.html: HTML file too complex (too large)'],
    ['a.html: HTML-Datei zu tief verschachtelt (zu groß)', 'a.html: HTML file nested too deeply (too large)'],
    ['a.pdf: Fehler beim Laden des PDFs: boom', 'a.pdf: error loading the PDF: boom'],
    ['a.belegtool: Baumtiefe überschreitet das Limit von 200 Ebenen.', 'a.belegtool: tree depth exceeds the limit of 200 levels.'],
    ['Baumtiefe überschreitet das Limit von 200 Ebenen.', 'Tree depth exceeds the limit of 200 levels.'],
    ["a.docx: Unerwarteter Inhalt für 'a.docx': die Datei beginnt nicht wie ein .docx.",
      "a.docx: unexpected content for 'a.docx': the file does not start like a .docx."],
    ["a.pdf: 'a.pdf' sieht aus wie ELF-Binärdatei, nicht wie .pdf – abgelehnt.",
      "a.pdf: 'a.pdf' looks like ELF binary, not like .pdf – rejected."],
    ['a.png: Ungültige PDF-Daten erzeugt für: a.png', 'a.png: invalid PDF data produced for: a.png'],
    ['a.png: Ungültige PDF-Daten erzeugt aus Datei: C:\\x\\a.png', 'a.png: invalid PDF data produced from file: C:\\x\\a.png'],
    ['DATEV-Modus ist aus.', 'DATEV mode is off.'],
    ['Dieses Dokument ist nicht (gültig) mit DATEV verknüpft.', 'This document is not (validly) linked to DATEV.'],
    ['Keine Daten zum Zurückschreiben.', 'No data to write back.'],
    ['Keine Daten zum Ablegen.', 'No data to file.'],
    ['Kein Mandant angegeben.', 'No client specified.'],
    ['Keine Verbindung zur DATEV-Schnittstelle.', 'No connection to the DATEV interface.'],
    ['Export lieferte keine Datei.', 'The export produced no file.'],
    ['Kein lokaler Speicherort gebunden.', 'No local save location bound.'],
    ['Ausgecheckte Datei ist nicht beschreibbar.', 'The checked-out file is not writable.'],
    ['Nur 1 von 3 Teil(en) nach DATEV abgelegt — die bereits abgelegten bleiben in DATEV.',
      'Only 1 of 3 part(s) filed to DATEV — those already filed remain in DATEV.'],
    ['Keine Daten zum Speichern.', 'No data to save.'],
    ['Ungültiger Befehl: x; y', 'Invalid command: x; y'],
    ['Datei nicht importierbar: kaputt', 'File cannot be imported: kaputt'],
    ['Dieser Pfad darf nicht direkt geöffnet werden', 'This path cannot be opened directly'],
    ['ungültiger Wert', 'invalid value'],
    ['Unvollständig geschrieben: 5 von 9 Bytes', 'Incompletely written: 5 of 9 bytes'],
    ['Konnte die vorhandene Datei vor dem Speichern nicht sichern: C:\\a.belegtool',
      'Could not back up the existing file before saving: C:\\a.belegtool'],
    ['x.pdf – nicht importierbar', 'x.pdf – not importable'],
    ['x.pdf – nicht importierbar (zu groß)', 'x.pdf – not importable (too large)'],
    ['x.pdf – nicht importierbar (Limit überschritten)', 'x.pdf – not importable (limit exceeded)'],
    ['x.zip – nicht importierbar (zu tief verschachtelt)', 'x.zip – not importable (nested too deeply)'],
    ['Weitere Einträge – nicht importierbar (Limit überschritten)', 'More entries – not importable (limit exceeded)'],
    ['Weitere Anhänge – nicht importierbar (Limit überschritten)', 'More attachments – not importable (limit exceeded)'],
    ['Weitere Teile – nicht importierbar (Limit überschritten)', 'More parts – not importable (limit exceeded)'],
  ]
  for (const [de, enText] of CASES) {
    it(de, () => { expect(localizeMessage(t, de)).toBe(enText) })
  }
})
