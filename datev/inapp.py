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

from infra.log_config import diag, logger
from .provenance import parse_checkout_path
from .types import program_keeps_revisions
from .writeback import CHECKED_OUT_SELF, LOCKED, OK, decide_save_back


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


def checkout_label(doc):
    """A human label of WHO has the document checked out, from a ``get_document`` response, or
    None. The DMS document carries ``checkout_user`` (a User ``{name, id}``) + ``checkout_computer``
    (the machine name, e.g. ``WTS (USER_4)``). Used to show 'ausgecheckt von …' instead of a bare
    'checked out' — so the user can tell their OWN checkout (the normal flow) from someone else's."""
    if not isinstance(doc, dict) or not doc.get("checked_out"):
        return None
    user = doc.get("checkout_user")
    name = (user.get("name") if isinstance(user, dict) else None) or ""
    computer = doc.get("checkout_computer") or ""
    name, computer = name.strip(), str(computer).strip()
    if name and computer:
        return f"{name} ({computer})"
    return name or computer or None


def _local_identity():
    """(COMPUTERNAME, USERNAME) of the running session — what 'me on this computer' means."""
    return ((os.environ.get("COMPUTERNAME") or "").strip(),
            (os.environ.get("USERNAME") or "").strip())


def is_my_checkout(doc, *, my_machine, my_user, my_dms_id=None):
    """Pure: is ``doc`` checked out by ME? The reliable identifier — confirmed against live data
    on the DATEV terminal server — is the **Windows session user** in ``checkout_computer``.

    DATEV reports ``checkout_computer`` as ``"<label> (<windows-user>)"``, e.g. ``"WTS (USER1)"``.
    On a terminal server ``<label>`` (``WTS``) is a DATEV/TS session label, **not** the Windows
    ``COMPUTERNAME`` (e.g. ``TSHOST``), so comparing the machine string is meaningless — and
    the same per-person, per-box label is stable. The discriminating part is the **session user**
    (``USER1``), which equals the Windows ``USERNAME`` (``user1``) → that is "me on this box".

    The DMS user id (``checkout_user.id``) is kept as an ADDITIONAL accept signal, but it is NOT
    reliable on its own: a re-provisioned Nutzer leaves the checkout stamped with a now-DELETED
    GUID that differs from the live connection's (a DATEV-side data problem — see project docs /
    DATEV ticket), so we never *require* it. ``my_machine`` is accepted for signature/diagnostic
    stability but no longer gates the decision.

    CONSERVATIVE: with neither the session user nor the DMS id confirmed → False, so a checkout by
    ANOTHER user (a different ``(windows-user)``) BLOCKS the write-back. (The caller logs the live
    inputs so the match can be verified on the box.)"""
    if not isinstance(doc, dict) or not doc.get("checked_out"):
        return False
    cc = str(doc.get("checkout_computer") or "")
    m = re.search(r"\(([^)]+)\)", cc)
    sess_user = m.group(1).strip() if m else ""
    same_session_user = bool(my_user) and sess_user.lower() == str(my_user).lower()
    cu = doc.get("checkout_user") or {}
    same_dms_user = (bool(my_dms_id) and cu.get("id") is not None
                     and str(cu.get("id")).strip().lower() == str(my_dms_id).strip().lower())
    return same_session_user or same_dms_user


def _parse_folders(folders):
    """Defensive: normalize a domain's folders (+ nested registers) into
    ``[{id, name, registers:[{id, name}]}]``. Tolerates missing/oddly-named keys."""
    out = []
    for f in (folders or []):
        if not isinstance(f, dict) or f.get("id") is None:
            continue
        regs = []
        for r in (f.get("registers") or f.get("register") or []):
            if isinstance(r, dict) and r.get("id") is not None:
                regs.append({"id": r["id"], "name": (r.get("name") or "").strip()})
        out.append({"id": f["id"], "name": (f.get("name") or "").strip(), "registers": regs})
    return out


def build_create_payload(*, file_id, client_guid, description, user_guid, domain_id=1,
                         folder_id=None, register_id=None, structure_name="beleg.pdf",
                         created=None, receipt_date=None, fiscal_year=None, fiscal_month=None):
    """Pure: the DocumentCreate body for a class-1 ("Dokument") create — the mandatory
    set proven on the live box (class · correspondence_partner_guid · description · domain ·
    user · one structure_item with counter/parent_counter + the dates + the int file id).
    **No `state` for class 1.** Optional, per the DATEV DMS Document spec: ``folder``/``register``
    placement; ``receipt_date`` (Belegdatum, the document's own date); ``year``/``month`` (the
    Veranlagungszeitraum/-monat, ints). ``created`` sets the structure-item technical dates
    (default now)."""
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
    if receipt_date:
        payload["receipt_date"] = receipt_date  # DATEV "date of the receipt or the document"
    _apply_fiscal_period(payload, fiscal_year, fiscal_month)
    return payload


def _apply_fiscal_period(payload, year, month):
    """Set the Veranlagungszeitraum on the DocumentCreate body. The DATEV DMS Document spec
    names these ``year`` (int32, "Year of the assessment basis") and ``month`` (int16, "Month
    of the assessment") — set each only when given (a year without a month is valid; a month
    alone is meaningless on its own and dropped)."""
    if year in (None, ""):
        return
    try:
        payload["year"] = int(year)
    except (TypeError, ValueError):
        return
    if month not in (None, ""):
        try:
            payload["month"] = int(month)
        except (TypeError, ValueError):
            pass


def _structure_items_list(structure_items):
    """Normalize the SCIM-ish envelope (``{structure_items:[...]}``) or a plain list to a list of
    dict items that carry an ``id``."""
    items = (structure_items.get("structure_items", structure_items)
             if isinstance(structure_items, dict) else structure_items)
    return [it for it in (items or []) if isinstance(it, dict) and it.get("id") is not None]


def structure_item_id_for_file(structure_items, file_id):
    """The STABLE structure-item id whose ``document_file_id`` matches the checkout path's
    ``file_id`` — the durable PUT handle (``document_file_id`` changes per version, the
    structure-item id does not). Accepts the SCIM-ish envelope or a plain list. None if absent."""
    for it in _structure_items_list(structure_items):
        if it.get("document_file_id") == file_id:
            return it["id"]
    return None


def resolve_structure_item(structure_items, path_file_id=None):
    """Choose the structure item to write back to → ``{id, document_file_id}`` or None.

    The number in a DokOrg checkout path is NOT reliably a server ``document_file_id``: the
    ``AppData\\Roaming\\DokOrg\\CheckOut\\<guid>\\<n>\\…`` *working-copy* id is a different
    namespace, so ``get_document_file(<n>)`` 404s and matching it against ``document_file_id``
    finds nothing. Strategy: (1) prefer a structure item whose ``document_file_id`` matches the
    path number (the DMS / ``…\\DokorgPro\\<file-id>`` case, where the number IS the file id);
    (2) else fall back to the SOLE structure item (single-file document — the common case). With
    several items and no path match → None (ambiguous; caller refuses rather than guess)."""
    items = _structure_items_list(structure_items)
    chosen = None
    if path_file_id is not None:
        for it in items:
            if it.get("document_file_id") == path_file_id:
                chosen = it
                break
    if chosen is None and len(items) == 1:
        chosen = items[0]
    if chosen is None:
        return None
    return {"id": chosen["id"], "document_file_id": chosen.get("document_file_id")}


class DatevService:
    """Live in-app DATEV operations over an (injected) ``DatevConnectClient``. DATEV-mode
    only; built lazily by ``CoreApi`` when the user's settings enable DATEV mode."""

    def __init__(self, client, feature=None, my_sid=None, base_url=None):
        self._client = client
        self.feature = feature
        self._my_sid = my_sid
        self._base_url = base_url

    # --- construction (the only live-wired part) ---------------------------
    @classmethod
    def connect(cls, settings=None, client=None, my_sid=None):
        """Build a live service: an SSO-curl ``DatevConnectClient`` against the configured
        DMS base, probed once with ``GET /info`` (→ ``feature``). ``client`` may be injected
        (tests / a pre-built client); otherwise it is constructed from ``settings``
        (``dms_base_url`` override, else the loopback default)."""
        base = None
        if client is None:
            from .config import dms_base_url, self_signed_allowed, load_config
            from .transport import make_curl_sso_transport
            from .client import DatevConnectClient
            from .types import DatevConfig
            # Resolve the DMS host:port from (1) a settings override, then (2) the
            # ``datev.config.json`` next to the exe, then (3) the loopback default. The file
            # was previously IGNORED here — connect() only ever read the settings override, so
            # a shipped datev.config.json never took effect (v3.10.0 bug). dms_base_url() pins
            # the /datev/api/dms/v2 path onto whichever host:port wins.
            file_cfg = load_config()
            override = (settings or {}).get("dms_base_url")
            if override:
                base = dms_base_url({"base_url": override})
            else:
                base = dms_base_url(file_cfg)  # honour the file's base_url (else default)
            allow_self_signed = self_signed_allowed(file_cfg, base)
            cfg = DatevConfig(base_url=base, allow_self_signed=allow_self_signed)
            client = DatevConnectClient(cfg, make_curl_sso_transport(allow_self_signed))
        feature = None
        try:
            feature = (client.get_info() or {}).get("feature")
        except Exception:
            logger.warning("[datev] get_info failed during connect (base=%s)", base, exc_info=True)
            feature = None
        if my_sid is None:
            my_sid = _current_user_sid()
        return cls(client, feature=feature, my_sid=my_sid, base_url=base)

    def status(self) -> dict:
        keeps = program_keeps_revisions(self.feature)
        # Surface WHERE we connected (base_url) + WHICH config file drove it, so the user can
        # see/diagnose the host instead of a hidden default (v3.10.0: "I can not see the path").
        from .config import basis_dir, CONFIG_NAME
        cfg_path = str(basis_dir() / CONFIG_NAME)
        return {"ok": True, "connected": self.feature is not None,
                "feature": self.feature, "keeps_revisions": keeps,
                "base_url": self._base_url, "config_path": cfg_path,
                "config_present": (basis_dir() / CONFIG_NAME).is_file()}

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
        # Resolve the structure item (PUT handle) AND the real server document_file_id from the
        # server — the path number is not reliably a document_file_id (DokOrg CheckOut working-copy
        # id), so writing back with it 404s. The doc_guid is the reliable key.
        try:
            items_raw = self._client.list_structure_items(doc_guid)
            chosen = resolve_structure_item(items_raw, file_id)
            if chosen:
                prov["structure_item_id"] = chosen["id"]
                dfid = chosen.get("document_file_id")
                if isinstance(dfid, str) and dfid.strip().lstrip("-").isdigit():
                    dfid = int(dfid)
                if isinstance(dfid, int) and not isinstance(dfid, bool):
                    prov["file_id"] = dfid  # the REAL server file id (path number may be a working copy)
            diag(f"[datev] resolved: file_id={prov['file_id']!r} (path={file_id!r}) "
                 f"structure_item_id={prov['structure_item_id']!r}")
        except Exception:
            logger.warning("[datev] structure-item resolve failed", exc_info=True)
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
        # re-read concurrency state
        try:
            doc = self._client.get_document(doc_guid) or {}
            remote_change_dt = doc.get("change_date_time")
            checked_out_now = bool(doc.get("checked_out"))
        except Exception as e:
            return {"ok": False, "verdict": "error", "error": str(e)}
        # CHECKOUT STATE decides the path BEFORE any server overwrite is attempted: DATEV refuses an
        # API update_structure_item on a checked-out document ("The document can't be changed because
        # it is checked out" — confirmed live 2026-06-30). So:
        #   • checked out by ANOTHER user → LOCKED (they may be editing; never touch it);
        #   • checked out by ME → CHECKED_OUT_SELF: the API write-back is impossible, the caller saves
        #     the local working copy and the user checks it in via DATEV (the native DokOrg flow);
        #   • not checked out → the guarded in-place API write-back below.
        checked_out_by_other = checked_out_now and not self._is_my_checkout(doc)
        if checked_out_now:
            verdict = LOCKED if checked_out_by_other else CHECKED_OUT_SELF
            diag(f"[datev] writeback: checked_out=True by_other={checked_out_by_other} "
                 f"checkout_computer={doc.get('checkout_computer')!r} → verdict={verdict}")
            out = {"ok": False, "verdict": verdict}
            if verdict == LOCKED:
                out["checkout_by"] = checkout_label(doc)  # WHO has it (another user)
            return out
        try:
            remote_bytes = self._client.get_document_file(file_id)
        except Exception as e:
            return {"ok": False, "verdict": "error", "error": str(e)}
        verdict = decide_save_back(
            user_confirmed=user_confirmed,
            checked_out_by_other_now=False,            # not checked out (handled above)
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
        # Re-hash the bytes DokAb actually STORED (it may re-process on store), so the next
        # write-back's content guard compares the real server state — hashing our uploaded
        # bytes here would spuriously trip conflict_content if the server normalised them.
        # Fall back to the uploaded bytes if the read-back fails (better than no baseline).
        try:
            new_sha256 = sha256(self._client.get_document_file(new_file_id))
        except Exception:
            new_sha256 = sha256(edited_bytes)
        return {"ok": True, "verdict": OK, "new_file_id": new_file_id,
                "structure_item_id": sid, "http_status": res.get("http_status"),
                "backup_path": backup_path, "provenance": new_prov,
                "new_change_dt": self._safe_change_dt(doc_guid),
                "new_sha256": new_sha256}

    def _safe_change_dt(self, doc_guid):
        try:
            return (self._client.get_document(doc_guid) or {}).get("change_date_time")
        except Exception:
            return None

    # --- file a NEW document (create) --------------------------------------
    def resolve_client(self, mandant_number):
        """Mandant number → ``{guid, name, number}`` (raises via the client if not found)."""
        return self._client.resolve_client_guid(mandant_number)

    def list_clients(self):
        """All DATEV clients as normalized ``{guid, number, name}`` rows, sorted by number —
        the source for the filing dialog's searchable client dropdown. Raises (via the client)
        when master-data is unreachable; the caller then DISABLES DATEV filing (no client data
        ⇒ no safe target). Tolerates either a bare list or a ``{clients:[…]}`` envelope."""
        data = self._client.list_clients()
        rows = data.get("clients", data) if isinstance(data, dict) else data
        out = []
        for c in (rows or []):
            if not isinstance(c, dict):
                continue
            guid = c.get("id") or c.get("guid")
            if not guid:
                continue
            out.append({"guid": guid, "number": str(c.get("number") or "").strip(),
                        "name": (c.get("name") or "").strip()})
        out.sort(key=lambda r: (r["number"], r["name"]))
        return out

    def list_placements(self, domain_id=1):
        """Folders (and their registers) for a domain — the optional placement pickers in the
        filing dialog. Parses the ``/domains`` tree DEFENSIVELY (the live shape is
        domain→folder→register with reused ids); any shape surprise yields an empty list so the
        dialog falls back to plain id entry rather than crashing. Returns
        ``[{id, name, registers:[{id, name}]}]``."""
        try:
            data = self._client.list_domains()
        except Exception:
            logger.warning("[datev] list_domains failed", exc_info=True)
            return []
        domains = data.get("domains", data) if isinstance(data, dict) else data
        for dom in (domains or []):
            if not isinstance(dom, dict):
                continue
            if domain_id is not None and dom.get("id") not in (domain_id, str(domain_id)):
                continue
            return _parse_folders(dom.get("folders") or dom.get("folder") or [])
        # no id match (or single untagged domain) → take the first domain's folders
        first = next((d for d in (domains or []) if isinstance(d, dict)), None)
        return _parse_folders((first or {}).get("folders") or (first or {}).get("folder") or [])

    def file_document(self, pdf_bytes, *, client_guid, description, domain_id=1,
                      folder_id=None, register_id=None, structure_name="beleg.pdf",
                      user_guid=None, document_date=None, fiscal_year=None, fiscal_month=None):
        """Create a NEW DATEV document from ``pdf_bytes`` (upload → create). Returns
        ``{ok, provenance}`` where provenance connects the working doc to the new document.
        ``user_guid`` defaults to the SID-matched connection user. ``document_date`` (ISO) sets
        the ``receipt_date`` (Belegdatum); ``fiscal_year``/``fiscal_month`` carry the Veranlagungszeitraum."""
        if user_guid is None:
            user = pick_connection_user(self._safe_users(), self._my_sid)
            if not user:
                return {"ok": False, "error": "Kein gültiger DATEV-Benutzer gefunden."}
            user_guid = user["id"]
        file_id = self._client.upload_document_file(pdf_bytes)
        payload = build_create_payload(
            file_id=file_id, client_guid=client_guid, description=description,
            user_guid=user_guid, domain_id=domain_id, folder_id=folder_id,
            register_id=register_id, structure_name=structure_name,
            receipt_date=document_date, fiscal_year=fiscal_year, fiscal_month=fiscal_month)
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

    def _is_my_checkout(self, doc):
        """Is ``doc`` checked out by the CONNECTING user (the normal DokOrg edit flow)? Decided by
        the Windows **session user** in ``checkout_computer`` (the machine label / Nutzer-GUID / SID
        are unreliable here — see CLAUDE.md / DATEV ticket), with the DMS user id as a bonus signal.
        Conservative — unconfirmed ⇒ False ⇒ another user's checkout blocks the write-back.

        The breadcrumb logs BOTH sides of the computer/owner comparison (the checkout vs. this
        session) so the match rule can be verified — and hardened to require a computer+owner
        match — from the field diag (belegtool_diag.log). See docs/datev-ticket-deleted-nutzer.md."""
        my_machine, my_user = _local_identity()
        me_dms = pick_connection_user(self._safe_users(), self._my_sid) or {}
        mine = is_my_checkout(doc, my_machine=my_machine, my_user=my_user,
                              my_dms_id=me_dms.get("id"))
        d = doc or {}
        cc = str(d.get("checkout_computer") or "")
        m = re.search(r"\(([^)]+)\)", cc)
        sess_user = m.group(1).strip() if m else ""
        cu = d.get("checkout_user") or {}
        same_session_user = bool(my_user) and sess_user.lower() == str(my_user).lower()
        same_dms_user = (bool(me_dms.get("id")) and cu.get("id") is not None
                         and str(cu.get("id")).strip().lower() == str(me_dms.get("id")).strip().lower())
        sid_match = (bool(me_dms.get("sid")) and bool(self._my_sid)
                     and str(me_dms.get("sid")).lower() == str(self._my_sid).lower())
        diag("[datev] checkout ownership: mine=%s | CHECKOUT computer=%r session_user=%r "
             "user={name=%r id=%r is_deleted=%r} | ME computername=%r username=%r sid=%r "
             "conn_user={name=%r id=%r sid=%r via=%s} | same_session_user=%s same_dms_user=%s"
             % (mine, cc, sess_user, cu.get("name"), cu.get("id"), cu.get("is_deleted"),
                my_machine, my_user, self._my_sid, me_dms.get("name"), me_dms.get("id"),
                me_dms.get("sid"), "sid" if sid_match else "first-active",
                same_session_user, same_dms_user))
        return mine


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
