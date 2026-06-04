import { describe, it, expect } from 'vitest'
import { findNode, findParent, flattenIds, depthOf, isAncestorOf, afterLevels } from './tree'

// root → [a, f → [b, g → [c]]]
const root = {
  id: 'root', is_folder: true, children: [
    { id: 'a' },
    { id: 'f', is_folder: true, children: [
      { id: 'b' },
      { id: 'g', is_folder: true, name: 'g', children: [{ id: 'c' }] },
    ] },
  ],
}

describe('lib/tree', () => {
  it('findNode', () => {
    expect(findNode(root, 'c').id).toBe('c')
    expect(findNode(root, 'nope')).toBeNull()
  })
  it('findParent', () => {
    expect(findParent(root, 'c').id).toBe('g')
    expect(findParent(root, 'a').id).toBe('root')
    expect(findParent(root, 'root')).toBeNull()
  })
  it('flattenIds (pre-order, excludes root)', () => {
    expect(flattenIds(root)).toEqual(['a', 'f', 'b', 'g', 'c'])
  })
  it('depthOf (root children = 0)', () => {
    expect(depthOf(root, 'a')).toBe(0)
    expect(depthOf(root, 'b')).toBe(1)
    expect(depthOf(root, 'c')).toBe(2)
  })
  it('isAncestorOf', () => {
    expect(isAncestorOf(root, 'f', 'c')).toBe(true)
    expect(isAncestorOf(root, 'a', 'c')).toBe(false)
  })
  it('afterLevels pops out from a last child', () => {
    // c is the last child of g (last child of f) → can drop after c at c/g/f levels
    const lvls = afterLevels(root, 'c').map((l) => l.parentId)
    expect(lvls).toEqual(['g', 'f', 'root'])
    // a is not a last child within a deep chain → just its own level
    expect(afterLevels(root, 'a').map((l) => l.parentId)).toEqual(['root'])
  })
})
