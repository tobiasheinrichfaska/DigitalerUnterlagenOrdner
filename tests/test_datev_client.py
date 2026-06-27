"""DATEVconnect read client (round 1) — unit-tested with a fake transport (no live
DATEVconnect). Covers feature detection, the read calls, query/path building, Basic auth,
and the 401 / license / error mappings."""
import base64
import json

import pytest

from datev.client import DatevConnectClient
from datev.config import (
    dms_base_url,
    is_loopback,
    master_data_base_url,
    resolve_auth_mode,
    self_signed_allowed,
)
from datev.endpoints import build_url
from datev.synthetic_pdf import make_test_pdf
from datev.transport import build_curl_args, parse_header_dump
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


# --- write: create only (round 2a) -----------------------------------------
def test_resolve_client_guid_finds_by_number():
    # master-data returns an envelope {clients: [...]}; match on number → GUID.
    body = {"clients": [{"id": "g-1", "number": 10000, "name": "Muster GmbH"},
                        {"id": "g-2", "number": 10001, "name": "Beispiel AG"}]}
    cli, fake = _client(lambda *a: _resp(obj=body))
    res = cli.resolve_client_guid(10001)
    assert res["guid"] == "g-2" and res["name"] == "Beispiel AG"
    # the lookup goes to the master-data base, not the DMS base
    assert fake.calls[0]["url"] == "https://localhost:58452/datev/api/master-data/v1/clients"


def test_resolve_client_guid_not_found_raises():
    cli, _ = _client(lambda *a: _resp(obj=[{"id": "g-1", "number": 10000}]))
    with pytest.raises(DatevError):
        cli.resolve_client_guid(99999)


def test_upload_document_file_posts_octet_stream_and_returns_id():
    seen = {}

    def handler(method, url, headers, body):
        seen.update(method=method, ctype=headers.get("Content-Type"), body=body)
        return _resp(obj={"id": 1489})

    cli, _ = _client(handler)
    assert cli.upload_document_file(b"%PDF-1.4 x") == 1489
    assert seen["method"] == "POST"
    assert seen["ctype"] == "application/octet-stream"
    assert seen["body"] == b"%PDF-1.4 x"          # raw bytes, binary-safe


def test_upload_document_file_coerces_string_id_to_int():
    # DATEV returns the file id as a STRING; create wants an int → must coerce.
    cli, _ = _client(lambda *a: _resp(obj={"id": "1085408"}))
    fid = cli.upload_document_file(b"%PDF-1.4 x")
    assert fid == 1085408 and isinstance(fid, int)


def test_create_document_posts_json_body_and_returns_doc():
    seen = {}

    def handler(method, url, headers, body):
        seen.update(method=method, ctype=headers.get("Content-Type"), body=body)
        return _resp(obj={"id": "doc-guid", "change_date_time": "2026-06-27T10:00:00"})

    cli, _ = _client(handler)
    payload = {"class": {"id": 1}, "correspondence_partner_guid": "g-2",
               "structure_items": [{"name": "x.pdf", "type": 1, "document_file_id": 1489}]}
    doc = cli.create_document(payload)
    assert doc["id"] == "doc-guid"
    assert seen["method"] == "POST" and seen["ctype"] == "application/json"
    assert json.loads(seen["body"])["correspondence_partner_guid"] == "g-2"


def test_create_document_recovers_id_from_location_when_body_empty():
    # the live box may answer 201 + empty body + Location header (no JSON id).
    loc = "https://h/v2/documents/doc-guid-xyz"
    cli, _ = _client(lambda *a: _resp(201, body=b"", headers={"location": loc}))
    doc = cli.create_document({"class": {"id": 1}})
    assert doc["id"] == "doc-guid-xyz" and doc["http_status"] == 201 and doc["location"] == loc


def test_create_document_license_error_maps():
    env = {"error_description": "No License found for component K0001928 ... product 63218"}
    cli, _ = _client(lambda *a: _resp(200, obj=env))
    with pytest.raises(DatevLicenseError):
        cli.create_document({"class": {"id": 1}})


def test_synthetic_pdf_is_valid_single_page_with_marker():
    b = make_test_pdf("ZZZ TEST bitte loeschen")
    assert b.startswith(b"%PDF-") and b.rstrip().endswith(b"%%EOF")
    assert b"ZZZ TEST bitte loeschen" in b      # the marker text is in the content stream


def test_synthetic_pdf_renders_umlauts_winansi():
    b = make_test_pdf("löschen –")
    assert b"/WinAnsiEncoding" in b              # font set so umlauts/en-dash render
    assert "löschen".encode("cp1252") in b       # ö encoded as WinAnsi 0xF6, not '?'


def test_update_structure_item_puts_id_and_file():
    seen = {}

    def handler(method, url, headers, body):
        seen.update(method=method, url=url, body=body)
        return _resp(200, body=b"")

    cli, _ = _client(handler)
    res = cli.update_structure_item("doc-guid", 1085409, 1085411, revision_comment="x")
    assert seen["method"] == "PUT"
    assert "/documents/doc-guid/structure-items/1085409" in seen["url"]
    sent = json.loads(seen["body"])
    assert sent["id"] == 1085409 and sent["document_file_id"] == 1085411
    assert res["http_status"] == 200


def test_parse_checkout_path_extracts_guid_and_file_id():
    from datev.provenance import parse_checkout_path
    p = r"C:\Users\x\AppData\Local\Temp\DATEV\fa89ad42-8cd4-4828-8234-143161d41985\1085411.pdf"
    out = parse_checkout_path(p)
    assert out == {"doc_guid": "fa89ad42-8cd4-4828-8234-143161d41985", "file_id": 1085411}
    assert parse_checkout_path("nothing-here.pdf") == {}
    assert parse_checkout_path(r"\\srv\fa89ad42-8cd4-4828-8234-143161d41985\1085411") \
        ["doc_guid"] == "fa89ad42-8cd4-4828-8234-143161d41985"
    # anchored: a GUID folder that is NOT the file's parent must NOT be captured (no false
    # "from DATEV" for an ordinary file that merely lives under a GUID-named directory).
    assert parse_checkout_path(
        r"C:\fa89ad42-8cd4-4828-8234-143161d41985\sub\rechnung.pdf") == {}


def test_provenance_stats_and_match():
    from datev.provenance import match_entries, provenance_stats
    entries = [
        {"doc_id": "A", "desc": "Rechnung 1", "name": "r1.pdf", "size": 100, "file_id": 1},
        {"doc_id": "B", "desc": "Rechnung 2", "name": "r2.pdf", "size": 100, "file_id": 2},  # size collision
        {"doc_id": "C", "desc": "Bescheid", "name": "b.pdf", "size": 250, "file_id": 3},
    ]
    st = provenance_stats(entries)
    assert st["files"] == 3
    assert st["unique_size"] == 1            # only size 250 is unique
    assert st["unique_title"] == 3           # all titles distinct
    assert st["unique_size_title"] == 3      # size+title always distinct here
    assert st["worst_size_collision"] == 2
    assert len(match_entries(entries, size=100)) == 2                 # ambiguous
    assert len(match_entries(entries, size=100, title="Rechnung 1")) == 1  # disambiguated
    assert match_entries(entries, size=999) == []


def test_delete_document_sends_delete():
    seen = {}
    cli, _ = _client(lambda m, u, h, b: seen.update(method=m, url=u) or _resp(204, body=b""))
    res = cli.delete_document("doc-guid")
    assert seen["method"] == "DELETE" and seen["url"].endswith("/documents/doc-guid")
    assert res["http_status"] == 204


def test_master_data_base_url_pins_path_from_dms_base():
    assert master_data_base_url("https://DatevHeinrich:58452/datev/api/dms/v2") == \
        "https://DatevHeinrich:58452/datev/api/master-data/v1"
    assert master_data_base_url("") == "https://localhost:58452/datev/api/master-data/v1"


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
                           allow_self_signed=False, out_path="/tmp/o", body_path=None)
    assert "--negotiate" in args and args[args.index("-u") + 1] == ":"  # current Windows user
    assert "--http1.1" in args                                         # OPOS hardening (avoids 000)
    assert args[args.index("-X") + 1] == "GET"
    assert args[-1] == "https://h/v2/info"                              # url last
    assert "Accept: application/json" in args                          # forwarded
    assert not any("Authorization" in a for a in args)                 # SSO does the auth
    assert "-k" not in args                                            # strict TLS by default
    assert "--data-binary" not in args                                 # no body on a GET


def test_parse_header_dump_takes_final_block_location():
    dump = ("HTTP/1.1 401 Unauthorized\r\nWWW-Authenticate: Negotiate\r\n\r\n"
            "HTTP/1.1 201 Created\r\nLocation: https://h/v2/documents/abc\r\n"
            "Content-Length: 0\r\n\r\n")
    h = parse_header_dump(dump)
    assert h["location"] == "https://h/v2/documents/abc"
    assert "www-authenticate" not in h          # the 401 block is ignored


def test_build_curl_args_self_signed_and_file_body():
    # body comes from a FILE (@path), not stdin (@-), so Negotiate can replay it on the retry.
    args = build_curl_args("POST", "https://h/v2/documents", {}, allow_self_signed=True,
                           out_path="/tmp/o", body_path="/tmp/body")
    assert "-k" in args                                                # tolerate self-signed
    assert "--data-binary" in args and args[args.index("--data-binary") + 1] == "@/tmp/body"


# --- connection config (mirrors OPOS datev_api) ----------------------------
def test_is_loopback():
    assert is_loopback("https://localhost:58452/x") and is_loopback("https://127.0.0.1/x")
    assert not is_loopback("https://server.firma.local/x")


def test_resolve_auth_mode_matches_opos():
    assert resolve_auth_mode({"auth": "basic"}) == "basic"   # explicit wins
    assert resolve_auth_mode({"auth": "sso"}) == "sso"
    assert resolve_auth_mode({"user": "u@d.local"}) == "basic"  # user present ⇒ Basic
    assert resolve_auth_mode({}) == "sso"                    # nothing ⇒ Windows SSO


def test_dms_base_url_pins_path_from_opos_accounting_config():
    # the live 404: OPOS config points at the accounting API; we keep the host, pin DMS.
    acc = {"base_url": "https://DatevHeinrich:58452/datev/api/accounting/v1"}
    assert dms_base_url(acc) == "https://DatevHeinrich:58452/datev/api/dms/v2"
    # already-correct DMS url is idempotent
    dms = {"base_url": "https://DatevHeinrich:58452/datev/api/dms/v2"}
    assert dms_base_url(dms) == "https://DatevHeinrich:58452/datev/api/dms/v2"
    # no/garbage base_url ⇒ default
    assert dms_base_url({}) == "https://localhost:58452/datev/api/dms/v2"
    assert dms_base_url({"base_url": "not-a-url"}) == "https://localhost:58452/datev/api/dms/v2"


def test_self_signed_allowed_loopback_default_and_override():
    assert self_signed_allowed({}, "https://localhost/x")            # loopback ⇒ trust
    assert not self_signed_allowed({}, "https://lan-host/x")         # LAN ⇒ strict
    assert self_signed_allowed({"verify_tls": False}, "https://lan-host/x")    # explicit wins
    assert not self_signed_allowed({"verify_tls": True}, "https://localhost/x")
