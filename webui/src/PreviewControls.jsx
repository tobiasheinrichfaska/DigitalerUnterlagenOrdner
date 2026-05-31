// Compression controls for the selected leaf, shown above its preview (like the
// old app's preview panel): a Komprimieren dropdown + commit / reset / rotate.
// Tree/document operations (split, status, folders, …) live in the context menu.

const DPIS = [72, 100, 150, 200, 300]

export function PreviewControls({ node, dispatch }) {
  if (node.is_folder) return null
  const cmd = (extra) => dispatch({ ...extra, node_id: node.id })

  return (
    <div className="preview-controls">
      <select
        className="compress-select"
        value=""
        disabled={node.no_compression}
        onChange={(e) => {
          const dpi = Number(e.target.value)
          e.target.value = ''
          if (dpi) cmd({ type: 'Compress', dpi })
        }}
      >
        <option value="">Komprimieren…{node.is_compressed ? ` (aktuell ${node.dpi_current} DPI)` : ''}</option>
        {DPIS.map((d) => (
          <option key={d} value={d}>{d} DPI</option>
        ))}
      </select>

      <button onClick={() => cmd({ type: 'Commit' })} disabled={!node.is_compressed}>
        ✓ Lesbarkeit geprüft
      </button>
      <button onClick={() => cmd({ type: 'Reset' })} disabled={!node.is_compressed}>
        Zurücksetzen
      </button>
      <span className="sep" />
      <button title="rechts drehen" onClick={() => cmd({ type: 'Rotate', direction: 'right' })}>↻</button>
      <button title="links drehen" onClick={() => cmd({ type: 'Rotate', direction: 'left' })}>↺</button>
    </div>
  )
}
