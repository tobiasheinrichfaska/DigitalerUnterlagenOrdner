# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""SPDX headers in all Python sources of the three packages (scripts/add_spdx_headers.py).

The insertion logic is unit-tested (shebang / encoding line / ``from __future__`` / BOM / CRLF / idempotence); the real tree is
then checked with the script's own check logic. Covers the three packages AND (since 2026-11-26, released by the owner) the main repo
(core/, services/, formats/, infra/, universal_importer/, tools/, scripts/, tests/, host.py, ...).
"""
import ast
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import add_spdx_headers as sp

ROOT = Path(__file__).resolve().parent.parent
CR = "Copyright (C) 2026 Tobias Heinrich"
H1 = "# SPDX-License-Identifier: AGPL-3.0-or-later"
H2 = "# SPDX-FileCopyrightText: " + CR


def test_copyright_line_is_taken_verbatim_from_license():
    line = sp.copyright_line()
    assert line == CR
    assert line in (ROOT / "LICENSE").read_text(encoding="utf-8")


def test_header_goes_to_the_top():
    assert sp.add_header('"""doc"""\nx = 1\n', CR) == f'{H1}\n{H2}\n"""doc"""\nx = 1\n'


def test_header_respects_shebang_and_encoding_line():
    src = "#!/usr/bin/env python\n# -*- coding: utf-8 -*-\n\"\"\"d\"\"\"\n"
    out = sp.add_header(src, CR)
    assert out == f"#!/usr/bin/env python\n# -*- coding: utf-8 -*-\n{H1}\n{H2}\n\"\"\"d\"\"\"\n"
    only_coding = "# coding=latin-1\nx = 1\n"
    assert sp.add_header(only_coding, CR).splitlines()[:3] == ["# coding=latin-1", H1, H2]


def test_header_stays_valid_before_future_import():
    src = '"""d"""\nfrom __future__ import annotations\nx: int = 1\n'
    out = sp.add_header(src, CR)
    compile(out, "x.py", "exec")  # a __future__ import must still be accepted
    assert ast.get_docstring(ast.parse(out)) == "d"


def test_idempotent_and_byte_stable():
    once = sp.add_header("x = 1\n", CR)
    assert sp.add_header(once, CR) == once


def test_crlf_and_bom_are_preserved():
    out = sp.add_header("﻿x = 1\r\ny = 2\r\n", CR)
    assert out == f"﻿{H1}\r\n{H2}\r\nx = 1\r\ny = 2\r\n"
    assert "\n" not in out.replace("\r\n", "")


def test_empty_file_gets_just_the_header():
    assert sp.add_header("", CR) == f"{H1}\n{H2}\n"


def test_foreign_identifier_is_reported_not_overwritten():
    txt = "# SPDX-License-Identifier: MIT\nx = 1\n"
    assert sp.conflicting_id(txt) == "MIT"
    assert sp.add_header(txt, CR) == txt


def test_every_package_source_has_the_header():
    cr = sp.copyright_line()
    files = sp.source_files(sp.package_roots())
    if not files:
        pytest.skip("packages live in their own repos since 2026-11-27 (belegtool-archives, belegtool-compress, datev-dokab)")
    bad = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        head = "\n".join(text.splitlines()[:15])
        if not (sp.has_header(text) and f"SPDX-FileCopyrightText: {cr}" in head):
            bad.append(f.relative_to(ROOT).as_posix())
    assert not bad, f"{len(bad)} file(s) without SPDX header, run scripts/add_spdx_headers.py: {bad[:10]}"


def test_every_main_repo_source_has_the_header():
    cr = sp.copyright_line()
    files = sp.source_files(sp.main_roots())
    assert len(files) > 100, "main repo sources not found"
    bad = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        head = "\n".join(text.splitlines()[:15])
        if not (sp.has_header(text) and f"SPDX-FileCopyrightText: {cr}" in head):
            bad.append(f.relative_to(ROOT).as_posix())
    assert not bad, f"{len(bad)} file(s) without SPDX header, run scripts/add_spdx_headers.py: {bad[:10]}"


def test_main_roots_cover_every_tracked_python_file():
    tracked = subprocess.run(["git", "ls-files", "*.py"], capture_output=True, text=True, cwd=ROOT).stdout.split()
    covered = {f.relative_to(ROOT).as_posix() for f in sp.source_files(sp.default_roots())}
    missing = [t for t in tracked if t not in covered and not t.startswith(".claude/")]
    assert not missing, f"tracked .py files outside the SPDX scope: {missing[:10]}"


def test_check_mode_cli_agrees():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "add_spdx_headers.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
