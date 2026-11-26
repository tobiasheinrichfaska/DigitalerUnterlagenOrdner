# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""The host's thin re-exports must be the SAME objects as the package's (single implementation)."""

import belegtool_compress.compress as pkg_compress
import belegtool_compress.cpu as pkg_cpu
from formats import compress_pdf_bytes as shim_compress
from services import cpu as shim_cpu


def test_compress_reexport_is_package_object():
    for name in ("compress_all_methods", "compress_pdf_bytes", "CompressionCancelled",
                 "CompressionConfig", "DEFAULT_CONFIG", "reencode_pdf_structure",
                 "recompress_with_pikepdf"):
        assert getattr(shim_compress, name) is getattr(pkg_compress, name), name


def test_cpu_reexport_is_package_object():
    for name in ("worker_count", "set_current_thread_below_normal", "default_sampler",
                 "SystemCpuSampler", "is_remote_session", "default_budget_for_ram",
                 "total_physical_ram", "CAP_LOCAL", "CAP_REMOTE"):
        assert getattr(shim_cpu, name) is getattr(pkg_cpu, name), name
