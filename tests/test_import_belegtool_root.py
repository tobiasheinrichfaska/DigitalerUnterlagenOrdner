"""Check: importing a .belegtool must NOT nest its 'root' folder under the app root.

The user flagged that the import logic must avoid pulling a .belegtool's own
`root` node in under a new root. This verifies the stripping is done by
create_wrapper_node (which operates on root.children), independent of how the
tree is rendered.
"""

from formats.pdf_storage import PDFStorage, create_wrapper_node
from formats.pdf_node import PDFNode
from helpers import create_valid_pdf


def _leaf(name):
    n = PDFNode(name, pdf_data=create_valid_pdf(pages=1))
    n.no_compression = True            # deterministic save (no background compress)
    return n


def _save_belegtool(storage: PDFStorage, path) -> str:
    p = str(path)
    storage.save(p)
    return p


def _names(node):
    """Recursively collect all node names in a subtree."""
    out = [node.name]
    for c in node.children:
        out += _names(c)
    return out


def test_belegtool_with_multiple_top_nodes_not_rooted_under_root(tmp_path):
    # Build a storage: a folder with one doc + a standalone doc at top level.
    src = PDFStorage()
    folder = PDFNode("OrdnerA", is_folder=True)
    folder.add_child(_leaf("doc1"))
    src.root.add_child(folder)
    src.root.add_child(_leaf("doc2"))

    path = _save_belegtool(src, tmp_path / "mybeleg.belegtool")

    # Reimport into a NON-empty app storage (the create_wrapper_node path).
    app = PDFStorage()
    app.root.add_child(_leaf("existing"))

    temp = PDFStorage(path)
    # The loaded belegtool has its own "root" folder with the saved top-level nodes.
    assert temp.root.name == "root" and temp.root.is_folder
    assert {c.name for c in temp.root.children} == {"OrdnerA", "doc2"}

    wrapper = create_wrapper_node(temp, path)
    app.root.add_child(wrapper)

    # The belegtool's own "root" node must NOT appear anywhere in the imported tree.
    imported_names = _names(wrapper)
    assert "root" not in imported_names, f"belegtool root leaked: {imported_names}"

    # Multiple top-level nodes -> grouped under a folder named after the FILE.
    assert wrapper.is_folder and wrapper.name == "mybeleg"
    assert {c.name for c in wrapper.children} == {"OrdnerA", "doc2"}

    # The pre-existing node is untouched; the import sits next to it.
    assert {c.name for c in app.root.children} == {"existing", "mybeleg"}


def test_single_node_belegtool_imports_without_root_or_folder(tmp_path):
    src = PDFStorage()
    src.root.add_child(_leaf("nur_ein_dokument"))
    path = _save_belegtool(src, tmp_path / "single.belegtool")

    temp = PDFStorage(path)
    wrapper = create_wrapper_node(temp, path)

    # Single document -> the node itself, no "root", no extra folder.
    assert wrapper.is_folder is False
    assert wrapper.name == "nur_ein_dokument"
