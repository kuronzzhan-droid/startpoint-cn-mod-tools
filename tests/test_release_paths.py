# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


MOD_TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MOD_TOOLS))


class ReleasePathResolutionCase(unittest.TestCase):
    def setUp(self) -> None:
        self.release = importlib.import_module("wf_release")
        self.core = importlib.import_module("wf_mod_tool")
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = self.root / "store" / "production" / "upload"
        self.store.mkdir(parents=True)
        self.server = self.root / "server"
        (self.server / "assets").mkdir(parents=True)
        self.cdn = self.root / "cdn" / "cn"
        (self.cdn / "archive-common-diff").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _profile(self, *, server_dir: Path | None = None, cdn_dir: Path | None = None):
        return SimpleNamespace(
            id="cn",
            store=self.store,
            server_dir=server_dir,
            cdn_dir=cdn_dir,
        )

    def test_tool_root_supports_embedded_and_flat_tool_layouts(self) -> None:
        paths_module = importlib.import_module("wf_release_paths")

        self.assertEqual(
            self.root / "server",
            paths_module.tool_checkout_root(
                self.root / "server" / "mod-tools" / "wf_release.py"
            ),
        )
        self.assertEqual(
            self.root / "wf-mod-tools",
            paths_module.tool_checkout_root(
                self.root / "wf-mod-tools" / "wf_release.py"
            ),
        )

    def test_explicit_environment_detaches_server_and_cdn_from_tool_checkout(self) -> None:
        with (
            mock.patch.object(self.core, "resolve_profile", return_value=self._profile()),
            mock.patch.dict(
                self.release.os.environ,
                {
                    "WF_SERVER_DIR": str(self.server),
                    "WF_CDN_DIR": str(self.cdn),
                },
                clear=False,
            ),
        ):
            paths = self.release._resolve_repo_paths("cn")

        expected_tool_root = importlib.import_module(
            "wf_release_paths"
        ).tool_checkout_root(Path(self.release.__file__))
        self.assertEqual(expected_tool_root, paths.tool_root)
        self.assertEqual(self.server.resolve(), paths.server_root)
        self.assertEqual(self.cdn.resolve(), paths.cdn_root)
        self.assertEqual(self.server.resolve() / "assets", paths.live_roots.server)
        self.assertEqual((self.store.parent / "medium_upload").resolve(), paths.live_roots.medium)

    def test_profile_paths_are_used_when_environment_is_unset(self) -> None:
        profile = self._profile(server_dir=self.server, cdn_dir=self.cdn)
        with (
            mock.patch.object(self.core, "resolve_profile", return_value=profile),
            mock.patch.dict(self.release.os.environ, {}, clear=False),
        ):
            self.release.os.environ.pop("WF_SERVER_DIR", None)
            self.release.os.environ.pop("WF_CDN_DIR", None)
            paths = self.release._resolve_repo_paths("cn")

        self.assertEqual(self.server.resolve(), paths.server_root)
        self.assertEqual(self.cdn.resolve(), paths.cdn_root)
        self.assertEqual(self.server.resolve() / "assets", paths.live_roots.server)

    def test_target_store_environment_wins_over_profile_store(self) -> None:
        env_store = self.root / "env-store" / "production" / "upload"
        env_store.mkdir(parents=True)
        profile = self._profile(server_dir=self.server, cdn_dir=self.cdn)
        with (
            mock.patch.object(self.core, "resolve_profile", return_value=profile),
            mock.patch.dict(
                self.release.os.environ,
                {
                    "WF_TARGET_STORE": str(env_store),
                    "WF_SERVER_DIR": str(self.server),
                    "WF_CDN_DIR": str(self.cdn),
                },
                clear=False,
            ),
        ):
            paths = self.release._resolve_repo_paths("cn")

        self.assertEqual(env_store.resolve(), paths.live_roots.common)

    def test_invalid_explicit_server_root_fails_closed(self) -> None:
        missing_server = self.root / "missing-server"
        with (
            mock.patch.object(self.core, "resolve_profile", return_value=self._profile()),
            mock.patch.dict(
                self.release.os.environ,
                {
                    "WF_SERVER_DIR": str(missing_server),
                    "WF_CDN_DIR": str(self.cdn),
                },
                clear=False,
            ),
        ):
            with self.assertRaisesRegex(self.release.ReleaseError, "server root"):
                self.release._resolve_repo_paths("cn")

    def test_invalid_explicit_cdn_root_fails_closed(self) -> None:
        invalid_cdn = self.root / "invalid-cdn"
        invalid_cdn.mkdir()
        with (
            mock.patch.object(self.core, "resolve_profile", return_value=self._profile()),
            mock.patch.dict(
                self.release.os.environ,
                {
                    "WF_SERVER_DIR": str(self.server),
                    "WF_CDN_DIR": str(invalid_cdn),
                },
                clear=False,
            ),
        ):
            with self.assertRaisesRegex(self.release.ReleaseError, "CDN root"):
                self.release._resolve_repo_paths("cn")


if __name__ == "__main__":
    unittest.main()
