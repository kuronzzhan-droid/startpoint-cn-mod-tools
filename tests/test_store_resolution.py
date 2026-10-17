# -*- coding: utf-8 -*-
"""store 解析链回归:WF_TARGET_STORE > profiles.json 激活档案 > 自动探测 > 历史兜底。

背景(2026-08-02 群反馈「工具里那一行弹国服太变态了」):
wf_quest_lib._store_base() 曾对 load_profiles() 返回的 dict 取 .active_store 属性,
必抛 AttributeError → 永远落到作者本机的 `弹国服/...`,WF_TARGET_STORE 与
profiles.json 一律失效,外部用户的 Boss/连战塔/商店/平衡套件全部不可用。
wf_publish 侧则只读 profiles.json,"纯环境变量"用法必报「未找到数据包 store」。

本套件全程用临时目录 + 环境变量隔离,不依赖任何真实 store。
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wf_mod_tool as core  # noqa: E402
import wf_publish  # noqa: E402
import wf_quest_lib as quest  # noqa: E402

ZONE = "master/battle/zone.orderedmap"


class EnvIsolatedCase(unittest.TestCase):
    """清掉 WF_TARGET_STORE / WF_PROFILE,给每个用例一棵干净的临时根目录。"""

    def setUp(self):
        env_patch = mock.patch.dict(os.environ)
        env_patch.start()
        self.addCleanup(env_patch.stop)
        os.environ.pop("WF_TARGET_STORE", None)
        os.environ.pop("WF_PROFILE", None)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def make_dir(self, *parts: str) -> Path:
        path = self.root.joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def no_profile(self):
        return mock.patch.object(core, "resolve_profile", return_value=None)

    def rooted(self):
        return mock.patch.object(quest, "ROOT", self.root)


class QuestLibStoreBaseTests(EnvIsolatedCase):
    def test_env_target_store_wins_over_legacy_layout(self):
        store = self.make_dir("env-store")
        self.make_dir(*quest.LEGACY_STORE_REL.split("/"))  # 诱饵:历史路径就在眼前
        os.environ["WF_TARGET_STORE"] = str(store)
        with self.rooted():
            self.assertEqual(quest._store_base(), store)

    def test_profile_store_used_when_env_absent(self):
        store = self.make_dir("profile-store")
        self.make_dir(*quest.LEGACY_STORE_REL.split("/"))
        profile = core.VersionProfile(id="cn", label="CN", store=store)
        with mock.patch.object(core, "resolve_profile", return_value=profile), self.rooted():
            self.assertEqual(quest._store_base(), store)

    def test_auto_detection_finds_data_pack_without_any_config(self):
        upload = self.make_dir(
            "data-pack", "WorldFlipper", "dummy", "download", "production", "upload"
        )
        with self.no_profile(), self.rooted():
            self.assertEqual(quest._store_base(), upload)

    def test_legacy_layout_still_resolves_for_the_author_machine(self):
        legacy = self.make_dir(*quest.LEGACY_STORE_REL.split("/"))
        with self.no_profile(), self.rooted():
            self.assertEqual(quest._store_base(), legacy)

    def test_nothing_configured_raises_actionable_error(self):
        with self.no_profile(), self.rooted(), mock.patch.object(
            core, "find_world_upload", return_value=None
        ):
            with self.assertRaises(FileNotFoundError) as ctx:
                quest._store_base()
        message = str(ctx.exception)
        self.assertIn("WF_TARGET_STORE", message)
        self.assertIn("profiles.json", message)
        self.assertNotIn("弹国服", message)

    def test_env_pointing_at_missing_dir_is_a_hard_error(self):
        os.environ["WF_TARGET_STORE"] = str(self.root / "not-there")
        with self.rooted():
            with self.assertRaises(ValueError) as ctx:
                quest._store_base()
        message = str(ctx.exception)
        self.assertIn("WF_TARGET_STORE", message)
        self.assertIn("profiles.json", message)

    def test_store_path_follows_the_resolved_base(self):
        store = self.make_dir("env-store")
        os.environ["WF_TARGET_STORE"] = str(store)
        with self.rooted():
            self.assertEqual(quest.store_path(ZONE), store / quest.hashed_rel(ZONE))


class QuestLibTableIoTests(EnvIsolatedCase):
    def test_round_trip_writes_into_the_env_store(self):
        store = self.make_dir("env-store")
        os.environ["WF_TARGET_STORE"] = str(store)
        tree = {"1": "1,2,3", "2": ""}
        with self.rooted():
            written = quest.save_table(ZONE, tree, backup=False)
            self.assertEqual(written, store / quest.hashed_rel(ZONE))
            self.assertEqual(quest.load_table(ZONE), tree)
        self.assertFalse((self.root / "弹国服").exists())

    def test_save_table_refuses_to_conjure_a_store_tree(self):
        missing = self.root / "missing-store"
        with mock.patch.object(quest, "_store_base", return_value=missing):
            with self.assertRaises(FileNotFoundError) as ctx:
                quest.save_table(ZONE, {"1": "row"})
        self.assertFalse(missing.exists())
        self.assertIn("WF_TARGET_STORE", str(ctx.exception))

    def test_load_table_reports_a_missing_store_root_actionably(self):
        missing = self.root / "missing-store"
        with mock.patch.object(quest, "_store_base", return_value=missing):
            with self.assertRaises(FileNotFoundError) as ctx:
                quest.load_table(ZONE)
        self.assertIn("profiles.json", str(ctx.exception))

    def test_explicit_path_bypasses_store_resolution(self):
        target = self.root / "loose" / "table.orderedmap"
        target.parent.mkdir(parents=True)
        with mock.patch.object(quest, "_store_base", side_effect=AssertionError("resolved")):
            quest.save_table(ZONE, {"1": "x"}, path=target, backup=False)
            self.assertEqual(quest.load_table(ZONE, path=target), {"1": "x"})


class CoreResolveTargetStoreTests(EnvIsolatedCase):
    def test_supplied_profile_is_not_re_resolved(self):
        store = self.make_dir("profile-store")
        profile = core.VersionProfile(id="cn", label="CN", store=store)
        with mock.patch.object(core, "resolve_profile") as resolve_profile:
            self.assertEqual(
                core.resolve_active_store(self.root, profile=profile), store
            )
            resolve_profile.assert_not_called()

    def test_supplied_none_profile_skips_lookup_and_falls_through(self):
        upload = self.make_dir(
            "pack", "WorldFlipper", "dummy", "download", "production", "upload"
        )
        with mock.patch.object(core, "resolve_profile") as resolve_profile:
            self.assertEqual(core.resolve_active_store(self.root, profile=None), upload)
            resolve_profile.assert_not_called()

    def test_returns_none_when_the_chain_is_exhausted(self):
        with self.no_profile(), mock.patch.object(
            core, "find_world_upload", return_value=None
        ):
            self.assertIsNone(core.resolve_active_store(self.root))


class PublishStoreResolutionTests(EnvIsolatedCase):
    """wf_publish 侧:纯环境变量(无 profiles.json)也要能定位 store。"""

    def _run_list(self, tables: str = "ability"):
        cdn = self.root / "cdn"
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(wf_publish, "CDN_ROOT", cdn), mock.patch.object(
            wf_publish, "CDN_DIFF", cdn / "archive-common-diff"
        ), mock.patch.object(wf_publish, "WORK", self.root / "work"), mock.patch.object(
            wf_publish, "PENDING", self.root / "work" / "sync_pending.json"
        ), mock.patch.object(
            wf_publish, "current_max_version", return_value="1.4.54"
        ), redirect_stdout(out), redirect_stderr(err):
            code = wf_publish.main(["--tables", tables, "--list"])
        return code, out.getvalue(), err.getvalue()

    def test_env_target_store_alone_resolves_the_store(self):
        store = self.make_dir("env-store")
        relative = wf_publish._relative_for_logical(core.ABILITY_LOGICAL)
        target = store / relative
        target.parent.mkdir(parents=True)
        target.write_bytes(b"payload")
        os.environ["WF_TARGET_STORE"] = str(store)

        with self.no_profile():
            code, out, err = self._run_list()

        self.assertEqual(code, 0, err)
        self.assertNotIn("未找到数据包 store", out + err)
        self.assertIn(str(store.resolve()), out)

    def test_no_store_anywhere_reports_how_to_configure_one(self):
        with self.no_profile(), mock.patch.object(
            core, "default_target_store", return_value=None
        ), mock.patch.object(core, "find_world_upload", return_value=None):
            code, out, err = self._run_list()

        self.assertEqual(code, 1)
        self.assertIn("未找到数据包 store", err)
        self.assertIn("WF_TARGET_STORE", err)
        self.assertIn("profiles.json", err)


if __name__ == "__main__":
    unittest.main()
