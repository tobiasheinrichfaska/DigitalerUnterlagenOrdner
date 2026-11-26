# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
r"""
Diagnose-Skript fuer MSG-Dateien (nutzt den eigenen Leser belegtool_archives.msg_reader: olefile + compressed-rtf).
Aufruf: python diagnose_msg.py "pfad\zur\datei.msg"
"""
import sys
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
    raw = f.read()
print(f"Erste 32 Bytes (hex): {raw[:32].hex()}")
print(f"CFB-Signatur (echtes .msg): {raw[:8] == bytes.fromhex('D0CF11E0A1B11AE1')}")
print(f"'Content-Type:' in Datei: {b'Content-Type:' in raw}")
print(f"'From:'         in Datei: {b'From:' in raw}")
print()

# --- 2. eigener MSG-Leser ---
try:
    from belegtool_archives import msg_reader
    msg = msg_reader.open_msg(raw)
    print(f"Betreff  : {msg.subject!r}")
    print(f"Datum    : {msg.date!r}")
    html = msg.html_body
    print(f"htmlBody : {bool(html)} ({len(html or b'')} Bytes)")
    print(f"body     : {bool(msg.text_body)} ({len(msg.text_body or '')} Zeichen)")
    print(f"rtfBody  : {bool(msg.rtf_body)} ({len(msg.rtf_body or b'')} Bytes)")
    print()
    atts = list(msg.attachments())
    print(f"Anzahl Anhaenge: {len(atts)}")
    for i, att in enumerate(atts):
        try:
            fname = att.name or "(kein Name)"
            print(f"  [{i}] {fname!r}  |  art={att.kind}  |  {att.size} Bytes  |  {att.reason or 'ok'}")
        except Exception as e:
            print(f"  [{i}] FEHLER beim Lesen: {e}")
except Exception as e:
    print(f"MSG-Leser Fehler: {e}")
    import traceback
    traceback.print_exc()

print()
print("Fertig.")
