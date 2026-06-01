// Working-preview compression controls for the selected leaf.
//
// Browsing the DPI slider and the method dropdown only shows a *transient*
// preview (App renders it via render_compressed) — nothing is written to the
// document, so there is no undo entry and the node never becomes "pending".
// The document changes only on a deliberate apply ("❓ Lesbarkeit geprüft" →
// Compress, or "Original" → Reset), which is the single undoable step.
import { useState, useEffect } from 'react'
import { core } from './core'

const kb = (n) => `${Math.round(n / 1024)} KB`

export function PreviewControls({ node, session, dispatch, onPreview, defaultDpi = 150 }) {
  const off = node.no_compression
  const [dpi, setDpi] = useState(node.dpi_current ?? defaultDpi)
  const [options, setOptions] = useState(null) // [{method, size}] smallest first
  const [method, setMethod] = useState(node.compression_method ?? 'original')

  // Show a transient preview of `m` at `d` (null request = plain/original).
  const preview = (d, m) => onPreview(m === 'original' ? null : { dpi: d, method: m })

  // (Re)initialise from the model whenever the *applied* compression changes —
  // mount, reselect, after apply/reset/rotate. Pure dropdown/slider browsing does
  // not touch the model, so it never re-fires this (no undo/preview thrash).
  useEffect(() => {
    if (off) { setOptions([]); setMethod('original'); onPreview(null); return }
    core.compressOptions(session, node.id, dpi).then((r) => {
      const opts = r?.ok ? r.options : []
      setOptions(opts)
      const m = node.compression_method ?? opts[0]?.method ?? 'original'
      setMethod(m)
      preview(dpi, m)
    })
  }, [node.id, node.is_compressed, node.compression_method, node.dpi_current]) // eslint-disable-line react-hooks/exhaustive-deps

  const onDpi = (d) => {
    setDpi(d)
    if (off) return
    core.compressOptions(session, node.id, d).then((r) => setOptions(r?.ok ? r.options : []))
    preview(d, method)
  }
  const onMethod = (m) => { setMethod(m); preview(dpi, m) }

  // is the current preview already what the document holds?
  const applied = node.is_compressed
    ? node.compression_method === method && node.dpi_current === dpi
    : method === 'original'

  const applyChoice = () => {
    if (method === 'original') {
      if (node.is_compressed) dispatch({ type: 'Reset', node_id: node.id })
    } else {
      dispatch({ type: 'Compress', node_id: node.id, dpi, method })
    }
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
        onChange={(e) => onMethod(e.target.value)}>
        <option value="original">Original (keine Kompression)</option>
        {options?.map((o, i) => (
          <option key={o.method} value={o.method}>
            {o.method} — {kb(o.size)}{i === 0 ? ' · beste' : ''}
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
