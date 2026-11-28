// Display-time localization of node names that the external archive package bakes
// in as German text ("<name> – nicht importierbar (<reason>)", "Weitere Einträge"…).
// Stored names are never changed; ordinary user names are never translated.
// R11-1: hard length cap (a hostile .belegtool name must never cost render time) and a
// per-translator memo so tree renders do not redo the template work for every row.
import { localizeMessage } from './messages'

const MARKER = ' – nicht importierbar'
const FIXED = new Set(['Weitere Einträge', 'Weitere Anhänge', 'Weitere Teile'])
export const MAX_NAME_LEN = 600
const MEMO_CAP = 2000
const memos = new WeakMap()  // t → Map(name → localized)

function compute(t, name) {
  if (FIXED.has(name)) return t(name)
  if (name.length > MAX_NAME_LEN) return name
  const i = name.indexOf(MARKER + ' (', 1)
  const labelled = (name.endsWith(MARKER) && name.length > MARKER.length)
    || (i >= 1 && name.endsWith(')') && name.length - (i + MARKER.length + 2) >= 2)
  return labelled ? localizeMessage(t, name) : name
}

export function displayName(t, name) {
  if (typeof name !== 'string') return name
  if (name.length > MAX_NAME_LEN) return name
  let memo = memos.get(t)
  if (!memo) { memo = new Map(); memos.set(t, memo) }
  const hit = memo.get(name)
  if (hit !== undefined) return hit
  const out = compute(t, name)
  if (memo.size >= MEMO_CAP) memo.clear()
  memo.set(name, out)
  return out
}
