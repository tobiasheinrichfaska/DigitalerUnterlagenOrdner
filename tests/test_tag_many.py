"""#7 — multi-select tagging: TagMany adds/removes ONE tag across many nodes as a
single undoable step, preserving each node's other tags. (SetTags replaces a whole
set and only ever targeted one node.)
"""
from core.commands import apply, command_from_dict, command_to_dict
from core.model import Document, Node


def _do(doc, cmd_dict):
    return apply(doc, command_from_dict(cmd_dict), engine=None)


def _leaf(nid, tags=()):
    return Node(name=nid, id=nid, pdf_length=1, tags=tuple(tags))


def _doc(*leaves):
    return Document(Node(name="root", id="r", is_folder=True, children=tuple(leaves)))


def test_add_tag_to_many():
    doc = _doc(_leaf("a"), _leaf("b"))
    out = _do(doc, {"type": "TagMany", "node_ids": ["a", "b"], "tag": "Steuer", "add": True})
    assert out.find("a").tags == ("Steuer",)
    assert out.find("b").tags == ("Steuer",)


def test_add_preserves_existing_other_tags_and_is_idempotent():
    doc = _doc(_leaf("a", ["2024"]), _leaf("b", ["Steuer"]))
    out = _do(doc, {"type": "TagMany", "node_ids": ["a", "b"], "tag": "Steuer", "add": True})
    assert out.find("a").tags == ("2024", "Steuer")   # appended, order kept
    assert out.find("b").tags == ("Steuer",)           # already present → unchanged (no dup)


def test_remove_tag_from_many_keeps_other_tags():
    doc = _doc(_leaf("a", ["2024", "Steuer"]), _leaf("b", ["Steuer"]), _leaf("c", ["x"]))
    out = _do(doc, {"type": "TagMany", "node_ids": ["a", "b", "c"], "tag": "Steuer", "add": False})
    assert out.find("a").tags == ("2024",)
    assert out.find("b").tags == ()
    assert out.find("c").tags == ("x",)                # didn't have it → untouched


def test_dedupes_ids_and_skips_missing():
    doc = _doc(_leaf("a"))
    out = _do(doc, {"type": "TagMany", "node_ids": ["a", "a", "gone"], "tag": "T", "add": True})
    assert out.find("a").tags == ("T",)                # added once, no crash on 'gone'


def test_empty_or_whitespace_tag_is_a_noop():
    doc = _doc(_leaf("a", ["keep"]))
    for bad in ("", "   "):
        out = _do(doc, {"type": "TagMany", "node_ids": ["a"], "tag": bad, "add": True})
        assert out.find("a").tags == ("keep",)


def test_works_on_folders_too():
    folder = Node(name="f", id="f", is_folder=True, children=())
    doc = Document(Node(name="root", id="r", is_folder=True, children=(folder,)))
    out = _do(doc, {"type": "TagMany", "node_ids": ["f"], "tag": "Ordnertag", "add": True})
    assert out.find("f").tags == ("Ordnertag",)


def test_tag_is_trimmed():
    doc = _doc(_leaf("a"))
    out = _do(doc, {"type": "TagMany", "node_ids": ["a"], "tag": "  Steuer  ", "add": True})
    assert out.find("a").tags == ("Steuer",)


def test_wire_roundtrip():
    cmd = command_from_dict({"type": "TagMany", "node_ids": ["a", "b"], "tag": "T", "add": False})
    assert cmd.node_ids == ("a", "b") and cmd.tag == "T" and cmd.add is False
    d = command_to_dict(cmd)
    # round-trips back to an equivalent command
    again = command_from_dict(d)
    assert again.node_ids == cmd.node_ids and again.tag == cmd.tag and again.add == cmd.add
