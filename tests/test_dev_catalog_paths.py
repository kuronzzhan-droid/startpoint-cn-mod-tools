# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


MOD_TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MOD_TOOLS))

import wf_mod_tool as core  # noqa: E402


class DevCatalogPathCase(unittest.TestCase):
    def setUp(self) -> None:
        self.previous = sys.modules.pop("wf_dev_catalog", None)
        self.addCleanup(self._restore_module)

    def _restore_module(self) -> None:
        sys.modules.pop("wf_dev_catalog", None)
        if self.previous is not None:
            sys.modules["wf_dev_catalog"] = self.previous

    def test_module_roots_use_shared_resolvers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cdn = root / "cdn" / "cn"
            server = root / "server"
            with (
                mock.patch.dict(
                    os.environ,
                    {
                        "WF_CDN_DIR": "relative-cdn",
                        "WF_SERVER_DIR": "relative-server",
                    },
                    clear=True,
                ),
                mock.patch.object(
                    core, "resolve_cdn_root_lax", return_value=cdn
                ) as cdn_resolver,
                mock.patch.object(
                    core, "resolve_server_dir", return_value=server
                ) as server_resolver,
            ):
                catalog = importlib.import_module("wf_dev_catalog")

        self.assertEqual(cdn, catalog.CDN_ROOT)
        self.assertEqual(server / "assets" / "asset-patch" / "active", catalog.ASSET_PATCH_ACTIVE)
        cdn_resolver.assert_called_once_with()
        server_resolver.assert_called_once_with()

    def test_invalid_explicit_configuration_fails_closed_during_import(self) -> None:
        with (
            mock.patch.dict(
                os.environ, {"WF_CDN_DIR": "relative-cdn"}, clear=True
            ),
            mock.patch.object(
                core,
                "resolve_cdn_root_lax",
                side_effect=ValueError("shared catalog resolver sentinel"),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "shared catalog resolver sentinel"):
                importlib.import_module("wf_dev_catalog")

    def test_foreign_entity_rows_use_the_resolved_asset_patch_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cdn = root / "cdn" / "cn"
            active = root / "server" / "assets" / "asset-patch" / "active"
            active.mkdir(parents=True)
            archive_name = "pinball-1.4.54-1.4.55-1-test.zip"
            member = "production/upload/aa/" + "b" * 38
            with zipfile.ZipFile(active / archive_name, "w") as bundle:
                bundle.writestr(member, b"payload")

            catalog = importlib.import_module("wf_dev_catalog")
            archive = catalog.ArchiveInput(
                kind="diff",
                from_version="1.4.54",
                to_version="1.4.55",
                platform="android",
                layer="common",
                order=1,
                relative_path=f"asset-patch/active/{archive_name}",
                compressed_bytes=(active / archive_name).stat().st_size,
                sha256="a" * 64,
                foreign_root=True,
            )

            rows, issues = catalog.backfill_entity_rows(
                [archive], cdn, asset_patch_active=active
            )

        self.assertIn(member, rows)
        self.assertEqual([], issues)


if __name__ == "__main__":
    unittest.main()
