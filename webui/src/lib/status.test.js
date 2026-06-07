import { describe, it, expect } from 'vitest'
import { statusColor, statusDots, hasUndecided } from './status'

const leaf = (status = '', extra = {}) => ({ is_folder: false, status, ...extra })
const folder = (children) => ({ is_folder: true, status: '', children })

describe('statusColor', () => {
  it('maps the three statuses, nothing else', () => {
    expect(statusColor('vorjahreswert')).toBe('red')
    expect(statusColor('zu erfassen')).toBe('yellow')
    expect(statusColor('erfasst')).toBe('green')
    expect(statusColor('')).toBe(null)
    expect(statusColor('bogus')).toBe(null)
  })
})

describe('statusDots — leaf', () => {
  it('one dot for a status, none for no status', () => {
    expect(statusDots(leaf('erfasst'))).toEqual(['green'])
    expect(statusDots(leaf(''))).toEqual([])
  })
})

describe('statusDots — folder aggregation', () => {
  it('distinct statuses in red->yellow->green order', () => {
    const f = folder([leaf('erfasst'), leaf('vorjahreswert'), leaf('erfasst')])
    expect(statusDots(f)).toEqual(['red', 'green']) // no yellow, all have status -> no black
  })

  it('adds black when some have status and some do not', () => {
    const f = folder([leaf('erfasst'), leaf('')])
    expect(statusDots(f)).toEqual(['green', 'black'])
  })

  it('all-no-status -> no dots (no black)', () => {
    expect(statusDots(folder([leaf(''), leaf('')]))).toEqual([])
  })

  it('empty folder -> no dots', () => {
    expect(statusDots(folder([]))).toEqual([])
  })

  it('aggregates deeply (grandchildren)', () => {
    const f = folder([folder([leaf('vorjahreswert'), leaf('')]), leaf('zu erfassen')])
    expect(statusDots(f)).toEqual(['red', 'yellow', 'black'])
  })
})

describe('hasUndecided', () => {
  it('leaf reflects its own flag', () => {
    expect(hasUndecided(leaf('', { compression_undecided: true }))).toBe(true)
    expect(hasUndecided(leaf('', { compression_undecided: false }))).toBe(false)
  })

  it('folder is true if any descendant leaf is undecided', () => {
    const f = folder([leaf('', { compression_undecided: false }),
      folder([leaf('', { compression_undecided: true })])])
    expect(hasUndecided(f)).toBe(true)
  })

  it('folder is false when no descendant is undecided', () => {
    expect(hasUndecided(folder([leaf('erfasst'), leaf('erfasst')]))).toBe(false)
  })
})
