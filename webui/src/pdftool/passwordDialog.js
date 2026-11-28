// Small accessible password dialog (vanilla DOM, like fileDialog.js) for an encrypted PDF.
// openPasswordDialog({ wrong }) resolves to the typed password, or null on cancel. The password
// only travels through the returned promise into PDF.js' updatePassword — never logged/stored.
import { toolT } from './lang.js'

const el = (tag, props = {}, kids = []) => {
  const n = Object.assign(document.createElement(tag), props)
  for (const k of kids) n.append(k)
  return n
}

export function openPasswordDialog({ wrong = false } = {}) {
  return new Promise((resolve) => {
    const prev = document.activeElement
    const hint = el('div', {
      id: 'pw-hint', role: 'alert',
      textContent: wrong ? toolT('Falsches Passwort. Bitte erneut versuchen.')
        : toolT('Dieses PDF ist passwortgeschützt. Bitte Passwort eingeben.'),
    })
    if (wrong) hint.style.color = '#b91c1c'
    const input = el('input', { type: 'password', id: 'pw-input', autocomplete: 'off',
      ariaLabel: toolT('Passwort') })
    input.style.cssText = 'width:100%;box-sizing:border-box;margin:10px 0'
    const ok = el('button', { type: 'submit', textContent: toolT('Öffnen') })
    const cancel = el('button', { type: 'button', textContent: toolT('Abbrechen') })
    const row = el('div', {}, [ok, cancel])
    row.style.cssText = 'display:flex;gap:8px;justify-content:flex-end'
    const title = el('h2', { id: 'pw-title', textContent: toolT('Passwort erforderlich') })
    title.style.cssText = 'font-size:16px;margin:0 0 8px'
    const box = el('form', { role: 'dialog', ariaModal: 'true' }, [title, hint, input, row])
    box.setAttribute('aria-labelledby', 'pw-title')
    box.setAttribute('aria-describedby', 'pw-hint')
    box.style.cssText = 'background:#fff;padding:16px;border-radius:8px;width:340px;max-width:90vw'
    const overlay = el('div', { id: 'pw-overlay' }, [box])
    overlay.style.cssText = 'position:fixed;inset:0;z-index:50;background:rgba(0,0,0,.45);'
      + 'display:flex;align-items:center;justify-content:center'

    const done = (value) => {
      input.value = ''
      overlay.remove()
      try { prev && prev.focus && prev.focus() } catch { /* ignore */ }
      resolve(value)
    }
    box.addEventListener('submit', (e) => { e.preventDefault(); if (input.value) done(input.value) })
    cancel.addEventListener('click', () => done(null))
    overlay.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { e.preventDefault(); done(null) }
      if (e.key === 'Tab') {  // keep focus inside the modal
        const items = [input, ok, cancel]
        const i = items.indexOf(document.activeElement)
        e.preventDefault()
        items[(i + (e.shiftKey ? items.length - 1 : 1)) % items.length].focus()
      }
    })
    document.body.append(overlay)
    input.focus()
  })
}
