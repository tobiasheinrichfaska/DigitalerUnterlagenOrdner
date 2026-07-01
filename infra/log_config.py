# log_config.py
import logging
import os
import sys

# Write log to %LOCALAPPDATA%\PDF-Storage\ (always user-writable, even when
# installed in Program Files). Fall back to home dir if LOCALAPPDATA is unset.
_log_dir = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "PDF-Storage"
)
os.makedirs(_log_dir, exist_ok=True)
LOGFILE = os.path.join(_log_dir, "pdf_tool.log")

# LOGLEVEL is controlled via the env var PDF_TOOL_LOG_LEVEL.
# Default 99 = logging effectively off (no handler attached, no file written).
# Set to 10 (DEBUG), 20 (INFO), 30 (WARNING), 40 (ERROR), 50 (CRITICAL) to enable.
_DEFAULT_LOGLEVEL = 99


def _parse_loglevel(raw: str | None) -> int:
    if raw is None:
        return _DEFAULT_LOGLEVEL
    raw = raw.strip()
    if not raw:
        return _DEFAULT_LOGLEVEL
    try:
        return int(raw)
    except ValueError:
        # Allow level names (DEBUG, INFO, ...) too.
        name = raw.upper()
        return getattr(logging, name, _DEFAULT_LOGLEVEL)


LOGLEVEL = _parse_loglevel(os.environ.get("PDF_TOOL_LOG_LEVEL"))

# True when the user actually enabled logging (≤ 50 covers DEBUG..CRITICAL).
LOGGING_ENABLED = LOGLEVEL <= logging.CRITICAL

logger = logging.getLogger("pdf_tool")
logger.setLevel(LOGLEVEL)

# Bestehende Handler entfernen (z. B. aus früherem Lauf)
if logger.hasHandlers():
    logger.handlers.clear()

if LOGGING_ENABLED:
    # Log-Datei beim Start löschen
    if os.path.exists(LOGFILE):
        try:
            os.remove(LOGFILE)
        except Exception:
            pass  # Falls Datei gesperrt ist, einfach ignorieren

    # Datei-Handler hinzufügen
    file_handler = logging.FileHandler(LOGFILE, mode='w', encoding="utf-8")
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(LOGLEVEL)

    logger.addHandler(file_handler)
else:
    # Kein Handler → kein I/O. Eine NullHandler verhindert "No handlers could be found" Warnungen.
    logger.addHandler(logging.NullHandler())


# --- always-on diagnostic breadcrumb (independent of LOGLEVEL) -------------------------------
# Some field issues (slow startup, DATEV checkout ownership) are hard to reproduce and the normal
# logger is OFF by default. `diag()` appends a timestamped line to belegtool_diag.log NEXT TO THE
# EXE (so it's trivial to find) — falling back to %LOCALAPPDATA% when the exe dir is read-only.
# Best-effort + size-bounded; never raises.
def _diag_targets():
    name = "belegtool_diag.log"
    # Frozen exe → next to the exe (easy to find) + the user log dir as fallback. Dev/tests →
    # ONLY the user log dir (never write into the source tree).
    if getattr(sys, "frozen", False):
        return [os.path.join(os.path.dirname(sys.executable), name), os.path.join(_log_dir, name)]
    return [os.path.join(_log_dir, name)]


def diag(msg: str) -> None:
    from datetime import datetime
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
    for path in _diag_targets():
        try:
            if os.path.exists(path) and os.path.getsize(path) > 1_000_000:
                os.remove(path)  # bound growth (diag events are infrequent)
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
            return
        except OSError:
            continue
