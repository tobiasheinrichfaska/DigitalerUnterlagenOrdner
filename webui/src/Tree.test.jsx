import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Tree } from './Tree'

const baseTree = {
  id: 'root', is_folder: true, children: [
    { id: 'F', name: 'Ordner', is_folder: true, collapsed: false, children: [
      { id: 'L1', name: 'doc1', is_folder: false, pdf_length: 2, children: [] },
    ] },
    { id: 'L2', name: 'doc2', is_folder: false, pdf_length: 1, children: [] },
  ],
}

function renderTree(props = {}) {
  const spies = {
    onSelect: vi.fn(), onContext: vi.fn(), onToggleCollapse: vi.fn(),
    onMove: vi.fn(), onMoveMany: vi.fn(), onDropFiles: vi.fn(), onRename: vi.fn(),
  }
  const result = render(
    <Tree node={baseTree} selectedIds={[]} primaryId={null} grabbedId={null} forceExpand={false}
      levelsFor={() => []} pending={[]} {...spies} {...props} />,
  )
  return { ...result, ...spies }
}

const collapsedTree = {
  ...baseTree,
  children: baseTree.children.map((c) => (c.id === 'F' ? { ...c, collapsed: true } : c)),
}

describe('Tree', () => {
  it('renders folder and leaf names', () => {
    renderTree()
    expect(screen.getByText(/Ordner/)).toBeInTheDocument()
    expect(screen.getByText(/doc1/)).toBeInTheDocument()
    expect(screen.getByText(/doc2/)).toBeInTheDocument()
  })

  it('click selects with modifier flags', () => {
    const { onSelect } = renderTree()
    fireEvent.click(screen.getByText(/doc2/))
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 'L2' }), { ctrl: false, shift: false })
    fireEvent.click(screen.getByText(/doc1/), { ctrlKey: true })
    expect(onSelect).toHaveBeenLastCalledWith(expect.objectContaining({ id: 'L1' }), { ctrl: true, shift: false })
    fireEvent.click(screen.getByText(/doc2/), { shiftKey: true })
    expect(onSelect).toHaveBeenLastCalledWith(expect.objectContaining({ id: 'L2' }), { ctrl: false, shift: true })
  })

  it('chevron toggles collapse without selecting', () => {
    const { onToggleCollapse, onSelect } = renderTree()
    fireEvent.click(screen.getByTitle('Zuklappen')) // folder is expanded → chevron says "Zuklappen"
    expect(onToggleCollapse).toHaveBeenCalledWith('F')
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('hides children of a collapsed folder; chevron flips', () => {
    renderTree({ node: collapsedTree })
    expect(screen.queryByText(/doc1/)).toBeNull()
    expect(screen.getByText(/doc2/)).toBeInTheDocument()
    expect(screen.getByTitle('Aufklappen')).toBeInTheDocument()
  })

  it('forceExpand shows children even when the folder is collapsed', () => {
    renderTree({ node: collapsedTree, forceExpand: true })
    expect(screen.getByText(/doc1/)).toBeInTheDocument()
  })

  it('marks the grabbed node with a .grabbed row', () => {
    const { container } = renderTree({ grabbedId: 'L2' })
    const grabbed = container.querySelector('.row.grabbed')
    expect(grabbed).toBeTruthy()
    expect(grabbed.textContent).toMatch(/doc2/)
  })

  it('marks the primary/selected rows', () => {
    const { container } = renderTree({ selectedIds: ['L1', 'L2'], primaryId: 'L2' })
    expect(container.querySelectorAll('.row.selected').length).toBe(2)
    expect(container.querySelector('.row.primary').textContent).toMatch(/doc2/)
  })

  it('clicking an already-marked node again starts inline rename → Enter dispatches onRename', async () => {
    const { onRename } = renderTree({ primaryId: 'L2' }) // doc2 is already the primary
    fireEvent.click(screen.getByText(/doc2/))            // click marked again → schedules rename
    const input = await screen.findByDisplayValue('doc2', {}, { timeout: 1000 })
    fireEvent.change(input, { target: { value: 'neuerName' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(onRename).toHaveBeenCalledWith('L2', 'neuerName')
  })

  it('Escape in the rename input cancels (no onRename)', async () => {
    const { onRename } = renderTree({ primaryId: 'L2' })
    fireEvent.click(screen.getByText(/doc2/))
    const input = await screen.findByDisplayValue('doc2', {}, { timeout: 1000 })
    fireEvent.keyDown(input, { key: 'Escape' })
    expect(onRename).not.toHaveBeenCalled()
  })

  it('rows are draggable and right-click opens the context menu', () => {
    const { onContext, container } = renderTree()
    expect(container.querySelector('.row[draggable="true"]')).toBeTruthy()
    fireEvent.contextMenu(screen.getByText(/doc2/))
    expect(onContext).toHaveBeenCalledWith(expect.any(Number), expect.any(Number), expect.objectContaining({ id: 'L2' }))
  })

  it('exposes tree/treeitem roles and aria-selected for accessibility', () => {
    const { container } = renderTree({ selectedIds: ['L2'] })
    expect(container.querySelector('ul.tree')).toHaveAttribute('role', 'tree')
    const rows = container.querySelectorAll('.row[role="treeitem"]')
    expect(rows.length).toBe(3) // F, L1, L2
    const selected = [...rows].filter((r) => r.getAttribute('aria-selected') === 'true')
    expect(selected.length).toBe(1)
    expect(selected[0].textContent).toContain('doc2')
    expect(rows[0].getAttribute('tabindex')).toBe('-1')
  })
})
