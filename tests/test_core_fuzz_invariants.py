# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Seeded fuzz of core model/commands/session: random command sequences, invariants
checked after every step (unique ids, acyclic, page_count == pdf_length, undo/redo,
replay, dict + .belegtool round-trips)."""

import io
import os
import random

import pikepdf
import pytest

from core.bridge import load_belegtool, save_belegtool
from core.commands import (
    AddFolder, CommandError, DeleteMany, Delete, GroupIntoFolder, InsertNodes, Merge, Move,
    MoveMany, Rename, Rotate, SetCollapsed, SetStatus, SetTags, Split, SplitInto, TagMany,
    apply_all,
)
from core.engine import RealEngine
from core.model import Document, Node
from core.session import DocumentSession

SEQUENCES = int(os.environ.get("FUZZ_SEQUENCES", "40"))
STEPS = int(os.environ.get("FUZZ_STEPS", "25"))
TAGS = ["a", "b", "c"]
STATUSES = ["", "zu erfassen", "erfasst", "vorjahreswert"]


def _pdf(n):
    pdf = pikepdf.Pdf.new()
    for _ in range(n):
        pdf.add_blank_page(page_size=(100, 100))
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


PDFS = {n: _pdf(n) for n in (1, 2, 3)}


def _leaf(rng, name):
    n = rng.choice((1, 2, 3))
    return Node(name=name, pdf_length=n, original_data=PDFS[n])


def _all(doc):
    return list(doc.root.iter())


def _nobytes(d):
    d = dict(d)
    d.pop("has_source", None)
    d["children"] = [_nobytes(c) for c in d["children"]]
    return d


def _check(doc, engine):
    nodes = _all(doc)
    ids = [n.id for n in nodes]
    assert len(ids) == len(set(ids)), "duplicate ids"
    seen = set()

    def walk(n):  # acyclic: no node object is its own ancestor (frozen tree => depth bound)
        assert id(n) not in seen
        seen.add(id(n))
        for c in n.children:
            walk(c)
        seen.discard(id(n))
    walk(doc.root)
    for n in nodes:
        if n.is_folder:
            assert n.original_data is None and n.current_data is None
        else:
            assert not n.children
            data = n.current_data or n.original_data
            assert data, f"leaf {n.name} without bytes"
            assert engine.page_count(data) == n.pdf_length, f"page_count != pdf_length for {n.name}"
    # folders: pdf_length stays 0 in the model (aggregate is a view concern)
    return doc.to_dict()


def _gen(rng, doc, counter):
    nodes = _all(doc)
    non_root = nodes[1:]
    folders = [n for n in nodes if n.is_folder]
    leaves = [n for n in nodes if not n.is_folder]
    pick = lambda xs: rng.choice(xs)
    k = rng.randrange(14)
    counter[0] += 1
    nm = f"n{counter[0]}"
    if k == 0 or not non_root:
        return AddFolder(pick(folders).id, nm, rng.choice([None, 0, 1, 99]), new_id="F" + nm)
    if k in (1, 2):
        return InsertNodes(pick(folders).id, tuple(_leaf(rng, nm + str(i)) for i in range(rng.randint(1, 2))),
                           rng.choice([None, 0, 1]))
    if k == 3:  # re-import of an existing subtree (same ids)
        sub = pick(non_root)
        return InsertNodes(pick(folders).id, (sub,), rng.choice([None, 0]))
    if k == 4:
        return Move(pick(non_root).id, pick(folders).id, rng.choice([None, 0, 1, 5]))
    if k == 5:
        ids = tuple(n.id for n in rng.sample(non_root, min(len(non_root), rng.randint(1, 3))))
        return MoveMany(ids, pick(folders).id, rng.choice([None, 0, 1, 5]))
    if k == 6:
        return rng.choice([Delete(pick(non_root).id),
                           DeleteMany(tuple(n.id for n in rng.sample(non_root, min(len(non_root), 2))))])
    if k == 7:
        return rng.choice([Rename(pick(nodes).id, nm), SetStatus(pick(nodes).id, pick(STATUSES))])
    if k == 8:
        return rng.choice([SetTags(pick(nodes).id, tuple(rng.sample(TAGS, rng.randint(0, 2)))),
                           TagMany(tuple(n.id for n in rng.sample(nodes, min(len(nodes), 3))), pick(TAGS), rng.random() < .5)])
    if k == 9 and leaves:
        return Merge(tuple(n.id for n in rng.sample(leaves, min(len(leaves), rng.randint(2, 3)))))
    if k == 10 and leaves:
        return rng.choice([Split(pick(leaves).id), SplitInto(pick(leaves).id, rng.randint(1, 2), rng.random() < .5)])
    if k == 11 and leaves:
        return Rotate(pick(leaves).id, pick(["left", "right", "180"]))
    if k == 12:
        return SetCollapsed(pick(folders).id, rng.random() < .5)
    if k == 13:
        return GroupIntoFolder(tuple(n.id for n in rng.sample(non_root, min(len(non_root), 2))), pick(folders).id, nm, new_id="G" + nm)
    return Rename(pick(nodes).id, nm)


def run_sequence(seed, tmp_path=None, steps=STEPS):
    rng = random.Random(seed)
    engine = RealEngine()
    root = Node(name="root", id="root", is_folder=True, children=(
        Node(name="f0", id="f0", is_folder=True, children=(_leaf(rng, "l0"), _leaf(rng, "l1"))),
        _leaf(rng, "l2"),
    ))
    init = Document(root)
    s = DocumentSession(init, engine)
    counter = [0]
    states = [init]
    cmds = []
    _check(init, engine)
    for step in range(steps):
        cmd = _gen(rng, s.document, counter)
        before = s.document
        try:
            after = s.dispatch(cmd)
        except (CommandError, KeyError, ValueError):
            assert s.document is before, "failed command mutated session"
            continue
        cmds.append(cmd)
        if after is not before:
            states.append(after)
        d = _check(after, engine)
        assert _nobytes(Document.from_dict(d).to_dict()) == _nobytes(d), "to_dict/from_dict"
        # undo/redo
        if after is not before:
            s.undo()
            assert s.document is before, "undo"
            s.redo()
            assert s.document is after and s.document.to_dict() == d, "redo"
    final = s.document.to_dict()
    # replay (Split/Merge mint random ids, so later commands can't be replayed by id)
    if not any(isinstance(c, (Split, SplitInto, Merge)) for c in s.log):
        rep = apply_all(init, s.log, engine)
        assert rep.to_dict() == s.document.to_dict(), "replay"
    # bridge roundtrip
    if tmp_path is not None:
        p = tmp_path / f"f{seed}.belegtool"
        save_belegtool(s.document, p)
        back = load_belegtool(p)
        want, got = s.document.to_dict(), back.to_dict()
        # known limitation: the root's own name/tags/status are not persisted in .belegtool
        for k in ("name", "tags", "status"):
            want[k] = got[k]
        assert got == want, "belegtool roundtrip"
    # full undo
    while s.can_undo():
        s.undo()
    assert s.document == init, "full undo"
    while s.can_redo():
        s.redo()
    assert s.document.to_dict() == final, "full redo"


@pytest.mark.parametrize("chunk", range(4))
def test_fuzz_core_invariants(chunk, tmp_path):
    per = SEQUENCES // 4
    for seed in range(chunk * per, (chunk + 1) * per):
        try:
            run_sequence(seed, tmp_path if seed % 5 == 0 else None)
        except AssertionError as e:
            raise AssertionError(f"seed {seed}: {e}") from e
