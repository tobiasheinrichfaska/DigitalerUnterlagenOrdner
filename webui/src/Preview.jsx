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
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { core } from './lib/core'
import { pageFraction, scrollForAnchor } from './lib/zoomAnchor'
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

  // #9 zoom re-anchoring: remember the logical document position at the viewport top
  // (which page + how far down it) so a zoom change can keep it fixed instead of the
  // raw pixel scrollTop. anchorRef is refreshed every frame we scroll / (re)lay out.
  const anchorRef = useRef(null)
  const firstZoom = useRef(true)

  // page count + dims depend only on the node (a variant has the same geometry).
  // Restore from a small geometry cache instantly, then refresh in the background —
  // so a switch-back doesn't wait on a page_dims round-trip.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: reset page geometry when the node changes (then refresh from cache/backend)
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
    // Reset the "already loaded" mirror SYNCHRONOUSLY (not via the [pages] effect,
    // which lags one render): the scroll-restore effect below fires update() right
    // away, and fetchMissing reads pagesRef — if it still held the previous variant's
    // pages it would conclude "nothing to fetch" and you'd have to scroll to load the
    // new (compressed) preview. Clearing it here makes the variant switch refresh in place.
    pagesRef.current = {}
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: drop rendered pages when the node/variant changes
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

  // Capture the current top-of-viewport anchor (cheap: reuses the O(log n) visible
  // range + one element read). Stored for the next zoom change to re-apply (#9).
  const captureAnchor = useCallback(() => {
    const root = scrollRef.current
    if (!root || count === 0) return
    const vr = visibleRange()
    if (!vr) return
    const el = pageEls.current[vr[0]]
    if (!el) return
    anchorRef.current = { index: vr[0], fraction: pageFraction(root.scrollTop, el.offsetTop, el.offsetHeight) }
  }, [visibleRange, count])

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
    if (nodeId && scrollRef.current) {
      scrollMemory.set(nodeId, scrollRef.current.scrollTop)
      // Keep scrollMemory bounded (cap at 64 entries, same as geomCache) so
      // it doesn't grow unbounded across a long session with many nodes.
      if (scrollMemory.size > 64) scrollMemory.delete(scrollMemory.keys().next().value)
    }
    if (raf.current) return
    raf.current = requestAnimationFrame(() => { raf.current = 0; captureAnchor(); update() })
  }, [nodeId, update, captureAnchor])

  // Cancel any pending rAF on unmount to avoid calling update() on an unmounted component.
  useEffect(() => () => { if (raf.current) cancelAnimationFrame(raf.current) }, [])

  // restore scroll position + fetch the visible window on node/variant/count change.
  // Keyed on the node OBJECT (not its id) so a same-id content change — commit
  // ("Lesbarkeit geprüft"), rotate, reset — also refetches, matching the clear effect
  // above (which is what made those need a manual scroll before).
  useEffect(() => {
    const root = scrollRef.current
    if (!root || count === 0) return
    root.scrollTop = scrollMemory.get(nodeId) || 0
    const id = requestAnimationFrame(() => { captureAnchor(); update() })
    return () => cancelAnimationFrame(id)
  }, [count, node, reqKey, update]) // eslint-disable-line react-hooks/exhaustive-deps

  // #9: when the zoom changes the page boxes relayout (heights scale with zoom).
  // Re-apply the captured anchor against the NEW geometry so the document position
  // at the viewport top stays put instead of the pixel scrollTop. Skip the first
  // run (initial mount has no prior position to preserve — top-anchored is fine).
  useLayoutEffect(() => {
    if (firstZoom.current) { firstZoom.current = false; return }
    const root = scrollRef.current
    const a = anchorRef.current
    if (!root || !a) return
    const el = pageEls.current[a.index]
    if (!el) return
    root.scrollTop = scrollForAnchor(el.offsetTop, el.offsetHeight, a.fraction)
    if (nodeId) scrollMemory.set(nodeId, root.scrollTop)
  }, [zoom]) // eslint-disable-line react-hooks/exhaustive-deps

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
