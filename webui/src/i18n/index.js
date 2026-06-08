// Source-string i18n, dependency-free. The KEY is the German text written inline
// in the UI: t('Öffnen'). German is the default language and needs no dictionary;
// other languages map the German source → their translation. A missing translation
// falls back to the German source, so nothing is ever blank.
//
// Add a language: add a file exporting a { '<German>': '<translated>' } map, then
// register it in TRANSLATIONS + LANGUAGE_NAMES. i18n.test.js checks coverage.
import { enUS } from './en-US'
import { enGB } from './en-GB'
import { fr } from './fr'
import { es } from './es'
import { la } from './la'
import { qya } from './qya'
import { sjn } from './sjn'
import { ko } from './ko'
import { tlh } from './tlh'
import { ru } from './ru'
import { uk } from './uk'
import { hr } from './hr'
import { yi } from './yi'
import { mnn } from './mnn'
import { ca } from './ca'
import { bar } from './bar'
import { nds } from './nds'
import { vie } from './vie'
import { gd } from './gd'
import { ga } from './ga'
import { cy } from './cy'

export const TRANSLATIONS = { 'en-US': enUS, 'en-GB': enGB, fr, es, la, qya, sjn, ko, tlh, ru, uk, hr, yi, mnn, ca, bar, nds, vie, gd, ga, cy } // code -> { '<German source>': '<translation>' }
export const DEFAULT_LANG = 'de'
export const SUPPORTED = ['de', ...Object.keys(TRANSLATIONS)]
export const LANGUAGE_NAMES = {
  de: 'Deutsch', 'en-US': 'English (US)', 'en-GB': 'English (UK)', fr: 'Français', es: 'Español',
  la: 'Latina', qya: 'Quenya', sjn: 'Sindarin', ko: '한국어', tlh: 'tlhIngan Hol',
  ru: 'Русский', uk: 'Українська', hr: 'Hrvatski',
  yi: 'ייִדיש', mnn: 'Minionese 🍌',
  ca: 'Català', bar: 'Boarisch', nds: 'Plattdüütsch', vie: 'Weanerisch',
  gd: 'Gàidhlig', ga: 'Gaeilge', cy: 'Cymraeg',
}

/** Translate German `text` into `lang`, interpolating `{name}` from `vars`.
 *  Default language (or a missing entry) returns the German source unchanged. */
export function translate(lang, text, vars) {
  const dict = TRANSLATIONS[lang]
  let s = (!dict || lang === DEFAULT_LANG) ? text : (dict[text] ?? text)
  if (vars) s = s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m))
  return s
}

/** A valid stored choice → exact browser locale (e.g. en-GB) → 2-letter language →
 *  DEFAULT_LANG. A bare/generic English (stored or browser "en") maps to en-US. */
export function resolveInitialLang(stored, navLang) {
  if (stored && SUPPORTED.includes(stored)) return stored
  if (stored === 'en') return 'en-US'                 // legacy/generic English
  const nav = navLang || ''
  if (SUPPORTED.includes(nav)) return nav             // exact locale, e.g. en-GB
  const short = nav.slice(0, 2).toLowerCase()
  if (short === 'en') return 'en-US'                  // generic English → US
  if (SUPPORTED.includes(short)) return short
  return DEFAULT_LANG
}
