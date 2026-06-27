"""Pure validation for window-geometry persistence — so a window saved on a now-gone
monitor falls back to the default instead of opening off-screen."""
from infra.window_geometry import valid_geometry, geometry_visible

VS = (0, 0, 1920, 1080)            # single monitor
DUAL = (0, 0, 3840, 1080)          # two 1920-wide monitors side by side
G = {"x": 100, "y": 100, "width": 1280, "height": 820}


def test_valid_geometry():
    assert valid_geometry(G)
    assert not valid_geometry({"x": 0, "y": 0, "width": 100, "height": 100})  # too small
    assert not valid_geometry({"x": 0, "y": 0, "width": 1280})                # missing height
    assert not valid_geometry(None)
    assert not valid_geometry({"x": "a", "y": 0, "width": 1280, "height": 820})


def test_visible_on_primary_screen():
    assert geometry_visible(G, VS)


def test_off_to_the_right_disconnected_monitor_is_rejected():
    # saved on a 2nd monitor (x=2000) that is no longer attached
    assert not geometry_visible({**G, "x": 2000}, VS)


def test_above_the_top_is_rejected():
    assert not geometry_visible({**G, "y": -200}, VS)


def test_partial_left_overlap_accepted_but_fully_off_rejected():
    assert geometry_visible({**G, "x": -1100}, VS)      # ~180 px of the title bar visible
    assert not geometry_visible({**G, "x": -1250}, VS)  # only ~30 px → unreachable


def test_second_monitor_geometry_accepted_on_dual_desktop():
    assert geometry_visible({**G, "x": 2100}, DUAL)


def test_no_virtual_screen_trusts_a_valid_geometry():
    assert geometry_visible({**G, "x": 5000, "y": 5000}, None)
    assert not geometry_visible({"width": 1280}, None)   # still must be valid
