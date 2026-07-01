// Vanilla-DOM DATEV filing dialog for the PDF-Tool surface (the organizer uses the React
// DatevFileDialog). Shares the pure logic in lib/datevFiling.js so both surfaces behave the
// same. openFileDialog(...) resolves to the datev_file opts object, or null on cancel.
import { filterClients, registersFor, MONTHS, yearChoices, validateFiling, buildFileOpts, soleClientGuid }
  from '../lib/datevFiling.js'

const el = (tag, props = {}, kids = []) => {
  const n = Object.assign(document.createElement(tag), props)
  for (const k of kids) n.append(k)
  return n
}

export function openFileDialog({ clients, placements = [], currentYear, defaultName = '' }) {
  return new Promise((resolve) => {
    const state = { clientGuid: '', description: defaultName, folderId: '', registerId: '',
      documentDate: '', fiscalYear: '', fiscalMonth: '' }

    const search = el('input', { type: 'search', placeholder: 'Suchen (Nummer oder Name)…',
      ariaLabel: 'Mandant suchen' })
    const clientSel = el('select', { size: 6, ariaLabel: 'Mandant', style: 'width:100%' })
    const descInp = el('input', { type: 'text', value: defaultName,
      placeholder: 'Name des Dokuments in DATEV', ariaLabel: 'Bezeichnung' })
    const folderSel = el('select', { ariaLabel: 'Ordner' })
    const registerSel = el('select', { ariaLabel: 'Register', disabled: true })
    const dateInp = el('input', { type: 'date', ariaLabel: 'Belegdatum' })
    const yearSel = el('select', { ariaLabel: 'Veranlagungsjahr' })
    const monthSel = el('select', { ariaLabel: 'Veranlagungsmonat' })
    const fileBtn = el('button', { type: 'button', textContent: 'Ablegen', disabled: true })
    const cancelBtn = el('button', { type: 'button', textContent: 'Abbrechen' })
    const hint = el('div', { style: 'color:#b91c1c;font-size:13px;min-height:1em' })

    const opt = (v, label) => el('option', { value: String(v), textContent: label })
    const fillClients = () => {
      const matches = filterClients(clients, search.value)
      clientSel.replaceChildren(...matches.map(
        (c) => opt(c.guid, `${c.number ? `${c.number} — ` : ''}${c.name}`)))
      // auto-select the sole match (a 1-option listbox doesn't fire change on click in WebView2);
      // if the current selection scrolled out of the filtered set, drop it so a stale guid can't submit.
      const sole = soleClientGuid(matches)
      if (sole) { clientSel.value = sole; state.clientGuid = sole }
      else if (!matches.some((c) => c.guid === state.clientGuid)) { state.clientGuid = ''; clientSel.value = '' }
      refresh()
    }
    const fillRegisters = () => {
      const regs = registersFor(placements, state.folderId)
      registerSel.disabled = !regs.length
      registerSel.replaceChildren(opt('', '— ohne —'), ...regs.map((r) => opt(r.id, r.name || r.id)))
    }
    folderSel.replaceChildren(opt('', '— ohne —'),
      ...placements.map((f) => opt(f.id, f.name || f.id)))
    yearSel.replaceChildren(opt('', '— ohne —'),
      ...yearChoices(currentYear).map((y) => opt(y, y)))
    monthSel.replaceChildren(opt('', '— ohne —'), ...MONTHS.map((m) => opt(m, m)))

    const refresh = () => {
      const v = validateFiling(state)
      fileBtn.disabled = !v.ok
      hint.textContent = v.ok ? '' : v.error
    }
    search.oninput = fillClients
    descInp.oninput = () => { state.description = descInp.value; refresh() }
    clientSel.onchange = () => { state.clientGuid = clientSel.value; refresh() }
    folderSel.onchange = () => { state.folderId = folderSel.value; state.registerId = ''; fillRegisters(); refresh() }
    registerSel.onchange = () => { state.registerId = registerSel.value; refresh() }
    dateInp.onchange = () => { state.documentDate = dateInp.value; refresh() }
    yearSel.onchange = () => { state.fiscalYear = yearSel.value; refresh() }
    monthSel.onchange = () => { state.fiscalMonth = monthSel.value; refresh() }
    fillClients()   // initial fill (after refresh is defined) — auto-selects a sole client
    fillRegisters()

    const field = (label, control) => el('label', { style: 'display:flex;flex-direction:column;gap:3px;font-size:13px;flex:1' },
      [el('span', { textContent: label }), control])
    const row = (...kids) => el('div', { style: 'display:flex;gap:10px' }, kids)

    const backdrop = el('div', { className: 'pdftool-modal-backdrop',
      style: 'position:fixed;inset:0;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:50' })
    const modal = el('div', { role: 'dialog',
      style: 'background:#fff;border-radius:10px;padding:18px;width:460px;max-width:92vw;box-shadow:0 12px 40px rgba(0,0,0,.3);display:flex;flex-direction:column;gap:10px' },
      [
        el('h2', { textContent: 'Nach DATEV ablegen', style: 'margin:0 0 4px;font-size:18px' }),
        field('Mandant', search), clientSel,
        field('Bezeichnung', descInp),
        row(field('Ordner', folderSel), field('Register', registerSel)),
        row(field('Belegdatum', dateInp), field('Veranlagungsjahr', yearSel), field('Veranlagungsmonat', monthSel)),
        hint,
        el('div', { style: 'display:flex;gap:8px;justify-content:flex-end' }, [fileBtn, cancelBtn]),
      ])
    modal.setAttribute('aria-modal', 'true')  // hyphenated ARIA attr isn't set via Object.assign
    backdrop.append(modal)

    let closed = false
    const close = (result) => {
      if (closed) return            // idempotent: a stray Esc after close must not double-remove
      closed = true
      document.removeEventListener('keydown', onKey)
      if (backdrop.parentNode) backdrop.parentNode.removeChild(backdrop)
      resolve(result)
    }
    const onKey = (e) => { if (e.key === 'Escape') close(null) }
    cancelBtn.onclick = () => close(null)
    backdrop.onclick = (e) => { if (e.target === backdrop) close(null) }
    fileBtn.onclick = () => { if (validateFiling(state).ok) close(buildFileOpts(state)) }
    document.addEventListener('keydown', onKey)
    document.body.append(backdrop)
    search.focus()
  })
}
