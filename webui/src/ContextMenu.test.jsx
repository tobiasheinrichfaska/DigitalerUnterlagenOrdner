import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ContextMenu } from './ContextMenu'

// The status keys come from the core at runtime via config().statuses (that
// core↔config contract is asserted in tests/test_status_config.py); their UI labels
// are German display text run through t() (see statusLabel/STATUS_DE in ContextMenu).
// Components render without a LanguageProvider here, so t() yields the default
// language (German) — the assertions below expect the German labels.
const STATUS_KEYS = ['erfasst', 'zu erfassen', 'vorjahreswert']

function setup(node, extra = {}) {
  const spies = {
    dispatch: vi.fn(), onClose: vi.fn(), onExport: vi.fn(),
    onSetCollapsed: vi.fn(), onExpandAll: vi.fn(), onCollapseAll: vi.fn(),
  }
  const result = render(
    <ContextMenu menu={{ x: 10, y: 10, node }} mergeIds={extra.mergeIds ?? null}
      group={extra.group ?? null} selectedIds={extra.selectedIds ?? []}
      statuses={extra.statuses ?? STATUS_KEYS} {...spies} />,
  )
  return { ...result, ...spies }
}

const leaf = { id: 'L', name: 'doc', is_folder: false, pdf_length: 3, status: 'zu erfassen' }
const folder = { id: 'F', name: 'Ord', is_folder: true, collapsed: false, status: 'zu erfassen' }

describe('ContextMenu', () => {
  it('renders nothing without a menu', () => {
    const { container } = render(<ContextMenu menu={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('leaf: Split shown (multi-page), no folder-only entries', () => {
    setup(leaf)
    expect(screen.getByText(/Splitten/)).toBeInTheDocument()
    expect(screen.queryByText('Ordner anlegen')).toBeNull()
    expect(screen.queryByText('Zuklappen')).toBeNull()
    expect(screen.getByText('Alle aufklappen')).toBeInTheDocument()
  })

  it('single-page leaf hides Split', () => {
    setup({ ...leaf, pdf_length: 1 })
    expect(screen.queryByText(/Splitten/)).toBeNull()
  })

  it('folder: Ordner anlegen + Zuklappen + Alle entries; no Split', () => {
    setup(folder)
    expect(screen.getByText('Ordner anlegen')).toBeInTheDocument()
    expect(screen.getByText('Zuklappen')).toBeInTheDocument() // expanded → "Zuklappen"
    expect(screen.getByText('Alle aufklappen')).toBeInTheDocument()
    expect(screen.getByText('Alle zuklappen')).toBeInTheDocument()
    expect(screen.queryByText(/Splitten/)).toBeNull()
  })

  it('collapsed folder shows Aufklappen', () => {
    setup({ ...folder, collapsed: true })
    expect(screen.getByText('Aufklappen')).toBeInTheDocument()
  })

  it('Split submenu: "pro Seite" dispatches Split', () => {
    const { dispatch, onClose } = setup(leaf)
    fireEvent.click(screen.getByText(/Splitten/))      // open the submenu
    fireEvent.click(screen.getByText('pro Seite'))
    expect(dispatch).toHaveBeenCalledWith({ type: 'Split', node_id: 'L' })
    expect(onClose).toHaveBeenCalled()
  })

  it('Split submenu: "pro Seite → neuer Ordner" dispatches SplitInto into a folder', () => {
    const { dispatch } = setup(leaf)
    fireEvent.click(screen.getByText(/Splitten/))
    fireEvent.click(screen.getByText(/pro Seite → neuer Ordner/))
    expect(dispatch).toHaveBeenCalledWith({ type: 'SplitInto', size: 1, into_folder: true, node_id: 'L' })
  })

  it('Split submenu: "N Seiten pro Knoten…" prompts and dispatches SplitInto(size=N)', () => {
    vi.spyOn(window, 'prompt').mockReturnValue('5')
    const { dispatch } = setup(leaf)
    fireEvent.click(screen.getByText(/Splitten/))
    fireEvent.click(screen.getByText(/N Seiten pro Knoten/))
    expect(dispatch).toHaveBeenCalledWith({ type: 'SplitInto', size: 5, into_folder: false, node_id: 'L' })
  })

  it('Split submenu: cancelled N prompt dispatches nothing', () => {
    vi.spyOn(window, 'prompt').mockReturnValue(null)
    const { dispatch, onClose } = setup(leaf)
    fireEvent.click(screen.getByText(/Splitten/))
    fireEvent.click(screen.getByText(/N Seiten → neuer Ordner/))
    expect(dispatch).not.toHaveBeenCalled()
    expect(onClose).toHaveBeenCalled()
  })

  it('status entry dispatches SetStatus', () => {
    const { dispatch } = setup(leaf)
    fireEvent.click(screen.getByText('Erfasst'))
    expect(dispatch).toHaveBeenCalledWith({ type: 'SetStatus', node_id: 'L', status: 'erfasst' })
  })

  it('folder collapse entry toggles via onSetCollapsed', () => {
    const { onSetCollapsed, onClose } = setup(folder)
    fireEvent.click(screen.getByText('Zuklappen'))
    expect(onSetCollapsed).toHaveBeenCalledWith('F', true)
    expect(onClose).toHaveBeenCalled()
  })

  it('Alle auf-/zuklappen call the handlers', () => {
    const { onExpandAll, onCollapseAll } = setup(leaf)
    fireEvent.click(screen.getByText('Alle aufklappen'))
    expect(onExpandAll).toHaveBeenCalled()
    fireEvent.click(screen.getByText('Alle zuklappen'))
    expect(onCollapseAll).toHaveBeenCalled()
  })

  it('Löschen dispatches Delete (danger styling)', () => {
    const { dispatch } = setup(leaf)
    const del = screen.getByText('Löschen')
    expect(del).toHaveClass('danger')
    fireEvent.click(del)
    expect(dispatch).toHaveBeenCalledWith({ type: 'Delete', node_id: 'L' })
  })

  it('merge entry appears when the clicked node is in the selection and dispatches Merge', () => {
    const { dispatch } = setup(leaf, { mergeIds: ['L', 'M'], selectedIds: ['L', 'M'] })
    fireEvent.click(screen.getByText(/Zusammenführen/))
    expect(dispatch).toHaveBeenCalledWith({ type: 'Merge', node_ids: ['L', 'M'] })
  })

  it('merge entry is hidden when the clicked node is OUTSIDE the selection', () => {
    // matches the export/status/delete membership rule — right-clicking an
    // unrelated node must not offer merging the (invisible) selection
    setup({ ...leaf, id: 'X' }, { mergeIds: ['L', 'M'], selectedIds: ['L', 'M'] })
    expect(screen.queryByText(/Zusammenführen/)).toBeNull()
  })

  it('group entry appears when the clicked node is in the selection', () => {
    setup(leaf, { group: { ids: ['L', 'M'], parentId: 'P' }, selectedIds: ['L', 'M'] })
    expect(screen.getByText(/In neuen Ordner/)).toBeInTheDocument()
  })

  it('group entry is hidden when the clicked node is OUTSIDE the selection', () => {
    // same membership rule as merge — don't group the invisible selection from an
    // unrelated node
    setup({ ...leaf, id: 'X' }, { group: { ids: ['L', 'M'], parentId: 'P' }, selectedIds: ['L', 'M'] })
    expect(screen.queryByText(/In neuen Ordner/)).toBeNull()
  })

  it('export uses the selection when the node is part of it', () => {
    const { onExport } = setup(leaf, { selectedIds: ['L', 'X'] })
    fireEvent.click(screen.getByText(/Auswahl als PDF exportieren/))
    expect(onExport).toHaveBeenCalledWith(['L', 'X'])
  })

  it('backdrop click closes', () => {
    const { onClose, container } = setup(leaf)
    fireEvent.click(container.querySelector('.cm-backdrop'))
    expect(onClose).toHaveBeenCalled()
  })

  it('Escape closes the menu (F3)', () => {
    const { onClose } = setup(leaf)
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })
})
