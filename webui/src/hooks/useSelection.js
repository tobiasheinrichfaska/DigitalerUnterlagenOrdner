import { useState } from 'react'

// Groups the tree-selection state: the primary (preview-driving) node, the
// multi-selection id list (Merge / group / multi-move), and the shift-range anchor.
// The selection *logic* (click handling, range, folder/child resolve) stays in App,
// where it needs the live tree and the active view — this hook just owns the state.
export function useSelection() {
  const [selected, setSelected] = useState(null)
  const [selectedIds, setSelectedIds] = useState([])
  const [anchorId, setAnchorId] = useState(null)
  return { selected, setSelected, selectedIds, setSelectedIds, anchorId, setAnchorId }
}
