# Datei: tests/conftest.py
import pytest
import gc
import tkinter
import shutil
from pathlib import Path

from belegtool_main import DigitalerBelegGUI

OUTPUT_DIR = Path(__file__).parent / "data" / "output"

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