"""Helpers for the single-exe dual-GUI setup — relaunching the other front end.

In a frozen PyInstaller build ``sys.executable`` is the bundled exe itself, so the
old GUI can start the new GUI by re-running the same executable with ``--new``.
In a dev checkout we re-run ``app.py`` through the current Python interpreter.
"""

import os
import sys

NEW_GUI_FLAG = "--new"


def new_gui_command(startup_path=None):
    """argv list to launch this app's React/pywebview GUI, optionally opening
    ``startup_path`` (a .belegtool file)."""
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, NEW_GUI_FLAG]
    else:
        entry = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
        cmd = [sys.executable, entry, NEW_GUI_FLAG]
    if startup_path:
        cmd.append(startup_path)
    return cmd
