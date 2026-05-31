import { useEffect, useState, useCallback } from 'react'
import { core } from './core'
import { Tree } from './Tree'
import './App.css'

export default function App() {
  const [state, setState] = useState(null) // { session, tree, can_undo, can_redo }
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [pages, setPages] = useState(null) // null = nothing rendered yet, [] = no preview
  const [busy, setBusy] = useState(false)

  const apply = (resp) => {
    if (!resp) return
    if (resp.ok === false) {
      if (resp.error !== 'cancelled') setError(resp.error)
      return
    }
    setError(null)
    setState(resp)
  }

  useEffect(() => {
    core.open().then(apply).catch((e) => setError(String(e.message || e)))
  }, [])

  const session = state?.session

  // Re-render the currently selected node's preview (after edits / undo / redo).
  const renderSelected = useCallback(() => {
    if (!selected) return
    setBusy(true)
    core.render(session, selected.id).then((resp) => {
      setBusy(false)
      setPages(resp?.ok ? resp.pages : [])
    })
  }, [session, selected])

  const dispatch = useCallback(
    (command) => core.dispatch(session, command).then((r) => { apply(r); renderSelected() }),
    [session, renderSelected],
  )

  const undo = () => core.undo(session).then((r) => { apply(r); renderSelected() })
  const redo = () => core.redo(session).then((r) => { apply(r); renderSelected() })

  const select = useCallback(
    (node) => {
      setSelected(node)
      setPages(null)
      setBusy(true)
      core.render(session, node.id).then((resp) => {
        setBusy(false)
        setPages(resp?.ok ? resp.pages : [])
      })
    },
    [session],
  )

  const openFile = () =>
    core.openFile(session).then((resp) => {
      apply(resp)
      if (resp?.ok) { setSelected(null); setPages(null) }
    })

  if (!state && !error) {
    return <div className="app"><p className="status">Verbinde mit Core…</p></div>
  }

  return (
    <div className="app">
      <header>
        <h1>DigitalerBelegeOrdner</h1>
        <div className="toolbar">
          <button onClick={openFile}>📂 Öffnen</button>
          <button onClick={() => core.saveFile(session)}>💾 Speichern</button>
          <span className="sep" />
          <button
            onClick={() =>
              dispatch({ type: 'AddFolder', parent_id: state.tree.id, name: 'Neuer Ordner', index: null, new_id: null })
            }
          >
            ＋ Ordner
          </button>
          <button onClick={undo} disabled={!state?.can_undo} title="Rückgängig">↶</button>
          <button onClick={redo} disabled={!state?.can_redo} title="Wiederholen">↷</button>
        </div>
      </header>

      {error && <p className="error">⚠ {error}</p>}

      <div className="body">
        <div className="pane tree-pane">
          {state && <Tree node={state.tree} dispatch={dispatch} selectedId={selected?.id} onSelect={select} />}
        </div>
        <div className="pane preview-pane">
          {!selected && <p className="status">Knoten auswählen für die Vorschau</p>}
          {selected && busy && <p className="status">Rendere…</p>}
          {selected && !busy && pages?.length === 0 && (
            <p className="status">Keine Vorschau (Ordner oder leer)</p>
          )}
          {selected && pages?.map((src, i) => (
            <img key={i} src={src} alt={`Seite ${i + 1}`} className="preview-page" />
          ))}
        </div>
      </div>
    </div>
  )
}
