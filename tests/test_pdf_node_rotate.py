import pytest
from pdf_node import PDFNode
from pathlib import Path
from PIL import Image
from helpers import create_valid_pdf
import itertools

INPUT_DIR = Path("tests/data/input/")
EXPECTED_DIR = Path("tests/data/expected/")
OUTPUT_DIR = Path("tests/data/output/")
EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------------
# Vergleichsbilder erzeugen
# -------------------------------

@pytest.mark.order(1)
def test_generate_rotation_reference_images():
    angles = [0, 90, 180, 270]

    base_node = PDFNode("ref_base", pdf_data=create_valid_pdf(pages=1))
    base_node.no_compression = True
    base_node.dpi_current = None
    base_node.update_preview()

    for angle in angles:
        node = base_node.copy()

        if angle > 0:
            node.original_pdf_data = node._rotate_pdf_data(node.original_pdf_data, angle)
            node.current_pdf_data = None

        node.no_compression = True
        node.dpi_current = None
        node.update_preview()

        img = node.original_preview_images[0]
        img.save(EXPECTED_DIR / f"expected_rotation_{angle:03}.png")

    # Sicherstellen, dass die Bilder eindeutig sind
    imgs = [Image.open(EXPECTED_DIR / f"expected_rotation_{a:03}.png") for a in angles]
    pixels = [list(img.getdata()) for img in imgs]
    assert all(pixels[i] != pixels[j] for i in range(4) for j in range(i + 1, 4)), "Rotationsergebnisse nicht eindeutig"

# -----------------------------------------
# Rotation mit Bildvergleich
# -----------------------------------------

DIRECTIONS = ["right", "left", "180"]
MAX_ACTIONS = 3
MAX_REPEATS = {"right": 2, "left": 2, "180": 1}
ANGLE_MAP = {"right": 90, "left": -90, "180": 180}

def expected_rotation_angle(sequence: list[str]) -> int:
    return sum(ANGLE_MAP[step] for step in sequence) % 360

def apply_rotation_sequence(node: PDFNode, sequence: list[str]):
    counts = {"right": 0, "left": 0, "180": 0}
    for direction in sequence:
        if counts[direction] >= MAX_REPEATS[direction]:
            continue
        node.rotate(direction)
        counts[direction] += 1
    return node

@pytest.mark.order(2)
def test_rotation_combinations_against_reference_images():
    reference_images = {
        angle: Image.open(EXPECTED_DIR / f"expected_rotation_{angle:03}.png").tobytes()
        for angle in [0, 90, 180, 270]
    }

    base_node = PDFNode("test_base", pdf_data=create_valid_pdf(pages=1))
    base_node.no_compression = True
    base_node.dpi_current = None
    base_node.update_preview()

    for depth in range(1, MAX_ACTIONS + 1):
        for sequence in itertools.product(DIRECTIONS, repeat=depth):
            if any(sequence.count(d) > MAX_REPEATS[d] for d in DIRECTIONS):
                continue

            angle = expected_rotation_angle(sequence)

            node = base_node.copy()
            apply_rotation_sequence(node, list(sequence))
            node.no_compression = True
            node.dpi_current = None
            node.update_preview()

            actual = node.original_preview_images[0].tobytes()
            assert actual == reference_images[angle], f"Falsches Bild bei {sequence}, erwartet {angle}°"

# -----------------------------------------
# Ungültige Rotation testen
# -----------------------------------------

def test_rotation_with_invalid_pdf():
    invalid_data = b"Dies ist kein PDF"
    node = PDFNode("kaputt.pdf")

    with pytest.raises(ValueError, match="Ungültige PDF-Daten"):
        node.set_original_and_current_data(
            original_data=invalid_data,
            current_data=None,
            dpi_original=None,
            dpi_current=None,
            no_compression=False
        )

    assert node.original_preview_images == []
    assert node.current_preview_images == []
