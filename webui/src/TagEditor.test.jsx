// Component tests for the per-node tag editor: add (Enter/comma/blur/quick-fav),
// remove (× and Backspace-on-empty), de-duplication, and the localStorage-backed
// favourites set. Every mutation goes out as a single SetTags dispatch that
// replaces the whole tag set. German source strings (no provider).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup, within } from '@testing-library/react'
import { TagEditor } from './TagEditor'

const FAV_KEY = 'beleg.tagFavourites'

beforeEach(() => localStorage.clear())
afterEach(cleanup)

const renderEditor = ({ tags = [], docTags = [] } = {}) => {
  const dispatch = vi.fn()
  const node = { id: 'N1', tags }
  render(<TagEditor node={node} docTags={docTags} dispatch={dispatch} />)
  return { dispatch }
}

const lastTags = (dispatch) => dispatch.mock.calls.at(-1)[0].tags

describe('TagEditor — adding', () => {
  it('Enter adds the typed tag via a SetTags dispatch', () => {
    const { dispatch } = renderEditor({ tags: ['a'] })
    const input = screen.getByPlaceholderText('+ Tag')
    fireEvent.change(input, { target: { value: 'steuer' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(dispatch).toHaveBeenCalledWith({ type: 'SetTags', node_id: 'N1', tags: ['a', 'steuer'] })
  })

  it('comma also commits the tag', () => {
    const { dispatch } = renderEditor()
    const input = screen.getByPlaceholderText('+ Tag')
    fireEvent.change(input, { target: { value: 'beleg' } })
    fireEvent.keyDown(input, { key: ',' })
    expect(lastTags(dispatch)).toEqual(['beleg'])
  })

  it('blur with pending text commits it', () => {
    const { dispatch } = renderEditor()
    const input = screen.getByPlaceholderText('+ Tag')
    fireEvent.change(input, { target: { value: 'rest' } })
    fireEvent.blur(input)
    expect(lastTags(dispatch)).toEqual(['rest'])
  })

  it('does not add a duplicate tag', () => {
    const { dispatch } = renderEditor({ tags: ['x'] })
    const input = screen.getByPlaceholderText('+ Tag')
    fireEvent.change(input, { target: { value: 'x' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(dispatch).not.toHaveBeenCalled()
  })

  it('trims surrounding whitespace before adding', () => {
    const { dispatch } = renderEditor()
    const input = screen.getByPlaceholderText('+ Tag')
    fireEvent.change(input, { target: { value: '  spaced  ' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(lastTags(dispatch)).toEqual(['spaced'])
  })
})

describe('TagEditor — removing', () => {
  it('the × button removes that tag', () => {
    const { dispatch } = renderEditor({ tags: ['a', 'b'] })
    // the remove button title is "Tag entfernen"; first one removes 'a'
    fireEvent.click(screen.getAllByTitle('Tag entfernen')[0])
    expect(lastTags(dispatch)).toEqual(['b'])
  })

  it('Backspace on an empty input removes the last tag', () => {
    const { dispatch } = renderEditor({ tags: ['a', 'b'] })
    const input = screen.getByPlaceholderText('+ Tag')
    fireEvent.keyDown(input, { key: 'Backspace' })
    expect(lastTags(dispatch)).toEqual(['a'])
  })
})

describe('TagEditor — favourites (localStorage)', () => {
  it('quick-fav chips appear for favourites not already on the node and add on click', () => {
    localStorage.setItem(FAV_KEY, JSON.stringify(['wichtig']))
    const { dispatch } = renderEditor({ tags: [] })
    const chip = screen.getByText('+ wichtig')
    fireEvent.click(chip)
    expect(lastTags(dispatch)).toEqual(['wichtig'])
  })

  it('starring a tag persists it to localStorage favourites', () => {
    renderEditor({ tags: ['neu'] })
    fireEvent.click(screen.getByTitle('Zu Favoriten'))
    expect(JSON.parse(localStorage.getItem(FAV_KEY))).toContain('neu')
  })

  it('document tags are offered as autocomplete suggestions', () => {
    const { container } = (() => {
      const dispatch = vi.fn()
      const r = render(<TagEditor node={{ id: 'N1', tags: ['a'] }} docTags={['a', 'b', 'c']} dispatch={dispatch} />)
      return r
    })()
    const opts = [...container.querySelectorAll('#te-suggest option')].map((o) => o.value)
    // 'a' is already on the node, so it is filtered out of the suggestions
    expect(opts).toEqual(['b', 'c'])
  })
})

describe('TagEditor — multi select (#7: TagMany)', () => {
  // A(Steuer, 2024) + B(Steuer) → Steuer on all; 2024 only on A (partial)
  const nodes = [{ id: 'A', tags: ['Steuer', '2024'] }, { id: 'B', tags: ['Steuer'] }]
  const setupMulti = () => {
    const dispatch = vi.fn()
    const utils = render(<TagEditor node={nodes[0]} nodes={nodes} docTags={[]} dispatch={dispatch} />)
    return { ...utils, dispatch }
  }

  it('shows a "N markiert" badge with the selection count', () => {
    setupMulti()
    expect(screen.getByText('2 markiert')).toBeInTheDocument()
  })

  it('renders the tag UNION; a tag not on every node is partial', () => {
    const { container } = setupMulti()
    const partial = container.querySelectorAll('.te-chip-partial')
    expect(partial.length).toBe(1)
    expect(partial[0].textContent).toContain('2024')
    const solid = [...container.querySelectorAll('.te-chip')].filter((c) => !c.classList.contains('te-chip-partial'))
    expect(solid.length).toBe(1)
    expect(solid[0].textContent).toContain('Steuer')
  })

  it('adding a tag dispatches TagMany add over ALL selected ids', () => {
    const { dispatch } = setupMulti()
    const input = screen.getByPlaceholderText('+ Tag')
    fireEvent.change(input, { target: { value: 'Wichtig' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(dispatch).toHaveBeenCalledWith({ type: 'TagMany', node_ids: ['A', 'B'], tag: 'Wichtig', add: true })
  })

  it('removing a full chip dispatches TagMany remove over ALL selected ids', () => {
    const { container, dispatch } = setupMulti()
    const solid = [...container.querySelectorAll('.te-chip')].find((c) => !c.classList.contains('te-chip-partial'))
    fireEvent.click(within(solid).getByTitle('Tag entfernen'))
    expect(dispatch).toHaveBeenCalledWith({ type: 'TagMany', node_ids: ['A', 'B'], tag: 'Steuer', add: false })
  })

  it('Backspace does NOT remove a tag in multi mode (avoids a surprise bulk delete)', () => {
    const { dispatch } = setupMulti()
    const input = screen.getByPlaceholderText('+ Tag')
    fireEvent.keyDown(input, { key: 'Backspace' })
    expect(dispatch).not.toHaveBeenCalled()
  })
})
