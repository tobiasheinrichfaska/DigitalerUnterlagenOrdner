// Pure anchor math for zoom re-anchoring (v3.10.0 #9).
//
// The preview lays pages out at width = 560 * zoom with a fixed aspect-ratio, so
// page heights scale with zoom and the total scrollHeight changes — but the raw
// pixel scrollTop does not. Zooming while scrolled down therefore drifts the
// document position. The fix: capture a LOGICAL anchor before the zoom change and
// re-apply it after the relayout.
//
// An anchor is { index, fraction }: which page sits at the viewport top, and how
// far down that page (0..1) the top edge falls. It is independent of zoom, so it
// can be measured under the old layout and re-applied against the new one.

const clamp01 = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : x)

// Intra-page fraction of `scrollTop` within the page box at [pageTop, pageTop+pageHeight).
// Returns 0 for a degenerate (zero/negative-height) box. Clamped to [0,1].
export function pageFraction(scrollTop, pageTop, pageHeight) {
  if (!(pageHeight > 0)) return 0
  return clamp01((scrollTop - pageTop) / pageHeight)
}

// The scrollTop that places `fraction` of the page box (at pageTop/pageHeight) at the
// viewport top — the inverse of pageFraction. Rounded to an integer pixel.
export function scrollForAnchor(pageTop, pageHeight, fraction) {
  const top = pageTop > 0 ? pageTop : 0
  const h = pageHeight > 0 ? pageHeight : 0
  return Math.round(top + clamp01(fraction) * h)
}
