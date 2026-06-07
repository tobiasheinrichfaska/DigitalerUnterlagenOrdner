// How-to-use Help. Opens in the current UI language (falling back to English where
// not yet translated); the 🇩🇪 / 🇬🇧 flags switch to the authoritative German / English
// text. Footer offers two ways to report translation corrections: a pre-filled GitHub
// issue (preferred) and a mailto fallback (no account needed).
import { useEffect, useState } from 'react'
import { useT } from './i18n/LanguageProvider'
import { helpFor } from './help/content'

const REPO = 'https://github.com/tobiasheinrichfaska/DigitalerUnterlagenOrdner'
const EMAIL = 'tobias.a.w.heinrich@gmail.com'

export function HelpModal({ lang, onClose }) {
  const { t } = useT()
  const [view, setView] = useState(helpFor(lang) === helpFor('en') && lang !== 'en' ? 'en' : lang)
  const sections = helpFor(view)

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const subject = `[Übersetzung/Translation] ${lang}`
  const body = `Sprache / language: ${lang}\n\nKorrektur / correction:\n`
  const ghUrl = `${REPO}/issues/new?title=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
  const mailUrl = `mailto:${EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`

  return (
    <>
      <div className="cm-backdrop" onClick={onClose} />
      <div className="help-modal" role="dialog" aria-modal="true" aria-label={t('Hilfe')}>
        <div className="help-head">
          <h2>❓ {t('Hilfe')}</h2>
          <div className="help-flags">
            <button className={view === 'de' ? 'on' : ''} title="Deutsch"
              onClick={() => setView('de')} aria-pressed={view === 'de'}>🇩🇪</button>
            <button className={view === 'en' ? 'on' : ''} title="English"
              onClick={() => setView('en')} aria-pressed={view === 'en'}>🇬🇧</button>
          </div>
          <button className="help-close" onClick={onClose} aria-label={t('Schließen')}>✕</button>
        </div>

        <div className="help-body">
          {sections.map((s) => (
            <section key={s.t}>
              <h3>{s.t}</h3>
              <ul>{s.items.map((it, i) => <li key={i}>{it}</li>)}</ul>
            </section>
          ))}
        </div>

        <div className="help-foot">
          <span>{t('Übersetzungsfehler melden:')}</span>
          <a href={ghUrl} target="_blank" rel="noreferrer">▸ GitHub</a>
          <a href={mailUrl}>✉ E-Mail</a>
        </div>
      </div>
    </>
  )
}
