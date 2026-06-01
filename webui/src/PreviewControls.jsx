// Compression controls for the selected leaf (like the old app's preview panel):
// selecting a leaf always compresses and picks the best method; a DPI slider
// re-runs; the dropdown shows the chosen method and includes "Original" (no
// compression). ❓ Lesbarkeit geprüft / rotate. Undo handles reverting (no reset).
import { useState, useEffect } from 'react'
import { core } from './core'

const kb = (n) => `${Math.round(n / 1024)} KB`

export function PreviewControls({ node, session, dispatch }) {
  const [dpi, setDpi] = useState(node.dpi_current ?? 150)
  const [options, setOptions] = useState(null) // [{method, size}] smallest first
  const [method, setMethod] = useState('original')
  const off = node.no_compression

  // apply compression (best, a chosen method, or "original" = none) and keep the
  // method list + selection in sync.
  const apply = (d, m = null) => {
    if (m === 'original') {
      dispatch({ type: 'Reset', node_id: node.id })
      setMethod('original')
      return
    }
    dispatch({ type: 'Compress', node_id: node.id, dpi: d, method: m })
    core.compressOptions(session, node.id, d).then((r) => {
      const opts = r?.ok ? r.options : []
      setOptions(opts)
      setMethod(m ?? opts[0]?.method ?? 'original')
    })
  }

  // on select: always compress + choose best (so the dropdown is ready)
  useEffect(() => {
    if (off) { setOptions([]); setMethod('original'); return }
    apply(dpi)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps  (keyed per node)

  return (
    <div className="preview-controls">
      <label className="dpi" title="Kompressions-DPI">
        DPI <b>{dpi}</b>
        <input
          type="range" min="50" max="300" step="10" value={dpi} disabled={off}
          onChange={(e) => setDpi(Number(e.target.value))}
          onMouseUp={() => apply(dpi)} onTouchEnd={() => apply(dpi)}
        />
      </label>

      <select className="compress-select" value={method} disabled={off}
        onChange={(e) => apply(dpi, e.target.value)}>
        <option value="original">Original (keine Kompression)</option>
        {options?.map((o, i) => (
          <option key={o.method} value={o.method}>
            {o.method} — {kb(o.size)}{i === 0 ? ' · beste' : ''}
          </option>
        ))}
      </select>

      <button onClick={() => dispatch({ type: 'Commit', node_id: node.id })} disabled={!node.is_compressed}>
        ❓ Lesbarkeit geprüft
      </button>
      <span className="sep" />
      <button title="rechts drehen" onClick={() => dispatch({ type: 'Rotate', node_id: node.id, direction: 'right' })}>↻</button>
      <button title="links drehen" onClick={() => dispatch({ type: 'Rotate', node_id: node.id, direction: 'left' })}>↺</button>
    </div>
  )
}
