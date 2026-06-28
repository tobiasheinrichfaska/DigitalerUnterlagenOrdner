// Shared accessible-menu helpers (#10): roving focus, role tagging, dismiss.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup, renderHook } from '@testing-library/react'
import { useRef } from 'react'
import { rovingFocusKeydown, tagMenuItems, useMenuDismiss } from './useMenu'

afterEach(cleanup)

const makeMenu = () => {
  const div = document.createElement('div')
  div.innerHTML = '<button>a</button><button>b</button><button>c</button>'
  document.body.appendChild(div)
  return { div, btns: [...div.querySelectorAll('button')] }
}

const key = (k) => ({ key: k, preventDefault: vi.fn() })

describe('rovingFocusKeydown', () => {
  it('ArrowDown moves to the next button and wraps at the end', () => {
    const { div, btns } = makeMenu()
    btns[0].focus()
    rovingFocusKeydown(div, key('ArrowDown'))
    expect(document.activeElement).toBe(btns[1])
    btns[2].focus()
    rovingFocusKeydown(div, key('ArrowDown'))
    expect(document.activeElement).toBe(btns[0])  // wrap
    div.remove()
  })

  it('ArrowUp wraps to the last from the first; Home/End jump to the ends', () => {
    const { div, btns } = makeMenu()
    btns[0].focus()
    rovingFocusKeydown(div, key('ArrowUp'))
    expect(document.activeElement).toBe(btns[2])  // wrap
    rovingFocusKeydown(div, key('Home'))
    expect(document.activeElement).toBe(btns[0])
    rovingFocusKeydown(div, key('End'))
    expect(document.activeElement).toBe(btns[2])
    div.remove()
  })

  it('is a no-op on an empty/null container', () => {
    expect(() => rovingFocusKeydown(null, key('ArrowDown'))).not.toThrow()
  })
})

describe('tagMenuItems', () => {
  it('marks every button as role=menuitem', () => {
    const { div, btns } = makeMenu()
    tagMenuItems(div)
    expect(btns.every((b) => b.getAttribute('role') === 'menuitem')).toBe(true)
    div.remove()
  })
})

function Harness({ open, onClose }) {
  const ref = useRef(null)
  useMenuDismiss(ref, open, onClose)
  return (
    <div>
      <span data-testid="outside">outside</span>
      {open && <div ref={ref} data-testid="menu"><button>x</button></div>}
    </div>
  )
}

describe('useMenuDismiss', () => {
  it('Escape calls onClose while open', () => {
    const onClose = vi.fn()
    render(<Harness open onClose={onClose} />)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('an outside mousedown calls onClose; inside does not', () => {
    const onClose = vi.fn()
    render(<Harness open onClose={onClose} />)
    fireEvent.mouseDown(screen.getByText('x'))      // inside the menu
    expect(onClose).not.toHaveBeenCalled()
    fireEvent.mouseDown(screen.getByTestId('outside'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('does nothing when closed (no listeners attached)', () => {
    const onClose = vi.fn()
    renderHook(() => useMenuDismiss({ current: null }, false, onClose))
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).not.toHaveBeenCalled()
  })
})
