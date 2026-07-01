// DATEV filing dialog (v3.11.0): pick the Mandant (searchable), optional folder + register,
// the document date (Belegdatum) and the Veranlagungszeitraum (year + month). Prop-driven —
// the bridge calls (datev_clients/datev_placements/datev_file) live in the caller — so it
// renders deterministically in tests. No client data ⇒ filing is disabled (the user's rule:
// without a connection / client list there is no safe DATEV target).
import { useMemo, useState } from 'react'
import { useT } from './i18n/LanguageProvider'
import { useModal } from './hooks/useModal'
import { filterClients, registersFor, MONTHS, yearChoices, validateFiling, buildFileOpts, soleClientGuid } from './lib/datevFiling'

export function DatevFileDialog({ clients, placements = [], loading, error, currentYear,
                                  defaultName = '', onSubmit, onCancel }) {
  const { t } = useT()
  const dialogRef = useModal({ onClose: onCancel })
  const [query, setQuery] = useState('')
  const [clientGuid, setClientGuid] = useState('')
  const [description, setDescription] = useState(defaultName)  // the DATEV document NAME
  const [folderId, setFolderId] = useState('')
  const [registerId, setRegisterId] = useState('')
  const [documentDate, setDocumentDate] = useState('')
  const [fiscalYear, setFiscalYear] = useState('')
  const [fiscalMonth, setFiscalMonth] = useState('')

  const filtered = useMemo(() => filterClients(clients || [], query), [clients, query])
  // Derive the effective selection (no setState-in-effect): keep the current pick while it's still
  // visible, else fall back to the SOLE match — so a single client enables Ablegen without a manual
  // click (a 1-option listbox doesn't fire change on click in WebView2), and narrowing the search
  // past the current pick drops it instead of submitting a hidden client.
  const effectiveClientGuid = filtered.some((c) => c.guid === clientGuid)
    ? clientGuid : (soleClientGuid(filtered) || '')
  const registers = useMemo(() => registersFor(placements, folderId), [placements, folderId])
  const years = useMemo(() => yearChoices(currentYear), [currentYear])
  const state = { clientGuid: effectiveClientGuid, description, folderId, registerId, documentDate, fiscalYear, fiscalMonth }
  const valid = validateFiling(state)
  const noClients = !loading && !error && (clients || []).length === 0
  const canSubmit = !loading && !error && !noClients && valid.ok

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div ref={dialogRef} className="modal datev-file-dialog" role="dialog" aria-modal="true"
        onClick={(e) => e.stopPropagation()}>
        <h2>{t('Nach DATEV ablegen')}</h2>

        {loading && <p className="status">{t('Mandanten werden geladen…')}</p>}
        {error && <p className="error" role="alert">{t('Mandantenliste nicht verfügbar')}: {error}</p>}
        {noClients && <p className="error" role="alert">{t('Keine Mandanten gefunden — DATEV-Ablage nicht möglich.')}</p>}

        {!loading && !error && !noClients && (
          <>
            <div className="field">
              <span className="field-label">{t('Mandant')}</span>
              <input type="search" value={query} placeholder={t('Suchen (Nummer oder Name)…')}
                onChange={(e) => setQuery(e.target.value)} aria-label={t('Mandant suchen')} />
              <select className="datev-client-list" size={6} value={effectiveClientGuid}
                onChange={(e) => setClientGuid(e.target.value)} aria-label={t('Mandant')}>
                {filtered.map((c) => (
                  <option key={c.guid} value={c.guid}>
                    {c.number ? `${c.number} — ` : ''}{c.name}
                  </option>
                ))}
              </select>
            </div>

            <label className="field">
              <span>{t('Bezeichnung')}</span>
              <input type="text" value={description} onChange={(e) => setDescription(e.target.value)}
                placeholder={t('Name des Dokuments in DATEV')} aria-label={t('Bezeichnung')} />
            </label>

            <div className="field-row">
              <label className="field">
                <span>{t('Ordner')}</span>
                <select value={folderId} onChange={(e) => { setFolderId(e.target.value); setRegisterId('') }}>
                  <option value="">{t('— ohne —')}</option>
                  {placements.map((f) => <option key={f.id} value={f.id}>{f.name || f.id}</option>)}
                </select>
              </label>
              <label className="field">
                <span>{t('Register')}</span>
                <select value={registerId} onChange={(e) => setRegisterId(e.target.value)}
                  disabled={!registers.length}>
                  <option value="">{t('— ohne —')}</option>
                  {registers.map((r) => <option key={r.id} value={r.id}>{r.name || r.id}</option>)}
                </select>
              </label>
            </div>

            <div className="field-row">
              <label className="field">
                <span>{t('Belegdatum')}</span>
                <input type="date" value={documentDate} onChange={(e) => setDocumentDate(e.target.value)} />
              </label>
              <label className="field">
                <span>{t('Veranlagungsjahr')}</span>
                <select value={fiscalYear} onChange={(e) => setFiscalYear(e.target.value)}>
                  <option value="">{t('— ohne —')}</option>
                  {years.map((y) => <option key={y} value={y}>{y}</option>)}
                </select>
              </label>
              <label className="field">
                <span>{t('Veranlagungsmonat')}</span>
                <select value={fiscalMonth} onChange={(e) => setFiscalMonth(e.target.value)}>
                  <option value="">{t('— ohne —')}</option>
                  {MONTHS.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </label>
            </div>

            {!valid.ok && <p className="muted">{t(valid.error)}</p>}
          </>
        )}

        <div className="modal-actions">
          <button className="primary" disabled={!canSubmit}
            onClick={() => onSubmit(buildFileOpts(state))}>{t('Ablegen')}</button>
          <button onClick={onCancel}>{t('Abbrechen')}</button>
        </div>
      </div>
    </div>
  )
}
