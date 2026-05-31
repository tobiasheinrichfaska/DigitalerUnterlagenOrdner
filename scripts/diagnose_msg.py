"""
Diagnose-Skript fuer MSG-Dateien.
Aufruf: python diagnose_msg.py "pfad\zur\datei.msg"
"""
import sys
import io
import os

if len(sys.argv) < 2:
    print("Aufruf: python diagnose_msg.py <pfad.msg>")
    sys.exit(1)

path = sys.argv[1]
print(f"Datei: {path}")
print(f"Groesse: {os.path.getsize(path)} Bytes")
print()

# --- 1. Rohe Byte-Erkennung ---
with open(path, "rb") as f:
    data = f.read(32)
print(f"Erste 32 Bytes (hex): {data.hex()}")
with open(path, "rb") as f:
    raw = f.read()
print(f"'Content-Type:' in Datei: {b'Content-Type:' in raw}")
print(f"'From:'         in Datei: {b'From:' in raw}")
print()

# --- 2. extract_msg ---
try:
    import extract_msg
    msg = extract_msg.Message(path)
    print(f"Betreff  : {msg.subject!r}")
    print(f"Datum    : {msg.date!r}")
    print(f"Von      : {msg.sender!r}")
    print(f"htmlBody : {bool(msg.htmlBody)} ({len(msg.htmlBody or b'')} Bytes)")
    print(f"body     : {bool(msg.body)} ({len(msg.body or '')} Zeichen)")
    print()
    print(f"Anzahl Anhaenge: {len(msg.attachments)}")
    for i, att in enumerate(msg.attachments):
        try:
            fname = att.longFilename or att.shortFilename or "(kein Name)"
            data_att = att.data
            size = len(data_att) if data_att else 0
            print(f"  [{i}] {fname!r}  |  data={'None' if data_att is None else f'{size} Bytes'}  |  type={type(att).__name__}")
        except Exception as e:
            print(f"  [{i}] FEHLER beim Lesen: {e}")
except Exception as e:
    print(f"extract_msg Fehler: {e}")
    import traceback; traceback.print_exc()

print()
print("Fertig.")
