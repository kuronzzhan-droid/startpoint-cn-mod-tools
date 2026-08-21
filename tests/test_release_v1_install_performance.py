"""Fixed temporary-target performance evidence for installer and recovery."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tests.test_release_v1_performance import (
    _benchmark_environment,
    _guard_sparse_sentinel,
    _make_sparse_file,
)
import tests.test_release_v1_vertical as vertical
from wf_release_v1.canonical import canonical_json_bytes
from wf_release_v1.transaction import install_release


_SENTINEL_BYTES = 10 * 1024 * 1024 * 1024
_PHASES = (
    "releaseVerify",
    "objectImport",
    "materialize",
    "candidateVerify",
    "stopStart",
    "health",
    "capabilities",
    "rollback",
)


def _timed(stack: ExitStack, owner: object, name: str, bucket: dict[str, float], label: str) -> None:
    original = getattr(owner, name)

    def observed(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            bucket[label] += time.perf_counter() - started

    stack.enter_context(patch.object(owner, name, observed))


def _sample(*, recovery: bool, sentinel_source: Path) -> dict[str, float | int]:
    import wf_release_v1.materialize as materialize
    import wf_release_v1.probe as probe
    import wf_release_v1.transaction as transaction

    case = vertical.CharacterInstallVerticalTests(
        "test_combined_mode_release_is_accepted_only_after_restart"
    )
    case.setUp()
    sentinel = case.target.component_roots.content / "undeclared-ten-gb-sentinel.bin"
    os.link(sentinel_source, sentinel)
    sentinel_bytes = sentinel_source.stat().st_size
    phases = {name: 0.0 for name in _PHASES}
    candidate_hashes = 0
    real_hash = materialize._hash_stable

    def observed_hash(path: Path, *, candidate: bool):
        nonlocal candidate_hashes
        if candidate:
            candidate_hashes += 1
        return real_hash(path, candidate=candidate)

    platform = vertical._VerticalPlatform(
        case.target,
        case.contract,
        wrong_mode=recovery,
    )
    started = time.perf_counter()
    try:
        with ExitStack() as stack:
            _guard_sparse_sentinel(stack, sentinel)
            _timed(
                stack,
                transaction,
                "verify_release_contract",
                phases,
                "releaseVerify",
            )
            _timed(stack, transaction, "import_verified_object", phases, "objectImport")
            _timed(stack, transaction, "materialize_candidates", phases, "materialize")
            _timed(stack, transaction, "verify_candidates", phases, "candidateVerify")
            _timed(stack, transaction, "wait_health_ready", phases, "health")
            _timed(stack, transaction, "_restore_components", phases, "rollback")
            _timed(stack, probe.TargetProbe, "run", phases, "capabilities")
            _timed(stack, platform, "start_server", phases, "stopStart")
            _timed(stack, platform, "stop_owned", phases, "stopStart")
            stack.enter_context(patch.object(materialize, "_hash_stable", observed_hash))
            result = install_release(
                case.mode_release,
                case.target,
                platform,
                health_timeout=2,
            )
        expected = "recovered" if recovery else "succeeded"
        if result.outcome != expected:
            raise AssertionError((result, expected))
        if sentinel.stat().st_size != sentinel_bytes:
            raise AssertionError("undeclared sparse sentinel changed")
        return {
            **phases,
            "total": time.perf_counter() - started,
            "candidateHashCalls": candidate_hashes,
        }
    finally:
        case.doCleanups()


def collect_install_benchmark(
    runs: int,
    *,
    sentinel_bytes: int = _SENTINEL_BYTES,
) -> dict[str, object]:
    if type(runs) is not int or runs < 1:
        raise ValueError("runs must be a positive integer")
    if type(sentinel_bytes) is not int or sentinel_bytes <= 0:
        raise ValueError("sentinel bytes must be a positive integer")
    with tempfile.TemporaryDirectory(prefix="wfrel-install-benchmark-") as temporary:
        sentinel_source = Path(temporary) / "sparse-sentinel.bin"
        _make_sparse_file(sentinel_source, sentinel_bytes)
        vertical.CharacterInstallVerticalTests.setUpClass()
        try:
            success = [
                _sample(recovery=False, sentinel_source=sentinel_source)
                for _ in range(runs)
            ]
            recovery = [
                _sample(recovery=True, sentinel_source=sentinel_source)
                for _ in range(runs)
            ]
        finally:
            vertical.CharacterInstallVerticalTests.doClassCleanups()

    def medians(samples: list[dict[str, float | int]]) -> dict[str, float | int]:
        result: dict[str, float | int] = {}
        for field in (*_PHASES, "total", "candidateHashCalls"):
            value = statistics.median(item[field] for item in samples)
            result[field] = int(value) if field == "candidateHashCalls" else value
        return result

    return {
        "schemaVersion": 1,
        "environment": _benchmark_environment(),
        "runs": {"success": success, "recovery": recovery},
        "median": {"success": medians(success), "recovery": medians(recovery)},
        "sentinelBytes": sentinel_bytes,
        "metricScope": "nested phase wall time; values overlap and do not sum to total",
    }


class InstallPerformanceTests(unittest.TestCase):
    def test_fixed_fixture_records_success_recovery_and_bounded_scan_evidence(self) -> None:
        ci_sentinel = 1024 * 1024 * 1024
        evidence = collect_install_benchmark(1, sentinel_bytes=ci_sentinel)
        self.assertEqual(ci_sentinel, evidence["sentinelBytes"])
        for lane in ("success", "recovery"):
            sample = evidence["runs"][lane][0]  # type: ignore[index]
            self.assertGreater(sample["total"], 0)
            self.assertGreater(sample["candidateHashCalls"], 0)
            for phase in _PHASES:
                if lane == "success" and phase == "rollback":
                    self.assertEqual(0, sample[phase])
                else:
                    self.assertGreater(sample[phase], 0)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 wf-release-v1 安装器同机性能基线 JSON")
    parser.add_argument("--benchmark", action="store_true", required=True)
    parser.add_argument("--runs", type=int, default=5)
    arguments = parser.parse_args(argv)
    sys.stdout.buffer.write(canonical_json_bytes(collect_install_benchmark(arguments.runs)))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
