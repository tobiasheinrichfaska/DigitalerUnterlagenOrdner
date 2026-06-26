import { describe, it, expect } from 'vitest'
import { pageFraction, scrollForAnchor } from './zoomAnchor'

describe('lib/zoomAnchor — pageFraction (v3.10.0 #9)', () => {
  it('is 0 at the page top, 0.5 at the middle, ~1 at the bottom', () => {
    expect(pageFraction(100, 100, 800)).toBe(0)
    expect(pageFraction(500, 100, 800)).toBe(0.5)
    expect(pageFraction(899, 100, 800)).toBeCloseTo(0.99875, 5)
  })
  it('clamps above the page top (scroll past the bottom) to 1', () => {
    expect(pageFraction(2000, 100, 800)).toBe(1)
  })
  it('clamps below the page top (scroll above it) to 0', () => {
    expect(pageFraction(50, 100, 800)).toBe(0)
  })
  it('is 0 for a degenerate (zero / negative) height box', () => {
    expect(pageFraction(500, 100, 0)).toBe(0)
    expect(pageFraction(500, 100, -10)).toBe(0)
  })
})

describe('lib/zoomAnchor — scrollForAnchor (v3.10.0 #9)', () => {
  it('inverts pageFraction: top → pageTop, middle → +half height', () => {
    expect(scrollForAnchor(100, 800, 0)).toBe(100)
    expect(scrollForAnchor(100, 800, 0.5)).toBe(500)
    expect(scrollForAnchor(100, 800, 1)).toBe(900)
  })
  it('round-trips a fraction through both functions under a NEW (scaled) layout', () => {
    // page at zoom 1: top=300, height=800 → scrolled to 60% down the page
    const frac = pageFraction(780, 300, 800) // = 0.6
    expect(frac).toBeCloseTo(0.6, 6)
    // same page at zoom 1.5: top=450, height=1200 → keep the 60% document position
    expect(scrollForAnchor(450, 1200, frac)).toBe(450 + Math.round(0.6 * 1200)) // 1170
  })
  it('clamps the fraction and guards negative geometry, rounds to an int pixel', () => {
    expect(scrollForAnchor(100, 800, 2)).toBe(900) // fraction clamped to 1
    expect(scrollForAnchor(100, 800, -1)).toBe(100) // fraction clamped to 0
    expect(scrollForAnchor(-50, -800, 0.5)).toBe(0) // negative geometry → 0
    expect(scrollForAnchor(100, 333, 0.5)).toBe(Math.round(100 + 0.5 * 333)) // 267
  })
})
