import { describe, it, expect } from 'vitest'
import { findNode, findParent, depthOf, isAncestorOf, afterLevels, newFolderTarget } from './tree'

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

describe('newFolderTarget (v3.10.0 #8)', () => {
  it('targets the ROOT with no/invalid selection', () => {
    expect(newFolderTarget(root, null)).toEqual({ parentId: 'root', index: null })
    expect(newFolderTarget(root, 'ghost')).toEqual({ parentId: 'root', index: null })
  })
  it('targets INSIDE a selected folder', () => {
    expect(newFolderTarget(root, 'f')).toEqual({ parentId: 'f', index: null })
    expect(newFolderTarget(root, 'g')).toEqual({ parentId: 'g', index: null })
  })
  it('targets a SIBLING right after a selected leaf', () => {
    expect(newFolderTarget(root, 'a')).toEqual({ parentId: 'root', index: 1 })
    expect(newFolderTarget(root, 'b')).toEqual({ parentId: 'f', index: 1 })
    expect(newFolderTarget(root, 'c')).toEqual({ parentId: 'g', index: 1 })
  })
  it('is null-safe without a tree', () => {
    expect(newFolderTarget(null, 'a')).toEqual({ parentId: null, index: null })
  })
})
