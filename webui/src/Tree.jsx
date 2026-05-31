// Recursive document-tree view. Click a node to select it (preview); right-click
// for operations (rename, split, status, folders, delete) via the context menu.

function TreeNode({ node, selectedId, onSelect, onContext }) {
  return (
    <li>
      <div
        className={node.id === selectedId ? 'row selected' : 'row'}
        onClick={() => onSelect(node)}
        onContextMenu={(e) => { e.preventDefault(); onContext(e.clientX, e.clientY, node) }}
      >
        <span className={node.is_folder ? 'name folder' : 'name leaf'}>
          {node.is_folder ? '📁' : '📄'} {node.name}
        </span>
      </div>
      {node.children?.length > 0 && (
        <ul>
          {node.children.map((c) => (
            <TreeNode key={c.id} node={c} selectedId={selectedId} onSelect={onSelect} onContext={onContext} />
          ))}
        </ul>
      )}
    </li>
  )
}

export function Tree({ node, selectedId, onSelect, onContext }) {
  // `node` is the implicit root container — don't render it; show its children.
  return (
    <ul className="tree">
      {(node.children ?? []).map((c) => (
        <TreeNode key={c.id} node={c} selectedId={selectedId} onSelect={onSelect} onContext={onContext} />
      ))}
    </ul>
  )
}
