# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Audit R-3 (rotate must not keep document-level JavaScript) / R-4 (InsertNodes replay)."""
import io

import pikepdf

from core.commands import InsertNodes, Rename, apply
from core.engine import RealEngine
from core.model import Document, Node
from core.session import DocumentSession
from helpers import create_valid_pdf


def test_rotate_drops_document_level_javascript():
    p = pikepdf.new()
    p.add_blank_page()
    js = pikepdf.Dictionary(S=pikepdf.Name.JavaScript, JS=pikepdf.String("app.alert(1)"))
    p.Root.OpenAction = js
    p.Root.AA = pikepdf.Dictionary(WC=js)
    p.Root.Names = pikepdf.Dictionary(JavaScript=pikepdf.Dictionary(Names=pikepdf.Array()))
    b = io.BytesIO()
    p.save(b)
    out = pikepdf.open(io.BytesIO(RealEngine().rotate(b.getvalue(), 90)))
    assert "/OpenAction" not in out.Root
    assert "/AA" not in out.Root
    assert "/Names" not in out.Root or "/JavaScript" not in out.Root.Names
    assert int(out.pages[0].Rotate) == 90


def test_insert_nodes_collision_reid_is_replayable():
    a = Node(name="a", id="A", pdf_length=1, original_data=create_valid_pdf(pages=1))
    root = Node(name="root", id="r", is_folder=True, children=(a,))
    s = DocumentSession(Document(root))
    dup = Node(name="dup", id="A", pdf_length=1, original_data=create_valid_pdf(pages=1))
    s.dispatch(InsertNodes("r", (dup,)))
    new = [n.id for n in s.document.root.iter() if n.name == "dup"][0]
    assert new != "A"
    s.dispatch(Rename(new, "renamed"))
    d = s.initial
    for c in s.log:
        d = apply(d, c)
    assert d == s.document
