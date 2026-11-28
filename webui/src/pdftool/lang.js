// Translator for the vanilla-DOM PDF-Tool surface: same source-string i18n and the same stored
// language choice as the organizer (localStorage 'beleg.lang', else the browser locale).
import { translate, resolveInitialLang } from '../i18n/index.js'

export function currentLang() {
  let stored = null
  try { stored = localStorage.getItem('beleg.lang') } catch { /* blocked storage */ }
  return resolveInitialLang(stored, typeof navigator !== 'undefined' ? navigator.language : '')
}

export const toolT = (text, vars) => translate(currentLang(), text, vars)
