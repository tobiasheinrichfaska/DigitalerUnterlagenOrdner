import { useEffect, useState, useCallback, useRef } from 'react'
import { core } from './core'
import { Tree } from './Tree'
import { PreviewControls } from './PreviewControls'
import { ContextMenu } from './ContextMenu'
import './App.css'

function readAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(r.result)
    r.onerror = () => reject(r.error)
    r.readAsDataURL(file)
  })
}

function findNode(node, id) {
  if (node.id === id) return node
  for (const c of node.children ?? []) {
    const r = findNode(c, id)
    if (r) return r
  }
  return null
}

function findParent(node, id, parent = null) {
  if (node.id === id) return parent
  for (const c of node.children ?? []) {
    const r = findParent(c, id, node)
    if (r) return r
  }
  return null
}

// visible pre-order list of ids (excludes the implicit root) — for shift-range
function flattenIds(root) {
  const out = []
  const walk = (n) => { for (const c of n.children ?? []) { out.push(c.id); walk(c) } }
  walk(root)
  return out
}

// depth of a node (root's children = 0)
function depthOf(root, id, d = -1) {
  if (root.id === id) return d
  for (const c of root.children ?? []) {
    const r = depthOf(c, id, d + 1)
    if (r !== null) return r
  }
  return null
}

// Drop levels for the gap AFTER `id`: deepest first (insert right after the row,
// at its own level), then — only while the row is the *last child* of its parent —
// each shallower ancestor level, up to the root. Lets a bottom drop choose how far
// to "pop out". Each entry = { parentId, index, depth }.
function afterLevels(root, id) {
  const levels = []
  let curId = id
  let depth = depthOf(root, id)
  while (true) {
    const parent = findParent(root, curId)
    if (!parent) break
    const idx = (parent.children ?? []).findIndex((c) => c.id === curId)
    if (idx === -1) break
    levels.push({ parentId: parent.id, index: idx + 1, depth, parentName: parent.id === root.id ? null : parent.name })
    const isLast = idx === parent.children.length - 1
    if (!isLast || parent.id === root.id) break
    curId = parent.id
    depth -= 1
  }
  return levels
}

export default function App() {
  const [state, setState] = useState(null) // { session, tree, can_undo, can_redo }
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null) // transient success message (e.g. export)
  const [selected, setSelected] = useState(null) // primary node (drives the preview)
  const [selectedIds, setSelectedIds] = useState([]) // multi-selection (Merge / group / multi-move)
  const [anchorId, setAnchorId] = useState(null) // anchor for shift-range select
  const [pages, setPages] = useState(null) // null = nothing rendered yet, [] = no preview
  const [busy, setBusy] = useState(0) // active async core calls (counter)
  const [menu, setMenu] = useState(null) // context menu { x, y, node }
  const [zoom, setZoom] = useState(1) // preview zoom factor
  const [config, setConfig] = useState(null) // fixed core defaults (e.g. default_dpi)
  const [previewReq, setPreviewReq] = useState(null) // {dpi, method} → transient compressed preview; null → plain
  const [dropActive, setDropActive] = useState(false) // OS file drag hovering the window
  const [dirty, setDirty] = useState(false) // unsaved changes since last open/save
  const [pending, setPending] = useState([]) // optimistic import placeholders in the tree
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
    setNotice(null)
    setState(resp)
  }

  const session = state?.session

  // Unified preview rendering for the selected node. Folders → []. For a leaf,
  // PreviewControls sets a request (previewReq = {dpi, method}) → a *transient*
  // compressed preview (render_compressed, no document mutation); null → the plain
  // stored bytes. Re-fires when `selected` identity changes (every edit replaces
  // it) or the request changes, so edits and method/DPI browsing both refresh.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- clearing the preview is intended
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

  // push this window's unsaved state to the host (per-window close guard).
  // (A Python-side flag, not evaluate_js — the latter hangs during window close.)
  useEffect(() => { core.setDirty(dirty).catch(() => {}) }, [dirty])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time initial load
    run(core.open()).then(apply).catch((e) => setError(String(e.message || e)))
    core.config().then((r) => { if (r?.ok) setConfig(r) }).catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // after any edit/undo/redo: apply, keep `selected` fresh from the new tree
  // (the preview effect re-renders because `selected`'s identity changed).
  const afterChange = useCallback(
    (resp) => {
      apply(resp)
      if (resp?.ok) {
        setDirty(true) // an edit/undo/redo/import changed the document
        setSelectedIds((ids) => ids.filter((id) => findNode(resp.tree, id))) // drop vanished ids
        if (selected) setSelected(findNode(resp.tree, selected.id))
      }
    },
    [selected],
  )

  const dispatch = useCallback(
    (command) => run(core.dispatch(session, command)).then(afterChange),
    [session, afterChange, run],
  )
  const undo = () => run(core.undo(session)).then(afterChange)
  const redo = () => run(core.redo(session)).then(afterChange)

  // imports land in the selected folder (or root if a leaf/nothing is selected)
  const importTarget = () => (selected?.is_folder ? selected.id : null)
  const handleImport = (promise) =>
    run(promise).then((resp) => {
      afterChange(resp)
      if (resp?.warning) setError(`Teilweise importiert — ${resp.warning}`)
    })

  // read each dropped file's content and import it under parentId at index (null =
  // append). Multiple files keep their order (index bumps per file).
  const onDropFiles = async (files, parentId, index = null) => {
    setDropActive(false)
    const target = parentId || state?.tree?.id
    const list = Array.from(files || [])
    const stamp = Date.now()
    const items = list.map((file, i) => ({
      key: `pending-${stamp}-${i}`, file, name: file.name,
      idx: index == null ? null : index + i,
    }))
    // show ALL dropped files in the tree immediately as progress placeholders
    setPending((p) => [...p, ...items.map(({ key, name }) => ({ key, name, parentId: target }))])
    // import sequentially (keeps order); drop each placeholder as it finishes
    for (const it of items) {
      try {
        const data = await readAsDataURL(it.file)
        await handleImport(core.importBytes(session, it.name, data, parentId, it.idx))
      } catch (err) {
        setError(String(err?.message || err))
      } finally {
        setPending((p) => p.filter((x) => x.key !== it.key))
      }
    }
  }

  // OS file drag onto the window: tree rows handle precise targeting (drop onto a
  // folder); this is the fallback for drops elsewhere → the selected folder/root.
  useEffect(() => {
    if (!session) return undefined
    const hasFiles = (e) => Array.from(e.dataTransfer?.types || []).includes('Files')
    const onOver = (e) => { if (hasFiles(e)) { e.preventDefault(); setDropActive(true) } }
    const onLeave = (e) => { if (!e.relatedTarget) setDropActive(false) }
    const onDrop = (e) => {
      if (!hasFiles(e)) return
      e.preventDefault()
      onDropFiles(e.dataTransfer.files, importTarget())
    }
    window.addEventListener('dragover', onOver)
    window.addEventListener('dragleave', onLeave)
    window.addEventListener('drop', onDrop)
    return () => {
      window.removeEventListener('dragover', onOver)
      window.removeEventListener('dragleave', onLeave)
      window.removeEventListener('drop', onDrop)
    }
  }) // re-binds each render so it closes over the current session/selected

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

  // drag a multi-selection → move all of them at the drop position (the core
  // discounts the moved-out siblings before the slot). index null = append/into.
  const onMoveMany = useCallback((ids, newParentId, index = null) => {
    dispatch({ type: 'MoveMany', node_ids: ids, new_parent_id: newParentId, index })
  }, [dispatch])

  // pop-out drop levels for the gap after a row (for the slide-to-choose-level UX)
  const levelsFor = useCallback((id) => (state?.tree ? afterLevels(state.tree, id) : []), [state])

  // plain click → single-select; Ctrl/Cmd-click → toggle; Shift-click → range
  // (over the visible pre-order, so it spans depths). The primary (preview) node
  // is the clicked one, or the last remaining on a Ctrl-deselect.
  const select = useCallback((node, mods = {}) => {
    const { ctrl = false, shift = false } = mods
    if (shift && anchorId && state?.tree) {
      const order = flattenIds(state.tree)
      const a = order.indexOf(anchorId)
      const b = order.indexOf(node.id)
      if (a !== -1 && b !== -1) {
        const [lo, hi] = a <= b ? [a, b] : [b, a]
        setSelectedIds(order.slice(lo, hi + 1))
        setSelected(node); setPages(null); setPreviewReq(null)
        return
      }
    }
    if (ctrl && selectedIds.includes(node.id)) {
      const next = selectedIds.filter((i) => i !== node.id)
      setSelectedIds(next)
      setSelected(next.length ? findNode(state.tree, next[next.length - 1]) : null)
    } else {
      setSelectedIds(ctrl ? [...selectedIds, node.id] : [node.id])
      setSelected(node)
    }
    setAnchorId(node.id)
    setPages(null)
    setPreviewReq(null) // PreviewControls re-sets it on mount for a leaf
  }, [selectedIds, state, anchorId])

  // 2+ selected sibling leaves → the ids that can be merged into one PDF (else null)
  const mergeable = (() => {
    if (selectedIds.length < 2 || !state?.tree) return null
    const nodes = selectedIds.map((id) => findNode(state.tree, id))
    if (nodes.some((n) => !n || n.is_folder)) return null
    const parents = selectedIds.map((id) => findParent(state.tree, id)?.id)
    if (new Set(parents).size !== 1 || parents.some((p) => p == null)) return null
    return selectedIds
  })()

  // 2+ selected nodes (any depth) → group into a new folder. The folder goes in
  // their common parent if they share one, else at the root (always safe).
  const groupable = (() => {
    if (selectedIds.length < 2 || !state?.tree) return null
    if (selectedIds.some((id) => !findNode(state.tree, id))) return null
    const parents = selectedIds.map((id) => findParent(state.tree, id)?.id)
    const parentId = new Set(parents).size === 1 && parents[0] != null ? parents[0] : state.tree.id
    return { ids: selectedIds, parentId }
  })()

  const openFile = () => {
    if (dirty && !window.confirm('Das aktuelle Dokument hat ungespeicherte Änderungen.\nTrotzdem eine andere Datei öffnen und die Änderungen verwerfen?')) return
    run(core.openFile(session)).then((resp) => {
      apply(resp)
      if (resp?.ok) { setSelected(null); setSelectedIds([]); setPages(null); setPreviewReq(null); setDirty(false) }
    })
  }

  const saveFile = () =>
    run(core.saveFile(session)).then((resp) => { if (resp?.ok) { setDirty(false); setNotice('Gespeichert') } })

  // export to a TOC PDF. nodeIds = null → the WHOLE document (toolbar button);
  // the context menu passes specific ids for an explicit selection export.
  const exportPdf = (nodeIds = null) =>
    run(core.exportPdf(session, nodeIds)).then((resp) => {
      if (resp?.ok) { setError(null); setNotice(`PDF exportiert (${resp.count} ${resp.count === 1 ? 'Eintrag' : 'Einträge'})`) }
      else if (resp?.error && resp.error !== 'cancelled') setError(resp.error)
    })

  // keyboard shortcuts (ignored while typing in a field)
  useEffect(() => {
    if (!session) return undefined
    const onKey = (e) => {
      const tag = e.target?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      const mod = e.ctrlKey || e.metaKey
      const k = e.key.toLowerCase()
      if (mod && k === 's') { e.preventDefault(); saveFile() }
      else if (mod && k === 'o') { e.preventDefault(); openFile() }
      else if (mod && k === 'e') { e.preventDefault(); exportPdf() }
      else if (mod && k === 'n') { e.preventDefault(); core.newWindow() }
      else if (mod && k === 'z' && e.shiftKey) { e.preventDefault(); if (state?.can_redo) redo() }
      else if (mod && k === 'y') { e.preventDefault(); if (state?.can_redo) redo() }
      else if (mod && k === 'z') { e.preventDefault(); if (state?.can_undo) undo() }
      else if (k === 'delete' && selected) { e.preventDefault(); dispatch({ type: 'Delete', node_id: selected.id }) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }) // re-binds each render to close over current handlers/state

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
        <h1 title="DigitalerBelegeOrdner">{state?.tree?.name || 'DigitalerBelegeOrdner'}{dirty ? ' •' : ''}</h1>
        <div className="toolbar">
          <button onClick={openFile}>📂 Öffnen</button>
          <button onClick={() => core.newWindow()} title="Weiteres Dokument in neuem Fenster">🗗 Neues Fenster</button>
          <button onClick={() => handleImport(core.importDialog(session, importTarget()))}>📥 Importieren</button>
          <button onClick={saveFile}>💾 Speichern{dirty ? ' •' : ''}</button>
          <button onClick={() => exportPdf(selectedIds.length ? selectedIds : null)} title="Als PDF mit Inhaltsverzeichnis exportieren (Auswahl, sonst das ganze Dokument)">⬇ Export PDF{selectedIds.length ? ` (Auswahl ${selectedIds.length})` : ''}</button>
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
      {notice && !error && <p className="notice">✓ {notice}</p>}

      <div className="body">
        <div className="pane tree-pane">
          {state && (
            <Tree
              node={state.tree}
              selectedIds={selectedIds}
              primaryId={selected?.id}
              onSelect={select}
              onContext={(x, y, node) => setMenu({ x, y, node })}
              onMove={onMove}
              onMoveMany={onMoveMany}
              levelsFor={levelsFor}
              onDropFiles={onDropFiles}
              pending={pending}
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

      <ContextMenu menu={menu} dispatch={dispatch} onClose={() => setMenu(null)} mergeIds={mergeable} group={groupable} onExport={exportPdf} selectedIds={selectedIds} />

      {dropActive && (
        <div className="drop-overlay">
          <div className="drop-overlay-badge">
            📥 Dateien ablegen — auf eine Position im Baum (rein/zwischen) für ein genaues Ziel, sonst in {selected?.is_folder ? selected.name : 'oberste Ebene'}
          </div>
        </div>
      )}
    </div>
  )
}
