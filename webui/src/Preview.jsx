// Virtualized, windowed preview for a selected leaf. Renders a placeholder box
// per page (height fixed by the page aspect-ratio, so it doesn't jump when the
// real image arrives), and only fetches the pages near the viewport via
// core.renderWindow (±BUFFER prefetch). Scroll position is remembered per node.
//
// Used for the plain stored preview; the compression-browsing preview and folders
// still go through App's all-pages path.
import { useCallback, useEffect, useRef, useState } from 'react'
import { core } from './core'

const BUFFER = 5 // pages to prefetch on each side of the visible range
const scrollMemory = new Map() // nodeId -> scrollTop (survives remounts)

export function Preview({ session, node, zoom = 1 }) {
  const nodeId = node?.id
  const [count, setCount] = useState(0)
  const [dims, setDims] = useState([])
  const [pages, setPages] = useState({}) // pageIndex -> data-URL

  const scrollRef = useRef(null)
  const pageEls = useRef([])
  const visible = useRef(new Set())
  const inflight = useRef(new Set()) // ranges already requested ("first-last")
  const token = useRef(0) // bumped on node change to drop stale responses

  // --- metadata on node change ---
  useEffect(() => {
    if (!session || !nodeId) { setCount(0); setDims([]); setPages({}); return }
    const t = ++token.current
    let alive = true
    setPages({}); visible.current = new Set(); inflight.current = new Set(); pageEls.current = []
    Promise.all([core.pageCount(session, nodeId), core.pageDims(session, nodeId)])
      .then(([c, d]) => {
        if (!alive || token.current !== t) return
        setCount(c?.ok ? c.count : 0)
        setDims(d?.ok ? d.dims : [])
      })
      .catch(() => {})
    return () => { alive = false }
  }, [session, nodeId])

  // --- fetch a window of pages covering [lo, hi] (± BUFFER) ---
  const fetchRange = useCallback((lo, hi) => {
    if (!session || !nodeId || count === 0) return
    const first = Math.max(0, lo - BUFFER)
    const last = Math.min(count - 1, hi + BUFFER)
    if (last < first) return
    const key = `${first}-${last}`
    if (inflight.current.has(key)) return
    inflight.current.add(key)
    const t = token.current
    core.renderWindow(session, nodeId, first, last - first + 1)
      .then((r) => {
        inflight.current.delete(key)
        if (!r?.ok || token.current !== t) return
        setPages((prev) => {
          const next = { ...prev }
          r.pages.forEach((url, i) => { if (url) next[first + i] = url })
          return next
        })
      })
      .catch(() => inflight.current.delete(key))
  }, [session, nodeId, count])

  // --- observe which pages are on screen; fetch around them ---
  useEffect(() => {
    const root = scrollRef.current
    if (!root || count === 0) return
    root.scrollTop = scrollMemory.get(nodeId) || 0
    const io = new IntersectionObserver((entries) => {
      let changed = false
      for (const e of entries) {
        const idx = Number(e.target.dataset.page)
        if (e.isIntersecting) {
          if (!visible.current.has(idx)) { visible.current.add(idx); changed = true }
        } else if (visible.current.delete(idx)) {
          changed = true
        }
      }
      if (changed && visible.current.size) {
        const arr = [...visible.current]
        fetchRange(Math.min(...arr), Math.max(...arr))
      }
    }, { root, rootMargin: '300px 0px' })
    pageEls.current.slice(0, count).forEach((el) => el && io.observe(el))
    if (!scrollMemory.get(nodeId)) fetchRange(0, 0) // fresh node at the top
    return () => io.disconnect()
  }, [count, nodeId, fetchRange])

  const onScroll = useCallback(() => {
    if (nodeId && scrollRef.current) scrollMemory.set(nodeId, scrollRef.current.scrollTop)
  }, [nodeId])

  if (!nodeId) return null
  if (count === 0) return <p className="status">Keine Vorschau (Ordner oder leer)</p>

  const width = Math.round(560 * zoom)
  return (
    <div className="win-preview" ref={scrollRef} onScroll={onScroll}>
      {Array.from({ length: count }, (_, i) => {
        const [w, h] = dims[i] || [595, 842]
        const url = pages[i]
        return (
          <div
            key={i}
            data-page={i}
            ref={(el) => { pageEls.current[i] = el }}
            className="win-page"
            style={{ width: `${width}px`, aspectRatio: `${w} / ${h}` }}
          >
            {url
              ? <img src={url} alt={`Seite ${i + 1}`} />
              : <div className="win-skeleton">Seite {i + 1}</div>}
          </div>
        )
      })}
    </div>
  )
}
