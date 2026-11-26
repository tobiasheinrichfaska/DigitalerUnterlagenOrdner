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

## Licensing note (`.msg` reader)

`.msg` support needs the extra `msg` = `olefile` (BSD-2-Clause) + `compressed-rtf` (MIT) - both permissive; `extract-msg` (GPLv3) and
RTFDE (LGPLv3) were replaced by the own reader `msg_reader.py` on 2026-11-26 (main repo: `docs/licence-audit.md`,
`tests/test_no_gpl_msg_deps.py`). The main repo's `requirements.txt` pins `olefile==0.47` and `compressed-rtf==1.0.7`. After the
extraction nothing changes: the reader never imports the host.
