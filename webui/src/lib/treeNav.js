// Pure tree helpers for keyboard navigation + optical carry-move. No React.
// The "tree" is the document root Node ({ id, name, is_folder, children }).
//
// `applyMove` mirrors the Python `move_node` (core/model.py): remove the node,
// then insert it under the new parent at `index` (post-removal frame). So the
// optical preview produced here matches exactly what dispatching a single
// `Move` command will commit.

function find(node, id) {
  if (node.id === id) return node
  for (const c of node.children ?? []) {
    const r = find(c, id)
    if (r) return r
  }
  return null
}

function findParentOf(node, id, parent = null) {
  if (node.id === id) return parent
  for (const c of node.children ?? []) {
    const r = findParentOf(c, id, node)
    if (r) return r
  }
  return null
}

// Pre-order list of visible rows (excludes the implicit root). Children of a
// collapsed folder (node.collapsed, a persisted model field) are skipped. Each
// entry: {id, parentId, index, depth, isFolder}.
export function visibleOrder(root) {
  const out = []
  const walk = (n, parentId, depth) => {
    ;(n.children ?? []).forEach((c, i) => {
      out.push({ id: c.id, parentId, index: i, depth, isFolder: !!c.is_folder })
      if (c.is_folder && !c.collapsed) walk(c, c.id, depth + 1)
    })
  }
  walk(root, root.id, 0)
  return out
}

// Shift-range selection: all VISIBLE ids between anchor and target (inclusive,
// either direction). Collapsed folders' descendants are hidden rows and must NOT
// be swept into the range (they'd silently inflate "{n} Elemente" / DeleteMany).
// Returns null when either end isn't currently visible (caller falls back).
export function rangeIds(root, anchorId, targetId) {
  const order = visibleOrder(root).map((e) => e.id)
  const a = order.indexOf(anchorId)
  const b = order.indexOf(targetId)
  if (a === -1 || b === -1) return null
  const [lo, hi] = a <= b ? [a, b] : [b, a]
  return order.slice(lo, hi + 1)
}

// Previous/next visible id for ↑/↓. Returns null at the ends.
export function navStep(order, currentId, dir) {
  const i = order.findIndex((e) => e.id === currentId)
  if (i === -1) return order.length ? order[0].id : null
  const j = dir === 'up' ? i - 1 : i + 1
  return j >= 0 && j < order.length ? order[j].id : null
}

// One carry step for the grabbed node → {new_parent_id, index} | null.
//  up/down: reorder within siblings (null at the ends — use left to leave)
//  right  : nest into the previous sibling IF it's a folder (append last)
//  left   : out one level, just after the parent (null if parent is root)
export function moveTarget(root, nodeId, dir) {
  const parent = findParentOf(root, nodeId)
  if (!parent) return null
  const siblings = parent.children ?? []
  const index = siblings.findIndex((c) => c.id === nodeId)
  if (index === -1) return null

  if (dir === 'up') return index > 0 ? { new_parent_id: parent.id, index: index - 1 } : null
  if (dir === 'down') return index < siblings.length - 1 ? { new_parent_id: parent.id, index: index + 1 } : null
  if (dir === 'right') {
    const prev = siblings[index - 1]
    return prev && prev.is_folder ? { new_parent_id: prev.id, index: null } : null
  }
  if (dir === 'left') {
    const grand = findParentOf(root, parent.id)
    if (!grand) return null // parent is the root
    const pIndex = (grand.children ?? []).findIndex((c) => c.id === parent.id)
    return { new_parent_id: grand.id, index: pIndex + 1 }
  }
  return null
}

function removeNode(node, id) {
  const kids = (node.children ?? []).filter((c) => c.id !== id).map((c) => removeNode(c, id))
  return { ...node, children: kids }
}

function insertChild(node, parentId, child, index) {
  if (node.id === parentId) {
    const kids = [...(node.children ?? [])]
    const at = index == null ? kids.length : Math.max(0, Math.min(index, kids.length))
    kids.splice(at, 0, child)
    return { ...node, children: kids }
  }
  return { ...node, children: (node.children ?? []).map((c) => insertChild(c, parentId, child, index)) }
}

// Pure: relocate nodeId under newParentId at index (remove then insert). Returns
// a new tree (structural copy). Matches Python move_node semantics.
export function applyMove(root, nodeId, newParentId, index) {
  const node = find(root, nodeId)
  if (!node) return root
  return insertChild(removeNode(root, nodeId), newParentId, node, index)
}

// Where a node currently sits → {parentId, index} | null. Used on drop to read
// the node's final position out of the preview tree for the single Move dispatch.
export function locate(root, nodeId) {
  const parent = findParentOf(root, nodeId)
  if (!parent) return null
  return { parentId: parent.id, index: (parent.children ?? []).findIndex((c) => c.id === nodeId) }
}

// Multi-node carry-move drop. During the carry only the PRIMARY is moved optically
// (the others stay visibly locked); on drop the whole block follows the primary.
// We express the landing slot the way MoveMany expects it — in the PRE-REMOVAL
// frame: the original index of the first NON-carried node after the primary in the
// preview (the core discounts the moved-out siblings before that slot). No such
// node → null = append to the destination folder.
//
// Returns { parentId, index } for a MoveMany dispatch, or null if the primary did
// not actually move (a no-op drop should not push an undo entry).
export function moveManyDrop(originalTree, previewTree, ids, primaryId) {
  const to = locate(previewTree, primaryId)
  if (!to) return null
  const from = locate(originalTree, primaryId)
  if (from && from.parentId === to.parentId && from.index === to.index) return null // unmoved
  const carried = new Set(ids)
  const previewParent = find(previewTree, to.parentId)
  let successor = null
  for (let i = to.index + 1; i < (previewParent?.children ?? []).length; i++) {
    if (!carried.has(previewParent.children[i].id)) { successor = previewParent.children[i]; break }
  }
  const origParent = find(originalTree, to.parentId)
  const index = successor && origParent
    ? origParent.children.findIndex((c) => c.id === successor.id)
    : null
  return { parentId: to.parentId, index }
}

