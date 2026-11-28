// Accessibility regressions (audit W4, AX-1..AX-12). jsdom can express roles, names,
// tabindex and focus; colour/contrast items are CSS and covered by the axe scan.
// No vi.mock — real components against the default (German) i18n context.
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, fireEvent, cleanup, within, waitFor } from '@testing-library/react'
import { Tree } from './Tree'
import { PreviewControls } from './PreviewControls'
import { PreviewPane } from './PreviewPane'
import { Preview } from './Preview'
import { SaveDialog } from './SaveDialog'
import { ExportDialog } from './ExportDialog'
import { DatevFileDialog } from './DatevFileDialog'
import { HelpModal } from './HelpModal'
import { ContextMenu } from './ContextMenu'
import { SaveSplitButton } from './SaveSplitButton'
import { TagEditor } from './TagEditor'
import { TagViewBar } from './TagViewBar'
import { StatusBar } from './StatusBar'
import { LanguageProvider } from './i18n/LanguageProvider'

afterEach(() => { cleanup(); delete window.pywebview; document.documentElement.lang = '' })

const tree = {
  id: 'root', is_folder: true, children: [
    { id: 'F', name: 'Ordner', is_folder: true, collapsed: false, status: '', children: [
      { id: 'L1', name: 'doc1', is_folder: false, pdf_length: 2, status: 'erfasst', children: [] },
      { id: 'L2', name: 'doc2', is_folder: false, pdf_length: 2, status: 'zu erfassen', children: [] },
    ] },
    { id: 'L3', name: 'doc3', is_folder: false, pdf_length: 1, status: 'vorjahreswert', children: [] },
  ],
}
const renderTree = (props = {}) => render(
  <Tree node={tree} selectedIds={[]} primaryId={null} grabbedId={null} forceExpand={false}
    levelsFor={() => []} pending={[]} onSelect={vi.fn()} onContext={vi.fn()} onToggleCollapse={vi.fn()}
    onMove={vi.fn()} onMoveMany={vi.fn()} onDropFiles={vi.fn()} onRename={vi.fn()} {...props} />,
)

describe('AX-1 tree ARIA structure', () => {
  it('has only role=none/treeitem children, nested lists are groups, rows carry aria-level', () => {
    const { container } = renderTree()
    const root = container.querySelector('[role=tree]')
    for (const li of root.querySelectorAll('li')) expect(li.getAttribute('role')).toBe('none')
    const group = root.querySelector('ul')
    expect(group.getAttribute('role')).toBe('group')
    expect(screen.getByText(/doc1/).closest('[role=treeitem]').getAttribute('aria-level')).toBe('2')
    expect(screen.getByText(/doc3/).closest('[role=treeitem]').getAttribute('aria-level')).toBe('1')
    expect(root.getAttribute('aria-multiselectable')).toBe('true')
    expect(root.getAttribute('aria-label')).toBe('Dokumentstruktur')
  })
})

describe('AX-12 roving tabindex', () => {
  it('the primary row is the single tab stop', () => {
    const { container } = renderTree({ primaryId: 'L2', selectedIds: ['L2'] })
    const stops = [...container.querySelectorAll('[role=treeitem]')].filter((r) => r.tabIndex === 0)
    expect(stops).toHaveLength(1)
    expect(stops[0]).toHaveTextContent('doc2')
  })
  it('without a primary the first row is the tab stop', () => {
    const { container } = renderTree()
    const stops = [...container.querySelectorAll('[role=treeitem]')].filter((r) => r.tabIndex === 0)
    expect(stops).toHaveLength(1)
    expect(stops[0]).toHaveTextContent('Ordner')
  })
})

describe('AX-4 rename input', () => {
  it('is labelled', () => {
    renderTree({ primaryId: 'L1', selectedIds: ['L1'] })
    fireEvent.keyDown(window, { key: 'F2' })
    expect(screen.getByRole('textbox', { name: 'Umbenennen' })).toBeInTheDocument()
  })
})

describe('AX-7 status dots have text alternatives', () => {
  it('leaf and folder aggregate dots expose their status names', () => {
    renderTree()
    expect(screen.getAllByRole('img', { name: 'Erfasst' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('img', { name: 'Zu erfassen' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('img', { name: 'Vorjahr' }).length).toBeGreaterThan(0)
  })
})

describe('AX-9 chevron name', () => {
  it('folder chevron has an aria-label, not the glyph', () => {
    renderTree()
    expect(screen.getByRole('button', { name: 'Zuklappen' })).toBeInTheDocument()
  })
})

function installApi() {
  window.pywebview = { api: new Proxy({}, { get(_, p) {
    if (typeof p !== 'string' || p === 'then') return undefined
    return () => Promise.resolve(
      p === 'page_count' ? { ok: true, count: 2 }
        : p === 'page_dims' ? { ok: true, dims: [[595, 842], [595, 842]] }
          : p === 'compress_options' ? { ok: true, options: [], original_size: 100 }
            : { ok: true, pages: [] })
  } }) }
}

describe('AX-2 / AX-9 preview controls', () => {
  it('compress select and rotate buttons have names', () => {
    installApi()
    render(<PreviewControls node={{ id: 'n', name: 'd', is_folder: false, pdf_length: 2, has_source: true, dpi_current: 150 }}
      dispatch={vi.fn()} onPreview={vi.fn()} onResolved={vi.fn()} />)
    expect(screen.getByRole('combobox', { name: 'Kompressionsmethode' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'links drehen' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'rechts drehen' })).toBeInTheDocument()
  })
})

describe('AX-9 zoom bar, status bar, tags', () => {
  it('zoom buttons are named by their action', () => {
    installApi()
    render(<PreviewPane previewRef={{ current: null }} tagsOn={false} selected={{ id: 'n', name: 'd', is_folder: false, pdf_length: 2 }}
      docTags={[]} dispatch={() => {}} session="s" onPreview={() => {}} defaultDpi={150} onCompressionResolved={() => {}}
      windowed pages={null} pageInfo={null} zoom={1} setZoom={vi.fn()} previewReq={null} onPageInfo={() => {}} busy={0} />)
    for (const n of ['kleiner', 'größer', '100% — zurücksetzen']) expect(screen.getByRole('button', { name: n })).toBeInTheDocument()
  })
  it('tag editor star/remove name the tag', () => {
    render(<TagEditor node={{ id: 'N', tags: ['abc'] }} docTags={[]} dispatch={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Tag entfernen: abc' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Zu Favoriten: abc/ })).toBeInTheDocument()
  })
  it('tag search clear is named', () => {
    render(<TagViewBar search="x" setSearch={vi.fn()} group={false} setGroup={vi.fn()} allTags={[]}
      onOpenInNewWindow={vi.fn()} onReset={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Suche löschen' })).toBeInTheDocument()
  })
  it('status bar cache buttons are named', async () => {
    window.pywebview = { api: new Proxy({}, { get: (_, p) => (p === 'then' ? undefined : () => ({ ok: true, cache_used: 0, cache_budget: 200 * 1048576, cache_free: 0, cache_pages: 0, prefetch_active: false })) }) }
    render(<StatusBar docPages={20} />)
    expect(await screen.findByRole('button', { name: 'Cache verkleinern (−50 MB)' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cache vergrößern (+50 MB)' })).toBeInTheDocument()
  })
})

describe('AX-3 dialogs are named', () => {
  it('Save dialog', () => {
    render(<SaveDialog count={1} onChoose={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByRole('dialog', { name: 'Komprimierungs-Alternativen speichern?' })).toBeInTheDocument()
  })
  it('Export dialog', () => {
    render(<ExportDialog hasTags={false} onChoose={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByRole('dialog', { name: 'PDF exportieren' })).toBeInTheDocument()
  })
  it('DATEV filing dialog', () => {
    render(<DatevFileDialog clients={[]} placements={[]} currentYear={2026} onSubmit={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByRole('dialog', { name: 'Nach DATEV ablegen' })).toBeInTheDocument()
  })
})

describe('AX-5 scrollable regions are keyboard reachable', () => {
  it('help body', () => {
    const { container } = render(<HelpModal lang="de" onClose={vi.fn()} />)
    const body = container.querySelector('.help-body')
    expect(body.tabIndex).toBe(0)
    expect(body.getAttribute('aria-label')).toBeTruthy()
  })
  it('page preview', async () => {
    installApi()
    const { container } = render(<Preview session="s1" node={{ id: 'n', is_folder: false, pdf_length: 2 }} zoom={1} previewReq={null} onPage={null} />)
    await waitFor(() => expect(container.querySelector('.win-preview')).not.toBeNull())
    const el = container.querySelector('.win-preview')
    expect(el.tabIndex).toBe(0)
    expect(screen.getByRole('region', { name: 'Seitenvorschau' })).toBe(el)
  })
})

describe('AX-10 focus returns after Escape', () => {
  it('save split menu returns focus to the caret', () => {
    render(<SaveSplitButton onSave={vi.fn()} onSaveAs={vi.fn()} />)
    const caret = screen.getByRole('button', { name: 'Weitere Speicheroptionen' })
    fireEvent.click(caret)
    const item = screen.getByRole('menuitem')
    item.focus()
    fireEvent.keyDown(item, { key: 'Escape' })
    expect(screen.queryByRole('menu')).toBeNull()
    expect(document.activeElement).toBe(caret)
  })
  it('context menu returns focus to the invoking element when it closes', () => {
    const row = document.createElement('div'); row.tabIndex = -1; document.body.appendChild(row); row.focus()
    const node = { id: 'L', name: 'doc', is_folder: false, pdf_length: 3 }
    const props = { dispatch: vi.fn(), onClose: vi.fn(), statuses: [], selectedIds: [] }
    const { rerender } = render(<ContextMenu menu={{ x: 1, y: 1, node }} {...props} />)
    expect(document.activeElement).not.toBe(row)
    rerender(<ContextMenu menu={null} {...props} />)
    expect(document.activeElement).toBe(row)
    row.remove()
  })
})

describe('AX-11 document language', () => {
  beforeEach(() => { try { localStorage.setItem('beleg.lang', 'fr') } catch { /* */ } })
  afterEach(() => { try { localStorage.removeItem('beleg.lang') } catch { /* */ } })
  it('follows the selected UI language', () => {
    render(<LanguageProvider><span /></LanguageProvider>)
    expect(document.documentElement.lang).toBe('fr')
  })
  it('maps a non-BCP-47 internal code to a private-use tag', () => {
    localStorage.setItem('beleg.lang', 'mnn')
    render(<LanguageProvider><span /></LanguageProvider>)
    expect(document.documentElement.lang).toBe('x-mnn')
  })
})
void within
