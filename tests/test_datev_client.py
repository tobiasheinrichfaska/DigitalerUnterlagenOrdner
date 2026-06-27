"""DATEVconnect read client (round 1) — unit-tested with a fake transport (no live
DATEVconnect). Covers feature detection, the read calls, query/path building, Basic auth,
and the 401 / license / error mappings."""
import base64
import json

import pytest

from datev.client import DatevConnectClient
from datev.endpoints import build_url
from datev.transport import build_curl_args
from datev.types import (
    DatevAuthError,
    DatevConfig,
    DatevError,
    DatevLicenseError,
    HttpResponse,
    program_keeps_revisions,
)

CFG = DatevConfig(base_url="https://localhost:58452/datev/api/dms/v2",
                  username="u@d.local", password="pw", allow_self_signed=True)


def _resp(status=200, obj=None, body=None, headers=None):
    if body is None:
        body = json.dumps(obj).encode() if obj is not None else b""
    elif isinstance(body, str):
        body = body.encode()
    return HttpResponse(status, headers or {}, body)


class _Fake:
    def __init__(self, handler):
        self.calls = []
        self._handler = handler

    def __call__(self, method, url, headers, body):
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body})
        return self._handler(method, url, headers, body)


def _client(handler):
    fake = _Fake(handler)
    return DatevConnectClient(CFG, fake), fake


# --- program type ----------------------------------------------------------
def test_program_keeps_revisions():
    assert program_keeps_revisions("DokAbRev")
    assert program_keeps_revisions("DMS")
    assert program_keeps_revisions("dms")          # case-insensitive
    assert not program_keeps_revisions("DokAB")    # plain Document Filing → overwrite
    assert not program_keeps_revisions(None)


# --- read calls ------------------------------------------------------------
def test_get_info_returns_feature_and_sends_basic_auth():
    cli, fake = _client(lambda *a: _resp(obj={"feature": "DokAB"}))
    assert cli.get_info()["feature"] == "DokAB"
    auth = fake.calls[0]["headers"]["Authorization"]
    assert auth == "Basic " + base64.b64encode(b"u@d.local:pw").decode()


def test_list_documents_passes_filter_top_skip_in_query():
    cli, fake = _client(lambda *a: _resp(obj=[{"id": "1"}]))
    cli.list_documents(filter="year eq 2024", top=5, skip=10)
    url = fake.calls[0]["url"]
    assert url.startswith("https://localhost:58452/datev/api/dms/v2/documents?")
    assert "top=5" in url and "skip=10" in url and "filter=" in url


def test_get_document_file_returns_raw_bytes():
    pdf = b"%PDF-1.4 binary"
    cli, _ = _client(lambda *a: _resp(body=pdf, headers={"content-type": "application/octet-stream"}))
    assert cli.get_document_file("file-123") == pdf


def test_get_document_encodes_path_param():
    cli, fake = _client(lambda *a: _resp(obj={"id": "a/b"}))
    cli.get_document("a/b uuid")
    assert "/documents/a%2Fb%20uuid" in fake.calls[0]["url"]


# --- error mapping ---------------------------------------------------------
def test_401_raises_auth_error():
    cli, _ = _client(lambda *a: _resp(401, body="nope"))
    with pytest.raises(DatevAuthError):
        cli.get_info()


def test_license_envelope_on_2xx_raises_license_error():
    env = {"error": "no_license",
           "error_description": "No License found for component K0001928 ... product 63218"}
    cli, _ = _client(lambda *a: _resp(200, obj=env))
    with pytest.raises(DatevLicenseError):
        cli.get_info()


def test_4xx_error_envelope_maps_description():
    env = {"error_description": "Dokument nicht gefunden"}
    cli, _ = _client(lambda *a: _resp(404, obj=env))
    with pytest.raises(DatevError) as ei:
        cli.get_document("missing")
    assert "nicht gefunden" in str(ei.value)
    assert not isinstance(ei.value, DatevLicenseError)


# --- url builder -----------------------------------------------------------
def test_build_url_query_and_missing_param():
    assert build_url("https://h/v2/", "/documents", query={"top": 5, "skip": None}) == \
        "https://h/v2/documents?top=5"
    with pytest.raises(ValueError):
        build_url("https://h/v2", "/documents/{id}", params={})


def test_no_auth_header_without_credentials():
    cfg = DatevConfig(base_url="https://h/v2")  # SSO/anonymous: no Basic header
    fake = _Fake(lambda *a: _resp(obj={"feature": "DokAB"}))
    DatevConnectClient(cfg, fake).get_info()
    assert "Authorization" not in fake.calls[0]["headers"]


# --- SSO curl arg builder (the other DATEV programs self-authenticate) -----
def test_build_curl_args_uses_negotiate_and_drops_auth_header():
    args = build_curl_args("GET", "https://h/v2/info",
                           {"Accept": "application/json", "Authorization": "Basic x"},
                           allow_self_signed=False, out_path="/tmp/o", has_body=False)
    assert "--negotiate" in args and args[args.index("-u") + 1] == ":"  # current Windows user
    assert args[args.index("-X") + 1] == "GET"
    assert args[-1] == "https://h/v2/info"                              # url last
    assert "Accept: application/json" in args                          # forwarded
    assert not any("Authorization" in a for a in args)                 # SSO does the auth
    assert "-k" not in args                                            # strict TLS by default


def test_build_curl_args_self_signed_and_body():
    args = build_curl_args("POST", "https://h/v2/documents", {}, allow_self_signed=True,
                           out_path="/tmp/o", has_body=True)
    assert "-k" in args                                                # tolerate self-signed
    assert "--data-binary" in args and args[args.index("--data-binary") + 1] == "@-"
