"""Routing for the unified single-exe entry point (app.py)."""

import app


def test_default_launches_old_gui():
    assert app.select_gui([]) == "old"


def test_file_arg_still_launches_old_gui():
    # A bare .belegtool path opens in the legacy GUI (unchanged behaviour).
    assert app.select_gui(["C:/docs/x.belegtool"]) == "old"


def test_new_flag_launches_new_gui():
    assert app.select_gui(["--new"]) == "new"


def test_new_flag_with_file_launches_new_gui():
    assert app.select_gui(["--new", "C:/docs/x.belegtool"]) == "new"


def test_startup_path_extracted_after_new_flag():
    assert app._startup_path(["--new", "C:/docs/x.belegtool"]) == "C:/docs/x.belegtool"


def test_startup_path_none_without_file():
    assert app._startup_path(["--new"]) is None
    assert app._startup_path([]) is None
