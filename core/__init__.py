"""Headless core service for the BelegTool.

A per-user process that exposes the PDF logic over a local named pipe, so a React UI
(via the pywebview host) — and a CLI test client — can drive it. The core is headless
(no UI imports); the React migration it enabled is complete (the legacy Tk GUI was
removed in v3.6.0). See docs/DATA_CONTRACT.md.

Step 0a: connection plumbing only (handshake + open), multi-client. No features.
"""

CORE_VERSION = "0.1.0"
