// Virtualized, windowed preview for a selected leaf. Renders a placeholder box
// per page (height fixed by the page aspect-ratio, so it doesn't jump when the
// real image arrives), and only fetches the pages near the viewport (±BUFFER
// prefetch). Scroll position is remembered per node.
//
// `previewReq` (from the compression controls) switches the *source*: null →
// the plain stored bytes (core.renderWindow); {dpi, method} → a transient
// compressed variant (core.renderCompressedWindow). Both go through the same
// RenderService cache (keyed by the variant's content hash), so switching
// methods/back-to-original is windowed and cached, not an all-pages re-render.
import { useCallback, useEffect, useRef, useState } from 'react'
import { core } from './core'

const BUFFER = 5 // pages to prefetch on each side of the visible range
const scrollMemory = new Map() // nodeId -> scrollTop (survives remounts)

export function Preview({ session, node, zoom = 1, previewReq = null }) {
  const nodeId = node?.id
  const reqKey = previewReq ? `${previewReq.dpi}:${previewReq.method}` : 'orig'

  const [count, setCount] = useState(0)
  const [dims, setDims] = useState([])
  const [pages, setPages] = useState({}) // pageIndex -> data-URL

  const scrollRef = useRef(null)
  const pageEls = useRef([])
  const visible = useRef(new Set())
  const inflight = useRef(new Set()) // ranges already requested ("first-last")
  const token = useRef(0) // bumped on node/variant change to drop stale responses

  // page count + dims depend only on the node (a compressed variant has the same
  // page geometry), so fetch them once per node.
  useEffect(() => {
    if (!session || !nodeId) { setCount(0); setDims([]); return }
    let alive = true
    Promise.all([core.pageCount(session, nodeId), core.pageDims(session, nodeId)])
      .then(([c, d]) => {
        if (!alive) return
        setCount(c?.ok ? c.count : 0)
        setDims(d?.ok ? d.dims : [])
      })
      .catch(() => {})
    return () => { alive = false }
  }, [session, nodeId])

  // drop rendered images whenever the node OR the variant (method/dpi) changes;
  // the IntersectionObserver below then refetches the visible window.
  useEffect(() => {
    token.current += 1
    visible.current = new Set()
    inflight.current = new Set()
    setPages({})
  }, [nodeId, reqKey])

  const fetchRange = useCallback((lo, hi) => {
    if (!session || !nodeId || count === 0) return
    const first = Math.max(0, lo - BUFFER)
    const last = Math.min(count - 1, hi + BUFFER)
    if (last < first) return
    const key = `${first}-${last}`
    if (inflight.current.has(key)) return
    inflight.current.add(key)
    const t = token.current
    const req = previewReq
      ? core.renderCompressedWindow(session, nodeId, previewReq.dpi, previewReq.method, first, last - first + 1)
      : core.renderWindow(session, nodeId, first, last - first + 1)
    req
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
  }, [session, nodeId, count, reqKey]) // eslint-disable-line react-hooks/exhaustive-deps

  // observe which pages are on screen; (re)attaches on node/variant change so the
  // visible window is refetched with the right source.
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
    return () => io.disconnect()
  }, [count, nodeId, reqKey, fetchRange])

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
