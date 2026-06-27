"""HTTP transports for the probe:
  • make_urllib_transport  — stdlib urllib + Basic (the client adds the Basic header);
  • make_curl_sso_transport — Windows SSO (Negotiate) as the current user via curl.exe,
    matching how the other DATEV programs authenticate (no username/password needed).
Both tolerate DATEVconnect's self-signed localhost cert when asked. HTTP is injected, so
the client stays testable; the curl ARG construction is a pure, tested helper."""
import os
import ssl
import subprocess
import tempfile
import urllib.error
import urllib.request

from .types import DatevError, HttpResponse


def make_urllib_transport(allow_self_signed=False, timeout=30):
    ctx = ssl.create_default_context()
    if allow_self_signed:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    def transport(method, url, headers, body=None):
        req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return HttpResponse(resp.status, dict(resp.headers.items()), resp.read())
        except urllib.error.HTTPError as e:
            # A 4xx/5xx is a normal response we want to inspect (license envelope, 401, …),
            # not an exception — hand the body back to the client for error mapping.
            body_bytes = e.read() if hasattr(e, "read") else b""
            headers_out = dict(e.headers.items()) if e.headers else {}
            return HttpResponse(e.code, headers_out, body_bytes or b"")

    return transport


def build_curl_args(method, url, headers, allow_self_signed, out_path, has_body, curl="curl.exe"):
    """Pure: the curl command line for one SSO request. ``--negotiate -u :`` authenticates
    as the current Windows user; the status goes to stdout (``-w``), the body to ``out_path``
    (``-o``, binary-safe), the request body (round 2) comes from stdin. We never forward an
    Authorization header — SSO does the auth."""
    args = [curl, "-s", "-S", "--negotiate", "-u", ":", "-X", method,
            "-w", "%{http_code}", "-o", out_path]
    if allow_self_signed:
        args.append("-k")
    for key, value in (headers or {}).items():
        if key.lower() == "authorization":
            continue
        args += ["-H", f"{key}: {value}"]
    if has_body:
        args += ["--data-binary", "@-"]
    args.append(url)
    return args


def make_curl_sso_transport(allow_self_signed=False, timeout=30, curl="curl.exe"):
    def transport(method, url, headers, body=None):
        fd, out_path = tempfile.mkstemp(prefix="datevprobe_")
        os.close(fd)
        try:
            args = build_curl_args(method, url, headers, allow_self_signed, out_path,
                                   body is not None, curl)
            proc = subprocess.run(args, input=body, capture_output=True, timeout=timeout)
            status_text = proc.stdout.decode("ascii", "ignore").strip()[-3:]
            status = int(status_text) if status_text.isdigit() else 0
            with open(out_path, "rb") as f:
                data = f.read()
            if status == 0:  # curl itself failed (no HTTP exchange) — surface its stderr
                err = proc.stderr.decode("utf-8", "replace").strip()
                raise DatevError(f"SSO/curl fehlgeschlagen: {err or 'kein Statuscode (curl.exe vorhanden?)'}")
            return HttpResponse(status, {}, data)
        finally:
            try:
                os.remove(out_path)
            except OSError:
                pass

    return transport
