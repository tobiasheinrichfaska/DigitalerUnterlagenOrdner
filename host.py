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
    """JS-facing API: CoreApi ops + native file dialogs.

    Note: do NOT store the pywebview window as an attribute here — pywebview
    serialises the js_api object and recurses infinitely into the .NET window.
    Fetch it on demand via ``webview.windows[0]`` instead.
    """

    def __init__(self):
        self._core = CoreApi()

    # core ops (delegate)
    def config(self):
        return self._core.config()

    def open(self, session=None, path=None):
        return self._core.open(session, path)

    def dispatch(self, session, command):
        return self._core.dispatch(session, command)

    def undo(self, session):
        return self._core.undo(session)

    def redo(self, session):
        return self._core.redo(session)

    def render(self, session, node_id, dpi=100):
        return self._core.render(session, node_id, dpi)

    def compress_options(self, session, node_id, dpi=150):
        return self._core.compress_options(session, node_id, dpi)

    # host-only ops (native dialogs)
    def open_file(self, session=None):
        result = webview.windows[0].create_file_dialog(webview.FileDialog.OPEN, file_types=FILE_TYPES)
        if not result:
            return {"ok": False, "error": "cancelled"}
        return self._core.open(session, result[0])

    def save_file(self, session):
        path = webview.windows[0].create_file_dialog(
            webview.FileDialog.SAVE, save_filename="unbenannt.belegtool",
            file_types=("BelegTool (*.belegtool)",))
        if not path:
            return {"ok": False, "error": "cancelled"}
        if isinstance(path, (tuple, list)):
            path = path[0]
        return self._core.save(session, path)


def main():
    api = HostApi()
    entry = DEV_URL if os.environ.get("BELEG_DEV") else PROD_INDEX
    webview.create_window(
        "DigitalerBelegeOrdner", entry, js_api=api,
        width=1280, height=820, min_size=(900, 600))
    webview.start()


if __name__ == "__main__":
    main()
