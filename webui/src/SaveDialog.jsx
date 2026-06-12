// Save-time choice when the document has computed-but-unapplied compression
// alternatives: embed them (bigger file, instant on reopen) or save just the
// base version (smaller, recompute on reopen). Committed ("Lesbarkeit geprüft")
// nodes have no alternatives, so this only appears when there's something to embed.
import { useT } from './i18n/LanguageProvider'
import { useModal } from './hooks/useModal'

export function SaveDialog({ count, onChoose, onCancel }) {
  const { t } = useT()
  // Focus management: focus first element on open, trap Tab, close on Esc, restore focus on unmount.
  const dialogRef = useModal({ onClose: onCancel })
  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div ref={dialogRef} className="modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <h2>{t('Komprimierungs-Alternativen speichern?')}</h2>
        <p>{t('{n} Dokument(e) haben berechnete Komprimierungs-Alternativen.', { n: count })}</p>
        <p className="muted">
          {t('„Wie geplant" behält die Alternativen in der Datei (größer, beim Öffnen sofort verfügbar). „Original" speichert nur die Basis-Fassung (kleiner; Alternativen werden beim Öffnen neu berechnet).')}
        </p>
        <div className="modal-actions">
          <button className="primary" onClick={() => onChoose(true)}>{t('Wie geplant speichern')}</button>
          <button onClick={() => onChoose(false)}>{t('Original speichern')}</button>
          <button onClick={onCancel}>{t('Abbrechen')}</button>
        </div>
      </div>
    </div>
  )
}
