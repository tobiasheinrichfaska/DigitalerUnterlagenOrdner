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
