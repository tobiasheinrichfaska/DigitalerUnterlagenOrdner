// View controls above the tree (shown only when tagging is on): a search box that
// filters the tree by name / effective tag, and a "group by tag" toggle that flattens
// leaves into one folder per tag. Both are view-only — the saved document is untouched.
// While a view is active, structural editing (reorder / import / delete …) is disabled;
// content edits (compress, rename, status, tag) stay available. "Open in new window"
// materialises the current view as a fresh, fully-editable document.
import { useT } from './i18n/LanguageProvider'

export function TagViewBar({ search, setSearch, grouped, setGrouped, active, onReset, onOpenInNewWindow }) {
  const { t } = useT()
  const hint = grouped ? t('Nach Tag gruppiert — Umsortieren aus') : t('Ansicht gefiltert — Umsortieren aus')
  return (
    <div className="tag-view-bar">
      <span className="tvb-search">
        🔍
        <input value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder={t('Tags suchen…')} aria-label={t('Tags suchen…')} />
        {search && <button className="tvb-clear" title={t('Suche löschen')} onClick={() => setSearch('')}>×</button>}
      </span>
      <label className="tvb-group" title={t('Belege nach Tag gruppieren (nur Ansicht)')}>
        <input type="checkbox" checked={grouped} onChange={(e) => setGrouped(e.target.checked)} />
        {t('Nach Tag gruppieren')}
      </label>
      {active && (
        <span className="tvb-hint">
          ⚠ {hint}
          {onOpenInNewWindow && (
            <button className="tvb-act" onClick={onOpenInNewWindow}>{t('In neuem Fenster öffnen')}</button>
          )}
          <button className="tvb-act" onClick={onReset}>{t('Ansicht zurücksetzen')}</button>
        </span>
      )}
    </div>
  )
}
