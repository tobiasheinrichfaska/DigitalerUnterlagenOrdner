// Recursive document-tree view. Click a node to select it (preview); right-click
// for operations (rename, split, status, folders, delete) via the context menu.
// Drag a row onto another to move it: dropping on the top/bottom quarter reorders
// it as a sibling (before/after); dropping on the middle of a folder moves it
// inside. The drop only dispatches a Move command — the tree re-renders from the
// core's returned state (no optimistic local mutation).
import { useState } from 'react'

function dropZone(e, isFolder) {
  const r = e.currentTarget.getBoundingClientRect()
  const y = e.clientY - r.top
  if (isFolder) {
    if (y < r.height * 0.25) return 'before'
    if (y > r.height * 0.75) return 'after'
    return 'into'
  }
  return y < r.height / 2 ? 'before' : 'after'
}

function TreeNode({ node, parentId, index, selectedIds, primaryId, onSelect, onContext, onMove, onMoveMany, drag, setDrag }) {
  const [over, setOver] = useState(null) // 'into' | 'before' | 'after' | null

  const handleDragOver = (e) => {
    if (!drag || drag === node.id) return
    e.preventDefault()
    e.stopPropagation()
    setOver(dropZone(e, node.is_folder))
  }
  const handleDrop = (e) => {
    if (!drag || drag === node.id) { setOver(null); return }
    e.preventDefault()
    e.stopPropagation()
    // dragging a member of the multi-selection moves the whole set (at the drop spot)
    const many = selectedIds.includes(drag) && selectedIds.length > 1
    if (many) {
      if (over === 'into') onMoveMany(selectedIds, node.id, null)
      else onMoveMany(selectedIds, parentId, over === 'before' ? index : index + 1)
    } else if (over === 'into') onMove(drag, node.id, null)
    else if (over === 'before') onMove(drag, parentId, index)
    else if (over === 'after') onMove(drag, parentId, index + 1)
    setOver(null)
    setDrag(null)
  }

  const cls = ['row']
  if (selectedIds.includes(node.id)) cls.push('selected')
  if (node.id === primaryId) cls.push('primary')
  if (over) cls.push(`drop-${over}`)

  return (
    <li>
      <div
        className={cls.join(' ')}
        draggable
        onDragStart={(e) => { e.stopPropagation(); setDrag(node.id); e.dataTransfer.effectAllowed = 'move' }}
        onDragEnd={() => { setDrag(null); setOver(null) }}
        onDragOver={handleDragOver}
        onDragLeave={() => setOver(null)}
        onDrop={handleDrop}
        onClick={(e) => onSelect(node, { ctrl: e.ctrlKey || e.metaKey, shift: e.shiftKey })}
        onContextMenu={(e) => { e.preventDefault(); onContext(e.clientX, e.clientY, node) }}
      >
        <span className={node.is_folder ? 'name folder' : 'name leaf'}>
          {node.is_folder ? '📁' : '📄'} {node.name}
        </span>
      </div>
      {node.children?.length > 0 && (
        <ul>
          {node.children.map((c, i) => (
            <TreeNode key={c.id} node={c} parentId={node.id} index={i}
              selectedIds={selectedIds} primaryId={primaryId} onSelect={onSelect} onContext={onContext}
              onMove={onMove} onMoveMany={onMoveMany} drag={drag} setDrag={setDrag} />
          ))}
        </ul>
      )}
    </li>
  )
}

export function Tree({ node, selectedIds, primaryId, onSelect, onContext, onMove, onMoveMany }) {
  // `node` is the implicit root container — don't render it; show its children.
  const [drag, setDrag] = useState(null)
  const dropOnRoot = (e) => {
    if (!drag) return
    e.preventDefault()
    if (selectedIds.includes(drag) && selectedIds.length > 1) onMoveMany(selectedIds, node.id)
    else onMove(drag, node.id, null)
    setDrag(null)
  }
  return (
    <ul
      className="tree"
      onDragOver={(e) => { if (drag) e.preventDefault() }}
      onDrop={dropOnRoot}
    >
      {(node.children ?? []).map((c, i) => (
        <TreeNode key={c.id} node={c} parentId={node.id} index={i}
          selectedIds={selectedIds} primaryId={primaryId} onSelect={onSelect} onContext={onContext}
          onMove={onMove} onMoveMany={onMoveMany} drag={drag} setDrag={setDrag} />
      ))}
    </ul>
  )
}
