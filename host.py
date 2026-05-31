"""pywebview host — the single warm process for the React UI.

Embeds the data-driven core (core.api.CoreApi) and exposes it to the React app as
``window.pywebview.api.*``. HostApi adds the methods that need the native window
(open/save file dialogs); everything else delegates to CoreApi. One Python
process; the React build is just static assets.

Run:
  - dev:  cd webui && npm run dev ; then  set BELEG_DEV=1 ; python host.py
  - prod: cd webui && npm run build ; then  python host.py
"""

import os

import webview

from core.api import CoreApi

HERE = os.path.dirname(os.path.abspath(__file__))
DEV_URL = "http://localhost:5173"
PROD_INDEX = os.path.join(HERE, "webui", "dist", "index.html")
FILE_TYPES = ("BelegTool (*.belegtool)", "PDF (*.pdf)", "Alle Dateien (*.*)")


class HostApi:
    """JS-facing API: CoreApi ops + native file dialogs (need the window)."""

    def __init__(self):
        self.core = CoreApi()
        self.window = None  # set after the window is created

    # core ops (delegate)
    def open(self, session=None, path=None):
        return self.core.open(session, path)

    def dispatch(self, session, command):
        return self.core.dispatch(session, command)

    def undo(self, session):
        return self.core.undo(session)

    def redo(self, session):
        return self.core.redo(session)

    def render(self, session, node_id, dpi=100):
        return self.core.render(session, node_id, dpi)

    # host-only ops (native dialogs)
    def open_file(self, session=None):
        result = self.window.create_file_dialog(webview.OPEN_DIALOG, file_types=FILE_TYPES)
        if not result:
            return {"ok": False, "error": "cancelled"}
        return self.core.open(session, result[0])

    def save_file(self, session):
        path = self.window.create_file_dialog(
            webview.SAVE_DIALOG, save_filename="unbenannt.belegtool",
            file_types=("BelegTool (*.belegtool)",))
        if not path:
            return {"ok": False, "error": "cancelled"}
        if isinstance(path, (tuple, list)):
            path = path[0]
        return self.core.save(session, path)


def main():
    api = HostApi()
    entry = DEV_URL if os.environ.get("BELEG_DEV") else PROD_INDEX
    api.window = webview.create_window(
        "DigitalerBelegeOrdner", entry, js_api=api,
        width=1280, height=820, min_size=(900, 600))
    webview.start()


if __name__ == "__main__":
    main()
