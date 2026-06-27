"""Data-driven DATEVconnect DMS v2 endpoint catalog + URL builder. Round 1 = read only.
(Round 2 will add the create/exchange POST+PUT endpoints; kept out until then so the
read probe can't accidentally write.)"""
from urllib.parse import quote, urlencode

# name -> (HTTP method, path template with {placeholders})
ENDPOINTS = {
    "info": ("GET", "/info"),
    "domains": ("GET", "/domains"),
    "documents": ("GET", "/documents"),
    "document": ("GET", "/documents/{id}"),
    "structure_items": ("GET", "/documents/{id}/structure-items"),
    "document_file": ("GET", "/document-files/{file_id}"),
}


def build_url(base_url, path_template, params=None, query=None):
    """Compose base + path (with URL-encoded path params) + optional query string."""
    base = base_url.rstrip("/")
    path = path_template
    for key, value in (params or {}).items():
        path = path.replace("{" + key + "}", quote(str(value), safe=""))
    if "{" in path:
        raise ValueError(f"missing path param in {path_template!r}")
    qs = urlencode({k: v for k, v in (query or {}).items() if v is not None})
    return f"{base}{path}" + (f"?{qs}" if qs else "")
