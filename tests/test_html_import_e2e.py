# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""End-to-end guard for the HTML/e-mail import (security review 2026-11-25, finding H-1).

``block_remote_link`` returning ``None`` does NOT block anything in xhtml2pdf: it falls back to
the ORIGINAL uri when the callback result is falsy. The unit tests of the callback alone
therefore proved nothing. These tests run the real ``html_to_pdf`` against a local HTTP server
and a local image file and assert that nothing is fetched / embedded.
"""

import base64
import http.server
import io
import threading

import pytest

pytest.importorskip("xhtml2pdf")
fitz = pytest.importorskip("fitz")

from universal_importer.converters import html_to_pdf  # noqa: E402

# 1x1 PNG
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg=="
)


@pytest.fixture()
def server():
    hits = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.end_headers()
            self.wfile.write(_PNG)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv, hits
    finally:
        srv.shutdown()
        srv.server_close()


def _image_sizes(result) -> list:
    """(width, height) of every image embedded in the PDF."""
    doc = fitz.open(stream=result.data.getvalue(), filetype="pdf")
    try:
        return [(img[2], img[3]) for p in doc for img in p.get_images()]
    finally:
        doc.close()


@pytest.mark.parametrize("snippet", [
    '<img src="{url}/px.png?v=1">',
    '<div style="background-image:url({url}/bg.png)">x</div>',
    '<style>div{{background:url("{url}/bg2.png")}}</style><div>x</div>',
    "<style>@import url({url}/a.css);</style><p>x</p>",
    '<style>@import "{url}/b.css";</style><p>x</p>',
    '<link rel="stylesheet" href="{url}/c.css"><p>x</p>',
    '<pdf:embed src="{url}/e.pdf" />',
    '<table background="{url}/t.png"><tr><td>x</td></tr></table>',
    '<img src="//127.0.0.1:{port}/proto.png">',
])
def test_html_import_never_contacts_the_network(server, snippet):
    srv, hits = server
    url = f"http://127.0.0.1:{srv.server_port}"
    html = "<html><body>" + snippet.format(url=url, port=srv.server_port) + "</body></html>"
    html_to_pdf(html, "mail.pdf")
    assert hits == [], f"importer fetched {hits}"


def test_html_import_does_not_embed_a_local_image(tmp_path):
    from PIL import Image
    secret = tmp_path / "secret_scan.png"
    Image.new("RGB", (7, 5), (200, 10, 10)).save(secret)  # distinctive size: 7x5
    for src in (str(secret), secret.as_uri(), "secret_scan.png"):
        res = html_to_pdf(f'<html><body><img src="{src}"></body></html>', "m.pdf")
        assert (7, 5) not in _image_sizes(res), f"local file embedded via {src!r}"


def test_html_import_keeps_inline_data_images():
    data = "data:image/png;base64," + base64.b64encode(_PNG).decode()
    res = html_to_pdf(f'<html><body><p>hi</p><img src="{data}"></body></html>', "m.pdf")
    assert _image_sizes(res) == [(1, 1)]
