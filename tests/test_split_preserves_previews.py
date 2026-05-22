from pdf_node import PDFNode
from helpers import create_valid_pdf, wait_for_ready


def test_split_preserves_previews():
    # 🔧 Erzeuge 2-seitiges gültiges PDF
    data = create_valid_pdf(pages=2)
    node = PDFNode(name="TestSplit", pdf_data=data)

    # ⏳ Warten auf Vorschau & Kompression
    wait_for_ready(node)

    # ✅ Validierung der Vorschau
    assert len(node.original_preview_images) == 2, (
        f"Original-Vorschau fehlt oder unvollständig: {len(node.original_preview_images)} Seiten"
    )
    assert len(node.current_preview_images) == 2, (
        f"Aktuelle Vorschau fehlt oder unvollständig: {len(node.current_preview_images)} Seiten"
    )

    # 🖼 Referenzbilder sichern (Seite 2 = Index 1)
    ref_orig = node.original_preview_images[1]
    ref_curr = node.current_preview_images[1]

    # 🔪 Split durchführen
    split_nodes = node.split()
    assert len(split_nodes) == 1, "Split sollte genau 1 neuen Knoten erzeugen"

    split_node = split_nodes[0]
    wait_for_ready(split_node)

    split_orig = split_node.original_preview_images[0]
    split_curr = split_node.current_preview_images[0]

    # 📏 Bildvergleich (keine Objektgleichheit, nur Größe & Modus)
    assert split_orig.size == ref_orig.size, "Original-Vorschaugröße stimmt nicht überein"
    assert split_orig.mode == ref_orig.mode, "Original-Vorschaumodus stimmt nicht überein"
    assert split_curr.size == ref_curr.size, "Current-Vorschaugröße stimmt nicht überein"
    assert split_curr.mode == ref_curr.mode, "Current-Vorschaumodus stimmt nicht überein"

    # 🔍 Flags prüfen
    assert split_node.no_compression is True
    assert split_node.is_compressed is True
    assert split_node.dpi_current is 120
