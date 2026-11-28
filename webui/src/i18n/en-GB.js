// British English (en-GB). Derived from the base `en` dictionary, overriding the
// few spellings that differ from American English (colour, greyscale, favourite,
// licence). The base is American.
import { en } from './en'

export const enGB = {
  ...en,
  'JPEG (Graustufen)': 'JPEG (greyscale)',
  'JPEG (Farbe)': 'JPEG (colour)',
  'PNG (Graustufen)': 'PNG (greyscale)',
  'Struktur (Farbe erhalten)': 'Structural (colour preserved)',
  'Zu Favoriten': 'Add to favourites',
  'Aus Favoriten entfernen': 'Remove from favourites',
  'Favorit hinzufügen': 'Add favourite',
  'Lizenz & Quelltext': 'Licence & source code',
  'Passwort-Eingabe abgebrochen – das Dokument wurde nicht geöffnet.': 'Password entry cancelled – the document was not opened.',
  'Freie Software unter AGPL-3.0-or-later; Lizenzen der Bestandteile: THIRD_PARTY_NOTICES.md':
    'Free software under AGPL-3.0-or-later; licences of the components: THIRD_PARTY_NOTICES.md',
}
