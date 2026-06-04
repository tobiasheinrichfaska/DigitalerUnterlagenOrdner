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

  it('isAncestor works', () => {
    expect(isAncestor(tree, 'f', 'c1')).toBe(true)
    expect(isAncestor(tree, 'c1', 'f')).toBe(false)
    expect(isAncestor(tree, 'a', 'b')).toBe(false)
  })
})
