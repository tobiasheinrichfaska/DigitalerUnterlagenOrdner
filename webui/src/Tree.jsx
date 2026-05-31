// Recursive document-tree view. Each node action dispatches a real core command.

function TreeNode({ node, dispatch, selectedId, onSelect }) {
  const rename = () => {
    const name = window.prompt('Neuer Name', node.name)
    if (name) dispatch({ type: 'Rename', node_id: node.id, name })
  }
  const del = () => dispatch({ type: 'Delete', node_id: node.id })
  const addFolder = () =>
    dispatch({ type: 'AddFolder', parent_id: node.id, name: 'Neuer Ordner', index: null, new_id: null })

  return (
    <li>
      <div className={node.id === selectedId ? 'row selected' : 'row'}>
        <span
          className={node.is_folder ? 'name folder' : 'name leaf'}
          onClick={() => onSelect(node)}
        >
          {node.is_folder ? '📁' : '📄'} {node.name}
        </span>
        <span className="actions">
          {node.is_folder && <button title="Ordner anlegen" onClick={addFolder}>＋</button>}
          <button title="Umbenennen" onClick={rename}>✎</button>
          <button title="Löschen" onClick={del}>🗑</button>
        </span>
      </div>
      {node.children?.length > 0 && (
        <ul>
          {node.children.map((c) => (
            <TreeNode key={c.id} node={c} dispatch={dispatch} selectedId={selectedId} onSelect={onSelect} />
          ))}
        </ul>
      )}
    </li>
  )
}

export function Tree({ node, dispatch, selectedId, onSelect }) {
  // `node` is the implicit root container — don't render it; show its children.
  return (
    <ul className="tree">
      {(node.children ?? []).map((c) => (
        <TreeNode key={c.id} node={c} dispatch={dispatch} selectedId={selectedId} onSelect={onSelect} />
      ))}
    </ul>
  )
}
