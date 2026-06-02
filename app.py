"""Single entry point bundling both GUIs into one executable.

One exe, two front ends — dispatch on a CLI flag:

    app.exe                 → legacy Tk GUI (default)
    app.exe file.belegtool  → legacy Tk GUI, opening that file
    app.exe --new           → React/pywebview GUI
    app.exe --new file      → React/pywebview GUI, opening that file (transfer)

In a frozen build ``sys.executable`` is this exe, so one GUI can relaunch the
other via subprocess without a second executable — that is what the planned
"open in new GUI" transfer button will use.
"""

import sys

from launch_util import NEW_GUI_FLAG


def select_gui(args):
    """Return 'new' or 'old' for the given argv tail (``sys.argv[1:]``)."""
    return "new" if NEW_GUI_FLAG in args else "old"


def _startup_path(args):
    """First non-flag argument, if any — the .belegtool to open on launch."""
    rest = [a for a in args if a != NEW_GUI_FLAG]
    return rest[0] if rest else None


def main(args=None):
    args = sys.argv[1:] if args is None else args
    if select_gui(args) == "new":
        from host import main as host_main
        host_main(_startup_path(args))
    else:
        from belegtool_main import start_gui
        start_gui()


if __name__ == "__main__":
    main()
