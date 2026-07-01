// Pure DATEV-mode helpers (UI-free, unit-tested). The bridge calls live in App.jsx;
// these just interpret provenance + write-back verdicts.

// A working document is DATEV-connected iff its root carries complete provenance
// (doc_guid + file_id). Mirrors datev/writeback.py::is_connected.
export function isDatevConnected(provenance) {
  return !!(provenance && provenance.doc_guid && provenance.file_id != null)
}

// Map a non-ok write-back verdict (datev/writeback.py) to a t() message key. Every
// non-ok verdict means: the DATEV document was NOT overwritten — save locally instead.
export const DATEV_VERDICT_KEY = {
  locked: 'DATEV: Das Dokument ist ausgecheckt — nur lokal speichern möglich.',
  conflict_changed: 'DATEV: Das Dokument wurde zwischenzeitlich geändert — bitte lokal speichern.',
  conflict_content: 'DATEV: Der Serverstand weicht vom geöffneten Stand ab — bitte lokal speichern.',
  no_structure_item: 'DATEV: Kein Strukturelement gefunden — bitte lokal speichern.',
  // checked_out_self (ok:false) = the doc is checked out by ME and the local working-copy save ALSO
  // failed (locked); mirrors the PDF-Tool surface's message so both surfaces read identically.
  checked_out_self: 'DATEV: Ausgecheckte Datei konnte nicht gespeichert werden (gesperrt?)',
}

export function datevVerdictKey(verdict) {
  return DATEV_VERDICT_KEY[verdict] || 'DATEV-Rückschreiben fehlgeschlagen.'
}

// The basename of a saved local path (handles both \\ and / separators).
export function localBaseName(path) {
  if (!path) return ''
  return String(path).split(/[\\/]/).pop()
}

// A success notice that makes the locally-saved FORMAT explicit by appending the saved file
// name — a .belegtool bundle (organizer) vs the plain .pdf of a DATEV checkout (PDF-Tool) —
// so the user can always tell which format landed on disk. Falls back to the bare message
// when nothing was saved locally.
export function datevSavedNotice(message, res) {
  const name = localBaseName(res && res.local_saved)
  return name ? `${message} · ${name}` : message
}
