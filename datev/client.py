"""DATEVconnect DMS v2 client, governed by the probe GUI. Round 1 = read; round 2a adds
CREATE-ONLY writes (upload a file, create a document) + the master-data client lookup that
turns a Mandant number into the required ``correspondence_partner_guid``. HTTP is injected
(Transport) so this is unit-tested with a fake — no live DATEVconnect. Errors are mapped to
DatevAuthError (401) / DatevLicenseError (missing component license) / DatevError."""
import base64
import json

from .config import master_data_base_url
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
    def __init__(self, config, transport, master_data_base=None):
        self._cfg = config
        self._transport = transport
        # master-data lives at a different path on the same host (round 2); derive if not given.
        self._md_base = master_data_base or master_data_base_url(config.base_url)
        self._auth = None
        if config.username and config.password:
            raw = f"{config.username}:{config.password}".encode("utf-8")
            self._auth = "Basic " + base64.b64encode(raw).decode("ascii")

    def _headers(self, accept="application/json", content_type=None):
        headers = {"Accept": accept}
        if content_type:
            headers["Content-Type"] = content_type
        if self._auth:
            headers["Authorization"] = self._auth
        return headers

    def _check(self, res, name):
        if res.status == 401:
            raise DatevAuthError("Nicht autorisiert (401) — Anmeldedaten prüfen.",
                                 res.status, _text(res.body))
        if res.status >= 400:
            raise _error_from_body(_text(res.body), res.status, name)
        return res

    def _send(self, name, params=None, query=None, accept="application/json",
              body=None, content_type=None):
        method, tmpl = ENDPOINTS[name]
        url = build_url(self._cfg.base_url, tmpl, params, query)
        res = self._transport(method, url, self._headers(accept, content_type), body)
        return self._check(res, name)

    def _send_url(self, method, url, name, accept="application/json", body=None,
                  content_type=None):
        """Like ``_send`` but to an arbitrary URL (master-data lives off the DMS base)."""
        res = self._transport(method, url, self._headers(accept, content_type), body)
        return self._check(res, name)

    def _as_json(self, res, name):
        try:
            parsed = json.loads(_text(res.body) or "null")
        except ValueError:
            raise DatevError(f"Ungültiges JSON von {name}", res.status, _text(res.body))
        # DATEVconnect can return a license/error envelope WITH a 2xx status.
        if isinstance(parsed, dict) and ("error_description" in parsed or "error" in parsed):
            raise _error_from_body(_text(res.body), res.status, name)
        return parsed

    def _json(self, name, **kw):
        return self._as_json(self._send(name, accept="application/json", **kw), name)

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

    def get_document_raw(self, doc_id):
        """GET /documents/{id} returning the HTTP status + raw body verbatim (no parsing/
        filtering) — the decisive existence check: 200 with real data = exists, 404 = never
        persisted. A >=400 raises (so the status/body still surface via the error path)."""
        res = self._send("document", params={"id": doc_id}, accept="application/json")
        return {"http_status": res.status, "raw_body": _text(res.body),
                "location": res.headers.get("location")}

    def list_structure_items(self, doc_id):
        return self._json("structure_items", params={"id": doc_id})

    def get_document_file(self, file_id):
        """The raw bytes of a document file (binary; octet-stream)."""
        res = self._send("document_file", params={"file_id": file_id},
                         accept="application/octet-stream")
        return res.body

    # --- master-data (round 2a): Mandant number -> correspondence_partner_guid ----------
    def list_clients(self):
        """All clients from Client-Master-Data. A list (or an envelope with a ``clients``
        array) of ``{id (GUID), number, name, …}``."""
        url = self._md_base.rstrip("/") + "/clients"
        return self._as_json(self._send_url("GET", url, "clients"), "clients")

    def resolve_client_guid(self, number):
        """The GUID (``Client.id``) for a Mandant number — the required
        ``correspondence_partner_guid`` for a document create. Raises if not found."""
        want = str(number).strip()
        data = self.list_clients()
        clients = data.get("clients", data) if isinstance(data, dict) else data
        for c in (clients or []):
            if str(c.get("number", "")).strip() == want:
                guid = c.get("id")
                if guid:
                    return {"guid": guid, "name": c.get("name"), "number": c.get("number")}
        raise DatevError(f"Mandant {want} nicht gefunden (Client-Stammdaten).")

    # --- create only (round 2a) ---------------------------------------------------------
    def upload_document_file(self, pdf_bytes):
        """POST the file bytes (octet-stream) -> the new ``document_file_id`` (int)."""
        res = self._send("document_files_create", accept="application/json",
                         body=pdf_bytes, content_type="application/octet-stream")
        parsed = self._as_json(res, "document_files_create")
        file_id = parsed.get("id") if isinstance(parsed, dict) else None
        if file_id is None:
            raise DatevError("Kein document_file_id in der Upload-Antwort.", res.status,
                             _text(res.body))
        # DATEV returns the id as a STRING, but DocumentCreate.structure_items[].document_file_id
        # is typed integer — sending the string leaves the file unbound (structure-less doc).
        if isinstance(file_id, str) and file_id.strip().lstrip("-").isdigit():
            file_id = int(file_id)
        return file_id

    def create_document(self, payload):
        """POST a DocumentCreate body -> the created Document. The live box may answer 201 with
        an empty body and the new id only in the ``Location`` header, so we fall back to that
        (and always surface the HTTP status) instead of returning a confusing empty result."""
        body = json.dumps(payload).encode("utf-8")
        res = self._send("documents_create", accept="application/json",
                         body=body, content_type="application/json")
        text = _text(res.body).strip()
        parsed = None
        if text:
            try:
                parsed = json.loads(text)
            except ValueError:
                raise DatevError(f"Ungültiges JSON von documents_create", res.status, text)
            if isinstance(parsed, dict) and ("error_description" in parsed or "error" in parsed):
                raise _error_from_body(text, res.status, "documents_create")
        if isinstance(parsed, dict) and parsed.get("id"):
            parsed.setdefault("http_status", res.status)
            return parsed
        # empty/idless body: recover the created id from Location (201 Created)
        loc = res.headers.get("location")
        result = {"http_status": res.status}
        if loc:
            result["location"] = loc
            result["id"] = loc.rstrip("/").split("/")[-1]
        elif parsed is not None:
            result["body"] = parsed
        return result
