"""The pdfium rasterizer (production backend): geometry, orientation, annotations/forms, failure modes,
backend selection and the process-wide lock. Needs NO PyMuPDF (PDFs come from ``synth.py``)."""

import math
import threading
import time

import pytest

from belegtool_compress import raster
from synth import broken_xref, encrypted_with_password, make_pdf


def _render(data, index=0, dpi=72, gray=False):
    with raster.open_pdf(data) as s:
        return s.render(index, dpi, gray=gray)


def _px(img, x, y):
    return img.getpixel((x, y))


# ---- geometry: pixel size = ceil(points * dpi / 72), rotation/crop/offset/UserUnit aware -------------

@pytest.mark.parametrize("dpi", [50, 100, 150, 300])
def test_pixel_size_is_ceil_of_points(dpi):
    img = _render(make_pdf(), dpi=dpi)
    assert img.size == (math.ceil(595 * dpi / 72), math.ceil(842 * dpi / 72))


@pytest.mark.parametrize("rot", [90, 270])
def test_rotation_swaps_dimensions(rot):
    img = _render(make_pdf([{"rotate": rot}]), dpi=72)
    assert img.size == (842, 595)


def test_cropbox_and_mediabox_offset_define_the_page():
    img = _render(make_pdf([{"mediabox": [100, 200, 695, 1042], "cropbox": [150, 250, 450, 650]}]), dpi=72)
    assert img.size == (300, 400)


def test_fractional_size_rounds_up():
    img = _render(make_pdf([{"mediabox": [0, 0, 595.276, 841.89]}]), dpi=150)
    assert img.size == (math.ceil(595.276 * 150 / 72), math.ceil(841.89 * 150 / 72))


@pytest.mark.parametrize("objstm", [False, True])
def test_userunit_is_honoured_even_though_pdfium_ignores_it(objstm):
    img = _render(make_pdf([{"userunit": 2.0}], objstm=objstm), dpi=72)
    assert img.size == (1190, 1684)  # pdfium alone would give 595 x 842


def test_page_size_is_in_points_as_displayed():
    with raster.open_pdf(make_pdf([{"rotate": 90, "userunit": 2.0}])) as s:
        w, h = s.page_size(0)
    assert (round(w), round(h)) == (1684, 1190)


# ---- orientation: the red square starts lower-left of the UNROTATED page --------------------------

@pytest.mark.parametrize("rot,corner", [
    (0, "bl"),     # lower-left stays lower-left
    (90, "tl"),    # clockwise 90: lower-left goes to upper-left
    (180, "tr"),
    (270, "br"),
])
def test_content_orientation_follows_rotate(rot, corner):
    img = _render(make_pdf([{"rotate": rot}]), dpi=72)
    w, h = img.size
    pos = {"bl": (20, h - 20), "tl": (20, 20), "tr": (w - 20, 20), "br": (w - 20, h - 20)}
    for name, (x, y) in pos.items():
        red = _px(img, x, y) == (255, 0, 0)
        assert red == (name == corner), (rot, name, _px(img, x, y))


def test_background_is_white():
    img = _render(make_pdf(rects=[]), dpi=72)
    assert _px(img, 300, 400) == (255, 255, 255)


# ---- colour modes ---------------------------------------------------------------------------------

def test_gray_is_luminance_of_the_rgb_render():
    data = make_pdf()
    rgb, gray = _render(data, dpi=100), _render(data, dpi=100, gray=True)
    assert rgb.mode == "RGB" and gray.mode == "L"
    assert gray.tobytes() == rgb.convert("L").tobytes()  # documented: ITU-R 601 via Pillow, not pdfium's grayscale flag
    assert _px(gray, 20, gray.height - 20) == 76          # pure red -> luminance 76


# ---- annotations and form fields are drawn (white-background render of what a viewer shows) -----------

def test_annotation_appearance_is_drawn():
    img = _render(make_pdf(annot=True), dpi=72)
    assert _px(img, 250, 842 - 250) == (0, 255, 0)
    assert _px(_render(make_pdf(), dpi=72), 250, 842 - 250) == (255, 255, 255)


def test_form_field_widget_is_drawn():
    img = _render(make_pdf(widget=True), dpi=72)
    assert _px(img, 450, 842 - 250) == (0, 0, 255)


# ---- failure modes ----------------------------------------------------------------------------------

def test_encrypted_with_empty_password_renders():
    img = _render(make_pdf(encrypt=True), dpi=72)
    assert _px(img, 20, img.height - 20) == (255, 0, 0)


def test_wrong_password_raises_rastererror():
    with pytest.raises(raster.RasterError):
        raster.open_pdf(encrypted_with_password()).__enter__()


def test_damaged_xref_is_repaired_by_the_backend():
    img = _render(broken_xref(make_pdf()), dpi=72)
    assert _px(img, 20, img.height - 20) == (255, 0, 0)


@pytest.mark.parametrize("junk", [b"", b"not a pdf at all", b"%PDF-1.4\n%%EOF"])
def test_garbage_raises_rastererror(junk):
    with pytest.raises(raster.RasterError):
        with raster.open_pdf(junk):
            pass


def test_out_of_range_page_raises_indexerror():
    with raster.open_pdf(make_pdf(pages=2)) as s:
        assert s.page_count == 2
        with pytest.raises(IndexError):
            s.render(2, 72)
        with pytest.raises(IndexError):
            s.render(-1, 72)


def test_session_is_closed_after_use_and_close_is_idempotent():
    s = raster.open_pdf(make_pdf())
    s.close()
    s.close()
    with pytest.raises(raster.RasterError):
        s.render(0, 72)


def test_absurd_pixel_request_is_refused_not_allocated():
    with raster.open_pdf(make_pdf()) as s:
        with pytest.raises(raster.RasterError):
            s.render(0, 100_000)


# ---- backend selection ------------------------------------------------------------------------------

def test_default_backend_is_pdfium(monkeypatch):
    monkeypatch.delenv("BELEG_RASTER", raising=False)
    assert raster.get_backend().name == "pdfium"


def test_unknown_backend_name_falls_back_to_pdfium(monkeypatch):
    monkeypatch.setenv("BELEG_RASTER", "gibt-es-nicht")
    assert raster.get_backend().name == "pdfium"


def test_registered_backend_is_selected_by_env(monkeypatch):
    class Fake:
        name = "fake"

        def open(self, raw, background=None):
            raise raster.RasterError("fake")

    monkeypatch.setitem(raster._FACTORIES, "fake", Fake)
    monkeypatch.setenv("BELEG_RASTER", "fake")
    assert raster.get_backend().name == "fake"
    with pytest.raises(raster.RasterError):
        raster.open_pdf(make_pdf())


# ---- the process-wide lock (pdfium is not thread safe) ----------------------------------------------

def test_priority_lock_is_exclusive():
    lock = raster.PriorityLock()
    inside, peak, errors = [0], [0], []

    def work():
        for _ in range(200):
            lock.acquire(background=True)
            try:
                inside[0] += 1
                peak[0] = max(peak[0], inside[0])
                inside[0] -= 1
            finally:
                lock.release()

    ts = [threading.Thread(target=work) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert peak[0] == 1 and not errors


def test_foreground_overtakes_waiting_background():
    lock = raster.PriorityLock()
    order = []
    lock.acquire(background=True)  # a background render is running

    def waiter(name, bg):
        lock.acquire(background=bg)
        order.append(name)
        lock.release()

    bgs = [threading.Thread(target=waiter, args=(f"bg{i}", True)) for i in range(3)]
    [t.start() for t in bgs]
    time.sleep(0.1)               # the background waiters are queued first
    fg = threading.Thread(target=waiter, args=("fg", False))
    fg.start()
    time.sleep(0.1)
    lock.release()
    [t.join(5) for t in bgs + [fg]]
    assert order[0] == "fg", order
    assert sorted(order) == ["bg0", "bg1", "bg2", "fg"]


def test_open_foreground_session_keeps_background_work_out_between_its_calls():
    """An interactive page = open + size + render (several lock acquisitions): background work must not slip in
    between them, or the page waits for a whole background render at EVERY step (measured ~3x single-page latency)."""
    data = make_pdf()
    got = []

    def background():
        raster.PDFIUM_LOCK.acquire(background=True)
        got.append(1)
        raster.PDFIUM_LOCK.release()

    fg = raster.open_pdf(data, background=False)
    t = threading.Thread(target=background)
    t.start()
    fg.page_size(0)
    fg.render(0, 50)
    time.sleep(0.1)
    assert not got, "background work ran while a foreground session was open"
    fg.close()
    t.join(5)
    assert got == [1]


def test_background_session_does_not_block_other_background_work():
    bg = raster.open_pdf(make_pdf(), background=True)
    try:
        raster.PDFIUM_LOCK.acquire(background=True)  # would deadlock if a bg session held priority
        raster.PDFIUM_LOCK.release()
    finally:
        bg.close()


def test_failed_foreground_open_releases_its_priority():
    with pytest.raises(raster.RasterError):
        raster.open_pdf(b"%PDF-1.4 kaputt", background=False)
    raster.PDFIUM_LOCK.acquire(background=True)  # must not wait forever
    raster.PDFIUM_LOCK.release()


def test_threads_with_own_sessions_render_identical_bytes():
    """8 threads x 25 pages over shared + separate sessions vs. the single-thread reference."""
    data = make_pdf(pages=5, rects=[(10, 10, 300, 300, (0.2, 0.4, 0.9))])
    ref = [_render(data, i % 5, dpi=60).tobytes() for i in range(5)]
    bad, errors = [], []

    def work(tid):
        try:
            for k in range(25):
                i = (tid + k) % 5
                with raster.open_pdf(data, background=bool(tid % 2)) as s:
                    if s.render(i, 60).tobytes() != ref[i]:
                        bad.append((tid, k))
        except Exception as e:  # pragma: no cover
            errors.append(repr(e))

    ts = [threading.Thread(target=work, args=(t,)) for t in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors and not bad


def test_pool_threads_are_background_threads():
    from belegtool_compress import cpu
    assert cpu.is_background_thread() is False
    seen = []
    t = threading.Thread(target=lambda: (cpu.set_current_thread_below_normal(), seen.append(cpu.is_background_thread())))
    t.start()
    t.join()
    assert seen == [True]
