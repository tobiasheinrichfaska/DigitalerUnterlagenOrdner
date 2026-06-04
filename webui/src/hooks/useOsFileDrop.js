import { useEffect } from 'react'

// Wires window-level OS file-drop: toggles `setDropActive` while an OS file drag
// hovers the window, and calls `onDropFiles(files)` on a window drop. Precise
// tree-position drops are handled by the Tree's own zones (which stopPropagation,
// so they never reach this window-level fallback). Re-binds each render so it
// closes over the current callbacks.
export function useOsFileDrop(onDropFiles, setDropActive, enabled = true) {
  useEffect(() => {
    if (!enabled) return undefined
    const hasFiles = (e) => Array.from(e.dataTransfer?.types || []).includes('Files')
    const onOver = (e) => { if (hasFiles(e)) { e.preventDefault(); setDropActive(true) } }
    const onLeave = (e) => { if (!e.relatedTarget) setDropActive(false) }
    const onDrop = (e) => {
      if (!hasFiles(e)) return
      e.preventDefault()
      onDropFiles(e.dataTransfer.files)
    }
    window.addEventListener('dragover', onOver)
    window.addEventListener('dragleave', onLeave)
    window.addEventListener('drop', onDrop)
    return () => {
      window.removeEventListener('dragover', onOver)
      window.removeEventListener('dragleave', onLeave)
      window.removeEventListener('drop', onDrop)
    }
  })
}
