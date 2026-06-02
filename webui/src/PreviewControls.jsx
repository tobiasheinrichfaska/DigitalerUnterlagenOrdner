// Working-preview compression controls for the selected leaf — LAZY.
//
// Selecting a leaf runs no compression: the preview shows the stored bytes
// (plain render). The method list (which runs compression) is fetched only when
// the user opens the dropdown; a transient compressed preview is shown only when
// they pick a method or move the DPI slider. The document changes only on a
// deliberate apply ("❓ Lesbarkeit geprüft" → Compress, "Original" → Reset).
import { useState, useEffect } from 'react'
import { core } from './core'

const kb = (n) => `${Math.round(n / 1024)} KB`

// Readable labels for the backend compression method keys.
const METHOD_LABELS = {
  jpg: 'JPEG (Graustufen)',
  jpg_color: 'JPEG (Farbe)',
  png: 'PNG (Graustufen)',
  pikepdf: 'Struktur (Farbe erhalten)',
}
const methodLabel = (m) => METHOD_LABELS[m] ?? m

export function PreviewControls({ node, session, dispatch, onPreview, defaultDpi = 150 }) {
  // A committed node reloaded from disk has no source bytes (original dropped on
  // save) → it can't be re-compressed or reset; lock the controls.
  const noSource = node.has_source === false
  const off = node.no_compression || noSource
  const [dpi, setDpi] = useState(node.dpi_current ?? defaultDpi)
  const [options, setOptions] = useState(null) // method list, loaded on demand
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
      setLoading(false)
    })
  }

  const onDpi = (d) => {
    setDpi(d)
    if (off || method === 'original') return
    loadOptions(d)       // sizes depend on DPI → refresh
    preview(d, method)
  }
  const onMethod = (m) => { setMethod(m); preview(dpi, m) }

  const applied = node.is_compressed
    ? node.compression_method === method && node.dpi_current === dpi
    : method === 'original'

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
      <label className="dpi" title="Kompressions-DPI">
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
        <option value="original">{noSource ? 'bereits komprimiert (keine Quelle)' : loading ? 'Kompression läuft …' : 'unkomprimierte Fassung'}</option>
        {/* before the list loads, keep the saved method selectable */}
        {!options && method !== 'original' && <option value={method}>{methodLabel(method)}</option>}
        {options?.map((o, i) => (
          <option key={o.method} value={o.method}>
            {methodLabel(o.method)} — {kb(o.size)}{i === 0 ? ' · beste' : ''}
          </option>
        ))}
      </select>

      <button onClick={applyChoice} disabled={off || applied}
        title="Die aktuell angezeigte Komprimierung übernehmen">
        {applied ? '✓ übernommen' : '❓ Lesbarkeit geprüft'}
      </button>
      <span className="sep" />
      <button title="rechts drehen" onClick={() => dispatch({ type: 'Rotate', node_id: node.id, direction: 'right' })}>↻</button>
      <button title="links drehen" onClick={() => dispatch({ type: 'Rotate', node_id: node.id, direction: 'left' })}>↺</button>
    </div>
  )
}
