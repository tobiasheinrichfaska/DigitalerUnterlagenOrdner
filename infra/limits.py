# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Thin re-export: the bomb-guard caps live in the separable package ``belegtool_archives``
(packages/belegtool-archives). Kept so ``from infra.limits import ...`` stays valid."""

from belegtool_archives.limits import *  # noqa: F401,F403
from belegtool_archives.limits import (  # noqa: F401  (underscore name not covered by *)
    _SAFE_ZIP_COMPRESS_TYPES,
    BOMB_CAP_BYTES,
    BOMB_CAP_ENTRIES,
    unsupported_zip_member,
)
