"""Entry point for the standalone DATEV read-probe (one-file exe). See datev/probe_gui.py.
Build: scripts/build_datev_probe.ps1  →  dist/DATEV-Probe.exe"""
from datev.probe_gui import main

if __name__ == "__main__":
    main()
