"""Data-driven DATEVconnect DMS v2 endpoint catalog + URL builder.

Read endpoints (round 1) and the **create-only** write endpoints (round 2a): upload a file
and create a document. The exchange (PUT) + delete endpoints are still withheld until round
2b, so the create-only probe cannot modify or remove an existing document."""
from urllib.parse import quote, urlencode

# name -> (HTTP method, path template with {placeholders})
ENDPOINTS = {
    # --- read (round 1) ---
    "info": ("GET", "/info"),
    "domains": ("GET", "/domains"),
    "documents": ("GET", "/documents"),
    "document": ("GET", "/documents/{id}"),
    "structure_items": ("GET", "/documents/{id}/structure-items"),
    "document_file": ("GET", "/document-files/{file_id}"),
    "documentstates": ("GET", "/documentstates"),
    # --- create only (round 2a) ---
    "document_files_create": ("POST", "/document-files"),   # octet-stream body -> {id}
    "documents_create": ("POST", "/documents"),             # DocumentCreate JSON -> Document
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
