// DATEV-mode bar (v3.10.0; DATEV-mode only). A small header strip with:
//  - a toggle that turns DATEV mode on/off (persisted per-user on the host),
//  - when the open document is DATEV-connected: a "linked" badge (+ a checked-out
//    hint) and a „Nach DATEV zurückschreiben" action (guarded write-back),
//  - when DATEV mode is on but the document is NOT connected: a „Nach DATEV ablegen"
//    action (file it as a new DATEV document).
// Pure/prop-driven — all bridge calls live in App.jsx, so it renders deterministically
// in tests against plain props.
import { useT } from './i18n/LanguageProvider'

export function DatevBar({ datevMode, connected, serviceConnected, sourceName, checkedOutAtOpen,
                           onToggleMode, onSaveBack, onFile, busy }) {
  const { t } = useT()
  // SERVICE connection (null while still connecting). DATEV writes are refused without it,
  // so the actions are disabled and the reason is shown — never a dead button.
  const online = serviceConnected === true
  const connecting = serviceConnected == null
  const connLabel = connecting ? t('verbinde…') : t('keine Verbindung')
  return (
    <div className={`datev-bar${datevMode ? ' on' : ''}`}>
      <button type="button" className={`datev-toggle${datevMode ? ' active' : ''}`}
        onClick={onToggleMode} aria-pressed={datevMode}
        title={t('DATEV-Modus ein-/ausschalten')}>
        DATEV{datevMode ? ' ●' : ''}
      </button>
      {datevMode && !online && (
        <span className={`datev-conn${connecting ? ' connecting' : ' offline'}`}
          title={t('Verbindung zur DATEV-Schnittstelle')}>
          {connecting ? '⏳' : '⚠️'} {connLabel}
        </span>
      )}
      {datevMode && connected && (
        <span className="datev-state connected">
          🔗 {t('Mit DATEV verknüpft')}{sourceName ? `: ${sourceName}` : ''}
          {checkedOutAtOpen ? <em className="datev-warn"> · {t('in DATEV ausgecheckt')}</em> : null}
          <button type="button" className="datev-action" onClick={onSaveBack} disabled={busy || !online}
            title={online ? undefined : t('Keine Verbindung zur DATEV-Schnittstelle')}>
            {t('Nach DATEV zurückschreiben')}
          </button>
        </span>
      )}
      {datevMode && !connected && (
        <span className="datev-state">
          <button type="button" className="datev-action" onClick={onFile} disabled={busy || !online}
            title={online ? undefined : t('Keine Verbindung zur DATEV-Schnittstelle')}>
            {t('Nach DATEV ablegen')}
          </button>
        </span>
      )}
    </div>
  )
}
