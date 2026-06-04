import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import { core } from './lib/core'
import { Tree } from './Tree'
import { PreviewControls } from './PreviewControls'
import { Preview } from './Preview'
import { ContextMenu } from './ContextMenu'
import { SaveDialog } from './SaveDialog'
import { TagEditor } from './TagEditor'
import { StatusBar } from './StatusBar'
import { allTags } from './lib/tags'
import { findNode, findParent, flattenIds, isAncestorOf, afterLevels } from './lib/tree'
import { visibleOrder, navStep, moveTarget, applyMove, locate } from './lib/treeNav'
import { resolveSelection } from './lib/selection'
import { useT } from './i18n/LanguageProvider'
import { LANGUAGE_NAMES } from './i18n/index'
import './App.css'

function readAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(r.result)
    r.onerror = () => reject(r.error)
    r.readAsDataURL(file)
  })
}

export default function App() {
  const { t, lang, setLang } = useT()
  const [state, setState] = useState(null) // { session, tree, can_undo, can_redo }
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null) // transient success message (e.g. export)
  const [selected, setSelected] = useState(null) // primary node (drives the preview)
  const [selectedIds, setSelectedIds] = useState([]) // multi-selection (Merge / group / multi-move)
  const [anchorId, setAnchorId] = useState(null) // anchor for shift-range select
  const [pages, setPages] = useState(null) // null = nothing rendered yet, [] = no preview
  const [busy, setBusy] = useState(0) // active async core calls (counter)
  const [menu, setMenu] = useState(null) // context menu { x, y, node }
  const [saveAsk, setSaveAsk] = useState(null) // save dialog { mode:'in'|'as', count }
  const [tagsOn, setTagsOn] = useState(false) // tagging off by default; auto-on when a loaded file has tags
  const toggleTags = () => setTagsOn((v) => !v)
  const [zoom, setZoom] = useState(1) // preview zoom factor
  const [config, setConfig] = useState(null) // fixed core defaults (e.g. default_dpi)
  const [previewReq, setPreviewReq] = useState(null) // {dpi, method} → transient compressed preview; null → plain
  const [pageInfo, setPageInfo] = useState(null) // {page, total} of the windowed preview viewport
  const [dropActive, setDropActive] = useState(false) // OS file drag hovering the window
  const [dirty, setDirty] = useState(false) // unsaved changes since last open/save
  const [pending, setPending] = useState([]) // optimistic import placeholders in the tree
  const [grab, setGrab] = useState(null) // keyboard carry: { id, tree } (optical preview until drop)
  const [treeWidth, setTreeWidth] = useState(() => {
    const v = parseInt(localStorage.getItem('beleg.treeWidth'), 10)
    return v >= 220 && v <= 800 ? v : 340 // px; remembered across sessions (UI prefs, not the document)
  })
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

  // stable identity (only stable state setters inside) so callbacks that depend
  // on it don't get re-created every render.
  const apply = useCallback((resp) => {
    if (!resp) return
    if (resp.ok === false) {
      if (resp.error !== 'cancelled') setError(resp.error)
      return
    }
    setError(null)
    setNotice(null)
    setState(resp)
  }, [])

  const session = state?.session

  // Unified preview rendering for the selected node. Folders → []. For a leaf,
  // PreviewControls sets a request (previewReq = {dpi, method}) → a *transient*
  // compressed preview (render_compressed, no document mutation); null → the plain
  // stored bytes. Re-fires when `selected` identity changes (every edit replaces
  // it) or the request changes, so edits and method/DPI browsing both refresh.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: reset the page indicator when the selected node / preview request changes
    setPageInfo(null) // stale page indicator until the new node reports its viewport
    if (!session || !selected) { setPages(null); return }
    if (selected.is_folder) {
      run(core.render(session, selected.id)).then((r) => setPages(r?.ok ? r.pages : []))
    } else {
      // leaves (plain stored bytes AND the compressed working-preview) are
      // windowed on demand by <Preview>; nothing to fetch here.
      setPages(null)
    }
  }, [selected, session]) // eslint-disable-line react-hooks/exhaustive-deps

  // every leaf preview is virtualized; only folders use the `pages` path
  const windowed = !!(selected && !selected.is_folder)

  const onPreview = useCallback((req) => setPreviewReq(req), [])

  // push this window's unsaved state to the host (per-window close guard).
  // (A Python-side flag, not evaluate_js — the latter hangs during window close.)
  useEffect(() => { core.setDirty(dirty).catch(() => {}) }, [dirty])

  useEffect(() => {
    // Fetch config first so we can honour a startup_path (a .belegtool handed
    // over by the legacy GUI's "open in new GUI"); otherwise open an empty doc.
    core.config()
      .then((r) => { if (r?.ok) setConfig(r); return r })
      .catch(() => null)
      .then((r) => run(core.open(null, r?.startup_path || null)).then((resp) => {
        apply(resp)
        if (resp?.ok && allTags(resp.tree).length > 0) setTagsOn(true) // a tagged file auto-enables tagging
      }))
      .catch((e) => setError(String(e.message || e)))
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
    [apply, selected],
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
    // a single file may keep its exact drop index; multiple files append (a fixed
    // index would collide once one file expands into several nodes).
    const useIndex = list.length === 1 ? index : null
    const items = list.map((file, i) => ({ key: `pending-${stamp}-${i}`, file, name: file.name }))
    // show ALL dropped files in the tree immediately as progress placeholders
    setPending((p) => [...p, ...items.map(({ key, name }) => ({ key, name, parentId: target }))])
    // import sequentially (keeps order); drop each placeholder as it finishes
    for (const it of items) {
      try {
        const data = await readAsDataURL(it.file)
        await handleImport(core.importBytes(session, it.name, data, parentId, useIndex))
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

  // Resolve a multi-selection to a clean (non-mixed) set, asking the user how to
  // handle any folder that overlaps with its own selected items. Reused by delete,
  // move, group and export. `warnNone` adds the destructive "this also affects the
  // folder's unselected contents" prompt (delete only). Returns ids[] or null (abort).
  const resolveSel = useCallback((ids, { warnNone = false } = {}) => {
    const tree = state?.tree
    if (!tree) return null
    const ask = (kind, name) => {
      if (kind === 'none') {
        return window.confirm(t('Der Ordner „{name}“ enthält nicht ausgewählte Elemente, die mit einbezogen werden. Fortfahren?', { name })) ? 'proceed' : 'abort'
      }
      if (window.confirm(t('„{name}“: den ganzen Ordner einbeziehen? (Abbrechen = nur die ausgewählten Elemente, Ordner ausschließen)', { name }))) return 'all'
      if (window.confirm(t('Nur die ausgewählten Elemente verwenden und „{name}“ ausschließen? (Abbrechen = Vorgang abbrechen)', { name }))) return 'exclude'
      return 'abort'
    }
    return resolveSelection(tree, ids, ask, { warnNone })
  }, [state, t])

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
    const clean = resolveSel(ids)  // resolve folder/child overlaps (no destructive warn)
    if (!clean || !clean.length) return
    dispatch({ type: 'MoveMany', node_ids: clean, new_parent_id: newParentId, index })
  }, [dispatch, resolveSel])

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

  // --- folder collapse/expand (persisted: SetCollapsed / SetAllCollapsed) ---
  const setCollapsedFor = useCallback((id, val) => dispatch({ type: 'SetCollapsed', node_id: id, collapsed: val }), [dispatch])
  const toggleCollapse = useCallback((id) => {
    const n = state?.tree && findNode(state.tree, id)
    if (n) setCollapsedFor(id, !n.collapsed)
  }, [state, setCollapsedFor])
  const expandAll = useCallback(() => dispatch({ type: 'SetAllCollapsed', collapsed: false }), [dispatch])
  const collapseAll = useCallback(() => dispatch({ type: 'SetAllCollapsed', collapsed: true }), [dispatch])

  // Stable callback + no-op guard: an inline onPage was recreated every render,
  // churning <Preview>'s fetch effect into a loop (constant "Vorschau lädt").
  const onPageInfo = useCallback((page, total) => {
    setPageInfo((p) => (p && p.page === page && p.total === total ? p : { page, total }))
  }, [])

  // total pages in this document (sum of leaf page counts) — for the cache "n / m"
  const docPages = useMemo(() => {
    let n = 0
    const walk = (node) => {
      if (!node) return
      if (!node.is_folder) n += node.pdf_length || 0
      ;(node.children || []).forEach(walk)
    }
    walk(state?.tree)
    return n
  }, [state?.tree])

  // Delete the whole selection (one undo), resolving folder/child overlaps first,
  // then focus the next remaining node.
  const deleteSelection = useCallback(() => {
    const tree = state?.tree
    const ids = selectedIds.length ? selectedIds : (selected ? [selected.id] : [])
    if (!ids.length || !tree) return
    const toDelete = resolveSel(ids, { warnNone: true })  // data layer rejects mixed
    if (!toDelete || !toDelete.length) return
    // pick the next node to focus: first still-present row after the deletion, else before
    const order = visibleOrder(tree)
    const gone = (id) => toDelete.includes(id) || toDelete.some((d) => isAncestorOf(tree, d, id))
    const firstIdx = order.findIndex((e) => gone(e.id))
    const nextId = (order.slice(firstIdx + 1).find((e) => !gone(e.id))
      || order.slice(0, Math.max(0, firstIdx)).reverse().find((e) => !gone(e.id)))?.id || null
    run(core.dispatch(session, { type: 'DeleteMany', node_ids: toDelete })).then((resp) => {
      apply(resp)
      if (resp?.ok) {
        setDirty(true)
        setSelectedIds(nextId ? [nextId] : [])
        setSelected(nextId ? findNode(resp.tree, nextId) : null)
        setPages(null)
        setPreviewReq(null)
      }
    })
  }, [selectedIds, selected, state, session, run, apply, resolveSel])

  // drag the splitter to resize the tree pane (persisted to localStorage)
  useEffect(() => { localStorage.setItem('beleg.treeWidth', String(treeWidth)) }, [treeWidth])
  const startResize = useCallback((e) => {
    e.preventDefault()
    const startX = e.clientX, startW = treeWidth
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    const onMove = (ev) => setTreeWidth(Math.max(220, Math.min(800, startW + ev.clientX - startX)))
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [treeWidth])

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

  // group the selection into a new folder, resolving folder/child overlaps first
  const groupSelection = (name) => {
    if (!name || !groupable || !state?.tree) return
    const ids = resolveSel(groupable.ids)
    if (!ids || !ids.length) return
    const parents = ids.map((id) => findParent(state.tree, id)?.id)
    const parentId = new Set(parents).size === 1 && parents[0] != null ? parents[0] : state.tree.id
    dispatch({ type: 'GroupIntoFolder', node_ids: ids, parent_id: parentId, name, new_id: null, index: null })
  }

  const openFile = () => {
    if (dirty && !window.confirm(t('Eine andere Datei öffnen und die ungespeicherten Änderungen verwerfen?'))) return
    run(core.openFile(session)).then((resp) => {
      apply(resp)
      if (resp?.ok) {
        setSelected(null); setSelectedIds([]); setPages(null); setPreviewReq(null); setDirty(false)
        if (allTags(resp.tree).length > 0) setTagsOn(true) // a tagged file auto-enables tagging
      }
    })
  }

  const onSaved = (resp) => { if (resp?.ok) { setDirty(false); setNotice(t('Gespeichert')) } }
  const doSave = (mode, store) =>
    run(mode === 'as' ? core.saveFileAs(session, store) : core.saveFile(session, store)).then(onSaved)
  // Preflight: only ask about alternatives when there are some to embed; else save straight.
  const preflightSave = (mode) => run(core.saveInfo(session)).then((info) => {
    if (info?.ok && info.has_alternatives) setSaveAsk({ mode, count: info.count })
    else doSave(mode, true)
  })
  const saveFile = () => preflightSave('in')
  const saveFileAs = () => preflightSave('as')

  // export to a TOC PDF. nodeIds = null → the WHOLE document (toolbar button);
  // the context menu passes specific ids for an explicit selection export.
  const exportPdf = (nodeIds = null) => {
    let ids = nodeIds
    if (Array.isArray(nodeIds)) {  // a selection → resolve folder/child overlaps first
      ids = resolveSel(nodeIds)
      if (!ids || !ids.length) return undefined
    }
    return run(core.exportPdf(session, ids)).then((resp) => {
      if (resp?.ok) {
        setError(null)
        const entries = t(resp.count === 1 ? 'Eintrag' : 'Einträge')
        const base = t('PDF exportiert ({count} {entries})', { count: resp.count, entries })
        setNotice(resp.warning ? `${base} — ${resp.warning}` : base)
      }
      else if (resp?.error && resp.error !== 'cancelled') setError(resp.error)
    })
  }

  // keyboard shortcuts (ignored while typing in a field)
  useEffect(() => {
    if (!session) return undefined
    const onKey = (e) => {
      const tag = e.target?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      const mod = e.ctrlKey || e.metaKey
      const k = e.key.toLowerCase()
      const tree = state?.tree

      // Insert = grab / drop (carry-move). The carry is optical (grab.tree) until
      // dropped; dropping commits a single Move only if the position changed.
      if (e.key === 'Insert') {
        e.preventDefault()
        if (grab) {
          const from = locate(tree, grab.id)
          const to = locate(grab.tree, grab.id)
          if (to && (!from || from.parentId !== to.parentId || from.index !== to.index)) {
            dispatch({ type: 'Move', node_id: grab.id, new_parent_id: to.parentId, index: to.index })
          }
          setGrab(null)
        } else if (selected && tree) {
          setGrab({ id: selected.id, tree })
        }
        return
      }
      // While carrying: arrows move optically; Esc cancels (reverts); swallow the rest.
      if (grab) {
        if (e.key === 'Escape') { e.preventDefault(); setGrab(null); return }
        const dir = { ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right' }[e.key]
        if (dir) {
          e.preventDefault()
          const t = moveTarget(grab.tree, grab.id, dir)
          if (t) setGrab({ id: grab.id, tree: applyMove(grab.tree, grab.id, t.new_parent_id, t.index) })
        }
        return
      }
      // Navigation (not carrying)
      if ((e.key === 'ArrowUp' || e.key === 'ArrowDown') && tree) {
        e.preventDefault()
        const order = visibleOrder(tree)
        const nextId = selected ? navStep(order, selected.id, e.key === 'ArrowUp' ? 'up' : 'down') : order[0]?.id
        const nn = nextId && findNode(tree, nextId)
        if (nn) select(nn)
        return
      }
      if (e.key === 'ArrowRight' && selected?.is_folder && tree) {
        e.preventDefault()
        const n = findNode(tree, selected.id)
        if (n?.collapsed) setCollapsedFor(selected.id, false)
        else { const first = n?.children?.[0]; if (first) select(first) }
        return
      }
      if (e.key === 'ArrowLeft' && tree) {
        e.preventDefault()
        const n = selected && findNode(tree, selected.id)
        if (n?.is_folder && !n.collapsed) { setCollapsedFor(selected.id, true); return }
        const p = selected && findParent(tree, selected.id)
        if (p && p.id !== tree.id) select(p)
        return
      }
      if (mod && k === 's') { e.preventDefault(); saveFile() }
      else if (mod && k === 'o') { e.preventDefault(); openFile() }
      else if (mod && k === 'e') { e.preventDefault(); exportPdf() }
      else if (mod && k === 'n') { e.preventDefault(); core.newWindow() }
      else if (mod && k === 'z' && e.shiftKey) { e.preventDefault(); if (state?.can_redo) redo() }
      else if (mod && k === 'y') { e.preventDefault(); if (state?.can_redo) redo() }
      else if (mod && k === 'z') { e.preventDefault(); if (state?.can_undo) undo() }
      else if (k === 'delete' && (selectedIds.length || selected)) { e.preventDefault(); deleteSelection() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }) // re-binds each render to close over current handlers/state

  if (!state && !error) {
    return (
      <div className="app loading">
        <div className="spinner big" />
        <p className="status">{t('Verbinde mit Core…')}</p>
      </div>
    )
  }

  return (
    <div className={`app${busy ? ' busy' : ''}${tagsOn ? '' : ' tags-off'}`}>
      <header>
        <h1 title={config?.app_name || 'DigitalerUnterlagenOrdner'}>{state?.tree?.name || config?.app_name || 'DigitalerUnterlagenOrdner'}{dirty ? ' •' : ''}</h1>
        <div className="toolbar">
          <button onClick={openFile}>📂 {t('Öffnen')}</button>
          <button onClick={() => core.newWindow()} title={t('Weiteres Dokument in neuem Fenster')}>🗗 {t('Neues Fenster')}</button>
          <button onClick={() => handleImport(core.importDialog(session, importTarget()))}>📥 {t('Importieren')}</button>
          <button onClick={saveFile}>💾 {t('Speichern')}{dirty ? ' •' : ''}</button>
          <button onClick={saveFileAs} title={t('Speichern unter…')}>💾…</button>
          <button onClick={() => exportPdf(selectedIds.length ? selectedIds : null)} title={t('Als PDF mit Inhaltsverzeichnis exportieren (Auswahl, sonst das ganze Dokument)')}>⬇ {t('Export PDF')}{selectedIds.length ? ` (${t('Auswahl')} ${selectedIds.length})` : ''}</button>
          <span className="sep" />
          <button
            onClick={() =>
              dispatch({ type: 'AddFolder', parent_id: state.tree.id, name: t('Neuer Ordner'), index: null, new_id: null })
            }
          >
            ＋ {t('Ordner')}
          </button>
          <button onClick={undo} disabled={!state?.can_undo} title={t('Rückgängig')}>↶</button>
          <button onClick={redo} disabled={!state?.can_redo} title={t('Wiederholen')}>↷</button>
          <span className="sep" />
          <button className={tagsOn ? 'tag-toggle on' : 'tag-toggle'} aria-pressed={tagsOn}
            onClick={toggleTags} title={t('Tags ein-/ausschalten')}>🏷️ {t('Tags')}</button>
          <span className="sep" />
          <select className="lang-select" value={lang} title={t('Sprache')} aria-label={t('Sprache')}
            onChange={(e) => setLang(e.target.value)}>
            {Object.entries(LANGUAGE_NAMES).map(([code, name]) => (
              <option key={code} value={code}>🌐 {name}</option>
            ))}
          </select>
          {busy ? <span className="spinner" title={t('Arbeite…')} /> : null}
        </div>
      </header>


      {error && <p className="error">⚠ {error}</p>}
      {notice && !error && <p className="notice">✓ {notice}</p>}

      <div className="body">
        <div className="pane tree-pane" style={{ flex: `0 0 ${treeWidth}px` }}>
          {state && (
            <Tree
              node={grab ? grab.tree : state.tree}
              selectedIds={selectedIds}
              primaryId={selected?.id}
              grabbedId={grab?.id}
              forceExpand={!!grab}
              onToggleCollapse={toggleCollapse}
              onSelect={select}
              onContext={(x, y, node) => setMenu({ x, y, node })}
              onMove={onMove}
              onMoveMany={onMoveMany}
              levelsFor={levelsFor}
              onRename={(id, name) => {
                const n = findNode(state.tree, id)
                if (n && name && name.trim() && name.trim() !== n.name) dispatch({ type: 'Rename', node_id: id, name: name.trim() })
              }}
              onDropFiles={onDropFiles}
              pending={pending}
            />
          )}
        </div>
        <div className="splitter" onMouseDown={startResize} title={t('Breite der Baumansicht ziehen')} />
        <div className="pane preview-pane" ref={previewRef}>
          {tagsOn && selected && <TagEditor node={selected} docTags={allTags(state?.tree)} dispatch={dispatch} />}
          {selected && <PreviewControls key={selected.id} node={selected} session={session} dispatch={dispatch} onPreview={onPreview} defaultDpi={config?.default_dpi ?? 150} />}
          {selected && (windowed || pages?.length > 0) && (
            <div className="zoom-bar">
              {(() => {
                const total = pageInfo?.total ?? selected.pdf_length
                if (!total) return null
                return <span className="page-info">{pageInfo ? t('Seite {page} / {total}', { page: pageInfo.page, total }) : t('{total} Seiten', { total })}</span>
              })()}
              <button onClick={() => setZoom((z) => Math.max(0.25, z - 0.25))} title={t('kleiner')}>−</button>
              <span>{Math.round(zoom * 100)}%</span>
              <button onClick={() => setZoom((z) => Math.min(4, z + 0.25))} title={t('größer')}>＋</button>
              <button onClick={() => setZoom(1)} title={t('zurücksetzen')}>100%</button>
            </div>
          )}
          {!selected && <p className="status">{t('Knoten auswählen für die Vorschau')}</p>}
          {windowed && <Preview session={session} node={selected} zoom={zoom} previewReq={previewReq} onPage={onPageInfo} />}
          {!windowed && selected && busy > 0 && pages === null && <div className="spinner big" />}
          {!windowed && selected && busy === 0 && pages?.length === 0 && (
            <p className="status">{t('Keine Vorschau (Ordner oder leer)')}</p>
          )}
          {!windowed && selected && pages?.map((src, i) => (
            <img key={i} src={src} alt={t('Seite {n}', { n: i + 1 })} className="preview-page" style={{ width: `${zoom * 100}%` }} />
          ))}
        </div>
      </div>

      <ContextMenu menu={menu} dispatch={dispatch} onClose={() => setMenu(null)} mergeIds={mergeable} group={groupable} onExport={exportPdf} onDelete={deleteSelection} onGroup={groupSelection} selectedIds={selectedIds}
        onSetCollapsed={setCollapsedFor} onExpandAll={expandAll} onCollapseAll={collapseAll} statuses={config?.statuses ?? []} />

      {saveAsk && (
        <SaveDialog count={saveAsk.count}
          onCancel={() => setSaveAsk(null)}
          onChoose={(store) => { const m = saveAsk.mode; setSaveAsk(null); doSave(m, store) }} />
      )}

      {dropActive && (
        <div className="drop-overlay">
          <div className="drop-overlay-badge">
            📥 {t('Dateien ablegen — auf eine Position im Baum (rein/zwischen) für ein genaues Ziel, sonst in {target}', { target: selected?.is_folder ? selected.name : t('oberste Ebene') })}
          </div>
        </div>
      )}

      <StatusBar docPages={docPages} />
    </div>
  )
}
