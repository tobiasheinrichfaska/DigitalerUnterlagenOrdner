"""Persisted app-settings store — pure, path-injected (no real %APPDATA%)."""
import json

from infra.settings import (
    DEFAULTS,
    load_settings,
    save_settings,
    settings_path,
    update_settings,
)


def test_load_missing_file_returns_defaults(tmp_path):
    assert load_settings(str(tmp_path / "nope.json")) == DEFAULTS
    assert DEFAULTS["datev_mode"] is False  # DATEV off by default → datev never imported


def test_save_then_load_roundtrips_known_keys(tmp_path):
    p = str(tmp_path / "settings.json")
    save_settings({"datev_mode": True, "dms_base_url": "https://h:58452/x"}, p)
    got = load_settings(p)
    assert got["datev_mode"] is True
    assert got["dms_base_url"] == "https://h:58452/x"


def test_save_drops_unknown_keys(tmp_path):
    p = str(tmp_path / "settings.json")
    save_settings({"datev_mode": True, "evil": "x", "__proto__": 1}, p)
    on_disk = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert set(on_disk) == set(DEFAULTS)  # only known keys persisted
    assert "evil" not in on_disk


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{ not json", encoding="utf-8")
    assert load_settings(str(p)) == DEFAULTS


def test_datev_mode_coerced_to_bool(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"datev_mode": 1}), encoding="utf-8")
    assert load_settings(str(p))["datev_mode"] is True


def test_update_settings_merges_and_persists(tmp_path):
    p = str(tmp_path / "settings.json")
    save_settings({"datev_mode": False, "dms_base_url": "https://a"}, p)
    out = update_settings(p, datev_mode=True)
    assert out["datev_mode"] is True
    assert out["dms_base_url"] == "https://a"  # untouched key survives
    assert load_settings(p)["datev_mode"] is True


def test_settings_path_lives_next_to_window_json(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = settings_path()
    assert p.endswith("settings.json")
    assert "DigitalerUnterlagenOrdner" in p
