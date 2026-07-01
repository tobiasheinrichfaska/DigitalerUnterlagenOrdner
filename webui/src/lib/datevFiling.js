// Pure, UI-free helpers for the DATEV filing dialog (shared by the React organizer and the
// vanilla-JS PDF-Tool surface). Unit-tested without any DOM/bridge.

// Filter the client list by a free-text query, matching the number OR the name
// (case-insensitive, all whitespace-separated terms must match). Empty query → all.
export function filterClients(clients, query) {
  const terms = String(query || '').toLowerCase().split(/\s+/).filter(Boolean)
  if (!terms.length) return clients || []
  return (clients || []).filter((c) => {
    const hay = `${c.number || ''} ${c.name || ''}`.toLowerCase()
    return terms.every((t) => hay.includes(t))
  })
}

// When exactly ONE client matches the search, it should become the selection automatically.
// A single-option `<select size>` listbox does NOT reliably fire a change event on click in
// WebView2 (the sole option is already the focused/highlighted row), so without this the user
// "can only select a client when there's more than one" and Ablegen never enables. Returns the
// guid to auto-select, or null when the choice is genuinely ambiguous (0 or >1 matches).
export function soleClientGuid(filtered) {
  return filtered && filtered.length === 1 ? filtered[0].guid : null
}

// The registers of the chosen folder (empty when no folder / no match).
export function registersFor(placements, folderId) {
  if (folderId == null || folderId === '') return []
  const f = (placements || []).find((p) => String(p.id) === String(folderId))
  return (f && f.registers) || []
}

// 1..12 for the Veranlagungsmonat dropdown.
export const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1)

// A sensible year list for the Veranlagungsjahr dropdown: current year back N (default 8).
export function yearChoices(currentYear, back = 8) {
  const y = Number(currentYear)
  if (!Number.isFinite(y)) return []
  return Array.from({ length: back + 1 }, (_, i) => y - i)
}

// Validate a filing form state. A client is REQUIRED (no client → no safe target, the user's
// rule); a Bezeichnung (the document's NAME in DATEV) is REQUIRED so the filed document is
// never nameless (the v3.11.0 "pdf lacks Name" bug); a month without a year is meaningless.
// Returns { ok, error }.
export function validateFiling(state) {
  if (!state || !state.clientGuid) return { ok: false, error: 'Bitte einen Mandanten wählen.' }
  if (!String((state && state.description) || '').trim()) {
    return { ok: false, error: 'Bitte eine Bezeichnung eingeben.' }
  }
  if (state.fiscalMonth && !state.fiscalYear) {
    return { ok: false, error: 'Monat ohne Jahr ist nicht möglich — bitte ein Jahr wählen.' }
  }
  return { ok: true, error: null }
}

// Turn a date input value (yyyy-mm-dd, or empty) into the ISO datetime DATEV expects, or null.
export function dateToIso(value) {
  if (!value) return null
  // a bare yyyy-mm-dd → local midnight, matching DATEV's "expressed in local time" dates
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value
}

// Build the datev_file opts object from the form state (only set fields are included).
export function buildFileOpts(state) {
  const opts = { clientGuid: state.clientGuid }
  const description = String((state && state.description) || '').trim()
  if (description) opts.description = description  // → DocumentCreate "description" = the DATEV name
  if (state.folderId != null && state.folderId !== '') opts.folderId = Number(state.folderId)
  if (state.registerId != null && state.registerId !== '') opts.registerId = Number(state.registerId)
  const iso = dateToIso(state.documentDate)
  if (iso) opts.documentDate = iso
  if (state.fiscalYear) opts.fiscalYear = Number(state.fiscalYear)
  if (state.fiscalMonth) opts.fiscalMonth = Number(state.fiscalMonth)
  return opts
}
