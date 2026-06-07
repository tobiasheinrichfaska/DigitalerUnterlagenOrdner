// Working-preview compression controls for the selected leaf — LAZY.
//
// Selecting a leaf runs no compression: the preview shows the stored bytes
// (plain render). The method list (which runs compression) is fetched only when
// the user opens the dropdown; a transient compressed preview is shown only when
// they pick a method or move the DPI slider. The document changes only on a
// deliberate apply ("❓ Lesbarkeit geprüft" → Compress, "Original" → Reset).
import { useState, useEffect } from 'react'
import { core } from './lib/core'
import { useT } from './i18n/LanguageProvider'

const kb = (n) => `${Math.round(n / 1024)} KB`

// backend compression method key → German display text (translated by t()).
const METHOD_DE = {
  jpg: 'JPEG (Graustufen)', jpg_color: 'JPEG (Farbe)',
  png: 'PNG (Graustufen)', pikepdf: 'Struktur (Farbe erhalten)',
}

// Remember the compression method the user last picked for each node, so
// re-selecting that node restores the choice instead of resetting to "original".
// Session-only (cleared on reload); keyed by node id.
const methodMemory = new Map()

export function PreviewControls({ node, session, dispatch, onPreview, defaultDpi = 150 }) {
  const { t } = useT()
  // backend method key → German display text, which t() then translates.
  const methodLabel = (m) => t(METHOD_DE[m] ?? m)
  // A committed node reloaded from disk has no source bytes (original dropped on
  // save) → it can't be re-compressed or reset; lock the controls.
  const noSource = node.has_source === false
  const off = node.no_compression || noSource
  const [dpi, setDpi] = useState(node.dpi_current ?? defaultDpi)
  const [options, setOptions] = useState(null) // method list, loaded on demand
  const [origSize, setOrigSize] = useState(null) // byte size of the uncompressed source
  const [loading, setLoading] = useState(false) // compression options being computed
  const [method, setMethod] = useState(node.compression_method ?? 'original')

  // keep the dropdown/slider in sync with the model after apply/reset/undo —
  // pure state, never triggers compression
  /* eslint-disable react-hooks/set-state-in-effect -- intentionally re-sync local controls from the model */
  useEffect(() => {
    setMethod(node.compression_method ?? 'original')
    setDpi(node.dpi_current ?? defaultDpi)
  }, [node.is_compressed, node.compression_method, node.dpi_current]) // eslint-disable-line react-hooks/exhaustive-deps
  /* eslint-enable react-hooks/set-state-in-effect */

  const preview = (d, m) => onPreview({ dpi: d, method: m })
  const loadOptions = (d) => {
    if (off) return
    setLoading(true)
    core.compressOptions(session, node.id, d).then((r) => {
      setOptions(r?.ok ? r.options : [])
      setOrigSize(r?.ok ? r.original_size : null)
      setLoading(false)
    })
  }

  // On displaying a (compressible, not-yet-committed) node: eagerly compute its
  // options and default to the previously chosen method, else the smallest one —
  // so a node shows its best compression by default. Non-blocking + cancellable;
  // the component is keyed by node id, so this runs once per displayed node.
  // Only auto-compute for small nodes — on a big node the all-methods compute is
  // expensive, so >5 pages just shows the original (compress manually via the dropdown).
  const AUTO_MAX_PAGES = 5
  /* eslint-disable react-hooks/set-state-in-effect -- async result drives the controls */
  useEffect(() => {
    if (off || node.is_compressed || node.compression_no_gain || node.pdf_length > AUTO_MAX_PAGES) return
    let alive = true
    const d = node.dpi_current ?? defaultDpi
    setLoading(true)
    core.compressOptions(session, node.id, d)
      .then((r) => {
        if (!alive) return
        const opts = r?.ok ? r.options : []
        setOptions(opts)
        setOrigSize(r?.ok ? r.original_size : null)
        setLoading(false)
        const remembered = methodMemory.get(node.id)
        const valid = remembered === 'original' || opts.some((o) => o.method === remembered)
        const pick = valid ? remembered : opts[0]?.method // options are smallest-first
        if (pick && pick !== 'original') { setMethod(pick); preview(d, pick) }
      })
      .catch(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [node.id]) // eslint-disable-line react-hooks/exhaustive-deps
  /* eslint-enable react-hooks/set-state-in-effect */

  const onDpi = (d) => {
    setDpi(d)
    if (off || method === 'original') return
    loadOptions(d)       // sizes depend on DPI → refresh
    preview(d, method)
  }
  const onMethod = (m) => { setMethod(m); methodMemory.set(node.id, m); preview(dpi, m) }

  const applied = node.is_compressed
    ? node.compression_method === method && node.dpi_current === dpi
    : method === 'original'

  // Live size of the current pick (updates when DPI/method change reloads options),
  // shown next to the controls so the size/"beste" is visible without opening the list.
  const currentOpt = options?.find((o) => o.method === method)
  const sizeNow = method === 'original' ? origSize : currentOpt?.size
  const isBest = !!options && options.length > 0 && method !== 'original' && options[0].method === method

  const applyChoice = () => {
    if (method === 'original') {
      if (node.is_compressed) dispatch({ type: 'Reset', node_id: node.id })
    } else {
      dispatch({ type: 'Compress', node_id: node.id, dpi, method })
    }
    onPreview(null) // show the now-stored bytes via plain render (no recompute)
  }

  return (
    <div className="preview-controls">
      <label className="dpi" title={t('Kompressions-DPI')}>
        DPI <b>{dpi}</b>
        <input
          type="range" min="50" max="300" step="10" value={dpi} disabled={off}
          onChange={(e) => setDpi(Number(e.target.value))}
          onMouseUp={(e) => onDpi(Number(e.target.value))} onTouchEnd={(e) => onDpi(Number(e.target.value))}
        />
      </label>

      <select className="compress-select" value={method} disabled={off}
        onMouseDown={() => { if (!options) loadOptions(dpi) }}
        onFocus={() => { if (!options) loadOptions(dpi) }}
        onChange={(e) => onMethod(e.target.value)}>
        <option value="original">{
          noSource ? t('bereits komprimiert (keine Quelle)')
            : loading ? t('Kompression läuft …')
              : `${t('unkomprimierte Fassung')}${origSize != null ? ` — ${kb(origSize)}` : ''}`
        }</option>
        {/* before the list loads, keep the saved method selectable */}
        {!options && method !== 'original' && <option value={method}>{methodLabel(method)}</option>}
        {options?.map((o, i) => (
          <option key={o.method} value={o.method}>
            {methodLabel(o.method)} — {kb(o.size)}{i === 0 ? ` · ${t('beste')}` : ''}
          </option>
        ))}
      </select>

      {sizeNow != null && !off && (
        <span className="csize" title={t('Größe der aktuellen Auswahl bei diesem DPI')}>
          {loading ? '…' : kb(sizeNow)}{isBest ? ` · ${t('beste')}` : ''}
        </span>
      )}

      <button onClick={applyChoice} disabled={off || applied}
        title={t('Die aktuell angezeigte Komprimierung übernehmen')}>
        {applied ? `✓ ${t('übernommen')}` : `❓ ${t('Lesbarkeit geprüft')}`}
      </button>
      <span className="sep" />
      <button title={t('rechts drehen')} onClick={() => dispatch({ type: 'Rotate', node_id: node.id, direction: 'right' })}>↻</button>
      <button title={t('links drehen')} onClick={() => dispatch({ type: 'Rotate', node_id: node.id, direction: 'left' })}>↺</button>
    </div>
  )
}
