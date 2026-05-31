import { useEffect, useState, useCallback } from 'react'
import { core } from './core'
import { Tree } from './Tree'
import { PreviewControls } from './PreviewControls'
import { ContextMenu } from './ContextMenu'
import './App.css'

function findNode(node, id) {
  if (node.id === id) return node
  for (const c of node.children ?? []) {
    const r = findNode(c, id)
    if (r) return r
  }
  return null
}

export default function App() {
  const [state, setState] = useState(null) // { session, tree, can_undo, can_redo }
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [pages, setPages] = useState(null) // null = nothing rendered yet, [] = no preview
  const [busy, setBusy] = useState(0) // active async core calls (counter)
  const [menu, setMenu] = useState(null) // context menu { x, y, node }
  const [zoom, setZoom] = useState(1) // preview zoom factor

  // run any core call with the global busy indicator on
  const run = useCallback((promise) => {
    setBusy((n) => n + 1)
    return promise.finally(() => setBusy((n) => Math.max(0, n - 1)))
  }, [])

  const apply = (resp) => {
    if (!resp) return
    if (resp.ok === false) {
      if (resp.error !== 'cancelled') setError(resp.error)
      return
    }
    setError(null)
    setState(resp)
  }

  const session = state?.session

  const renderNode = useCallback(
    (node) => {
      if (!node) { setPages(null); return }
      run(core.render(session, node.id)).then((resp) => setPages(resp?.ok ? resp.pages : []))
    },
    [session, run],
  )

  useEffect(() => {
    run(core.open()).then(apply).catch((e) => setError(String(e.message || e)))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // after any edit/undo/redo: apply, keep `selected` fresh from the new tree, re-render preview
  const afterChange = useCallback(
    (resp) => {
      apply(resp)
      if (resp?.ok && selected) {
        const fresh = findNode(resp.tree, selected.id)
        setSelected(fresh)
        renderNode(fresh)
      }
    },
    [selected, renderNode],
  )

  const dispatch = useCallback(
    (command) => run(core.dispatch(session, command)).then(afterChange),
    [session, afterChange, run],
  )
  const undo = () => run(core.undo(session)).then(afterChange)
  const redo = () => run(core.redo(session)).then(afterChange)

  const select = useCallback(
    (node) => {
      setSelected(node)
      setPages(null)
      renderNode(node)
    },
    [renderNode],
  )

  const openFile = () =>
    run(core.openFile(session)).then((resp) => {
      apply(resp)
      if (resp?.ok) { setSelected(null); setPages(null) }
    })

  if (!state && !error) {
    return (
      <div className="app loading">
        <div className="spinner big" />
        <p className="status">Verbinde mit Core…</p>
      </div>
    )
  }

  return (
    <div className={busy ? 'app busy' : 'app'}>
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
          {busy ? <span className="spinner" title="Arbeite…" /> : null}
        </div>
      </header>

      {error && <p className="error">⚠ {error}</p>}

      <div className="body">
        <div className="pane tree-pane">
          {state && (
            <Tree
              node={state.tree}
              selectedId={selected?.id}
              onSelect={select}
              onContext={(x, y, node) => setMenu({ x, y, node })}
            />
          )}
        </div>
        <div className="pane preview-pane">
          {selected && <PreviewControls key={selected.id} node={selected} session={session} dispatch={dispatch} />}
          {selected && pages?.length > 0 && (
            <div className="zoom-bar">
              <button onClick={() => setZoom((z) => Math.max(0.25, z - 0.25))} title="kleiner">−</button>
              <span>{Math.round(zoom * 100)}%</span>
              <button onClick={() => setZoom((z) => Math.min(4, z + 0.25))} title="größer">＋</button>
              <button onClick={() => setZoom(1)} title="zurücksetzen">100%</button>
            </div>
          )}
          {!selected && <p className="status">Knoten auswählen für die Vorschau</p>}
          {selected && busy > 0 && pages === null && <div className="spinner big" />}
          {selected && busy === 0 && pages?.length === 0 && (
            <p className="status">Keine Vorschau (Ordner oder leer)</p>
          )}
          {selected && pages?.map((src, i) => (
            <img key={i} src={src} alt={`Seite ${i + 1}`} className="preview-page" style={{ width: `${zoom * 100}%` }} />
          ))}
        </div>
      </div>

      <ContextMenu menu={menu} dispatch={dispatch} onClose={() => setMenu(null)} />
    </div>
  )
}
