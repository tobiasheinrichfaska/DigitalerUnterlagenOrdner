// App header toolbar — presentational. All actions come in as handlers; the only
// state it reads is display flags (dirty, selection count, undo/redo availability,
// tags on, busy) and the current language.
import { useT } from './i18n/LanguageProvider'
import { LANGUAGE_NAMES } from './i18n/index'

export function Toolbar({
  onOpen, onNewWindow, onImport, onSave, onSaveAs, onExport, onAddFolder,
  onUndo, onRedo, onToggleTags, onHelp, lang, setLang,
  dirty, selectedCount, canUndo, canRedo, tagsOn, busy, editLocked = false,
}) {
  const { t } = useT()
  const lockTitle = editLocked ? t('In der gefilterten Ansicht nicht verfügbar') : undefined
  return (
    <div className="toolbar">
      <button onClick={onOpen}>📂 {t('Öffnen')}</button>
      <button onClick={onNewWindow} title={t('Weiteres Dokument in neuem Fenster')}>🗗 {t('Neues Fenster')}</button>
      <button onClick={onImport} disabled={editLocked} title={lockTitle}>📥 {t('Importieren')}</button>
      <button onClick={onSave}>💾 {t('Speichern')}{dirty ? ' •' : ''}</button>
      <button onClick={onSaveAs} title={t('Speichern unter…')}>💾…</button>
      <button onClick={onExport} title={t('Als PDF mit Inhaltsverzeichnis exportieren (Auswahl, sonst das ganze Dokument)')}>
        ⬇ {t('Export PDF')}{selectedCount ? ` (${t('Auswahl')} ${selectedCount})` : ''}
      </button>
      <span className="sep" />
      <button onClick={onAddFolder} disabled={editLocked} title={lockTitle}>＋ {t('Ordner')}</button>
      <button onClick={onUndo} disabled={!canUndo} title={t('Rückgängig')}>↶</button>
      <button onClick={onRedo} disabled={!canRedo} title={t('Wiederholen')}>↷</button>
      <span className="sep" />
      <button className={tagsOn ? 'tag-toggle on' : 'tag-toggle'} aria-pressed={tagsOn}
        onClick={onToggleTags} title={t('Tags ein-/ausschalten')}>🏷️ {t('Tags')}</button>
      <span className="sep" />
      <select className="lang-select" value={lang} title={t('Sprache')} aria-label={t('Sprache')}
        onChange={(e) => setLang(e.target.value)}>
        {Object.entries(LANGUAGE_NAMES).map(([code, name]) => (
          <option key={code} value={code}>🌐 {name}</option>
        ))}
      </select>
      <button onClick={onHelp} title={t('Hilfe')}>❓ {t('Hilfe')}</button>
      {busy ? <span className="spinner" title={t('Arbeite…')} /> : null}
    </div>
  )
}
