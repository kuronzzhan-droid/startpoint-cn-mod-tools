"""Fixed-fixture performance evidence for the wf-release-v1 vertical slice."""

from __future__ import annotations

import argparse
import builtins
from contextlib import ExitStack
import ctypes
import gc
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time
import tracemalloc
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from tests.release_v1_fixtures import make_patch_overlay, make_sealed_character_workspace
from tests.release_v1_schema_support import requirements_wire
from wf_release_v1.canonical import canonical_json_bytes
from wf_release_v1.schema import parse_requirements


_SPARSE_SENTINEL_BYTES = 1024 * 1024 * 1024
_PHASES = ("coldBuild", "repeatBuild", "singleFileChangeBuild", "verify")
_OVERLAY_FIXTURE_BYTES: tuple[bytes, bytes] | None = None

def _make_sparse_file(path: Path, size: int) -> None:
    """Create a logical large file without writing or allocating its contents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        if os.name == "nt":
            import msvcrt

            returned = ctypes.c_ulong(0)
            handle = msvcrt.get_osfhandle(stream.fileno())
            success = ctypes.windll.kernel32.DeviceIoControl(  # type: ignore[attr-defined]
                ctypes.c_void_p(handle),
                ctypes.c_ulong(0x000900C4),  # FSCTL_SET_SPARSE
                None,
                0,
                None,
                0,
                ctypes.byref(returned),
                None,
            )
            if not success:
                raise ctypes.WinError()
        stream.truncate(size)

def _fixed_overlay_bytes() -> tuple[bytes, bytes]:
    """Generate once so all five manual samples use byte-identical sources."""
    global _OVERLAY_FIXTURE_BYTES
    if _OVERLAY_FIXTURE_BYTES is None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = make_patch_overlay(
                root / "worldflipper-overlay-1.4.54-to-1.4.55.zip",
                from_version="1.4.54",
                target_version="1.4.55",
            )
            second = make_patch_overlay(
                root / "worldflipper-overlay-1.4.55-to-1.4.56.zip",
                from_version="1.4.55",
                target_version="1.4.56",
            )
            _OVERLAY_FIXTURE_BYTES = (first.read_bytes(), second.read_bytes())
    return _OVERLAY_FIXTURE_BYTES

def _same_path(candidate: object, target: Path) -> bool:
    if isinstance(candidate, int):
        return False
    try:
        return os.path.normcase(os.path.abspath(os.fspath(candidate))) == os.path.normcase(
            os.path.abspath(os.fspath(target))
        )
    except TypeError:
        return False

class _ReaderProbe:
    def __init__(self, stream, evidence: dict[str, int]) -> None:
        self._stream = stream
        self._evidence = evidence

    def __enter__(self):
        self._stream.__enter__()
        return self

    def __exit__(self, exc_type, exc, traceback):
        return self._stream.__exit__(exc_type, exc, traceback)

    def read(self, size: int = -1):
        raw = self._stream.read(size)
        self._evidence["readCalls"] += 1
        self._evidence["bytesRead"] += len(raw)
        if not raw:
            self._evidence["eofReads"] += 1
        return raw

    def __getattr__(self, name: str):
        return getattr(self._stream, name)

class _DigestProbe:
    def __init__(self, digest, evidence: dict[str, int], initial: bytes) -> None:
        self._digest = digest
        self._evidence = evidence
        self._evidence["instances"] += 1
        self._evidence["bytesHashed"] += len(initial)

    def update(self, raw: bytes) -> None:
        self._evidence["bytesHashed"] += len(raw)
        self._digest.update(raw)

    def hexdigest(self) -> str:
        return self._digest.hexdigest()

class _OsProxy:
    def __init__(self, active: list[str | None], readers: dict[str, dict[str, int]]) -> None:
        self._active = active
        self._readers = readers

    def fdopen(self, descriptor: int, *args, **kwargs):
        stream = os.fdopen(descriptor, *args, **kwargs)
        label = self._active[0]
        if label is None:
            return stream
        evidence = self._readers.setdefault(
            label,
            {"instances": 0, "readCalls": 0, "bytesRead": 0, "eofReads": 0},
        )
        evidence["instances"] += 1
        return _ReaderProbe(stream, evidence)

    def __getattr__(self, name: str):
        return getattr(os, name)

def _measure(action):
    gc.collect()
    tracemalloc.start()
    started = time.perf_counter()
    try:
        result = action()
        wall_time = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, wall_time, peak

def _guard_sparse_sentinel(stack: ExitStack, sentinel: Path) -> None:
    """Fail immediately if any common open/read path reaches the 1 GiB sentinel."""
    real_builtin_open = builtins.open
    real_io_open = io.open
    real_path_open = Path.open
    real_os_open = os.open

    def builtin_open(candidate, *args, **kwargs):
        if _same_path(candidate, sentinel):
            raise AssertionError("build opened the undeclared sparse sentinel via builtins.open")
        return real_builtin_open(candidate, *args, **kwargs)

    def io_open(candidate, *args, **kwargs):
        if _same_path(candidate, sentinel):
            raise AssertionError("build opened the undeclared sparse sentinel via io.open")
        return real_io_open(candidate, *args, **kwargs)

    def path_open(candidate: Path, *args, **kwargs):
        if _same_path(candidate, sentinel):
            raise AssertionError("build opened the undeclared sparse sentinel via Path.open")
        return real_path_open(candidate, *args, **kwargs)

    def os_open(candidate, *args, **kwargs):
        if _same_path(candidate, sentinel):
            raise AssertionError("build opened the undeclared sparse sentinel via os.open")
        return real_os_open(candidate, *args, **kwargs)

    stack.enter_context(patch.object(builtins, "open", builtin_open))
    stack.enter_context(patch.object(io, "open", io_open))
    stack.enter_context(patch.object(Path, "open", path_open))
    stack.enter_context(patch.object(os, "open", os_open))

def _measure_build(request, sentinel: Path):
    """Measure the authoritative Producer copy/hash seam, not Task 4 ZIP inspection."""
    import wf_release_v1.producer as producer

    active: list[str | None] = [None]
    readers: dict[str, dict[str, int]] = {}
    digests: dict[str, dict[str, int]] = {}
    copy_calls: dict[str, int] = {}
    real_copy = producer._copy_pinned_source
    real_sha256 = hashlib.sha256

    def observed_copy(source):
        label = os.fspath(source.path)
        copy_calls[label] = copy_calls.get(label, 0) + 1
        active[0] = label
        try:
            return real_copy(source)
        finally:
            active[0] = None

    def observed_sha256(initial: bytes = b"", *args, **kwargs):
        digest = real_sha256(initial, *args, **kwargs)
        label = active[0]
        if label is None:
            return digest
        evidence = digests.setdefault(label, {"instances": 0, "bytesHashed": 0})
        return _DigestProbe(digest, evidence, initial)

    hash_proxy = SimpleNamespace(sha256=observed_sha256)
    os_proxy = _OsProxy(active, readers)
    with ExitStack() as stack:
        _guard_sparse_sentinel(stack, sentinel)
        stack.enter_context(patch.object(producer, "_copy_pinned_source", observed_copy))
        stack.enter_context(patch.object(producer, "hashlib", hash_proxy))
        stack.enter_context(patch.object(producer, "os", os_proxy))
        receipt, wall_time, peak = _measure(lambda: producer.build_character_release(request))

    expected = {os.fspath(path): path.stat().st_size for path in request.overlay_archives}
    if copy_calls != {label: 1 for label in expected}:
        raise AssertionError(("outer source copy call count", copy_calls, expected))
    for label, size in expected.items():
        reader = readers.get(label)
        digest = digests.get(label)
        if reader is None or digest is None:
            raise AssertionError(("missing source instrumentation", label))
        if reader["instances"] != 1 or reader["bytesRead"] != size or reader["eofReads"] != 1:
            raise AssertionError(("source was not traversed exactly once", label, reader, size))
        if digest != {"instances": 1, "bytesHashed": size}:
            raise AssertionError(("source was not fully hashed exactly once", label, digest, size))
    total = sum(expected.values())
    if (receipt.bytes_read, receipt.hash_count) != (total, len(expected)):
        raise AssertionError(("receipt disagrees with observed source work", receipt, expected))
    return receipt, {
        "wallTimeSeconds": wall_time,
        "peakTracemallocBytes": peak,
        "bytesRead": total,
        "hashCount": len(expected),
    }

def _measure_verify(release: Path):
    """Count the release payload SHA pass; metadata/Overlay structural reads are separate."""
    import wf_release_v1.verifier as verifier
    import wf_release_v1.verifier_zip as verifier_zip

    real_copy_hash = verifier.copy_hash_member
    evidence = {"bytesRead": 0, "hashCount": 0}
    digest_evidence = {"instances": 0, "bytesHashed": 0}
    digest_active = [False]
    real_sha256 = hashlib.sha256

    def observed_sha256(initial: bytes = b"", *args, **kwargs):
        digest = real_sha256(initial, *args, **kwargs)
        if not digest_active[0]:
            return digest
        return _DigestProbe(digest, digest_evidence, initial)

    def observed_copy_hash(stream, member, destination=None):
        reader = {"instances": 1, "readCalls": 0, "bytesRead": 0, "eofReads": 0}
        digest_active[0] = True
        try:
            result = real_copy_hash(_ReaderProbe(stream, reader), member, destination)
        finally:
            digest_active[0] = False
        if reader["bytesRead"] != member.size:
            raise AssertionError(("verifier did not read one full payload", member.name, reader))
        evidence["bytesRead"] += reader["bytesRead"]
        evidence["hashCount"] += 1
        return result

    with (
        patch.object(verifier, "copy_hash_member", observed_copy_hash),
        patch.object(verifier_zip, "hashlib", SimpleNamespace(sha256=observed_sha256)),
    ):
        report, wall_time, peak = _measure(lambda: verifier.verify_release(release))
    if report.payload_bytes != evidence["bytesRead"]:
        raise AssertionError(("verifier report disagrees with payload hash bytes", report, evidence))
    if digest_evidence != {
        "instances": evidence["hashCount"],
        "bytesHashed": evidence["bytesRead"],
    }:
        raise AssertionError(("verifier payload hash pass was not repeated exactly", digest_evidence))
    return report, {
        "wallTimeSeconds": wall_time,
        "peakTracemallocBytes": peak,
        **evidence,
    }

def _request(workspace: Path, overlays: tuple[Path, ...], output: Path):
    from wf_release_v1.producer import BuildRequest

    return BuildRequest(
        name="seris-dragon-king",
        version="1.0.0",
        workspace=workspace,
        overlay_archives=overlays,
        output=output,
        requirements=parse_requirements(requirements_wire()),
    )

def _exercise_fixed_fixture() -> dict[str, dict[str, float | int]]:
    import wf_release_v1.producer as producer

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        workspace = make_sealed_character_workspace(root / "workspace")
        sentinel = workspace / "unrelated" / "never-read.bin"
        _make_sparse_file(sentinel, _SPARSE_SENTINEL_BYTES)
        if sentinel.stat().st_size != _SPARSE_SENTINEL_BYTES:
            raise AssertionError("sparse sentinel has the wrong logical size")

        overlay_one = root / "sources" / "worldflipper-overlay-1.4.54-to-1.4.55.zip"
        overlay_two = root / "sources" / "worldflipper-overlay-1.4.55-to-1.4.56.zip"
        overlay_one.parent.mkdir()
        first_raw, second_raw = _fixed_overlay_bytes()
        overlay_one.write_bytes(first_raw)
        overlay_two.write_bytes(second_raw)
        overlay_identity = {
            path: (path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())
            for path in (overlay_one, overlay_two)
        }

        output = root / "output"
        output.mkdir()
        cold_receipt, cold = _measure_build(
            _request(workspace, (overlay_one, overlay_two), output / "cold.zip"),
            sentinel,
        )
        repeat_receipt, repeat = _measure_build(
            _request(workspace, (overlay_one, overlay_two), output / "repeat.zip"),
            sentinel,
        )

        # Prepare (outside the timed build) one changed, manifest-declared workspace
        # file and re-seal it. The explicit Overlay sources remain byte-identical.
        declared = (
            workspace
            / "package"
            / "roots"
            / "common"
            / "master"
            / "character"
            / "character.orderedmap"
        )
        changed_raw = b"character-table-single-file-change"
        declared.write_bytes(changed_raw)
        manifest_path = workspace / "package" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        claim = manifest["roots"]["common"][0]
        claim["size"] = len(changed_raw)
        claim["sha256"] = hashlib.sha256(changed_raw).hexdigest()
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        import wf_character_workspace

        sealed = wf_character_workspace.seal_workspace(workspace)
        if not sealed.release_ready:
            raise AssertionError("changed workspace did not re-seal")
        current_overlay_identity = {
            path: (path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())
            for path in (overlay_one, overlay_two)
        }
        if current_overlay_identity != overlay_identity:
            raise AssertionError("single workspace-file setup changed an Overlay source")
        changed_receipt, changed = _measure_build(
            _request(workspace, (overlay_one, overlay_two), output / "changed.zip"),
            sentinel,
        )

        if cold_receipt.archive_sha256 != repeat_receipt.archive_sha256:
            raise AssertionError("identical inputs did not produce identical archives")
        if cold_receipt.release_id != repeat_receipt.release_id:
            raise AssertionError("identical inputs did not produce identical release IDs")
        if cold_receipt.output.read_bytes() != repeat_receipt.output.read_bytes():
            raise AssertionError("identical inputs did not produce identical archive bytes")
        if changed_receipt.archive_sha256 == cold_receipt.archive_sha256:
            raise AssertionError("single source-file change did not change archive identity")

        with zipfile.ZipFile(cold_receipt.output) as bundle:
            for overlay in (overlay_one, overlay_two):
                member = f"wf-release-v1/content/{overlay.name}"
                if bundle.read(member) != overlay.read_bytes():
                    raise AssertionError(("Producer rewrote outer Overlay bytes", overlay.name))

        # A verifier call must remain independent from Producer/source inspection state.
        with (
            patch.object(
                producer,
                "_copy_pinned_source",
                side_effect=AssertionError("verify called the Producer copy seam"),
            ),
            patch.object(
                producer,
                "inspect_character_source",
                side_effect=AssertionError("verify called the Producer source inspector"),
            ),
        ):
            first_report, verify_metrics = _measure_verify(cold_receipt.output)
            second_report, repeat_verify_metrics = _measure_verify(cold_receipt.output)
        if first_report != second_report or verify_metrics["hashCount"] != 2:
            raise AssertionError(("repeated verify shared or skipped state", first_report, second_report))
        if repeat_verify_metrics["hashCount"] != verify_metrics["hashCount"]:
            raise AssertionError(("repeat verify did not repeat authoritative hashes", repeat_verify_metrics))

        return {
            "coldBuild": cold,
            "repeatBuild": repeat,
            "singleFileChangeBuild": changed,
            "verify": verify_metrics,
        }

def _benchmark_environment() -> dict[str, object]:
    temporary = Path(tempfile.gettempdir())
    storage = {"kind": "windows-volume" if os.name == "nt" else "posix-filesystem", "deviceId": str(temporary.stat().st_dev)}
    if os.name == "nt":
        storage["drive"] = temporary.drive.upper()
    environment = {
        "python": {"implementation": platform.python_implementation(),
                   "version": platform.python_version()},
        "platform": {"os": platform.system(), "architecture": platform.machine()},
        "temporaryStorage": storage,
    }
    if any(not isinstance(value, str) or not value.strip() for group in environment.values() for value in group.values()):
        raise ValueError("benchmark environment field is empty")
    return environment

def collect_benchmark(runs: int) -> dict[str, object]:
    if type(runs) is not int or runs < 1:
        raise ValueError("runs must be a positive integer")
    samples = [_exercise_fixed_fixture() for _ in range(runs)]
    median: dict[str, dict[str, float | int]] = {}
    for phase in _PHASES:
        median[phase] = {}
        for metric in ("wallTimeSeconds", "peakTracemallocBytes", "bytesRead", "hashCount"):
            values = [sample[phase][metric] for sample in samples]
            value = statistics.median(values)
            median[phase][metric] = int(value) if all(type(item) is int for item in values) else value
    return {
        "schemaVersion": 1,
        "environment": _benchmark_environment(),
        "runs": samples,
        "median": median,
        "metricScope": {
            "build": "Producer outer Overlay copy/full-SHA only; Task 4 structural reads excluded",
            "verify": "release payload full-SHA only; metadata and component Overlay reads excluded",
        },
    }

class ReleasePerformanceTests(unittest.TestCase):
    def test_fixed_fixture_locks_io_hash_and_repeatability_contracts(self) -> None:
        evidence = _exercise_fixed_fixture()
        self.assertEqual(set(_PHASES), set(evidence))
        for phase in _PHASES:
            with self.subTest(phase=phase):
                for metric in ("wallTimeSeconds", "peakTracemallocBytes", "bytesRead", "hashCount"):
                    self.assertGreater(evidence[phase][metric], 0)

    def test_benchmark_identifies_the_comparison_environment(self) -> None:
        environment = collect_benchmark(1)["environment"]
        temporary = Path(tempfile.gettempdir())
        storage = {"kind": "windows-volume" if os.name == "nt" else "posix-filesystem", "deviceId": str(temporary.stat().st_dev)}
        if os.name == "nt":
            storage["drive"] = temporary.drive.upper()
        self.assertEqual({
            "python": {"implementation": platform.python_implementation(), "version": platform.python_version()},
            "platform": {"os": platform.system(), "architecture": platform.machine()},
            "temporaryStorage": storage,
        }, environment)
        self.assertRegex(environment["python"]["version"], r"^[0-9]+\.[0-9]+\.[0-9]+$")  # type: ignore[index]
        self.assertTrue(all(isinstance(value, str) and value.strip()
                            for group in environment.values() for value in group.values()))

    def test_benchmark_rejects_empty_environment_identity(self) -> None:
        for probe in ("python_implementation", "python_version", "system", "machine"):
            with self.subTest(probe=probe), patch.object(platform, probe, return_value=""), \
                    self.assertRaisesRegex(ValueError, r"benchmark environment field is empty"):
                _benchmark_environment()
        with patch.object(Path, "stat", return_value=SimpleNamespace(st_dev="")), \
                self.assertRaisesRegex(ValueError, r"benchmark environment field is empty"):
            _benchmark_environment()

def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 wf-release-v1 同机性能基线 JSON")
    parser.add_argument("--benchmark", action="store_true", required=True)
    parser.add_argument("--runs", type=int, default=5)
    arguments = parser.parse_args(argv)
    sys.stdout.buffer.write(canonical_json_bytes(collect_benchmark(arguments.runs)))
    return 0

if __name__ == "__main__":
    raise SystemExit(_main())
