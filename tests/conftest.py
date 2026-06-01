# Datei: tests/conftest.py
import pytest
import gc
import tkinter
import shutil
from pathlib import Path

from belegtool_main import DigitalerBelegGUI

OUTPUT_DIR = Path(__file__).parent / "data" / "output"

# Keep the test run headless: the legacy GUI tests create real Tk roots, which
# otherwise flash visible windows. Withdraw every root at creation — patched once
# here so it also covers TkinterDnD.Tk and DigitalerBelegGUI (both subclass Tk).
_orig_tk_init = tkinter.Tk.__init__


def _withdrawn_tk_init(self, *args, **kwargs):
    _orig_tk_init(self, *args, **kwargs)
    try:
        self.withdraw()
    except Exception:
        pass


tkinter.Tk.__init__ = _withdrawn_tk_init

@pytest.fixture
def app():
    """Robustes GUI-Fenster mit sauberem Zustand und Memory Reset."""
    gui = DigitalerBelegGUI()
    gui.update()
    yield gui
    gui.destroy()
    gui.update_idletasks()

    # Speicher + Zustand zurücksetzen
    del gui
    gc.collect()
    tkinter._default_root = None

@pytest.fixture(autouse=True, scope="session")
def clean_output_dir():
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)