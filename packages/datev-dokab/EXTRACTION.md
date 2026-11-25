# Extracting datev-dokab into its own repository

No code change is required. The directory is self-contained (own `pyproject.toml`, tests, LICENSE).
Run in a **fresh clone** of the main repository:

1. `git clone <main-repo-url> datev-dokab-extract && cd datev-dokab-extract`
2. `git filter-repo --subdirectory-filter packages/datev-dokab`
   (history of the moved files is preserved; the move was done with `git mv`)
3. Verify: `pip install -e .[dev] && pytest`
4. Create the empty GitHub repo `datev-dokab`, then
   `git remote add origin https://github.com/<owner>/datev-dokab.git && git push -u origin HEAD:main`
5. `git tag v0.1.0 && git push origin v0.1.0`
6. In the main repo:
   - `requirements.txt`: replace the line `./packages/datev-dokab` with
     `datev-dokab @ git+https://github.com/<owner>/datev-dokab.git@v0.1.0`
   - `.github/workflows/ci.yml`: drop the `datev-dokab` job (the requirements line now installs the package)
   - `git rm -r packages/datev-dokab`, and update the note in `CLAUDE.md`
7. Later changes: bump the version in `pyproject.toml`, tag, update the tag in `requirements.txt`.
