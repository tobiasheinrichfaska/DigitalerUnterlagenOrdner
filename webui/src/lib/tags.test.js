import { describe, it, expect } from 'vitest'
import { allTags, effectiveTagsOf, filterTree, groupByTag, isGroupNode, displayedNodeIds, realSelectionIds } from './tags'

// root → [a(Steuer,2023), f[Steuer] → [b(Spende), c()]]
const tree = {
  id: 'r', is_folder: true, name: 'root', children: [
    { id: 'a', name: 'Telekom', tags: ['Steuer', '2023'] },
    { id: 'f', name: '2024', is_folder: true, tags: ['Steuer'], children: [
      { id: 'b', name: 'Spendenquittung', tags: ['Spende'] },
      { id: 'c', name: 'Sonstiges', tags: [] },
    ] },
  ],
}
const ids = (t) => (t?.children || []).map((c) => `${c.id}:${(c.children || []).map((g) => g.id).join(',')}`)

describe('allTags', () => {
  it('collects distinct tags across the whole tree, sorted', () => {
    expect(allTags(tree)).toEqual(['2023', 'Spende', 'Steuer'])
  })
  it('handles empty / missing', () => {
    expect(allTags(null)).toEqual([])
    expect(allTags({ id: 'x' })).toEqual([])
  })
})

describe('effectiveTagsOf', () => {
  it('inherits ancestor-folder tags (downward), faded separately from own', () => {
    expect(effectiveTagsOf(tree, 'b')).toEqual({ own: ['Spende'], inherited: ['Steuer'] })
    expect(effectiveTagsOf(tree, 'c')).toEqual({ own: [], inherited: ['Steuer'] })
    expect(effectiveTagsOf(tree, 'a')).toEqual({ own: ['Steuer', '2023'], inherited: [] })
  })
})

describe('filterTree', () => {
  it('empty query returns the tree unchanged', () => {
    expect(filterTree(tree, '')).toBe(tree)
  })
  it('a tagged folder shows its whole subtree (downward inheritance)', () => {
    // f is tagged Steuer; a has own Steuer → both top-level kept, f keeps both kids
    expect(ids(filterTree(tree, 'Steuer'))).toEqual(['a:', 'f:b,c'])
  })
  it('an untagged folder containing one match shows only that path, not siblings', () => {
    // only b has Spende → f kept as container with ONLY b (not c)
    expect(ids(filterTree(tree, 'Spende'))).toEqual(['f:b'])
  })
  it('does NOT match by node name — only tags', () => {
    // "Telekom" is a node NAME (its tags are Steuer/2023); searching it finds nothing
    expect(filterTree(tree, 'telekom').children).toEqual([])
  })
})

describe('groupByTag', () => {
  // serialize a node list as id(child,child)… so structure (kept folders) is visible
  const ser = (nodes) => (nodes || []).map((n) => {
    const kids = n.children && n.children.length ? `(${ser(n.children)})` : ''
    return `${n.id}${kids}`
  }).join(',')
  const grouped = groupByTag(tree)
  const groups = (grouped.children || []).map((g) => `${g.name}:${ser(g.children)}`)

  it('makes one folder per OWN tag (sorted) and keeps folders + ancestor paths', () => {
    // a owns Steuer,2023 ; f owns Steuer (kept whole → b,c inside) ; b owns Spende
    // (kept under its ancestor f, c pruned). No fully-untagged path → no extra group.
    expect(groups).toEqual(['2023:a', 'Spende:f(b)', 'Steuer:a,f(b,c)'])
  })
  it('a node can appear under more than one tag (b under Spende and inside Steuer)', () => {
    const spende = grouped.children.find((g) => g.name === 'Spende')
    const steuer = grouped.children.find((g) => g.name === 'Steuer')
    expect(ser(spende.children)).toContain('b')                 // b surfaced under its own tag
    expect(ser(steuer.children.find((n) => n.id === 'f').children)).toContain('b') // and inside tagged f
  })
  it('group folders carry synthetic ids; real nodes keep real ids', () => {
    expect(grouped.children.every((g) => isGroupNode(g.id))).toBe(true)
    expect(isGroupNode('a')).toBe(false)
  })
  it('collects fully-untagged paths into a final group, keeping folders', () => {
    const t3 = { id: 'r', is_folder: true, name: 'root', children: [
      { id: 'x', name: 'x', tags: ['A'] },
      { id: 'D', name: 'D', is_folder: true, tags: [], children: [
        { id: 'y', name: 'y', tags: [] }, // untagged leaf under an untagged folder
      ] },
    ] }
    const g = groupByTag(t3).children.map((c) => `${c.name}:${ser(c.children)}`)
    expect(g).toEqual(['A:x', 'Ohne Tags:D(y)'])
  })
})

describe('displayedNodeIds', () => {
  it('collects real ids from a filtered view (skips hidden siblings)', () => {
    expect(displayedNodeIds(filterTree(tree, 'Spende')).sort()).toEqual(['b', 'f'])
  })
  it('de-duplicates across a grouped view and skips synthetic group headers', () => {
    // grouping shows a/f/b/c (b and f appear twice) → distinct real ids only
    expect(displayedNodeIds(groupByTag(tree)).sort()).toEqual(['a', 'b', 'c', 'f'])
  })
})

describe('realSelectionIds', () => {
  it('drops synthetic group ids and de-duplicates real ones', () => {
    // a shift-range over a grouped view: group headers + a repeated real leaf
    expect(realSelectionIds(['__tag__Steuer', 'a', 'b', '__tag__Spende', 'b']))
      .toEqual(['a', 'b'])
  })
  it('is a no-op on a clean real-id selection', () => {
    expect(realSelectionIds(['a', 'b', 'c'])).toEqual(['a', 'b', 'c'])
  })
  it('handles null / empty', () => {
    expect(realSelectionIds(null)).toEqual([])
    expect(realSelectionIds([])).toEqual([])
  })
})
