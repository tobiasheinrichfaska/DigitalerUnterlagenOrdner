// Export options, asked before the native save dialog: printed table of contents
// (+clickable links), tag index (+links — only offered when the document has tags),
// PDF sidebar bookmarks, and (#13) optional splitting into several files at a page
// threshold + a chosen break level. Returns the chosen options to the caller.
import { useState } from 'react'
import { useT } from './i18n/LanguageProvider'
import { useModal } from './hooks/useModal'

export function ExportDialog({ hasTags, datevAvailable = false, onChoose, onCancel }) {
  const { t } = useT()
  const [toc, setToc] = useState(true)
  const [tocLinks, setTocLinks] = useState(true)
  const [index, setIndex] = useState(hasTags)
  const [indexLinks, setIndexLinks] = useState(true)
  const [bookmarks, setBookmarks] = useState(true)
  const [split, setSplit] = useState(false)
  const [splitPages, setSplitPages] = useState(100)
  const [splitLevel, setSplitLevel] = useState('top')
  const [toDatev, setToDatev] = useState(false)  // file the export into DATEV (same client)

  // Focus management: focus first element on open, trap Tab, close on Esc, restore focus on unmount.
  const dialogRef = useModal({ onClose: onCancel })

  const confirm = () => onChoose({
    toc,
    toc_links: toc && tocLinks,   // only meaningful when toc is on
    // split mode renders its own per-file TOC and ignores the index + bookmarks
    index: hasTags && index && !split, index_links: hasTags && index && !split && indexLinks,
    bookmarks: bookmarks && !split,
    split_pages: split ? Math.max(1, Number(splitPages) || 100) : null,
    split_level: splitLevel,
    to_datev: datevAvailable && toDatev,  // → file the exported PDF(s) into DATEV instead of disk
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

        {/* Split mode renders its own per-file TOC and ignores the tag index +
            bookmarks — disable them so the dialog reflects what will actually happen. */}
        <label className="exp-row" title={hasTags ? undefined : t('Keine Tags im Dokument')}>
          <input type="checkbox" checked={index && !split} disabled={!hasTags || split}
            onChange={(e) => setIndex(e.target.checked)} />
          {t('Stichwortverzeichnis (nach Tags)')}
        </label>
        <label className="exp-row exp-sub">
          <input type="checkbox" checked={indexLinks} disabled={!hasTags || !index || split}
            onChange={(e) => setIndexLinks(e.target.checked)} />
          {t('mit anklickbaren Links')}
        </label>

        <label className="exp-row">
          <input type="checkbox" checked={bookmarks && !split} disabled={split}
            onChange={(e) => setBookmarks(e.target.checked)} />
          {t('PDF-Lesezeichen (Seitenleiste)')}
        </label>

        <label className="exp-row">
          <input type="checkbox" checked={split} onChange={(e) => setSplit(e.target.checked)} />
          {t('In mehrere Dateien aufteilen')}
        </label>
        <label className="exp-row exp-sub">
          {t('max. Seiten pro Datei')}
          <input type="number" min="1" className="exp-num" value={splitPages} disabled={!split}
            onChange={(e) => setSplitPages(e.target.value)} />
        </label>
        <label className="exp-row exp-sub">
          {t('Trennen bei:')}
          <select className="exp-level" value={splitLevel} disabled={!split}
            onChange={(e) => setSplitLevel(e.target.value)}>
            <option value="top">{t('oberste Ordner')}</option>
            <option value="folder">{t('jeder Ordnergrenze')}</option>
            <option value="page">{t('mitten im Dokument')}</option>
          </select>
        </label>

        {datevAvailable && (
          <label className="exp-row datev-export-row">
            <input type="checkbox" checked={toDatev} onChange={(e) => setToDatev(e.target.checked)} />
            {t('Nach DATEV ablegen (gleicher Mandant)')}
          </label>
        )}

        <div className="modal-actions">
          <button className="primary" onClick={confirm}>{t('Exportieren')}</button>
          <button onClick={onCancel}>{t('Abbrechen')}</button>
        </div>
      </div>
    </div>
  )
}
