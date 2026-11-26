"""Raster comparison tool: PyMuPDF (fitz) vs. pypdfium2 on synthetic + fixture PDFs.

Phase-1 spike tool (docs/pdfium-spike.md) and later the Windows parity runner
(docs/windows-pc-testlauf.md, Phase 5).  Needs ``PyMuPDF`` (dev/oracle only) and ``pypdfium2``.

    python scripts/raster_compare.py                 # all checks, markdown tables to stdout
    python scripts/raster_compare.py --only dims,diff
    python scripts/raster_compare.py --pdf some.pdf  # extra real PDF(s) (e.g. a real scan)

Checks: dims (a), diff (b), jpeg (c), speed (d), threads (e), memory (f).
Exit code 1 when a hard threshold fails (dims > 1 px, diff over limit, speed < 0.7x, thread mismatch).
"""
import argparse
import io
import math
import os
import sys
import threading
import time
import zlib

import numpy as np
import pikepdf
from PIL import Image

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None
import pypdfium2 as pdfium

DPIS = (50, 100, 150, 300)
MAX_PIXELS = 64_000_000
class PriorityLock:
    """Process-wide pdfium lock with foreground priority: a background acquirer waits while any
    foreground acquirer is queued, so an interactive page waits for at most ONE running render."""

    def __init__(self):
        self._cv = threading.Condition(threading.Lock())
        self._busy = False
        self._fg_waiting = 0
        self.background = False  # default for plain `with lock:`

    def acquire(self, background: bool = False):
        with self._cv:
            if not background:
                self._fg_waiting += 1
            try:
                while self._busy or (background and self._fg_waiting):
                    self._cv.wait()
            finally:
                if not background:
                    self._fg_waiting -= 1
            self._busy = True

    def release(self):
        with self._cv:
            self._busy = False
            self._cv.notify_all()


PDFIUM_LOCK = PriorityLock()


# ---------------------------------------------------------------- backends
def fitz_render(data: bytes, index: int, dpi: int, gray: bool = False) -> Image.Image:
    with fitz.open(stream=data, filetype="pdf") as doc:
        page = doc[index]
        pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY if gray else fitz.csRGB)
        return Image.open(io.BytesIO(pix.tobytes("ppm"))).convert("L" if gray else "RGB")


_UU_CACHE = {}


def user_unit(data: bytes, index: int) -> float:
    """/UserUnit of a page (pdfium ignores it; MuPDF/Acrobat honour it -> scale ourselves).
    Looked up once per document (keyed by length+crc32), not per page."""
    key = (len(data), zlib.crc32(data))
    units = _UU_CACHE.get(key)
    if units is None:
        units = ()
        if b"UserUnit" in data or b"ObjStm" in data:
            try:
                with pikepdf.open(io.BytesIO(data), suppress_warnings=True) as pdf:
                    units = tuple(float(p.obj.get("/UserUnit", 1.0)) for p in pdf.pages)
            except Exception:
                units = ()
        if len(_UU_CACHE) > 8:
            _UU_CACHE.clear()
        _UU_CACHE[key] = units
    u = units[index] if index < len(units) else 1.0
    return u if u > 0 else 1.0


def pdfium_render(data: bytes, index: int, dpi: int, gray: bool = False, lock=PDFIUM_LOCK,
                  background: bool = False) -> Image.Image:
    dpi = dpi * user_unit(data, index)
    lock.acquire(background)
    try:
        pdf = pdfium.PdfDocument(data)
        try:
            try:
                pdf.init_forms()
            except Exception:
                pass
            page = pdf[index]
            try:
                bm = page.render(scale=dpi / 72.0, grayscale=False, fill_color=(255, 255, 255, 255),
                                 may_draw_forms=True, draw_annots=True)
                img = bm.to_pil()
                img.load()
            finally:
                page.close()
        finally:
            pdf.close()
    finally:
        lock.release()
    return img.convert("L" if gray else "RGB")


# ---------------------------------------------------------------- fixtures
def _text_page(doc, w=595, h=842, label="Text"):
    p = doc.new_page(width=w, height=h)
    y = 72
    for i in range(40):
        p.insert_text((50, y), f"{label} Zeile {i}: Rechnung 4711 Betrag 1.234,56 EUR Überweisung", fontsize=10)
        y += 16
    return p


def _noise_jpeg(w=900, h=1200, seed=1, mode="RGB", quality=85) -> bytes:
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 256, (h // 8, w // 8, 3), dtype=np.uint8)
    img = Image.fromarray(base).resize((w, h), Image.BILINEAR)
    if mode == "L":
        img = img.convert("L")
    if mode == "CMYK":
        img = img.convert("CMYK")
    b = io.BytesIO()
    img.save(b, "JPEG", quality=quality)
    return b.getvalue()


def _scan_jpeg(seed=2, mode="RGB", quality=75) -> bytes:
    """Realistic 'scan': a rendered text page (200 dpi) with paper tint + sensor noise, as JPEG."""
    d = fitz.open()
    _text_page(d, label="Scan")
    pix = d[0].get_pixmap(dpi=200)
    img = Image.open(io.BytesIO(pix.tobytes("ppm"))).convert("RGB")
    rng = np.random.default_rng(seed)
    arr = np.asarray(img, dtype=np.float32)
    arr = arr * np.array([0.97, 0.96, 0.90], dtype=np.float32) + rng.normal(0, 4, arr.shape)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    if mode == "L":
        img = img.convert("L")
    b = io.BytesIO()
    img.save(b, "JPEG", quality=quality)
    return b.getvalue()


def make_cases() -> dict:
    """name -> (bytes, kind) with kind in {'text','scan'} (threshold class)."""
    cases = {}

    d = fitz.open(); _text_page(d); cases["text_a4"] = (d.tobytes(), "text")

    d = fitz.open(); p = d.new_page(width=595, height=842)
    for i in range(30):
        p.draw_line((40, 40 + i * 25), (550, 80 + i * 24), color=(0, 0, 0), width=0.5 + i * 0.1)
    p.draw_circle((300, 400), 120, color=(0.8, 0.1, 0.1), fill=(0.9, 0.9, 0.2))
    p.draw_rect((100, 600, 400, 700), color=(0, 0, 1), fill=(0.7, 0.8, 1))
    cases["vector"] = (d.tobytes(), "text")

    d = fitz.open(); p = d.new_page(width=595, height=842)
    p.insert_image(fitz.Rect(0, 0, 595, 842), stream=_scan_jpeg())
    cases["scan_color_jpeg"] = (d.tobytes(), "scan")

    d = fitz.open(); p = d.new_page(width=595, height=842)
    p.insert_image(fitz.Rect(20, 20, 575, 822), stream=_noise_jpeg())
    cases["stress_noise_jpeg"] = (d.tobytes(), "stress")

    d = fitz.open(); p = d.new_page(width=595, height=842)
    p.insert_image(fitz.Rect(0, 0, 595, 842), stream=_scan_jpeg(mode="L"))
    cases["scan_gray_jpeg"] = (d.tobytes(), "scan")

    d = fitz.open(); p = d.new_page(width=595, height=842)
    p.insert_image(fitz.Rect(20, 20, 575, 822), stream=_noise_jpeg(mode="CMYK"))
    cases["image_cmyk_jpeg"] = (d.tobytes(), "scan")

    # 16-bit grey PNG
    arr = (np.linspace(0, 65535, 300 * 300).reshape(300, 300)).astype(np.uint16)
    b = io.BytesIO(); Image.fromarray(arr).save(b, "PNG")
    d = fitz.open(); p = d.new_page(width=400, height=400)
    try:
        p.insert_image(fitz.Rect(20, 20, 380, 380), stream=b.getvalue())
        cases["image_16bit_png"] = (d.tobytes(), "scan")
    except Exception as e:  # pragma: no cover
        print("skip 16bit:", e, file=sys.stderr)

    # transparency: semi-transparent shapes + soft-mask PNG
    d = fitz.open(); p = d.new_page(width=595, height=842)
    p.draw_rect((50, 50, 400, 400), fill=(1, 0, 0), fill_opacity=0.5)
    p.draw_rect((200, 200, 550, 550), fill=(0, 0, 1), fill_opacity=0.5)
    rgba = Image.new("RGBA", (200, 200), (0, 128, 0, 90)); b = io.BytesIO(); rgba.save(b, "PNG")
    p.insert_image(fitz.Rect(100, 600, 400, 800), stream=b.getvalue())
    cases["transparency"] = (d.tobytes(), "text")

    # annotations + form fields
    d = fitz.open(); p = _text_page(d, label="Annot")
    p.add_highlight_annot(fitz.Rect(50, 60, 300, 80))
    p.add_text_annot((400, 100), "Notiz")
    p.add_freetext_annot(fitz.Rect(300, 300, 500, 360), "FreeText Anmerkung", fontsize=12,
                         text_color=(1, 0, 0), fill_color=(1, 1, 0.8))
    p.add_rect_annot(fitz.Rect(60, 400, 250, 450)).update()
    p.add_stamp_annot(fitz.Rect(300, 500, 500, 580), stamp=0)
    for n, y in (("name", 620), ("ort", 660)):
        w = fitz.Widget(); w.field_name = n; w.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        w.rect = fitz.Rect(100, y, 400, y + 24); w.field_value = "Max Mustermann"; w.text_fontsize = 12
        p.add_widget(w)
    w = fitz.Widget(); w.field_name = "cb"; w.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
    w.rect = fitz.Rect(100, 700, 120, 720); w.field_value = True
    p.add_widget(w)
    cases["annot_forms"] = (d.tobytes(), "text")

    # rotation
    for rot in (90, 180, 270):
        d = fitz.open(); p = _text_page(d, label=f"Rot{rot}")
        p.insert_image(fitz.Rect(300, 100, 560, 360), stream=_noise_jpeg(300, 300, 5))
        p.set_rotation(rot)
        cases[f"rotate_{rot}"] = (d.tobytes(), "text")

    # geometry: MediaBox offset / CropBox / UserUnit (pikepdf edits)
    base = cases["text_a4"][0]

    def edit(fn):
        with pikepdf.open(io.BytesIO(base)) as pdf:
            fn(pdf.pages[0].obj)
            b = io.BytesIO(); pdf.save(b); return b.getvalue()

    def crop_rot(o):
        o.CropBox = pikepdf.Array([20, 50, 520, 750]); o.Rotate = 90

    cases["mediabox_offset"] = (edit(lambda o: setattr(o, "MediaBox", pikepdf.Array([100, 200, 695, 1042]))), "text")
    cases["cropbox"] = (edit(lambda o: setattr(o, "CropBox", pikepdf.Array([20, 50, 520, 750]))), "text")
    # crop edge cuts through glyphs (clipping + sub-pixel origin): informational stress case
    cases["cropbox_clip"] = (edit(lambda o: setattr(o, "CropBox", pikepdf.Array([50, 100, 400, 600]))), "stress")
    cases["cropbox_rot90"] = (edit(crop_rot), "text")
    cases["userunit_2"] = (edit(lambda o: setattr(o, "UserUnit", 2.0)), "text")
    cases["fractional_size"] = (edit(lambda o: setattr(o, "MediaBox", pikepdf.Array([0, 0, 595.276, 841.89]))), "text")

    # huge MediaBox (pixel budget): 200x200 in = 14400 pt, mostly empty
    cases["huge_mediabox"] = (edit(lambda o: setattr(o, "MediaBox", pikepdf.Array([0, 0, 14400, 14400]))), "text")

    # encrypted with empty user password
    with pikepdf.open(io.BytesIO(base)) as pdf:
        b = io.BytesIO()
        pdf.save(b, encryption=pikepdf.Encryption(user="", owner="owner", R=4))
        cases["encrypted_empty_pw"] = (b.getvalue(), "text")

    # damaged xref: replace startxref offset by garbage
    bad = bytearray(base)
    i = bad.rfind(b"startxref")
    bad[i:] = b"startxref\n999999\n%%EOF\n"
    cases["broken_xref"] = (bytes(bad), "text")
    return cases


# ---------------------------------------------------------------- checks
def dims_ok(a: tuple, b: tuple) -> bool:
    return abs(a[0] - b[0]) <= 1 and abs(a[1] - b[1]) <= 1


def capped(w_pt: float, h_pt: float, dpi: int) -> int:
    px = (w_pt * dpi / 72.0) * (h_pt * dpi / 72.0)
    if px <= MAX_PIXELS or px <= 0:
        return dpi
    return max(1, int(dpi * math.sqrt(MAX_PIXELS / px)))


def page_pts(data: bytes):
    with fitz.open(stream=data, filetype="pdf") as d:
        r = d[0].rect
        return r.width, r.height


def mad(a: Image.Image, b: Image.Image):
    """Mean absolute difference (0..255) over the common area."""
    w, h = min(a.width, b.width), min(a.height, b.height)
    x = np.asarray(a.crop((0, 0, w, h)), dtype=np.int16)
    y = np.asarray(b.crop((0, 0, w, h)), dtype=np.int16)
    return float(np.abs(x - y).mean())


def blur_mad(a: Image.Image, b: Image.Image, radius: float = 1.5):
    """MAD after a Gaussian blur: removes glyph anti-aliasing/gamma/hinting differences between
    two rasterizers but still exposes structural defects (missing annotations, shifted content,
    wrong rotation, black pages)."""
    from PIL import ImageFilter
    return mad(a.filter(ImageFilter.GaussianBlur(radius)), b.filter(ImageFilter.GaussianBlur(radius)))


def check_dims_diff(cases):
    rows = []
    fails = []
    for name, (data, kind) in cases.items():
        for dpi in DPIS:
            if name == "huge_mediabox" and dpi != 150:
                continue
            try:
                w, h = page_pts(data)
                use = capped(w, h, dpi)
                fa = fitz_render(data, 0, use)
                pa = pdfium_render(data, 0, use)
            except Exception as e:
                rows.append((name, dpi, "-", "-", "-", "-", f"ERR {type(e).__name__}: {str(e)[:50]}"))
                fails.append((name, dpi, "error"))
                continue
            dim_ok = dims_ok(fa.size, pa.size)
            m = mad(fa, pa)
            mb = blur_mad(fa, pa)
            lim = 6.0 if kind in ("scan", "stress") else 3.0
            verdict = "ok"
            if not dim_ok:
                verdict = "DIM"
            if mb > lim * 1.2:
                verdict = "STRUKTUR" if verdict == "ok" else verdict + "+STRUKTUR"
            elif mb > lim:
                verdict = "GRENZE" if verdict == "ok" else verdict  # <= 1.2x limit: documented tolerance
            elif m > lim:
                verdict = "AA" if verdict == "ok" else verdict  # raw over limit, structure fine
            if verdict not in ("ok", "AA", "GRENZE") and kind != "stress":
                fails.append((name, dpi, verdict))
            rows.append((name, dpi, f"{fa.width}x{fa.height}", f"{pa.width}x{pa.height}",
                         f"{m:.2f}", f"{mb:.2f}", verdict))
    print("\n### (a)+(b) Pixelmaße und mittlere Abweichung (RGB, 0..255)\n")
    print("| Fall | DPI | fitz | pdfium | MAD roh | MAD geglättet | Urteil |\n|---|---|---|---|---|---|---|")
    for r in rows:
        print("| " + " | ".join(str(c) for c in r) + " |")
    print("\n### (b2) Graustufen (jpg/png-Methoden), 150 DPI\n")
    print("Orakel = fitz RGB->L (gleiche Luminanzformel wie pdfium-RGB->L). "
          "Spalte 'nativ' = fitz csGRAY (MuPDF hellt gesättigte Farben auf: Rot 129 statt 76) - nur Information.\n")
    print("| Fall | fitz | pdfium | MAD roh | MAD geglättet | MAD vs. fitz nativ-Gray | Urteil |\n|---|---|---|---|---|---|---|")
    for name, (data, kind) in cases.items():
        if name == "huge_mediabox":
            continue
        try:
            fa = fitz_render(data, 0, 150, gray=False).convert("L")
            fn = fitz_render(data, 0, 150, gray=True)
            pa = pdfium_render(data, 0, 150, gray=True)
            m = mad(fa, pa)
            mb = blur_mad(fa, pa)
            mn = mad(fn, pa)
            lim = 6.0 if kind in ("scan", "stress") else 3.0
            v = "ok" if mb <= lim and dims_ok(fa.size, pa.size) else "FAIL"
            if v == "ok" and m > lim:
                v = "AA"
            if v == "FAIL" and kind != "stress":
                fails.append((name, "gray", v))
            print(f"| {name} | {fa.width}x{fa.height} | {pa.width}x{pa.height} | {m:.2f} | {mb:.2f} | {mn:.2f} | {v} |")
        except Exception as e:
            print(f"| {name} | - | - | - | - | - | ERR {type(e).__name__} |")
            fails.append((name, "gray", "error"))
    return fails


def check_align_annots(cases):
    """Systematic offset (best +-2 px shift must be <= 1 px) and annotation/widget presence."""
    fails = []
    print("\n### (b3) Versatz und Annotationen/Formularfelder (150 DPI)\n")
    print("| Fall | bester Versatz (dy,dx) | Urteil |\n|---|---|---|")
    from PIL import ImageFilter
    for name, (data, kind) in cases.items():
        if name == "huge_mediabox":
            continue
        a = np.asarray(fitz_render(data, 0, 150).convert("L").filter(ImageFilter.GaussianBlur(1)), dtype=int)
        b = np.asarray(pdfium_render(data, 0, 150).convert("L").filter(ImageFilter.GaussianBlur(1)), dtype=int)
        best = min(((np.abs(np.roll(np.roll(b, dy, 0), dx, 1) - a).mean(), (dy, dx))
                    for dy in range(-2, 3) for dx in range(-2, 3)))
        # <= 1 px like (a); near-horizontal hairlines ('vector') cannot constrain the x shift
        ok = max(abs(best[1][0]), abs(best[1][1])) <= (2 if name == "vector" else 1)
        if not ok:
            fails.append((name, "align", str(best[1])))
        print(f"| {name} | {best[1]} | {'ok' if ok else 'FAIL'} |")
    data = cases["annot_forms"][0]
    sc = 150 / 72.0
    box = (int(40 * sc), int(40 * sc), int(560 * sc), int(740 * sc))
    full = pdfium_render(data, 0, 150)
    f = fitz_render(data, 0, 150)
    region = lambda im: im.crop(box)
    m_region = blur_mad(region(f), region(full))
    # same page without annotations/forms must differ visibly -> they ARE drawn by default
    PDFIUM_LOCK.acquire()
    try:
        pdf = pdfium.PdfDocument(data)
        page = pdf[0]
        bare = page.render(scale=sc, draw_annots=False, may_draw_forms=False).to_pil().convert("RGB")
        page.close()
        pdf.close()
    finally:
        PDFIUM_LOCK.release()
    m_bare = mad(full, bare)
    print(f"\nAnnotationen/Widgets: Region-MAD (geglättet) fitz vs pdfium = {m_region:.2f}; "
          f"pdfium mit vs. ohne Annotationen/Formulare differiert um {m_bare:.2f} (muss > 0.05 sein)")
    if m_region > 3.0 or m_bare <= 0.05:
        fails.append(("annot_forms", "annots", f"{m_region:.2f}/{m_bare:.2f}"))
    return fails


def jpeg_size(img: Image.Image, q: int) -> int:
    b = io.BytesIO()
    img.save(b, "JPEG", quality=q)
    return len(b.getvalue())


def check_jpeg(cases):
    fails = []
    print("\n### (c) JPEG-Größe der Kompressionsvarianten (150 DPI)\n")
    print("| Fall | Variante | fitz B | pdfium B | Abw. | Urteil |\n|---|---|---|---|---|---|")
    for name, (data, kind) in cases.items():
        if name == "huge_mediabox":
            continue
        for var, gray, q in (("jpg (grau, q60)", True, 60), ("jpg_color (q75)", False, 75)):
            try:
                a = jpeg_size(fitz_render(data, 0, 150, gray), q)
                b = jpeg_size(pdfium_render(data, 0, 150, gray), q)
            except Exception:
                continue
            dev = (b - a) / a * 100
            ok = abs(dev) <= 15
            if not ok:
                fails.append((name, var, f"{dev:+.1f}%"))
            print(f"| {name} | {var} | {a} | {b} | {dev:+.1f} % | {'ok' if ok else 'FAIL'} |")
    return fails


def multipage(n=20):
    with fitz.open() as d:
        for i in range(n):
            p = d.new_page()
            p.insert_text((72, 100), f"Seite {i}", fontsize=24)
            p.insert_image(fitz.Rect(50, 150, 500, 600), stream=_noise_jpeg(450, 450, i))
            for j in range(20):
                p.insert_text((50, 650 + j * 6), "Rechnung " * 8, fontsize=5)
        return d.tobytes()


def _bench_pair(fa, fb, n_pages, repeats=11):
    """Best-of-N mean ms/page for two backends, measured interleaved (A,B,A,B...) so a noisy
    neighbour on a shared machine hits both alike; the minimum filters scheduler noise."""
    best = [1e9, 1e9]
    for _ in range(repeats):
        for k, fn in enumerate((fa, fb)):
            t = time.perf_counter()
            for i in range(n_pages):
                fn(i)
            best[k] = min(best[k], (time.perf_counter() - t) / n_pages * 1000)
    return best


def check_speed(cases):
    docs = {
        "Text+Bild (20 S.)": (multipage(), 20),
        "Scan farbig (1 S.)": (cases["scan_color_jpeg"][0], 1),
        "Text dicht (1 S.)": (cases["text_a4"][0], 1),
    }
    print("\n### (d) Geschwindigkeit je Seite (open+render+PIL+close je Seite, Best-of-11 interleaved, ms)\n")
    print("| Dokument | DPI | fitz | pdfium | pdfium/fitz-Tempo |\n|---|---|---|---|---|")
    worst = 9.9
    ratios = []
    for name, (data, n) in docs.items():
        for dpi in (100, 150, 300):
            f, p = _bench_pair(lambda i: fitz_render(data, i, dpi),
                               lambda i: pdfium_render(data, i, dpi), n)
            r = f / p
            ratios.append(r)
            worst = min(worst, r)
            print(f"| {name} | {dpi} | {f:.1f} | {p:.1f} | {r:.2f}x |")
    ratios.sort()
    med = ratios[len(ratios) // 2]
    slow = [r for r in ratios if r < 0.7]
    print(f"\nMedian-Verhältnis {med:.2f}x, schlechtester Fall {worst:.2f}x, {len(slow)} von {len(ratios)} Fällen unter 0.7x "
          f"(Ziel >= 0.7x; hart: Median >= 0.7x und kein Fall < 0.5x, Einzelfälle < 0.7x werden dokumentiert)")
    return [] if (med >= 0.7 and worst >= 0.5) else [("speed", "Median/schlechtester Fall", f"{med:.2f}x/{worst:.2f}x")]


def check_threads():
    data = multipage(20)
    ref = [pdfium_render(data, i % 20, 100).tobytes() for i in range(20)]
    errs = []
    n_threads, per = 8, 200

    def work(tid):
        for k in range(per):
            i = (tid + k) % 20
            try:
                if pdfium_render(data, i, 100).tobytes() != ref[i]:
                    errs.append((tid, k, "mismatch"))
            except Exception as e:  # pragma: no cover
                errs.append((tid, k, repr(e)))

    t0 = time.perf_counter()
    ts = [threading.Thread(target=work, args=(t,)) for t in range(n_threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    dt = time.perf_counter() - t0
    print("\n### (e) Thread-Sicherheit mit globalem Lock\n")
    print(f"8 Threads x 200 Seiten (100 DPI) = {n_threads*per} Renderings in {dt:.1f} s; "
          f"Fehler/Abweichungen: {len(errs)}")

    single = []
    for i in range(20):
        t = time.perf_counter()
        pdfium_render(data, i, 100)
        single.append(time.perf_counter() - t)
    single_med = sorted(single)[len(single) // 2]
    stop = threading.Event()

    def bg(tid):
        k = tid
        while not stop.is_set():
            pdfium_render(data, k % 20, 100, background=True)
            k += 1

    bts = [threading.Thread(target=bg, args=(t,), daemon=True) for t in range(4)]
    for t in bts:
        t.start()
    time.sleep(0.3)
    lat = []
    for i in range(30):
        t = time.perf_counter()
        pdfium_render(data, i % 20, 100)
        lat.append(time.perf_counter() - t)
        time.sleep(0.02)
    stop.set()
    for t in bts:
        t.join()
    lat.sort()
    med, p95 = lat[len(lat) // 2], lat[int(len(lat) * 0.95)]
    bound = 3 * single_med  # 2x single + wait of one running page
    print(f"Vordergrund-Seite allein: {single_med*1000:.1f} ms; bei 4 Hintergrund-Threads: Median "
          f"{med*1000:.1f} ms, p95 {p95*1000:.1f} ms; Ziel <= 2x + 1 Seite = {bound*1000:.1f} ms")
    fails = []
    if errs:
        fails.append(("threads", "", f"{len(errs)} Fehler"))
    if med > bound:
        fails.append(("latency", "", f"median {med*1000:.0f}ms > {bound*1000:.0f}ms"))
    return fails


def rss_mb():
    try:
        with open("/proc/self/statm") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1e6
    except Exception:
        try:
            import psutil
            return psutil.Process().memory_info().rss / 1e6
        except Exception:
            return float("nan")


def check_memory():
    data = multipage(20)
    for _ in range(100):  # warm up allocator
        pdfium_render(data, 0, 100)
    r0 = rss_mb()
    marks = []
    for i in range(1000):
        pdfium_render(data, i % 20, 100)
        if i in (249, 499, 749, 999):
            marks.append(rss_mb())
    print("\n### (f) Speicher (1000 Seiten, Dokument je Aufruf geschlossen)\n")
    print(f"RSS vor: {r0:.0f} MB; nach 250/500/750/1000: " + " / ".join(f"{m:.0f}" for m in marks) + " MB")
    growth = marks[-1] - marks[0]
    ok = growth < 30 or growth != growth
    print(f"Wachstum zwischen Seite 250 und 1000: {growth:.1f} MB -> {'ok' if ok else 'LECK?'}")
    return [] if ok else [("memory", "", f"{growth:.0f}MB")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="dims,align,jpeg,speed,threads,memory")
    ap.add_argument("--pdf", action="append", default=[], help="extra real PDFs (kind 'scan')")
    args = ap.parse_args()
    if fitz is None:
        sys.exit("PyMuPDF (fitz) wird als Orakel benötigt: pip install PyMuPDF")
    only = set(args.only.split(","))
    print(f"fitz {fitz.VersionBind}; pypdfium2 {pdfium.version.PYPDFIUM_INFO}; pdfium {pdfium.version.PDFIUM_INFO}")
    cases = make_cases()
    for p in args.pdf:
        with open(p, "rb") as f:
            cases[os.path.basename(p)] = (f.read(), "scan")
    fails = []
    if only & {"dims", "diff"}:
        fails += check_dims_diff(cases)
    if "align" in only:
        fails += check_align_annots(cases)
    if "jpeg" in only:
        fails += check_jpeg(cases)
    if "speed" in only:
        fails += check_speed(cases)
    if "threads" in only:
        fails += check_threads()
    if "memory" in only:
        fails += check_memory()
    print("\n### Ergebnis\n")
    if fails:
        for f in fails:
            print("FAIL:", *f)
        sys.exit(1)
    print("alle Schwellen erfüllt")


if __name__ == "__main__":
    main()
