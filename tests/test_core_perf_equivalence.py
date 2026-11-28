# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Perf-audit PF-1/PF-2/PF-3: the fast paths must behave EXACTLY like the old naive ones.

The reference implementations below are the pre-optimisation handler bodies (one tree
rebuild per id) and the pre-optimisation linear-scan ``variants_for``/``evaluated``.
Seeded random documents + commands are applied to both and compared structurally.
"""
import gc
import hashlib
import random
import time

import pytest

from core import commands as C
from core.commands import CommandError, apply
from core.engine import RealEngine
from core.model import Document, Node, STATUSES


# --------------------------------------------------------------------------- refs
def ref_tag_many(doc, cmd):
    tag = (cmd.tag or "").strip()
    if not tag:
        return doc
    for nid in dict.fromkeys(cmd.node_ids):
        node = doc.find(nid)
        if node is None:
            continue
        cur = tuple(node.tags or ())
        if cmd.add:
            if tag not in cur:
                doc = doc.update_node(nid, tags=cur + (tag,))
        elif tag in cur:
            doc = doc.update_node(nid, tags=tuple(t for t in cur if t != tag))
    return doc


def ref_set_status_many(doc, cmd):
    if cmd.status not in STATUSES:
        raise CommandError(f"invalid status: {cmd.status!r}")
    for nid in dict.fromkeys(cmd.node_ids):
        if doc.find(nid) is not None:
            doc = C._apply_status(doc, nid, cmd.status)
    return doc


def ref_set_no_gain(doc, cmd):
    for nid in dict.fromkeys(cmd.node_ids):
        node = doc.find(nid)
        if node is not None and not node.is_folder and not node.compression_no_gain:
            doc = doc.update_node(nid, compression_no_gain=True)
    return doc


def ref_delete_many(doc, cmd):
    ids = [i for i in dict.fromkeys(cmd.node_ids)
           if doc.find(i) is not None and doc.parent_of(i) is not None]
    id_set = set(ids)
    pmap = C._parent_id_map(doc.root)
    for i in ids:
        pid = pmap.get(i)
        while pid is not None:
            if pid in id_set:
                raise CommandError("Gemischte Auswahl: ein Ordner und ein darin liegendes Element sind beide ausgewählt.")
            pid = pmap.get(pid)
    for i in ids:
        doc = doc.remove_node(i)
    return doc


def ref_move_many(doc, cmd):
    C._require_folder(doc, cmd.new_parent_id)
    ids = C._top_level_ids(doc, list(cmd.node_ids))
    if not ids:
        return doc
    nodes = C._validate_move_targets(doc, ids, cmd.new_parent_id)
    parent = doc.find(cmd.new_parent_id)
    raw = len(parent.children) if cmd.index is None else max(0, min(cmd.index, len(parent.children)))
    moved = set(ids)
    before = sum(1 for i, c in enumerate(parent.children) if c.id in moved and i < raw)
    at = raw - before
    for nid in ids:
        doc = doc.remove_node(nid)
    for offset, node in enumerate(nodes):
        doc = doc.insert_child(cmd.new_parent_id, node, at + offset)
    return doc


def ref_group(doc, cmd):
    C._require_folder(doc, cmd.parent_id)
    ids = C._top_level_ids(doc, list(cmd.node_ids))
    if not ids:
        raise CommandError("Nichts zu gruppieren.")
    C._validate_move_targets(doc, ids, cmd.parent_id)
    folder = Node(name=cmd.name or "Neue Gruppe", is_folder=True,
                  **({"id": cmd.new_id} if cmd.new_id else {}))
    fid = folder.id
    doc = doc.insert_child(cmd.parent_id, folder, cmd.index)
    for nid in ids:
        doc = doc.move_node(nid, fid, None)
    return doc


REFS = {
    C.TagMany: ref_tag_many, C.SetStatusMany: ref_set_status_many,
    C.SetNoGain: ref_set_no_gain, C.DeleteMany: ref_delete_many,
    C.MoveMany: ref_move_many, C.GroupIntoFolder: ref_group,
}


# --------------------------------------------------------------------------- gen
def rand_doc(rnd, n_nodes):
    counter = [0]

    def mk(depth):
        counter[0] += 1
        i = counter[0]
        if depth < 4 and (depth == 0 or rnd.random() < 0.35):
            kids = tuple(mk(depth + 1) for _ in range(rnd.randint(0, 5)))
            return Node(name=f"F{i}", is_folder=True, id=f"id{i}", children=kids,
                        tags=tuple(rnd.sample(["a", "b", "c"], rnd.randint(0, 2))))
        return Node(name=f"L{i}", id=f"id{i}", pdf_length=1,
                    status=rnd.choice(list(STATUSES)),
                    tags=tuple(rnd.sample(["a", "b", "c"], rnd.randint(0, 2))),
                    compression_no_gain=rnd.random() < 0.2)
    while True:
        root = mk(0)
        if sum(1 for _ in root.iter()) >= min(n_nodes, 8):
            return Document(root)
        counter[0] = 0


def rand_cmd(rnd, doc):
    ids = [n.id for n in doc.root.iter()]
    pick = lambda: tuple(rnd.choice(ids + ["missing"]) for _ in range(rnd.randint(0, 8)))
    folders = [n.id for n in doc.root.iter() if n.is_folder]
    kind = rnd.choice(list(REFS))
    if kind is C.TagMany:
        return C.TagMany(pick(), rnd.choice(["a", "b", "z", " ", "q"]), rnd.random() < 0.5)
    if kind is C.SetStatusMany:
        return C.SetStatusMany(pick(), rnd.choice(list(STATUSES) + ["bogus"]))
    if kind is C.SetNoGain:
        return C.SetNoGain(pick())
    if kind is C.DeleteMany:
        return C.DeleteMany(pick())
    if kind is C.MoveMany:
        return C.MoveMany(pick(), rnd.choice(folders + ["missing"]),
                          rnd.choice([None, 0, 1, 2, 5, 99, -3]))
    return C.GroupIntoFolder(pick(), rnd.choice(folders + ["missing"]),
                             name=rnd.choice(["G", ""]), new_id=f"grp{rnd.randrange(10**9)}",
                             index=rnd.choice([None, 0, 3, 99]))


def outcome(fn, doc, cmd):
    try:
        return ("ok", fn(doc, cmd))
    except Exception as e:  # noqa: BLE001 - compare type + message
        return ("err", type(e).__name__, str(e))


@pytest.mark.parametrize("seed", range(40))
def test_multi_node_commands_match_naive_reference(seed):
    rnd = random.Random(seed)
    doc = rand_doc(rnd, 40)
    for _ in range(25):
        cmd = rand_cmd(rnd, doc)
        want = outcome(REFS[type(cmd)], doc, cmd)
        got = outcome(lambda d, c: apply(d, c), doc, cmd)
        assert got == want, (seed, cmd)
        if got[0] == "ok":
            doc = got[1]


# --------------------------------------------------------------------------- perf
def _big(n, per=20):
    folders = []
    for f in range((n + per - 1) // per):
        folders.append(Node(name=f"F{f}", is_folder=True, children=tuple(
            Node(name=f"b{f}.{i}", pdf_length=1) for i in range(min(per, n - f * per)))))
    return Document(Node(name="d", is_folder=True, children=tuple(folders)))


def test_multi_node_commands_are_not_quadratic():
    doc = _big(4000)
    leaves = [n.id for n in doc.root.iter() if not n.is_folder]
    tgt = doc.root.children[-1].id
    k = tuple(leaves[:2000])
    for cmd in (C.TagMany(k, "x", True), C.SetStatusMany(k, "erfasst"),
                C.DeleteMany(k), C.MoveMany(k, tgt, 0),
                C.GroupIntoFolder(k, doc.root.id, "G")):
        t = time.perf_counter()
        apply(doc, cmd)
        dt = time.perf_counter() - t
        assert dt < 1.0, (type(cmd).__name__, dt)  # was 2-4 s each at k=n/2, n=4000


# --------------------------------------------------------------------------- engine
class RefIndex:
    """pre-optimisation variants_for/evaluated over the engine's raw layers."""
    def __init__(self, eng):
        self.eng = eng

    def variants_for(self, b):
        digest = hashlib.sha1(b).digest()
        out = {}
        items = list(self.eng._mcache.items()) + list(self.eng._persisted.items())
        for (d, dpi), result in items:
            if d == digest and result:
                out.setdefault(dpi, {}).update(result)
        return out

    def evaluated(self, b):
        digest = hashlib.sha1(b).digest()
        return (any(d == digest for (d, _x) in self.eng._mcache)
                or any(d == digest for (d, _x) in self.eng._persisted))


@pytest.mark.parametrize("seed", range(15))
def test_variant_index_matches_linear_scan(seed):
    rnd = random.Random(seed)
    eng = RealEngine()
    ref = RefIndex(eng)
    blobs = [b"%PDF-" + bytes([i]) * 50 for i in range(30)]
    for _ in range(80):
        b = rnd.choice(blobs)
        op = rnd.random()
        if op < 0.5:
            eng.seed_variants(b, {rnd.choice([50, 100, 150]): rnd.choice(
                [{"jpg": b"x", "png": b"yy"}, {"jpg": b"z"}, {}])})
        elif op < 0.7:
            with eng._mcache_lock:
                eng._mcache[(hashlib.sha1(b).digest(), rnd.choice([50, 150]))] = rnd.choice(
                    [{}, {"jpg": b"m"}])
        elif op < 0.85:
            closed = rnd.sample(blobs, 3)
            live = rnd.sample(blobs, 3)
            eng.prune_persisted(closed, live)
        for probe in blobs:
            assert eng.variants_for(probe) == ref.variants_for(probe)
            assert eng.evaluated(probe) == ref.evaluated(probe)


def test_variant_lookup_is_constant_time_per_leaf():
    eng = RealEngine()
    blobs = [b"%%PDF-%d" % i + b"x" * 40 for i in range(3000)]
    for b in blobs:
        eng.seed_variants(b, {150: {"jpg": b"v"}})
    t = time.perf_counter()
    for b in blobs:
        eng.variants_for(b)
        eng.evaluated(b)
    assert time.perf_counter() - t < 0.5  # linear scan: ~3000*3000 tuple compares (seconds)


def test_digest_is_not_recomputed_for_documents_beyond_256_leaves(monkeypatch):
    import core.engine as engine_mod
    calls = []
    orig = engine_mod.hashlib.sha1
    monkeypatch.setattr(engine_mod.hashlib, "sha1", lambda b: (calls.append(1), orig(b))[1])
    eng = RealEngine()
    blobs = [b"%%PDF-%d" % i + bytes(100) for i in range(1000)]
    for _ in range(3):
        for b in blobs:
            eng.variants_for(b)
    assert len(calls) == 1000  # cyclic walk over >256 distinct objects hashes each ONCE


def test_digest_memo_pinned_bytes_are_bounded_without_refcounts():
    eng = RealEngine()
    for i in range(40):
        eng._digest(bytes([i]) * (4 * 1024 * 1024) + b"%d" % i)  # 160 MB of dead bytes
    assert eng._dlive_bytes <= 64 * 1024 * 1024
    assert sum(len(e[0]) for e in eng._dlive.values()) == eng._dlive_bytes


def test_digest_memo_budget_follows_live_bytes_hint(monkeypatch):
    import core.engine as engine_mod
    calls = []
    orig = engine_mod.hashlib.sha1
    monkeypatch.setattr(engine_mod.hashlib, "sha1", lambda b: (calls.append(1), orig(b))[1])
    eng = RealEngine()
    blobs = [b"%d" % i + bytes(50_000) for i in range(2000)]  # ~100 MB live
    eng.set_live_bytes(sum(map(len, blobs)))
    for _ in range(3):
        for b in blobs:
            eng._digest(b)
    assert len(calls) == 2000
    t = time.perf_counter()
    for b in blobs:
        eng._digest(b)
    assert time.perf_counter() - t < 0.03


def test_coreapi_wires_live_bytes_hint_so_big_docs_hash_once(monkeypatch):
    """PF-1 follow-up: >64 MiB of leaf sources must not be re-hashed on every command."""
    import core.engine as engine_mod
    from core.api import CoreApi
    from core.commands import InsertNodes
    calls = []
    orig = engine_mod.hashlib.sha1
    monkeypatch.setattr(engine_mod.hashlib, "sha1", lambda b: (calls.append(1), orig(b))[1])
    api = CoreApi()
    sid = api.open()["session"]
    leaves = tuple(Node(name="d%d" % i, pdf_length=1, no_compression=True,
                        original_data=b"%%PDF-%d" % i + bytes(50_000))
                   for i in range(2000))
    api._sessions[sid].dispatch(InsertNodes(parent_id=api._sessions[sid].document.root.id,
                                            nodes=leaves, index=None))
    target = leaves[0].id
    for k in range(5):
        t = time.perf_counter()
        assert api.dispatch(sid, {"type": "Rename", "node_id": target, "name": "n%d" % k})["ok"]
        # the deterministic property is the hash count below; the wall-clock bound is only a
        # coarse sanity limit (a cold re-hash of 100 MB takes several times this under load)
        assert time.perf_counter() - t < 1.0
    assert len(calls) <= 2000
    big = api._engine._dlive_budget
    assert big >= 2 * 100_000_000
    api.close_session(sid)
    assert api._engine._dlive_budget < big
