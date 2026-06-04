// Virtualized, windowed preview for a selected leaf. Renders a placeholder box
// per page (height fixed by the page aspect-ratio, so it doesn't jump when the
// real image arrives), and only fetches the pages near the viewport.
//
// The UI asks ONLY for the page(s) currently on screen (a small, fast request).
// Prefetching the pages around the request — and seeding the rest lazily — is the
// middleware's job (RenderService.seed): it warms the cache around each request in
// the background and yields the instant a newer request arrives. So a jump or a
// node switch renders the visible page immediately, and scrolling hits a warm cache.
//
// On every scroll (incl. jumps / scrollbar drag) we compute the visible page range
// by binary-searching page offsets and fetch exactly that.
//
// `previewReq` switches the source: null → plain bytes (renderWindow); {dpi, method}
// → a transient compressed variant (renderCompressedWindow). Both go through the
// same RenderService cache. Scroll position is remembered per node.
import { useCallback, useEffect, useRef, useState } from 'react'
import { core } from './core'
import { useT } from './i18n/LanguageProvider'

const scrollMemory = new Map() // nodeId -> scrollTop (survives remounts)

// The rendered page bitmaps live in ONE place: the middleware RenderService cache
// (source of truth, content-versioned, 200 MB LRU). The UI keeps only the current
// node's already-fetched pages (component state) and never re-requests them; a
// switch-back re-fetches from the warm middleware cache. We do cache the cheap
// geometry (page count/dims) so a switch-back doesn't wait on a page_dims round-trip.
const geomCache = new Map() // nodeId -> { count, dims }  (metadata only; LRU-bounded)

export function Preview({ session, node, zoom = 1, previewReq = null, onPage = null }) {
  const { t } = useT()
  const nodeId = node?.id
  const reqKey = previewReq ? `${previewReq.dpi}:${previewReq.method}` : 'orig'

  const [count, setCount] = useState(0)
  const [dims, setDims] = useState([])
  const [pages, setPages] = useState({}) // pageIndex -> data-URL

  const scrollRef = useRef(null)
  const pageEls = useRef([])
  const inflight = useRef(new Set()) // ranges already requested ("first-last")
  const token = useRef(0) // bumped on node/variant change to drop stale responses
  const raf = useRef(0)
  const pagesRef = useRef({}) // mirror of `pages` for stale-free "already loaded?" checks
  useEffect(() => { pagesRef.current = pages }, [pages])

  // page count + dims depend only on the node (a variant has the same geometry).
  // Restore from a small geometry cache instantly, then refresh in the background —
  // so a switch-back doesn't wait on a page_dims round-trip.
  useEffect(() => {
    if (!session || !nodeId) { setCount(0); setDims([]); return }
    const cached = geomCache.get(nodeId)
    if (cached) { setCount(cached.count); setDims(cached.dims) }
    let alive = true
    Promise.all([core.pageCount(session, nodeId), core.pageDims(session, nodeId)])
      .then(([c, d]) => {
        if (!alive) return
        const cnt = c?.ok ? c.count : 0
        const dms = d?.ok ? d.dims : []
        setCount(cnt); setDims(dms)
        geomCache.set(nodeId, { count: cnt, dims: dms })
        if (geomCache.size > 64) geomCache.delete(geomCache.keys().next().value)
      })
      .catch(() => {})
    return () => { alive = false }
  }, [session, nodeId])

  // drop rendered images when the node OR variant changes (keyed by the node OBJECT
  // so an edit — new object — also refetches). The warm middleware cache makes the
  // re-fetch fast.
  useEffect(() => {
    token.current += 1
    inflight.current = new Set()
    setPages({})
  }, [node, reqKey])

  // fetch pages [first, last] (callers decide the span). Results go to component
  // state only; the bitmaps themselves are cached by the middleware.
  const fetchSpan = useCallback((first, last) => {
    if (first > last || first < 0 || !session || !nodeId) return
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
  }, [session, nodeId, reqKey]) // eslint-disable-line react-hooks/exhaustive-deps

  // fetch only the pages in [first,last] we don't already have, as contiguous runs
  const fetchMissing = useCallback((first, last) => {
    const lo = Math.max(0, first)
    const hi = Math.min(count - 1, last)
    const have = pagesRef.current
    let run = null
    for (let p = lo; p <= hi; p++) {
      if (!have[p]) { if (run) run[1] = p; else run = [p, p] }
      else if (run) { fetchSpan(run[0], run[1]); run = null }
    }
    if (run) fetchSpan(run[0], run[1])
  }, [fetchSpan, count])

  // the visible page range, via binary search on page offsets (O(log n) — fine for
  // huge documents and correct after a jump).
  const visibleRange = useCallback(() => {
    const root = scrollRef.current
    if (!root || count === 0) return null
    const top = root.scrollTop
    const bottom = top + root.clientHeight
    const els = pageEls.current
    let lo = 0, hi = count - 1, firstV = -1
    while (lo <= hi) {
      const mid = (lo + hi) >> 1
      const el = els[mid]
      if (!el) { lo = mid + 1; continue }
      if (el.offsetTop + el.offsetHeight >= top) { firstV = mid; hi = mid - 1 } else { lo = mid + 1 }
    }
    if (firstV < 0) return null
    let lastV = firstV
    for (let i = firstV; i < count; i++) {
      const el = els[i]
      if (!el || el.offsetTop > bottom) break
      lastV = i
    }
    return [firstV, lastV]
  }, [count])

  // fetch the visible page(s) first (only what's missing), then the immediate ±1
  // neighbours so a single-page scroll lands on a ready page. The broader window
  // (and neighbouring nodes) is warmed by the middleware — see CoreApi._seed_around.
  const update = useCallback(() => {
    // Before the page boxes are laid out (right after selecting a node), visibleRange
    // is null — fall back to the top so the first page loads immediately instead of
    // waiting for the first scroll.
    const vr = visibleRange() || [0, 0]
    fetchMissing(vr[0], vr[1])          // visible — highest priority
    fetchMissing(vr[1] + 1, vr[1] + 1)  // one ahead
    fetchMissing(vr[0] - 1, vr[0] - 1)  // one behind
    onPage?.(vr[0] + 1, count) // 1-based first visible page + total
  }, [visibleRange, fetchMissing, onPage, count])

  const onScroll = useCallback(() => {
    if (nodeId && scrollRef.current) scrollMemory.set(nodeId, scrollRef.current.scrollTop)
    if (raf.current) return
    raf.current = requestAnimationFrame(() => { raf.current = 0; update() })
  }, [nodeId, update])

  // restore scroll position + fetch the visible window on node/variant/count change
  useEffect(() => {
    const root = scrollRef.current
    if (!root || count === 0) return
    root.scrollTop = scrollMemory.get(nodeId) || 0
    const id = requestAnimationFrame(() => update())
    return () => cancelAnimationFrame(id)
  }, [count, nodeId, reqKey, update])

  if (!nodeId) return null
  if (count === 0) return <p className="status">{t('Keine Vorschau (Ordner oder leer)')}</p>

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
              ? <img src={url} alt={t('Seite {n}', { n: i + 1 })} />
              : <div className="win-skeleton">{t('Seite {n}', { n: i + 1 })}</div>}
          </div>
        )
      })}
    </div>
  )
}
