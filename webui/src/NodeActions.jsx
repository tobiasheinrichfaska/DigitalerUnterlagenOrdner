// Actions for the selected node — all dispatch real (undoable) core commands.

const STATUSES = [
  ['erfasst', 'Erfasst'],
  ['zu erfassen', 'Zu erfassen'],
  ['vorjahreswert', 'Vorjahr'],
]

export function NodeActions({ node, dispatch }) {
  const cmd = (extra) => dispatch({ ...extra, node_id: node.id })
  const isLeaf = !node.is_folder

  return (
    <div className="node-actions">
      <span className="na-name">{node.is_folder ? '📁' : '📄'} {node.name}</span>

      <div className="na-group">
        {STATUSES.map(([key, label]) => (
          <button
            key={key}
            className={node.status === key ? 'active' : ''}
            onClick={() => cmd({ type: 'SetStatus', status: key })}
          >
            {label}
          </button>
        ))}
      </div>

      {isLeaf && (
        <div className="na-group">
          <button onClick={() => cmd({ type: 'Compress', dpi: 150 })} disabled={node.no_compression}>
            Komprimieren
          </button>
          <button onClick={() => cmd({ type: 'Commit' })} disabled={!node.is_compressed}>
            Lesbarkeit geprüft
          </button>
          <button onClick={() => cmd({ type: 'Reset' })} disabled={!node.is_compressed}>
            Zurücksetzen
          </button>
          <button title="rechts drehen" onClick={() => cmd({ type: 'Rotate', direction: 'right' })}>↻</button>
          <button title="links drehen" onClick={() => cmd({ type: 'Rotate', direction: 'left' })}>↺</button>
          <button onClick={() => cmd({ type: 'Split' })}>Splitten</button>
        </div>
      )}

      <div className="na-group period" key={node.id}>
        <span>Zeitraum</span>
        <input
          type="number" placeholder="von" defaultValue={node.vz_start ?? ''}
          onBlur={(e) => cmd({ type: 'SetPeriod', vz_start: e.target.value ? Number(e.target.value) : null, vz_end: node.vz_end })}
        />
        <span>–</span>
        <input
          type="number" placeholder="bis" defaultValue={node.vz_end ?? ''}
          onBlur={(e) => cmd({ type: 'SetPeriod', vz_start: node.vz_start, vz_end: e.target.value ? Number(e.target.value) : null })}
        />
      </div>
    </div>
  )
}
