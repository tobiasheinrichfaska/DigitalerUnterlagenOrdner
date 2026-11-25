# Extracting belegtool-archives into its own repository

No code change is required. The directory is self-contained (own `pyproject.toml`, tests, LICENSE).
Run in a **fresh clone** of the main repository:

1. `git clone <main-repo-url> belegtool-archives-extract && cd belegtool-archives-extract`
2. `git filter-repo --subdirectory-filter packages/belegtool-archives`
   (history of the moved files is preserved; the move was done with `git mv`)
3. Verify: `pip install -e .[dev] && pytest`
4. Create the empty GitHub repo `belegtool-archives`, then
   `git remote add origin https://github.com/<owner>/belegtool-archives.git && git push -u origin HEAD:main`
5. `git tag v0.1.0 && git push origin v0.1.0`
6. In the main repo:
   - `requirements.txt`: replace the line `./packages/belegtool-archives` with
     `belegtool-archives @ git+https://github.com/<owner>/belegtool-archives.git@v0.1.0`
   - `.github/workflows/ci.yml`: drop the `belegtool-archives` job (the requirements line now installs the package)
   - `git rm -r packages/belegtool-archives`, and update the note in `CLAUDE.md`
   - keep `infra/limits.py` (re-export) and `universal_importer/archives.py` (injects `UniversalImporter` as `convert_member`)
7. Later changes: bump the version in `pyproject.toml`, tag, update the tag in `requirements.txt`.

## Licensing note (`extract-msg`, GPLv3)

`.msg` support needs the OPTIONAL `extract-msg` (extra `msg`, GPLv3). The main repo's `requirements.txt`
currently pins `extract-msg==0.55.0` itself, so shipped builds contain it; the open licence question
(commercial licence vs. GPLv3 component, options: drop `.msg` from commercial builds or replace the
library by an own `olefile` reader) is documented in the main repo's CLAUDE.md, "Findings from 2026-10-18".
Replacing the reader happens inside this package only (`archives.py`, the `extract_msg` block).
