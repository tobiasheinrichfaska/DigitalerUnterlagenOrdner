// Localizes backend (CoreApi) messages that carry DYNAMIC parts. Static German
// strings localize via a plain t(msg) lookup; the messages below are formatted by
// the Python host (filename, exception text, skipped names baked in), so an exact
// dictionary hit is impossible. Each template here is the exact German wording the
// backend produces (and a key in en.js): reverse-match the raw message back to
// template + variables, then re-emit through t(template, vars) — the static wording
// translates while the dynamic values survive. Pure, UI-free, data-driven.
//
// Keep in sync with core/api.py (_friendly_import_error + the export/import
// warnings), formats/pdf_storage.py + formats/toc_export.py (the load/export
// integrity warnings) and App.jsx's composites ("Teilweise importiert",
// "Datei beschädigt geladen") — messages.test.js locks the static fragments
// against all four sources.

export const MESSAGE_TEMPLATES = [
  // whole  = the dynamic tail may itself contain '; ' → match BEFORE the '; ' split.
  // nested = variables that are themselves backend messages → localize recursively.
  { tpl: 'Teilweise importiert — {warning}', nested: ['warning'], whole: true },
  // degraded .belegtool load (H-1/M-3, 2026-11-04) — composed in App.jsx, parts from pdf_storage
  { tpl: 'Datei beschädigt geladen: {warning} — Speichern legt eine neue Datei an.', nested: ['warning'], whole: true },
  { tpl: '{name}: Datei beschädigt – nicht importiert: {warning}', nested: ['warning'], whole: true },
  { tpl: '{name}: beginnt hinter dem Seitenende – übersprungen' },
  { tpl: '{name}: ragt über das Seitenende hinaus – gekürzt' },
  { tpl: '{name}: ungültige Seitenanzahl ({value})' },
  { tpl: '{n} Seiten mehr als die Struktur beschreibt – nicht zugeordnet' },
  { tpl: '{name}: Seiten fehlen im Export (Quelldaten beschädigt oder Seitenzahl falsch)' },
  { tpl: 'ungültige Daten: {error}', whole: true },
  { tpl: 'Ohne Seiten übersprungen: {names}', whole: true },
  { tpl: '{name}: Office-Programm zum Konvertieren nicht verfügbar (Word/Excel/PowerPoint erforderlich)' },
  { tpl: '{name}: Dateityp {ext} wird nicht unterstützt' },
  { tpl: '{name}: Datei ist passwortgeschützt' },
  { tpl: '{name}: Datei enthält keine lesbaren Seiten' },
  { tpl: '{name}: Archiv/E-Mail konnte nicht gelesen werden ({msg})' },
  { tpl: '{name}: beschädigte oder ungültige Datei' },
  { tpl: '{name}: Dokument verweist auf eine externe Vorlage/Quelle und wird aus Sicherheitsgründen nicht importiert' },
  // TX-1..4 (audit x2): import/load/DATEV/archive messages with dynamic parts
  { tpl: '{name}: Textdatei zu groß' },
  { tpl: '{name}: HTML-Datei zu groß' },
  { tpl: '{name}: HTML-Datei zu komplex (zu groß)' },
  { tpl: '{name}: HTML-Datei zu tief verschachtelt (zu groß)' },
  { tpl: '{name}: Fehler beim Laden des PDFs: {error}' },
  { tpl: '{name}: Baumtiefe überschreitet das Limit von {n} Ebenen.' },
  { tpl: 'Baumtiefe überschreitet das Limit von {n} Ebenen.' },
  { tpl: "{name}: Unerwarteter Inhalt für '{file}': die Datei beginnt nicht wie ein {ext}." },
  { tpl: "{name}: '{file}' sieht aus wie {label}, nicht wie {ext} – abgelehnt.", nested: ['label'] },
  { tpl: '{name}: Ungültige PDF-Daten erzeugt für: {file}' },
  { tpl: '{name}: Ungültige PDF-Daten erzeugt aus Datei: {file}' },
  { tpl: 'Nur {done} von {total} Teil(en) nach DATEV abgelegt — die bereits abgelegten bleiben in DATEV.' },
  { tpl: 'Ungültiger Befehl: {error}', whole: true },
  { tpl: 'Datei nicht importierbar: {error}', whole: true },
  { tpl: 'Unvollständig geschrieben: {written} von {n} Bytes' },
  { tpl: 'Konnte die vorhandene Datei vor dem Speichern nicht sichern: {path}', whole: true },
  { tpl: '{name} – nicht importierbar ({reason})', nested: ['name', 'reason'] },
  { tpl: '{name} – nicht importierbar', nested: ['name'] },
]

// Linear matcher (R11-1): a template is split into its fixed literals; the variables are the
// non-empty gaps between them. Literals are located left-to-right with indexOf (the first
// after the previous one) and the last literal must be a suffix — the same captures the old
// lazy `([\s\S]+?)` regex produced, but without any backtracking (no regex at all).
const COMPILED = MESSAGE_TEMPLATES.map(({ tpl, nested = [], whole = false }) => {
  const names = []
  const lits = ['']
  for (const part of tpl.split(/(\{\w+\})/)) {
    const m = /^\{(\w+)\}$/.exec(part)
    if (m) { names.push(m[1]); lits.push('') } else lits[lits.length - 1] += part
  }
  return { tpl, nested, whole, names, lits }
})

function matchLiterals(msg, lits) {
  const k = lits.length - 1
  if (k === 0) return msg === lits[0] ? [] : null
  if (!msg.startsWith(lits[0])) return null
  const end = msg.length - lits[k].length
  if (end < 0 || !msg.endsWith(lits[k])) return null
  const out = []
  let pos = lits[0].length
  for (let i = 1; i < k; i += 1) {
    const idx = msg.indexOf(lits[i], pos + 1)
    if (idx < 0 || idx + lits[i].length > end) return null
    out.push(msg.slice(pos, idx))
    pos = idx + lits[i].length
  }
  if (end < pos + 1) return null
  out.push(msg.slice(pos, end))
  return out
}

/** Hard input cap: longer strings are returned as-is (never regex/scan-processed). */
export const MAX_LOCALIZE_LEN = 2000

function matchTemplates(t, msg, wholeOnly) {
  for (const { tpl, nested, whole, names, lits } of COMPILED) {
    if (whole !== wholeOnly) continue
    const m = matchLiterals(msg, lits)
    if (m) {
      const vars = {}
      names.forEach((n, i) => { vars[n] = nested.includes(n) ? localizeMessage(t, m[i]) : m[i] })
      return t(tpl, vars)
    }
  }
  return null
}

/** Localize a backend message: whole-message templates (their tail may contain
 *  '; ') → '; '-joined per-file list (localize each part) → per-part templates
 *  (dynamic filename/ext survive) → plain t() lookup. */
export function localizeMessage(t, msg) {
  if (typeof msg !== 'string' || !msg || msg.length > MAX_LOCALIZE_LEN) return msg
  const whole = matchTemplates(t, msg, true)
  if (whole !== null) return whole
  if (msg.includes('; ')) return msg.split('; ').map((p) => localizeMessage(t, p)).join('; ')
  return matchTemplates(t, msg, false) ?? t(msg)
}
