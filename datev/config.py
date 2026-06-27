"""Connection config, mirroring OPOS's datev_api so the probe connects the same way:
a ``datev.config.json`` next to the exe ({base_url, auth, user, password, verify_tls}),
loopback-aware self-signed TLS, and the same auth-mode resolution."""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

CONFIG_NAME = "datev.config.json"
DMS_PATH = "/datev/api/dms/v2"  # the Dokumentenablage API base path (spec: document management 2.3.1)


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


def self_signed_allowed(cfg, base_url):
    """Explicit ``verify_tls`` wins; else trust the self-signed cert only for a loopback host."""
    v = (cfg or {}).get("verify_tls")
    if isinstance(v, bool):
        return not v
    return is_loopback(base_url)
