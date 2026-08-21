#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Accepted-artifact lock and special normal-reuse tests."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import tempfile
import unittest
import zlib
from pathlib import Path

from PIL import Image

import wf_assets
import wf_dsl
import wf_pixelart_special_compat_compile as special_compile
import wf_summer_thunder_package_assemble as module


def _amf(value) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=-15)
    raw = wf_dsl.encode_amf3(value)
    return compressor.compress(raw) + compressor.flush()


def _stored_png() -> bytes:
    image = Image.new("RGBA", (2, 1))
    image.putdata([(255, 220, 0, 255), (0, 180, 255, 255)])
    output = io.BytesIO()
    image.save(output, format="PNG")
    return wf_assets.png_encode(output.getvalue())


def _special_fixture():
    prefix = f"character/{module.CODE_NAME}/pixelart"
    ticks = [*range(1, 130), 152, 158, 159, 160, 161]
    atlas = [
        {
            "n": f"{prefix}/pixelart{tick:04d}",
            "x": index % 2,
            "y": 0,
            "w": 1,
            "h": 1,
            "fx": -128,
            "fy": -128,
            "fw": 256,
            "fh": 256,
        }
        for index, tick in enumerate(ticks)
    ]
    timeline = {
        "sequences": [
            {"name": "skill_ready", "kind": "once", "begin": 51, "end": 110},
            {"name": "kachidoki", "kind": "loop", "begin": 111, "end": 158},
        ],
        "circles": [],
        "points": [],
        "sounds": [],
    }
    normal = {
        f"{prefix}/sprite_sheet.png": _stored_png(),
        f"{prefix}/sprite_sheet.atlas.amf3.deflate": _amf(atlas),
        f"{prefix}/pixelart.frame.amf3.deflate": _amf(
            {"name": f"{prefix}/pixelart", "x": -128, "y": -128,
             "scale": 6, "smoothing": False}
        ),
        f"{prefix}/pixelart.timeline.amf3.deflate": _amf(timeline),
    }
    special, report = special_compile.compile_special_compatibility(
        normal,
        target_prefix=prefix,
        expected_normal_sha256={
            logical: hashlib.sha256(payload).hexdigest()
            for logical, payload in normal.items()
        },
    )
    return normal, special, report


def _production_identity_report() -> dict:
    _normal, _special, report = _special_fixture()
    prefix = f"character/{module.CODE_NAME}/pixelart/"
    result = copy.deepcopy(report)
    result["package_manifest_eligible"] = True
    result["normal_sha256"] = {
        prefix + "pixelart.frame.amf3.deflate": module.NORMAL_V3_FRAME_SHA256,
        prefix + "pixelart.timeline.amf3.deflate": module.NORMAL_V3_TIMELINE_SHA256,
        prefix + "sprite_sheet.atlas.amf3.deflate": module.NORMAL_V3_ATLAS_SHA256,
        prefix + "sprite_sheet.png": module.NORMAL_V3_SPRITE_SHA256,
    }
    result["normal_sheet_stored_sha256"] = module.NORMAL_V3_SPRITE_SHA256
    result["special_sheet_stored_sha256"] = module.NORMAL_V3_SPRITE_SHA256
    result["output_sha256"] = dict(module.LOCKED_SPECIAL_COMPAT_V3.payload_sha256)
    result["roots"] = {"common": sorted(result["output_sha256"])}
    return result


class SpecialSourceGateTests(unittest.TestCase):
    def test_rejects_forbidden_api_predecessors(self):
        for relative, message in (
            ("special_production_api_v2", "v2.*forbidden"),
            ("special_identity_canary_api_v3", "old v3.*forbidden"),
        ):
            lock = module.ArtifactLock(
                "special",
                f"art/animations/special/{relative}/report.json",
                "a" * 64,
                f"art/animations/special/{relative}/roots/common",
                4,
            )
            with self.assertRaisesRegex(module.PackageAssemblyError, message):
                module.validate_special_artifact_lock(lock, report={})

    def test_accepts_only_the_closed_compatibility_v3_identity(self):
        report = _production_identity_report()
        module.validate_special_artifact_lock(
            module.LOCKED_SPECIAL_COMPAT_V3, report=report
        )
        report["atlas_records"] = 133
        with self.assertRaisesRegex(module.PackageAssemblyError, "134"):
            module.validate_special_artifact_lock(
                module.LOCKED_SPECIAL_COMPAT_V3, report=report
            )

    def test_payload_semantics_reuse_all_normal_records(self):
        normal, special, report = _special_fixture()
        result = module.validate_special_reuse_payloads(normal, special, report)
        self.assertEqual(134, result["atlas_record_count"])
        self.assertEqual(2, result["unique_crop_sha256"])
        self.assertEqual(0, result["new_art_pixels"])

        report["special_key_mappings"][0]["source_crop_pixel_sha256"] = "0" * 64
        with self.assertRaisesRegex(module.PackageAssemblyError, "crop hash"):
            module.validate_special_reuse_payloads(normal, special, report)


class ArtifactLockTests(unittest.TestCase):
    def test_production_source_locks_use_full_sha256_values(self):
        for lock in module.LOCKED_ARTIFACTS:
            self.assertRegex(lock.report_sha256, r"^[0-9a-f]{64}$")
            if lock.acceptance_sha256 is not None:
                self.assertRegex(lock.acceptance_sha256, r"^[0-9a-f]{64}$")
            for logical, digest in lock.payload_sha256:
                self.assertTrue(logical)
                self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_report_and_each_payload_are_hash_locked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload_root = root / "module" / "roots" / "common"
            logical = "battle/effect/test/test.png"
            payload = wf_assets.PNG_FAKE + b"locked"
            target = payload_root / Path(*logical.split("/"))
            target.parent.mkdir(parents=True)
            target.write_bytes(payload)
            report = {
                "writes_live": False,
                "output_sha256": {logical: hashlib.sha256(payload).hexdigest()},
            }
            report_raw = json.dumps(report, sort_keys=True).encode("utf-8")
            (root / "module" / "report.json").write_bytes(report_raw)
            lock = module.ArtifactLock(
                "test", "module/report.json", hashlib.sha256(report_raw).hexdigest(),
                "module/roots/common", 1,
            )
            self.assertEqual({logical: payload}, module.load_locked_artifact(root, lock))
            target.write_bytes(payload + b"drift")
            with self.assertRaisesRegex(module.PackageAssemblyError, "payload drift"):
                module.load_locked_artifact(root, lock)

    def test_explicit_payload_and_acceptance_are_both_locked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload_root = root / "module" / "roots"
            logical = f"character/{module.CODE_NAME}/ui/square_0.png"
            payload = wf_assets.PNG_FAKE + b"accepted"
            target = payload_root / Path(*logical.split("/"))
            target.parent.mkdir(parents=True)
            target.write_bytes(payload)
            report_raw = b'{"writes_live":false}'
            acceptance_raw = b'{"writes_live":false,"package_manifest_eligible":true}'
            (root / "module" / "report.json").write_bytes(report_raw)
            (root / "module" / "acceptance.json").write_bytes(acceptance_raw)
            lock = module.ArtifactLock(
                "explicit", "module/report.json", hashlib.sha256(report_raw).hexdigest(),
                "module/roots", 1,
                ((logical, hashlib.sha256(payload).hexdigest()),),
                "module/acceptance.json", hashlib.sha256(acceptance_raw).hexdigest(),
            )
            self.assertEqual({logical: payload}, module.load_locked_artifact(root, lock))
            (root / "module" / "acceptance.json").write_bytes(acceptance_raw + b"\n")
            with self.assertRaisesRegex(module.PackageAssemblyError, "acceptance drift"):
                module.load_locked_artifact(root, lock)


if __name__ == "__main__":
    unittest.main()
