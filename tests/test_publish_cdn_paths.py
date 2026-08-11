# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MOD_TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MOD_TOOLS))

import wf_mod_tool as core  # noqa: E402


class PublishCdnPathCase(unittest.TestCase):
    def setUp(self) -> None:
        self.previous = sys.modules.pop("wf_publish", None)
        self.addCleanup(self._restore_publish_module)

    def _restore_publish_module(self) -> None:
        sys.modules.pop("wf_publish", None)
        if self.previous is not None:
            sys.modules["wf_publish"] = self.previous

    def test_explicit_environment_still_uses_shared_resolver(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            expected = Path(td) / "cdn" / "cn"
            with (
                mock.patch.dict(
                    os.environ, {"WF_CDN_DIR": "relative-cdn"}, clear=True
                ),
                mock.patch.object(
                    core, "resolve_cdn_root_lax", return_value=expected
                ) as resolver,
            ):
                publish = importlib.import_module("wf_publish")

        self.assertEqual(expected, publish.CDN_ROOT)
        resolver.assert_called_once_with()

    def test_invalid_explicit_environment_fails_closed_during_import(self) -> None:
        with (
            mock.patch.dict(
                os.environ, {"WF_CDN_DIR": "relative-cdn"}, clear=True
            ),
            mock.patch.object(
                core,
                "resolve_cdn_root_lax",
                side_effect=ValueError("shared CDN resolver sentinel"),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "shared CDN resolver sentinel"):
                importlib.import_module("wf_publish")


if __name__ == "__main__":
    unittest.main()
