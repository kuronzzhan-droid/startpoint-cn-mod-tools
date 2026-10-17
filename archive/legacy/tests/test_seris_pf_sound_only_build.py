# -*- coding: utf-8 -*-
from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = REPO_ROOT / "work" / "seris_v2" / "integration" / "build_candidate.py"
MOD_TOOLS = REPO_ROOT / "mod-tools"
if str(MOD_TOOLS) not in sys.path:
    sys.path.insert(0, str(MOD_TOOLS))

import wf_dsl

PF_TIMELINES = (
    "battle/effect/powerflip/seris_human_shooting_powerflip/"
    "seris_human_shooting_powerflip_lv1.timeline.amf3.deflate",
    "battle/effect/powerflip/seris_human_shooting_powerflip/"
    "seris_human_shooting_powerflip_lv2.timeline.amf3.deflate",
    "battle/effect/powerflip/seris_human_shooting_powerflip/"
    "seris_human_shooting_powerflip_lv3.timeline.amf3.deflate",
    "battle/effect/powerflip/seris_dragon_special_powerflip/"
    "seris_dragon_special_powerflip_lv1.timeline.amf3.deflate",
    "battle/effect/powerflip/seris_dragon_special_powerflip/"
    "seris_dragon_special_powerflip_lv2.timeline.amf3.deflate",
    "battle/effect/powerflip/seris_dragon_special_powerflip/"
    "seris_dragon_special_powerflip_lv3.timeline.amf3.deflate",
)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def _timeline(sound_path: str) -> bytes:
    inflated = wf_dsl.encode_amf3({"sounds": [{"path": sound_path}]})
    compressor = zlib.compressobj(level=9, wbits=-15)
    return compressor.compress(inflated) + compressor.flush()


def _make_baseline(root: Path) -> tuple[Path, dict[str, object]]:
    baseline = root / "baseline"
    common: list[dict[str, object]] = []
    for logical in PF_TIMELINES:
        raw = f"old:{logical}".encode("utf-8")
        _write(baseline / "roots" / "common" / Path(*logical.split("/")), raw)
        common.append(
            {
                "logical_path": logical,
                "sha256": _sha256(raw),
                "size": len(raw),
                "preserve_me": "unchanged",
            }
        )
    extra_logical = "character/seris_dragon_king/ui/full_shot_0.png"
    extra_raw = b"baseline-extra-payload"
    _write(
        baseline / "roots" / "common" / Path(*extra_logical.split("/")),
        extra_raw,
    )
    common.append(
        {
            "logical_path": extra_logical,
            "sha256": _sha256(extra_raw),
            "size": len(extra_raw),
        }
    )
    manifest: dict[str, object] = {
        "package_id": "seris_dragon_king",
        "package_version": "published-baseline",
        "roots": {
            "common": common,
            "android": [{"logical_path": "untouched/android", "sha256": "aa", "size": 1}],
            "medium": [{"logical_path": "untouched/medium", "sha256": "bb", "size": 2}],
        },
        "qa": {"delivery_mode": "production", "workspace_input_sha256": "keep-this"},
        "tables": [{"logical_path": "untouched/table", "outer_keys": ["keep"]}],
    }
    _write(
        baseline / "manifest.json",
        (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    return baseline, manifest


def _make_effects(root: Path) -> Path:
    effects = root / "effects"
    for logical in PF_TIMELINES:
        sound_path = (
            "sound_effect/unique/se_seris_water_rise"
            if "seris_human_" in logical
            else "sound_effect/unique/se_seris_dragon_breath"
        )
        _write(effects / Path(*logical.split("/")), _timeline(sound_path))
    # A sound-only build must ignore every non-target payload in the source tree.
    _write(effects / "battle/effect/powerflip/decoy.atlas.amf3.deflate", b"decoy")
    return effects


class TestSerisPfSoundOnlyBuild(unittest.TestCase):
    def _module(self):
        spec = importlib.util.spec_from_file_location("seris_pf_sound_only", BUILD_SCRIPT)
        if spec is None or spec.loader is None:
            self.fail(f"cannot load build script: {BUILD_SCRIPT}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_build_changes_only_six_timelines_and_their_manifest_hash_and_size(self) -> None:
        module = self._module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            baseline, baseline_manifest = _make_baseline(root)
            effects = _make_effects(root)
            integration = root / "integration"
            output = integration / "pf-sound-candidate"
            evidence = integration / "evidence" / "pf-sound-only.json"

            report = module.build_pf_sound_only_candidate(
                baseline,
                output,
                evidence,
                effects_source=effects,
                allowed_output_root=integration,
            )

            self.assertEqual("pf_sound_only", report["phase"])
            self.assertEqual(list(PF_TIMELINES), report["changed_payload_paths"])
            self.assertEqual(
                sorted(["manifest.json", *[f"roots/common/{p}" for p in PF_TIMELINES]]),
                report["changed_paths"],
            )
            self.assertEqual(report, json.loads(evidence.read_text(encoding="utf-8")))
            self.assertFalse(
                (
                    output
                    / "roots/common/battle/effect/powerflip/decoy.atlas.amf3.deflate"
                ).exists()
            )

            expected_manifest = copy.deepcopy(baseline_manifest)
            by_path = {
                entry["logical_path"]: entry
                for entry in expected_manifest["roots"]["common"]
            }
            for logical in PF_TIMELINES:
                source_raw = (effects / Path(*logical.split("/"))).read_bytes()
                self.assertEqual(
                    source_raw,
                    (output / "roots" / "common" / Path(*logical.split("/"))).read_bytes(),
                )
                by_path[logical]["sha256"] = _sha256(source_raw)
                by_path[logical]["size"] = len(source_raw)
            candidate_manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(expected_manifest, candidate_manifest)
            self.assertEqual(
                (baseline / "roots/common/character/seris_dragon_king/ui/full_shot_0.png").read_bytes(),
                (output / "roots/common/character/seris_dragon_king/ui/full_shot_0.png").read_bytes(),
            )

    def test_rejects_existing_output_directory(self) -> None:
        module = self._module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            baseline, _ = _make_baseline(root)
            effects = _make_effects(root)
            integration = root / "integration"
            output = integration / "already-exists"
            output.mkdir(parents=True)
            sentinel = output / "sentinel.txt"
            sentinel.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(module.BuildError, "new output directory"):
                module.build_pf_sound_only_candidate(
                    baseline,
                    output,
                    integration / "evidence.json",
                    effects_source=effects,
                    allowed_output_root=integration,
                )
            self.assertEqual("keep", sentinel.read_text(encoding="utf-8"))

    def test_diff_guard_rejects_any_non_target_payload_change(self) -> None:
        module = self._module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            baseline, _ = _make_baseline(root)
            effects = _make_effects(root)
            candidate = root / "candidate"
            module._copy_tree(baseline, candidate)
            for logical in PF_TIMELINES:
                target = candidate / "roots" / "common" / Path(*logical.split("/"))
                target.write_bytes((effects / Path(*logical.split("/"))).read_bytes())
            extra = candidate / "roots/common/character/seris_dragon_king/ui/full_shot_0.png"
            extra.write_bytes(b"unexpected-drift")

            with self.assertRaisesRegex(module.BuildError, "unexpected payload diff"):
                module._audit_pf_sound_only_diff(
                    module._snapshot(baseline), module._snapshot(candidate)
                )

    def test_rejects_evidence_overlap_before_mutating_baseline_or_effects(self) -> None:
        module = self._module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            baseline, _ = _make_baseline(root)
            effects = _make_effects(root)
            baseline_manifest = baseline / "manifest.json"
            human_timeline = effects / Path(*PF_TIMELINES[0].split("/"))
            before_manifest = baseline_manifest.read_bytes()
            before_timeline = human_timeline.read_bytes()

            for index, evidence in enumerate((baseline_manifest, human_timeline)):
                output = root / f"candidate-{index}"
                with self.subTest(evidence=evidence):
                    with self.assertRaisesRegex(module.BuildError, "evidence.*overlap"):
                        module.build_pf_sound_only_candidate(
                            baseline,
                            output,
                            evidence,
                            effects_source=effects,
                            allowed_output_root=root,
                        )
                    self.assertFalse(output.exists())
                    self.assertEqual(before_manifest, baseline_manifest.read_bytes())
                    self.assertEqual(before_timeline, human_timeline.read_bytes())

    def test_rejects_overlapping_baseline_and_effect_source_trees(self) -> None:
        module = self._module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            baseline, _ = _make_baseline(root)
            nested_effects = _make_effects(baseline)
            output = root / "candidate"

            with self.assertRaisesRegex(module.BuildError, "baseline.*effect source.*overlap"):
                module.build_pf_sound_only_candidate(
                    baseline,
                    output,
                    root / "evidence.json",
                    effects_source=nested_effects,
                    allowed_output_root=root,
                )
            self.assertFalse(output.exists())

    def test_rejects_corrupt_raw_deflate_timeline_without_creating_output(self) -> None:
        module = self._module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            baseline, _ = _make_baseline(root)
            effects = _make_effects(root)
            corrupt = effects / Path(*PF_TIMELINES[2].split("/"))
            corrupt.write_bytes(b"not-raw-deflate")
            output = root / "candidate"

            with self.assertRaisesRegex(module.BuildError, "cannot decode PF sound timeline"):
                module.build_pf_sound_only_candidate(
                    baseline,
                    output,
                    root / "evidence.json",
                    effects_source=effects,
                    allowed_output_root=root,
                )
            self.assertFalse(output.exists())

    def test_rejects_valid_timeline_with_wrong_custom_sound(self) -> None:
        module = self._module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            baseline, _ = _make_baseline(root)
            effects = _make_effects(root)
            wrong = effects / Path(*PF_TIMELINES[4].split("/"))
            wrong.write_bytes(_timeline("sound_effect/unique/se_seris_water_rise"))
            output = root / "candidate"

            with self.assertRaisesRegex(module.BuildError, "unexpected sound paths"):
                module.build_pf_sound_only_candidate(
                    baseline,
                    output,
                    root / "evidence.json",
                    effects_source=effects,
                    allowed_output_root=root,
                )
            self.assertFalse(output.exists())

    def test_cli_requires_explicit_baseline_parameter(self) -> None:
        module = self._module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            effects = _make_effects(root)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = module.main(
                    [
                        "--pf-sound-only",
                        "--output-package",
                        str(root / "integration" / "candidate"),
                        "--effects-source",
                        str(effects),
                        "--evidence",
                        str(root / "integration" / "evidence.json"),
                    ]
                )
            self.assertEqual(1, code)
            self.assertIn("--baseline-package is required", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
