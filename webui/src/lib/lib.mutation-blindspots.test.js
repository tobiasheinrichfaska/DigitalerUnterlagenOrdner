// Mutation-testing blind spots in webui/src/lib (see audit x3, MU-21..MU-27). No vi.mock.
import { describe, it, expect } from 'vitest'
import { aggregateStatus, statusDots, sweepCandidates, SWEEP_MAX_PAGES } from './status'
import { effectiveTagsOf } from './tags'
import { isAncestor, resolveSelection } from './selection'
import { afterLevels } from './tree'
import { navStep } from './treeNav'
import { localizeMessage } from './messages'
import { translate } from '../i18n/index'

const L = (id, status = '', extra = {}) =>
  ({ id, is_folder: false, status, compression_undecided: false, children: [], ...extra })
const F = (id, children) => ({ id, is_folder: true, status: '', children })

describe('aggregateStatus — folders without any status (MU-21, status.js:50/54)', () => {
  it('a folder whose leaves all have no status shows NO dots (no black marker)', () => {
    const tree = F('root', [F('f', [L('a'), L('b')])])
    const map = aggregateStatus(tree)
    expect(map.get('f').dots).toEqual([])
    expect(map.get('root').dots).toEqual([])
    expect(map.get('a').dots).toEqual([])
    expect(statusDots(tree.children[0])).toEqual([])  // the per-row helper agrees
  })

  it('an empty folder next to an unstatused leaf stays dot-free; next to a statused leaf it does not turn black', () => {
    const t1 = F('root', [F('e', []), L('a')])
    expect(aggregateStatus(t1).get('root').dots).toEqual([])
    const t2 = F('root', [F('e', []), L('a', 'erfasst')])
    expect(aggregateStatus(t2).get('root').dots).toEqual(['green'])   // no black: empty folders count as neither
  })

  it('mixed statused + unstatused leaves still add the black dot, statused-only does not', () => {
    const mixed = F('root', [F('f', [L('a', 'erfasst'), L('b')])])
    expect(aggregateStatus(mixed).get('f').dots).toEqual(['green', 'black'])
    const only = F('root', [F('f', [L('a', 'erfasst'), L('b', 'zu erfassen')])])
    expect(aggregateStatus(only).get('f').dots).toEqual(['yellow', 'green'])
  })
})

describe('sweepCandidates default page cap (MU-22, status.js:80/86)', () => {
  const cand = (id, pages) => ({
    id, is_folder: false, status: '', has_source: true, is_compressed: false,
    no_compression: false, compression_undecided: true, pdf_length: pages,
  })
  it('SWEEP_MAX_PAGES is 5: a 5-page leaf is swept, a 6-page leaf is not', () => {
    expect(SWEEP_MAX_PAGES).toBe(5)
    const tree = { id: 'r', is_folder: true, children: [cand('p5', 5), cand('p6', 6), cand('p0', 0)] }
    expect(sweepCandidates(tree)).toEqual(['p5'])
  })
})

describe('effectiveTagsOf — the document root does not donate tags (MU-23, tags.js:32)', () => {
  it('tags on the root are not inherited by its descendants, folder tags are', () => {
    const tree = {
      id: 'r', is_folder: true, tags: ['RootTag'], children: [
        { id: 'f', is_folder: true, tags: ['F'], children: [{ id: 'x', tags: ['own'] }] },
        { id: 'y', tags: [] },
      ],
    }
    expect(effectiveTagsOf(tree, 'y')).toEqual({ own: [], inherited: [] })
    expect(effectiveTagsOf(tree, 'x')).toEqual({ own: ['own'], inherited: ['F'] })
  })
})

describe('selection — unknown ancestor / top-most clean-up (MU-24, selection.js:40/92)', () => {
  const tree = {
    id: 'root', is_folder: true, children: [
      { id: 'f', is_folder: true, children: [
        { id: 'c1', is_folder: false }, { id: 'c2', is_folder: false },
      ] },
      { id: 'a', is_folder: false },
    ],
  }
  it('isAncestor is false for an id that does not exist, and for a non-ancestor', () => {
    expect(isAncestor(tree, 'nope', 'c1')).toBe(false)
    expect(isAncestor(tree, 'a', 'c1')).toBe(false)
    expect(isAncestor(tree, 'f', 'f')).toBe(false)
  })
  it('a still-selected folder swallows its selected descendants in the final result', () => {
    // partial selection answered with something that neither drops the items nor the folder:
    // the safety net must still never return both a folder and a node inside it
    const out = resolveSelection(tree, ['f', 'c1'], () => 'keep')
    expect(out).toEqual(['f'])
    // control: unrelated ids are untouched
    expect(resolveSelection(tree, ['c1', 'a'], () => 'keep').sort()).toEqual(['a', 'c1'])
  })
})

describe('afterLevels — full level records (MU-25, tree.js:82/84/86)', () => {
  // root → [a, f → [b, g(name) → [c]]]
  const root = {
    id: 'root', is_folder: true, children: [
      { id: 'a' },
      { id: 'f', is_folder: true, name: 'F', children: [
        { id: 'b' },
        { id: 'g', is_folder: true, name: 'G', children: [{ id: 'c' }] },
      ] },
    ],
  }
  it('every level carries parentId, post-row index, depth and the parent name (null at root)', () => {
    expect(afterLevels(root, 'c')).toEqual([
      { parentId: 'g', index: 1, depth: 2, parentName: 'G' },
      { parentId: 'f', index: 2, depth: 1, parentName: 'F' },
      { parentId: 'root', index: 2, depth: 0, parentName: null },
    ])
    expect(afterLevels(root, 'a')).toEqual([{ parentId: 'root', index: 1, depth: 0, parentName: null }])
  })
  it('a row that is NOT the last child of a nested folder offers only its own level', () => {
    expect(afterLevels(root, 'b')).toEqual([{ parentId: 'f', index: 1, depth: 1, parentName: 'F' }])
  })
  it('an unknown id yields no levels', () => {
    expect(afterLevels(root, 'ghost')).toEqual([])
  })
})

describe('localizeMessage — tails with "; " stay verbatim for whole templates (MU-26, messages.js:27/28/67)', () => {
  const t = (key, vars) => translate('en-US', key, vars)
  it('"ungültige Daten: …" keeps an exception text that contains "; " and looks like a message', () => {
    const tail = 'bad; a.pdf: Datei ist passwortgeschützt'
    expect(localizeMessage(t, `ungültige Daten: ${tail}`)).toBe(`invalid data: ${tail}`)
  })
  it('"Ohne Seiten übersprungen: …" keeps a name list containing "; "', () => {
    const names = 'x; a.pdf: Datei ist passwortgeschützt'
    expect(localizeMessage(t, `Ohne Seiten übersprungen: ${names}`))
      .toBe(t('Ohne Seiten übersprungen: {names}', { names }))
    expect(localizeMessage(t, `Ohne Seiten übersprungen: ${names}`)).not.toContain('password-protected')
  })
  it('non-string / empty input is returned untouched and never throws', () => {
    expect(localizeMessage(t, 42)).toBe(42)
    expect(localizeMessage(t, null)).toBe(null)
    expect(localizeMessage(t, undefined)).toBe(undefined)
    expect(localizeMessage(t, '')).toBe('')
    expect(localizeMessage(t, { a: 1 })).toEqual({ a: 1 })
  })
})

describe('navStep — focus lost (MU-27, treeNav.js:58)', () => {
  const order = [{ id: 'A' }, { id: 'B' }, { id: 'C' }]
  it('an unknown / stale current id lands on the FIRST visible row; an empty tree yields null', () => {
    expect(navStep(order, 'ghost', 'down')).toBe('A')
    expect(navStep(order, 'ghost', 'up')).toBe('A')
    expect(navStep(order, null, 'down')).toBe('A')
    expect(navStep([], 'ghost', 'down')).toBe(null)
  })
  it('steps up and down by exactly one row', () => {
    expect(navStep(order, 'B', 'down')).toBe('C')
    expect(navStep(order, 'B', 'up')).toBe('A')
  })
})
