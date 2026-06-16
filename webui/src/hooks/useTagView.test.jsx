// Tests for useTagView: the derived viewActive / filterActive flags and toggleTags.
import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useTagView } from './useTagView'

describe('useTagView — defaults', () => {
  it('starts off: tagging disabled, no view active', () => {
    const { result } = renderHook(() => useTagView())
    expect(result.current.tagsOn).toBe(false)
    expect(result.current.viewActive).toBe(false)
    expect(result.current.filterActive).toBe(false)
  })
})

describe('useTagView — derived flags require tagsOn', () => {
  it('a search or group-by has NO effect while tagging is off', () => {
    const { result } = renderHook(() => useTagView())
    act(() => { result.current.setTagSearch('beleg'); result.current.setGroupBy(true) })
    expect(result.current.viewActive).toBe(false)
    expect(result.current.filterActive).toBe(false)
  })

  it('an active search → both viewActive and filterActive', () => {
    const { result } = renderHook(() => useTagView())
    act(() => { result.current.toggleTags(); result.current.setTagSearch('beleg') })
    expect(result.current.viewActive).toBe(true)
    expect(result.current.filterActive).toBe(true)
  })

  it('group-by alone → viewActive but NOT filterActive (no real subset)', () => {
    const { result } = renderHook(() => useTagView())
    act(() => { result.current.toggleTags(); result.current.setGroupBy(true) })
    expect(result.current.viewActive).toBe(true)
    expect(result.current.filterActive).toBe(false)
  })

  it('a whitespace-only search is treated as empty', () => {
    const { result } = renderHook(() => useTagView())
    act(() => { result.current.toggleTags(); result.current.setTagSearch('   ') })
    expect(result.current.viewActive).toBe(false)
    expect(result.current.filterActive).toBe(false)
  })
})
