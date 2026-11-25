"""Entry point for the standalone DATEV read-probe (one-file exe). See tools/datev_probe/probe_gui.py.
Build: scripts/build_datev_probe.ps1  ->  dist/DATEV-Probe.exe
Needs the `datev` package (pip install ./packages/datev-dokab) importable."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "datev_probe"))

from probe_gui import main  # noqa: E402

if __name__ == "__main__":
    main()
