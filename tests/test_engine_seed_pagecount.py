# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""SV-4: persisted (seeded) variants must pass the same page-count guard as fresh ones."""
import io

import pikepdf

from core.commands import Compress, apply
from core.engine import RealEngine
from core.model import Document, Node


def _pdf(n):
    p = pikepdf.new()
    for _ in range(n):
        p.add_blank_page()
    b = io.BytesIO()
    p.save(b)
    return b.getvalue()


def test_seeded_variant_with_wrong_page_count_is_dropped():
    src, bad, good = _pdf(3), _pdf(1), _pdf(3)
    leaf = Node(name="a", pdf_length=3, original_data=src)
    doc = Document(root=Node(name="root", children=(leaf,), is_folder=True))
    e = RealEngine()
    e.seed_variants(src, {150: {"jpg": bad, "png": good}})
    assert e.compress(src, 150, "jpg") is None
    assert e.compress(src, 150, "png") == good
    doc2 = apply(doc, Compress(node_id=leaf.id, dpi=150, method="jpg"), e)
    n = [x for x in doc2.root.iter() if not x.is_folder][0]
    assert n.current_data is None or e.page_count(n.current_data) == n.pdf_length
