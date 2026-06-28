// App header toolbar — presentational. All actions come in as handlers; the only
// state it reads is display flags (dirty, selection count, undo/redo availability,
// tags on, busy) and the current language.
//
// #2 redesign: the buttons are icon-only to stay compact. The visible label moved
// into the tooltip (title); every button also carries an aria-label so screen
// readers and role/name queries keep the full name. The Export button shows the
// current selection count as a small badge.
import { useT } from './i18n/LanguageProvider'
import { LANGUAGE_NAMES } from './i18n/index'
import { SaveSplitButton } from './SaveSplitButton'

export function Toolbar({
  onOpen, onNewWindow, onImport, onSave, onSaveAs, onExport, onAddFolder,
  onUndo, onRedo, onToggleTags, onHelp, lang, setLang,
  dirty, selectedCount, canUndo, canRedo, tagsOn, busy, editLocked = false,
}) {
  const { t } = useT()
  const lockTitle = editLocked ? t('In der gefilterten Ansicht nicht verfügbar') : undefined
  return (
    <div className="toolbar">
      <button className="tb-btn" onClick={onOpen} title={t('Öffnen')} aria-label={t('Öffnen')}>📂</button>
      <button className="tb-btn" onClick={onNewWindow}
        title={t('Weiteres Dokument in neuem Fenster')} aria-label={t('Neues Fenster')}>🗗</button>
      <button className="tb-btn" onClick={onImport} disabled={editLocked}
        title={lockTitle || t('Importieren')} aria-label={t('Importieren')}>📥</button>
      <SaveSplitButton onSave={onSave} onSaveAs={onSaveAs} dirty={dirty} />
      <button className="tb-btn export-btn" onClick={onExport} aria-label={t('Export PDF')}
        title={t('Als PDF mit Inhaltsverzeichnis exportieren (Auswahl, sonst das ganze Dokument)')}>
        ⬇{selectedCount ? <span className="count-badge" aria-hidden="true">{selectedCount}</span> : null}
      </button>
      <span className="sep" />
      <button className="tb-btn" onClick={onAddFolder} disabled={editLocked}
        title={lockTitle || t('Ordner')} aria-label={t('Ordner')}>＋</button>
      <button className="tb-btn" onClick={onUndo} disabled={!canUndo}
        title={t('Rückgängig')} aria-label={t('Rückgängig')}>↶</button>
      <button className="tb-btn" onClick={onRedo} disabled={!canRedo}
        title={t('Wiederholen')} aria-label={t('Wiederholen')}>↷</button>
      <span className="sep" />
      <button className={tagsOn ? 'tb-btn tag-toggle on' : 'tb-btn tag-toggle'} aria-pressed={tagsOn}
        onClick={onToggleTags} title={t('Tags ein-/ausschalten')} aria-label={t('Tags')}>🏷️</button>
      <span className="sep" />
      <select className="lang-select" value={lang} title={t('Sprache')} aria-label={t('Sprache')}
        onChange={(e) => setLang(e.target.value)}>
        {Object.entries(LANGUAGE_NAMES).map(([code, name]) => (
          <option key={code} value={code}>🌐 {name}</option>
        ))}
      </select>
      <button className="tb-btn" onClick={onHelp} title={t('Hilfe')} aria-label={t('Hilfe')}>❓</button>
      {busy ? <span className="spinner" title={t('Arbeite…')} /> : null}
    </div>
  )
}
