// British English (en-GB). Derived from the base `en` dictionary, overriding the
// few spellings that differ from American English (colour, greyscale). The base
// already uses British "favourite".
import { en } from './en'

export const enGB = {
  ...en,
  'JPEG (Graustufen)': 'JPEG (greyscale)',
  'JPEG (Farbe)': 'JPEG (colour)',
  'PNG (Graustufen)': 'PNG (greyscale)',
  'Struktur (Farbe erhalten)': 'Structural (colour preserved)',
  '{n} markiert': '{n} selected',
  'nur auf einigen markiert': 'on only some of the selection',
  'Weitere Speicheroptionen': 'More save options',
}
