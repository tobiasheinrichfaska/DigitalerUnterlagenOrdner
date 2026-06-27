"""Data-driven DATEVconnect DMS v2 endpoint catalog + URL builder.

Full surface: read endpoints, the create endpoints (upload a file + create a document), and
the exchange (PUT structure-item) + delete endpoints. The in-app write-back uses GET document /
GET document-file / POST document-file / PUT structure-item; the create flow adds POST documents;
the probe additionally uses the read/list + DELETE endpoints."""
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
    # --- create (round 2a) ---
    "document_files_create": ("POST", "/document-files"),   # octet-stream body -> {id}
    "documents_create": ("POST", "/documents"),             # DocumentCreate JSON -> Document
    # --- exchange / delete (round 2b) ---
    "structure_item_update": ("PUT", "/documents/{id}/structure-items/{sid}"),  # swap the file
    "documents_delete": ("DELETE", "/documents/{id}"),       # remove our test document
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
