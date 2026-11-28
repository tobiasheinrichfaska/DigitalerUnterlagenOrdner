# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""HTML optional end tags: real depth must follow the HTML parsing model, not the raw tag count."""
import sys
import types

import pytest

for _m in ("pythoncom", "win32com", "win32com.client"):
    if _m not in sys.modules:
        try:
            __import__(_m)
        except ImportError:
            sys.modules[_m] = types.ModuleType(_m)
if not hasattr(sys.modules["win32com"], "client"):
    sys.modules["win32com"].client = sys.modules["win32com.client"]

from universal_importer.converters import _check_html_complexity

N = 500


@pytest.mark.parametrize("html", [
    "<table>" + "<tr><td>a<td>b" * N + "</table>",
    "<table>" + "<tr><th>a<td>b" * N,
    "<table><thead>" + "<tr><th>a" * N + "<tbody>" + "<tr><td>b" * N + "<tfoot><tr><td>c",
    "<table>" + "<tbody><tr><td>a" * N,
    "<ul>" + "<li>x" * N,
    "<ol>" + "<li><p>x" * N,
    "<dl>" + "<dt>a<dd>b" * N,
    "<select>" + "<option>a" * N,
    "<p>x" * N,
    "<p>x<div>y" * 100 + "<p>a<ul><li>b</ul><table></table><h1>x" * 50,
])
def test_optional_end_tags_do_not_count_as_nesting(html):
    _check_html_complexity(html)


def test_end_tag_of_ancestor_pops_everything_above():
    _check_html_complexity(("<div><table><tr><td>" + "<b>" * 100 + "</div>") * 5)
    _check_html_complexity(("<table><tr><td>a<td>b</table>") * N)


@pytest.mark.parametrize("html", ["<div>" * 5000, "<table><tr><td>" + "<table><tr><td>" * 300, "<ul>" + "<li><ul>" * 300])
def test_real_deep_nesting_still_refused(html):
    with pytest.raises(ValueError):
        _check_html_complexity(html)
