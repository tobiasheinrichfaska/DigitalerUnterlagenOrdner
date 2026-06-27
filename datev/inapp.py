"""In-app DATEV orchestration — the glue the BelegTool host calls in **DATEV mode only**.

Sits on top of the (tested, injected-transport) ``DatevConnectClient`` and the pure
``writeback``/``provenance`` helpers, and turns the open/save/file-anew flows of
``docs/datev-integration-design.md`` into concrete steps:

- **capture** a document's DATEV origin from its checkout path (+ the open-time baseline),
- **write back** edited bytes to an existing DATEV document, **guarded** by ``decide_save_back``
  (DokAb keeps no revision, so the overwrite is permanent — never write on a failed guard),
- **file** a not-connected document (or an exported PDF) as a NEW DATEV document,
- look up the **same client** of an existing document (for "export → file under the same Mandant").

The ``DatevConnectClient`` is **injected**, so every orchestration step is unit-tested with a
fake client — no live DATEVconnect. Live wiring (SSO curl transport, ``GET /info``) is in
``connect()`` and is the only part not exercised by the unit tests.
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime

from .provenance import parse_checkout_path
from .types import program_keeps_revisions
from .writeback import OK, decide_save_back


def sha256(data) -> str:
    return hashlib.sha256(data or b"").hexdigest()


def _now_iso():
    # DATEV wants a naive local ISO timestamp (seconds) for the structure item dates.
    return datetime.now().replace(microsecond=0).isoformat()


def pick_connection_user(users, my_sid=None):
    """Choose the document ``user`` GUID from an IAM **SCIM** user list. Prefers the user
    whose ``linked_windows_identity.value`` (Windows SID) matches the connecting user;
    falls back to the first ACTIVE user. Returns ``{id, name, sid}`` or None.

    Accepts either the raw SCIM envelope (``{resources:[...]}``) or a plain list."""
    resources = users.get("resources", users) if isinstance(users, dict) else users
    parsed = []
    for u in (resources or []):
        if not isinstance(u, dict):
            continue
        sid = ((u.get("linked_windows_identity") or {}).get("value")
               if isinstance(u.get("linked_windows_identity"), dict) else None)
        active = u.get("active", True)
        if u.get("is_deleted"):
            active = False
        parsed.append({"id": u.get("id"), "name": u.get("display_name") or u.get("name"),
                       "sid": sid, "active": active})
    if my_sid:
        for u in parsed:
            if u["sid"] and u["sid"].lower() == str(my_sid).lower() and u["id"]:
                return {"id": u["id"], "name": u["name"], "sid": u["sid"]}
    for u in parsed:
        if u["active"] and u["id"]:
            return {"id": u["id"], "name": u["name"], "sid": u["sid"]}
    return None


def build_create_payload(*, file_id, client_guid, description, user_guid, domain_id=1,
                         folder_id=None, register_id=None, structure_name="beleg.pdf",
                         created=None):
    """Pure: the DocumentCreate body for a class-1 ("Dokument") create — the mandatory
    set proven on the live box (class · correspondence_partner_guid · description · domain ·
    user · one structure_item with counter/parent_counter + the dates + the int file id).
    **No `state` for class 1.** ``folder``/``register`` are optional placement."""
    when = created or _now_iso()
    payload = {
        "class": {"id": 1},
        "correspondence_partner_guid": client_guid,
        "description": description,
        "domain": {"id": int(domain_id)},
        "user": {"id": user_guid},
        "structure_items": [{
            "name": structure_name, "type": 1,
            "counter": 1, "parent_counter": 0,
            "creation_date": when, "last_modification_date": when,
            "document_file_id": int(file_id),
        }],
    }
    if folder_id is not None:
        payload["folder"] = {"id": int(folder_id)}
    if register_id is not None:
        payload["register"] = {"id": int(register_id)}
    return payload


def structure_item_id_for_file(structure_items, file_id):
    """The STABLE structure-item id whose ``document_file_id`` matches the checkout path's
    ``file_id`` — the durable PUT handle (``document_file_id`` changes per version, the
    structure-item id does not). Accepts the SCIM-ish envelope or a plain list. None if absent."""
    items = (structure_items.get("structure_items", structure_items)
             if isinstance(structure_items, dict) else structure_items)
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        if it.get("document_file_id") == file_id and it.get("id") is not None:
            return it["id"]
    return None


class DatevService:
    """Live in-app DATEV operations over an (injected) ``DatevConnectClient``. DATEV-mode
    only; built lazily by ``CoreApi`` when the user's settings enable DATEV mode."""

    def __init__(self, client, feature=None, my_sid=None):
        self._client = client
        self.feature = feature
        self._my_sid = my_sid

    # --- construction (the only live-wired part) ---------------------------
    @classmethod
    def connect(cls, settings=None, client=None, my_sid=None):
        """Build a live service: an SSO-curl ``DatevConnectClient`` against the configured
        DMS base, probed once with ``GET /info`` (→ ``feature``). ``client`` may be injected
        (tests / a pre-built client); otherwise it is constructed from ``settings``
        (``dms_base_url`` override, else the loopback default)."""
        if client is None:
            from .config import dms_base_url, self_signed_allowed
            from .transport import make_curl_sso_transport
            from .client import DatevConnectClient
            from .types import DatevConfig
            # Normalize the settings override through dms_base_url() too, so a host-only
            # override (no /datev/api/dms/v2 path) gets the DMS path pinned — same as the
            # file-based config path. No override ⇒ the loopback default.
            override = (settings or {}).get("dms_base_url")
            base = dms_base_url({"base_url": override}) if override else dms_base_url({})
            allow_self_signed = self_signed_allowed({}, base)
            cfg = DatevConfig(base_url=base, allow_self_signed=allow_self_signed)
            client = DatevConnectClient(cfg, make_curl_sso_transport(allow_self_signed))
        feature = None
        try:
            feature = (client.get_info() or {}).get("feature")
        except Exception:
            feature = None
        if my_sid is None:
            my_sid = _current_user_sid()
        return cls(client, feature=feature, my_sid=my_sid)

    def status(self) -> dict:
        keeps = program_keeps_revisions(self.feature)
        return {"ok": True, "connected": self.feature is not None,
                "feature": self.feature, "keeps_revisions": keeps}

    # --- on open: capture provenance + baseline ----------------------------
    def capture_provenance(self, path, opened_bytes):
        """If ``path`` is a DATEV checkout path, return ``(provenance, baseline)`` else
        ``(None, None)``. ``provenance`` = ``{doc_guid, file_id, structure_item_id,
        correspondence_partner_guid, source_name}`` (persisted on the node); ``baseline`` =
        ``{open_change_dt, was_checked_out_at_open, opened_sha256}`` (runtime only — the
        opened file IS the server file at open, so its hash is the content guard)."""
        parsed = parse_checkout_path(path)
        if not parsed.get("doc_guid"):
            return None, None
        doc_guid = parsed["doc_guid"]
        file_id = parsed.get("file_id")
        prov = {"doc_guid": doc_guid, "file_id": file_id,
                "structure_item_id": None, "correspondence_partner_guid": None,
                "source_name": os.path.basename(str(path)) or None}
        baseline = {"open_change_dt": None, "was_checked_out_at_open": False,
                    "opened_sha256": sha256(opened_bytes)}
        try:
            doc = self._client.get_document(doc_guid) or {}
            baseline["open_change_dt"] = doc.get("change_date_time")
            baseline["was_checked_out_at_open"] = bool(doc.get("checked_out"))
            prov["correspondence_partner_guid"] = doc.get("correspondence_partner_guid")
        except Exception:
            pass
        if file_id is not None:
            try:
                sid = structure_item_id_for_file(
                    self._client.list_structure_items(doc_guid), file_id)
                prov["structure_item_id"] = sid
            except Exception:
                pass
        return prov, baseline

    # --- on save: guarded write-back ---------------------------------------
    def writeback(self, provenance, baseline, edited_bytes, *, user_confirmed=True,
                  comment=None, backup_dir=None):
        """Guarded in-place write-back of ``edited_bytes`` to the connected DATEV document.
        Re-reads the server NOW, runs ``decide_save_back`` against the open-time baseline,
        and only on verdict ``ok`` performs upload + ``PUT structure-item`` (after backing up
        the just-fetched server bytes locally — the only undo on revision-less DokAb).
        Returns ``{ok, verdict, ...}``; any non-ok verdict means: do a filesystem save instead."""
        doc_guid = provenance.get("doc_guid")
        file_id = provenance.get("file_id")
        sid = provenance.get("structure_item_id")
        # re-read concurrency state + current server bytes
        try:
            doc = self._client.get_document(doc_guid) or {}
            remote_change_dt = doc.get("change_date_time")
            checked_out_now = bool(doc.get("checked_out"))
        except Exception as e:
            return {"ok": False, "verdict": "error", "error": str(e)}
        try:
            remote_bytes = self._client.get_document_file(file_id)
        except Exception as e:
            return {"ok": False, "verdict": "error", "error": str(e)}
        verdict = decide_save_back(
            user_confirmed=user_confirmed,
            was_checked_out_at_open=baseline.get("was_checked_out_at_open", False),
            checked_out_by_other_now=checked_out_now,
            open_change_dt=baseline.get("open_change_dt"),
            remote_change_dt=remote_change_dt,
            opened_sha256=baseline.get("opened_sha256"),
            remote_sha256=sha256(remote_bytes))
        if verdict != OK:
            return {"ok": False, "verdict": verdict}
        if sid is None:
            # no durable PUT handle (e.g. structure lookup failed at open) — refuse rather
            # than guess; the UI falls back to a filesystem save.
            return {"ok": False, "verdict": "no_structure_item"}
        backup_path = None
        if backup_dir:
            try:
                os.makedirs(backup_dir, exist_ok=True)
                # Defense-in-depth: this is a reusable service — never let a doc_guid /
                # file_id from a (possibly crafted) provenance inject path separators into
                # the backup filename. Keep only hex/dash/digits; the result stays inside
                # backup_dir regardless of caller (CoreApi also gates with valid_provenance).
                safe_guid = re.sub(r"[^0-9A-Fa-f-]", "", str(doc_guid))[:36] or "doc"
                safe_fid = re.sub(r"[^0-9]", "", str(file_id)) or "f"
                backup_path = os.path.join(
                    backup_dir, f"datev_backup_{safe_guid}_{safe_fid}.pdf")
                with open(backup_path, "wb") as f:
                    f.write(remote_bytes or b"")
            except OSError:
                backup_path = None
        # The guard has passed; the upload + PUT are the only steps that actually overwrite.
        # A mid-write network/HTTP/license error (or a non-int sid from a crafted provenance)
        # must surface as a clean verdict, NOT an unhandled exception across the JS bridge —
        # the local backup above is already written, so the user can still recover + save local.
        try:
            new_file_id = self._client.upload_document_file(edited_bytes)
            res = self._client.update_structure_item(doc_guid, sid, new_file_id,
                                                      revision_comment=comment)
        except Exception as e:
            return {"ok": False, "verdict": "error", "error": str(e),
                    "backup_path": backup_path}
        new_prov = dict(provenance)
        new_prov["file_id"] = new_file_id  # structure_item_id stays stable
        return {"ok": True, "verdict": OK, "new_file_id": new_file_id,
                "structure_item_id": sid, "http_status": res.get("http_status"),
                "backup_path": backup_path, "provenance": new_prov,
                "new_change_dt": self._safe_change_dt(doc_guid)}

    def _safe_change_dt(self, doc_guid):
        try:
            return (self._client.get_document(doc_guid) or {}).get("change_date_time")
        except Exception:
            return None

    # --- file a NEW document (create) --------------------------------------
    def client_guid_for_document(self, doc_guid):
        """The ``correspondence_partner_guid`` of an existing document — used to file an
        export under the **same client** as the connected source document."""
        try:
            return (self._client.get_document(doc_guid) or {}).get("correspondence_partner_guid")
        except Exception:
            return None

    def resolve_client(self, mandant_number):
        """Mandant number → ``{guid, name, number}`` (raises via the client if not found)."""
        return self._client.resolve_client_guid(mandant_number)

    def file_document(self, pdf_bytes, *, client_guid, description, domain_id=1,
                      folder_id=None, register_id=None, structure_name="beleg.pdf",
                      user_guid=None):
        """Create a NEW DATEV document from ``pdf_bytes`` (upload → create). Returns
        ``{ok, provenance}`` where provenance connects the working doc to the new document.
        ``user_guid`` defaults to the SID-matched connection user."""
        if user_guid is None:
            user = pick_connection_user(self._safe_users(), self._my_sid)
            if not user:
                return {"ok": False, "error": "Kein gültiger DATEV-Benutzer gefunden."}
            user_guid = user["id"]
        file_id = self._client.upload_document_file(pdf_bytes)
        payload = build_create_payload(
            file_id=file_id, client_guid=client_guid, description=description,
            user_guid=user_guid, domain_id=domain_id, folder_id=folder_id,
            register_id=register_id, structure_name=structure_name)
        created = self._client.create_document(payload)
        new_guid = created.get("id")
        sid = None
        if new_guid:
            try:
                sid = structure_item_id_for_file(
                    self._client.list_structure_items(new_guid), file_id)
            except Exception:
                sid = None
        prov = {"doc_guid": new_guid, "file_id": file_id, "structure_item_id": sid,
                "correspondence_partner_guid": client_guid, "source_name": structure_name}
        return {"ok": True, "provenance": prov, "http_status": created.get("http_status")}

    def _safe_users(self):
        try:
            return self._client.list_users()
        except Exception:
            return []


def _current_user_sid():
    """The connecting Windows user's SID (``whoami /user``) for SCIM user matching, or None.
    Best-effort + Windows-only; the create flow falls back to the first active user."""
    try:
        import subprocess
        out = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                             capture_output=True, text=True, timeout=10,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        # CSV: "DOMAIN\user","S-1-5-…"
        parts = [p.strip().strip('"') for p in (out.stdout or "").strip().split(",")]
        for p in parts:
            if p.startswith("S-1-"):
                return p
    except Exception:
        pass
    return None
