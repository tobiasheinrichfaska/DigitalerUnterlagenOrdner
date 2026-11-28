import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Tree } from './Tree'
import { LanguageProvider } from './i18n/LanguageProvider'

const tree = {
  id: 'root', is_folder: true, children: [
    { id: 'A', name: 'x.zip – nicht importierbar (zu groß)', is_folder: false, pdf_length: 0, children: [] },
    { id: 'B', name: 'Rechnung', is_folder: false, pdf_length: 1, children: [] },
  ],
}

describe('Tree display of archive labels (TX-4)', () => {
  it('shows the English label but renames the REAL stored name', () => {
    localStorage.setItem('beleg.lang', 'en-US')
    const onRename = vi.fn()
    render(
      <LanguageProvider>
        <Tree node={tree} selectedIds={[]} primaryId="A" grabbedId={null} forceExpand={false}
          levelsFor={() => []} pending={[]} onSelect={vi.fn()} onContext={vi.fn()} onToggleCollapse={vi.fn()}
          onMove={vi.fn()} onMoveMany={vi.fn()} onDropFiles={vi.fn()} onRename={onRename} />
      </LanguageProvider>,
    )
    expect(screen.getByText(/x\.zip – not importable \(too large\)/)).toBeInTheDocument()
    expect(screen.getByText(/Rechnung/)).toBeInTheDocument()
    fireEvent.keyDown(screen.getAllByRole('treeitem')[0], { key: 'F2' })
    const input = document.querySelector('input.rename-input')
    expect(input).not.toBeNull()
    expect(input.value).toBe('x.zip – nicht importierbar (zu groß)')
    localStorage.removeItem('beleg.lang')
  })
})
