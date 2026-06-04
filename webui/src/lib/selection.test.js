import { describe, it, expect } from 'vitest'
import { resolveSelection, isAncestor } from './selection'

// root
//   f (folder) → c1, c2
//   a, b (leaves)
const tree = {
  id: 'root', is_folder: true, name: 'root', children: [
    { id: 'f', is_folder: true, name: 'F', children: [
      { id: 'c1', is_folder: false, name: 'c1' },
      { id: 'c2', is_folder: false, name: 'c2' },
    ] },
    { id: 'a', is_folder: false, name: 'a' },
    { id: 'b', is_folder: false, name: 'b' },
  ],
}

const never = () => { throw new Error('ask should not be called') }

describe('resolveSelection', () => {
  it('independent leaves need no resolution', () => {
    expect(resolveSelection(tree, ['a', 'b'], never).sort()).toEqual(['a', 'b'])
  })

  it('folder alone: silent by default, warns only with warnNone', () => {
    expect(resolveSelection(tree, ['f'], never)).toEqual(['f']) // move/group/export: no prompt
    expect(resolveSelection(tree, ['f'], (k) => { expect(k).toBe('none'); return 'proceed' }, { warnNone: true })).toEqual(['f'])
    expect(resolveSelection(tree, ['f'], () => 'abort', { warnNone: true })).toBeNull()
  })

  it('folder with ALL children selected → fine, folder covers them (no ask)', () => {
    expect(resolveSelection(tree, ['f', 'c1', 'c2'], never)).toEqual(['f'])
  })

  it('folder with PARTIAL children → include all keeps the folder', () => {
    expect(resolveSelection(tree, ['f', 'c1'], (k) => { expect(k).toBe('partial'); return 'all' })).toEqual(['f'])
  })

  it('folder with PARTIAL children → exclude keeps only the selected child', () => {
    expect(resolveSelection(tree, ['f', 'c1'], () => 'exclude')).toEqual(['c1'])
  })

  it('partial → abort returns null', () => {
    expect(resolveSelection(tree, ['f', 'c1'], () => 'abort')).toBeNull()
  })

  // nested: root > A(folder) > [ B(folder) > [c1,c2], d ]
  const nested = {
    id: 'root', is_folder: true, name: 'root', children: [
      { id: 'A', is_folder: true, name: 'A', children: [
        { id: 'B', is_folder: true, name: 'B', children: [
          { id: 'c1', is_folder: false, name: 'c1' },
          { id: 'c2', is_folder: false, name: 'c2' },
        ] },
        { id: 'd', is_folder: false, name: 'd' },
      ] },
    ],
  }

  it('nested: deep descendant selected with ancestor folder → exclude keeps the leaf', () => {
    // A selected + c1 (two levels down) → exclude A → only c1 remains
    expect(resolveSelection(nested, ['A', 'c1'], () => 'exclude')).toEqual(['c1'])
    // include all → keep A (covers everything)
    expect(resolveSelection(nested, ['A', 'c1'], () => 'all')).toEqual(['A'])
  })

  it('nested: inner folder fully selected collapses to that folder, outer left alone', () => {
    // B + all of B's children → B covers them; d not selected, A not selected → [B, d]? no:
    // only B and its children are selected → result is just B
    expect(resolveSelection(nested, ['B', 'c1', 'c2'], never)).toEqual(['B'])
  })

  it('nested: two leaves under the same unselected folder need no resolution', () => {
    expect(resolveSelection(nested, ['c1', 'd'], never).sort()).toEqual(['c1', 'd'])
  })

  it('isAncestor works', () => {
    expect(isAncestor(tree, 'f', 'c1')).toBe(true)
    expect(isAncestor(tree, 'c1', 'f')).toBe(false)
    expect(isAncestor(tree, 'a', 'b')).toBe(false)
  })
})
