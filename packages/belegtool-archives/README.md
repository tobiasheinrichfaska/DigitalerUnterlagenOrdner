# belegtool-archives

Dependency-free Python library that unpacks **ZIP / TAR / TGZ / EML / MSG** containers into a nested
structure (`{"name", "content": BytesIO}` leaves, `{"name", "children": [...]}` folders) with hard
**decompression-bomb guards**. The import name is `belegtool_archives`.

Extracted from the DigitalerUnterlagenOrdner (BelegTool) project, which consumes it for its import
pipeline. It does not import the host application.

## What it does

- Recurses into nested containers (`.zip`/`.tar`/`.tgz`/`.eml`/`.msg` inside another container), depth-bounded
  (`_ARCHIVE_MAX_DEPTH = 10`); one shared budget (decoded bytes + member count, `limits.BOMB_CAP_*`) spans all levels.
- Zip members are limited to stored/deflate (bzip2/LZMA are refused); tar streams (gz/bz2/xz, multi-stream) are
  inflated bounded by the remaining budget; member paths become folder nodes (path traversal and drive letters
  stripped, total folder depth capped).
- Mail: body + attachments (EML via the standard library; MSG via the optional `extract-msg`).

## Converting members

The library does not convert images/Office/HTML. The host injects a callable:

```python
from belegtool_archives import extract_zip_to_structure

def convert_member(content: bytes, name: str):   # return PDF bytes or io.BytesIO; raise on failure
    ...

tree = extract_zip_to_structure(data, convert_member=convert_member)
```

Without `convert_member` only `.pdf` members pass through; every other member degrades to a folder node
`"<name> – nicht importierbar (<reason>)"`.

## Install

```
pip install .                      # from this directory
pip install ".[msg]"               # + .msg support (extract-msg, GPLv3 - see below)
pip install "belegtool-archives @ git+https://github.com/<owner>/belegtool-archives.git@v0.1.0"
pip install -e .[dev] && pytest    # development
```

## Licensing note - `extract-msg` is GPLv3

`.msg` support uses the **optional** dependency `extract-msg` (GPLv3). It is **not** installed by default
(extra `msg`); without it `.msg` files degrade to "nicht importierbar" and everything else works. A build that
bundles it is subject to GPLv3 on that component; the commercial license of the main project cannot cover it
(open question tracked in the main repository's CLAUDE.md, "Findings from 2026-10-18"). Library code here only
uses it through a guarded `try: import extract_msg`.

## License

AGPL-3.0-or-later, see [LICENSE](LICENSE) - the same as the main project. As in the main project
([DigitalerUnterlagenOrdner](https://github.com/tobiasheinrichfaska/DigitalerUnterlagenOrdner)), a
**commercial license** is available for closed-source or proprietary use (contact:
tobias.a.w.heinrich@gmail.com; terms in that repository's `LICENSE_COMMERCIAL.md`). Contributions
are subject to the project's **Contributor License Agreement** (see `CONTRIBUTING.md` of the main
repository): you grant the maintainer a perpetual, worldwide, non-exclusive, royalty-free,
irrevocable right to use, modify and redistribute your contribution under any license, including
commercial licenses.
