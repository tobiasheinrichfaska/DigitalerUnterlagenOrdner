# belegtool-archives

Python library (no hard dependencies; `.msg` needs the permissive extra `msg`) that unpacks **ZIP / TAR / TGZ / EML / MSG** containers into a nested
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
- Mail: body + attachments (EML via the standard library; MSG via the own reader `msg_reader.py` on `olefile` + `compressed-rtf`, extra `msg`). An Outlook message attached to a `.msg` is recursed like any nested container.

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

## Licensing note - the `.msg` reader (2026-11-26)

`.msg` support is an own reader (`belegtool_archives/msg_reader.py`, `rtf_deencap.py`) on two **permissive** packages, installed by the
extra `msg`: **`olefile` 0.47 - BSD-2-Clause** (PyPI: `License: BSD`, classifier "BSD License", wheel `LICENSE.txt` = two-clause BSD) and
**`compressed-rtf` 1.0.7 - MIT** (PyPI: `license_expression: MIT`). They replace `extract-msg` (GPLv3) and its dependency RTFDE (LGPLv3),
which are no longer imported, listed or bundled (guarded by `tests/test_no_gpl_msg_deps.py` in the main repository). Without the extra,
`.msg` files degrade to "nicht importierbar" and everything else works.

Behaviour notes (pinned in `tests/test_msg_parity.py` / `tests/test_msg_reader.py`): body priority HTML (0x1013, bytes as stored) > HTML
unwrapped from an encapsulated RTF (`\fromhtml1`, simplified de-encapsulation, no RTFDE) > plain text turned into minimal HTML > raw RTF as
`.rtf`; an ordinary (non-encapsulated) RTF is NOT converted. Deliberate deviations from extract-msg: embedded messages are recursed (extract-msg
degraded them), an attachment without data no longer fails the whole mail, unreadable RTF/strings degrade instead of raising.
**Tested with synthetic files only (`tests/msg_fixture.py`) - never with real Outlook mails.**

## License

AGPL-3.0-or-later, see [LICENSE](LICENSE) and [COPYING](COPYING) (full AGPL text) - the same as the main project. As in the main project
([DigitalerUnterlagenOrdner](https://github.com/tobiasheinrichfaska/DigitalerUnterlagenOrdner)), a
**commercial license** is available for closed-source or proprietary use (contact:
tobias.a.w.heinrich@gmail.com; terms in that repository's `LICENSE_COMMERCIAL.md`). Contributions
are subject to the project's **Contributor License Agreement** (see `CONTRIBUTING.md` of the main
repository): you grant the maintainer a perpetual, worldwide, non-exclusive, royalty-free,
irrevocable right to use, modify and redistribute your contribution under any license, including
commercial licenses. The full wording of the CLA is part of this package: [`CONTRIBUTING.md`](CONTRIBUTING.md).
