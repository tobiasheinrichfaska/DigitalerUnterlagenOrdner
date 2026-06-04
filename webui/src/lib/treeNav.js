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

// All folder ids in the tree (for "collapse all").
export function allFolderIds(root) {
  const out = []
  const walk = (n) => {
    for (const c of n.children ?? []) {
      if (c.is_folder) out.push(c.id)
      walk(c)
    }
  }
  walk(root)
  return out
}
