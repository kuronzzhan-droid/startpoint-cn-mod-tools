from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zlib

import wf_dsl
from wf_preview_2d import build_server
from wf_preview_2d_core import PreviewError, load_preview


def _png(width: int, height: int, rgba: tuple[int, int, int, int] = (0, 0, 0, 0)) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    rows = b"".join(b"\0" + bytes(rgba) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def _write_amf(path: Path, value: object) -> None:
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    plain = wf_dsl.encode_amf3(value)
    path.write_bytes(compressor.compress(plain) + compressor.flush())


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class Preview2DTests(unittest.TestCase):
    def test_png_sequences_are_grouped_and_codepoint_sorted(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wf-preview-sequence-") as raw:
            root = Path(raw)
            (root / "idle_0002.png").write_bytes(_png(3, 4))
            (root / "idle_0001.png").write_bytes(_png(2, 4))
            (root / "attack-10.png").write_bytes(_png(5, 6))
            (root / "attack-2.png").write_bytes(_png(4, 6))
            before = _snapshot(root)

            bundle = load_preview(root)

            self.assertEqual(bundle.manifest["mode"], "png-sequence")
            self.assertEqual(
                [sequence["name"] for sequence in bundle.manifest["sequences"]],
                ["attack", "idle"],
            )
            attack = bundle.manifest["sequences"][0]
            self.assertEqual([frame["frameNumber"] for frame in attack["frames"]], [2, 10])
            self.assertEqual(bundle.manifest["canvas"], {
                "width": 5, "height": 6, "originX": 2, "originY": 3,
            })
            self.assertNotIn(str(root), json.dumps(bundle.manifest))
            self.assertEqual(_snapshot(root), before)

    def test_character_package_pixelart_json_uses_hold_last_and_frame_origin(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wf-preview-sheet-") as raw:
            package = Path(raw)
            root = package / "pixelart"
            root.mkdir()
            (root / "sprite_sheet.png").write_bytes(_png(8, 4))
            (root / "sprite_sheet.atlas.json").write_text(json.dumps([
                {"n": "hero/pixelart0001", "x": 0, "y": 0, "w": 2, "h": 3,
                 "fx": -1, "fy": 0, "fw": 4, "fh": 4},
                {"n": "hero/pixelart0003", "x": 2, "y": 0, "w": 2, "h": 3,
                 "fx": 0, "fy": -1, "fw": 4, "fh": 4},
            ]), encoding="utf-8")
            (root / "pixelart.timeline.json").write_text(json.dumps({"sequences": [
                {"name": "idle", "kind": "loop", "begin": 1, "end": 3},
            ]}), encoding="utf-8")
            (root / "pixelart.frame.json").write_text(
                json.dumps({"originX": 1, "originY": 3, "scale": 1}), encoding="utf-8")

            bundle = load_preview(package)

            self.assertEqual(bundle.manifest["mode"], "sprite-sheet")
            self.assertEqual(bundle.manifest["canvas"], {
                "width": 4, "height": 4, "originX": 1, "originY": 3,
            })
            frames = bundle.manifest["sequences"][0]["frames"]
            self.assertEqual([frame["atlasName"] for frame in frames], [
                "hero/pixelart0001", "hero/pixelart0001", "hero/pixelart0003",
            ])
            self.assertEqual(frames[0]["destination"], {"x": 1, "y": 0, "w": 2, "h": 3})

    def test_rotated_atlas_bounds_use_the_stored_rectangle(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wf-preview-rotated-") as raw:
            root = Path(raw)
            (root / "sprite_sheet.png").write_bytes(_png(4, 6))
            (root / "sprite_sheet.atlas.json").write_text(json.dumps([
                {"n": "hero/pixelart0001", "x": 2, "y": 0, "w": 2, "h": 4,
                 "fw": 8, "fh": 8, "r": True},
            ]), encoding="utf-8")
            (root / "pixelart.timeline.json").write_text(json.dumps({"sequences": [
                {"name": "idle", "kind": "loop", "begin": 1, "end": 1},
            ]}), encoding="utf-8")

            bundle = load_preview(root)

            frame = bundle.manifest["sequences"][0]["frames"][0]
            self.assertEqual(frame["source"], {"x": 2, "y": 0, "w": 2, "h": 4})
            self.assertTrue(frame["rotated"])
            html = (Path(__file__).resolve().parents[1] / "wf_preview_2d.html").read_text(
                encoding="utf-8"
            )
            self.assertIn(
                "drawImage(image,s.x,s.y,s.w,s.h,-d.h/2,-d.w/2,d.h,d.w)",
                html,
            )

    def test_sealed_character_layout_discovers_declared_nested_pixelart(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wf-preview-sealed-") as raw:
            workspace = Path(raw)
            package = workspace / "package"
            root = package / "roots/common/character/rolf/pixelart"
            root.mkdir(parents=True)
            (root / "sprite_sheet.png").write_bytes(_png(8, 4))
            (root / "sprite_sheet.atlas.json").write_text(json.dumps([
                {"n": "rolf/pixelart0001", "x": 0, "y": 0, "w": 2, "h": 3,
                 "fw": 4, "fh": 4},
            ]), encoding="utf-8")
            (root / "pixelart.timeline.json").write_text(json.dumps({"sequences": [
                {"name": "idle", "kind": "loop", "begin": 1, "end": 1},
            ]}), encoding="utf-8")
            paths = [
                "character/rolf/pixelart/pixelart.timeline.json",
                "character/rolf/pixelart/sprite_sheet.atlas.json",
                "character/rolf/pixelart/sprite_sheet.png",
            ]
            (package / "manifest.json").write_text(json.dumps({
                "roots": {
                    "common": [
                        {"logical_path": path, "sha256": "0" * 64, "size": 1}
                        for path in paths
                    ],
                    "medium": [], "android": [], "server": [],
                },
            }), encoding="utf-8")
            before = _snapshot(workspace)

            from_workspace = load_preview(workspace)
            from_package = load_preview(package)

            self.assertEqual("sprite-sheet", from_workspace.manifest["mode"])
            self.assertEqual(from_workspace.manifest, from_package.manifest)
            self.assertEqual(
                "character/rolf/pixelart",
                from_workspace.manifest["sourceLogicalRoot"],
            )
            self.assertNotIn(str(workspace), json.dumps(from_workspace.manifest))
            self.assertEqual(before, _snapshot(workspace))

            second = package / "roots/common/character/other/pixelart"
            second.mkdir(parents=True)
            manifest = json.loads((package / "manifest.json").read_text("utf-8"))
            manifest["roots"]["common"].append({
                "logical_path": "character/other/pixelart/sprite_sheet.png",
                "sha256": "0" * 64,
                "size": 1,
            })
            (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(PreviewError, "ambiguous"):
                load_preview(package)

    def test_world_flipper_stored_png_signature_is_normalized_in_memory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wf-preview-stored-png-") as raw:
            root = Path(raw)
            standard = _png(3, 2)
            stored = b"\x89png\r\n\x1a\n" + standard[8:]
            path = root / "idle_1.png"
            path.write_bytes(stored)
            before = _snapshot(root)

            bundle = load_preview(root)
            token = bundle.manifest["sequences"][0]["frames"][0]["asset"]

            self.assertEqual(standard, bundle.read_asset(token))
            self.assertEqual(before, _snapshot(root))

    def test_amf3_deflate_metadata_is_supported_and_trailing_plaintext_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wf-preview-amf-") as raw:
            root = Path(raw)
            (root / "special_sprite_sheet.png").write_bytes(_png(4, 4))
            _write_amf(root / "special_sprite_sheet.atlas.amf3.deflate", [
                {"n": "special0000", "x": 0, "y": 0, "w": 2, "h": 2,
                 "fw": 2, "fh": 2},
            ])
            _write_amf(root / "special.timeline.amf3.deflate", {"sequences": [
                {"name": "skill", "kind": "once", "begin": 0, "end": 0},
            ]})
            _write_amf(root / "special.frame.amf3.deflate", {"scale": 1})

            bundle = load_preview(root)
            self.assertEqual(bundle.manifest["sequences"][0]["kind"], "once")

            atlas = root / "special_sprite_sheet.atlas.amf3.deflate"
            plain = zlib.decompress(atlas.read_bytes(), -15) + b"junk"
            compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
            atlas.write_bytes(compressor.compress(plain) + compressor.flush())
            with self.assertRaisesRegex(PreviewError, "trailing AMF3 bytes"):
                load_preview(root)

    def test_invalid_sources_and_metadata_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wf-preview-invalid-") as raw:
            root = Path(raw)
            with self.assertRaisesRegex(PreviewError, "no PNG frames"):
                load_preview(root)

            (root / "sprite_sheet.png").write_bytes(_png(2, 2))
            (root / "sprite_sheet.atlas.json").write_text(json.dumps([
                {"n": "pixelart0000", "x": 0, "y": 0, "w": 3, "h": 2},
            ]), encoding="utf-8")
            (root / "pixelart.timeline.json").write_text(json.dumps({"sequences": [
                {"name": "bad", "kind": "loop", "begin": 0, "end": 0},
            ]}), encoding="utf-8")
            with self.assertRaisesRegex(PreviewError, "outside sprite sheet"):
                load_preview(root)

    def test_asset_identity_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wf-preview-drift-") as raw:
            root = Path(raw)
            path = root / "idle_1.png"
            path.write_bytes(_png(1, 1))
            bundle = load_preview(root)
            token = bundle.manifest["sequences"][0]["frames"][0]["asset"]
            path.write_bytes(_png(2, 1))
            with self.assertRaisesRegex(PreviewError, "changed after preview load"):
                bundle.read_asset(token)

    def test_http_surface_is_loopback_read_only_and_does_not_modify_source(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wf-preview-http-") as raw:
            root = Path(raw)
            (root / "idle_1.png").write_bytes(_png(2, 2))
            before = _snapshot(root)
            bundle = load_preview(root)
            server = build_server(bundle, port=0)
            self.assertEqual(server.server_address[0], "127.0.0.1")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                html = urlopen(base + "/", timeout=2).read().decode("utf-8")
                manifest = json.loads(urlopen(base + "/manifest.json", timeout=2).read())
                token = manifest["sequences"][0]["frames"][0]["asset"]
                self.assertEqual(urlopen(base + "/asset/" + token, timeout=2).read(), _png(2, 2))
                self.assertIn("逐帧", html)
                self.assertIn("帧墙", html)
                for control in ("sequence", "play", "previous", "next", "scrub", "ending",
                                "speed", "scale", "transparent", "origin", "crop"):
                    self.assertIn(f'id="{control}"', html)
                self.assertNotIn(str(root), json.dumps(manifest))
                for path in ("/asset/../manifest.json", "/missing"):
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(base + path, timeout=2)
                    self.assertEqual(caught.exception.code, 404)
                    caught.exception.close()
                with self.assertRaises(HTTPError) as caught:
                    urlopen(Request(base + "/manifest.json", data=b"{}", method="POST"), timeout=2)
                self.assertEqual(caught.exception.code, 405)
                caught.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            self.assertEqual(_snapshot(root), before)

    def test_reparse_png_is_rejected_when_platform_allows_symlinks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wf-preview-link-") as raw:
            root = Path(raw)
            target = root / "target.bin"
            target.write_bytes(_png(1, 1))
            link = root / "idle_1.png"
            try:
                link.symlink_to(target)
            except OSError as error:
                self.skipTest(f"symlink creation unavailable: {error}")
            with self.assertRaisesRegex(PreviewError, "regular non-reparse"):
                load_preview(root)


if __name__ == "__main__":
    unittest.main()
