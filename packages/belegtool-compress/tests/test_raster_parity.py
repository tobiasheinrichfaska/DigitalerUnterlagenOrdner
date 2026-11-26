"""Parity of the production rasterizer (pdfium) with PyMuPDF as the ORACLE (docs/pdfium-spike.md).

Skipped where PyMuPDF is not installed (it is a dev-only dependency); CI runs it on Windows and Linux.
Thresholds come from the spike: pixel dimensions equal (±1 px); mean absolute difference (0..255) after a
Gaussian blur (which removes glyph anti-aliasing/gamma differences but keeps structure) <= 3 for text/vector and
<= 6 for scans, with a documented 20 % tolerance for crop-edge cases; the RAW difference is allowed to exceed
those numbers on dense text (3.3-5.9 measured: anti-aliasing only) but must stay < 10; mean brightness within
2/255; JPEG variant sizes within 15 %."""

import io

import pytest

pytest.importorskip("fitz")

import fitz  # noqa: E402
from PIL import Image, ImageChops, ImageFilter, ImageStat  # noqa: E402

import fitz_backend  # noqa: E402,F401  (registers BELEG_RASTER=pymupdf)
from belegtool_compress import compress as cpb, pixels, raster  # noqa: E402
from synth import make_pdf  # noqa: E402

TEXT_LIMIT, SCAN_LIMIT, TOLERANCE = 3.0, 6.0, 1.2


# ---------------------------------------------------------------- fixtures

def _text_page(doc, label="Text"):
    p = doc.new_page(width=595, height=842)
    for i in range(40):
        p.insert_text((50, 72 + i * 16), f"{label} Zeile {i}: Rechnung 4711 Betrag 1.234,56 EUR Überweisung", fontsize=10)
    return p


def _scan_jpeg(mode="RGB") -> bytes:
    """A realistic 'scan': rendered text page (200 dpi) with paper tint and sensor noise, as JPEG."""
    import random
    d = fitz.open()
    _text_page(d, "Scan")
    img = Image.open(io.BytesIO(d[0].get_pixmap(dpi=200).tobytes("ppm"))).convert("RGB")
    rnd = random.Random(2)
    px = img.load()
    for y in range(0, img.height):
        for x in range(0, img.width):
            r, g, b = px[x, y]
            n = rnd.randint(-5, 5)
            px[x, y] = (max(0, min(255, int(r * .97) + n)), max(0, min(255, int(g * .96) + n)),
                        max(0, min(255, int(b * .90) + n)))
    if mode == "L":
        img = img.convert("L")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=75)
    return buf.getvalue()


def _case(name):
    d = fitz.open()
    kind = "text"
    if name == "text":
        _text_page(d)
    elif name == "vector":
        p = d.new_page(width=595, height=842)
        for i in range(30):
            p.draw_line((40, 40 + i * 25), (550, 80 + i * 24), color=(0, 0, 0), width=0.5 + i * 0.1)
        p.draw_circle((300, 400), 120, color=(0.8, 0.1, 0.1), fill=(0.9, 0.9, 0.2))
        p.draw_rect((100, 600, 400, 700), color=(0, 0, 1), fill=(0.7, 0.8, 1))
    elif name == "scan_color":
        kind = "scan"
        d.new_page(width=595, height=842).insert_image(fitz.Rect(0, 0, 595, 842), stream=_scan_jpeg())
    elif name == "scan_gray":
        kind = "scan"
        d.new_page(width=595, height=842).insert_image(fitz.Rect(0, 0, 595, 842), stream=_scan_jpeg("L"))
    elif name == "transparency":
        p = d.new_page(width=595, height=842)
        p.draw_rect((50, 50, 400, 400), fill=(1, 0, 0), fill_opacity=0.5)
        p.draw_rect((200, 200, 550, 550), fill=(0, 0, 1), fill_opacity=0.5)
    elif name == "annot_forms":
        p = _text_page(d, "Annot")
        p.add_highlight_annot(fitz.Rect(50, 60, 300, 80))
        p.add_freetext_annot(fitz.Rect(300, 300, 500, 360), "FreeText Anmerkung", fontsize=12,
                             text_color=(1, 0, 0), fill_color=(1, 1, 0.8))
        p.add_rect_annot(fitz.Rect(60, 400, 250, 450)).update()
        for n, y in (("name", 620), ("ort", 660)):
            w = fitz.Widget()
            w.field_name, w.field_type = n, fitz.PDF_WIDGET_TYPE_TEXT
            w.rect, w.field_value, w.text_fontsize = fitz.Rect(100, y, 400, y + 24), "Max Mustermann", 12
            p.add_widget(w)
        w = fitz.Widget()
        w.field_name, w.field_type = "cb", fitz.PDF_WIDGET_TYPE_CHECKBOX
        w.rect, w.field_value = fitz.Rect(100, 700, 120, 720), True
        p.add_widget(w)
    elif name.startswith("rotate_"):
        p = _text_page(d, name)
        p.set_rotation(int(name.split("_")[1]))
    else:
        raise KeyError(name)
    data = d.tobytes()
    d.close()
    return data, kind


def _geometry(name):
    """pikepdf-built variants of the same text page: offset MediaBox, clean CropBox, UserUnit, fractional size."""
    specs = {
        "mediabox_offset": {"mediabox": [100, 200, 695, 1042]},
        "cropbox": {"mediabox": [0, 0, 595, 842], "cropbox": [20, 50, 520, 750]},
        "cropbox_rot90": {"cropbox": [20, 50, 520, 750], "rotate": 90},
        "userunit_2": {"userunit": 2.0},
        "fractional": {"mediabox": [0, 0, 595.276, 841.89]},
    }
    return make_pdf([specs[name]], rects=[(30, 60, 300, 40, (0, 0, 0))]), "text"


GEOMETRY = ["mediabox_offset", "cropbox", "cropbox_rot90", "userunit_2", "fractional"]
CONTENT = ["text", "vector", "scan_color", "scan_gray", "transparency", "annot_forms",
           "rotate_90", "rotate_180", "rotate_270"]
_CACHE = {}


def case(name):
    if name not in _CACHE:
        _CACHE[name] = _geometry(name) if name in GEOMETRY else _case(name)
    return _CACHE[name]


def _both(data, dpi, gray=False):
    with raster.get_backend("pdfium").open(data) as a, raster.get_backend("pymupdf").open(data) as b:
        return a.render(0, dpi, gray=gray), b.render(0, dpi, gray=gray)


def _mad(a, b):
    w, h = min(a.width, b.width), min(a.height, b.height)
    return ImageStat.Stat(ImageChops.difference(a.crop((0, 0, w, h)), b.crop((0, 0, w, h)))).mean[0] \
        if a.mode == "L" else sum(ImageStat.Stat(ImageChops.difference(
            a.crop((0, 0, w, h)), b.crop((0, 0, w, h)))).mean) / 3


def _blur_mad(a, b):
    return _mad(a.filter(ImageFilter.GaussianBlur(1.5)), b.filter(ImageFilter.GaussianBlur(1.5)))


def _brightness(img):
    return sum(ImageStat.Stat(img.convert("L")).mean)


# ---------------------------------------------------------------- pixel parity

@pytest.mark.parametrize("dpi", [50, 100, 150, 300])
@pytest.mark.parametrize("name", ["text", "rotate_90", "cropbox", "userunit_2"])
def test_dimensions_and_structure_match_oracle_across_dpi(name, dpi):
    data, kind = case(name)
    pd, fz = _both(data, dpi)
    assert abs(pd.width - fz.width) <= 1 and abs(pd.height - fz.height) <= 1, (pd.size, fz.size)
    limit = (SCAN_LIMIT if kind == "scan" else TEXT_LIMIT) * TOLERANCE
    assert _blur_mad(pd, fz) <= limit
    assert _mad(pd, fz) < 10  # raw: anti-aliasing only, never a structural defect
    assert abs(_brightness(pd) - _brightness(fz)) < 2


@pytest.mark.parametrize("name", [n for n in CONTENT + GEOMETRY])
def test_dimensions_and_structure_match_oracle_150dpi(name):
    data, kind = case(name)
    pd, fz = _both(data, 150)
    assert abs(pd.width - fz.width) <= 1 and abs(pd.height - fz.height) <= 1, (pd.size, fz.size)
    limit = (SCAN_LIMIT if kind == "scan" else TEXT_LIMIT) * TOLERANCE
    assert _blur_mad(pd, fz) <= limit
    assert _mad(pd, fz) < 10
    assert abs(_brightness(pd) - _brightness(fz)) < 2


@pytest.mark.parametrize("name", ["text", "scan_color", "annot_forms", "rotate_270", "cropbox"])
def test_grayscale_matches_oracle_luminance(name):
    data, kind = case(name)
    pd, fz = _both(data, 150, gray=True)
    assert pd.mode == fz.mode == "L"
    assert abs(pd.width - fz.width) <= 1 and abs(pd.height - fz.height) <= 1
    assert _blur_mad(pd, fz) <= (SCAN_LIMIT if kind == "scan" else TEXT_LIMIT) * TOLERANCE


def test_native_mupdf_gray_brightens_saturated_colour_but_we_use_luminance():
    """Documented deviation (docs/pdfium-spike.md): MuPDF's csGRAY maps pure red to ~129, luminance is 76."""
    d = fitz.open()
    d.new_page(width=100, height=100).draw_rect((10, 10, 90, 90), fill=(1, 0, 0), color=None)
    data = d.tobytes()
    native = Image.open(io.BytesIO(d[0].get_pixmap(dpi=72, colorspace=fitz.csGRAY).tobytes("ppm"))).convert("L")
    with raster.open_pdf(data) as s:
        ours = s.render(0, 72, gray=True)
    assert 120 <= native.getpixel((50, 50)) <= 140
    assert ours.getpixel((50, 50)) == 76


def test_annotations_and_widgets_region_matches_oracle():
    data, _ = case("annot_forms")
    pd, fz = _both(data, 150)
    s = 150 / 72
    box = (int(40 * s), int(40 * s), int(560 * s), int(740 * s))
    assert _blur_mad(pd.crop(box), fz.crop(box)) <= TEXT_LIMIT * TOLERANCE


# ---------------------------------------------------------------- budget and failure parity

def test_pixel_budget_clamps_like_the_oracle(monkeypatch):
    monkeypatch.setattr(pixels, "MAX_RENDER_PIXELS", 250_000)
    data = make_pdf([{"mediabox": [0, 0, 595, 14400]}])
    sizes = {}
    for backend in ("pdfium", "pymupdf"):
        with raster.get_backend(backend).open(data) as s:
            img, w, h = cpb._render_one_page(s, 0, 150, "jpg", cpb.DEFAULT_CONFIG, "L")
        with Image.open(io.BytesIO(img)) as im:
            assert im.width * im.height <= 250_000
            sizes[backend] = im.size
        assert (w, h) == (595, 14400)
    assert abs(sizes["pdfium"][0] - sizes["pymupdf"][0]) <= 1 and abs(sizes["pdfium"][1] - sizes["pymupdf"][1]) <= 1


# ---------------------------------------------------------------- compression parity

def _compress_with(backend, data, monkeypatch):
    monkeypatch.setenv("BELEG_RASTER", backend)
    return cpb.compress_all_methods(data, dpi=120)


@pytest.mark.parametrize("name", ["scan_color", "text", "rotate_90"])
def test_compression_variants_match_oracle_in_size_and_pages(name, monkeypatch):
    data, _ = case(name)
    a = _compress_with("pdfium", data, monkeypatch)
    b = _compress_with("pymupdf", data, monkeypatch)
    assert set(a) == set(b), (set(a), set(b))
    from pypdf import PdfReader
    n_src = len(PdfReader(io.BytesIO(data)).pages)
    for method in a:
        assert len(PdfReader(io.BytesIO(a[method])).pages) == n_src  # page-count guard holds
        delta = (len(a[method]) - len(b[method])) / len(b[method])
        assert abs(delta) <= 0.15, (method, len(a[method]), len(b[method]))


def test_default_backend_env_selects_oracle_and_back(monkeypatch):
    monkeypatch.setenv("BELEG_RASTER", "pymupdf")
    assert raster.get_backend().name == "pymupdf"
    monkeypatch.delenv("BELEG_RASTER")
    assert raster.get_backend().name == "pdfium"
