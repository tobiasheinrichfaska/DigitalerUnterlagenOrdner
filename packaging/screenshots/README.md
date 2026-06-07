# Store listing screenshots

The PNGs uploaded to the Microsoft Store listing (Partner Center → submission → Store
listing → **Screenshots**). They are **not** part of the MSIX package.

- Capture from the **demo document only** (`scripts/make_demo_belegtool.py` → open with
  `python host.py <demo.belegtool>`), never from real/personal data.
- Size: **≥ 1366×768** (16:9). On an ultrawide, capture the **window only** (don't maximize);
  the app window resized to ~1600×920 works well.
- Suggested set: `01_main.png`, `02_export.png`, `03_compression.png`, `04_tags.png`,
  `05_help.png` (1 required; 3–5 recommended — main/export/help are the strongest).

Drop the captured `*.png` files here and commit them alongside the listing text in
`packaging/store-listing.md`.
