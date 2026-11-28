// Display-time localization of node names that the external archive package bakes
// in as German text ("<name> – nicht importierbar (<reason>)", "Weitere Einträge"…).
// Stored names are never changed; ordinary user names are never translated.
import { localizeMessage } from './messages'

const ARCHIVE_LABEL = /^[\s\S]+ – nicht importierbar(?: \([\s\S]+\))?$/
const FIXED = new Set(['Weitere Einträge', 'Weitere Anhänge', 'Weitere Teile'])

export function displayName(t, name) {
  if (typeof name !== 'string') return name
  if (FIXED.has(name)) return t(name)
  return ARCHIVE_LABEL.test(name) ? localizeMessage(t, name) : name
}
