// DOM-wiring tests for the vanilla PDF-Tool filing dialog (the React surface has its own
// DatevFileDialog.test.jsx; the shared pure logic is in datevFiling.test.js). jsdom env.
import { describe, it, expect, afterEach } from 'vitest'
import { openFileDialog } from './fileDialog'

// Close any still-open dialog (Escape) so its document-level keydown listener doesn't leak.
afterEach(() => { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })); document.body.innerHTML = '' })

const CLIENTS = [
  { guid: 'g1', number: '10001', name: 'Alpha AG' },
  { guid: 'g2', number: '10002', name: 'Beta GmbH' },
]
const PLACEMENTS = [{ id: 177, name: 'Stammakte', registers: [{ id: 461, name: 'Korrespondenz' }] }]

const open = (extra = {}) => openFileDialog({ clients: CLIENTS, placements: PLACEMENTS, currentYear: 2026, ...extra })
const q = (sel) => document.querySelector(sel)
const fileBtn = () => [...document.querySelectorAll('button')].find((b) => b.textContent === 'Ablegen')
const cancelBtn = () => [...document.querySelectorAll('button')].find((b) => b.textContent === 'Abbrechen')

describe('openFileDialog (vanilla PDF-Tool dialog)', () => {
  it('renders a real aria-modal dialog and disables Ablegen until a client is chosen', () => {
    open({ defaultName: 'Beleg' })                          // name prefilled → only the client is missing
    const modal = q('[role="dialog"]')
    expect(modal.getAttribute('aria-modal')).toBe('true')   // real attribute, not an expando
    expect(fileBtn().disabled).toBe(true)
    q('select[aria-label="Mandant"]').value = 'g2'
    q('select[aria-label="Mandant"]').dispatchEvent(new Event('change'))
    expect(fileBtn().disabled).toBe(false)
  })

  // Regression — the "pdf lacks Name when saving to datev" bug: a client without a Bezeichnung
  // must keep Ablegen disabled; the name (prefilled from defaultName) carries through as description.
  it('requires a Bezeichnung; prefills it from defaultName and carries it as description', async () => {
    const p = open()                                        // no defaultName → name empty
    q('select[aria-label="Mandant"]').value = 'g2'
    q('select[aria-label="Mandant"]').dispatchEvent(new Event('change'))
    expect(fileBtn().disabled).toBe(true)                   // client chosen but no name → refused
    const desc = q('input[aria-label="Bezeichnung"]')
    desc.value = 'Stromrechnung'; desc.dispatchEvent(new Event('input'))
    expect(fileBtn().disabled).toBe(false)
    fileBtn().click()
    await expect(p).resolves.toEqual({ clientGuid: 'g2', description: 'Stromrechnung' })
  })

  it('auto-selects the only client so Ablegen enables without clicking it', () => {
    // Regression — "one client won't activate save": a sole match must auto-select (a 1-option
    // listbox doesn't fire change on click in WebView2).
    openFileDialog({ clients: [{ guid: 'only', number: '10001', name: 'Einzige GmbH' }],
      placements: PLACEMENTS, currentYear: 2026, defaultName: 'Beleg' })
    expect(q('select[aria-label="Mandant"]').value).toBe('only')
    expect(fileBtn().disabled).toBe(false)
  })

  it('search narrows the client options', () => {
    open()
    const search = q('input[aria-label="Mandant suchen"]')
    search.value = 'beta'
    search.dispatchEvent(new Event('input'))
    const opts = q('select[aria-label="Mandant"]').querySelectorAll('option')
    expect(opts).toHaveLength(1)
    expect(opts[0].textContent).toMatch(/Beta GmbH/)
  })

  it('register stays disabled until a folder with registers is chosen, and resets on folder change', () => {
    open()
    const reg = q('select[aria-label="Register"]')
    expect(reg.disabled).toBe(true)
    const folder = q('select[aria-label="Ordner"]')
    folder.value = '177'; folder.dispatchEvent(new Event('change'))
    expect(reg.disabled).toBe(false)
    expect([...reg.options].some((o) => o.textContent === 'Korrespondenz')).toBe(true)
  })

  it('resolves the built opts on confirm', async () => {
    const p = open({ defaultName: 'Beleg' })
    q('select[aria-label="Mandant"]').value = 'g1'
    q('select[aria-label="Mandant"]').dispatchEvent(new Event('change'))
    q('select[aria-label="Veranlagungsjahr"]').value = '2025'
    q('select[aria-label="Veranlagungsjahr"]').dispatchEvent(new Event('change'))
    q('select[aria-label="Veranlagungsmonat"]').value = '3'
    q('select[aria-label="Veranlagungsmonat"]').dispatchEvent(new Event('change'))
    fileBtn().click()
    await expect(p).resolves.toEqual({ clientGuid: 'g1', description: 'Beleg', fiscalYear: 2025, fiscalMonth: 3 })
    expect(q('[role="dialog"]')).toBeNull()   // dialog removed from the DOM
  })

  it('resolves null on cancel and on Escape', async () => {
    const p1 = open()
    cancelBtn().click()
    await expect(p1).resolves.toBeNull()
    const p2 = open()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await expect(p2).resolves.toBeNull()
  })
})
