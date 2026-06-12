import { useEffect } from 'react'
import { findNode, findParent } from '../lib/tree'
import { visibleOrder, navStep, moveTarget, applyMove, locate } from '../lib/treeNav'

// Global keyboard: arrow navigation, Insert carry-move (optical grab → drop, one
// undoable Move), and Ctrl shortcuts (save/open/export/new-window/undo/redo/delete).
// Ignored while typing in INPUT/TEXTAREA/SELECT. Re-binds each render to close over
// current state/handlers.
export function useKeyboard({
  enabled, reorderEnabled = true, tree, selected, selectedIds, grab, setGrab, select, dispatch,
  setCollapsedFor, saveFile, openFile, exportPdf, newWindow, undo, redo,
  deleteSelection, canUndo, canRedo,
  // modal/menu flags: shortcuts must be OFF while any overlay is open
  saveAskOpen = false, exportAskOpen = false, helpOpen = false, menuOpen = false,
}) {
  useEffect(() => {
    // Disable all shortcuts while any modal dialog or context menu is open so that
    // e.g. pressing Delete or Ctrl+S inside a dialog does not trigger tree actions.
    if (!enabled || saveAskOpen || exportAskOpen || helpOpen || menuOpen) return undefined
    const onKey = (e) => {
      const tag = e.target?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      const mod = e.ctrlKey || e.metaKey
      const k = e.key.toLowerCase()

      // Insert = grab / drop (carry-move). The carry is optical (grab.tree) until
      // dropped; dropping commits a single Move only if the position changed.
      // Disabled while a filtered view is active (positions are virtual there).
      if (e.key === 'Insert') {
        e.preventDefault()
        if (!reorderEnabled) return
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
      // Ctrl+E: mirrors the toolbar button — export the selection when present,
      // otherwise export the whole document (null). Keeps keyboard and mouse consistent.
      else if (mod && k === 'e') { e.preventDefault(); exportPdf(selectedIds.length ? selectedIds : null) }
      else if (mod && k === 'n') { e.preventDefault(); newWindow() }
      else if (mod && k === 'z' && e.shiftKey) { e.preventDefault(); if (canRedo) redo() }
      else if (mod && k === 'y') { e.preventDefault(); if (canRedo) redo() }
      else if (mod && k === 'z') { e.preventDefault(); if (canUndo) undo() }
      else if (k === 'delete' && reorderEnabled && (selectedIds.length || selected)) { e.preventDefault(); deleteSelection() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })
}
