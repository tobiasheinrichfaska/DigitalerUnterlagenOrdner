// Tag editor for the current selection. Free-form entry with autocomplete from
// (favourites ∪ tags already used in the document), plus a managed "favourites" set
// kept in localStorage and surfaced as quick-add chips.
//
// One node selected → dispatches SetTags (replaces that node's whole tag set).
// Several selected (#7) → dispatches TagMany (add/remove ONE tag across all selected
// as one undo step); chips show the UNION of their tags, a tag not on every node is
// "partial" (te-chip-partial) and adding it completes it across the selection.
import { useState } from 'react'
import { useT } from './i18n/LanguageProvider'
import { tagSelectionState, tagsOnAll } from './lib/tags'

const FAV_KEY = 'beleg.tagFavourites'
const loadFavs = () => { try { return JSON.parse(localStorage.getItem(FAV_KEY)) || [] } catch { return [] } }
const saveFavs = (f) => { try { localStorage.setItem(FAV_KEY, JSON.stringify(f)) } catch { /* ignore */ } }

export function TagEditor({ node, nodes = null, docTags = [], dispatch }) {
  const { t } = useT()
  const [input, setInput] = useState('')
  const [favs, setFavs] = useState(loadFavs)

  const selected = (nodes && nodes.length ? nodes : (node ? [node] : [])).filter(Boolean)
  const multi = selected.length > 1
  const ids = selected.map((n) => n.id)

  // Chips: single → the node's own tags (all solid); multi → union with onAll flags.
  const chips = multi
    ? tagSelectionState(selected)
    : (node?.tags || []).map((tg) => ({ tag: tg, onAll: true }))
  // Tags excluded from add suggestions: already-present ones (on the node, or on ALL
  // when multi — a partial tag stays suggestible so it can be completed).
  const presentForAdd = multi ? tagsOnAll(selected) : (node?.tags || [])

  const add = (raw) => {
    const v = (raw || '').trim()
    setInput('')
    if (!v) return
    if (multi) dispatch({ type: 'TagMany', node_ids: ids, tag: v, add: true })
    else if (!(node.tags || []).includes(v)) dispatch({ type: 'SetTags', node_id: node.id, tags: [...(node.tags || []), v] })
  }
  const remove = (tg) => {
    if (multi) dispatch({ type: 'TagMany', node_ids: ids, tag: tg, add: false })
    else dispatch({ type: 'SetTags', node_id: node.id, tags: (node.tags || []).filter((x) => x !== tg) })
  }
  const toggleFav = (tg) => {
    const next = favs.includes(tg) ? favs.filter((x) => x !== tg) : [...favs, tg]
    setFavs(next); saveFavs(next)
  }

  const suggestions = [...new Set([...favs, ...docTags])].filter((tg) => !presentForAdd.includes(tg))
  const quickFavs = favs.filter((tg) => !presentForAdd.includes(tg)).slice(0, 8)

  return (
    <div className="tag-editor" title={t('Tags')}>
      <span className="te-label">🏷️</span>
      {multi && <span className="te-multi">{t('{n} markiert', { n: selected.length })}</span>}
      {chips.map(({ tag, onAll }) => (
        <span key={tag} className={onAll ? 'te-chip' : 'te-chip te-chip-partial'}
          title={onAll ? undefined : t('nur auf einigen markiert')}>
          {tag}
          <button className="te-star" title={favs.includes(tag) ? t('Aus Favoriten entfernen') : t('Zu Favoriten')}
            onClick={() => toggleFav(tag)}>{favs.includes(tag) ? '★' : '☆'}</button>
          <button className="te-x" title={t('Tag entfernen')} onClick={() => remove(tag)}>×</button>
        </span>
      ))}
      <input className="te-input" list="te-suggest" value={input} placeholder={t('+ Tag')}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add(input) }
          else if (e.key === 'Backspace' && !input && !multi && (node.tags || []).length) remove((node.tags || [])[(node.tags || []).length - 1])
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
