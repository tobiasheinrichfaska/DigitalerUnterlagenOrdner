// Accessibility lock for the icon-only toolbar buttons: Undo/Redo/„Speichern
// unter" show no text, so a screen reader needs an aria-label (the visual
// tooltip stays the title attribute). Renders without a LanguageProvider →
// default language (German source strings).
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Toolbar } from './Toolbar'

describe('Toolbar accessibility', () => {
  it('icon-only buttons carry aria-labels', () => {
    const noop = vi.fn()
    render(
      <Toolbar onOpen={noop} onNewWindow={noop} onImport={noop} onSave={noop}
        onSaveAs={noop} onExport={noop} onAddFolder={noop} onUndo={noop} onRedo={noop}
        onToggleTags={noop} onHelp={noop} lang="de" setLang={noop}
        dirty={false} selectedCount={0} canUndo canRedo tagsOn={false} busy={0} />,
    )
    expect(screen.getByLabelText('Rückgängig')).toBeInTheDocument()
    expect(screen.getByLabelText('Wiederholen')).toBeInTheDocument()
    expect(screen.getByLabelText('Speichern unter…')).toBeInTheDocument()
  })
})
