// Compression controls for the selected leaf (like the old app's preview panel):
// a DPI slider, a method dropdown (jpg/png/pikepdf — best marked), and
// ? Lesbarkeit geprüft / Zurücksetzen / rotate. Operations live in the context menu.
import { useState } from 'react'
import { core } from './core'

const kb = (n) => `${Math.round(n / 1024)} KB`

export function PreviewControls({ node, session, dispatch }) {
  const [dpi, setDpi] = useState(node.dpi_current ?? 150)
  const [options, setOptions] = useState(null) // [{method, size}] smallest first
  if (node.is_folder) return null
  const off = node.no_compression

  const compress = (method = null) => dispatch({ type: 'Compress', node_id: node.id, dpi, method })

  // releasing the slider compresses (best method) and lists the available methods
  const onRelease = () => {
    if (off) return
    compress()
    core.compressOptions(session, node.id, dpi).then((r) => setOptions(r?.ok ? r.options : []))
  }

  return (
    <div className="preview-controls">
      <label className="dpi" title="Kompressions-DPI">
        DPI <b>{dpi}</b>
        <input
          type="range" min="50" max="300" step="10" value={dpi} disabled={off}
          onChange={(e) => setDpi(Number(e.target.value))}
          onMouseUp={onRelease} onTouchEnd={onRelease}
        />
      </label>

      <select
        className="compress-select" value="" disabled={off || !options?.length}
        onChange={(e) => { const m = e.target.value; e.target.value = ''; if (m) compress(m) }}
      >
        <option value="">{options?.length ? 'Methode wählen…' : '(Methode nach DPI-Wahl)'}</option>
        {options?.map((o, i) => (
          <option key={o.method} value={o.method}>
            {o.method} — {kb(o.size)}{i === 0 ? ' · beste' : ''}
          </option>
        ))}
      </select>

      <button onClick={() => dispatch({ type: 'Commit', node_id: node.id })} disabled={!node.is_compressed}>
        ❓ Lesbarkeit geprüft
      </button>
      <button onClick={() => dispatch({ type: 'Reset', node_id: node.id })} disabled={!node.is_compressed}>
        Zurücksetzen
      </button>
      <span className="sep" />
      <button title="rechts drehen" onClick={() => dispatch({ type: 'Rotate', node_id: node.id, direction: 'right' })}>↻</button>
      <button title="links drehen" onClick={() => dispatch({ type: 'Rotate', node_id: node.id, direction: 'left' })}>↺</button>
    </div>
  )
}
