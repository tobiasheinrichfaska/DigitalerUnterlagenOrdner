// Export options, asked before the native save dialog: printed table of contents
// (+clickable links), tag index (+links — only offered when the document has tags),
// and PDF sidebar bookmarks. Returns the chosen options to the caller.
import { useState } from 'react'
import { useT } from './i18n/LanguageProvider'
import { useModal } from './hooks/useModal'

export function ExportDialog({ hasTags, onChoose, onCancel }) {
  const { t } = useT()
  const [toc, setToc] = useState(true)
  const [tocLinks, setTocLinks] = useState(true)
  const [index, setIndex] = useState(hasTags)
  const [indexLinks, setIndexLinks] = useState(true)
  const [bookmarks, setBookmarks] = useState(true)

  // Focus management: focus first element on open, trap Tab, close on Esc, restore focus on unmount.
  const dialogRef = useModal({ onClose: onCancel })

  const confirm = () => onChoose({
    toc,
    toc_links: toc && tocLinks,   // only meaningful when toc is on
    index: hasTags && index, index_links: indexLinks,
    bookmarks,
  })

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div ref={dialogRef} className="modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <h2>{t('PDF exportieren')}</h2>

        <label className="exp-row">
          <input type="checkbox" checked={toc} onChange={(e) => setToc(e.target.checked)} />
          {t('Inhaltsverzeichnis')}
        </label>
        <label className="exp-row exp-sub">
          <input type="checkbox" checked={tocLinks} disabled={!toc}
            onChange={(e) => setTocLinks(e.target.checked)} />
          {t('mit anklickbaren Links')}
        </label>

        <label className="exp-row" title={hasTags ? undefined : t('Keine Tags im Dokument')}>
          <input type="checkbox" checked={index} disabled={!hasTags}
            onChange={(e) => setIndex(e.target.checked)} />
          {t('Stichwortverzeichnis (nach Tags)')}
        </label>
        <label className="exp-row exp-sub">
          <input type="checkbox" checked={indexLinks} disabled={!hasTags || !index}
            onChange={(e) => setIndexLinks(e.target.checked)} />
          {t('mit anklickbaren Links')}
        </label>

        <label className="exp-row">
          <input type="checkbox" checked={bookmarks} onChange={(e) => setBookmarks(e.target.checked)} />
          {t('PDF-Lesezeichen (Seitenleiste)')}
        </label>

        <div className="modal-actions">
          <button className="primary" onClick={confirm}>{t('Exportieren')}</button>
          <button onClick={onCancel}>{t('Abbrechen')}</button>
        </div>
      </div>
    </div>
  )
}
