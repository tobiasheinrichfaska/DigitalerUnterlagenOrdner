"""Relaunch-command construction for the single-exe dual-GUI setup."""

import sys

import launch_util


def test_dev_command_runs_app_py_with_flag():
    cmd = launch_util.new_gui_command()
    assert cmd[0] == sys.executable
    assert cmd[1].endswith("app.py")
    assert cmd[2] == launch_util.NEW_GUI_FLAG


def test_dev_command_appends_startup_path():
    cmd = launch_util.new_gui_command(r"C:\tmp\x.belegtool")
    assert cmd[-1] == r"C:\tmp\x.belegtool"
    assert launch_util.NEW_GUI_FLAG in cmd


def test_frozen_command_is_the_exe_itself(monkeypatch):
    # In a frozen build sys.executable IS the bundled exe — no app.py.
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\app\BelegTool.exe", raising=False)
    cmd = launch_util.new_gui_command(r"C:\tmp\x.belegtool")
    assert cmd == [r"C:\app\BelegTool.exe", launch_util.NEW_GUI_FLAG, r"C:\tmp\x.belegtool"]
