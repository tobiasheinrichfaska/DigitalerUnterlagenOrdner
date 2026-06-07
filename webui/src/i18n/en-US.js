// American English (en-US). Derived from the base `en` dictionary, overriding the
// few spellings that differ from British English (favorite, color, grayscale).
import { en } from './en'

export const enUS = {
  ...en,
  // -ize/-or/-grayscale: the base already uses the American "color"/"grayscale";
  // here we make the favourite→favorite spelling American too.
  'Zu Favoriten': 'Add to favorites',
  'Aus Favoriten entfernen': 'Remove from favorites',
  'Favorit hinzufügen': 'Add favorite',
}
