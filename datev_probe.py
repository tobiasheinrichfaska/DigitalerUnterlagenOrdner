# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Entry point for the standalone DATEV read-probe (one-file exe). See tools/datev_probe/probe_gui.py.
Build: scripts/build_datev_probe.ps1  ->  dist/DATEV-Probe.exe
Needs the `datev` package (the datev-dokab pin from requirements.txt) importable."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "datev_probe"))

from probe_gui import main  # noqa: E402

if __name__ == "__main__":
    main()
