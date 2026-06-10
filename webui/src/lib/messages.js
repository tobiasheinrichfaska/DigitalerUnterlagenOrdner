// Localizes backend (CoreApi) messages that carry DYNAMIC parts. Static German
// strings localize via a plain t(msg) lookup; the messages below are formatted by
// the Python host (filename, exception text, skipped names baked in), so an exact
// dictionary hit is impossible. Each template here is the exact German wording the
// backend produces (and a key in en.js): reverse-match the raw message back to
// template + variables, then re-emit through t(template, vars) — the static wording
// translates while the dynamic values survive. Pure, UI-free, data-driven.
//
// Keep in sync with core/api.py (_friendly_import_error + the export/import
// warnings) and App.jsx's "Teilweise importiert" composite — messages.test.js
// locks the static fragments against both sources.

export const MESSAGE_TEMPLATES = [
  // whole  = the dynamic tail may itself contain '; ' → match BEFORE the '; ' split.
  // nested = variables that are themselves backend messages → localize recursively.
  { tpl: 'Teilweise importiert — {warning}', nested: ['warning'], whole: true },
  { tpl: 'ungültige Daten: {error}', whole: true },
  { tpl: 'Ohne Seiten übersprungen: {names}', whole: true },
  { tpl: '{name}: Office-Programm zum Konvertieren nicht verfügbar (Word/Excel/PowerPoint erforderlich)' },
  { tpl: '{name}: Dateityp {ext} wird nicht unterstützt' },
  { tpl: '{name}: Datei ist passwortgeschützt' },
  { tpl: '{name}: Archiv/E-Mail konnte nicht gelesen werden ({msg})' },
  { tpl: '{name}: beschädigte oder ungültige Datei' },
]

const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const COMPILED = MESSAGE_TEMPLATES.map(({ tpl, nested = [], whole = false }) => {
  const names = []
  const src = tpl.split(/(\{\w+\})/).map((part) => {
    const m = /^\{(\w+)\}$/.exec(part)
    if (m) { names.push(m[1]); return '([\\s\\S]+?)' }
    return esc(part)
  }).join('')
  return { tpl, nested, whole, names, re: new RegExp(`^${src}$`) }
})

function matchTemplates(t, msg, wholeOnly) {
  for (const { tpl, nested, whole, names, re } of COMPILED) {
    if (whole !== wholeOnly) continue
    const m = re.exec(msg)
    if (m) {
      const vars = {}
      names.forEach((n, i) => { vars[n] = nested.includes(n) ? localizeMessage(t, m[i + 1]) : m[i + 1] })
      return t(tpl, vars)
    }
  }
  return null
}

/** Localize a backend message: whole-message templates (their tail may contain
 *  '; ') → '; '-joined per-file list (localize each part) → per-part templates
 *  (dynamic filename/ext survive) → plain t() lookup. */
export function localizeMessage(t, msg) {
  if (typeof msg !== 'string' || !msg) return msg
  const whole = matchTemplates(t, msg, true)
  if (whole !== null) return whole
  if (msg.includes('; ')) return msg.split('; ').map((p) => localizeMessage(t, p)).join('; ')
  return matchTemplates(t, msg, false) ?? t(msg)
}
