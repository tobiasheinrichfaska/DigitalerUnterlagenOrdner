# UI log — decisions & behavior notes (React front end)

A running log of UI behavior decisions for the React app. Newest first.

- **Don't show the `root` node at the top.** When a new UI is started (empty or
  loaded), the document's `root` folder is the implicit container — the tree
  renders its **children at the top level**, not a literal "root" entry.
  Top-level "＋ Ordner" (toolbar) still adds under root. *(implemented in `src/Tree.jsx`)*
