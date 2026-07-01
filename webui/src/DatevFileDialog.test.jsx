// DatevFileDialog tests (rendered without a LanguageProvider → German source strings).
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { DatevFileDialog } from './DatevFileDialog'

afterEach(cleanup)

const CLIENTS = [
  { guid: 'g1', number: '10001', name: 'Alpha AG' },
  { guid: 'g2', number: '10002', name: 'Beta GmbH' },
]
const PLACEMENTS = [{ id: 177, name: 'Stammakte', registers: [{ id: 461, name: 'Korrespondenz' }] }]

const render_ = (props = {}) => {
  const handlers = { onSubmit: vi.fn(), onCancel: vi.fn() }
  render(<DatevFileDialog clients={CLIENTS} placements={PLACEMENTS} currentYear={2026}
    {...handlers} {...props} />)
  return handlers
}

describe('DatevFileDialog', () => {
  it('disables Ablegen until a client is chosen, then submits the built opts', () => {
    const h = render_({ defaultName: 'Beleg' })           // name prefilled → only the client is missing
    const submit = screen.getByText('Ablegen')
    expect(submit).toBeDisabled()                         // no client → no safe target
    fireEvent.change(screen.getByLabelText('Mandant'), { target: { value: 'g2' } })
    expect(submit).not.toBeDisabled()
    fireEvent.click(submit)
    expect(h.onSubmit).toHaveBeenCalledWith({ clientGuid: 'g2', description: 'Beleg' })
  })

  // Regression — the "pdf lacks Name when saving to datev" bug: a client alone is NOT enough;
  // the Bezeichnung (DATEV document name) is required, and it flows through as `description`.
  it('requires a Bezeichnung even with a client; carries it as description', () => {
    const h = render_()                                   // no defaultName → name starts empty
    const submit = screen.getByText('Ablegen')
    fireEvent.change(screen.getByLabelText('Mandant'), { target: { value: 'g1' } })
    expect(submit).toBeDisabled()                         // client chosen but no name → still refused
    fireEvent.change(screen.getByLabelText('Bezeichnung'), { target: { value: 'Stromrechnung 2024' } })
    expect(submit).not.toBeDisabled()
    fireEvent.click(submit)
    expect(h.onSubmit).toHaveBeenCalledWith({ clientGuid: 'g1', description: 'Stromrechnung 2024' })
  })

  it('prefills the Bezeichnung from defaultName (the document name)', () => {
    render_({ defaultName: 'Eingangsrechnung' })
    expect(screen.getByLabelText('Bezeichnung')).toHaveValue('Eingangsrechnung')
  })

  // Regression — a SOLE matching client must auto-select so Ablegen enables without a manual
  // click (a 1-option listbox doesn't fire change on click in WebView2).
  it('auto-selects the only client so Ablegen enables without clicking it', () => {
    const h = render_({ clients: [{ guid: 'only', number: '10001', name: 'Einzige GmbH' }], defaultName: 'Beleg' })
    const submit = screen.getByText('Ablegen')
    expect(submit).not.toBeDisabled()                 // sole client auto-selected → ready
    expect(screen.getByLabelText('Mandant')).toHaveValue('only')
    fireEvent.click(submit)
    expect(h.onSubmit).toHaveBeenCalledWith({ clientGuid: 'only', description: 'Beleg' })
  })

  it('searching narrows the client options', () => {
    render_()
    fireEvent.change(screen.getByLabelText('Mandant suchen'), { target: { value: 'beta' } })
    const list = screen.getByLabelText('Mandant')
    expect(list.querySelectorAll('option')).toHaveLength(1)
    expect(list.querySelector('option').textContent).toMatch(/Beta GmbH/)
  })

  it('submits folder, register, date and Veranlagung year+month', () => {
    const h = render_({ defaultName: 'Beleg' })
    fireEvent.change(screen.getByLabelText('Mandant'), { target: { value: 'g1' } })
    fireEvent.change(screen.getByText('Ordner').closest('label').querySelector('select'),
      { target: { value: '177' } })
    fireEvent.change(screen.getByText('Register').closest('label').querySelector('select'),
      { target: { value: '461' } })
    fireEvent.change(screen.getByText('Belegdatum').closest('label').querySelector('input'),
      { target: { value: '2025-03-14' } })
    fireEvent.change(screen.getByText('Veranlagungsjahr').closest('label').querySelector('select'),
      { target: { value: '2025' } })
    fireEvent.change(screen.getByText('Veranlagungsmonat').closest('label').querySelector('select'),
      { target: { value: '3' } })
    fireEvent.click(screen.getByText('Ablegen'))
    expect(h.onSubmit).toHaveBeenCalledWith({
      clientGuid: 'g1', description: 'Beleg', folderId: 177, registerId: 461,
      documentDate: '2025-03-14T00:00:00', fiscalYear: 2025, fiscalMonth: 3,
    })
  })

  it('no clients (load failed/empty) → filing disabled with a reason', () => {
    render_({ clients: [] })
    expect(screen.getByText(/DATEV-Ablage nicht möglich/)).toBeInTheDocument()
    expect(screen.getByText('Ablegen')).toBeDisabled()
  })

  it('shows the load error and disables Ablegen', () => {
    render_({ clients: [], error: 'HTTP 404' })
    expect(screen.getByText(/HTTP 404/)).toBeInTheDocument()
    expect(screen.getByText('Ablegen')).toBeDisabled()
  })

  it('register select is disabled until a folder with registers is chosen', () => {
    render_()
    const reg = screen.getByText('Register').closest('label').querySelector('select')
    expect(reg).toBeDisabled()
    fireEvent.change(screen.getByText('Ordner').closest('label').querySelector('select'),
      { target: { value: '177' } })
    expect(reg).not.toBeDisabled()
  })
})
