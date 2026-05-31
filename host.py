"""pywebview host — the single warm process for the React UI.

Embeds the data-driven core (core.api.CoreApi) and exposes it to the React app as
``window.pywebview.api.*`` (open / dispatch / undo / redo), then opens a WebView2
window. The whole app is one Python process; the React build is just static assets.

Run:
  - dev:  start the Vite dev server (cd webui && npm run dev), then
          set BELEG_DEV=1 and run `python host.py`  (hot reload in the window)
  - prod: `python host.py`  -> loads the built webui/dist/index.html
"""

import os

import webview

from core.api import CoreApi

HERE = os.path.dirname(os.path.abspath(__file__))
DEV_URL = "http://localhost:5173"
PROD_INDEX = os.path.join(HERE, "webui", "dist", "index.html")


def main():
    api = CoreApi()  # the in-process core, exposed to JS as window.pywebview.api
    entry = DEV_URL if os.environ.get("BELEG_DEV") else PROD_INDEX
    webview.create_window(
        "DigitalerBelegeOrdner",
        entry,
        js_api=api,
        width=1280,
        height=820,
        min_size=(900, 600),
    )
    webview.start()


if __name__ == "__main__":
    main()
