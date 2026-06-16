import { useState } from 'react'

// Groups the tag-view state and its two derived flags. Tagging is off by default and
// auto-enables when a loaded file already has tags (App calls setTagsOn on open).
//
//   viewActive   — a non-identity view is on (active search OR group-by). While on,
//                  displayed positions are virtual → structural ops (reorder, import,
//                  delete, add-folder, merge, split) are disabled; content edits stay.
//   filterActive — a real SUBSET exists only for an active tag search (group-by alone
//                  reshapes the whole tree). "Open view in new window" is offered on
//                  this basis — independent of group-by.
export function useTagView() {
  const [tagsOn, setTagsOn] = useState(false)
  const [tagSearch, setTagSearch] = useState('')
  const [groupBy, setGroupBy] = useState(false)
  const toggleTags = () => setTagsOn((v) => !v)
  const viewActive = tagsOn && (tagSearch.trim() !== '' || groupBy)
  const filterActive = tagsOn && tagSearch.trim() !== ''
  return {
    tagsOn, setTagsOn, toggleTags,
    tagSearch, setTagSearch,
    groupBy, setGroupBy,
    viewActive, filterActive,
  }
}
