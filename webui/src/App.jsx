import { useEffect, useState, useCallback } from 'react'
import { core } from './core'
import { Tree } from './Tree'
import './App.css'

export default function App() {
  const [state, setState] = useState(null) // { session, tree, can_undo, can_redo }
  const [error, setError] = useState(null)

  const apply = (resp) => {
    if (!resp) return
    if (resp.ok === false) {
      setError(resp.error)
      return
    }
    setError(null)
    setState(resp)
  }

  useEffect(() => {
    core.open().then(apply).catch((e) => setError(String(e.message || e)))
  }, [])

  const session = state?.session
  const dispatch = useCallback(
    (command) => core.dispatch(session, command).then(apply),
    [session],
  )

  if (!state && !error) {
    return (
      <div className="app">
        <p className="status">Verbinde mit Core…</p>
      </div>
    )
  }

  return (
    <div className="app">
      <header>
        <h1>DigitalerBelegeOrdner</h1>
        <div className="toolbar">
          <button
            onClick={() =>
              dispatch({ type: 'AddFolder', parent_id: state.tree.id, name: 'Neuer Ordner', index: null, new_id: null })
            }
          >
            ＋ Ordner
          </button>
          <button onClick={() => core.undo(session).then(apply)} disabled={!state?.can_undo}>
            ↶ Rückgängig
          </button>
          <button onClick={() => core.redo(session).then(apply)} disabled={!state?.can_redo}>
            ↷ Wiederholen
          </button>
        </div>
      </header>

      {error && <p className="error">⚠ {error}</p>}

      {state && <Tree node={state.tree} dispatch={dispatch} />}
    </div>
  )
}
