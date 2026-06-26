// American English (en-US). Derived from the base `en` dictionary, overriding the
// few spellings that differ from British English (favorite, color, grayscale).
import { en } from './en'

export const enUS = {
  ...en,
  // Override only the spellings where US differs from the `en` base: favourite→favorite.
  // (The base happens to use American "color"/"grayscale"; en-GB.js overrides those.)
  'Zu Favoriten': 'Add to favorites',
  'Aus Favoriten entfernen': 'Remove from favorites',
  'Favorit hinzufügen': 'Add favorite',
  '{n} markiert': '{n} selected',
  'nur auf einigen markiert': 'on only some of the selection',
  'Weitere Speicheroptionen': 'More save options',
}
