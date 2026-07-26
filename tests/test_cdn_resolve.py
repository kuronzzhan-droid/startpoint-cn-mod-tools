# -*- coding: utf-8 -*-
"""CDN 根四级解析链(core.resolve_cdn_root)回归:T2 两仓独立的接入契约。

层级:WF_CDN_DIR env > profile.cdn_dir > 服务端识别(WF_SERVER_DIR/profile.server_dir
→ 复读服务端 .env 的 CDN_DIR,缺省 <server>/.cdn/cn)> 嵌套遗留兜底。
显式配置不合法=硬报错;派生候选不合法=顺延;全部落空=报完整尝试清单。
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wf_mod_tool as core  # noqa: E402


def make_cdn(root: Path) -> Path:
    (root / "archive-common-diff").mkdir(parents=True)
    return root


class _ResolveBase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # 隔离环境:清空相关 env,profile 默认为空
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        for key in ("WF_CDN_DIR", "WF_SERVER_DIR"):
            os.environ.pop(key, None)
        patcher = mock.patch.object(core, "load_profiles", return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)
        # 嵌套遗留兜底指向不存在的位置,避免测试机真实链干扰
        self.fake_project = self.root / "fake-project"
        patcher2 = mock.patch.object(
            core, "project_root", return_value=self.fake_project
        )
        patcher2.start()
        self.addCleanup(patcher2.stop)

    def _use_profile(self, entry: dict) -> None:
        mock.patch.object(
            core, "load_profiles",
            return_value={"active": "cn", "profiles": {"cn": {"store": ".", **entry}}},
        ).start()


class ResolveCdnRootTest(_ResolveBase):
    def test_env_wins(self) -> None:
        cdn = make_cdn(self.root / "somewhere" / "cn")
        os.environ["WF_CDN_DIR"] = str(cdn)
        self.assertEqual(cdn, core.resolve_cdn_root())

    def test_env_invalid_is_hard_error(self) -> None:
        os.environ["WF_CDN_DIR"] = str(self.root / "not-a-cdn")
        with self.assertRaises(ValueError) as ctx:
            core.resolve_cdn_root()
        self.assertIn("WF_CDN_DIR", str(ctx.exception))

    def test_profile_cdn_dir_used(self) -> None:
        cdn = make_cdn(self.root / "cdn-by-profile" / "cn")
        self._use_profile({"cdn_dir": str(cdn)})
        self.assertEqual(cdn, core.resolve_cdn_root())

    def test_profile_cdn_dir_invalid_is_hard_error(self) -> None:
        self._use_profile({"cdn_dir": str(self.root / "bogus")})
        with self.assertRaises(ValueError) as ctx:
            core.resolve_cdn_root()
        self.assertIn("cdn_dir", str(ctx.exception))

    def test_server_env_cdn_dir_declared(self) -> None:
        server = self.root / "server"
        declared_parent = self.root / "external-cdn"
        make_cdn(declared_parent / "cn")
        server.mkdir()
        (server / ".env").write_text(
            f'# comment\nCDN_DIR="{declared_parent}"\n', encoding="utf-8"
        )
        os.environ["WF_SERVER_DIR"] = str(server)
        self.assertEqual(declared_parent / "cn", core.resolve_cdn_root())

    def test_server_default_dot_cdn(self) -> None:
        server = self.root / "server2"
        make_cdn(server / ".cdn" / "cn")
        os.environ["WF_SERVER_DIR"] = str(server)
        self.assertEqual(server / ".cdn" / "cn", core.resolve_cdn_root())

    def test_server_env_relative_cdn_dir(self) -> None:
        server = self.root / "server3"
        make_cdn(server / "data" / "cdn" / "cn")
        server.mkdir(exist_ok=True)
        (server / ".env").write_text("CDN_DIR=data/cdn\n", encoding="utf-8")
        os.environ["WF_SERVER_DIR"] = str(server)
        self.assertEqual(server / "data" / "cdn" / "cn", core.resolve_cdn_root())

    def test_profile_server_dir_when_no_env(self) -> None:
        server = self.root / "server4"
        make_cdn(server / ".cdn" / "cn")
        self._use_profile({"server_dir": str(server)})
        self.assertEqual(server / ".cdn" / "cn", core.resolve_cdn_root())

    def test_legacy_nested_fallback(self) -> None:
        legacy = make_cdn(self.fake_project / ".cdn" / "cn")
        self.assertEqual(legacy, core.resolve_cdn_root())

    def test_all_missing_reports_tried_list(self) -> None:
        os.environ["WF_SERVER_DIR"] = str(self.root / "no-server")
        with self.assertRaises(ValueError) as ctx:
            core.resolve_cdn_root()
        message = str(ctx.exception)
        self.assertIn("已尝试", message)
        self.assertIn("嵌套遗留", message)

    def test_lax_falls_back_to_legacy_path(self) -> None:
        resolved = core.resolve_cdn_root_lax()
        self.assertEqual(self.fake_project / ".cdn" / "cn", resolved)


class ResolveServerDirTest(_ResolveBase):
    """resolve_server_dir:WF_SERVER_DIR > profile.server_dir > 嵌套遗留。"""

    def test_env_wins(self) -> None:
        server = self.root / "srv"
        os.environ["WF_SERVER_DIR"] = str(server)
        self.assertEqual(server, core.resolve_server_dir())

    def test_profile_server_dir(self) -> None:
        server = self.root / "srv2"
        self._use_profile({"server_dir": str(server)})
        self.assertEqual(server, core.resolve_server_dir())

    def test_legacy_fallback(self) -> None:
        self.assertEqual(self.fake_project, core.resolve_server_dir())


if __name__ == "__main__":
    unittest.main()
