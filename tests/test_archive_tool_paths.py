# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


MOD_TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MOD_TOOLS))

import wf_chain_squash as chain  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_pack_consolidate as pack  # noqa: E402


class ArchiveToolPathCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.expected = self.root / "configured-cdn" / "cn"

    def test_chain_squash_uses_shared_resolver_with_repo_fallback(self) -> None:
        args = SimpleNamespace(repo_root=str(self.repo), cdn=None)
        with (
            mock.patch.dict(
                os.environ, {"WF_CDN_DIR": "relative-cdn"}, clear=True
            ),
            mock.patch.object(
                core, "resolve_cdn_root_lax", return_value=self.expected
            ) as resolver,
        ):
            cdn_root, repo_root = chain._resolve_dirs(args)

        self.assertEqual(self.expected, cdn_root)
        self.assertEqual(self.repo.resolve(), repo_root)
        resolver.assert_called_once_with(
            legacy_root=self.repo.resolve() / ".cdn" / "cn"
        )

    def test_pack_consolidate_uses_shared_resolver_with_repo_fallback(self) -> None:
        with (
            mock.patch.dict(
                os.environ, {"WF_CDN_DIR": "relative-cdn"}, clear=True
            ),
            mock.patch.object(
                core, "resolve_cdn_root_lax", return_value=self.expected
            ) as resolver,
        ):
            cdn_root, repo_root = pack._resolve_dirs(repo_root=str(self.repo))

        self.assertEqual(self.expected, cdn_root)
        self.assertEqual(self.repo.resolve(), repo_root)
        resolver.assert_called_once_with(
            legacy_root=self.repo.resolve() / ".cdn" / "cn"
        )

    def test_explicit_cli_cdn_still_wins_for_both_tools(self) -> None:
        cli_cdn = self.root / "cli-cdn"
        with mock.patch.object(
            core,
            "resolve_cdn_root_lax",
            side_effect=AssertionError("shared resolver must not run"),
        ):
            chain_root, _ = chain._resolve_dirs(
                SimpleNamespace(repo_root=str(self.repo), cdn=str(cli_cdn))
            )
            pack_root, _ = pack._resolve_dirs(
                cdn=str(cli_cdn), repo_root=str(self.repo)
            )

        self.assertEqual(cli_cdn.resolve(), chain_root)
        self.assertEqual(cli_cdn.resolve(), pack_root)


if __name__ == "__main__":
    unittest.main()
