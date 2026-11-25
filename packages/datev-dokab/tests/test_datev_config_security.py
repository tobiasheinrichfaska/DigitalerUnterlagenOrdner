"""Security review 2026-11-25, finding H-2: ``datev.config.json`` must never be read from the
current working directory. Opening a document by double-click makes the file's folder the
CWD, so a planted config there redirected the SSO (``curl --negotiate -u : -k``) to an
attacker host. Also: only https, and curl is pinned to https."""

import json

import pytest

from datev import config
from datev.config import dms_base_url, load_config
from datev.transport import build_curl_args

EVIL = {"base_url": "https://evil.example:443", "verify_tls": False}


def test_load_config_ignores_the_current_directory(tmp_path, monkeypatch):
    (tmp_path / "datev.config.json").write_text(json.dumps(EVIL), encoding="utf-8")
    exe_dir = tmp_path / "exe"
    exe_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "basis_dir", lambda: exe_dir)
    assert load_config() == {}


def test_load_config_reads_next_to_the_exe(tmp_path, monkeypatch):
    exe_dir = tmp_path / "exe"
    exe_dir.mkdir()
    (exe_dir / "datev.config.json").write_text('{"base_url": "https://h:1"}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "basis_dir", lambda: exe_dir)
    assert load_config() == {"base_url": "https://h:1"}


def test_basis_dir_is_never_the_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config.sys, "frozen", False, raising=False)
    assert config.basis_dir().resolve() != tmp_path.resolve()


def test_basis_dir_frozen_is_the_exe_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config.sys, "executable", str(tmp_path / "app.exe"))
    assert config.basis_dir() == tmp_path


@pytest.mark.parametrize("raw", [
    "http://h:58452", "ftp://evil:21", "file:///C:/x", "smb://evil/share",
    "https://", "evil.example", "https://user:pw@evil.example",
])
def test_dms_base_url_accepts_only_plain_https(raw):
    default = "https://your-datev-server:58452/datev/api/dms/v2"
    assert dms_base_url({"base_url": raw}) == default


def test_dms_base_url_https_is_kept():
    assert dms_base_url({"base_url": "https://srv:58452"}) == "https://srv:58452/datev/api/dms/v2"


def test_curl_is_pinned_to_https():
    args = build_curl_args("GET", "https://h/x", {}, allow_self_signed=False,
                           out_path="o", curl="curl")
    i = args.index("--proto")
    assert args[i + 1] == "=https"
    j = args.index("--proto-redir")
    assert args[j + 1] == "=https"


def test_basis_dir_env_override_for_source_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(config.sys, "frozen", False, raising=False)
    monkeypatch.setenv("DATEV_CONFIG_DIR", str(tmp_path))
    assert config.basis_dir() == tmp_path


def test_basis_dir_frozen_ignores_env_override(tmp_path, monkeypatch):
    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config.sys, "executable", str(tmp_path / "app.exe"))
    monkeypatch.setenv("DATEV_CONFIG_DIR", str(tmp_path / "evil"))
    assert config.basis_dir() == tmp_path


def test_basis_dir_env_override_for_source_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(config.sys, "frozen", False, raising=False)
    monkeypatch.setenv("DATEV_CONFIG_DIR", str(tmp_path))
    assert config.basis_dir() == tmp_path


def test_basis_dir_frozen_ignores_env_override(tmp_path, monkeypatch):
    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config.sys, "executable", str(tmp_path / "app.exe"))
    monkeypatch.setenv("DATEV_CONFIG_DIR", str(tmp_path / "evil"))
    assert config.basis_dir() == tmp_path
