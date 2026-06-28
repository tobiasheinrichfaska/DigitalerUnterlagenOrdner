"""Connection config, mirroring OPOS's datev_api so the probe connects the same way:
a ``datev.config.json`` next to the exe ({base_url, auth, user, password, verify_tls}),
loopback-aware self-signed TLS, and the same auth-mode resolution."""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

CONFIG_NAME = "datev.config.json"
DMS_PATH = "/datev/api/dms/v2"  # the Dokumentenablage API base path (spec: document management 2.3.1)
MASTER_DATA_PATH = "/datev/api/master-data/v1"  # client master data (spec: Client Master Data 1.7.1)
IAM_PATH = "/datev/api/iam/v1"  # identity/users (per the Mitarbeiter domain link)


def basis_dir():
    """Where to look for config: next to the exe when frozen, else cwd (as in OPOS)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path.cwd()


def load_config(path=None):
    """Load datev.config.json (explicit path, then cwd, then next to the exe). {} if none."""
    candidates = [Path(path)] if path else [Path(CONFIG_NAME), basis_dir() / CONFIG_NAME]
    for p in candidates:
        try:
            return json.loads(Path(p).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
    return {}


def is_loopback(base_url):
    """True for localhost/127.0.0.1/::1 — where DATEVconnect's self-signed cert is expected."""
    try:
        host = (urlparse(base_url or "").hostname or "").strip("[]")
        return host in ("localhost", "127.0.0.1", "::1")
    except ValueError:
        return False


def resolve_auth_mode(cfg):
    """Explicit ``auth`` wins; else Basic when a user is configured, else SSO (as in OPOS)."""
    a = str((cfg or {}).get("auth") or "").lower()
    if a in ("sso", "basic"):
        return a
    return "basic" if (cfg or {}).get("user") else "sso"


def dms_base_url(cfg, default="https://localhost:58452" + DMS_PATH):
    """The Dokumentenablage base, taking host+port from the config but **pinning the DMS
    path**. An OPOS ``datev.config.json`` points ``base_url`` at the *accounting* API
    (``/datev/api/accounting/v1``); reusing it here would 404 on ``/info``. We keep its host
    (``DatevHeinrich:58452``) and force ``/datev/api/dms/v2``. No usable host ⇒ ``default``."""
    raw = (cfg or {}).get("base_url")
    if not raw:
        return default
    p = urlparse(raw)
    if not p.scheme or not p.netloc:
        return default
    return f"{p.scheme}://{p.netloc}{DMS_PATH}"


def master_data_base_url(dms_base, default="https://localhost:58452" + MASTER_DATA_PATH):
    """The Client-Master-Data base, taking host+port from the DMS base but pinning the
    master-data path. Round 2 needs ``…/master-data/v1/clients`` to turn a Mandant number
    into the ``correspondence_partner_guid`` a document create requires; the live box serves
    it on the same host:port as DMS (see the domain ``correspondence_partner.link``)."""
    p = urlparse(dms_base or "")
    if not p.scheme or not p.netloc:
        return default
    return f"{p.scheme}://{p.netloc}{MASTER_DATA_PATH}"


def iam_base_url(dms_base, default="https://localhost:58452" + IAM_PATH):
    """The IAM base (host+port from the DMS base, IAM path pinned) — for listing users to
    fill the document's mandatory ``user`` with a live, non-deleted GUID."""
    p = urlparse(dms_base or "")
    if not p.scheme or not p.netloc:
        return default
    return f"{p.scheme}://{p.netloc}{IAM_PATH}"


def self_signed_allowed(cfg, base_url):
    """Explicit ``verify_tls`` wins; else trust the self-signed cert only for a loopback host."""
    v = (cfg or {}).get("verify_tls")
    if isinstance(v, bool):
        return not v
    return is_loopback(base_url)
