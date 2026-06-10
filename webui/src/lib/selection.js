// Reusable selection resolver for context operations on a multi-selection.
//
// The data layer rejects a "mixed" selection (a folder AND an item inside it both
// selected). The UI must resolve such overlaps to a CLEAN top-most set first. For
// each selected folder we look at how many of its descendants are also selected:
//   - none     → warn: its (unselected) contents would be processed too      → proceed | abort
//   - all      → fine: keep the folder, drop the now-redundant descendants
//   - partial  → ask: include ALL its items / EXCLUDE the folder / abort
//
// `ask(kind, folderName)` returns:
//   kind 'none'    → 'proceed' | 'abort'
//   kind 'partial' → 'all' | 'exclude' | 'abort'
//
// Returns the resolved (clean, top-most) id array, or null if the user aborted.
// Pure — no React/DOM — so it is unit-testable and usable from any operation.

function find(node, id) {
  if (!node) return null
  if (node.id === id) return node
  for (const c of node.children || []) {
    const r = find(c, id)
    if (r) return r
  }
  return null
}

function descendantIds(node) {
  const out = []
  for (const c of node.children || []) {
    out.push(c.id)
    out.push(...descendantIds(c))
  }
  return out
}

export function isAncestor(root, ancestorId, descId) {
  const a = find(root, ancestorId)
  return a ? descendantIds(a).includes(descId) : false
}

/** 2+ selected sibling LEAVES → their ids sorted into DOCUMENT order (the order
 *  under the shared parent), ready for a Merge; else null. Document order — not
 *  click order — so the merged PDF's pages follow the visible order and the kept
 *  name/slot is the topmost node, not whichever happened to be clicked first. */
export function mergeableIds(root, selectedIds) {
  if (!root || (selectedIds?.length ?? 0) < 2) return null
  const nodes = selectedIds.map((id) => find(root, id))
  if (nodes.some((n) => !n || n.is_folder)) return null
  const parents = selectedIds.map((id) => findParentNode(root, id))
  if (parents.some((p) => p == null) || new Set(parents.map((p) => p.id)).size !== 1) return null
  const order = parents[0].children.map((c) => c.id)
  return [...selectedIds].sort((a, b) => order.indexOf(a) - order.indexOf(b))
}

function findParentNode(node, id, parent = null) {
  if (node.id === id) return parent
  for (const c of node.children || []) {
    const r = findParentNode(c, id, node)
    if (r) return r
  }
  return null
}

export function resolveSelection(root, ids, ask, { warnNone = false } = {}) {
  const set = new Set(ids)
  const folders = ids.filter((id) => { const n = find(root, id); return n && n.is_folder })
  for (const fid of folders) {
    if (!set.has(fid)) continue
    const node = find(root, fid)
    const desc = descendantIds(node)
    if (desc.length === 0) continue // empty folder — nothing to reconcile
    const sel = desc.filter((d) => set.has(d))
    if (sel.length === 0) {
      // a folder whose contents aren't individually selected. For destructive ops
      // (delete) warn that they'll be affected; for move/group/export just include
      // them silently (a folder naturally carries its contents).
      if (warnNone && ask('none', node.name) !== 'proceed') return null
      // keep the folder (it covers all its contents)
    } else if (sel.length === desc.length) {
      sel.forEach((d) => set.delete(d)) // all selected → the folder already covers them
    } else {
      const choice = ask('partial', node.name)
      if (choice === 'abort') return null
      if (choice === 'all') sel.forEach((d) => set.delete(d)) // keep folder, drop items
      else if (choice === 'exclude') set.delete(fid) // keep the selected items, drop folder
    }
  }
  // clean top-most: drop any id that is a descendant of another id still selected
  const out = [...set]
  return out.filter((id) => !out.some((o) => o !== id && isAncestor(root, o, id)))
}
