// Component tests for the Help modal: initial language (with EN fallback for an
// untranslated UI language), the 🇩🇪/🇬🇧 authoritative-text toggle, the pre-filled
// correction links, and close (button + Esc). German source strings (no provider).
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { HelpModal } from './HelpModal'
import { helpFor } from './help/content'

afterEach(cleanup)

const flag = (label) => screen.getByTitle(label) // "Deutsch" / "English"
const pressed = (el) => el.getAttribute('aria-pressed') === 'true'

describe('HelpModal — language', () => {
  it('opens in the UI language when that language has its own help text', () => {
    render(<HelpModal lang="de" onClose={() => {}} />)
    expect(pressed(flag('Deutsch'))).toBe(true)
    expect(pressed(flag('English'))).toBe(false)
  })

  it('falls back to English for a UI language with no authored help', () => {
    // an untranslated lang resolves to the EN fallback in helpFor → opens on EN
    expect(helpFor('zz')).toBe(helpFor('en')) // guard the assumption this test rests on
    render(<HelpModal lang="zz" onClose={() => {}} />)
    expect(pressed(flag('English'))).toBe(true)
  })

  it('the flags switch the authoritative text', () => {
    render(<HelpModal lang="de" onClose={() => {}} />)
    fireEvent.click(flag('English'))
    expect(pressed(flag('English'))).toBe(true)
    expect(pressed(flag('Deutsch'))).toBe(false)
  })
})

describe('HelpModal — correction links', () => {
  it('pre-fills a GitHub issue and a mailto with the current language', () => {
    render(<HelpModal lang="fr" onClose={() => {}} />)
    const gh = screen.getByText('▸ GitHub').closest('a')
    const mail = screen.getByText('✉ E-Mail').closest('a')
    expect(gh.getAttribute('href')).toContain('/issues/new?')
    expect(gh.getAttribute('href')).toContain(encodeURIComponent('[Übersetzung/Translation] fr'))
    expect(mail.getAttribute('href')).toMatch(/^mailto:/)
    expect(mail.getAttribute('href')).toContain(encodeURIComponent('fr'))
  })
})

describe('HelpModal — close', () => {
  it('the ✕ button closes', () => {
    const onClose = vi.fn()
    render(<HelpModal lang="de" onClose={onClose} />)
    fireEvent.click(screen.getByLabelText('Schließen'))
    expect(onClose).toHaveBeenCalled()
  })

  it('Esc closes (useModal)', () => {
    const onClose = vi.fn()
    render(<HelpModal lang="de" onClose={onClose} />)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })
})
