import pytest
import status_display

class DummyRoot:
    def __init__(self):
        self.titles = []

    def title(self, text):
        self.titles.append(text)

    def after(self, delay, func):
        # Keine echte Schleife – sofort zurückgeben
        return "dummy_id"

@pytest.fixture
def dummy_root():
    return DummyRoot()

def test_set_base_title():
    status_display.set_base_title("BelegTool")
    # kein assert möglich, da intern gespeichert – nur kein Fehler

def test_register_unregister_task(dummy_root):
    status_display.start_title_loop(dummy_root)

    status_display.register_task("Kompression")
    assert any("Kompression" in t for t in dummy_root.titles)

    status_display.unregister_task("Kompression")
    assert dummy_root.titles[-1].startswith("BelegTool") or "Kompression" not in dummy_root.titles[-1]
