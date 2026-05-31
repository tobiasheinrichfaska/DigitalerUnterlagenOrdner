"""Headless core service for the BelegTool.

A per-user process that exposes the existing PDF logic over a local named pipe,
so a React UI (via a webview host) — and a CLI test client — can drive it without
the Tkinter GUI. See docs/REACT_MIGRATION_PLAN.md and docs/DATA_CONTRACT.md.

Step 0a: connection plumbing only (handshake + open), multi-client. No features.
"""

CORE_VERSION = "0.1.0"
