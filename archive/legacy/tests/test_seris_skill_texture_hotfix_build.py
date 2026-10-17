# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_TOOLS = REPO_ROOT / "mod-tools"
if str(MOD_TOOLS) not in sys.path:
    sys.path.insert(0, str(MOD_TOOLS))

import wf_dsl


BUILD_SCRIPT = REPO_ROOT / "work" / "seris_v2" / "integration" / "build_candidate.py"
BASELINE = (
    REPO_ROOT
    / "work"
    / "cf2"
    / "seris_dragon_king_pf_sound_20260719"
    / "package"
)
EFFECTS = REPO_ROOT / "work" / "seris_v2" / "authoring" / "effects" / "_containers"
SKILL_DSL = REPO_ROOT / "work" / "seris_v2" / "authoring" / "skill_dsl"
PROGRAMS = {
    "battle/action/skill/seris_dragon_king/seris_dragon_king.action.dsl.amf3.deflate",
    "battle/action/skill/seris_dragon_king/seris_dragon_king_2.action.dsl.amf3.deflate",
    "battle/action/skill/seris_dragon_king/seris_dragon_king_matched.action.dsl.amf3.deflate",
    "battle/action/skill/seris_dragon_king/seris_dragon_king_matched_2.action.dsl.amf3.deflate",
}
FAMILIES = {
    "seris_human_royal_tide_ring",
    "seris_dragon_frozen_thunder_breath",
}


def _tree(path: Path) -> object:
    return wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]


def _primary_show_effect(tree: object) -> list[object]:
    found: list[list[object]] = []

    def walk(value: object) -> None:
        if isinstance(value, list):
            if (
                len(value) == 2
                and value[0] == "Command"
                and isinstance(value[1], list)
                and value[1]
                and value[1][0] == "ShowEffect"
                and len(value[1]) > 2
                and isinstance(value[1][2], list)
                and value[1][2][:1] == ["SpecifyEffectDirectly"]
            ):
                found.append(value[1])
            for child in value:
                walk(child)
        elif isinstance(value, dict):
            for child in value.values():
                walk(child)

    walk(tree)
    if not found:
        raise AssertionError("skill program has no direct ShowEffect")
    return found[0]


class TestSerisSkillTextureHotfixBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("seris_skill_texture_hotfix", BUILD_SCRIPT)
        if spec is None or spec.loader is None:
            raise AssertionError(f"cannot load build script: {BUILD_SCRIPT}")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_hotfix_is_reproducible_and_only_adds_loader_safe_families(self) -> None:
        self.assertTrue(
            hasattr(self.module, "build_skill_texture_hotfix_candidate"),
            "skill texture hotfix builder is missing",
        )
        with tempfile.TemporaryDirectory(prefix="seris-skill-texture-hotfix-") as tmp:
            root = Path(tmp)
            output = root / "candidate"
            evidence = root / "evidence.json"
            baseline_before = self.module._snapshot(BASELINE)

            report = self.module.build_skill_texture_hotfix_candidate(
                BASELINE,
                output,
                evidence,
                effects_source=EFFECTS,
                skill_dsl_source=SKILL_DSL,
                allowed_output_root=root,
            )

            self.assertEqual("skill_texture_hotfix", report["phase"])
            self.assertTrue(report["reproducible"])
            self.assertEqual(baseline_before, self.module._snapshot(BASELINE))
            required = {"manifest.json", *(f"roots/common/{path}" for path in PROGRAMS),
                        *(f"roots/common/battle/effect/skill_unique/{family}/{family}{suffix}"
                          for family in FAMILIES
                          for suffix in (".parts.amf3.deflate", ".timeline.amf3.deflate",
                                         ".atlas.amf3.deflate", ".png"))}
            changed = set(report["changed_paths"])
            self.assertTrue(required <= changed)
            # newer shared-source container fixes may ride along, but only
            # effect-container payloads are permitted beyond the core set
            for extra in changed - required:
                self.assertTrue(
                    extra.startswith("roots/common/battle/effect/"), extra
                )
            for family in FAMILIES:
                base = output / "roots" / "common" / "battle" / "effect" / "skill_unique" / family
                parts = _tree(base / f"{family}.parts.amf3.deflate")
                atlas = _tree(base / f"{family}.atlas.amf3.deflate")
                refs = {item["p"] for item in parts["i"]}
                names = {item["n"] for item in atlas}
                self.assertFalse(refs - names, family)
            for logical in PROGRAMS:
                baseline_tree = _tree(BASELINE / "roots" / "common" / logical)
                candidate_tree = _tree(output / "roots" / "common" / logical)
                baseline_effect = _primary_show_effect(baseline_tree)
                candidate_effect = _primary_show_effect(candidate_tree)
                # The primary ShowEffect carries every contract-driven field
                # (effect ref, offset, rotation, tracking flags, scale); the
                # hotfix may retarget all of them, so normalise the whole
                # command before requiring semantic equality elsewhere.
                baseline_effect[2][1] = candidate_effect[2][1]
                for index in (7, 8, 9, 10, 11, 12):
                    baseline_effect[index] = candidate_effect[index]
                self.assertEqual(
                    baseline_tree,
                    candidate_tree,
                    f"hotfix changed non-effect semantics in {logical}",
                )


if __name__ == "__main__":
    unittest.main()
