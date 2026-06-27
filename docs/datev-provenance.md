# Provenance — which DATEV document a BelegTool file came from

Two ways to answer "where in DATEV did this file come from", in order of reliability.

## 1. EXACT — the checkout path (primary)

When DATEV checks a document out to an external editor, it materializes the file at a temp path
shaped like:

```
…\<document-GUID>\<document-file-id>[.pdf]
e.g.  …\Temp\DATEV\fa89ad42-8cd4-4828-8234-143161d41985\1085411.pdf
```

- the **folder** = the source **document GUID**
- the **file name** = the source **document_file_id** (the *current* file — after an exchange it
  is the new id, e.g. `1085411`, not the original)

`datev/provenance.py::parse_checkout_path()` extracts `{doc_guid, file_id}` from such a path.
This is **unambiguous** — no guessing. BelegTool captures the path when the file is handed over,
stores `{doc_guid, file_id}` on the node, and on save:

1. `GET /documents/{doc_guid}/structure-items` → find the item whose `document_file_id == file_id`
   → its `structure_item.id`;
2. `POST /document-files` (new bytes) → new `document_file_id`;
3. `PUT /documents/{doc_guid}/structure-items/{structure_item.id}` with the new file id.

(DokAb overwrites — see [`datev-dokumentenablage-recipe.md`](datev-dokumentenablage-recipe.md) §5.)

## 2. HEURISTIC — match by components (fallback)

When there is **no** checkout path (e.g. an imported PDF), match against the Mandant's documents
by **file size**, **title** (`description`), and/or **file name**. The DATEVconnect document
filter can't query size/description, so the probe **indexes client-side**: list the Mandant's
documents → read each structure for `size`/`name` → match locally.

`datev/provenance.py`:
- `provenance_stats(entries)` — over the indexed set, how many files are **uniquely** identified
  by size / title / name / (size+title), plus the worst collision. This is the *measurement* the
  probe reports ("Mandant indexieren + auswerten").
- `match_entries(entries, size=, title=, name=)` — the candidates for a given file: **1 = confident
  provenance, several = ambiguous** (need another component), 0 = not from this Mandant/not filed.

**Reliability rule of thumb (measure per firm with the probe):** size alone collides (many small
PDFs share a byte count); **size + title** is usually unique; file name is weak (DATEV often
renames). Always prefer the exact path (§1); fall back to §2 only when no path is available, and
treat a multi-candidate result as "unknown, ask the user".

## Probe usage

In `DATEV-Probe.exe`, the **Provenance** panel: resolve a Mandant → *Mandant indexieren +
auswerten* prints the uniqueness percentages; enter a *Größe (B)* and/or *Titel* → *Match* shows
the candidate document(s). Use it to decide, per firm, whether the heuristic is trustworthy or the
checkout-path capture is mandatory.
