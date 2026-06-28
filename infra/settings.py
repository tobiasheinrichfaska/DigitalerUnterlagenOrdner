"""Persisted app settings — a small JSON store next to ``window.json``
(``%APPDATA%\\DigitalerUnterlagenOrdner\\settings.json``).

Data-driven: the known keys + their defaults live in ``DEFAULTS``; load/save only
ever touch those (an unknown key in the file is ignored, never written back). The
file path is injectable so the logic is unit-tested without touching the real
``%APPDATA%``.

Currently holds the **DATEV-mode** gate (off by default → the heavy ``datev`` package
is never imported on a normal launch) and an optional override of the DMS base URL.

⚠️ **Terminal-server safe — strictly per-user.** ``%APPDATA%`` (Roaming) is the user's
own profile, NOT a shared/machine location, so on an RDS box every clerk gets their own
``settings.json`` (same per-user location as ``window.json``). This is required for DATEV:
the connection authenticates via **Windows SSO as the logged-in user**, so each user
toggling DATEV mode / their DMS host independently is the correct, isolated behaviour.
Never move this to a machine-wide / ``%PROGRAMDATA%`` path.
"""

from __future__ import annotations

import json
import os

from infra.log_config import logger
from version_info import APP_NAME

# Known settings + their defaults. Adding a setting = adding a row here (data-driven);
# load/save never persist a key that isn't in this map.
DEFAULTS = {
    "datev_mode": False,        # gate the in-app DATEV integration (lazy-loaded when on)
    "dms_base_url": None,       # optional override; None ⇒ derive the default at connect time
}

_FILE_NAME = "settings.json"


def settings_path() -> str:
    """The on-disk settings file (sibling of ``window.json``)."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_NAME, _FILE_NAME)


def _coerce(values: dict) -> dict:
    """Defaults overlaid with only the KNOWN keys from ``values`` (unknown keys dropped,
    each coerced to its default's type where that is unambiguous)."""
    out = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        if key not in (values or {}):
            continue
        val = values[key]
        if isinstance(default, bool):
            out[key] = bool(val)
        else:
            out[key] = val
    return out


def load_settings(path: str = None) -> dict:
    """Settings from disk, merged over ``DEFAULTS`` (a missing/corrupt file ⇒ defaults)."""
    p = path or settings_path()
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return dict(DEFAULTS)
        return _coerce(data)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULTS)
    except OSError:
        logger.debug("settings load skipped", exc_info=True)
        return dict(DEFAULTS)


def save_settings(values: dict, path: str = None) -> dict:
    """Persist only the known keys (atomically enough for this tiny file). Returns the
    coerced dict that was written. Best-effort: a write error is logged, not raised."""
    p = path or settings_path()
    coerced = _coerce(values)
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(coerced, f, indent=2)
    except OSError:
        logger.warning("settings save failed", exc_info=True)
    return coerced


def update_settings(path: str = None, **changes) -> dict:
    """Load, apply ``changes`` (known keys only), save, and return the new settings."""
    current = load_settings(path)
    current.update({k: v for k, v in changes.items() if k in DEFAULTS})
    return save_settings(current, path)
