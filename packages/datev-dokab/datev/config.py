"""Connection config:
a ``datev.config.json`` next to the exe ({base_url, auth, user, password, verify_tls}),
loopback-aware self-signed TLS, and auth-mode resolution."""
import json
import os
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

CONFIG_NAME = "datev.config.json"
DMS_PATH = "/datev/api/dms/v2"  # the Dokumentenablage API base path (spec: document management 2.3.1)
MASTER_DATA_PATH = "/datev/api/master-data/v1"  # client master data (spec: Client Master Data 1.7.1)
IAM_PATH = "/datev/api/iam/v1"  # identity/users (per the Mitarbeiter domain link)

# The on-prem DATEVconnect host to use when no datev.config.json is present — a PLACEHOLDER
# (the client runs on a workstation, DATEVconnect on the server). Set the REAL host in the
# site-specific, gitignored datev.config.json; this hard-coded default is only a fallback.
DEFAULT_HOST = "your-datev-server:58452"
DEFAULT_BASE = f"https://{DEFAULT_HOST}"


def basis_dir():
    """Where the config lives: next to the exe when frozen; else the folder named by the
    ``DATEV_CONFIG_DIR`` environment variable (explicit, for source/dev runs); else the folder
    that contains the ``datev`` package (the source tree root, or site-packages once installed).

    NEVER the current working directory: opening a document by double-click makes ITS folder
    the CWD, so a ``datev.config.json`` planted next to a received file would redirect the
    Negotiate/SSO traffic to an attacker host (security review 2026-11-25, H-2)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    override = os.environ.get("DATEV_CONFIG_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent


def load_config(path=None):
    """Load datev.config.json (explicit path, else next to the exe — never the CWD). {} if none."""
    candidates = [Path(path)] if path else [basis_dir() / CONFIG_NAME]
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
    """Explicit ``auth`` wins; else Basic when a user is configured, else SSO ."""
    a = str((cfg or {}).get("auth") or "").lower()
    if a in ("sso", "basic"):
        return a
    return "basic" if (cfg or {}).get("user") else "sso"


def dms_base_url(cfg, default=DEFAULT_BASE + DMS_PATH):
    """The Dokumentenablage base, taking host+port from the config but **pinning the DMS
    path**. A ``datev.config.json`` often points ``base_url`` at the *accounting* API
    (``/datev/api/accounting/v1``); reusing it here would 404 on ``/info``. We keep its host
    and force ``/datev/api/dms/v2``. No usable host ⇒ ``default``
    (the on-prem DATEV server, not localhost)."""
    raw = (cfg or {}).get("base_url")
    if not raw:
        return default
    p = urlparse(raw)
    # Only plain https with a real host: no other scheme (cleartext Negotiate, ftp/smb/file via
    # curl) and no ``user:pw@`` userinfo that could disguise the real target (review H-2).
    if p.scheme != "https" or not p.hostname or "@" in p.netloc:
        return default
    return f"{p.scheme}://{p.netloc}{DMS_PATH}"


def master_data_base_url(dms_base, default=DEFAULT_BASE + MASTER_DATA_PATH):
    """The Client-Master-Data base, taking host+port from the DMS base but pinning the
    master-data path. Round 2 needs ``…/master-data/v1/clients`` to turn a Mandant number
    into the ``correspondence_partner_guid`` a document create requires; the live server serves
    it on the same host:port as DMS (see the domain ``correspondence_partner.link``)."""
    p = urlparse(dms_base or "")
    if not p.scheme or not p.netloc:
        return default
    return f"{p.scheme}://{p.netloc}{MASTER_DATA_PATH}"


def iam_base_url(dms_base, default=DEFAULT_BASE + IAM_PATH):
    """The IAM base (host+port from the DMS base, IAM path pinned) — for listing users to
    fill the document's mandatory ``user`` with a live, non-deleted GUID."""
    p = urlparse(dms_base or "")
    if not p.scheme or not p.netloc:
        return default
    return f"{p.scheme}://{p.netloc}{IAM_PATH}"


def self_signed_allowed(cfg, base_url):
    """Explicit ``verify_tls`` wins; else trust the self-signed cert for a loopback host OR the
    default on-prem DATEV host (DATEVconnect serves an internal/self-signed cert there — there is
    no public CA on the practice LAN). Any OTHER host must opt in via ``verify_tls: false``."""
    v = (cfg or {}).get("verify_tls")
    if isinstance(v, bool):
        return not v
    if is_loopback(base_url):
        return True
    host = (urlparse(base_url or "").hostname or "").lower()
    return host == DEFAULT_HOST.split(":")[0].lower()
