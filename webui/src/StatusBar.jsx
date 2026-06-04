// Bottom status bar: shows what's happening in the background (compression /
// preview rendering / cache prefetch) and the render-cache occupancy. Activity
// counts come from core.js (in-flight heavy calls); cache stats are polled from
// the core (cheap render_stats).
import { useEffect, useState } from 'react'
import { core, onActivity } from './lib/core'
import { useT } from './i18n/LanguageProvider'

const mb = (b) => Math.round((b || 0) / (1024 * 1024))

export function StatusBar({ docPages = 0 }) {
  const { t } = useT()
  const [act, setAct] = useState({ compress: 0, render: 0 })
  const [stats, setStats] = useState(null)

  useEffect(() => onActivity(setAct), [])

  useEffect(() => {
    let alive = true
    const poll = () => core.renderStats().then((r) => { if (alive && r?.ok) setStats(r) }).catch(() => {})
    poll()
    const id = setInterval(poll, 1500)
    return () => { alive = false; clearInterval(id) }
  }, [])

  const setBudget = (newMb) => core.setCacheBudget(newMb).then((r) => { if (r?.ok) setStats(r) }).catch(() => {})
  const enlarge = () => { if (stats) setBudget(mb(stats.cache_budget) + 50) }
  const shrink = () => { if (stats) setBudget(Math.max(50, mb(stats.cache_budget) - 50)) }

  const parts = []
  if (act.compress > 0) parts.push(t('Komprimiere {n}', { n: act.compress }))
  if (act.render > 0) parts.push(t('Vorschau lädt {n}', { n: act.render }))
  if (stats?.prefetch_active) parts.push(t('Cache füllt'))
  const busy = parts.length > 0

  return (
    <footer className="status-bar">
      <span className={busy ? 'sb-activity busy' : 'sb-activity'}>
        {busy ? `⚙ ${parts.join(' · ')}` : t('Bereit')}
      </span>
      {stats && (
        <span className="sb-cache" title={t('Vorschau-Cache · {free} MB frei', { free: mb(stats.cache_free) })}>
          📦 {t('Cache {used}/{total} MB · {pages}/{doc} Seiten', {
            used: mb(stats.cache_used), total: mb(stats.cache_budget),
            pages: stats.cache_pages, doc: docPages,
          })}
          <button className="sb-plus" title={t('Cache verkleinern (−50 MB)')} onClick={shrink}>−</button>
          <button className="sb-plus" title={t('Cache vergrößern (+50 MB)')} onClick={enlarge}>＋</button>
        </span>
      )}
    </footer>
  )
}
