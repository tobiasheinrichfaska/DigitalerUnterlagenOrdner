// Compression controls for the selected leaf (like the old app's preview panel):
// selecting a leaf always compresses and picks the best method; a DPI slider
// re-runs; the dropdown shows the chosen method and includes "Original" (no
// compression). ❓ Lesbarkeit geprüft / rotate. Undo handles reverting (no reset).
import { useState, useEffect } from 'react'
import { core } from './core'

const kb = (n) => `${Math.round(n / 1024)} KB`

export function PreviewControls({ node, session, dispatch, defaultDpi = 150 }) {
  const [dpi, setDpi] = useState(node.dpi_current ?? defaultDpi)
  const [options, setOptions] = useState(null) // [{method, size}] smallest first
  const off = node.no_compression
  // The chosen method lives in the model now → the dropdown is authoritative and
  // survives reselect / undo / reload. ('original' = no compression.)
  const method = off ? 'original' : (node.compression_method ?? 'original')

  // apply compression: fetch the method list first (so we know the best), then
  // dispatch Compress with an explicit method so the model records the choice.
  // m === null → auto-pick best; m === 'original' → Reset (no compression).
  const apply = (d, m = null) => {
    if (m === 'original') {
      dispatch({ type: 'Reset', node_id: node.id })
      return
    }
    core.compressOptions(session, node.id, d).then((r) => {
      const opts = r?.ok ? r.options : []
      setOptions(opts)
      const chosen = m ?? opts[0]?.method
      if (chosen) dispatch({ type: 'Compress', node_id: node.id, dpi: d, method: chosen })
    })
  }

  // on select: a node that already carries a compression keeps its saved method
  // (just load the labels); a fresh leaf auto-compresses and picks the best.
  useEffect(() => {
    if (off) { setOptions([]); return }
    if (node.is_compressed) {
      core.compressOptions(session, node.id, dpi).then((r) => setOptions(r?.ok ? r.options : []))
    } else {
      apply(dpi)
    }
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
