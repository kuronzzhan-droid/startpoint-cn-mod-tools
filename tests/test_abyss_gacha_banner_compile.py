#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Locked abyss-gacha banner storage-encoding tests."""

from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import wf_abyss_gacha_banner_compile as module
import wf_abyss_gacha_contract as contract
import wf_assets


class AbyssGachaBannerCompileTests(unittest.TestCase):
    def test_locked_banners_encode_and_decode_to_the_exact_source_pixels(self):
        result = module.compile_locked_banners()

        self.assertEqual(
            {
                contract.LIST_BANNER_PAYLOAD_LOGICAL,
                contract.TOP_BANNER_PAYLOAD_LOGICAL,
            },
            set(result.files),
        )
        self.assertFalse(contract.LIST_BANNER_LOGICAL.endswith(".png"))
        self.assertEqual(
            f"{contract.LIST_BANNER_LOGICAL}.png",
            contract.LIST_BANNER_PAYLOAD_LOGICAL,
        )
        self.assertTrue(contract.TOP_BANNER_PAYLOAD_LOGICAL.endswith(".png"))
        expected_sizes = {
            contract.LIST_BANNER_PAYLOAD_LOGICAL: (510, 180),
            contract.TOP_BANNER_PAYLOAD_LOGICAL: (1440, 1789),
        }
        for logical, payload in result.files.items():
            self.assertTrue(payload.startswith(wf_assets.PNG_FAKE))
            with Image.open(io.BytesIO(wf_assets.png_decode(payload))) as image:
                image.load()
                self.assertEqual(expected_sizes[logical], image.size)
                self.assertEqual("RGBA", image.mode)
                self.assertEqual(
                    hashlib.sha256(image.tobytes()).hexdigest(),
                    result.report["decoded_readback"][logical]["pixel_sha256"],
                )
        self.assertEqual(2, result.report["payload_count"])
        self.assertTrue(result.report["package_manifest_eligible"])
        self.assertFalse(result.report["writes_live"])

    def test_rejects_source_sha_and_dimension_drift_before_encoding(self):
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            for spec in module.LOCKED_BANNERS:
                (root / spec.source_name).write_bytes(
                    (module.SOURCE_ASSET_DIR / spec.source_name).read_bytes()
                )
            first = module.LOCKED_BANNERS[0]
            (root / first.source_name).write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                module.compile_banners(root, module.LOCKED_BANNERS)

            (root / first.source_name).write_bytes(
                (module.SOURCE_ASSET_DIR / first.source_name).read_bytes()
            )
            second = module.LOCKED_BANNERS[1]
            with Image.new("RGBA", (10, 10), (1, 2, 3, 255)) as image:
                image.save(root / second.source_name)
            changed = tuple(
                module.BannerSpec(
                    item.source_name,
                    hashlib.sha256((root / item.source_name).read_bytes()).hexdigest(),
                    item.logical_path,
                    item.size,
                )
                for item in module.LOCKED_BANNERS
            )
            with self.assertRaisesRegex(ValueError, "dimensions"):
                module.compile_banners(root, changed)


if __name__ == "__main__":
    unittest.main()
