# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""PF-4 equivalence oracle: the export (TOC/index/links/bookmarks/split) must keep its
structure — per-page text, link destinations and outline tree — when `_assemble` is
optimised. ORACLE below was recorded with the pre-optimisation code (sha256 of the
extracted structure); a change in produced PDF semantics changes the digest."""
import hashlib
import json
import random
import time

import fitz
import pikepdf
import pytest

from formats.pdf_node import PDFNode
from formats.toc_export import export_pdf, export_pdf_split_with_toc


def _pdf(n, tag):
    d = fitz.open()
    for i in range(n):
        d.new_page(width=300, height=300).insert_text((40, 60), f"{tag} p{i}")
    b = d.tobytes()
    d.close()
    return b


def _tree(seed, n_leaves):
    rnd = random.Random(seed)
    root_children, folders = [], []
    for i in range(n_leaves):
        leaf = PDFNode(name=f"Doc{i}", pdf_data=_pdf(rnd.randint(1, 3), f"L{i}"))
        leaf.pdf_length = len(pikepdf.open(__import__("io").BytesIO(leaf.current_pdf_data)).pages)
        if rnd.random() < 0.5:
            leaf.tags = [rnd.choice(["alpha", "beta", "gamma"])]
        if folders and rnd.random() < 0.6:
            rnd.choice(folders).add_child(leaf)
        else:
            if rnd.random() < 0.3:
                f = PDFNode(name=f"Ordner{i}", is_folder=True)
                if rnd.random() < 0.5:
                    f.tags = ["beta"]
                f.add_child(leaf)
                folders.append(f)
                root_children.append(f)
            else:
                root_children.append(leaf)
    return root_children


def _structure(path):
    out = {"pages": [], "links": [], "outline": None}
    with pikepdf.open(path) as pdf:
        pages = list(pdf.pages)
        idx = {p.objgen: i for i, p in enumerate(pages)}
        import pypdf
        r = pypdf.PdfReader(path)
        for i, p in enumerate(pages):
            out["pages"].append(r.pages[i].extract_text())
            for a in p.get("/Annots", []):
                d = a.get("/Dest")
                if d is not None:
                    out["links"].append((i, [round(float(x), 2) for x in a.Rect], idx[d[0].objgen], str(d[1])))

        def walk(items):
            res = []
            for it in items:
                d = it.destination
                res.append((it.title, idx[d[0].objgen] if d is not None else None, walk(it.children)))
            return res
        with pdf.open_outline() as ol:
            out["outline"] = walk(ol.root)
    return out


def _digest(s):
    return hashlib.sha256(json.dumps(s, sort_keys=True).encode()).hexdigest()


VARIANTS = [
    ("full", {}),
    ("notoc", {"toc": False}),
    ("nolinks", {"toc_links": False, "index_links": False}),
    ("nobm", {"bookmarks": False}),
    ("noindex", {"index": False}),
]
ORACLE = {
    "1-full": "fc9754a53b4dc2eae8114dc2596e676d0122d5248cfe794d7ecd876f24f5cc32",
    "1-notoc": "286716a2b31fedb95460f2f2e6c2871c70879e675360ac4c29150fd6b2bea598",
    "1-nolinks": "f2d748680f24e4a6e123199a12d9ce889d741e9a52b9b54a6d5ff34f833edec7",
    "1-nobm": "b66c6f9160d8d46e655de448c3c9e298bbd8a85dab4193fd173d601bccdbf25a",
    "1-noindex": "1b13275c9a3c99f0ddd1016d9aedc98638dd7ada7780b48a565249aa7cc0acb3",
    "1-split": "2c24ac7db4cd8527ca2eb9253fb8c5276469918942c37b4a235c419bceed8289",
    "2-full": "a9125d196e440110017af305077909921297d0d93959479a968048c15a473f0a",
    "2-notoc": "a418eeac5a5089202d1ac5c4d91b55fa862810176887b56bb1a123406142a95b",
    "2-nolinks": "96c7139b19a9ca68213168a08acbbd0cb564d5e68e3d512e260211a54bcee2f5",
    "2-nobm": "0aa95f6eb0c8f1560ba1db903fcc7acd0e8f5bba36788ae5d3fb50a34a77d4c7",
    "2-noindex": "41467f3252f9420036cc4e0a720c8b78baa60d2c1f862247ce562f0eb05111d8",
    "2-split": "86cfe30b2a6ab32e072acc1b2fe062f25835c432a7bd1b880193baf2127e3b1f"
}


def _compute(tmp_path):
    res = {}
    for seed, n in ((1, 12), (2, 40)):
        for name, opt in VARIANTS:
            p = str(tmp_path / f"o_{seed}_{name}.pdf")
            export_pdf(_tree(seed, n), p, opt)
            res[f"{seed}-{name}"] = _digest(_structure(p))
        base = str(tmp_path / f"s_{seed}.pdf")
        paths = export_pdf_split_with_toc(_tree(seed, n), base, 10)
        res[f"{seed}-split"] = _digest([_structure(q) for q in (paths if isinstance(paths, list) else [])] or paths)
    return res


def test_export_structure_equals_oracle(tmp_path):
    assert _compute(tmp_path) == ORACLE


def test_export_scales_linearly(tmp_path):
    # Ratio-based and noise-robust: the minimum of 3 repetitions per size (interleaved, so a
    # load burst hits both sizes) filters CPU-load spikes; a ~linear algorithm gives
    # time(2n)/time(n) ~ 2, a quadratic one ~ 4.
    pdf = _pdf(1, "x")

    def run(n):
        nodes = [PDFNode(name=f"d{i}", pdf_data=pdf) for i in range(n)]
        for x in nodes:
            x.pdf_length = 1
        t = time.perf_counter()
        export_pdf(nodes, str(tmp_path / f"b{n}.pdf"))
        return time.perf_counter() - t

    run(100)
    n = 1000
    a, b = [], []
    for _ in range(3):
        a.append(run(n))
        b.append(run(2 * n))
    t1, t2 = min(a), min(b)
    assert t2 / t1 < 3.2, f"super-linear export: t({n})={t1:.3f}s t({2 * n})={t2:.3f}s"
