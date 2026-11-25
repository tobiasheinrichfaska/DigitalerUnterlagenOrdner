"""Thin re-export of the CPU-fairness primitives of the separable package ``belegtool_compress``
(packages/belegtool-compress, module ``belegtool_compress.cpu``).

Kept so ``services.render_service``, ``host`` and ``core.api`` keep their import paths.
"""

from belegtool_compress.cpu import (  # noqa: F401
    CAP_LOCAL,
    CAP_REMOTE,
    IS_WINDOWS,
    SystemCpuSampler,
    default_budget_for_ram,
    default_sampler,
    is_remote_session,
    set_current_thread_below_normal,
    total_physical_ram,
    worker_count,
)
