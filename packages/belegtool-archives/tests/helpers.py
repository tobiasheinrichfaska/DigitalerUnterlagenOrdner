# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Test helper: tiny hand-written PDF bytes (the library only checks the %PDF header)."""


def create_valid_pdf(pages=1) -> bytes:
    kids = " ".join(f"{3 + i} 0 R" for i in range(pages))
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>",
    ] + ["<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>"] * pages
    out = "%PDF-1.4\n"
    for i, o in enumerate(objs, 1):
        out += f"{i} 0 obj\n{o}\nendobj\n"
    out += f"trailer\n<< /Root 1 0 R /Size {len(objs) + 1} >>\n%%EOF\n"
    return out.encode("latin-1")
