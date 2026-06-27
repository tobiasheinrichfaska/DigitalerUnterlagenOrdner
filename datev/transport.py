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

# Hide the curl.exe console window on Windows — otherwise each SSO call flashes a window
# in the windowed exe (mirrors OPOS datev_api._NO_WINDOW).
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


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


def parse_header_dump(text):
    """Last response block of a curl ``-D`` dump → a lowercased header dict (Negotiate makes
    curl emit a 401 block then the final block; we want the final one's headers, e.g. Location)."""
    blocks = [b for b in text.replace("\r\n", "\n").split("\n\n") if b.strip()]
    out = {}
    for line in (blocks[-1].splitlines() if blocks else []):
        if ":" in line and not line.startswith("HTTP/"):
            k, _, v = line.partition(":")
            out[k.strip().lower()] = v.strip()
    return out


def build_curl_args(method, url, headers, allow_self_signed, out_path, body_path=None,
                    header_path=None, curl="curl.exe"):
    """Pure: the curl command line for one SSO request — mirrors OPOS's hardened ``curl_args``.
    ``--negotiate -u :`` authenticates as the current Windows user; ``--http1.1`` avoids the
    HTTP/2 framing errors that show up as ``http_code 000`` on large bodies (the big documents
    list); bounded timeouts + one retry let a transient drop self-heal; ``--compressed`` shrinks
    big JSON. Status → stdout (``-w``), body → ``out_path`` (``-o``, binary-safe so a fetched PDF
    survives). A request body is passed as a **file** (``--data-binary @<path>``), NOT stdin:
    Negotiate sends an unauthenticated probe first and must **replay** the body on the
    authenticated retry — a streamed stdin body can't be rewound, so a POST/PUT would stall.
    We never forward an Authorization header — SSO does the auth."""
    args = [curl, "-sS", "--http1.1", "--negotiate", "-u", ":",
            "--connect-timeout", "15", "--max-time", "45",
            "--retry", "1", "--retry-connrefused", "--retry-delay", "2",
            "--compressed", "-X", method, "-w", "%{http_code}", "-o", out_path]
    if header_path is not None:
        args += ["-D", header_path]     # dump response headers (Location carries a created id)
    if allow_self_signed:
        args.append("-k")
    for key, value in (headers or {}).items():
        if key.lower() == "authorization":
            continue
        args += ["-H", f"{key}: {value}"]
    if body_path is not None:
        # Disable Expect:100-continue — DATEVconnect may not answer it, which stalls the POST
        # until curl's internal 1s fallback (and on some stacks longer); send the body straight.
        args += ["-H", "Expect:", "--data-binary", "@" + body_path]
    args.append(url)
    return args


def make_curl_sso_transport(allow_self_signed=False, timeout=60, curl="curl.exe"):
    # timeout > curl's own --max-time (45) so curl normally reports the real reason; this is
    # only the backstop if curl wedges and ignores --max-time (then Python kills it at 60s,
    # not 5 min, so a hang always surfaces fast).
    def transport(method, url, headers, body=None):
        fd, out_path = tempfile.mkstemp(prefix="datevprobe_")
        os.close(fd)
        hfd, header_path = tempfile.mkstemp(prefix="datevprobe_hdr_")
        os.close(hfd)
        body_path = None
        if body is not None:                       # write the body to a re-readable file
            bfd, body_path = tempfile.mkstemp(prefix="datevprobe_body_")
            with os.fdopen(bfd, "wb") as bf:
                bf.write(body)
        try:
            args = build_curl_args(method, url, headers, allow_self_signed, out_path,
                                   body_path, header_path, curl)
            try:
                proc = subprocess.run(args, capture_output=True, timeout=timeout,
                                      creationflags=_NO_WINDOW)
            except subprocess.TimeoutExpired:
                raise DatevError(f"Zeitüberschreitung nach {timeout}s — {method} {url} ohne Antwort.")
            status_text = proc.stdout.decode("ascii", "ignore").strip()[-3:]
            status = int(status_text) if status_text.isdigit() else 0
            with open(out_path, "rb") as f:
                data = f.read()
            with open(header_path, "r", encoding="utf-8", errors="replace") as f:
                resp_headers = parse_header_dump(f.read())
            if status == 0:  # curl itself failed (no HTTP exchange) — surface its stderr
                err = proc.stderr.decode("utf-8", "replace").strip()
                raise DatevError(f"SSO/curl fehlgeschlagen: {err or 'kein Statuscode (curl.exe vorhanden?)'}")
            return HttpResponse(status, resp_headers, data)
        finally:
            for p in (out_path, header_path, body_path):
                if p:
                    try:
                        os.remove(p)
                    except OSError:
                        pass

    return transport
