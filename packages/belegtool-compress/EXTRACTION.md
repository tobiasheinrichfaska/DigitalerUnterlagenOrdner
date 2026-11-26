# Extracting belegtool-compress into its own repository

No code change is required. The directory is self-contained (own `pyproject.toml`, tests, LICENSE).
Run in a **fresh clone** of the main repository:

1. `git clone <main-repo-url> belegtool-compress-extract && cd belegtool-compress-extract`
2. `git filter-repo --subdirectory-filter packages/belegtool-compress`
   (history of the moved files is preserved; the move was done with `git mv`)
3. Verify: `pip install -e .[dev] && pytest`
4. Create the empty GitHub repo `belegtool-compress`, then
   `git remote add origin https://github.com/<owner>/belegtool-compress.git && git push -u origin HEAD:main`
5. `git tag v0.1.0 && git push origin v0.1.0`
6. In the main repo:
   - `requirements.txt`: replace the line `./packages/belegtool-compress` with
     `belegtool-compress @ git+https://github.com/<owner>/belegtool-compress.git@v0.1.0`
   - `.github/workflows/ci.yml`: drop the `belegtool-compress` job (the requirements line now installs the package)
   - `git rm -r packages/belegtool-compress`, and update the note in `CLAUDE.md`
   - keep `formats/compress_pdf_bytes.py` and `services/cpu.py` (thin re-exports)
7. Later changes: bump the version in `pyproject.toml`, tag, update the tag in `requirements.txt`.

## Note

`pixels.capped_dpi` is a deliberate small copy of `services/render.capped_dpi` (the host's preview renderer
keeps its own); keep the two budgets (`MAX_RENDER_PIXELS`) in step when changing one.

The package depends on **pypdfium2** (permissive) only; PyMuPDF (AGPL/Artifex) is the test oracle in the `dev`/`oracle`
extras and must stay out of the package's runtime dependencies (the main repo guards this with
`tests/test_no_agpl_pdf_deps.py`). The parity measurements that justify the swap live in the main repo's
`docs/pdfium-spike.md` + `scripts/raster_compare.py`; copy them along if the history of that decision should travel with the package.
