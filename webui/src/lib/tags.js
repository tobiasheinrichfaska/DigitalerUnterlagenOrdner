// Pure, UI-free tag helpers (mirrors the model's per-node `tags`). More land here
// in 3c/3d (effectiveTags / filterTree / groupByTag); 3b just needs the catalog.

/** Every distinct tag used anywhere in the tree, sorted (for autocomplete). */
export function allTags(root) {
  const set = new Set()
  const walk = (n) => {
    if (!n) return
    for (const t of n.tags || []) set.add(t)
    for (const c of n.children || []) walk(c)
  }
  walk(root)
  return [...set].sort((a, b) => a.localeCompare(b))
}

/** Effective tags of `nodeId` = its own ∪ all ancestor folders' tags (DOWNWARD
 *  inheritance), de-duplicated. Returns { own: [...], inherited: [...] } so the UI
 *  can render own tags solid and inherited ones faded. */
export function effectiveTagsOf(root, nodeId) {
  let own = []
  let inherited = []
  const walk = (n, ancTags, isRoot) => {
    if (n.id === nodeId) {
      own = n.tags || []
      inherited = [...new Set(ancTags)].filter((t) => !own.includes(t))
      return true
    }
    const childAnc = isRoot ? ancTags : [...ancTags, ...(n.tags || [])]
    for (const c of n.children || []) if (walk(c, childAnc, false)) return true
    return false
  }
  walk(root, [], true)
  return { own, inherited }
}

/** View-only filter by TAG only (never by node name): keep a node whose EFFECTIVE
 *  tags (own ∪ ancestor-folder tags) match the query — that node's whole subtree is
 *  kept, since every descendant inherits the tag downward — plus the ancestors of any
 *  match as containers. So a tagged folder shows everything inside, while an untagged
 *  folder containing one tagged item shows only that path (not its other children).
 *  Returns a new (pruned) root; empty query → the original root unchanged. */
export function filterTree(root, query) {
  const q = (query || '').trim().toLowerCase()
  if (!q || !root) return root
  const hit = (s) => (s || '').toLowerCase().includes(q)
  const walk = (node, ancestorTags) => {
    const eff = [...ancestorTags, ...(node.tags || [])]
    if (eff.some(hit)) return node // tag match → whole subtree inherits the tag
    const kept = (node.children || []).map((c) => walk(c, eff)).filter(Boolean)
    return kept.length ? { ...node, children: kept } : null
  }
  const kids = (root.children || []).map((c) => walk(c, root.tags || [])).filter(Boolean)
  return { ...root, children: kids }
}

const GROUP_PREFIX = '__tag__' // synthetic group-folder id marker (not a real node)
/** True for the synthetic folders groupByTag produces (so the UI can skip ops on them). */
export const isGroupNode = (id) => typeof id === 'string' && id.startsWith(GROUP_PREFIX)

/** Normalise a selection captured over a group-by-tag view to REAL, UNIQUE node ids:
 *  a shift-range there sweeps across synthetic group-folder rows AND can include the
 *  same real leaf once per tag it appears under. Without this, selection counts
 *  ("Auswahl N" / "Status (N)") overcount while the ops silently act on fewer nodes. */
export const realSelectionIds = (ids) => [...new Set((ids || []).filter((id) => !isGroupNode(id)))]

/** Every REAL node id currently displayed by a view (skips synthetic group folders;
 *  de-duplicated, since grouping can show a node more than once). Feeds the backend
 *  "open this view in a new window" materialiser. */
export function displayedNodeIds(view) {
  const ids = new Set()
  const walk = (n) => {
    if (!n) return
    if (!isGroupNode(n.id)) ids.add(n.id)
    for (const c of n.children || []) walk(c)
  }
  for (const c of view?.children || []) walk(c) // skip the root container itself
  return [...ids]
}

/** View-only reshape: one synthetic folder per OWN tag (sorted). Inside each tag's
 *  folder is a pruned copy of the document showing the **paths** to every node that
 *  carries that tag — a tagged FOLDER is kept whole (all children come with it), a
 *  tagged leaf keeps its **ancestor folders** as context. Nodes may appear more than
 *  once (a node with several tags shows under each; an item tagged differently from
 *  its tagged parent shows both inside the parent and under its own tag). A final
 *  "untagged" group holds the paths that carry no tag at all (omitted if none).
 *  All real nodes keep their real ids (selection/preview work); only the group-folder
 *  headers carry synthetic ids (isGroupNode) and are never persisted — pure view. */
export function groupByTag(root, { untaggedLabel = 'Ohne Tags' } = {}) {
  if (!root) return root
  const ownTags = new Set()
  const collect = (n) => { for (const tg of n.tags || []) ownTags.add(tg); (n.children || []).forEach(collect) }
  ;(root.children || []).forEach(collect)

  // paths to nodes whose OWN tags include `tag`; a tagged node keeps its whole subtree
  const subtreeFor = (tag) => {
    const walk = (n) => {
      if ((n.tags || []).includes(tag)) return n // tagged → keep node + whole subtree
      const kept = (n.children || []).map(walk).filter(Boolean)
      return kept.length ? { ...n, children: kept } : null // else keep only as a container
    }
    return (root.children || []).map(walk).filter(Boolean)
  }
  // paths entirely free of tags (the leftover documents)
  const untaggedWalk = (n) => {
    if ((n.tags || []).length) return null // a tagged node belongs to a tag group, not here
    if (!n.is_folder) return n
    const kept = (n.children || []).map(untaggedWalk).filter(Boolean)
    return kept.length ? { ...n, children: kept } : null
  }

  const children = [...ownTags].sort((a, b) => a.localeCompare(b)).map((tag) => ({
    id: `${GROUP_PREFIX}${tag}`, name: tag, is_folder: true, tags: [], collapsed: false, children: subtreeFor(tag),
  }))
  const untagged = (root.children || []).map(untaggedWalk).filter(Boolean)
  if (untagged.length) {
    children.push({ id: GROUP_PREFIX, name: untaggedLabel, is_folder: true, tags: [], collapsed: false, children: untagged })
  }
  return { ...root, children }
}

/** Multi-select tagging (#7). Given the selected node objects, return the UNION of
 *  their OWN tags as [{ tag, onAll }] in first-seen order: `onAll` true when EVERY
 *  selected node carries the tag. Drives the editor's chip display — a tag on all is
 *  removable-from-all; a "partial" tag (onAll=false) can be added to complete it. */
export function tagSelectionState(nodes) {
  const list = (nodes || []).filter(Boolean)
  const order = []
  const counts = new Map()
  for (const n of list) {
    for (const tg of n.tags || []) {
      if (!counts.has(tg)) { counts.set(tg, 0); order.push(tg) }
      counts.set(tg, counts.get(tg) + 1)
    }
  }
  const total = list.length
  return order.map((tag) => ({ tag, onAll: total > 0 && counts.get(tag) === total }))
}

/** Tags already on EVERY selected node — excluded from the add suggestions (adding
 *  one would be a no-op). A partial tag stays suggestible so it can be completed. */
export function tagsOnAll(nodes) {
  return tagSelectionState(nodes).filter((s) => s.onAll).map((s) => s.tag)
}
