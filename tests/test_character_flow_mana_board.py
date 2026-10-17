# -*- coding: utf-8 -*-
"""flow 层：把包内玛纳板派生成 assets/mana_board.json 的键级回灌（临时目录）。

老包（119 份已发布 manifest）server 根里只有四项，永远不会带 mana_board.json；
本回灌从包自带的客户端表 `master/generated/mana_board.orderedmap` 派生该角色行，
键级并进服务端镜像。带了 mana_board.json 的新包由发布事务自己写，这里必须让路。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wf_character_flow as flow  # noqa: E402
import wf_character_workspace as workspace_module  # noqa: E402
from test_character_pack_mana_board import _SAMPLE_TREE, _client_mana_board  # noqa: E402

CHARACTER_ID = 149995
CLIENT_LOGICAL = "master/generated/mana_board.orderedmap"


def _write_client_table(package_dir: Path) -> None:
    path = package_dir / "roots" / "common" / Path(*CLIENT_LOGICAL.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_client_mana_board(_SAMPLE_TREE))


def _write_manifest(package_dir: Path, *, server_paths: list[str]) -> None:
    manifest = {
        "schema_version": 1,
        "package_id": "seofon_wind",
        "character_id": CHARACTER_ID,
        "code_name": "seofon_wind",
        "roots": {
            "common": [{"logical_path": CLIENT_LOGICAL}],
            "medium": [],
            "android": [],
            "server": [{"logical_path": item} for item in server_paths],
        },
        "tables": [],
    }
    (package_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


class SyncServerManaBoardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="flow-mana-board-"))
        self.addCleanup(
            lambda: __import__("shutil").rmtree(self.temp, ignore_errors=True)
        )
        self.package_dir = self.temp / "package"
        (self.package_dir / "roots" / "common").mkdir(parents=True)
        (self.package_dir / "roots" / "server").mkdir(parents=True)
        self.server_root = self.temp / "assets"
        self.server_root.mkdir()
        self.mirror = self.server_root / "mana_board.json"
        self.mirror.write_bytes(b'{"10":{"1":{"1":[["20201","0","0","q","0","(None)"]]}}}')
        _write_client_table(self.package_dir)
        _write_manifest(self.package_dir, server_paths=["character.json"])

    def _sync(self, **kwargs):
        return flow.sync_server_mana_board(
            self.package_dir, self.server_root, **kwargs
        )

    def test_dry_run_reports_the_addition_without_touching_the_mirror(self) -> None:
        before = self.mirror.read_bytes()
        report = self._sync()
        self.assertEqual(report["status"], "backfilled")
        self.assertEqual(report["added"], [str(CHARACTER_ID)])
        self.assertFalse(report["written"])
        self.assertEqual(self.mirror.read_bytes(), before)

    def test_apply_appends_the_key_without_disturbing_existing_keys(self) -> None:
        report = self._sync(apply=True)
        self.assertEqual(report["status"], "backfilled")
        self.assertTrue(report["written"])
        raw = self.mirror.read_bytes()
        self.assertFalse(raw.endswith(b"\n"))
        self.assertNotIn(b", ", raw)
        payload = json.loads(raw.decode("utf-8"))
        self.assertEqual(list(payload), ["10", str(CHARACTER_ID)])
        self.assertEqual(
            payload["10"], {"1": {"1": [["20201", "0", "0", "q", "0", "(None)"]]}}
        )
        self.assertEqual(payload[str(CHARACTER_ID)], _SAMPLE_TREE[str(CHARACTER_ID)])

    def test_second_apply_is_a_no_op(self) -> None:
        self._sync(apply=True)
        stable = self.mirror.read_bytes()
        report = self._sync(apply=True)
        self.assertEqual(report["status"], "up_to_date")
        self.assertFalse(report["written"])
        self.assertEqual(self.mirror.read_bytes(), stable)

    def test_missing_mirror_file_is_created(self) -> None:
        self.mirror.unlink()
        report = self._sync(apply=True)
        self.assertEqual(report["status"], "backfilled")
        self.assertEqual(
            json.loads(self.mirror.read_text(encoding="utf-8")),
            {str(CHARACTER_ID): _SAMPLE_TREE[str(CHARACTER_ID)]},
        )

    def test_package_that_declares_mana_board_is_left_to_the_transaction(self) -> None:
        _write_manifest(
            self.package_dir, server_paths=["character.json", "mana_board.json"],
        )
        before = self.mirror.read_bytes()
        report = self._sync(apply=True)
        self.assertEqual(report["status"], "package_owned")
        self.assertFalse(report["written"])
        self.assertEqual(self.mirror.read_bytes(), before)

    def test_package_without_the_client_table_is_skipped(self) -> None:
        (
            self.package_dir / "roots" / "common"
            / Path(*CLIENT_LOGICAL.split("/"))
        ).unlink()
        report = self._sync(apply=True)
        self.assertEqual(report["status"], "no_client_table")
        self.assertFalse(report["written"])

    def test_character_missing_from_the_client_table_fails_closed(self) -> None:
        _write_manifest(self.package_dir, server_paths=["character.json"])
        manifest_path = self.package_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["character_id"] = 129999
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        with self.assertRaises(flow.character_pack.PackPreflightError):
            self._sync(apply=True)


class ManaBoardCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="flow-mana-board-cli-"))
        self.addCleanup(
            lambda: __import__("shutil").rmtree(self.temp, ignore_errors=True)
        )
        self.workspace = workspace_module.init_workspace(
            self.temp / "ws", 111165, CHARACTER_ID, "seofon_wind", "seofon_wind",
        )
        _write_client_table(self.workspace.package_dir)
        _write_manifest(self.workspace.package_dir, server_paths=["character.json"])
        self.server_root = self.temp / "assets"
        self.server_root.mkdir()
        self.mirror = self.server_root / "mana_board.json"
        self.mirror.write_bytes(b"{}")

    def test_dry_run_is_the_default(self) -> None:
        code, payload = flow.run_command([
            "mana-board", "--workspace", str(self.workspace.root),
            "--server-root", str(self.server_root),
        ])
        self.assertEqual(code, 0)
        self.assertEqual(payload["stage"], "mana-board")
        self.assertEqual(payload["mana_board"]["status"], "backfilled")
        self.assertFalse(payload["mana_board"]["written"])
        self.assertEqual(self.mirror.read_bytes(), b"{}")

    def test_apply_writes_the_mirror(self) -> None:
        code, payload = flow.run_command([
            "mana-board", "--workspace", str(self.workspace.root),
            "--server-root", str(self.server_root), "--apply",
        ])
        self.assertEqual(code, 0)
        self.assertTrue(payload["mana_board"]["written"])
        self.assertEqual(
            json.loads(self.mirror.read_text(encoding="utf-8")),
            {str(CHARACTER_ID): _SAMPLE_TREE[str(CHARACTER_ID)]},
        )


class PublishHookTest(unittest.TestCase):
    """发布后钩子：可注入，失败只 [WARN] 不改发布返回码。"""

    class _FakeRelease:
        def publish_package(self, package_dir, profile_id, confirmation,
                            installed_package_dir=None):
            return SimpleNamespace(
                committed=True,
                release_id="release-1",
                from_version="1.4.139",
                version="1.4.140",
                active_manifest_sha256="a" * 64,
                archive_paths=(Path("common.zip"),),
                snapshot_dir=Path("snapshot-1"),
            )

    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="flow-mana-board-publish-"))
        self.addCleanup(
            lambda: __import__("shutil").rmtree(self.temp, ignore_errors=True)
        )
        self.workspace = workspace_module.init_workspace(
            self.temp / "ws", 111165, CHARACTER_ID, "seofon_wind", "seofon_wind",
        )
        _write_client_table(self.workspace.package_dir)

    def _publish(self, hook):
        from unittest.mock import patch
        status = SimpleNamespace(release_ready=True, to_dict=lambda: {})
        with patch.object(
            flow.workspace_module, "workspace_status", return_value=status
        ), patch.object(flow, "_manifest_mode", return_value="runtime_test"):
            return flow.run_command([
                "publish", "--workspace", str(self.workspace.root),
                "--confirm", "DIRECT_REAL_TEST",
            ], release_module=self._FakeRelease(),
                dev_catalog_hook=None, mana_board_hook=hook)

    def test_hook_report_is_carried_into_the_publish_payload(self) -> None:
        calls = []

        def hook(result, package_dir):
            calls.append((result.release_id, Path(package_dir)))
            return {"status": "backfilled", "written": True}

        code, payload = self._publish(hook)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [("release-1", self.workspace.package_dir)])
        self.assertEqual(payload["mana_board"], {"status": "backfilled", "written": True})

    def test_hook_failure_does_not_change_the_publish_exit_code(self) -> None:
        def hook(result, package_dir):
            raise RuntimeError("synthetic backfill failure")

        code, payload = self._publish(hook)
        self.assertEqual(code, 0)
        self.assertIsNone(payload["mana_board"])

    def test_default_hook_skips_when_archives_are_outside_the_live_cdn_root(self) -> None:
        """默认钩子只在归档确实落进真实 CDN 链根时才写仓库 assets/。"""
        result = SimpleNamespace(
            committed=True, archive_paths=(self.temp / "common.zip",),
        )
        self.assertIsNone(
            flow.backfill_server_mana_board_after_publish(
                result, self.workspace.package_dir
            )
        )


if __name__ == "__main__":
    unittest.main()
