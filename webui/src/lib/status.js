// Pure helpers for the tree's status dots and the compression "undecided" marker.
// UI-free + tested. Node shape: { is_folder, status, compression_undecided, children }.
//
// Status -> dot colour (no status -> no dot). Folder rows aggregate their descendants:
// one dot per distinct descendant status (red -> yellow -> green) plus a black dot when
// some descendants have a status and some don't. The red front dot ("undecided") means
// a leaf still has no confirmed compression decision (see core: compression_undecided).

const STATUS_COLOR = { vorjahreswert: 'red', 'zu erfassen': 'yellow', erfasst: 'green' }
const ORDER = ['vorjahreswert', 'zu erfassen', 'erfasst'] // red, yellow, green

export const statusColor = (status) => STATUS_COLOR[status] || null

const leaves = (node) =>
  node.is_folder ? (node.children || []).flatMap(leaves) : [node]

// Trailing status dots for a row. Leaf: its own status (0 or 1). Folder: distinct
// descendant statuses (ordered) + black when mixed with/without status; empty or
// all-no-status folder -> [].
export function statusDots(node) {
  if (!node.is_folder) {
    const c = statusColor(node.status)
    return c ? [c] : []
  }
  const ls = leaves(node)
  const present = new Set(ls.map((l) => l.status).filter((s) => STATUS_COLOR[s]))
  const dots = ORDER.filter((s) => present.has(s)).map((s) => STATUS_COLOR[s])
  const hasStatus = ls.some((l) => STATUS_COLOR[l.status])
  const hasNone = ls.some((l) => !STATUS_COLOR[l.status])
  if (hasStatus && hasNone) dots.push('black')
  return dots
}

// Front red "compression undecided" dot. Leaf: its own flag. Folder: any descendant
// leaf undecided.
export function hasUndecided(node) {
  if (!node.is_folder) return !!node.compression_undecided
  return leaves(node).some((l) => l.compression_undecided)
}

// Tooltip label key per dot colour (German source → t() translates). Black is the
// folder "mixed with/without status" marker.
export const DOT_LABEL = {
  red: 'Vorjahr', yellow: 'Zu erfassen', green: 'Erfasst', black: 'Teils ohne Status',
}

// Leaves eligible for the proactive no-gain sweep: cheap (≤ maxPages) leaves that are
// still undecided and actually compressible (have a source, not already applied/blocked).
// Pure so the selection rule is unit-tested rather than buried in an effect.
export const SWEEP_MAX_PAGES = 5
export function sweepCandidates(tree, maxPages = SWEEP_MAX_PAGES) {
  const ids = []
  const walk = (n) => {
    if (!n) return
    if (!n.is_folder && n.has_source && !n.is_compressed && !n.no_compression
        && n.compression_undecided && n.pdf_length > 0 && n.pdf_length <= maxPages) {
      ids.push(n.id)
    }
    n.children?.forEach(walk)
  }
  walk(tree)
  return ids
}
