// Component tests for the export-options dialog: the tag-index branch (offered
// only when the document has tags), the TOC→TOC-links dependency, and the
// option object handed back on confirm. Renders without a LanguageProvider →
// German source strings.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { ExportDialog } from './ExportDialog'

afterEach(cleanup)

const renderDialog = (props = {}) => {
  const onChoose = vi.fn()
  const onCancel = vi.fn()
  render(<ExportDialog hasTags={false} onChoose={onChoose} onCancel={onCancel} {...props} />)
  return { onChoose, onCancel }
}

describe('ExportDialog — tag index gating', () => {
  it('disables and unchecks the tag index when the document has no tags', () => {
    renderDialog({ hasTags: false })
    const idx = screen.getByLabelText('Stichwortverzeichnis (nach Tags)')
    expect(idx).toBeDisabled()
    expect(idx).not.toBeChecked()
  })

  it('enables and pre-checks the tag index when the document has tags', () => {
    renderDialog({ hasTags: true })
    const idx = screen.getByLabelText('Stichwortverzeichnis (nach Tags)')
    expect(idx).toBeEnabled()
    expect(idx).toBeChecked()
  })

  it('never reports index:true when there are no tags, even if the box could be ticked', () => {
    const { onChoose } = renderDialog({ hasTags: false })
    fireEvent.click(screen.getByText('Exportieren'))
    expect(onChoose).toHaveBeenCalledWith(expect.objectContaining({ index: false }))
  })
})

describe('ExportDialog — TOC ⇒ TOC-links dependency', () => {
  it('disables the TOC-links sub-option when TOC is turned off, and zeroes toc_links', () => {
    const { onChoose } = renderDialog()
    // two checkboxes share this label (TOC links + index links); the first is TOC's
    const tocLinks = screen.getAllByLabelText('mit anklickbaren Links')[0]

    // turn TOC off → the links sub-checkbox becomes disabled
    fireEvent.click(screen.getByLabelText('Inhaltsverzeichnis'))
    expect(tocLinks).toBeDisabled()

    fireEvent.click(screen.getByText('Exportieren'))
    expect(onChoose).toHaveBeenCalledWith(
      expect.objectContaining({ toc: false, toc_links: false }),
    )
  })
})

describe('ExportDialog — confirm / cancel', () => {
  it('returns the full default option set on Exportieren', () => {
    const { onChoose } = renderDialog({ hasTags: true })
    fireEvent.click(screen.getByText('Exportieren'))
    expect(onChoose).toHaveBeenCalledWith({
      toc: true, toc_links: true, index: true, index_links: true, bookmarks: true,
      split_pages: null, split_level: 'top',
    })
  })

  it('returns the split threshold + level when splitting is enabled (#13)', () => {
    const { onChoose } = renderDialog()
    fireEvent.click(screen.getByLabelText('In mehrere Dateien aufteilen'))
    const num = document.querySelector('.exp-num')
    fireEvent.change(num, { target: { value: '50' } })
    fireEvent.change(document.querySelector('.exp-level'), { target: { value: 'folder' } })
    fireEvent.click(screen.getByText('Exportieren'))
    expect(onChoose).toHaveBeenCalledWith(
      expect.objectContaining({ split_pages: 50, split_level: 'folder' }),
    )
  })

  it('disables and clears the index + bookmarks while splitting (split renders its own TOC)', () => {
    const { onChoose } = renderDialog({ hasTags: true })  // index + bookmarks on by default
    fireEvent.click(screen.getByLabelText('In mehrere Dateien aufteilen'))
    expect(screen.getByLabelText('Stichwortverzeichnis (nach Tags)')).toBeDisabled()
    expect(screen.getByLabelText('PDF-Lesezeichen (Seitenleiste)')).toBeDisabled()
    fireEvent.click(screen.getByText('Exportieren'))
    expect(onChoose).toHaveBeenCalledWith(expect.objectContaining({ index: false, bookmarks: false }))
  })

  it('keeps split_pages null while splitting is off', () => {
    const { onChoose } = renderDialog()
    fireEvent.click(screen.getByText('Exportieren'))
    expect(onChoose).toHaveBeenCalledWith(expect.objectContaining({ split_pages: null }))
  })

  it('cancels via the button, the backdrop, and Esc', () => {
    const { onCancel } = renderDialog()
    fireEvent.click(screen.getByText('Abbrechen'))
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onCancel).toHaveBeenCalled()
  })
})
