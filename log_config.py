# log_config.py
import logging
import os

LOGFILE = "pdf_tool.log"
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
