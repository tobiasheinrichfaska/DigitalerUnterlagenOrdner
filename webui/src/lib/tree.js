// Pure, UI-free tree helpers shared by App / Tree (no React, no DOM). The tree is
// the plain Document JSON: { id, name, is_folder, children:[…], … }.

export function findNode(node, id) {
  if (!node) return null
  if (node.id === id) return node
  for (const c of node.children ?? []) {
    const r = findNode(c, id)
    if (r) return r
  }
  return null
}

export function findParent(node, id, parent = null) {
  if (node.id === id) return parent
  for (const c of node.children ?? []) {
    const r = findParent(c, id, node)
    if (r) return r
  }
  return null
}

/** Depth of a node (root's children = 0). */
export function depthOf(root, id, d = -1) {
  if (root.id === id) return d
  for (const c of root.children ?? []) {
    const r = depthOf(c, id, d + 1)
    if (r !== null) return r
  }
  return null
}

/** Is `ancestorId` an ancestor of `descId` in the tree? */
export function isAncestorOf(root, ancestorId, descId) {
  let p = findParent(root, descId)
  while (p) {
    if (p.id === ancestorId) return true
    p = findParent(root, p.id)
  }
  return false
}

/** Where a new folder should be inserted relative to the current selection
 *  (planned item #8): INSIDE a selected folder, as a SIBLING right after a selected
 *  leaf, else at the ROOT (no/invalid selection). Returns { parentId, index } for an
 *  AddFolder command (index null = append). Pure. */
export function newFolderTarget(root, selectedId) {
  if (!root) return { parentId: null, index: null }
  const sel = selectedId ? findNode(root, selectedId) : null
  if (!sel) return { parentId: root.id, index: null }
  if (sel.is_folder) return { parentId: sel.id, index: null }
  const parent = findParent(root, sel.id) || root
  const idx = (parent.children ?? []).findIndex((c) => c.id === sel.id)
  return { parentId: parent.id, index: idx >= 0 ? idx + 1 : null }
}

/** Drop levels for the gap AFTER `id`: deepest first (insert right after the row,
 *  at its own level), then — only while the row is the *last child* of its parent —
 *  each shallower ancestor level, up to the root. Each entry = { parentId, index,
 *  depth, parentName }. */
export function afterLevels(root, id) {
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
