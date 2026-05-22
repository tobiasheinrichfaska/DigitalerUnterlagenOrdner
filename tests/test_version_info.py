import version_info
import re

def test_constants_are_strings():
    """APP_NAME und VERSION sollen Strings sein."""
    assert isinstance(version_info.APP_NAME, str)
    assert isinstance(version_info.VERSION, str)

def test_version_format():
    """
    VERSION sollte dem Muster X.Y oder X.Y.Z entsprechen,
    z. B. 3.0 oder 2.1.4
    """
    assert re.match(r"^\d+\.\d+(\.\d+)?$", version_info.VERSION)

def test_full_title_format():
    """
    get_full_title() soll APP_NAME und VERSION mit einem Leerzeichen kombinieren.
    """
    full_title = version_info.get_full_title()

    # Beispiel: "DigitalerBeleg 3.0"
    assert full_title.startswith(f"{version_info.APP_NAME} ")
    assert full_title.endswith(version_info.VERSION)
    assert full_title == f"{version_info.APP_NAME} {version_info.VERSION}"

def test_full_title_contains_version_once():
    """VERSION darf genau einmal im Titel vorkommen."""
    full_title = version_info.get_full_title()
    assert full_title.count(version_info.VERSION) == 1
