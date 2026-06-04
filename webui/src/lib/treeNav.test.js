import { describe, it, expect } from 'vitest'
import { visibleOrder, navStep, moveTarget, applyMove, locate, allFolderIds } from './treeNav'

// root
//  ├ A (folder)
//  │  ├ A1
//  │  └ A2
//  ├ B (folder)
//  │  └ B1
//  └ C
const tree = {
  id: 'root', is_folder: true, children: [
    { id: 'A', is_folder: true, children: [
      { id: 'A1', is_folder: false, children: [] },
      { id: 'A2', is_folder: false, children: [] },
    ] },
    { id: 'B', is_folder: true, children: [
      { id: 'B1', is_folder: false, children: [] },
    ] },
    { id: 'C', is_folder: false, children: [] },
  ],
}

const ids = (t, parentId = 'root') => {
  const p = find(t, parentId)
  return (p.children ?? []).map((c) => c.id)
}
function find(n, id) {
  if (n.id === id) return n
  for (const c of n.children ?? []) { const r = find(c, id); if (r) return r }
  return null
}

describe('visibleOrder', () => {
  it('pre-order, excludes root', () => {
    expect(visibleOrder(tree).map((e) => e.id)).toEqual(['A', 'A1', 'A2', 'B', 'B1', 'C'])
  })
  it('skips children of collapsed folders (node.collapsed)', () => {
    const t = { ...tree, children: tree.children.map((c) => (c.id === 'A' ? { ...c, collapsed: true } : c)) }
    expect(visibleOrder(t).map((e) => e.id)).toEqual(['A', 'B', 'B1', 'C'])
  })
  it('reports depth and folder flag', () => {
    const a1 = visibleOrder(tree).find((e) => e.id === 'A1')
    expect(a1).toMatchObject({ parentId: 'A', index: 0, depth: 1, isFolder: false })
  })
})

describe('navStep', () => {
  const order = visibleOrder(tree)
  it('moves down/up', () => {
    expect(navStep(order, 'A', 'down')).toBe('A1')
    expect(navStep(order, 'A1', 'up')).toBe('A')
  })
  it('stops at the ends', () => {
    expect(navStep(order, 'A', 'up')).toBe(null)
    expect(navStep(order, 'C', 'down')).toBe(null)
  })
})

describe('moveTarget', () => {
  it('up/down reorder within siblings, null at ends', () => {
    expect(moveTarget(tree, 'A2', 'up')).toEqual({ new_parent_id: 'A', index: 0 })
    expect(moveTarget(tree, 'A1', 'up')).toBe(null)
    expect(moveTarget(tree, 'A1', 'down')).toEqual({ new_parent_id: 'A', index: 1 })
    expect(moveTarget(tree, 'A2', 'down')).toBe(null)
  })
  it('right nests into the previous sibling folder', () => {
    expect(moveTarget(tree, 'B', 'right')).toEqual({ new_parent_id: 'A', index: null })
    expect(moveTarget(tree, 'C', 'right')).toEqual({ new_parent_id: 'B', index: null })
  })
  it('right is null when the previous sibling is not a folder', () => {
    expect(moveTarget(tree, 'A2', 'right')).toBe(null) // prev = A1 (leaf)
  })
  it('left moves out one level, just after the parent', () => {
    expect(moveTarget(tree, 'A1', 'left')).toEqual({ new_parent_id: 'root', index: 1 })
    expect(moveTarget(tree, 'A', 'left')).toBe(null) // parent is root
  })
})

describe('applyMove (matches move_node remove-then-insert)', () => {
  it('reorders within a parent', () => {
    const t = applyMove(tree, 'A2', 'A', 0)
    expect(ids(t, 'A')).toEqual(['A2', 'A1'])
  })
  it('nests into another folder', () => {
    const t = applyMove(tree, 'C', 'B', null)
    expect(ids(t)).toEqual(['A', 'B'])
    expect(ids(t, 'B')).toEqual(['B1', 'C'])
  })
  it('moves out a level', () => {
    const t = applyMove(tree, 'A1', 'root', 1)
    expect(ids(t)).toEqual(['A', 'A1', 'B', 'C'])
    expect(ids(t, 'A')).toEqual(['A2'])
  })
  it('locate reads the resulting position', () => {
    const t = applyMove(tree, 'C', 'B', null)
    expect(locate(t, 'C')).toEqual({ parentId: 'B', index: 1 })
  })
})

describe('allFolderIds', () => {
  it('lists every folder', () => {
    expect(allFolderIds(tree).sort()).toEqual(['A', 'B'])
  })
})
