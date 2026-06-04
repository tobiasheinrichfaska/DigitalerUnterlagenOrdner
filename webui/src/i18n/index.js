// Source-string i18n, dependency-free. The KEY is the German text written inline
// in the UI: t('Öffnen'). German is the default language and needs no dictionary;
// other languages map the German source → their translation. A missing translation
// falls back to the German source, so nothing is ever blank.
//
// Add a language: add a file exporting a { '<German>': '<translated>' } map, then
// register it in TRANSLATIONS + LANGUAGE_NAMES. i18n.test.js checks coverage.
import { en } from './en'
import { fr } from './fr'
import { es } from './es'
import { la } from './la'
import { ko } from './ko'
import { tlh } from './tlh'
import { ru } from './ru'
import { uk } from './uk'
import { hr } from './hr'
import { yi } from './yi'
import { mnn } from './mnn'

export const TRANSLATIONS = { en, fr, es, la, ko, tlh, ru, uk, hr, yi, mnn } // code -> { '<German source>': '<translation>' }
export const DEFAULT_LANG = 'de'
export const SUPPORTED = ['de', ...Object.keys(TRANSLATIONS)]
export const LANGUAGE_NAMES = {
  de: 'Deutsch', en: 'English', fr: 'Français', es: 'Español',
  la: 'Latina', ko: '한국어', tlh: 'tlhIngan Hol',
  ru: 'Русский', uk: 'Українська', hr: 'Hrvatski',
  yi: 'ייִדיש', mnn: 'Minionese 🍌',
}

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
