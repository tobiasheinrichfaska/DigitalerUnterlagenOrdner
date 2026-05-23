# log_config.py
import logging
import os
import sys

# Anchor log file to the EXE directory (frozen) or source directory (dev),
# so it never tries to write to CWD which may be C:\Windows\System32 when
# launched from Explorer.
if getattr(sys, 'frozen', False):
    _app_dir = os.path.dirname(sys.executable)
else:
    _app_dir = os.path.dirname(os.path.abspath(__file__))

LOGFILE = os.path.join(_app_dir, "pdf_tool.log")
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
