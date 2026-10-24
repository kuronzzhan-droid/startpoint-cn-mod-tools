# -*- coding: utf-8 -*-
"""The repoint builder must prove all three render-scale sites survive.

Repointing rewrites one class (``DevConfig_gf_android``) and repackages the
SWF.  FFDec reserializes the whole ABC while doing so, which is exactly how a
render-scale site could be lost without anyone noticing.  The builder therefore
has to fingerprint every site before and after the rewrite -- ``character-cell``
included, which it previously did not read back at all.
"""
from __future__ import annotations

from external_sources import client_patch_path, require_external_source

import hashlib
import importlib.util
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
RENDER_PATH = client_patch_path('offline-android/render_scale_pcode.py')
REPOINT_PATH = client_patch_path('repoint-apk/repoint_build.py')

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_offline_apk_render_scale import (  # noqa: E402
    EXPECTED_SITES,
    FakeFfdecRunner,
    fixture_blocks,
    load_module,
)


def _load(name: str, path: Path):
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(name, require_external_source(path))
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class RenderFingerprintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.swf = self.root / "source.swf"
        self.work = self.root / "work"
        self.profile = self.root / "profile"
        self.ffdec = self.root / "ffdec.jar"
        self.java = self.root / "java.exe"
        for path in (self.ffdec, self.java):
            path.write_bytes(b"fixture")

        blocks = fixture_blocks()
        self.patched: dict[str, str] = {}
        for site in self.module.RENDER_SITES:
            block = blocks[site.site_id]
            if block.startswith('trait method QName(PackageNamespace(""),"fixture")'):
                block = block.replace(
                    'trait method QName(PackageNamespace(""),"fixture")',
                    'trait method QName(PackageNamespace(""),"'
                    + site.method_name.rsplit("/", 1)[-1]
                    + '")',
                    1,
                )
            # Fingerprints describe a base that already carries every fix.
            self.patched[site.site_id] = site.patch(block)
        self.state = {
            site.method_name: self.patched[site.site_id]
            for site in self.module.RENDER_SITES
        }
        self.identities = {
            site.method_name: (700 + index * 17, 1700 + index * 29)
            for index, site in enumerate(self.module.RENDER_SITES)
        }
        self.swf.write_text(json.dumps(self.state, sort_keys=True), encoding="utf-8")
        self.runner = FakeFfdecRunner(
            self.module, self.swf, self.state, self.identities
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def fingerprints(self, swf: Path | None = None):
        with mock.patch.object(
            self.module.ABC_METHODS,
            "index_swf_methods",
            side_effect=self.runner.index,
        ):
            return self.module.site_fingerprints(
                swf or self.swf,
                ffdec=self.ffdec,
                java=self.java,
                profile_dir=self.profile,
                work_dir=self.work,
                runner=self.runner,
            )

    def test_fingerprints_cover_every_render_site_including_character_cell(self) -> None:
        report = self.fingerprints()

        self.assertEqual(set(EXPECTED_SITES), set(report))
        self.assertIn("character-cell", report)
        for site_id, digests in report.items():
            self.assertEqual({"pcode_sha256", "abc_sha256"}, set(digests), site_id)
            for value in digests.values():
                self.assertRegex(value, r"^[0-9a-f]{64}$")
        self.assertEqual(
            self.module._sha256_pcode(self.patched["character-cell"]),
            report["character-cell"]["pcode_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(
                self.patched["character-cell"].encode("utf-8")
            ).hexdigest(),
            report["character-cell"]["abc_sha256"],
        )

    def test_fingerprints_reject_a_base_missing_the_character_cell_fix(self) -> None:
        site = {s.site_id: s for s in self.module.RENDER_SITES}["character-cell"]
        unpatched = fixture_blocks()["character-cell"].replace(
            'trait method QName(PackageNamespace(""),"fixture")',
            'trait method QName(PackageNamespace(""),"'
            + site.method_name.rsplit("/", 1)[-1]
            + '")',
            1,
        )
        self.runner.states[self.swf.resolve()][site.method_name] = unpatched

        with self.assertRaisesRegex(
            self.module.RenderScaleError, "character-cell"
        ):
            self.fingerprints()

    def test_fingerprints_are_stable_across_offset_label_renumbering(self) -> None:
        # FFDec renumbers offset labels on every reserialization.  The P-code
        # fingerprint must see through that; the raw ABC digest must not.
        def labelled(path: Path, marker: str):
            state = {
                name: block.replace(" code\n", f" code\n{marker}:\n", 1)
                for name, block in self.state.items()
            }
            path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
            self.runner.states[path.resolve()] = state
            return path

        first = labelled(self.root / "labelled-a.swf", "ofs0008")
        second = labelled(self.root / "labelled-b.swf", "ofs01a4")

        before = self.fingerprints(first)
        after = self.fingerprints(second)

        self.assertEqual(
            {site: digest["pcode_sha256"] for site, digest in before.items()},
            {site: digest["pcode_sha256"] for site, digest in after.items()},
        )
        self.assertNotEqual(
            before["character-cell"]["abc_sha256"],
            after["character-cell"]["abc_sha256"],
        )

    def test_unchanged_assertion_catches_a_dropped_or_altered_site(self) -> None:
        before = self.fingerprints()
        self.module.assert_fingerprints_unchanged(before, dict(before))

        dropped = {k: v for k, v in before.items() if k != "character-cell"}
        with self.assertRaisesRegex(self.module.RenderScaleError, "character-cell"):
            self.module.assert_fingerprints_unchanged(before, dropped)
        with self.assertRaisesRegex(self.module.RenderScaleError, "character-cell"):
            self.module.assert_fingerprints_unchanged(dropped, before)

        altered = {k: dict(v) for k, v in before.items()}
        altered["character-cell"]["pcode_sha256"] = "0" * 64
        with self.assertRaisesRegex(self.module.RenderScaleError, "character-cell"):
            self.module.assert_fingerprints_unchanged(before, altered)

        altered = {k: dict(v) for k, v in before.items()}
        altered["member-view"]["abc_sha256"] = "0" * 64
        with self.assertRaisesRegex(self.module.RenderScaleError, "member-view"):
            self.module.assert_fingerprints_unchanged(before, altered)

    def test_unchanged_assertion_requires_the_full_expected_site_set(self) -> None:
        partial = {"pixel-art": {"pcode_sha256": "a" * 64, "abc_sha256": "b" * 64}}
        with self.assertRaisesRegex(self.module.RenderScaleError, "member-view"):
            self.module.assert_fingerprints_unchanged(partial, dict(partial))


class RepointBuilderContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.render = load_module()
        cls.repoint = _load("repoint_build_under_test", REPOINT_PATH)

    def test_builder_checks_all_three_render_sites(self) -> None:
        self.assertEqual(EXPECTED_SITES, self.repoint.RENDER_SITE_IDS)
        self.assertEqual(
            tuple(site.site_id for site in self.render.RENDER_SITES),
            self.repoint.RENDER_SITE_IDS,
        )

    def test_builder_reports_name_every_render_site_it_verified(self) -> None:
        source = REPOINT_PATH.read_text(encoding="utf-8")
        for site_id in EXPECTED_SITES:
            self.assertIn(site_id, source)
        # The superseded ad-hoc probes counted one token in one class and read
        # AS3 source text; neither could see the character-cell site.
        self.assertNotIn("SCALE_RENDERER", source)
        self.assertNotIn("SITE1_MARKERS", source)

    def test_builder_delegates_to_the_shared_render_site_definitions(self) -> None:
        def identities(module):
            return tuple(
                (site.site_id, site.class_name, site.method_name)
                for site in module.RENDER_SITES
            )

        self.assertEqual(identities(self.render), identities(self.repoint.RENDER))
        self.assertEqual(
            self.repoint.RENDER.RENDER_SITE_IDS, self.repoint.RENDER_SITE_IDS
        )


if __name__ == "__main__":
    unittest.main()
