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
LOGLEVEL = 99  # Standardmäßig: keine Ausgaben

logger = logging.getLogger("pdf_tool")
logger.setLevel(LOGLEVEL)

# Bestehende Handler entfernen (z. B. aus früherem Lauf)
if logger.hasHandlers():
    logger.handlers.clear()

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
