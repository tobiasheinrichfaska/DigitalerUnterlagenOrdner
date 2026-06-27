"""Real HTTP transport over stdlib urllib (Basic auth header is added by the client;
here we only handle the request + self-signed TLS tolerance for DATEVconnect's localhost
cert). SSO/Negotiate is out of scope for round 1 — Basic UPN works on the DokAB box."""
import ssl
import urllib.error
import urllib.request

from .types import HttpResponse


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
