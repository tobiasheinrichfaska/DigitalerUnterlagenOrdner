"""Honor zip/tar subfolders as real folder nodes (not a path embedded in the leaf
name). A member ``rechnungen/2024/beleg.pdf`` becomes
``DIR rechnungen > DIR 2024 > PDF beleg.pdf``; siblings merge under shared folders.
Fixes the zip path-in-name and the tar dropped-to-basename behaviours at once, and
composes with the #12 nested-container recursion.
"""
import io
import tarfile
import zipfile

from universal_importer import archives
from helpers import create_valid_pdf


def _zip_bytes(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, payload in members.items():
            z.writestr(name, payload)
    return buf.getvalue()


def _tar_bytes(members):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))
    return buf.getvalue()


def _byname(struct, name):
    return next((n for n in struct if n["name"] == name), None)


def _names(struct):
    return [n["name"] for n in struct]


def _walk(struct):
    for n in struct:
        yield n
        if "children" in n:
            yield from _walk(n["children"])


# ------------------------------------------------------------------- zip
def test_zip_subfolder_becomes_a_folder_node():
    pdf = create_valid_pdf(pages=1)
    struct = archives.extract_zip_to_structure(_zip_bytes({"ordner/beleg.pdf": pdf}))
    folder = _byname(struct, "ordner")
    assert folder is not None and "children" in folder
    leaf = _byname(folder["children"], "beleg.pdf")            # basename, NOT "ordner/beleg.pdf"
    assert leaf is not None and leaf["content"].getvalue().startswith(b"%PDF")


def test_zip_deep_path_nests_each_level():
    pdf = create_valid_pdf(pages=1)
    struct = archives.extract_zip_to_structure(_zip_bytes({"a/b/c/doc.pdf": pdf}))
    a = _byname(struct, "a")
    b = _byname(a["children"], "b")
    c = _byname(b["children"], "c")
    assert _byname(c["children"], "doc.pdf") is not None


def test_zip_siblings_merge_under_one_folder():
    pdf = create_valid_pdf(pages=1)
    struct = archives.extract_zip_to_structure(_zip_bytes({
        "ordner/a.pdf": pdf, "ordner/b.pdf": pdf, "top.pdf": pdf,
    }))
    assert _byname(struct, "top.pdf") is not None              # root-level leaf stays at root
    folder = _byname(struct, "ordner")
    assert sorted(_names(folder["children"])) == ["a.pdf", "b.pdf"]   # one folder, both leaves


def test_zip_same_basename_in_different_folders_stays_distinct():
    one, three = create_valid_pdf(pages=1), create_valid_pdf(pages=3)
    struct = archives.extract_zip_to_structure(_zip_bytes({"d1/x.pdf": one, "d2/x.pdf": three}))
    x1 = _byname(_byname(struct, "d1")["children"], "x.pdf")
    x2 = _byname(_byname(struct, "d2")["children"], "x.pdf")
    assert x1["content"].getvalue() == one and x2["content"].getvalue() == three


def test_zip_nested_container_under_a_subfolder():
    pdf = create_valid_pdf(pages=1)
    inner = _zip_bytes({"doc.pdf": pdf})
    struct = archives.extract_zip_to_structure(_zip_bytes({"ordner/inner.zip": inner}))
    folder = _byname(struct, "ordner")
    nested = _byname(folder["children"], "inner.zip")          # recursed container, basename
    assert nested is not None and "children" in nested
    assert _byname(nested["children"], "doc.pdf") is not None


# ------------------------------------------------------------------- tar
def test_tar_subfolders_nest_and_keep_distinct_basenames():
    pdf = create_valid_pdf(pages=1)
    struct = archives.extract_tar_to_structure(_tar_bytes({
        "d1/x.pdf": pdf, "d2/x.pdf": pdf, "root.pdf": pdf,
    }))
    assert _byname(struct, "root.pdf") is not None
    assert _byname(_byname(struct, "d1")["children"], "x.pdf") is not None
    assert _byname(_byname(struct, "d2")["children"], "x.pdf") is not None
    # the two x.pdf are NOT collapsed onto one root-level node any more
    assert "x.pdf" not in _names(struct)
