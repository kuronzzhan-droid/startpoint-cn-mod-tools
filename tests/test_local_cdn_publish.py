# -*- coding: utf-8 -*-
"""Temporary-root tests for stopped-server multi-root local CDN publication."""
from __future__ import annotations

import errno
import hashlib
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from release_inventory_support import InventoryCase

import wf_local_cdn_publish as publisher
import wf_local_scoped_release as adapter
import wf_scoped_release as scoped


class LocalCdnPublishTest(InventoryCase):
    def setUp(self) -> None:
        super().setUp()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cdn = self.root / ".cdn" / "cn"
        self.directories = {
            root: self.cdn / f"archive-{root}-diff"
            for root in ("common", "medium", "android")
        }
        for directory in self.directories.values():
            directory.mkdir(parents=True)
        self.edge = self.plan()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def plan(self) -> scoped.EdgePlan:
        raw_by_key = {
            (root, f"fixture/{root}.bin"): f"payload-{root}".encode()
            for root in ("common", "medium", "android")
        }
        members = [
            {
                "owner": f"owner-{root}",
                "kind": "file",
                "root": root,
                "logical_path": logical,
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            for (root, logical), raw in raw_by_key.items()
        ]
        contract = self.parse(self.payload(members))
        return scoped.build_edge_plan(
            contract,
            {key: None for key in raw_by_key},
            lambda member: raw_by_key[member.key],
            adapter.COMPATIBILITY_SPEC,
        )

    def publish(self, **kwargs):
        kwargs.setdefault("server_probe", lambda: False)
        with mock.patch.object(
            publisher,
            "COMPATIBILITY_EDGE_DIGEST",
            publisher._edge_digest(self.edge),
        ):
            return publisher.publish_local_311_edge(
                self.edge,
                self.cdn,
                confirmation=publisher.CONFIRMATION,
                **kwargs,
            )

    def test_fixture_edge_is_rejected_without_the_frozen_real_digest(self):
        with self.assertRaisesRegex(
            publisher.LocalCdnPublishError, "digest"
        ):
            publisher.publish_local_311_edge(
                self.edge,
                self.cdn,
                confirmation=publisher.CONFIRMATION,
                server_probe=lambda: False,
            )
        self.assertEqual([], list(self.cdn.rglob("*.zip")))
        self.assertFalse((self.cdn / publisher.LOCK_NAME).exists())

    def test_global_sequences_are_not_renumbered_and_parts_use_declared_roots(self):
        result = self.publish()
        self.assertEqual([1, 2, 3], [part.sequence for part in self.edge.parts])
        self.assertEqual(
            [part.name for part in self.edge.parts],
            [path.name for path in result.paths],
        )
        for part, path in zip(self.edge.parts, result.paths, strict=True):
            self.assertEqual(self.directories[part.root], path.parent)
            self.assertEqual(part.blob, path.read_bytes())
        self.assertFalse((self.cdn / publisher.LOCK_NAME).exists())
        self.assertEqual([], list(self.cdn.rglob("*.pending")))

    def test_stopped_probe_runs_under_lock_before_write_and_before_commit(self):
        calls = 0

        def stopped() -> bool:
            nonlocal calls
            calls += 1
            self.assertTrue((self.cdn / publisher.LOCK_NAME).is_file())
            self.assertEqual(
                calls > 1,
                bool(list(self.cdn.rglob("*.zip"))),
            )
            return False

        self.publish(server_probe=stopped)
        self.assertEqual(2, calls)

    def test_server_start_before_commit_rolls_back_archives(self):
        results = iter((False, True))
        with self.assertRaisesRegex(
            publisher.LocalCdnPublishError, "stopped"
        ):
            self.publish(server_probe=lambda: next(results))
        self.assertEqual([], list(self.cdn.rglob("*.zip")))
        self.assertEqual([], list(self.cdn.rglob("*.pending")))
        self.assertFalse((self.cdn / publisher.LOCK_NAME).exists())

    def test_existing_lock_is_refused_before_the_stopped_probe(self):
        lock = self.cdn / publisher.LOCK_NAME
        lock.write_bytes(b"foreign")
        probed = False

        def stopped() -> bool:
            nonlocal probed
            probed = True
            return False

        with self.assertRaises(publisher.LocalCdnPublishError):
            self.publish(server_probe=stopped)
        self.assertFalse(probed)
        self.assertEqual(b"foreign", lock.read_bytes())

    def test_default_probe_accepts_refusal_or_an_empty_listener_table(self):
        refused = ConnectionRefusedError(errno.ECONNREFUSED, "refused")
        with mock.patch.object(
            publisher.server_status.socket,
            "create_connection",
            side_effect=refused,
        ) as connect, mock.patch.object(
            publisher.server_status, "listening_ports"
        ) as ports:
            published = self.publish(server_probe=None)
        self.assertEqual(2, connect.call_count)
        ports.assert_not_called()
        for path in published.paths:
            path.unlink()

        # A dropped SYN is not evidence either way, so the local listener table
        # settles it.  Nothing listening on the configured port means stopped.
        timeout_edge = self.plan()
        with mock.patch.object(
            publisher,
            "COMPATIBILITY_EDGE_DIGEST",
            publisher._edge_digest(timeout_edge),
        ), mock.patch.object(
            publisher.server_status.socket,
            "create_connection",
            side_effect=socket.timeout("timed out"),
        ), mock.patch.object(
            publisher.server_status, "listening_ports", return_value={22, 443}
        ):
            published = publisher.publish_local_311_edge(
                timeout_edge, self.cdn, confirmation=publisher.CONFIRMATION,
            )
        for path in published.paths:
            path.unlink()
        self.assertFalse((self.cdn / publisher.LOCK_NAME).exists())

    def test_default_probe_refuses_a_listening_port_or_an_unreadable_table(self):
        for label, table in (
            ("listening", {"return_value": {8001}}),
            (
                "unreadable",
                {"side_effect": publisher.server_status.ServerStatusError("no table")},
            ),
        ):
            with self.subTest(table=label):
                edge = self.plan()
                with mock.patch.object(
                    publisher,
                    "COMPATIBILITY_EDGE_DIGEST",
                    publisher._edge_digest(edge),
                ), mock.patch.object(
                    publisher.server_status.socket,
                    "create_connection",
                    side_effect=socket.timeout("timed out"),
                ), mock.patch.object(
                    publisher.server_status, "listening_ports", **table
                ):
                    with self.assertRaisesRegex(
                        publisher.LocalCdnPublishError,
                        "stopped|verify|probe|table",
                    ):
                        publisher.publish_local_311_edge(
                            edge, self.cdn, confirmation=publisher.CONFIRMATION,
                        )
                self.assertFalse((self.cdn / publisher.LOCK_NAME).exists())
                for directory in self.directories.values():
                    self.assertEqual([], list(directory.iterdir()))

    def test_identical_retry_is_success_but_partial_or_mismatch_is_refused(self):
        first = self.publish()
        second = self.publish(
            server_probe=lambda: (_ for _ in ()).throw(
                AssertionError("idempotent retry must not require a stopped server")
            )
        )
        self.assertEqual(first, second)

        first.paths[0].write_bytes(b"mismatch")
        with self.assertRaisesRegex(
            publisher.LocalCdnPublishError, "mismatch|partial|canonical"
        ):
            self.publish()
        self.assertEqual(b"mismatch", first.paths[0].read_bytes())
        self.assertFalse((self.cdn / publisher.LOCK_NAME).exists())

    def test_partial_existing_edge_is_refused_without_overwrite(self):
        part = self.edge.parts[0]
        target = self.directories[part.root] / part.name
        target.write_bytes(part.blob)
        with self.assertRaisesRegex(
            publisher.LocalCdnPublishError, "partial|mismatch"
        ):
            self.publish()
        self.assertEqual(part.blob, target.read_bytes())
        self.assertEqual([target], list(self.cdn.rglob("*.zip")))
        self.assertFalse((self.cdn / publisher.LOCK_NAME).exists())

    def test_failure_after_first_visible_archive_rolls_back_every_root(self):
        count = 0

        def fail(phase: str) -> None:
            nonlocal count
            if phase == "after_archive":
                count += 1
                if count == 1:
                    raise RuntimeError("injected multi-root failure")

        with self.assertRaisesRegex(
            publisher.LocalCdnPublishError, "injected multi-root"
        ):
            self.publish(checkpoint=fail)
        self.assertEqual([], list(self.cdn.rglob("*.zip")))
        self.assertEqual([], list(self.cdn.rglob("*.pending")))
        self.assertFalse((self.cdn / publisher.LOCK_NAME).exists())

    def test_same_edge_name_in_the_wrong_root_is_a_hard_collision(self):
        foreign = self.directories["medium"] / self.edge.parts[0].name
        foreign.write_bytes(b"foreign")
        with self.assertRaisesRegex(
            publisher.LocalCdnPublishError,
            "already exists|collision|partial|wrong root",
        ):
            self.publish()
        self.assertEqual(b"foreign", foreign.read_bytes())
        self.assertEqual([foreign], list(self.cdn.rglob("*.zip")))
        self.assertFalse((self.cdn / publisher.LOCK_NAME).exists())

    def test_foreign_replacement_before_commit_is_left_with_recovery_lock(self):
        foreign = b"foreign replacement"

        def replace(phase: str) -> None:
            if phase == "before_commit":
                target = self.directories["common"] / self.edge.parts[0].name
                target.unlink()
                target.write_bytes(foreign)

        with self.assertRaisesRegex(
            publisher.LocalCdnPublishError, "identity|rollback|lock"
        ):
            self.publish(checkpoint=replace)
        target = self.directories["common"] / self.edge.parts[0].name
        self.assertEqual(foreign, target.read_bytes())
        self.assertTrue((self.cdn / publisher.LOCK_NAME).is_file())
        target.unlink()
        (self.cdn / publisher.LOCK_NAME).unlink()

    @unittest.skipUnless(sys.platform == "win32", "Windows handle cleanup contract")
    def test_foreign_lock_replacement_before_handle_open_is_retained(self):
        lock = self.cdn / publisher.LOCK_NAME
        foreign = b"foreign lock replacement"
        api = publisher.transaction._windows_owned_api()
        real_reopen = api.reopen_output_cleanup
        injected = False

        def replace_then_reopen(parent: int, name: str):
            nonlocal injected
            if name == publisher.LOCK_NAME and not injected:
                injected = True
                lock.unlink()
                lock.write_bytes(foreign)
            return real_reopen(parent, name)

        with mock.patch.object(
            api,
            "reopen_output_cleanup",
            side_effect=replace_then_reopen,
        ):
            with self.assertRaisesRegex(
                publisher.LocalCdnPublishError, "lock|identity"
            ):
                self.publish()

        self.assertTrue(injected)
        self.assertEqual(foreign, lock.read_bytes())
        for part in self.edge.parts:
            target = self.directories[part.root] / part.name
            self.assertEqual(part.blob, target.read_bytes())
        self.assertEqual([], list(self.cdn.rglob("*.wf-quarantine-*")))
        lock.unlink()

    def test_confirmation_and_stopped_server_are_mandatory(self):
        with self.assertRaisesRegex(publisher.LocalCdnPublishError, "requires"):
            publisher.publish_local_311_edge(
                self.edge,
                self.cdn,
                confirmation="NO",
                server_probe=lambda: False,
            )
        with self.assertRaisesRegex(publisher.LocalCdnPublishError, "stopped"):
            self.publish(server_probe=lambda: True)
        self.assertEqual([], list(self.cdn.rglob("*.zip")))


if __name__ == "__main__":
    unittest.main()
