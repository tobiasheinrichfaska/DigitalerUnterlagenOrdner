import { useEffect, useState, useCallback, useRef } from 'react'
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
  const [config, setConfig] = useState(null) // fixed core defaults (e.g. default_dpi)
  const [previewReq, setPreviewReq] = useState(null) // {dpi, method} → transient compressed preview; null → plain
  const previewRef = useRef(null)

  // Ctrl + mouse-wheel zooms the preview (native non-passive listener so we can
  // preventDefault the webview's page zoom).
  useEffect(() => {
    const el = previewRef.current
    if (!el) return
    const onWheel = (e) => {
      if (!e.ctrlKey) return
      e.preventDefault()
      setZoom((z) => Math.min(4, Math.max(0.25, z + (e.deltaY < 0 ? 0.15 : -0.15))))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  })

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

  // Unified preview rendering for the selected node. Folders → []. For a leaf,
  // PreviewControls sets a request (previewReq = {dpi, method}) → a *transient*
  // compressed preview (render_compressed, no document mutation); null → the plain
  // stored bytes. Re-fires when `selected` identity changes (every edit replaces
  // it) or the request changes, so edits and method/DPI browsing both refresh.
  useEffect(() => {
    if (!session || !selected) { setPages(null); return }
    if (selected.is_folder) {
      run(core.render(session, selected.id)).then((r) => setPages(r?.ok ? r.pages : []))
      return
    }
    const p = previewReq
      ? core.renderCompressed(session, selected.id, previewReq.dpi, previewReq.method)
      : core.render(session, selected.id)
    run(p).then((r) => setPages(r?.ok ? r.pages : []))
  }, [selected, previewReq, session]) // eslint-disable-line react-hooks/exhaustive-deps

  const onPreview = useCallback((req) => setPreviewReq(req), [])

  useEffect(() => {
    run(core.open()).then(apply).catch((e) => setError(String(e.message || e)))
    core.config().then((r) => { if (r?.ok) setConfig(r) }).catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // after any edit/undo/redo: apply, keep `selected` fresh from the new tree
  // (the preview effect re-renders because `selected`'s identity changed).
  const afterChange = useCallback(
    (resp) => {
      apply(resp)
      if (resp?.ok && selected) setSelected(findNode(resp.tree, selected.id))
    },
    [selected],
  )

  // dispatch a command; if the core blocks it as a pending-change clash, ask the
  // user and re-dispatch with force (the "block unless forced" policy).
  const dispatch = useCallback(
    (command) =>
      run(core.dispatch(session, command)).then((resp) => {
        if (resp?.risk === 'pending_compression') {
          if (window.confirm(`${resp.error}\n\nTrotzdem fortfahren?`)) {
            return run(core.dispatch(session, { ...command, force: true })).then(afterChange)
          }
          return // cancelled — leave state untouched
        }
        afterChange(resp)
      }),
    [session, afterChange, run],
  )
  const undo = () => run(core.undo(session)).then(afterChange)
  const redo = () => run(core.redo(session)).then(afterChange)

  // drag-drop move: dispatch a Move command (the core is the source of truth).
  // Adjust the index for the core's remove-then-insert when reordering within the
  // same parent to a later slot (the source's removal shifts everything down one).
  const onMove = useCallback((nodeId, newParentId, index) => {
    let idx = index
    if (idx != null && state?.tree) {
      const parent = findNode(state.tree, newParentId)
      const from = parent?.children?.findIndex((c) => c.id === nodeId)
      if (from != null && from !== -1 && from < idx) idx = idx - 1
    }
    dispatch({ type: 'Move', node_id: nodeId, new_parent_id: newParentId, index: idx })
  }, [state, dispatch])

  const select = useCallback((node) => {
    setSelected(node)
    setPages(null)
    setPreviewReq(null) // PreviewControls re-sets it on mount for a leaf
  }, [])

  const openFile = () =>
    run(core.openFile(session)).then((resp) => {
      apply(resp)
      if (resp?.ok) { setSelected(null); setPages(null); setPreviewReq(null) }
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
              onMove={onMove}
            />
          )}
        </div>
        <div className="pane preview-pane" ref={previewRef}>
          {selected && <PreviewControls key={selected.id} node={selected} session={session} dispatch={dispatch} onPreview={onPreview} defaultDpi={config?.default_dpi ?? 150} />}
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
