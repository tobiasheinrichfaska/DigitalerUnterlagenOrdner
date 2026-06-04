import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { LanguageProvider, useT } from './LanguageProvider'
import { ContextMenu } from '../ContextMenu'

const leaf = { id: 'L', name: 'doc', is_folder: false, pdf_length: 3, status: 'zu erfassen' }
const spies = () => ({
  dispatch: vi.fn(), onClose: vi.fn(), onExport: vi.fn(),
  onSetCollapsed: vi.fn(), onExpandAll: vi.fn(), onCollapseAll: vi.fn(),
})

function renderMenu() {
  return render(
    <LanguageProvider>
      <ContextMenu menu={{ x: 10, y: 10, node: leaf }} statuses={['erfasst', 'zu erfassen', 'vorjahreswert']} {...spies()} />
    </LanguageProvider>,
  )
}

describe('LanguageProvider drives component language', () => {
  // jsdom's navigator.language is en-US, so set the language explicitly to test
  // deterministically (the real app picks navigator/localStorage at runtime).
  beforeEach(() => { localStorage.clear() })

  it('renders German when the stored language is "de"', () => {
    localStorage.setItem('beleg.lang', 'de')
    renderMenu()
    expect(screen.getByText('Löschen')).toBeInTheDocument()
    expect(screen.getByText('Erfasst')).toBeInTheDocument()        // status.erfasst → 'Erfasst'
    expect(screen.getByText(/Splitten/)).toBeInTheDocument()
  })

  it('renders English when the stored language is "en"', () => {
    localStorage.setItem('beleg.lang', 'en')
    renderMenu()
    expect(screen.getByText('Delete')).toBeInTheDocument()
    expect(screen.getByText('Recorded')).toBeInTheDocument()        // status.erfasst → 'Recorded'
    expect(screen.getByText(/Split/)).toBeInTheDocument()
    expect(screen.queryByText('Löschen')).toBeNull()
  })

  it('setLang switches language live and persists it', () => {
    localStorage.setItem('beleg.lang', 'de')
    function Probe() {
      const { lang, setLang, t } = useT()
      return (
        <div>
          <span data-testid="label">{t('Löschen')}</span>
          <button onClick={() => setLang('en')}>to-en</button>
          <span data-testid="lang">{lang}</span>
        </div>
      )
    }
    render(<LanguageProvider><Probe /></LanguageProvider>)
    expect(screen.getByTestId('label').textContent).toBe('Löschen')
    fireEvent.click(screen.getByText('to-en'))
    expect(screen.getByTestId('label').textContent).toBe('Delete')
    expect(screen.getByTestId('lang').textContent).toBe('en')
    expect(localStorage.getItem('beleg.lang')).toBe('en')
  })
})
