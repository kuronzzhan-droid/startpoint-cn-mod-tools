from __future__ import annotations

import json
import http.client
from pathlib import Path
import struct
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zlib

from wf_release_v1.errors import ReleaseError


def _png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    rows = b"\0\xff\0\0\xff"
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


class ReleaseUIActionTests(unittest.TestCase):
    def test_action_allowlist_has_no_live_install_or_rollback(self) -> None:
        from wf_release_ui_actions import ACTIONS

        self.assertEqual(
            {
                "inspect-share", "import-share", "adopt-character", "preview",
                "checkout-character", "seal-character", "build-overlay",
                "capture-requirements", "inspect-target", "plan-install",
            },
            set(ACTIONS),
        )
        self.assertNotIn("install", ACTIONS)
        self.assertNotIn("rollback", ACTIONS)
        self.assertNotIn("publish", ACTIONS)

    def test_dispatch_is_strict_and_does_not_echo_absolute_paths(self) -> None:
        from wf_release_ui_actions import UIActionError, run_action

        share = str((Path(tempfile.gettempdir()) / "incoming.wfshare.zip").resolve())
        plan = Mock()
        plan.to_wire.return_value = {"archiveSha256": "a" * 64, "writesLive": False}
        with patch("wf_release_ui_actions.inspect_legacy_share", return_value=plan) as inspect:
            result = run_action("inspect-share", {"share": share})
        inspect.assert_called_once_with(Path(share))
        self.assertEqual("a" * 64, result.wire["archiveSha256"])
        self.assertNotIn(share, json.dumps(result.wire))

        with self.assertRaises(UIActionError):
            run_action("inspect-share", {"share": share, "install": True})
        with self.assertRaises(UIActionError):
            run_action("install", {"target": share})
        with self.assertRaises(UIActionError):
            run_action("inspect-share", {"share": "relative.zip"})

    def test_release_errors_are_preserved_for_the_http_boundary(self) -> None:
        from wf_release_ui_actions import run_action

        share = str((Path(tempfile.gettempdir()) / "bad.wfshare.zip").resolve())
        with patch(
            "wf_release_ui_actions.inspect_legacy_share",
            side_effect=ReleaseError("WFREL_SHARE_INVALID", "分享包格式无效"),
        ):
            with self.assertRaises(ReleaseError) as raised:
                run_action("inspect-share", {"share": share})
        self.assertEqual("WFREL_SHARE_INVALID", raised.exception.code)

    def test_every_preparation_action_has_one_explicit_dispatch_path(self) -> None:
        from wf_release_ui_actions import run_action

        root = str(Path(tempfile.gettempdir()).resolve())
        receipt = Mock()
        receipt.to_wire.return_value = {"writesLive": False}
        target = Mock()
        preview = Mock()
        preview.manifest = {
            "mode": "sprite-sheet",
            "sequences": [{"frames": [{}, {}]}],
        }
        patches = (
            patch("wf_release_ui_actions.import_legacy_share", return_value=receipt),
            patch("wf_release_ui_actions.adopt_legacy_character", return_value=receipt),
            patch("wf_release_ui_actions.checkout_character_workspace", return_value=receipt),
            patch("wf_release_ui_actions.seal_edited_character_workspace", return_value=receipt),
            patch("wf_release_ui_actions.build_character_overlay", return_value=receipt),
            patch("wf_release_ui_actions.capture_target_requirements", return_value=receipt),
            patch("wf_release_ui_actions.inspect_target_capability", return_value=receipt),
            patch("wf_release_ui_actions.plan_target_install", return_value=receipt),
            patch("wf_release_ui_actions.ManagedTarget.load", return_value=target),
            patch("wf_release_ui_actions.WindowsPlatformAdapter", return_value=object()),
            patch("wf_release_ui_actions.load_preview", return_value=preview),
        )
        entered = [item.start() for item in patches]
        self.addCleanup(lambda: [item.stop() for item in reversed(patches)])
        self.assertFalse(run_action(
            "import-share", {"share": root, "output": root, "mapping": None}
        ).wire["writesLive"])
        self.assertFalse(run_action(
            "adopt-character", {"imported": root, "config": root, "output": root}
        ).wire["writesLive"])
        self.assertFalse(run_action("checkout-character", {
            "workspace": root, "output": root, "packageVersion": "1.1.0",
        }).wire["writesLive"])
        self.assertFalse(run_action(
            "seal-character", {"workspace": root}
        ).wire["writesLive"])
        self.assertFalse(run_action("build-overlay", {
            "workspace": root, "fromVersion": "1.4.324",
            "targetVersion": "1.4.347", "output": root,
        }).wire["writesLive"])
        self.assertFalse(run_action("capture-requirements", {
            "target": root, "workspace": root, "output": root,
        }).wire["writesLive"])
        self.assertFalse(run_action(
            "inspect-target", {"target": root}
        ).wire["writesLive"])
        self.assertFalse(run_action(
            "plan-install", {"target": root, "release": root}
        ).wire["writesLive"])
        preview_result = run_action("preview", {"source": root, "variant": "auto"})
        self.assertIs(preview, preview_result.preview)
        self.assertEqual(2, preview_result.wire["frameCount"])
        self.assertEqual(11, len(entered))


class ReleaseUIServerTests(unittest.TestCase):
    def setUp(self) -> None:
        from wf_release_ui import build_server

        self.server = build_server(port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def _post(self, action: str, value: dict[str, object], *, token: str | None = None):
        request = Request(
            f"{self.base}/api/action/{action}",
            data=json.dumps(value).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-WF-Release-UI-Token": token or self.server.ui_state.token,
            },
        )
        return urlopen(request, timeout=3)

    def test_ui_is_loopback_only_token_protected_and_has_no_install_control(self) -> None:
        self.assertEqual("127.0.0.1", self.server.server_address[0])
        html = urlopen(self.base + "/", timeout=3).read().decode("utf-8")
        self.assertIn(self.server.ui_state.token, html)
        for action in (
            "inspect-share", "import-share", "adopt-character", "preview",
            "checkout-character", "seal-character", "build-overlay",
            "capture-requirements", "inspect-target", "plan-install",
        ):
            self.assertIn(f'data-action="{action}"', html)
        self.assertNotIn('data-action="install"', html)
        self.assertNotIn('data-action="rollback"', html)
        self.assertIn("不提供安装、回滚或发布按钮", html)

        with self.assertRaises(HTTPError) as caught:
            self._post("inspect-share", {"share": "D:\\x.zip"}, token="wrong")
        self.assertEqual(403, caught.exception.code)
        caught.exception.close()

    def test_preview_action_serves_read_only_assets_without_source_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wf-release-ui-preview-") as raw:
            root = Path(raw)
            standard = _png()
            (root / "idle_1.png").write_bytes(b"\x89png\r\n\x1a\n" + standard[8:])
            response = self._post("preview", {"source": str(root), "variant": "auto"})
            body = json.loads(response.read())
            response.close()
            self.assertTrue(body["ok"])
            self.assertEqual(1, body["result"]["frameCount"])
            self.assertNotIn(str(root), json.dumps(body))

            page = urlopen(self.base + "/preview/", timeout=3).read().decode("utf-8")
            manifest = json.loads(
                urlopen(self.base + "/preview/manifest.json", timeout=3).read()
            )
            token = manifest["sequences"][0]["frames"][0]["asset"]
            asset = urlopen(self.base + "/preview/asset/" + token, timeout=3).read()
            self.assertIn("WF 2D", page)
            self.assertEqual(standard, asset)
            self.assertNotIn(str(root), json.dumps(manifest))

    def test_http_rejects_unknown_actions_bad_json_large_bodies_and_writes(self) -> None:
        with self.assertRaises(HTTPError) as caught:
            self._post("install", {})
        self.assertEqual(400, caught.exception.code)
        caught.exception.close()

        request = Request(
            self.base + "/api/action/inspect-share",
            data=b"not-json",
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-WF-Release-UI-Token": self.server.ui_state.token,
            },
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=3)
        self.assertEqual(400, caught.exception.code)
        caught.exception.close()

        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        connection.putrequest("POST", "/api/action/inspect-share")
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", str(64 * 1024 + 1))
        connection.putheader("X-WF-Release-UI-Token", self.server.ui_state.token)
        connection.endheaders()
        large = connection.getresponse()
        self.assertEqual(400, large.status)
        large.read()
        connection.close()

        request = Request(self.base + "/", data=b"{}", method="PUT")
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=3)
        self.assertEqual(405, caught.exception.code)
        caught.exception.close()


if __name__ == "__main__":
    unittest.main()
