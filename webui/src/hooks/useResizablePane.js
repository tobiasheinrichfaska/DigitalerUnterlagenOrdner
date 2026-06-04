import { useState, useEffect, useCallback } from 'react'

// A draggable pane width persisted to localStorage. Returns the current width and
// a `startResize` mousedown handler for the splitter.
export function useResizablePane({ key = 'beleg.treeWidth', min = 220, max = 800, def = 340 } = {}) {
  const [width, setWidth] = useState(() => {
    const v = parseInt(localStorage.getItem(key), 10)
    return v >= min && v <= max ? v : def // remembered across sessions (UI pref, not the document)
  })

  useEffect(() => { localStorage.setItem(key, String(width)) }, [key, width])

  const startResize = useCallback((e) => {
    e.preventDefault()
    const startX = e.clientX, startW = width
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    const onMove = (ev) => setWidth(Math.max(min, Math.min(max, startW + ev.clientX - startX)))
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [width, min, max])

  return { width, startResize }
}
