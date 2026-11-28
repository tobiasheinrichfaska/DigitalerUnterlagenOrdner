import { describe, it, expect } from 'vitest'
import { resolveSelection, mergeableIds } from './selection'
import { groupByTag, GROUP_PREFIX } from './tags'
import { buildIndex, findNode, findParent } from './tree'

// ---- OLD (naive) reference implementations, copied verbatim from before PF-5/PF-7 ----
function find(node, id) {
  if (!node) return null
  if (node.id === id) return node
  for (const c of node.children || []) { const r = find(c, id); if (r) return r }
  return null
}
function descendantIds(node) {
  const out = []
  for (const c of node.children || []) { out.push(c.id); out.push(...descendantIds(c)) }
  return out
}
function isAncestorOld(root, a, d) { const n = find(root, a); return n ? descendantIds(n).includes(d) : false }
function resolveOld(root, ids, ask, { warnNone = false } = {}) {
  const set = new Set(ids)
  const orig = new Set(ids)
  const folders = ids.filter((id) => { const n = find(root, id); return n && n.is_folder })
  for (const fid of folders) {
    if (!set.has(fid)) continue
    const node = find(root, fid)
    const desc = descendantIds(node)
    if (desc.length === 0) continue
    const sel = desc.filter((d) => orig.has(d))
    if (sel.length === 0) {
      if (warnNone && ask('none', node.name) !== 'proceed') return null
    } else if (sel.length === desc.length) {
      sel.forEach((d) => set.delete(d))
    } else {
      const choice = ask('partial', node.name)
      if (choice === 'abort') return null
      if (choice === 'all') sel.forEach((d) => set.delete(d))
      else if (choice === 'exclude') set.delete(fid)
    }
  }
  const out = [...set]
  return out.filter((id) => !out.some((o) => o !== id && isAncestorOld(root, o, id)))
}
function findParentNode(node, id, parent = null) {
  if (node.id === id) return parent
  for (const c of node.children || []) { const r = findParentNode(c, id, node); if (r) return r }
  return null
}
function mergeableOld(root, selectedIds) {
  if (!root || (selectedIds?.length ?? 0) < 2) return null
  const nodes = selectedIds.map((id) => find(root, id))
  if (nodes.some((n) => !n || n.is_folder)) return null
  const parents = selectedIds.map((id) => findParentNode(root, id))
  if (parents.some((p) => p == null) || new Set(parents.map((p) => p.id)).size !== 1) return null
  const order = parents[0].children.map((c) => c.id)
  return [...selectedIds].sort((a, b) => order.indexOf(a) - order.indexOf(b))
}
function groupOld(root, { untaggedLabel = 'Ohne Tags' } = {}) {
  if (!root) return root
  const ownTags = new Set()
  const collect = (n) => { for (const tg of n.tags || []) ownTags.add(tg); (n.children || []).forEach(collect) }
  ;(root.children || []).forEach(collect)
  const subtreeFor = (tag) => {
    const walk = (n) => {
      if ((n.tags || []).includes(tag)) return n
      const kept = (n.children || []).map(walk).filter(Boolean)
      return kept.length ? { ...n, children: kept } : null
    }
    return (root.children || []).map(walk).filter(Boolean)
  }
  const untaggedWalk = (n) => {
    if ((n.tags || []).length) return null
    if (!n.is_folder) return n
    const kept = (n.children || []).map(untaggedWalk).filter(Boolean)
    return kept.length ? { ...n, children: kept } : null
  }
  const children = [...ownTags].sort((a, b) => a.localeCompare(b)).map((tag) => ({
    id: `${GROUP_PREFIX}${tag}`, name: tag, is_folder: true, tags: [], collapsed: false, children: subtreeFor(tag),
  }))
  const untagged = (root.children || []).map(untaggedWalk).filter(Boolean)
  if (untagged.length) children.push({ id: GROUP_PREFIX, name: untaggedLabel, is_folder: true, tags: [], collapsed: false, children: untagged })
  return { ...root, children }
}

// ---- seeded random trees ----
function rng(seed) { let s = seed >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296 } }
function randTree(seed, n, nTags = 6) {
  const r = rng(seed); let c = 0
  const folders = []
  const mk = (isF) => {
    const tags = []
    const k = r() < 0.35 ? 1 + Math.floor(r() * 2) : 0
    for (let i = 0; i < k; i++) tags.push('t' + Math.floor(r() * nTags))
    return { id: (isF ? 'F' : 'L') + c++, name: 'n' + c, is_folder: isF, tags, children: [] }
  }
  const root = { id: 'root', name: 'root', is_folder: true, tags: [], children: [] }
  folders.push(root)
  while (c < n) {
    const p = folders[Math.floor(r() * folders.length)]
    const isF = r() < 0.2
    const nd = mk(isF); p.children.push(nd); if (isF) folders.push(nd)
  }
  return root
}
const allIds = (n, out = []) => { out.push(n.id); (n.children || []).forEach((c) => allIds(c, out)); return out }
function randSel(seed, root, k) {
  const r = rng(seed); const ids = allIds(root); const sel = []
  for (let i = 0; i < k; i++) sel.push(ids[Math.floor(r() * ids.length)]) // duplicates + root + nested possible
  if (r() < 0.3) sel.push('does-not-exist')
  return sel
}
const asks = [
  () => 'all', () => 'exclude', () => 'abort',
]

describe('PF-5/6/7 equivalence with the old implementation', () => {
  it('resolveSelection matches on random trees/selections (all ask answers, warnNone)', () => {
    for (let seed = 1; seed <= 60; seed++) {
      const root = randTree(seed, 20 + (seed * 7) % 80)
      const ids = randSel(seed * 31, root, 1 + (seed % 15))
      for (const a of asks) for (const warnNone of [false, true]) for (const none of ['proceed', 'abort']) {
        const calls1 = [], calls2 = []
        const mk = (calls) => (kind, name) => { calls.push([kind, name]); return kind === 'none' ? none : a() }
        const o = resolveOld(root, ids, mk(calls1), { warnNone })
        const nw = resolveSelection(root, ids, mk(calls2), { warnNone })
        expect(nw).toEqual(o)
        expect(calls2).toEqual(calls1)
      }
    }
  })
  it('mergeableIds matches', () => {
    for (let seed = 1; seed <= 80; seed++) {
      const root = randTree(seed, 30)
      const ids = randSel(seed, root, 2 + (seed % 4))
      expect(mergeableIds(root, ids)).toEqual(mergeableOld(root, ids))
      const sib = root.children.filter((c) => !c.is_folder).map((c) => c.id).reverse()
      expect(mergeableIds(root, sib)).toEqual(mergeableOld(root, sib))
      const ix = buildIndex(root)
      expect(mergeableIds(root, sib, ix)).toEqual(mergeableOld(root, sib))
    }
  })
  it('groupByTag matches (incl. nested same tags, multi-tag nodes)', () => {
    for (let seed = 1; seed <= 80; seed++) {
      const root = randTree(seed, 10 + (seed * 13) % 150, 1 + (seed % 9))
      expect(groupByTag(root)).toEqual(groupOld(root))
      expect(groupByTag(root, { untaggedLabel: 'X' })).toEqual(groupOld(root, { untaggedLabel: 'X' }))
    }
    expect(groupByTag(null)).toBeNull()
  })
  it('buildIndex agrees with findNode/findParent', () => {
    const root = randTree(7, 100); const ix = buildIndex(root)
    for (const id of allIds(root)) {
      expect(ix.get(id).node).toBe(findNode(root, id))
      expect(ix.get(id).parent ?? null).toBe(findParent(root, id))
    }
    expect(ix.has('nope')).toBe(false)
  })
})

function bigTree(n, tagFor) {
  const root = { id: 'root', name: 'r', is_folder: true, tags: [], children: [] }
  let c = 0
  for (let t = 0; t < 10; t++) {
    const top = { id: 'T' + t, name: 'T', is_folder: true, tags: [], children: [] }
    for (let m = 0; m < 5; m++) {
      const mid = { id: `M${t}.${m}`, name: 'M', is_folder: true, tags: [], children: [] }
      for (let f = 0; f < n / 50 / 20; f++) {
        const fo = { id: `F${t}.${m}.${f}`, name: 'F', is_folder: true, tags: [], children: [] }
        for (let i = 0; i < 20; i++, c++) fo.children.push({ id: 'L' + c, name: 'L', is_folder: false, tags: tagFor(c), children: [] })
        mid.children.push(fo)
      }
      top.children.push(mid)
    }
    root.children.push(top)
  }
  return root
}
describe('PF-5/7 performance targets (5000 nodes)', () => {
  it('resolveSelection k=1000 < 100 ms', () => {
    const root = bigTree(5000, () => [])
    const leaves = allIds(root).filter((i) => i.startsWith('L')).slice(0, 1000)
    const t = performance.now()
    const out = resolveSelection(root, leaves, () => 'all')
    const dt = performance.now() - t
    console.log('resolveSelection k=1000 n=5000 ms', dt.toFixed(1))
    expect(out.length).toBe(1000)
    expect(dt).toBeLessThan(100)
  })
  it('groupByTag 500 tags < 100 ms', () => {
    const root = bigTree(5000, (c) => (c % 10 === 0 ? ['u' + (c / 10)] : []))
    const t = performance.now()
    const g = groupByTag(root)
    const dt = performance.now() - t
    console.log('groupByTag 500 tags n=5000 ms', dt.toFixed(1))
    expect(g.children.length).toBe(501)
    expect(dt).toBeLessThan(100)
  })
})
