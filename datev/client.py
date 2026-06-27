"""DATEVconnect DMS v2 read client (round 1), governed by the probe GUI. HTTP is injected
(Transport) so this is unit-tested with a fake — no live DATEVconnect. Errors are mapped to
DatevAuthError (401) / DatevLicenseError (missing component license) / DatevError."""
import base64
import json

from .endpoints import ENDPOINTS, build_url
from .types import DatevAuthError, DatevError, DatevLicenseError

_LICENSE_HINTS = ("lizenz", "license", "k0001928", "63218")


def _text(b):
    if isinstance(b, (bytes, bytearray)):
        return b.decode("utf-8", "replace")
    return b or ""


def _error_from_body(text, status, name):
    desc = text
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            desc = parsed.get("error_description") or parsed.get("error") or text
    except (ValueError, TypeError):
        pass
    if any(h in (desc or "").lower() for h in _LICENSE_HINTS):
        return DatevLicenseError(desc, status, text)
    return DatevError(desc or f"DATEV {name} fehlgeschlagen ({status})", status, text)


class DatevConnectClient:
    def __init__(self, config, transport):
        self._cfg = config
        self._transport = transport
        self._auth = None
        if config.username and config.password:
            raw = f"{config.username}:{config.password}".encode("utf-8")
            self._auth = "Basic " + base64.b64encode(raw).decode("ascii")

    def _send(self, name, params=None, query=None, accept="application/json"):
        method, tmpl = ENDPOINTS[name]
        url = build_url(self._cfg.base_url, tmpl, params, query)
        headers = {"Accept": accept}
        if self._auth:
            headers["Authorization"] = self._auth
        res = self._transport(method, url, headers, None)
        if res.status == 401:
            raise DatevAuthError("Nicht autorisiert (401) — Anmeldedaten prüfen.",
                                 res.status, _text(res.body))
        if res.status >= 400:
            raise _error_from_body(_text(res.body), res.status, name)
        return res

    def _json(self, name, **kw):
        res = self._send(name, accept="application/json", **kw)
        try:
            parsed = json.loads(_text(res.body) or "null")
        except ValueError:
            raise DatevError(f"Ungültiges JSON von {name}", res.status, _text(res.body))
        # DATEVconnect can return a license/error envelope WITH a 2xx status.
        if isinstance(parsed, dict) and ("error_description" in parsed or "error" in parsed):
            raise _error_from_body(_text(res.body), res.status, name)
        return parsed

    # --- read API (round 1) ------------------------------------------------
    def get_info(self):
        """The active-data-path info, incl. ``feature`` = DokAB / DokAbRev / DMS."""
        return self._json("info")

    def list_domains(self, filter=None):
        return self._json("domains", query={"filter": filter})

    def list_documents(self, filter=None, top=None, skip=None):
        return self._json("documents", query={"filter": filter, "top": top, "skip": skip})

    def get_document(self, doc_id):
        return self._json("document", params={"id": doc_id})

    def list_structure_items(self, doc_id):
        return self._json("structure_items", params={"id": doc_id})

    def get_document_file(self, file_id):
        """The raw bytes of a document file (binary; octet-stream)."""
        res = self._send("document_file", params={"file_id": file_id},
                         accept="application/octet-stream")
        return res.body
