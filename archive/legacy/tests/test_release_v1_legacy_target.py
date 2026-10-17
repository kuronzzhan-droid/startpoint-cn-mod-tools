"""Strict read-only facts for legacy CDN targets."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from typing import Callable

from wf_release_v1._platform_state import ManagedProcess
from wf_release_v1.errors import ReleaseError
from wf_release_v1.legacy_target import (
    LegacyProcessStatus,
    inspect_legacy_target,
)
from wf_release_v1.target import ComponentRoots, ManagedTarget, TargetCompatibility


SHA = "a" * 64
OPERATION_ID = "20260813T010203.000000Z-0123456789abcdef0123456789abcdef"
LAYERS = ("common", "medium", "android")


@dataclass
class FakePlatform:
    current: ManagedProcess | None
    calls: int = 0

    def current_process(self) -> ManagedProcess | None:
        self.calls += 1
        return self.current


class FailingPlatform:
    def current_process(self) -> ManagedProcess | None:
        raise ReleaseError("WFREL_PROCESS_IDENTITY", "identity changed")


def _archive_name(
    start: str,
    end: str,
    *,
    sequence: int = 1,
    tag: str = "fixture",
) -> str:
    return f"pinball-{start}-{end}-{sequence}-{tag}.zip"


def _write_archive(path: Path, payload: bytes = b"") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as bundle:
        bundle.writestr(".empty", payload)


class LegacyTargetFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        roots = {name: root / name for name in (
            "server", "runtime", "data", "state", "cdn", "modes",
            "candidate-content", "candidate-server", "candidate-modes",
        )}
        for path in roots.values():
            path.mkdir()
        self.target = ManagedTarget(
            server_bundle=roots["server"],
            runtime_pack=roots["runtime"],
            data_root=roots["data"],
            state_root=roots["state"],
            cdn_root=roots["cdn"],
            modes_root=roots["modes"],
            component_roots=ComponentRoots(
                roots["candidate-content"],
                roots["candidate-server"],
                roots["candidate-modes"],
            ),
            compatibility=TargetCompatibility("1.8.1", "1.4.54", False),
            server_url="http://127.0.0.1:8001",
        )
        self.cn = roots["cdn"] / "cn"
        for layer in LAYERS:
            (self.cn / f"archive-{layer}-diff").mkdir(parents=True)

    def add_edge(
        self,
        start: str,
        end: str,
        *,
        sequence: int = 1,
        tag: str = "fixture",
        layers: tuple[str, ...] = LAYERS,
    ) -> None:
        name = _archive_name(start, end, sequence=sequence, tag=tag)
        for layer in layers:
            _write_archive(self.cn / f"archive-{layer}-diff" / name)


def _tree_digest(root: Path) -> tuple[tuple[str, str], ...]:
    return tuple(
        (path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )


class LegacyTargetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="wf-release-v1-legacy-target-")
        self.addCleanup(self.temp.cleanup)
        self.fixture = LegacyTargetFixture(Path(self.temp.name).resolve())

    def test_returns_one_frozen_three_layer_chain_without_writing(self) -> None:
        self.fixture.add_edge("1.4.54", "1.4.55", tag="first")
        self.fixture.add_edge("1.4.55", "1.4.57", tag="second")
        process = ManagedProcess(100, 200, SHA, OPERATION_ID)
        platform = FakePlatform(process)
        before = _tree_digest(self.fixture.root)

        facts = inspect_legacy_target(self.fixture.target, platform)

        self.assertEqual("1.4.57", facts.chain_tail)
        self.assertEqual(self.fixture.target.compatibility, facts.compatibility)
        self.assertIs(LegacyProcessStatus.OWNED_RUNNING, facts.process_status)
        self.assertEqual((), facts.preview_only_reasons)
        self.assertEqual(1, platform.calls)
        self.assertEqual(LAYERS, tuple(item.layer for item in facts.layers))
        for layer in facts.layers:
            self.assertEqual(2, len(layer.archives))
            self.assertEqual(
                (("1.4.54", "1.4.55"), ("1.4.55", "1.4.57")),
                tuple((item.from_version, item.target_version) for item in layer.archives),
            )
            self.assertRegex(layer.sha256, r"^[0-9a-f]{64}$")
            for archive in layer.archives:
                self.assertGreater(archive.size, 0)
                self.assertRegex(archive.sha256, r"^[0-9a-f]{64}$")
        self.assertEqual(before, _tree_digest(self.fixture.root))
        with self.assertRaises(FrozenInstanceError):
            facts.layers[0].archives += ()  # type: ignore[misc]

    def test_empty_canonical_layers_use_the_declared_resource_baseline(self) -> None:
        facts = inspect_legacy_target(self.fixture.target, FakePlatform(None))
        self.assertEqual("1.4.54", facts.chain_tail)
        self.assertIs(LegacyProcessStatus.NOT_OWNED, facts.process_status)
        self.assertEqual(("WFREL_LEGACY_PROCESS_NOT_OWNED",), facts.preview_only_reasons)
        self.assertTrue(all(layer.archives == () for layer in facts.layers))

    def test_layer_specific_content_tags_still_describe_one_version_edge(self) -> None:
        for layer, tag in zip(LAYERS, ("common-a1", "medium-b2", "android-c3"), strict=True):
            _write_archive(
                self.fixture.cn
                / f"archive-{layer}-diff"
                / _archive_name("1.4.54", "1.4.55", tag=tag)
            )
        facts = inspect_legacy_target(self.fixture.target, FakePlatform(None))
        self.assertEqual("1.4.55", facts.chain_tail)
        self.assertEqual(
            ("common-a1", "medium-b2", "android-c3"),
            tuple(layer.archives[0].tag for layer in facts.layers),
        )

    def test_rejects_missing_misaligned_or_extra_layer_entries(self) -> None:
        cases: list[tuple[str, Callable[[LegacyTargetFixture], object]]] = [
            (
                "missing layer directory",
                lambda fx: (fx.cn / "archive-android-diff").rmdir(),
            ),
            (
                "edge missing from one layer",
                lambda fx: fx.add_edge("1.4.54", "1.4.55", layers=("common", "medium")),
            ),
            (
                "extra file",
                lambda fx: (fx.cn / "archive-common-diff" / "notes.txt").write_text("x"),
            ),
            (
                "extra directory",
                lambda fx: (fx.cn / "archive-common-diff" / "nested").mkdir(),
            ),
        ]
        for label, mutate in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory(
                prefix="wf-release-v1-legacy-target-case-"
            ) as directory:
                fixture = LegacyTargetFixture(Path(directory).resolve())
                mutate(fixture)
                with self.assertRaises(ReleaseError) as raised:
                    inspect_legacy_target(fixture.target, FakePlatform(None))
                self.assertEqual("WFREL_LEGACY_TARGET_INVALID", raised.exception.code)

    def test_rejects_forks_gaps_decreasing_edges_and_noncanonical_names(self) -> None:
        cases = (
            (
                "fork",
                (("1.4.54", "1.4.55", 1, "a"), ("1.4.54", "1.4.56", 1, "b")),
            ),
            (
                "gap",
                (("1.4.54", "1.4.55", 1, "a"), ("1.4.56", "1.4.57", 1, "b")),
            ),
            ("decrease", (("1.4.55", "1.4.54", 1, "a"),)),
            ("leading sequence zero", (("1.4.54", "1.4.55", 1, "a"),)),
        )
        for label, edges in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory(
                prefix="wf-release-v1-legacy-target-graph-"
            ) as directory:
                fixture = LegacyTargetFixture(Path(directory).resolve())
                for start, end, sequence, tag in edges:
                    fixture.add_edge(start, end, sequence=sequence, tag=tag)
                if label == "leading sequence zero":
                    for layer in LAYERS:
                        source = fixture.cn / f"archive-{layer}-diff" / _archive_name(
                            "1.4.54", "1.4.55", tag="a"
                        )
                        source.rename(source.with_name(source.name.replace("-1-a.zip", "-01-a.zip")))
                with self.assertRaises(ReleaseError) as raised:
                    inspect_legacy_target(fixture.target, FakePlatform(None))
                self.assertEqual("WFREL_LEGACY_TARGET_INVALID", raised.exception.code)

    def test_rejects_bad_zip_and_hardlinked_archives(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wf-release-v1-legacy-target-zip-") as directory:
            fixture = LegacyTargetFixture(Path(directory).resolve())
            fixture.add_edge("1.4.54", "1.4.55", tag="valid")
            common = fixture.cn / "archive-common-diff"
            (common / _archive_name("1.4.55", "1.4.56", tag="bad")).write_bytes(b"not a zip")
            with self.assertRaises(ReleaseError) as raised:
                inspect_legacy_target(fixture.target, FakePlatform(None))
            self.assertEqual("WFREL_LEGACY_TARGET_INVALID", raised.exception.code)

        with tempfile.TemporaryDirectory(prefix="wf-release-v1-legacy-target-hardlink-") as directory:
            fixture = LegacyTargetFixture(Path(directory).resolve())
            fixture.add_edge("1.4.54", "1.4.55", tag="case")
            source = fixture.cn / "archive-common-diff" / _archive_name(
                "1.4.54", "1.4.55", tag="case"
            )
            linked = fixture.cn / "archive-medium-diff" / source.name
            linked.unlink()
            os.link(source, linked)
            with self.assertRaises(ReleaseError) as raised:
                inspect_legacy_target(fixture.target, FakePlatform(None))
            self.assertEqual("WFREL_LEGACY_TARGET_INVALID", raised.exception.code)

    def test_process_identity_errors_never_downgrade_to_preview(self) -> None:
        with self.assertRaises(ReleaseError) as raised:
            inspect_legacy_target(self.fixture.target, FailingPlatform())
        self.assertEqual("WFREL_PROCESS_IDENTITY", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
