"""Unit tests for the CPU-fairness primitives (services/cpu.py).

All OS calls are injected/forced, so these run deterministically on any host.
"""

from services.cpu import (
    CAP_LOCAL,
    CAP_REMOTE,
    SystemCpuSampler,
    is_remote_session,
    worker_count,
)


# --- worker_count ----------------------------------------------------------

def test_worker_count_local_caps_at_cores_minus_one():
    # 6 cores, local → min(CAP_LOCAL, 5)
    assert worker_count(env={}, cpu_count=6, remote=False) == min(CAP_LOCAL, 5)


def test_worker_count_remote_uses_lower_cap():
    # plenty of cores but an RDP session → the remote cap dominates
    assert worker_count(env={}, cpu_count=16, remote=True) == CAP_REMOTE
    assert CAP_REMOTE < CAP_LOCAL


def test_worker_count_single_core_is_at_least_one():
    assert worker_count(env={}, cpu_count=1, remote=False) == 1
    assert worker_count(env={}, cpu_count=2, remote=True) == 1


def test_worker_count_env_override_wins():
    assert worker_count(env={"BELEG_WORKERS": "7"}, cpu_count=2, remote=True) == 7
    # invalid / zero override is ignored → falls back to the computed value
    assert worker_count(env={"BELEG_WORKERS": "0"}, cpu_count=6, remote=False) == min(CAP_LOCAL, 5)
    assert worker_count(env={"BELEG_WORKERS": "x"}, cpu_count=6, remote=False) == min(CAP_LOCAL, 5)


def test_is_remote_session_force_seam():
    assert is_remote_session(_force=True) is True
    assert is_remote_session(_force=False) is False


# --- SystemCpuSampler ------------------------------------------------------

def test_sampler_first_call_has_no_baseline():
    s = SystemCpuSampler(reader=lambda: (0, 0, 0))
    assert s.load() == 0.0  # no previous sample yet


def test_sampler_computes_busy_fraction_from_deltas():
    # scripted (idle, kernel, user) cumulative tuples; kernel includes idle.
    samples = iter([
        (100, 200, 50),   # baseline
        (150, 300, 150),  # Δidle=50, Δkernel=100, Δuser=100 → total=200, busy=150
    ])
    s = SystemCpuSampler(reader=lambda: next(samples))
    assert s.load() == 0.0          # baseline
    assert abs(s.load() - 0.75) < 1e-9  # busy 150 / total 200


def test_sampler_fully_busy_and_fully_idle():
    busy = iter([(0, 0, 0), (0, 100, 100)])    # Δidle=0 → 100% busy
    s = SystemCpuSampler(reader=lambda: next(busy))
    s.load()
    assert s.load() == 1.0

    idle = iter([(0, 0, 0), (200, 200, 0)])    # Δidle=200, Δtotal=200 → 0% busy
    s2 = SystemCpuSampler(reader=lambda: next(idle))
    s2.load()
    assert s2.load() == 0.0


def test_sampler_unknown_reading_assumes_idle():
    s = SystemCpuSampler(reader=lambda: None)
    assert s.load() == 0.0
