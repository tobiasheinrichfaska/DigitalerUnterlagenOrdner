import { describe, it, expect } from 'vitest'
import { allTags } from './tags'

const tree = {
  id: 'r', is_folder: true, tags: ['Belege'], children: [
    { id: 'a', tags: ['Steuer', '2023'] },
    { id: 'f', is_folder: true, tags: ['Steuer'], children: [
      { id: 'b', tags: ['Spende'] },
      { id: 'c', tags: [] },
    ] },
  ],
}

describe('allTags', () => {
  it('collects distinct tags across the whole tree, sorted', () => {
    expect(allTags(tree)).toEqual(['2023', 'Belege', 'Spende', 'Steuer'])
  })
  it('handles empty / missing', () => {
    expect(allTags(null)).toEqual([])
    expect(allTags({ id: 'x' })).toEqual([])
  })
})
