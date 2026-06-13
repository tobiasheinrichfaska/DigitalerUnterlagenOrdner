"""Golden Office/ODF -> PDF round-trip through office_via_com (REAL Office, Windows).

For each committed fixture in tests/data/input/ (see office_fixtures.SENTINELS) this
runs the actual COM conversion and asserts, **structurally**:
  - the output starts with %PDF,
  - it has exactly 1 page,
  - the file's sentinel survives into the rendered PDF text.

Structural (page count + key text), NOT byte-equality — Office output isn't
deterministic across versions/machines. Runs in the DEFAULT suite, but auto-skips
where Office/COM isn't available (non-Windows, or the specific app not installed),
so it never fails portability; it actively runs only on a real Office machine —
which is the whole point (it is the first real-Office check that the ODF
.odt/.ods/.odp routing actually converts, beyond the mocked-COM unit tests in
test_office_convert.py). Marked `office`; opt out with `pytest -m "not office"`.

(Re)generate the inputs with tests/make_office_fixtures.py.
"""
import sys

import pytest

# `office`: needs a REAL Office install + COM (it launches Word/Excel/PowerPoint).
# Runs in the default suite; auto-skips without Office. Opt out with -m "not office".
pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(sys.platform != "win32",
                       reason="office_via_com is Windows + COM only"),
]


@pytest.fixture(autouse=True)
def _quiet_faulthandler():
    """Office COM apartments raise/handle benign SEH on Quit (e.g. 0x80010108
    RPC_E_DISCONNECTED); pytest's faulthandler echoes them as scary 'Windows fatal
    exception' dumps even though they're caught and the run exits 0. Mute faulthandler
    for the duration of these tests, then restore it."""
    import faulthandler
    was_enabled = faulthandler.is_enabled()
    faulthandler.disable()
    try:
        yield
    finally:
        if was_enabled:
            faulthandler.enable()

import fitz  # noqa: E402  (PyMuPDF — read back the produced PDF)

from office_fixtures import INPUT_DIR, SENTINELS  # noqa: E402
from universal_importer.converters import office_via_com  # noqa: E402

_PROGID = {
    ".docx": "Word.Application", ".odt": "Word.Application",
    ".xlsx": "Excel.Application", ".ods": "Excel.Application",
    ".pptx": "PowerPoint.Application", ".odp": "PowerPoint.Application",
}


def _office_app_available(ext: str) -> bool:
    """True if the COM app that converts ``ext`` is registered (installed). A registry
    ProgID lookup — so we do NOT launch the app just to probe it (that doubled the COM
    churn). Lets the test SKIP (not fail) where e.g. Excel/PowerPoint isn't installed."""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, _PROGID[ext]):
            return True
    except OSError:
        return False


@pytest.mark.parametrize("fname,sentinel", sorted(SENTINELS.items()))
def test_office_golden_roundtrip(fname, sentinel):
    path = INPUT_DIR / fname
    if not path.exists():
        pytest.skip(f"fixture missing: {fname} (run tests/make_office_fixtures.py)")
    ext = path.suffix.lower()
    if not _office_app_available(ext):
        pytest.skip(f"Office app for {ext} not available on this machine")

    result = office_via_com(str(path), ext)
    data = result.data.getvalue()
    assert data.startswith(b"%PDF"), f"{fname}: output is not a PDF"

    with fitz.open(stream=data, filetype="pdf") as doc:
        assert doc.page_count == 1, f"{fname}: expected 1 page, got {doc.page_count}"
        text = "".join(page.get_text() for page in doc)

    # whitespace-insensitive: PDF text extraction can insert/drop spaces
    assert sentinel in "".join(text.split()), \
        f"{fname}: sentinel {sentinel!r} not found in converted PDF text"
