// Testmodus — golden-master review (dev/QA). Fetches CoreApi.test_mode and shows,
// per item, INPUT | LIVE | EXPECTED thumbnails with a match badge. Read-only;
// it does not touch the open document. Toggled from the App toolbar.
import { useEffect, useState } from 'react'
import { core } from './core'

const BADGE = {
  match: { text: '✓ stimmt mit Referenz überein', cls: 'tm-ok' },
  differ: { text: '✗ weicht ab', cls: 'tm-bad' },
  'no-expected': { text: '⚠ keine Referenz', cls: 'tm-warn' },
  'no-live': { text: '⚠ kein Ergebnis', cls: 'tm-warn' },
}

function Column({ title, pages }) {
  return (
    <div className="tm-col">
      <div className="tm-col-title">{title}</div>
      {pages && pages.length > 0
        ? pages.map((src, i) => <img key={i} src={src} alt={`${title} ${i + 1}`} />)
        : <div className="tm-empty">—</div>}
    </div>
  )
}

export function TestMode({ onClose }) {
  const [state, setState] = useState({ loading: true })

  useEffect(() => {
    let alive = true
    core.testMode()
      .then((r) => { if (alive) setState({ loading: false, ...r }) })
      .catch((e) => { if (alive) setState({ loading: false, ok: false, error: String(e.message || e) }) })
    return () => { alive = false }
  }, [])

  return (
    <div className="testmode">
      <div className="tm-bar">
        <b>Testmodus</b>
        <span className="tm-hint">Golden-Master: Eingabe · Live · Referenz</span>
        <button onClick={onClose}>Schließen</button>
      </div>

      {state.loading && <div className="tm-status">Operationen laufen …</div>}
      {!state.loading && !state.ok && (
        <div className="tm-status tm-bad">{state.error || 'Testmodus nicht verfügbar.'}</div>
      )}

      {!state.loading && state.ok && state.datasets.map((ds) => (
        <section className="tm-dataset" key={ds.name}>
          <h3>{ds.name}</h3>
          <div className="tm-desc">{ds.description}</div>
          {ds.error && <div className="tm-status tm-bad">{ds.error}</div>}
          {ds.items.map((it, i) => {
            const badge = BADGE[it.status] || BADGE['no-live']
            return (
              <div className="tm-item" key={i}>
                <div className="tm-item-head">
                  <span className="tm-label">{it.label}</span>
                  <span className={`tm-badge ${badge.cls}`}>{badge.text}</span>
                </div>
                <div className="tm-cols">
                  <Column title="Eingabe" pages={it.input} />
                  <Column title="Live" pages={it.live} />
                  <Column title="Referenz" pages={it.expected} />
                </div>
              </div>
            )
          })}
        </section>
      ))}
    </div>
  )
}
