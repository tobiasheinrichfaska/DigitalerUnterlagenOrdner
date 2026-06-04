// Source-string i18n, dependency-free. The KEY is the German text written inline
// in the UI: t('Öffnen'). German is the default language and needs no dictionary;
// other languages map the German source → their translation. A missing translation
// falls back to the German source, so nothing is ever blank.
//
// Add a language: add a file exporting a { '<German>': '<translated>' } map, then
// register it in TRANSLATIONS + LANGUAGE_NAMES. i18n.test.js checks coverage.
import { en } from './en'

export const TRANSLATIONS = { en } // code -> { '<German source>': '<translation>' }
export const DEFAULT_LANG = 'de'
export const SUPPORTED = ['de', ...Object.keys(TRANSLATIONS)]
export const LANGUAGE_NAMES = { de: 'Deutsch', en: 'English' }

/** Translate German `text` into `lang`, interpolating `{name}` from `vars`.
 *  Default language (or a missing entry) returns the German source unchanged. */
export function translate(lang, text, vars) {
  const dict = TRANSLATIONS[lang]
  let s = (!dict || lang === DEFAULT_LANG) ? text : (dict[text] ?? text)
  if (vars) s = s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m))
  return s
}

/** A valid stored choice → the browser's 2-letter language → DEFAULT_LANG. */
export function resolveInitialLang(stored, navLang) {
  if (stored && SUPPORTED.includes(stored)) return stored
  const short = (navLang || '').slice(0, 2).toLowerCase()
  if (SUPPORTED.includes(short)) return short
  return DEFAULT_LANG
}
