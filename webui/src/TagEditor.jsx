// Tag editor for the selected node (folder or leaf). Free-form entry with
// autocomplete from (favourites ∪ tags already used in the document), plus a
// managed "favourites" set kept in localStorage and surfaced as quick-add chips.
// Dispatches SetTags (replaces the node's whole tag set).
import { useState } from 'react'
import { useT } from './i18n/LanguageProvider'

const FAV_KEY = 'beleg.tagFavourites'
const loadFavs = () => { try { return JSON.parse(localStorage.getItem(FAV_KEY)) || [] } catch { return [] } }
const saveFavs = (f) => { try { localStorage.setItem(FAV_KEY, JSON.stringify(f)) } catch { /* ignore */ } }

export function TagEditor({ node, docTags = [], dispatch }) {
  const { t } = useT()
  const [input, setInput] = useState('')
  const [favs, setFavs] = useState(loadFavs)
  const tags = node.tags || []

  const setTags = (next) => dispatch({ type: 'SetTags', node_id: node.id, tags: next })
  const add = (raw) => {
    const v = (raw || '').trim()
    setInput('')
    if (v && !tags.includes(v)) setTags([...tags, v])
  }
  const remove = (tg) => setTags(tags.filter((x) => x !== tg))
  const toggleFav = (tg) => {
    const next = favs.includes(tg) ? favs.filter((x) => x !== tg) : [...favs, tg]
    setFavs(next); saveFavs(next)
  }

  const suggestions = [...new Set([...favs, ...docTags])].filter((tg) => !tags.includes(tg))
  const quickFavs = favs.filter((tg) => !tags.includes(tg)).slice(0, 8)

  return (
    <div className="tag-editor" title={t('Tags')}>
      <span className="te-label">🏷️</span>
      {tags.map((tg) => (
        <span key={tg} className="te-chip">
          {tg}
          <button className="te-star" title={favs.includes(tg) ? t('Aus Favoriten entfernen') : t('Zu Favoriten')}
            onClick={() => toggleFav(tg)}>{favs.includes(tg) ? '★' : '☆'}</button>
          <button className="te-x" title={t('Tag entfernen')} onClick={() => remove(tg)}>×</button>
        </span>
      ))}
      <input className="te-input" list="te-suggest" value={input} placeholder={t('+ Tag')}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add(input) }
          else if (e.key === 'Backspace' && !input && tags.length) remove(tags[tags.length - 1])
        }}
        onBlur={() => { if (input) add(input) }} />
      <datalist id="te-suggest">{suggestions.map((s) => <option key={s} value={s} />)}</datalist>
      {quickFavs.length > 0 && (
        <span className="te-favs">
          {quickFavs.map((tg) => (
            <button key={tg} className="te-fav" title={t('Favorit hinzufügen')} onClick={() => add(tg)}>+ {tg}</button>
          ))}
        </span>
      )}
    </div>
  )
}
