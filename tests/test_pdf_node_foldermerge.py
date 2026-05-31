import json
import pytest
from pathlib import Path
from pdf_node import PDFNode
from helpers import create_valid_pdf, wait_for_real_preview

BASE = Path(__file__).parent / "data"
INPUT = BASE / "input"
EXPECTED = BASE / "expected"
OUTPUT = BASE / "output"

EXPECTED.mkdir(parents=True, exist_ok=True)
OUTPUT.mkdir(parents=True, exist_ok=True)
INPUT.mkdir(parents=True, exist_ok=True)

def build_folder_node_from_input(prefix: str) -> PDFNode:
    files = sorted(INPUT.glob(f"*{prefix}*.pdf"))
    assert files, f"Keine Eingabedateien mit '{prefix}' im Namen gefunden."
    folder = PDFNode(name=f"folder_{prefix}", is_folder=True)
    for f in files:
        node = PDFNode.from_pdf(f.name, f.read_bytes())
        # from_pdf kicks off background compression. Wait for it to settle so the
        # folder's aggregated current_pdf_data (and the is_compressed/dpi flags in
        # to_dict) are deterministic — otherwise the byte-exact golden master is
        # racy depending on whether compression finished before the merge.
        wait_for_real_preview(node)
        folder.add_child(node)
    return folder

def test_folder_merge_combinations_from_input():
    f1 = build_folder_node_from_input("compress")
    f2 = build_folder_node_from_input("split")
    f3 = build_folder_node_from_input("merge")

    combos = [
        ("f1f2", [f1, f2]),
        ("f2f3", [f2, f3]),
        ("f3f1", [f3, f1]),
        ("f1f2f3", [f1, f2, f3]),
    ]

    errors = []

    for name, folders in combos:
        base = folders[0].copy()
        for other in folders[1:]:
            try:
                base.merge(other)
            except Exception as e:
                errors.append(f"Fehler beim Mergen {name}: {e}")
                continue

        # Schreibe Ergebnis
        pdf_out = OUTPUT / f"foldermerge_{name}.pdf"
        json_out = OUTPUT / f"foldermerge_{name}.json"
        pdf_out.write_bytes(base.current_pdf_data)
        json_out.write_text(json.dumps(base.to_dict(), indent=2, ensure_ascii=False))

        # Vergleich mit Referenz
        pdf_exp = EXPECTED / f"foldermerge_{name}.pdf"
        json_exp = EXPECTED / f"foldermerge_{name}.json"

        if not pdf_exp.exists() or not json_exp.exists():
            errors.append(f"Referenz fehlt: foldermerge_{name}")
        else:
            if base.current_pdf_data != pdf_exp.read_bytes():
                errors.append(f"PDF weicht ab: foldermerge_{name}")
            if base.to_dict() != json.loads(json_exp.read_text()):
                errors.append(f"Struktur weicht ab: foldermerge_{name}")

    if errors:
        pytest.fail("Folder-Merge Fehler:\n" + "\n".join(errors))

from pdf_node import PDFNode
from helpers import create_valid_pdf, wait_for_real_preview

def test_merge_folder_rebuilds_preview():
    # Ausgangsknoten einmal erzeugen
    base_node = PDFNode("base", pdf_data=create_valid_pdf(pages=1))
    base_node.no_compression = True
    wait_for_real_preview(base_node)

    # Zwei identische Folder mit je einer Kopie
    folder1 = PDFNode("folder1", is_folder=True)
    folder1.add_child(base_node.copy())
    folder2 = PDFNode("folder2", is_folder=True)
    folder2.add_child(base_node.copy())

    # Warten auf Lazy-Preview der Children
    for child in folder1.children + folder2.children:
        wait_for_real_preview(child)

    # Merge durchführen
    folder1.merge(folder2)

    # Vorschau auf oberster Ebene abwarten
    wait_for_real_preview(folder1)

    # Absicherung: 2 Vorschauen erwartet
    previews = folder1.current_preview_images
    assert len(previews) == 2
