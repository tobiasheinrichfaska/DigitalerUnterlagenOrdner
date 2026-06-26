// Right pane: tag editor (when tagging is on) + compression controls + zoom bar +
// the windowed preview (or legacy image list). Presentational — all state and
// handlers come in as props. `previewRef` is owned by App (for the ctrl-wheel zoom
// listener) and forwarded here onto the scroll container.
import { PreviewControls } from './PreviewControls'
import { Preview } from './Preview'
import { TagEditor } from './TagEditor'
import { useT } from './i18n/LanguageProvider'

export function PreviewPane({
  previewRef, tagsOn, selected, selectedNodes, docTags, dispatch, session, onPreview, defaultDpi,
  onCompressionResolved, windowed, pages, pageInfo, zoom, setZoom, previewReq, onPageInfo, busy,
}) {
  const { t } = useT()
  return (
    <div className="pane preview-pane" ref={previewRef}>
      {tagsOn && selected && <TagEditor node={selected} nodes={selectedNodes} docTags={docTags} dispatch={dispatch} />}
      {selected && <PreviewControls key={selected.id} node={selected} session={session} dispatch={dispatch} onPreview={onPreview} defaultDpi={defaultDpi} onResolved={onCompressionResolved} />}
      {selected && (windowed || pages?.length > 0) && (
        <div className="zoom-bar">
          {(() => {
            const total = pageInfo?.total ?? selected.pdf_length
            if (!total) return null
            return <span className="page-info">{pageInfo ? t('Seite {page} / {total}', { page: pageInfo.page, total }) : t('{total} Seiten', { total })}</span>
          })()}
          <button onClick={() => setZoom((z) => Math.max(0.25, z - 0.25))} title={t('kleiner')}>−</button>
          <span>{Math.round(zoom * 100)}%</span>
          <button onClick={() => setZoom((z) => Math.min(4, z + 0.25))} title={t('größer')}>＋</button>
          <button onClick={() => setZoom(1)} title={t('zurücksetzen')}>100%</button>
        </div>
      )}
      {!selected && <p className="status">{t('Knoten auswählen für die Vorschau')}</p>}
      {windowed && <Preview session={session} node={selected} zoom={zoom} previewReq={previewReq} onPage={onPageInfo} />}
      {!windowed && selected && busy > 0 && pages === null && <div className="spinner big" />}
      {!windowed && selected && busy === 0 && pages?.length === 0 && (
        <p className="status">{t('Keine Vorschau (Ordner oder leer)')}</p>
      )}
      {!windowed && selected && pages?.map((src, i) => (
        <img key={i} src={src} alt={t('Seite {n}', { n: i + 1 })} className="preview-page" style={{ width: `${zoom * 100}%` }} />
      ))}
    </div>
  )
}
