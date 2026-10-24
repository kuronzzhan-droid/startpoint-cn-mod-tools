from __future__ import annotations

from external_sources import client_patch_path, require_external_source

import hashlib
import importlib.util
import inspect
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = client_patch_path('offline-android/seris_phase4_pcode.py')
LOCK_MODULE_PATH = client_patch_path('offline-android/lock_discovery.py')
BASE_APK_SHA256 = "4f6884f33641788108c0522c7c70036c63ba530e1fdb183105b3cd395bdd66f6"

EXPECTED_SITES = (
    "preload_seris_dual_form_assets",
    "switch_special_pixel_slot_preserve_frame_scale",
    "default_seris_human_power_flip",
    "dynamic_seris_skill_cutin",
    "dynamic_seris_member_status_path",
    "refresh_seris_member_status_texture",
    "dynamic_seris_control_board_path",
    "refresh_seris_control_board_texture",
    "route_seris_skill_voice_by_form",
)

EXPECTED_ASSETS = (
    "character/seris_dragon_king/pixelart/special",
    "character/seris_dragon_king/ui/skill_cutin_dragon",
    "character/seris_dragon_king/ui/battle_control_board_dragon",
    "character/seris_dragon_king/ui/battle_member_status_dragon",
)


def load_module():
    require_external_source(MODULE_PATH)
    spec = importlib.util.spec_from_file_location("offline_seris_phase4", require_external_source(MODULE_PATH))
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_lock_module():
    require_external_source(LOCK_MODULE_PATH)
    spec = importlib.util.spec_from_file_location("offline_seris_lock_discovery", require_external_source(LOCK_MODULE_PATH))
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {LOCK_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _code(*lines: str) -> str:
    return "\n".join("            " + line for line in lines)


def _label(name: str) -> str:
    return "   " + name + ":"


def _method(*parts: str, maxstack: int = 1, localcount: int = 1) -> str:
    body = "\n".join(part for part in parts if part)
    return (
        'trait method QName(PackageNamespace(""),"fixture")\n'
        " method\n"
        f"  maxstack {maxstack}\n"
        f"  localcount {localcount}\n"
        "  initscopedepth 0\n"
        "  maxscopedepth 1\n"
        "  code\n"
        f"{body}\n"
        "  end ; code\n"
        " end ; method\n"
    )


def _named_method(name: str, *instructions: str) -> str:
    code = "\n".join(f"   {instruction}" for instruction in instructions)
    return (
        f'trait method QName(PackageNamespace(""),"{name}")\n'
        " method\n"
        "  code\n"
        f"{code}\n"
        "  end ; code\n"
        " end ; method\n"
    )


PRELOAD_ANCHOR = _code(
    "getscopeobject 1",
    "getslot 9",
    'findpropstrict QName(PackageNamespace(""),"getPixelArtAnimationPath")',
    'callproperty QName(PackageNamespace(""),"getPixelArtAnimationPath"), 0',
    'callpropvoid QName(Namespace("pinball.asset.logic:IAssetPathCollectionBuilder"),"addAnimationLayout"), 1',
)
SWAP_ANCHOR = _code(
    "pushnull",
    'astype QName(PackageNamespace("pinball.scene.battle.battle.barrier"),"BarrierHpGaugePeek")',
    "setlocal 20",
    'findproperty QName(PackageNamespace(""),"member")',
)
PF_ANCHOR = _code(
    'findpropstrict QName(PackageNamespace("pinball.common.data.skill.powerFlip"),"PowerFlipLogic")',
    'getlex QName(PackageNamespace(""),"powerFlipActionId")',
    'findpropstrict QName(PackageNamespace(""),"get_element")',
)
CUTIN_ANCHOR = _code(
    "getlocal2",
    'getproperty QName(PackageNamespace(""),"skillCutinImagePath")',
)
CUTIN_INSERT = _code(
    "getlocal2",
    'getproperty QName(PackageNamespace(""),"assistCharacter")',
    "iffalse ofs03b5",
)
STATUS_GETTER_ANCHOR = _code(
    'findproperty QName(PackageNamespace(""),"character")',
    'getproperty QName(PackageNamespace(""),"character")',
    'getproperty QName(PackageNamespace(""),"memberStatusImagePath")',
    "returnvalue",
)
STATUS_DRAW_ANCHOR = _code(
    "pushnull",
    'astype QName(PackageNamespace("flatomo.animation"),"Animation")',
    "setlocal 11",
    'findproperty QName(PackageNamespace(""),"healthPointGaugeGlow")',
)
CONTROL_GETTER_ANCHOR = _code(
    'findproperty QName(PackageNamespace(""),"character")',
    'getproperty QName(PackageNamespace(""),"character")',
    'getproperty QName(PackageNamespace(""),"controlBoardImagePath")',
    "returnvalue",
)
CONTROL_DRAW_ANCHOR = _code(
    "getlocal0",
    "pushscope",
    'findproperty QName(PackageNamespace(""),"animationAlive")',
)
VOICE_ANCHOR = "\n".join(
    (
        _label("ofs00db"),
        _code(
            "getlocal 6",
            "iffalse ofs00ea",
            "getlocal3",
            'getproperty QName(PackageNamespace(""),"switchedSkillVoicePaths")',
            "jump ofs00ef",
        ),
        _label("ofs00ea"),
        _code("getlocal3", 'getproperty QName(PackageNamespace(""),"skillVoicePaths")'),
        _label("ofs00ef"),
        _code('coerce QName(PackageNamespace(""),"Array")', "setlocal 8"),
    )
)


def fixture_blocks() -> dict[str, str]:
    return {
        EXPECTED_SITES[0]: _method(PRELOAD_ANCHOR),
        EXPECTED_SITES[1]: _method(SWAP_ANCHOR, maxstack=2, localcount=21),
        EXPECTED_SITES[2]: _method(PF_ANCHOR),
        EXPECTED_SITES[3]: _method(
            CUTIN_INSERT,
            CUTIN_ANCHOR,
            _label("ofs03b5"),
            CUTIN_ANCHOR,
            _code("returnvoid"),
            maxstack=2,
            localcount=3,
        ),
        EXPECTED_SITES[4]: _method(STATUS_GETTER_ANCHOR),
        EXPECTED_SITES[5]: _method(STATUS_DRAW_ANCHOR, maxstack=2, localcount=12),
        EXPECTED_SITES[6]: _method(CONTROL_GETTER_ANCHOR),
        EXPECTED_SITES[7]: _method(CONTROL_DRAW_ANCHOR, maxstack=2, localcount=2),
        EXPECTED_SITES[8]: _method(VOICE_ANCHOR, maxstack=2, localcount=9),
    }


class TestPatchSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_patch_schema_is_ordered_immutable_and_has_no_refresh(self) -> None:
        self.assertIsInstance(self.module.PATCHES, tuple)
        self.assertEqual(EXPECTED_SITES, tuple(p.site_id for p in self.module.PATCHES))
        self.assertFalse(hasattr(self.module, "refresh_locks"))
        patch = self.module.PATCHES[0]
        with self.assertRaises(FrozenInstanceError):
            patch.site_id = "mutated"
        self.assertTrue(self.module.SerisPatch.__dataclass_params__.frozen)
        self.assertIn("__slots__", self.module.SerisPatch.__dict__)

    def test_report_is_frozen_slotted_and_exact(self) -> None:
        self.assertEqual(
            (
                "output_path",
                "input_sha256",
                "output_sha256",
                "site_ids",
                "before_hashes",
                "after_hashes",
                "asset_logicals",
                "verified",
            ),
            tuple(self.module.SerisPatchReport.__dataclass_fields__),
        )
        self.assertTrue(self.module.SerisPatchReport.__dataclass_params__.frozen)
        self.assertIn("__slots__", self.module.SerisPatchReport.__dict__)

    def test_exact_assets_only(self) -> None:
        self.assertEqual(EXPECTED_ASSETS, self.module.extract_asset_logicals())
        serialized = json.dumps(self.module.extract_asset_logicals())
        for false_asset in ("character/", "/pixelart/special", "seris_dragon_king", "override_seris_human_powerflip"):
            self.assertNotIn(f'"{false_asset}"', serialized)

    def test_public_signatures_keep_stage_tools_explicit(self) -> None:
        apply_params = inspect.signature(self.module.apply_seris_phase4).parameters
        verify_params = inspect.signature(self.module.verify_seris_phase4).parameters
        for name in ("source_swf", "output_swf", "lock", "ffdec", "java", "profile_dir", "work_dir"):
            self.assertIn(name, apply_params)
        for name in ("output_swf", "lock", "ffdec", "java", "profile_dir", "work_dir"):
            self.assertIn(name, verify_params)


class TestPatchFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()
        cls.blocks = fixture_blocks()
        cls.by_id = {patch.site_id: patch for patch in cls.module.PATCHES}

    def test_all_nine_before_to_after_blocks_verify(self) -> None:
        for site_id in EXPECTED_SITES:
            with self.subTest(site=site_id):
                patch = self.by_id[site_id]
                output = patch.apply(self.blocks[site_id])
                self.assertNotEqual(self.blocks[site_id], output)
                patch.verify(output)

    def test_each_patch_rejects_zero_or_multiple_anchors(self) -> None:
        for site_id in EXPECTED_SITES:
            patch = self.by_id[site_id]
            block = self.blocks[site_id]
            anchor = self.module._PATCH_SPECS[site_id].before_anchor
            with self.subTest(site=site_id, kind="zero"):
                with self.assertRaises(self.module.SerisPatchError):
                    patch.apply(block.replace(anchor, "", 1))
            with self.subTest(site=site_id, kind="multiple"):
                with self.assertRaises(self.module.SerisPatchError):
                    patch.apply(block.replace(anchor, anchor + "\n" + anchor, 1))

    def test_each_patch_rejects_duplicate_application(self) -> None:
        for site_id in EXPECTED_SITES:
            with self.subTest(site=site_id):
                patch = self.by_id[site_id]
                with self.assertRaises(self.module.SerisPatchError):
                    patch.apply(patch.apply(self.blocks[site_id]))

    def test_each_patch_rejects_new_label_collision(self) -> None:
        for site_id in EXPECTED_SITES:
            spec = self.module._PATCH_SPECS[site_id]
            with self.subTest(site=site_id):
                collision = self.blocks[site_id] + f"   {spec.new_labels[0]}:\n"
                with self.assertRaises(self.module.SerisPatchError):
                    self.by_id[site_id].apply(collision)

    def test_each_verifier_rejects_semantic_marker_mutation(self) -> None:
        for site_id in EXPECTED_SITES:
            patch = self.by_id[site_id]
            spec = self.module._PATCH_SPECS[site_id]
            output = patch.apply(self.blocks[site_id])
            with self.subTest(site=site_id):
                with self.assertRaises(self.module.SerisPatchError):
                    patch.verify(output.replace(spec.marker, spec.marker + "_mutated", 1))

    def test_each_verifier_rejects_non_marker_semantic_mutation(self) -> None:
        critical = {
            "preload_seris_dual_form_assets": 'pushstring "character/seris_dragon_king/ui/skill_cutin_dragon"',
            "switch_special_pixel_slot_preserve_frame_scale": 'pushstring "/pixelart/special"',
            "default_seris_human_power_flip": 'getlex QName(PackageNamespace(""),"powerFlipActionId")',
            "dynamic_seris_skill_cutin": 'getproperty QName(PackageNamespace(""),"assistCharacter")',
            "dynamic_seris_member_status_path": 'getproperty QName(PackageNamespace(""),"memberStatusImagePath")',
            "refresh_seris_member_status_texture": 'callproperty QName(PackageNamespace(""),"getTexture"), 1',
            "dynamic_seris_control_board_path": 'getproperty QName(PackageNamespace(""),"controlBoardImagePath")',
            "refresh_seris_control_board_texture": 'getproperty QName(PackageNamespace(""),"foregroundImageDead")',
            "route_seris_skill_voice_by_form": 'getproperty QName(PackageNamespace(""),"switchedSkillVoicePaths")',
        }
        for site_id, token in critical.items():
            patch = self.by_id[site_id]
            output = patch.apply(self.blocks[site_id])
            with self.subTest(site=site_id):
                with self.assertRaises(self.module.SerisPatchError):
                    patch.verify(output.replace(token, token + "_mutated", 1))

    def test_each_verifier_rejects_duplicate_critical_semantics(self) -> None:
        critical = {
            "preload_seris_dual_form_assets": 'pushstring "character/seris_dragon_king/ui/skill_cutin_dragon"',
            "switch_special_pixel_slot_preserve_frame_scale": 'pushstring "/pixelart/special"',
            "default_seris_human_power_flip": 'getlex QName(PackageNamespace(""),"powerFlipActionId")',
            "dynamic_seris_skill_cutin": 'getproperty QName(PackageNamespace(""),"assistCharacter")',
            "dynamic_seris_member_status_path": 'getproperty QName(PackageNamespace(""),"memberStatusImagePath")',
            "refresh_seris_member_status_texture": 'callproperty QName(PackageNamespace(""),"getTexture"), 1',
            "dynamic_seris_control_board_path": 'getproperty QName(PackageNamespace(""),"controlBoardImagePath")',
            "refresh_seris_control_board_texture": 'getproperty QName(PackageNamespace(""),"foregroundImageDead")',
            "route_seris_skill_voice_by_form": 'getproperty QName(PackageNamespace(""),"switchedSkillVoicePaths")',
        }
        for site_id, token in critical.items():
            patch = self.by_id[site_id]
            output = patch.apply(self.blocks[site_id])
            with self.subTest(site=site_id):
                with self.assertRaises(self.module.SerisPatchError):
                    patch.verify(output.replace(token, token + "\n" + token, 1))

    def test_common_instructions_elsewhere_in_original_method_do_not_false_positive(self) -> None:
        unrelated = {
            "preload_seris_dual_form_assets": 'callpropvoid QName(Namespace("pinball.asset.logic:IAssetPathCollectionBuilder"),"addImage"), 1',
            "switch_special_pixel_slot_preserve_frame_scale": 'callproperty QName(PackageNamespace(""),"getAnimation"), 1',
            "default_seris_human_power_flip": 'findpropstrict QName(PackageNamespace(""),"get_element")',
            "dynamic_seris_skill_cutin": "getlocal 25",
            "dynamic_seris_member_status_path": "returnvalue",
            "refresh_seris_member_status_texture": 'callproperty QName(PackageNamespace(""),"getTexture"), 1',
            "dynamic_seris_control_board_path": "returnvalue",
            "refresh_seris_control_board_texture": 'setproperty QName(PackageNamespace(""),"texture")',
            "route_seris_skill_voice_by_form": 'getproperty QName(PackageNamespace(""),"skillVoicePaths")',
        }
        for site_id, instruction in unrelated.items():
            patch = self.by_id[site_id]
            block = self.blocks[site_id].replace("  code\n", "  code\n" + _code(instruction) + "\n", 1)
            with self.subTest(site=site_id):
                output = patch.apply(block)
                patch.verify(output)

    def test_production_like_preexisting_generic_counts_do_not_false_positive(self) -> None:
        production_like = {
            "preload_seris_dual_form_assets": (
                'callpropvoid QName(Namespace("pinball.asset.logic:IAssetPathCollectionBuilder"),"addImage"), 1',
                4,
            ),
            "route_seris_skill_voice_by_form": (
                'getproperty MultinameL([PackageNamespace("","1")])',
                9,
            ),
        }
        for site_id, (instruction, count) in production_like.items():
            patch = self.by_id[site_id]
            unrelated = "\n".join(_code(instruction) for _ in range(count))
            block = self.blocks[site_id].replace(
                "  code\n", "  code\n" + unrelated + "\n", 1
            )
            with self.subTest(site=site_id):
                output = patch.apply(block)
                patch.verify(output)

    def test_preload_and_power_flip_verifiers_reject_inverted_seris_branches(self) -> None:
        mutations = {
            "preload_seris_dual_form_assets": ("ifne ofs7a10", "ifeq ofs7a10"),
            "default_seris_human_power_flip": ("ifne ofs7a20", "ifeq ofs7a20"),
        }
        for site_id, (expected, inverted) in mutations.items():
            output = self.by_id[site_id].apply(self.blocks[site_id])
            self.assertIn(expected, output)
            with self.subTest(site=site_id):
                with self.assertRaises(self.module.SerisPatchError):
                    self.by_id[site_id].verify(output.replace(expected, inverted, 1))

    def test_each_verifier_accepts_ffdec_offset_label_renumbering(self) -> None:
        for site_index, site_id in enumerate(EXPECTED_SITES, start=1):
            patch = self.by_id[site_id]
            spec = self.module._PATCH_SPECS[site_id]
            output = patch.apply(self.blocks[site_id])
            reopened = output
            for label_index, label in enumerate(spec.new_labels, start=1):
                reopened = reopened.replace(
                    label,
                    f"ofs6{site_index:02x}{label_index:02x}",
                )
            with self.subTest(site=site_id):
                self.assertEqual(
                    self.module.canonical_pcode(output),
                    self.module.canonical_pcode(reopened),
                )
                patch.verify(reopened)

    def test_read_exported_method_dedents_real_ffdec_class_nesting(self) -> None:
        patch = self.by_id["preload_seris_dual_form_assets"]
        method = self.blocks[patch.site_id].replace(
            'trait method QName(PackageNamespace(""),"fixture")',
            'trait method QName(PackageNamespace(""),"resolvePathCollection")',
            1,
        )
        nested = "\n".join("      " + line if line else line for line in method.splitlines()) + "\n"
        with tempfile.TemporaryDirectory() as temporary:
            export_root = Path(temporary)
            target = (
                export_root
                / "scripts"
                / Path(*patch.class_name.split(".")).with_suffix(".pcode")
            )
            target.parent.mkdir(parents=True)
            target.write_text(nested, encoding="utf-8")
            extracted = self.module._read_exported_method(export_root, patch)
        self.assertEqual(method, extracted)
        patch.apply(extracted)

    def test_declarations_are_raised_and_verifier_rejects_insufficient_values(self) -> None:
        for site_id in EXPECTED_SITES:
            spec = self.module._PATCH_SPECS[site_id]
            output = self.by_id[site_id].apply(self.blocks[site_id])
            self.assertIn(f"maxstack {spec.required_maxstack}", output)
            self.assertIn(f"localcount {spec.required_localcount}", output)
            broken = output.replace(
                f"maxstack {spec.required_maxstack}", "maxstack 0", 1
            )
            with self.subTest(site=site_id):
                with self.assertRaises(self.module.SerisPatchError):
                    self.by_id[site_id].verify(broken)

    def test_cutin_requires_two_read_anchors_and_one_assist_insertion(self) -> None:
        patch = self.by_id["dynamic_seris_skill_cutin"]
        block = self.blocks[patch.site_id]
        with self.assertRaises(self.module.SerisPatchError):
            patch.apply(block.replace(CUTIN_ANCHOR, "", 1))
        with self.assertRaises(self.module.SerisPatchError):
            patch.apply(block.replace(CUTIN_INSERT, CUTIN_INSERT + "\n" + CUTIN_INSERT, 1))

    def test_cutin_verifier_rejects_assist_fallback_redirected_to_seris_join(self) -> None:
        patch = self.by_id["dynamic_seris_skill_cutin"]
        output = patch.apply(self.blocks[patch.site_id])
        redirected = output.replace("iffalse ofs03b5", "iffalse ofs7a30", 1)
        self.assertNotEqual(output, redirected)
        with self.assertRaises(self.module.SerisPatchError):
            patch.verify(redirected)

    def test_special_swap_keeps_data_driven_scale_and_seris_guard_order(self) -> None:
        patch = self.by_id["switch_special_pixel_slot_preserve_frame_scale"]
        output = patch.apply(self.blocks[patch.site_id])
        self.assertNotIn("SCALE_RENDERER", output)
        ordered = ('pushstring "ModDualForm"', 'pushstring "seris_dragon_king"', "pushbyte 22", 'pushstring "/pixelart/special"')
        positions = [output.index(token) for token in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("iffalse ofs7fe0", output)

    def test_voice_fallback_and_seris_form_selection_are_both_preserved(self) -> None:
        patch = self.by_id["route_seris_skill_voice_by_form"]
        output = patch.apply(self.blocks[patch.site_id])
        self.assertIn('getproperty QName(PackageNamespace(""),"switchedSkillVoicePaths")', output)
        self.assertIn('getproperty MultinameL([PackageNamespace("","1")])', output)
        self.assertLess(output.index('pushstring "seris_dragon_king"'), output.index("getproperty MultinameL"))


class FakeRef:
    def __init__(self, method_name: str, body_index: int, code: bytes) -> None:
        self.method_name = method_name
        self.body_index = body_index
        self.method_info_index = body_index + 1000
        self.code = code


class FakeIndex:
    def __init__(self, state: dict[str, str], calls: list[str]) -> None:
        self.state = state
        self.calls = calls

    def require_ref(self, method_name: str) -> FakeRef:
        self.calls.append(method_name)
        if method_name not in self.state:
            raise AssertionError(f"unknown fake method {method_name}")
        names = list(self.state)
        return FakeRef(method_name, names.index(method_name), self.state[method_name].encode("utf-8"))


class FakeFfdecRunner:
    def __init__(self, module, source: Path, initial: dict[str, str]) -> None:
        self.module = module
        self.states: dict[Path, dict[str, str]] = {source.resolve(): dict(initial)}
        self.calls: list[tuple[str, tuple[str, ...], Path, str]] = []

    def index(self, path: Path) -> FakeIndex:
        return FakeIndex(self._state(path), self.require_ref_calls)

    def _state(self, path: Path) -> dict[str, str]:
        resolved = Path(path).resolve()
        if resolved not in self.states:
            self.states[resolved] = json.loads(resolved.read_text(encoding="utf-8"))
        return self.states[resolved]

    require_ref_calls: list[str]

    def __call__(self, command, *, cwd: Path, env: dict[str, str], timeout: int):
        del timeout
        argv = tuple(str(part) for part in command)
        kind = "replace" if "-replace" in argv else "export"
        self.calls.append((kind, argv, Path(cwd), env["APPDATA"]))
        if kind == "replace":
            pos = argv.index("-replace")
            source = Path(argv[pos + 1]).resolve()
            destination = Path(argv[pos + 2]).resolve()
            replacement = Path(argv[pos + 4]).read_text(encoding="utf-8")
            body_index = int(argv[pos + 5])
            state = dict(self._state(source))
            method_name = list(state)[body_index]
            state[method_name] = replacement
            destination.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
            self.states[destination] = state
        else:
            pos = argv.index("-export")
            export_root = Path(argv[pos + 2])
            swf = Path(argv[pos + 3]).resolve()
            class_pos = argv.index("-selectclass")
            classes = argv[class_pos + 1].split(",")
            state = self._state(swf)
            for class_name in classes:
                methods = [
                    block.replace(
                        'trait method QName(PackageNamespace(""),"fixture")',
                        'trait method QName(PackageNamespace(""),"'
                        + patch.method_name.rsplit("/", 1)[-1]
                        + '")',
                        1,
                    )
                    for patch in self.module.PATCHES
                    if patch.class_name == class_name
                    for name, block in state.items() if name == patch.method_name
                ]
                target = export_root / "scripts" / Path(*class_name.split(".")).with_suffix(".pcode")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("\n".join(methods), encoding="utf-8")
        return {"returncode": 0, "stdout": "", "stderr": ""}


class TestFakeStagedFlow(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.swf"
        self.output = self.root / "output.swf"
        self.work = self.root / "work"
        self.profile = self.root / "profile"
        self.ffdec = self.root / "ffdec.jar"
        self.java = self.root / "java.exe"
        for path in (self.ffdec, self.java):
            path.write_bytes(b"fixture")
        blocks = fixture_blocks()
        stage_blocks = {
            patch.site_id: blocks[patch.site_id].replace(
                'trait method QName(PackageNamespace(""),"fixture")',
                'trait method QName(PackageNamespace(""),"'
                + patch.method_name.rsplit("/", 1)[-1]
                + '")',
                1,
            )
            for patch in self.module.PATCHES
        }
        self.initial = {
            patch.method_name: stage_blocks[patch.site_id]
            for patch in self.module.PATCHES
        }
        self.source.write_text(json.dumps(self.initial, sort_keys=True), encoding="utf-8")
        self.runner = FakeFfdecRunner(self.module, self.source, self.initial)
        self.runner.require_ref_calls = []
        self.after = {
            patch.site_id: hashlib.sha256(
                self.module.canonical_pcode(patch.apply(stage_blocks[patch.site_id])).encode("utf-8")
            ).hexdigest()
            for patch in self.module.PATCHES
        }
        self.before = {
            patch.site_id: hashlib.sha256(
                self.module.canonical_pcode(stage_blocks[patch.site_id]).encode("utf-8")
            ).hexdigest()
            for patch in self.module.PATCHES
        }
        self.before_abc = {
            patch.site_id: hashlib.sha256(
                stage_blocks[patch.site_id].encode("utf-8")
            ).hexdigest()
            for patch in self.module.PATCHES
        }
        self.after_abc = {
            patch.site_id: hashlib.sha256(
                patch.apply(stage_blocks[patch.site_id]).encode("utf-8")
            ).hexdigest()
            for patch in self.module.PATCHES
        }
        self.lock = {
            "schema_version": 4,
            "status": "accepted",
            "stage": "post-abyss",
            "site_ids": list(EXPECTED_SITES),
            "sites": {
                patch.site_id: {
                    "class_name": patch.class_name,
                    "method_name": patch.method_name,
                    "before_pcode_sha256": self.before[patch.site_id],
                    "after_pcode_sha256": self.after[patch.site_id],
                    "before_abc_sha256": self.before_abc[patch.site_id],
                    "after_abc_sha256": self.after_abc[patch.site_id],
                }
                for patch in self.module.PATCHES
            },
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def apply(self):
        with mock.patch.object(
            self.module.ABC_METHODS,
            "index_swf_methods",
            side_effect=self.runner.index,
        ):
            return self.module.apply_seris_phase4(
                self.source,
                self.output,
                self.lock,
                ffdec=self.ffdec,
                java=self.java,
                profile_dir=self.profile,
                work_dir=self.work,
                runner=self.runner,
            )

    def test_stage_resolves_by_name_reopens_and_cumulatively_reverifies(self) -> None:
        source_bytes = self.source.read_bytes()
        parent_appdata = "parent-appdata"
        with mock.patch.dict(os.environ, {"APPDATA": parent_appdata}, clear=False):
            report = self.apply()
            self.assertEqual(parent_appdata, os.environ["APPDATA"])
        self.assertEqual(source_bytes, self.source.read_bytes())
        self.assertTrue(self.output.is_file())
        self.assertTrue(report.verified)
        self.assertEqual(EXPECTED_SITES, report.site_ids)
        self.assertEqual(EXPECTED_ASSETS, report.asset_logicals)
        self.assertEqual(self.before, dict(report.before_hashes))
        self.assertEqual(self.after, dict(report.after_hashes))
        self.assertEqual(9, sum(kind == "replace" for kind, *_ in self.runner.calls))
        self.assertGreaterEqual(sum(kind == "export" for kind, *_ in self.runner.calls), 10)
        for patch in self.module.PATCHES:
            self.assertIn(patch.method_name, self.runner.require_ref_calls)
        commands = "\n".join(" ".join(argv).lower() for _, argv, _, _ in self.runner.calls)
        for forbidden in ("apksigner", "zipalign", "keystore", "-importscript"):
            self.assertNotIn(forbidden, commands)
        self.assertTrue(all(appdata == str(self.profile.resolve()) for *_, appdata in self.runner.calls))
        self.assertTrue(
            all(str(self.source.resolve()) not in argv for _, argv, _, _ in self.runner.calls)
        )
        for kind, argv, _, _ in self.runner.calls:
            if kind == "replace":
                self.assertIn("-onerror", argv)
                self.assertEqual("abort", argv[argv.index("-onerror") + 1])
        self.assertFalse(any(self.work.iterdir()))

    def test_stage_is_exclusive_and_rejects_wrong_lock(self) -> None:
        self.output.write_bytes(b"sentinel")
        with self.assertRaises(self.module.SerisPatchError):
            self.apply()
        self.assertEqual(b"sentinel", self.output.read_bytes())
        self.output.unlink()
        self.lock["sites"][EXPECTED_SITES[0]]["before_pcode_sha256"] = "0" * 64
        with self.assertRaises(self.module.SerisPatchError):
            self.apply()
        self.assertFalse(self.output.exists())

    def test_site_ids_define_order_while_canonical_site_key_order_is_irrelevant(self) -> None:
        self.lock["sites"] = dict(reversed(tuple(self.lock["sites"].items())))
        self.module._site_locks(self.lock)
        self.lock["site_ids"] = list(reversed(EXPECTED_SITES))
        with self.assertRaises(self.module.SerisPatchError):
            self.module._site_locks(self.lock)

    def test_stage_rejects_lexically_existing_output_leaf(self) -> None:
        real_lexists = os.path.lexists

        def pretend_broken_leaf(path) -> bool:
            if Path(path).resolve() == self.output.resolve():
                return True
            return real_lexists(path)

        with mock.patch.object(os.path, "lexists", side_effect=pretend_broken_leaf):
            with self.assertRaises(self.module.SerisPatchError):
                self.apply()
        self.assertFalse(self.runner.calls)

    def test_stage_preserves_output_created_by_an_external_publisher(self) -> None:
        original_publish = self.module._publish_staged_exclusive

        def publish_external_then_commit(staging, destination: Path, expected_hash: str) -> None:
            destination.write_bytes(b"external-sentinel")
            original_publish(staging, destination, expected_hash)

        with mock.patch.object(
            self.module,
            "_publish_staged_exclusive",
            side_effect=publish_external_then_commit,
        ):
            with self.assertRaises(self.module.SerisPatchError):
                self.apply()
        self.assertEqual(b"external-sentinel", self.output.read_bytes())

    def test_keyboard_interrupt_at_each_first_stage_boundary_leaves_no_final(self) -> None:
        for fail_call in (1, 2, 3):
            runner = FakeFfdecRunner(self.module, self.source, self.initial)
            runner.require_ref_calls = []

            def interrupt_nth(command, *, cwd, env, timeout, selected=fail_call):
                if len(runner.calls) + 1 == selected:
                    raise KeyboardInterrupt(f"cancel external call {selected}")
                return runner(command, cwd=cwd, env=env, timeout=timeout)

            with self.subTest(call=fail_call), mock.patch.object(
                self.module.ABC_METHODS,
                "index_swf_methods",
                side_effect=runner.index,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    self.module.apply_seris_phase4(
                        self.source,
                        self.output,
                        self.lock,
                        ffdec=self.ffdec,
                        java=self.java,
                        profile_dir=self.profile,
                        work_dir=self.work,
                        runner=interrupt_nth,
                    )
                self.assertFalse(self.output.exists())
                self.assertFalse(any(self.work.iterdir()))

    def test_keyboard_interrupt_during_snapshot_staging_and_cleanup_leaves_no_final(self) -> None:
        hooks = (
            "_copy_snapshot",
            "_stage_output_sibling",
            "_clean_transaction_before_publish",
        )
        for hook in hooks:
            with self.subTest(hook=hook), mock.patch.object(
                self.module,
                hook,
                side_effect=KeyboardInterrupt(f"cancel {hook}"),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    self.apply()
                self.assertFalse(self.output.exists())
                self.assertFalse(any(self.work.iterdir()))

    def test_publish_interrupt_never_unlinks_external_destination(self) -> None:
        def external_then_interrupt(staging, destination: Path, expected_hash: str):
            del staging, expected_hash
            destination.write_bytes(b"external-on-cancel")
            raise KeyboardInterrupt("cancel at commit")

        with mock.patch.object(
            self.module,
            "_publish_staged_exclusive",
            side_effect=external_then_interrupt,
        ):
            with self.assertRaises(KeyboardInterrupt):
                self.apply()
        self.assertEqual(b"external-on-cancel", self.output.read_bytes())
        self.assertFalse(any(self.work.iterdir()))

    def test_transaction_is_clean_before_final_commit(self) -> None:
        original_publish = self.module._publish_staged_exclusive

        def assert_clean_then_publish(staging, destination: Path, expected_hash: str):
            self.assertFalse(any(self.work.iterdir()))
            original_publish(staging, destination, expected_hash)

        with mock.patch.object(
            self.module,
            "_publish_staged_exclusive",
            side_effect=assert_clean_then_publish,
        ):
            self.apply()
        self.assertTrue(self.output.is_file())

    def test_stage_rejects_raw_abc_lock_mismatch_before_and_after(self) -> None:
        first = EXPECTED_SITES[0]
        self.lock["sites"][first]["before_abc_sha256"] = "0" * 64
        with self.assertRaises(self.module.SerisPatchError):
            self.apply()
        self.assertFalse(self.output.exists())
        self.lock["sites"][first]["before_abc_sha256"] = self.before_abc[first]
        self.lock["sites"][first]["after_abc_sha256"] = "0" * 64
        with self.assertRaises(self.module.SerisPatchError):
            self.apply()
        self.assertFalse(self.output.exists())

    def test_stage_stops_after_external_call_when_original_source_drifts(self) -> None:
        original_runner = self.runner

        def mutate_source_after_first_call(command, *, cwd, env, timeout):
            result = original_runner(command, cwd=cwd, env=env, timeout=timeout)
            if len(original_runner.calls) == 1:
                self.source.write_bytes(b"source-drift")
            return result

        with mock.patch.object(
            self.module.ABC_METHODS,
            "index_swf_methods",
            side_effect=original_runner.index,
        ):
            with self.assertRaises(self.module.SerisPatchError):
                self.module.apply_seris_phase4(
                    self.source,
                    self.output,
                    self.lock,
                    ffdec=self.ffdec,
                    java=self.java,
                    profile_dir=self.profile,
                    work_dir=self.work,
                    runner=mutate_source_after_first_call,
                )
        self.assertEqual(1, len(original_runner.calls))
        self.assertFalse(self.output.exists())

    def test_stage_rejects_output_ancestor_topology_before_external_calls(self) -> None:
        unsafe_output = self.root / "container"
        unsafe_work = unsafe_output / "work"
        with mock.patch.object(
            self.module.ABC_METHODS,
            "index_swf_methods",
            side_effect=self.runner.index,
        ):
            with self.assertRaises(self.module.SerisPatchError):
                self.module.apply_seris_phase4(
                    self.source,
                    unsafe_output,
                    self.lock,
                    ffdec=self.ffdec,
                    java=self.java,
                    profile_dir=self.profile,
                    work_dir=unsafe_work,
                    runner=self.runner,
                )
        self.assertFalse(self.runner.calls)
        self.assertFalse(unsafe_output.exists())

    def test_stage_rejects_source_output_hardlink_alias_before_external_calls(self) -> None:
        try:
            os.link(self.source, self.output)
        except OSError as exc:
            self.skipTest(f"hardlinks unavailable: {exc}")
        with self.assertRaises(self.module.SerisPatchError):
            self.apply()
        self.assertFalse(self.runner.calls)
        self.assertEqual(self.source.read_bytes(), self.output.read_bytes())

    def test_report_hash_is_bound_before_publish_and_never_reads_final_path(self) -> None:
        original_hash = self.module._sha256_file

        def reject_final_read(path: Path) -> str:
            if Path(path).resolve() == self.output.resolve():
                raise AssertionError("final output path was read after publication")
            return original_hash(path)

        with mock.patch.object(self.module, "_sha256_file", side_effect=reject_final_read):
            report = self.apply()
        self.assertTrue(self.output.is_file())
        self.assertEqual(hashlib.sha256(self.output.read_bytes()).hexdigest(), report.output_sha256)


def candidate_fixture(seris_module, lock_module) -> dict:
    sites = {}
    for index, patch in enumerate(seris_module.PATCHES):
        before_pcode = hashlib.sha256(f"before-pcode-{index}".encode()).hexdigest()
        after_pcode = hashlib.sha256(f"after-pcode-{index}".encode()).hexdigest()
        before_abc = hashlib.sha256(f"before-abc-{index}".encode()).hexdigest()
        after_abc = hashlib.sha256(f"after-abc-{index}".encode()).hexdigest()
        sites[patch.site_id] = {
            "class_name": patch.class_name,
            "method_name": patch.method_name,
            "before_pcode_sha256": before_pcode,
            "after_pcode_sha256": after_pcode,
            "before_abc_sha256": before_abc,
            "after_abc_sha256": after_abc,
        }
    compatibility_names = (
        "pinball.scene.battle.battle.squad.member:MemberImpl/startPowerFlip",
        "pinball.scene.battle.battle.squad.member:MemberImpl/resolveConditionalKind",
        "pinball.ui.component.pixelArtCharacter:PixelArtCharacterView/spriteSheetLoadCompleted",
        "pinball.scene.battle.battle.squad.member:MemberView/MemberView",
    )
    return {
        "schema_version": 4,
        "status": "candidate",
        "stage": "post-abyss",
        "site_count": 9,
        "verified": True,
        "source_apk_sha256": BASE_APK_SHA256,
        "source_swf_sha256": "08187f538703aecadce264b7bd5e085411f8e3aedb5f48adf2cf035a100f550d",
        "post_abyss_swf_sha256": hashlib.sha256(b"post-abyss-swf").hexdigest(),
        "abyss_stage": {
            "stage": "abyss-mode-equipment",
            "input_sha256": "08187f538703aecadce264b7bd5e085411f8e3aedb5f48adf2cf035a100f550d",
            "output_sha256": hashlib.sha256(b"post-abyss-swf").hexdigest(),
            "target_class": "pinball.common.data.character.BattleCharacterLogic",
            "before_method_sha256": hashlib.sha256(b"abyss-before").hexdigest(),
            "after_method_sha256": hashlib.sha256(b"abyss-after").hexdigest(),
            "match_count": 1,
        },
        "manifest_sha256": "2823fbfad46bfcdc34c8df77b3f2ed2acf9f5812b8b61644304cc6d11109d6f9",
        "dex_sha256": {
            "classes.dex": "c12d119d425f0e8f35623dbac07296e00a8b9e60620c4f371b307121b389c043",
            "classes2.dex": "b310c77febb7da0d2908b32274391ae39226a9df334e0d7d7f51b5a081bc539b",
        },
        "native_aggregate_sha256": "a42f92e417199a9ac99ca4f63efa0db487019bdf1220a86301fcfa0a4118f995",
        "native_members": deepcopy(lock_module.EXPECTED_NATIVE_MEMBERS),
        "offline_method_sha256": {
            "DevConfig_individual/DevConfig_individual": "ac87a4744507d4fa47fa46af99290a1aec0c230a5338e317cbeeb7c80badc139",
            "boot_ffc6#$script364/$init": "afcb8c8602158db0a64ba1560f36875166004283bfe6a04ad9eeaf49ee3714b2",
            "InitializeDummyRemote/logicAssetLoadedHandler": "d17591dc3c793faaa02c1080968b0bb30384b968f70dbe9363d8860fa30fcd3c",
            "DummyRemote/debugUnlinkTwitter": "45bc87da473d018f700f349fda2c743a6d11509cc236390584dccf2ac7d75a38",
        },
        "save_method_sha256": {
            "InitializeDummyRemote/logicAssetLoadedHandler": "d17591dc3c793faaa02c1080968b0bb30384b968f70dbe9363d8860fa30fcd3c",
            "DummyRemote/debugUnlinkTwitter": "45bc87da473d018f700f349fda2c743a6d11509cc236390584dccf2ac7d75a38",
        },
        "site_ids": list(EXPECTED_SITES),
        "asset_logicals": list(EXPECTED_ASSETS),
        "sites": sites,
        "native_compatibility": {
            name: {
                "abc_sha256": digest,
                "semantic_verified": True,
            }
            for name, digest in zip(
                compatibility_names,
                (
                    "675b4a9e5874e5bba8502ea998963a20ab198d3553e0159a5f8422b7c9987f51",
                    "eb0b16be3b9503e5604c97b5f8866cdc7754b6cf43a88d376b92ed0ef3ce00b0",
                    "9475368c4dd326f0d8230ba724d96a60af5d30dba37ac5d43d5bdd04a85b038b",
                    "0ca2af059a85e432c9c6dc991126d0eeba57acaa5ecc152aee83e36ed19a9d77",
                ),
            )
        },
        "three_way_merges": {
            "preload_seris_dual_form_assets": {
                "base_method_abc_sha256": "4c17b898e702b11092ee4d8ec148b18b3550900475f3b0e14a1ef725062f84fd",
                "post_abyss_before_abc_sha256": sites["preload_seris_dual_form_assets"]["before_abc_sha256"],
                "preserved_semantics": [
                    "offline_base_path",
                    "abyss_equipment_gate",
                    "seris_dual_form_preload",
                ],
                "verified": True,
            },
            "default_seris_human_power_flip": {
                "base_method_abc_sha256": "fe609f8079a69de8b6276a10f166676e232a917aedf03c1702314dbcd96ac4c9",
                "post_abyss_before_abc_sha256": sites["default_seris_human_power_flip"]["before_abc_sha256"],
                "preserved_semantics": [
                    "offline_base_power_flip",
                    "seris_human_dragon_selection",
                ],
                "verified": True,
            },
        },
    }


def extension_fixture(lock_module, base: dict) -> dict:
    extended = deepcopy(base)
    extended["render_site_ids"] = ["pixel-art", "member-view", "character-cell"]
    identities = (
        (
            "pixel-art",
            "pinball.ui.component.pixelArtCharacter.PixelArtCharacterView",
            "pinball.ui.component.pixelArtCharacter:PixelArtCharacterView/spriteSheetLoadCompleted",
            "9475368c4dd326f0d8230ba724d96a60af5d30dba37ac5d43d5bdd04a85b038b",
        ),
        (
            "member-view",
            "pinball.scene.battle.battle.squad.member.MemberView",
            "pinball.scene.battle.battle.squad.member:MemberView/MemberView",
            "0ca2af059a85e432c9c6dc991126d0eeba57acaa5ecc152aee83e36ed19a9d77",
        ),
        (
            "character-cell",
            "pinball.scene.character.cell.CharacterCellView",
            "pinball.scene.character.cell:CharacterCellView/drawWithAdvanceFlag",
            "cc64eafcb0bbaeb4f1ae705944da569cc1d59bf9dc7636b1bbfe64342175e3a7",
        ),
    )
    extended["render_sites"] = {
        site_id: {
            "class_name": class_name,
            "method_name": method_name,
            "before_pcode_sha256": hashlib.sha256(
                f"render-before-pcode-{site_id}".encode()
            ).hexdigest(),
            "after_pcode_sha256": hashlib.sha256(
                f"render-after-pcode-{site_id}".encode()
            ).hexdigest(),
            "before_abc_sha256": before_abc,
            "after_abc_sha256": hashlib.sha256(
                f"render-after-abc-{site_id}".encode()
            ).hexdigest(),
        }
        for site_id, class_name, method_name, before_abc in identities
    }
    extended["resource_version"] = {
        "site_id": "full-resource-version",
        "class_name": "pinball.config.core.DevConfig",
        "method_name": "boot_ffc6#$script364/$init",
        "source_version": "1.4.54",
        "target_version": "1.4.196",
        "before_pcode_sha256": hashlib.sha256(
            b"resource-before-pcode"
        ).hexdigest(),
        "after_pcode_sha256": hashlib.sha256(
            b"resource-after-pcode"
        ).hexdigest(),
        "before_abc_sha256": base["offline_method_sha256"][
            "boot_ffc6#$script364/$init"
        ],
        "after_abc_sha256": hashlib.sha256(b"resource-after-abc").hexdigest(),
    }
    return extended


class TestLockDiscovery(unittest.TestCase):
    def setUp(self) -> None:
        self.seris = load_module()
        self.module = load_lock_module()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.candidate = candidate_fixture(self.seris, self.module)
        self.candidate_path = self.root / "candidate.json"
        self.accepted_path = self.root / "base-lock.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_candidate(self, value=None) -> None:
        payload = self.candidate if value is None else value
        self.candidate_path.write_bytes(self.module._canonical_json_bytes(payload))

    def candidate_sha256(self, value=None) -> str:
        payload = self.candidate if value is None else value
        return hashlib.sha256(self.module._canonical_json_bytes(payload)).hexdigest()

    def accepted_base(self) -> dict:
        accepted = deepcopy(self.candidate)
        accepted["status"] = "accepted"
        return accepted

    def test_strict_json_rejects_duplicate_keys_and_nonstandard_constants(self) -> None:
        for raw in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
            self.candidate_path.write_text(raw, encoding="utf-8")
            with self.subTest(raw=raw), self.assertRaises(self.module.LockDiscoveryError):
                self.module._load_json_strict(self.candidate_path)

    def test_save_lock_uses_actual_read_and_write_method_identities(self) -> None:
        self.assertEqual(
            {
                "InitializeDummyRemote/logicAssetLoadedHandler":
                    "d17591dc3c793faaa02c1080968b0bb30384b968f70dbe9363d8860fa30fcd3c",
                "DummyRemote/debugUnlinkTwitter":
                    "45bc87da473d018f700f349fda2c743a6d11509cc236390584dccf2ac7d75a38",
            },
            self.module.EXPECTED_SAVE_METHOD_SHA256,
        )

    def test_save_haxe_verifier_checks_each_exact_method_body(self) -> None:
        refs = (
            SimpleNamespace(
                aliases=(
                    "pinball.remote.initialize:InitializeDummyRemote/logicAssetLoadedHandler",
                )
            ),
            SimpleNamespace(
                aliases=(
                    "pinball.context.remote.dummy:DummyRemote/debugUnlinkTwitter",
                )
            ),
        )

        def export_valid_methods(_source, export_root, classes, **_kwargs):
            self.assertEqual(
                (
                    "pinball.remote.initialize.InitializeDummyRemote",
                    "pinball.context.remote.dummy.DummyRemote",
                ),
                tuple(classes),
            )
            read_path = (
                Path(export_root)
                / "scripts/pinball/remote/initialize/InitializeDummyRemote.pcode"
            )
            write_path = (
                Path(export_root)
                / "scripts/pinball/context/remote/dummy/DummyRemote.pcode"
            )
            read_path.parent.mkdir(parents=True)
            write_path.parent.mkdir(parents=True)
            read_path.write_text(
                _named_method(
                    "logicAssetLoadedHandler",
                    'getproperty QName(PackageNamespace(""),"userDirectory")',
                    'pushstring "WorldFlipper/save_haxe"',
                    'callproperty QName(PackageNamespace(""),"resolvePath"), 1',
                    'getproperty QName(PackageNamespace(""),"READ")',
                    'callproperty QName(PackageNamespace(""),"readUTFBytes"), 1',
                ),
                encoding="utf-8",
            )
            write_path.write_text(
                _named_method(
                    "debugUnlinkTwitter",
                    'getproperty QName(PackageNamespace(""),"userDirectory")',
                    'pushstring "WorldFlipper/save_haxe"',
                    'callproperty QName(PackageNamespace(""),"resolvePath"), 1',
                    'getproperty QName(PackageNamespace(""),"WRITE")',
                    'callpropvoid QName(PackageNamespace(""),"writeUTFBytes"), 1',
                ),
                encoding="utf-8",
            )

        with mock.patch.object(
            self.module.SERIS.ABC_METHODS,
            "index_swf_methods",
            return_value=SimpleNamespace(refs=refs),
        ), mock.patch.object(
            self.module.SERIS,
            "_export_classes",
            side_effect=export_valid_methods,
        ):
            self.module._verify_save_haxe_pcode(
                self.root / "source.swf",
                export_root=self.root / "save-export",
                ffdec=self.root / "ffdec.jar",
                java=self.root / "java.exe",
                profile_dir=self.root / "profile",
                runner=mock.Mock(),
                timeout=1,
            )

    def test_save_haxe_verifier_rejects_literal_only_in_unrelated_method(self) -> None:
        refs = (
            SimpleNamespace(
                aliases=(
                    "pinball.remote.initialize:InitializeDummyRemote/logicAssetLoadedHandler",
                )
            ),
            SimpleNamespace(
                aliases=(
                    "pinball.context.remote.dummy:DummyRemote/debugUnlinkTwitter",
                )
            ),
        )

        def export_misplaced_literal(_source, export_root, _classes, **_kwargs):
            read_path = (
                Path(export_root)
                / "scripts/pinball/remote/initialize/InitializeDummyRemote.pcode"
            )
            write_path = (
                Path(export_root)
                / "scripts/pinball/context/remote/dummy/DummyRemote.pcode"
            )
            read_path.parent.mkdir(parents=True)
            write_path.parent.mkdir(parents=True)
            read_path.write_text(
                _named_method("logicAssetLoadedHandler", "returnvoid")
                + _named_method("unrelated", 'pushstring "WorldFlipper/save_haxe"'),
                encoding="utf-8",
            )
            write_path.write_text(
                _named_method(
                    "debugUnlinkTwitter",
                    'pushstring "WorldFlipper/save_haxe"',
                    'getproperty QName(PackageNamespace(""),"WRITE")',
                    'callpropvoid QName(PackageNamespace(""),"writeUTFBytes"), 1',
                ),
                encoding="utf-8",
            )

        with mock.patch.object(
            self.module.SERIS.ABC_METHODS,
            "index_swf_methods",
            return_value=SimpleNamespace(refs=refs),
        ), mock.patch.object(
            self.module.SERIS,
            "_export_classes",
            side_effect=export_misplaced_literal,
        ):
            with self.assertRaises(self.module.LockDiscoveryError):
                self.module._verify_save_haxe_pcode(
                    self.root / "source.swf",
                    export_root=self.root / "save-export",
                    ffdec=self.root / "ffdec.jar",
                    java=self.root / "java.exe",
                    profile_dir=self.root / "profile",
                    runner=mock.Mock(),
                    timeout=1,
                )

    def test_seris_exports_controlled_lock_interfaces_and_verify_lock_cli(self) -> None:
        self.assertTrue(callable(self.seris.discover_lock_candidate))
        self.assertTrue(callable(self.seris.accept_lock_candidate))
        accepted = deepcopy(self.candidate)
        accepted["status"] = "accepted"
        self.candidate_path.write_bytes(self.module._canonical_json_bytes(accepted))
        output = io.StringIO()
        with redirect_stdout(output):
            result = self.seris.main(["verify-lock", "--lock", str(self.candidate_path)])
        self.assertEqual(0, result)
        summary = json.loads(output.getvalue())
        self.assertEqual(9, summary["site_count"])
        self.assertTrue(summary["verified"])
        self.assertEqual(list(EXPECTED_ASSETS), summary["asset_logicals"])

    def test_candidate_schema_freezes_compatibility_merges_and_exact_order(self) -> None:
        self.module.validate_lock_document(self.candidate, expected_status="candidate")
        mutations = []
        for field, value in (
            ("source_apk_sha256", "0" * 64),
            ("stage", "base"),
            ("site_count", 8),
        ):
            item = deepcopy(self.candidate)
            item[field] = value
            mutations.append(item)
        item = deepcopy(self.candidate)
        item["site_ids"].reverse()
        mutations.append(item)
        item = deepcopy(self.candidate)
        item["native_compatibility"].pop(next(iter(item["native_compatibility"])))
        mutations.append(item)
        item = deepcopy(self.candidate)
        item["native_compatibility"][next(iter(item["native_compatibility"]))]["abc_sha256"] = "0" * 64
        mutations.append(item)
        item = deepcopy(self.candidate)
        item["abyss_stage"]["output_sha256"] = "0" * 64
        mutations.append(item)
        item = deepcopy(self.candidate)
        item["three_way_merges"]["preload_seris_dual_form_assets"]["verified"] = False
        mutations.append(item)
        for value in mutations:
            with self.subTest(value=value.get("stage")), self.assertRaises(self.module.LockDiscoveryError):
                self.module.validate_lock_document(value, expected_status="candidate")

    def test_extension_candidate_preserves_every_task9_field(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        validated = self.module.validate_extension_candidate(candidate, base)
        self.assertEqual(base, {key: candidate[key] for key in base})
        self.assertEqual(9, candidate["site_count"])
        self.assertEqual(base["sites"], candidate["sites"])
        self.assertEqual("accepted", candidate["status"])
        self.assertIs(candidate, validated)
        self.module.validate_lock_document(
            candidate,
            expected_status="accepted",
            require_extensions=True,
        )

    def test_extension_schema_rejects_old_field_or_corrected_site_drift(self) -> None:
        base = self.accepted_base()
        mutations = []
        changed_count = extension_fixture(self.module, base)
        changed_count["site_count"] = 12
        mutations.append(changed_count)
        polluted_sites = extension_fixture(self.module, base)
        polluted_sites["sites"]["pixel-art"] = polluted_sites["render_sites"][
            "pixel-art"
        ]
        mutations.append(polluted_sites)
        wrong_render_order = extension_fixture(self.module, base)
        wrong_render_order["render_site_ids"].reverse()
        mutations.append(wrong_render_order)
        obsolete_character_cell = extension_fixture(self.module, base)
        obsolete_character_cell["render_sites"]["character-cell"].update(
            {
                "class_name": "pinball.scene.character.cell.CharacterCell",
                "method_name": "pinball.scene.character.cell:CharacterCell/CharacterCell",
                "before_abc_sha256": "f1d643128a517f7ae5f6c0628c3d96761254a67f34520a257ab302519329a0b8",
            }
        )
        mutations.append(obsolete_character_cell)
        wrong_resource_before = extension_fixture(self.module, base)
        wrong_resource_before["resource_version"]["before_abc_sha256"] = "0" * 64
        mutations.append(wrong_resource_before)
        for candidate in mutations:
            with self.subTest(keys=tuple(candidate)), self.assertRaises(
                self.module.LockDiscoveryError
            ):
                self.module.validate_extension_candidate(candidate, base)

    def test_discover_extension_writes_new_full_candidate_and_never_edits_base(self) -> None:
        apk = self.root / "base.apk"
        with zipfile.ZipFile(apk, "w") as archive:
            archive.writestr("assets/worldflipper_android_release.swf", b"swf-fixture")
        base = self.accepted_base()
        base_path = self.root / "accepted-v4.json"
        base_raw = self.module._canonical_json_bytes(base)
        base_path.write_bytes(base_raw)
        base_sha256 = hashlib.sha256(base_raw).hexdigest()
        baseline_fields = {
            key: deepcopy(base[key])
            for key in (
                "source_swf_sha256",
                "manifest_sha256",
                "dex_sha256",
                "native_aggregate_sha256",
                "native_members",
            )
        }
        extension = {
            key: deepcopy(extension_fixture(self.module, base)[key])
            for key in ("render_site_ids", "render_sites", "resource_version")
        }
        calls = []

        def provider(*, source_swf: Path, accepted_lock, transaction_dir: Path):
            calls.append(
                (
                    source_swf.read_bytes(),
                    accepted_lock["status"],
                    source_swf.parent == transaction_dir,
                )
            )
            return extension

        candidate_path = self.root / "extension-candidate.json"
        with mock.patch.object(
            self.module,
            "_sha256_file",
            side_effect=lambda path: (
                BASE_APK_SHA256
                if Path(path).suffix == ".apk"
                else self.module.EXPECTED_SWF_SHA256
                if Path(path).name == "source.swf"
                else hashlib.sha256(Path(path).read_bytes()).hexdigest()
            ),
        ), mock.patch.object(
            self.module, "_inspect_base_apk", return_value=baseline_fields
        ):
            result = self.module.discover_extension_candidate(
                apk,
                base_path,
                candidate_path,
                work_dir=self.root / "extension-work",
                evidence_provider=provider,
                expected_old_lock_sha256=base_sha256,
            )
        self.assertEqual([(b"swf-fixture", "accepted", True)], calls)
        self.assertEqual(base_raw, base_path.read_bytes())
        self.assertEqual(
            self.module._canonical_json_bytes(result), candidate_path.read_bytes()
        )
        self.assertEqual(base, {key: result[key] for key in base})
        self.assertEqual(extension, {key: result[key] for key in extension})

    def test_discover_extension_rejects_wrong_old_lock_digest_before_provider(self) -> None:
        apk = self.root / "base.apk"
        apk.write_bytes(b"fixture")
        base_path = self.root / "accepted-v4.json"
        base_path.write_bytes(self.module._canonical_json_bytes(self.accepted_base()))
        provider = mock.Mock()
        with self.assertRaises(self.module.LockDiscoveryError):
            self.module.discover_extension_candidate(
                apk,
                base_path,
                self.root / "extension-candidate.json",
                work_dir=self.root / "extension-work",
                evidence_provider=provider,
                expected_old_lock_sha256="0" * 64,
            )
        provider.assert_not_called()

    def test_extension_provider_composes_all_stages_in_locked_order(self) -> None:
        source = self.root / "source.swf"
        source.write_bytes(b"source")
        transaction = self.root / "extension-pipeline"
        transaction.mkdir()
        accepted = self.accepted_base()
        extension = extension_fixture(self.module, accepted)
        calls = []

        def stage(name, expected_input, evidence):
            def invoke(*, source_swf: Path, accepted_lock, transaction_dir: Path):
                self.assertEqual(expected_input, source_swf.name)
                self.assertIs(accepted, accepted_lock)
                self.assertEqual(transaction, transaction_dir)
                calls.append(name)
                output = transaction_dir / f"post-{name}.swf"
                output.write_bytes(name.encode("ascii"))
                return output, deepcopy(evidence)

            return invoke

        def verify_final(*, source_swf: Path, extended_lock, transaction_dir: Path):
            self.assertEqual("post-resource.swf", source_swf.name)
            self.assertEqual(extension, extended_lock)
            self.assertEqual(transaction, transaction_dir)
            calls.append("verify")

        provider = self.module.compose_extension_evidence_provider(
            abyss_stage=stage("abyss", "source.swf", {}),
            seris_stage=stage("seris", "post-abyss.swf", {}),
            render_stage=stage(
                "render",
                "post-seris.swf",
                {
                    "render_site_ids": extension["render_site_ids"],
                    "render_sites": extension["render_sites"],
                },
            ),
            resource_stage=stage(
                "resource",
                "post-render.swf",
                {"resource_version": extension["resource_version"]},
            ),
            final_verifier=verify_final,
        )
        evidence = provider(
            source_swf=source,
            accepted_lock=accepted,
            transaction_dir=transaction,
        )

        self.assertEqual(
            ["abyss", "seris", "render", "resource", "verify"], calls
        )
        self.assertEqual(
            {
                "render_site_ids": extension["render_site_ids"],
                "render_sites": extension["render_sites"],
                "resource_version": extension["resource_version"],
            },
            evidence,
        )

    def test_build_extension_provider_wires_real_stage_adapters(self) -> None:
        source = self.root / "source.swf"
        source.write_bytes(b"source")
        transaction = self.root / "real-provider"
        transaction.mkdir()
        ffdec = self.root / "ffdec.jar"
        java = self.root / "java.exe"
        profile = self.root / "profile"
        ffdec.write_bytes(b"ffdec")
        java.write_bytes(b"java")
        accepted = self.accepted_base()
        extension = extension_fixture(self.module, accepted)
        render_module = object()
        resource_module = object()
        runner = object()
        calls = []

        def fake_stage(name, evidence):
            def invoke(**kwargs):
                calls.append(
                    (
                        name,
                        kwargs["source_swf"].name,
                        kwargs.get("render_module"),
                        kwargs.get("resource_module"),
                        kwargs["runner"],
                    )
                )
                output = transaction / f"wired-{name}.swf"
                output.write_bytes(name.encode("ascii"))
                return output, deepcopy(evidence)

            return invoke

        def verify_final(**kwargs):
            calls.append(
                (
                    "verify",
                    kwargs["source_swf"].name,
                    kwargs["render_module"],
                    kwargs["resource_module"],
                    kwargs["runner"],
                )
            )

        with mock.patch.object(
            self.module,
            "_load_extension_modules",
            return_value=(render_module, resource_module),
            create=True,
        ), mock.patch.object(
            self.module,
            "_apply_locked_abyss_stage",
            side_effect=fake_stage("abyss", {}),
            create=True,
        ), mock.patch.object(
            self.module,
            "_apply_locked_seris_stage",
            side_effect=fake_stage("seris", {}),
            create=True,
        ), mock.patch.object(
            self.module,
            "_discover_render_extension_stage",
            side_effect=fake_stage(
                "render",
                {
                    "render_site_ids": extension["render_site_ids"],
                    "render_sites": extension["render_sites"],
                },
            ),
            create=True,
        ), mock.patch.object(
            self.module,
            "_discover_resource_extension_stage",
            side_effect=fake_stage(
                "resource", {"resource_version": extension["resource_version"]}
            ),
            create=True,
        ), mock.patch.object(
            self.module,
            "_verify_extension_cumulative",
            side_effect=verify_final,
            create=True,
        ):
            provider = self.module.build_extension_evidence_provider(
                ffdec=ffdec,
                java=java,
                profile_dir=profile,
                runner=runner,
                timeout=19,
            )
            evidence = provider(
                source_swf=source,
                accepted_lock=accepted,
                transaction_dir=transaction,
            )

        self.assertEqual(
            [
                ("abyss", "source.swf", None, None, runner),
                ("seris", "wired-abyss.swf", None, None, runner),
                ("render", "wired-seris.swf", render_module, None, runner),
                (
                    "resource",
                    "wired-render.swf",
                    None,
                    resource_module,
                    runner,
                ),
                (
                    "verify",
                    "wired-resource.swf",
                    render_module,
                    resource_module,
                    runner,
                ),
            ],
            calls,
        )
        self.assertEqual(
            {
                "render_site_ids": extension["render_site_ids"],
                "render_sites": extension["render_sites"],
                "resource_version": extension["resource_version"],
            },
            evidence,
        )

    def test_render_extension_discovery_derives_each_reopened_hash(self) -> None:
        source = self.root / "post-seris.swf"
        source.write_bytes(b"post-seris")
        transaction = self.root / "render-discovery"
        transaction.mkdir()
        accepted = self.accepted_base()
        patched_by_path = {source.resolve(): frozenset()}
        after_abc = {
            site_id: hashlib.sha256(f"after-{site_id}".encode()).hexdigest()
            for site_id in self.module.RENDER_SITE_IDS
        }
        verify_counts = []

        sites = []
        for site_id in self.module.RENDER_SITE_IDS:
            class_name, method_name, _before_hash = (
                self.module.RENDER_SITE_IDENTITIES[site_id]
            )

            def patch(text, expected=site_id):
                self.assertEqual(f"before-{expected}", text)
                return f"after-{expected}"

            def verify(text, expected=site_id):
                self.assertEqual(f"after-{expected}", text)

            sites.append(
                SimpleNamespace(
                    site_id=site_id,
                    class_name=class_name,
                    method_name=method_name,
                    patch=patch,
                    verify=verify,
                )
            )
        site_by_method = {site.method_name: site for site in sites}

        class FakeIndex:
            def __init__(self, path):
                self.patched = patched_by_path[Path(path).resolve()]

            def require_ref(self, method_name):
                site = site_by_method[method_name]
                raw_hash = (
                    after_abc[site.site_id]
                    if site.site_id in self.patched
                    else self_outer.module.RENDER_SITE_IDENTITIES[site.site_id][2]
                )
                return SimpleNamespace(code=raw_hash.encode(), body_index=17)

        self_outer = self

        def replace_one(current, staged, site, replacement, body_index, **kwargs):
            self.assertEqual(17, body_index)
            self.assertEqual(f"after-{site.site_id}", replacement.read_text())
            staged.write_bytes(current.read_bytes() + site.site_id.encode())
            patched_by_path[staged.resolve()] = (
                patched_by_path[current.resolve()] | {site.site_id}
            )

        def verify_methods(swf, selected, locks, **kwargs):
            verify_counts.append(len(selected))
            self.assertEqual(
                {site.site_id for site in selected},
                set(patched_by_path[Path(swf).resolve()]),
            )
            for site in selected:
                self.assertEqual(
                    after_abc[site.site_id],
                    locks[site.site_id]["after_abc_sha256"],
                )
            return {
                site.site_id: locks[site.site_id]["after_pcode_sha256"]
                for site in selected
            }

        fake_render = SimpleNamespace(
            RENDER_SITES=tuple(sites),
            RenderScaleError=RuntimeError,
            ABC_METHODS=SimpleNamespace(
                index_swf_methods=lambda path: FakeIndex(path)
            ),
            _sha256_abc=lambda code: bytes(code).decode("ascii"),
            _sha256_pcode=lambda text: hashlib.sha256(text.encode()).hexdigest(),
            _export_classes=lambda *args, **kwargs: None,
            _read_exported_method=lambda export_root, site: f"before-{site.site_id}",
            _replace_one=replace_one,
            _verify_methods=verify_methods,
        )
        output, evidence = self.module._discover_render_extension_stage(
            source_swf=source,
            accepted_lock=accepted,
            transaction_dir=transaction,
            render_module=fake_render,
            ffdec=self.root / "ffdec.jar",
            java=self.root / "java.exe",
            profile_dir=self.root / "profile",
            runner=object(),
            timeout=23,
        )

        self.assertEqual([1, 2, 3], verify_counts)
        self.assertEqual(patched_by_path[output.resolve()], set(self.module.RENDER_SITE_IDS))
        self.assertEqual(list(self.module.RENDER_SITE_IDS), evidence["render_site_ids"])
        for site in sites:
            entry = evidence["render_sites"][site.site_id]
            self.assertEqual(site.class_name, entry["class_name"])
            self.assertEqual(site.method_name, entry["method_name"])
            self.assertEqual(
                self.module.RENDER_SITE_IDENTITIES[site.site_id][2],
                entry["before_abc_sha256"],
            )
            self.assertEqual(after_abc[site.site_id], entry["after_abc_sha256"])
            self.assertEqual(
                hashlib.sha256(f"before-{site.site_id}".encode()).hexdigest(),
                entry["before_pcode_sha256"],
            )
            self.assertEqual(
                hashlib.sha256(f"after-{site.site_id}".encode()).hexdigest(),
                entry["after_pcode_sha256"],
            )

    def test_resource_extension_discovery_uses_post_render_raw_hashes(self) -> None:
        source = self.root / "post-render.swf"
        source.write_bytes(b"post-render")
        transaction = self.root / "resource-discovery"
        transaction.mkdir()
        accepted = self.accepted_base()
        before_abc = accepted["offline_method_sha256"][
            "boot_ffc6#$script364/$init"
        ]
        dummy_abc = accepted["offline_method_sha256"][
            "DummyRemote/debugUnlinkTwitter"
        ]
        after_abc = hashlib.sha256(b"resource-after").hexdigest()
        staged_paths = set()
        reopened = []

        def method_refs(path):
            resource_hash = after_abc if Path(path).resolve() in staged_paths else before_abc
            return (
                SimpleNamespace(code=resource_hash.encode(), body_index=29),
                SimpleNamespace(code=dummy_abc.encode()),
            )

        def replace_one(current, staged, replacement, body_index, **kwargs):
            self.assertEqual(29, body_index)
            self.assertEqual("resource-after", replacement.read_text())
            staged.write_bytes(current.read_bytes() + b"resource")
            staged_paths.add(staged.resolve())

        def verify_reopened(swf, entry, dummy_hash, **kwargs):
            reopened.append((Path(swf), dict(entry), dummy_hash))

        fake_resource = SimpleNamespace(
            RESOURCE_SITE_ID="full-resource-version",
            RESOURCE_CLASS="pinball.config.core.DevConfig",
            RESOURCE_METHOD="boot_ffc6#$script364/$init",
            SOURCE_VERSION="1.4.54",
            TARGET_VERSION="1.4.196",
            ResourceVersionError=RuntimeError,
            _method_refs=method_refs,
            _sha256_abc=lambda code: bytes(code).decode("ascii"),
            _export_resource_class=lambda *args, **kwargs: None,
            _read_exported_resource=lambda export_root: "resource-before",
            _sha256_pcode=lambda text: hashlib.sha256(text.encode()).hexdigest(),
            patch_resource_version=lambda text: "resource-after",
            _replace_one=replace_one,
            _verify_reopened_swf=verify_reopened,
        )
        output, evidence = self.module._discover_resource_extension_stage(
            source_swf=source,
            accepted_lock=accepted,
            transaction_dir=transaction,
            resource_module=fake_resource,
            ffdec=self.root / "ffdec.jar",
            java=self.root / "java.exe",
            profile_dir=self.root / "profile",
            runner=object(),
            timeout=31,
        )

        entry = evidence["resource_version"]
        self.assertEqual(output.resolve(), reopened[0][0].resolve())
        self.assertEqual(dummy_abc, reopened[0][2])
        self.assertEqual(before_abc, entry["before_abc_sha256"])
        self.assertEqual(after_abc, entry["after_abc_sha256"])
        self.assertEqual(
            hashlib.sha256(b"resource-before").hexdigest(),
            entry["before_pcode_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(b"resource-after").hexdigest(),
            entry["after_pcode_sha256"],
        )

    def test_accept_extension_cas_replaces_exact_old_with_exact_candidate(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        self.accepted_path.write_bytes(old_raw)
        self.candidate_path.write_bytes(candidate_raw)
        accepted = self.module.accept_extension_candidate(
            self.candidate_path,
            self.accepted_path,
            confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
            expected_old_lock_sha256=hashlib.sha256(old_raw).hexdigest(),
            expected_candidate_sha256=hashlib.sha256(candidate_raw).hexdigest(),
        )
        self.assertEqual(candidate, accepted)
        self.assertEqual(candidate_raw, self.accepted_path.read_bytes())
        self.assertEqual(candidate_raw, self.candidate_path.read_bytes())
        self.assertEqual([], list(self.root.glob(".base-lock.json.*.cas-old")))
        self.assertEqual([], list(self.root.glob(".base-lock.json.*.tmp")))

    def test_accept_extension_publish_post_rename_interrupt_never_deletes_candidate(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        self.accepted_path.write_bytes(old_raw)
        self.candidate_path.write_bytes(candidate_raw)
        original_rename = (
            self.module.SERIS.PUBLISH_TOOLS._rename_staging_handle_no_replace
        )
        renamed_owners = []
        rename_count = 0

        def interrupt_after_candidate_rename(owned, destination):
            nonlocal rename_count
            rename_count += 1
            original_rename(owned, destination)
            if rename_count == 2:
                renamed_owners.append(owned)
                raise KeyboardInterrupt("cancel after candidate handle rename")

        with mock.patch.object(
            self.module.SERIS.PUBLISH_TOOLS,
            "_rename_staging_handle_no_replace",
            side_effect=interrupt_after_candidate_rename,
        ):
            with self.assertRaises(KeyboardInterrupt):
                self.module.accept_extension_candidate(
                    self.candidate_path,
                    self.accepted_path,
                    confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                    expected_old_lock_sha256=hashlib.sha256(old_raw).hexdigest(),
                    expected_candidate_sha256=hashlib.sha256(
                        candidate_raw
                    ).hexdigest(),
                )

        self.assertEqual(2, rename_count)
        self.assertTrue(
            self.accepted_path.is_file(),
            "post-rename interrupt removed the published candidate",
        )
        self.assertEqual(candidate_raw, self.accepted_path.read_bytes())
        recoveries = list(self.root.glob(".base-lock.json.*.cas-old"))
        self.assertEqual(1, len(recoveries))
        self.assertEqual(old_raw, recoveries[0].read_bytes())
        self.assertEqual(1, len(renamed_owners))
        self.assertTrue(renamed_owners[0].handle.closed)
        self.assertEqual([], list(self.root.glob(".base-lock.json.*.tmp")))

    def test_accept_extension_freeze_rejects_post_publish_rewrite_or_replacement(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        original_open = self.module._open_existing_for_cas
        for mode in ("rewrite", "replace"):
            with self.subTest(mode=mode):
                case_root = self.root / f"post-publish-{mode}"
                case_root.mkdir()
                accepted_path = case_root / "base-lock.json"
                candidate_path = case_root / "candidate.json"
                accepted_path.write_bytes(old_raw)
                candidate_path.write_bytes(candidate_raw)
                external_raw = f"external-{mode}\n".encode("ascii")
                opened = []
                open_count = 0

                def mutate_then_open(path):
                    nonlocal open_count
                    open_count += 1
                    target = Path(path)
                    if open_count == 2:
                        if mode == "rewrite":
                            target.write_bytes(external_raw)
                        else:
                            replacement = case_root / "external.json"
                            replacement.write_bytes(external_raw)
                            os.replace(replacement, target)
                    owned = original_open(target)
                    opened.append(owned)
                    return owned

                with mock.patch.object(
                    self.module,
                    "_open_existing_for_cas",
                    side_effect=mutate_then_open,
                ):
                    with self.assertRaises(self.module.LockDiscoveryError):
                        self.module.accept_extension_candidate(
                            candidate_path,
                            accepted_path,
                            confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                            expected_old_lock_sha256=hashlib.sha256(
                                old_raw
                            ).hexdigest(),
                            expected_candidate_sha256=hashlib.sha256(
                                candidate_raw
                            ).hexdigest(),
                        )

                self.assertEqual(2, open_count)
                self.assertEqual(external_raw, accepted_path.read_bytes())
                recoveries = list(case_root.glob(".base-lock.json.*.cas-old"))
                self.assertEqual(1, len(recoveries))
                self.assertEqual(old_raw, recoveries[0].read_bytes())
                self.assertTrue(opened)
                self.assertTrue(all(owned.handle.closed for owned in opened))
                self.assertEqual([], list(case_root.glob(".base-lock.json.*.tmp")))

    def test_accept_extension_freeze_boundary_interrupts_preserve_candidate_and_old(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        original_open = self.module._open_existing_for_cas
        original_read = self.module._read_owned_existing
        for boundary in ("before-freeze", "after-freeze"):
            with self.subTest(boundary=boundary):
                case_root = self.root / boundary
                case_root.mkdir()
                accepted_path = case_root / "base-lock.json"
                candidate_path = case_root / "candidate.json"
                accepted_path.write_bytes(old_raw)
                candidate_path.write_bytes(candidate_raw)
                opened = []
                open_count = 0
                read_count = 0

                def interrupt_freeze_open(path):
                    nonlocal open_count
                    open_count += 1
                    if boundary == "before-freeze" and open_count == 2:
                        raise KeyboardInterrupt("cancel before candidate freeze")
                    owned = original_open(path)
                    opened.append(owned)
                    return owned

                def interrupt_frozen_read(owned):
                    nonlocal read_count
                    read_count += 1
                    raw = original_read(owned)
                    if boundary == "after-freeze" and read_count == 3:
                        raise KeyboardInterrupt("cancel after candidate freeze")
                    return raw

                with mock.patch.object(
                    self.module,
                    "_open_existing_for_cas",
                    side_effect=interrupt_freeze_open,
                ), mock.patch.object(
                    self.module,
                    "_read_owned_existing",
                    side_effect=interrupt_frozen_read,
                ):
                    with self.assertRaises(KeyboardInterrupt):
                        self.module.accept_extension_candidate(
                            candidate_path,
                            accepted_path,
                            confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                            expected_old_lock_sha256=hashlib.sha256(
                                old_raw
                            ).hexdigest(),
                            expected_candidate_sha256=hashlib.sha256(
                                candidate_raw
                            ).hexdigest(),
                        )

                self.assertEqual(candidate_raw, accepted_path.read_bytes())
                recoveries = list(case_root.glob(".base-lock.json.*.cas-old"))
                self.assertEqual(1, len(recoveries))
                self.assertEqual(old_raw, recoveries[0].read_bytes())
                self.assertTrue(opened)
                self.assertTrue(all(owned.handle.closed for owned in opened))
                self.assertEqual([], list(case_root.glob(".base-lock.json.*.tmp")))

    def test_accept_extension_frozen_candidate_digest_mismatch_preserves_old_recovery(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        self.accepted_path.write_bytes(old_raw)
        self.candidate_path.write_bytes(candidate_raw)
        original_open = self.module._open_existing_for_cas
        original_read = self.module._read_owned_existing
        opened = []
        read_count = 0

        def track_open(path):
            owned = original_open(path)
            opened.append(owned)
            return owned

        def mismatch_frozen_digest(owned):
            nonlocal read_count
            read_count += 1
            raw = original_read(owned)
            if read_count == 3:
                return b"not-the-reviewed-candidate\n"
            return raw

        with mock.patch.object(
            self.module,
            "_open_existing_for_cas",
            side_effect=track_open,
        ), mock.patch.object(
            self.module,
            "_read_owned_existing",
            side_effect=mismatch_frozen_digest,
        ):
            with self.assertRaises(self.module.LockDiscoveryError):
                self.module.accept_extension_candidate(
                    self.candidate_path,
                    self.accepted_path,
                    confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                    expected_old_lock_sha256=hashlib.sha256(old_raw).hexdigest(),
                    expected_candidate_sha256=hashlib.sha256(
                        candidate_raw
                    ).hexdigest(),
                )

        self.assertEqual(candidate_raw, self.accepted_path.read_bytes())
        recoveries = list(self.root.glob(".base-lock.json.*.cas-old"))
        self.assertEqual(1, len(recoveries))
        self.assertEqual(old_raw, recoveries[0].read_bytes())
        self.assertEqual(2, len(opened))
        self.assertTrue(all(owned.handle.closed for owned in opened))

    def test_accept_extension_frozen_candidate_denies_write_and_delete_during_old_cleanup(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        self.accepted_path.write_bytes(old_raw)
        self.candidate_path.write_bytes(candidate_raw)
        original_delete = self.module._delete_retired_existing
        blocked = {"write": False, "delete": False}

        def attack_candidate_then_delete_old(retired):
            try:
                self.accepted_path.write_bytes(b"external-write\n")
            except OSError:
                blocked["write"] = True
            else:
                self.accepted_path.write_bytes(candidate_raw)
            try:
                self.accepted_path.unlink()
            except OSError:
                blocked["delete"] = True
            else:
                self.accepted_path.write_bytes(candidate_raw)
            return original_delete(retired)

        with mock.patch.object(
            self.module,
            "_delete_retired_existing",
            side_effect=attack_candidate_then_delete_old,
        ):
            accepted = self.module.accept_extension_candidate(
                self.candidate_path,
                self.accepted_path,
                confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                expected_old_lock_sha256=hashlib.sha256(old_raw).hexdigest(),
                expected_candidate_sha256=hashlib.sha256(candidate_raw).hexdigest(),
            )

        self.assertEqual(candidate, accepted)
        self.assertEqual({"write": True, "delete": True}, blocked)
        self.assertEqual(candidate_raw, self.accepted_path.read_bytes())
        self.assertEqual([], list(self.root.glob(".base-lock.json.*.cas-old")))
        self.assertEqual([], list(self.root.glob(".base-lock.json.*.tmp")))

    def test_accept_extension_old_cleanup_interrupt_boundaries_close_frozen_candidate(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        original_open = self.module._open_existing_for_cas
        original_delete = self.module._delete_retired_existing
        for boundary in ("before-cleanup", "after-cleanup"):
            with self.subTest(boundary=boundary):
                case_root = self.root / boundary
                case_root.mkdir()
                accepted_path = case_root / "base-lock.json"
                candidate_path = case_root / "candidate.json"
                accepted_path.write_bytes(old_raw)
                candidate_path.write_bytes(candidate_raw)
                opened = []

                def track_open(path):
                    owned = original_open(path)
                    opened.append(owned)
                    return owned

                def interrupt_cleanup(retired):
                    if boundary == "after-cleanup":
                        original_delete(retired)
                    raise KeyboardInterrupt(f"cancel {boundary}")

                with mock.patch.object(
                    self.module,
                    "_open_existing_for_cas",
                    side_effect=track_open,
                ), mock.patch.object(
                    self.module,
                    "_delete_retired_existing",
                    side_effect=interrupt_cleanup,
                ):
                    with self.assertRaises(KeyboardInterrupt):
                        self.module.accept_extension_candidate(
                            candidate_path,
                            accepted_path,
                            confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                            expected_old_lock_sha256=hashlib.sha256(
                                old_raw
                            ).hexdigest(),
                            expected_candidate_sha256=hashlib.sha256(
                                candidate_raw
                            ).hexdigest(),
                        )

                self.assertEqual(candidate_raw, accepted_path.read_bytes())
                recoveries = list(case_root.glob(".base-lock.json.*.cas-old"))
                if boundary == "before-cleanup":
                    self.assertEqual(1, len(recoveries))
                    self.assertEqual(old_raw, recoveries[0].read_bytes())
                else:
                    self.assertEqual([], recoveries)
                self.assertEqual(2, len(opened))
                self.assertTrue(all(owned.handle.closed for owned in opened))
                self.assertEqual([], list(case_root.glob(".base-lock.json.*.tmp")))

    def test_accept_extension_closes_frozen_handle_when_identity_check_fails(self) -> None:
        fake_handle = mock.Mock()
        fake_handle.fileno.return_value = 91
        kernel32 = SimpleNamespace(
            CreateFileW=mock.Mock(return_value=12345),
            CloseHandle=mock.Mock(),
        )
        fake_ctypes = SimpleNamespace(
            c_void_p=lambda value: SimpleNamespace(value=value),
            get_last_error=lambda: 0,
        )
        with mock.patch.object(
            self.module.SERIS.PUBLISH_TOOLS,
            "_windows_file_api",
            return_value=(fake_ctypes, object(), kernel32),
        ), mock.patch(
            "msvcrt.open_osfhandle", return_value=91
        ), mock.patch.object(
            self.module.os, "fdopen", return_value=fake_handle
        ), mock.patch.object(
            self.module.os, "fstat", return_value=SimpleNamespace()
        ), mock.patch.object(
            self.module.SERIS.PUBLISH_TOOLS,
            "_identity_from_stat",
            return_value=object(),
        ), mock.patch.object(
            self.module.SERIS.PUBLISH_TOOLS,
            "_require_file_identity",
            side_effect=self.module.SERIS.PUBLISH_TOOLS.BuildError("race"),
        ):
            with self.assertRaises(self.module.LockDiscoveryError):
                self.module._open_existing_for_cas(self.accepted_path)
        fake_handle.close.assert_called_once_with()

    def test_accept_extension_wrong_digest_or_old_projection_never_mutates_old(self) -> None:
        base = self.accepted_base()
        old_raw = self.module._canonical_json_bytes(base)
        self.accepted_path.write_bytes(old_raw)
        candidate = extension_fixture(self.module, base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        self.candidate_path.write_bytes(candidate_raw)
        cases = (
            ("0" * 64, hashlib.sha256(candidate_raw).hexdigest()),
            (hashlib.sha256(old_raw).hexdigest(), "0" * 64),
        )
        for old_digest, candidate_digest in cases:
            with self.subTest(old_digest=old_digest[:1], candidate_digest=candidate_digest[:1]):
                with self.assertRaises(self.module.LockDiscoveryError):
                    self.module.accept_extension_candidate(
                        self.candidate_path,
                        self.accepted_path,
                        confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                        expected_old_lock_sha256=old_digest,
                        expected_candidate_sha256=candidate_digest,
                    )
                self.assertEqual(old_raw, self.accepted_path.read_bytes())

        changed = extension_fixture(self.module, base)
        changed["site_count"] = 12
        changed_raw = self.module._canonical_json_bytes(changed)
        self.candidate_path.write_bytes(changed_raw)
        with self.assertRaises(self.module.LockDiscoveryError):
            self.module.accept_extension_candidate(
                self.candidate_path,
                self.accepted_path,
                confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                expected_old_lock_sha256=hashlib.sha256(old_raw).hexdigest(),
                expected_candidate_sha256=hashlib.sha256(changed_raw).hexdigest(),
            )
        self.assertEqual(old_raw, self.accepted_path.read_bytes())

    def test_accept_extension_external_race_preserves_external_and_old_recovery(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        self.accepted_path.write_bytes(old_raw)
        self.candidate_path.write_bytes(candidate_raw)
        original_publish = self.module._publish_candidate_owner_no_replace

        def external_then_publish(staging, destination):
            Path(destination).write_bytes(b"external-lock")
            original_publish(staging, destination)

        with mock.patch.object(
            self.module,
            "_publish_candidate_owner_no_replace",
            side_effect=external_then_publish,
        ):
            with self.assertRaises(self.module.LockDiscoveryError):
                self.module.accept_extension_candidate(
                    self.candidate_path,
                    self.accepted_path,
                    confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                    expected_old_lock_sha256=hashlib.sha256(old_raw).hexdigest(),
                    expected_candidate_sha256=hashlib.sha256(candidate_raw).hexdigest(),
                )
        self.assertEqual(b"external-lock", self.accepted_path.read_bytes())
        recoveries = list(self.root.glob(".base-lock.json.*.cas-old"))
        self.assertEqual(1, len(recoveries))
        self.assertEqual(old_raw, recoveries[0].read_bytes())

    def test_accept_extension_interrupt_after_retire_restores_exact_old(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        self.accepted_path.write_bytes(old_raw)
        self.candidate_path.write_bytes(candidate_raw)
        with mock.patch.object(
            self.module,
            "_publish_candidate_owner_no_replace",
            side_effect=KeyboardInterrupt("cancel after retire"),
        ):
            with self.assertRaises(KeyboardInterrupt):
                self.module.accept_extension_candidate(
                    self.candidate_path,
                    self.accepted_path,
                    confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                    expected_old_lock_sha256=hashlib.sha256(old_raw).hexdigest(),
                    expected_candidate_sha256=hashlib.sha256(candidate_raw).hexdigest(),
                )
        self.assertEqual(old_raw, self.accepted_path.read_bytes())
        self.assertEqual([], list(self.root.glob(".base-lock.json.*.cas-old")))

    def test_accept_extension_retire_post_rename_failure_restores_exact_old(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        original_require = (
            self.module.SERIS.PUBLISH_TOOLS._require_file_identity
        )
        failures = (
            (
                "identity",
                self.module.SERIS.PUBLISH_TOOLS.BuildError(
                    "retired identity fault"
                ),
                self.module.LockDiscoveryError,
            ),
            ("interrupt", KeyboardInterrupt("retired interrupt"), KeyboardInterrupt),
        )
        for name, failure, expected_error in failures:
            with self.subTest(name=name):
                case_root = self.root / name
                case_root.mkdir()
                accepted_path = case_root / "base-lock.json"
                candidate_path = case_root / "candidate.json"
                accepted_path.write_bytes(old_raw)
                candidate_path.write_bytes(candidate_raw)
                injected = False

                def fail_after_retire(path, identity, label):
                    nonlocal injected
                    if label == "retired accepted lock" and not injected:
                        injected = True
                        raise failure
                    return original_require(path, identity, label)

                with mock.patch.object(
                    self.module.SERIS.PUBLISH_TOOLS,
                    "_require_file_identity",
                    side_effect=fail_after_retire,
                ):
                    with self.assertRaises(expected_error):
                        self.module.accept_extension_candidate(
                            candidate_path,
                            accepted_path,
                            confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                            expected_old_lock_sha256=hashlib.sha256(
                                old_raw
                            ).hexdigest(),
                            expected_candidate_sha256=hashlib.sha256(
                                candidate_raw
                            ).hexdigest(),
                        )
                self.assertTrue(injected)
                self.assertEqual(old_raw, accepted_path.read_bytes())
                self.assertEqual(
                    [], list(case_root.glob(".base-lock.json.*.cas-old"))
                )

    def test_accept_extension_restore_race_closes_and_reports_live_recovery(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        self.accepted_path.write_bytes(old_raw)
        self.candidate_path.write_bytes(candidate_raw)
        original_restore = self.module._restore_retired_no_replace
        original_close = self.module._close_owned_existing

        def race_restore(retired, destination):
            Path(destination).write_bytes(b"external-race")
            return original_restore(retired, destination)

        with mock.patch.object(
            self.module,
            "_publish_candidate_owner_no_replace",
            side_effect=self.module.LockDiscoveryError("publish fault"),
        ), mock.patch.object(
            self.module,
            "_restore_retired_no_replace",
            side_effect=race_restore,
        ), mock.patch.object(
            self.module,
            "_close_owned_existing",
            wraps=original_close,
        ) as close_owned:
            with self.assertRaises(self.module.LockDiscoveryError) as raised:
                self.module.accept_extension_candidate(
                    self.candidate_path,
                    self.accepted_path,
                    confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                    expected_old_lock_sha256=hashlib.sha256(old_raw).hexdigest(),
                    expected_candidate_sha256=hashlib.sha256(
                        candidate_raw
                    ).hexdigest(),
                )
        self.assertEqual(b"external-race", self.accepted_path.read_bytes())
        recoveries = list(self.root.glob(".base-lock.json.*.cas-old"))
        self.assertEqual(1, len(recoveries))
        self.assertEqual(old_raw, recoveries[0].read_bytes())
        self.assertTrue(
            any(
                Path(call.args[0].path) == recoveries[0]
                for call in close_owned.call_args_list
            )
        )
        notes = getattr(raised.exception, "__notes__", ())
        self.assertTrue(any(str(recoveries[0]) in note for note in notes))

    def test_accept_extension_restore_identity_failure_reports_destination(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        self.accepted_path.write_bytes(old_raw)
        self.candidate_path.write_bytes(candidate_raw)
        original_require = (
            self.module.SERIS.PUBLISH_TOOLS._require_file_identity
        )
        original_close = self.module._close_owned_existing
        injected = False

        def fail_after_restore(path, identity, label):
            nonlocal injected
            if label == "restored accepted lock" and not injected:
                injected = True
                raise self.module.SERIS.PUBLISH_TOOLS.BuildError(
                    "restored identity fault"
                )
            return original_require(path, identity, label)

        with mock.patch.object(
            self.module,
            "_publish_candidate_owner_no_replace",
            side_effect=self.module.LockDiscoveryError("publish fault"),
        ), mock.patch.object(
            self.module.SERIS.PUBLISH_TOOLS,
            "_require_file_identity",
            side_effect=fail_after_restore,
        ), mock.patch.object(
            self.module,
            "_close_owned_existing",
            wraps=original_close,
        ) as close_owned:
            with self.assertRaises(self.module.LockDiscoveryError) as raised:
                self.module.accept_extension_candidate(
                    self.candidate_path,
                    self.accepted_path,
                    confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                    expected_old_lock_sha256=hashlib.sha256(old_raw).hexdigest(),
                    expected_candidate_sha256=hashlib.sha256(
                        candidate_raw
                    ).hexdigest(),
                )
        self.assertTrue(injected)
        self.assertEqual(old_raw, self.accepted_path.read_bytes())
        self.assertEqual([], list(self.root.glob(".base-lock.json.*.cas-old")))
        self.assertTrue(
            any(
                Path(call.args[0].path) == self.accepted_path
                for call in close_owned.call_args_list
            )
        )
        notes = getattr(raised.exception, "__notes__", ())
        self.assertFalse(any(".cas-old" in note for note in notes))
        self.assertTrue(any(str(self.accepted_path) in note for note in notes))

    def test_accept_extension_post_commit_cleanup_failure_keeps_candidate(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        self.accepted_path.write_bytes(old_raw)
        self.candidate_path.write_bytes(candidate_raw)
        original_close = self.module._close_owned_existing
        with mock.patch.object(
            self.module,
            "_delete_retired_existing",
            side_effect=self.module.LockDiscoveryError("cleanup fault"),
        ), mock.patch.object(
            self.module,
            "_restore_retired_no_replace",
        ) as restore, mock.patch.object(
            self.module,
            "_close_owned_existing",
            wraps=original_close,
        ) as close_owned:
            with self.assertRaises(self.module.LockDiscoveryError) as raised:
                self.module.accept_extension_candidate(
                    self.candidate_path,
                    self.accepted_path,
                    confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                    expected_old_lock_sha256=hashlib.sha256(old_raw).hexdigest(),
                    expected_candidate_sha256=hashlib.sha256(
                        candidate_raw
                    ).hexdigest(),
                )
        restore.assert_not_called()
        self.assertEqual(candidate_raw, self.accepted_path.read_bytes())
        recoveries = list(self.root.glob(".base-lock.json.*.cas-old"))
        self.assertEqual(1, len(recoveries))
        self.assertEqual(old_raw, recoveries[0].read_bytes())
        self.assertTrue(
            any(
                Path(call.args[0].path) == recoveries[0]
                for call in close_owned.call_args_list
            )
        )
        notes = getattr(raised.exception, "__notes__", ())
        self.assertTrue(any(str(recoveries[0]) in note for note in notes))

    def test_accept_extension_post_commit_errors_always_report_retained_digest(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        candidate_digest = hashlib.sha256(candidate_raw).hexdigest()
        original_read = self.module._read_owned_existing
        original_close = self.module._close_owned_existing
        original_delete = self.module._delete_retired_existing

        for boundary in ("cleanup-after", "final-read", "final-close"):
            with self.subTest(boundary=boundary):
                case_root = self.root / f"commit-report-{boundary}"
                case_root.mkdir()
                accepted_path = case_root / "base-lock.json"
                candidate_path = case_root / "candidate.json"
                accepted_path.write_bytes(old_raw)
                candidate_path.write_bytes(candidate_raw)
                read_count = 0
                close_count = 0

                def fail_read(owned):
                    nonlocal read_count
                    read_count += 1
                    raw = original_read(owned)
                    if boundary == "final-read" and read_count == 4:
                        raise self.module.LockDiscoveryError("final read fault")
                    return raw

                def fail_close(owned):
                    nonlocal close_count
                    close_count += 1
                    original_close(owned)
                    if boundary == "final-close" and close_count == 2:
                        raise KeyboardInterrupt("final close interrupt")

                def fail_cleanup_after(retired):
                    original_delete(retired)
                    if boundary == "cleanup-after":
                        raise KeyboardInterrupt("cleanup-after interrupt")

                with mock.patch.object(
                    self.module,
                    "_read_owned_existing",
                    side_effect=fail_read,
                ), mock.patch.object(
                    self.module,
                    "_close_owned_existing",
                    side_effect=fail_close,
                ), mock.patch.object(
                    self.module,
                    "_delete_retired_existing",
                    side_effect=fail_cleanup_after,
                ):
                    with self.assertRaises(BaseException) as raised:
                        self.module.accept_extension_candidate(
                            candidate_path,
                            accepted_path,
                            confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                            expected_old_lock_sha256=hashlib.sha256(
                                old_raw
                            ).hexdigest(),
                            expected_candidate_sha256=candidate_digest,
                        )

                self.assertEqual(candidate_raw, accepted_path.read_bytes())
                self.assertEqual(
                    [], list(case_root.glob(".base-lock.json.*.cas-old"))
                )
                notes = getattr(raised.exception, "__notes__", ())
                retained = [
                    note for note in notes if "candidate commit is retained" in note
                ]
                self.assertEqual(1, len(retained), notes)
                self.assertIn(str(accepted_path), retained[0])
                self.assertIn(candidate_digest, retained[0])

    def test_open_existing_for_cas_closes_descriptor_when_fdopen_fails(self) -> None:
        kernel32 = SimpleNamespace(
            CreateFileW=mock.Mock(return_value=12345),
            CloseHandle=mock.Mock(),
        )
        fake_ctypes = SimpleNamespace(
            c_void_p=lambda value: SimpleNamespace(value=value),
            get_last_error=lambda: 0,
        )
        with mock.patch.object(
            self.module.SERIS.PUBLISH_TOOLS,
            "_windows_file_api",
            return_value=(fake_ctypes, object(), kernel32),
        ), mock.patch(
            "msvcrt.open_osfhandle", return_value=91
        ), mock.patch.object(
            self.module.os,
            "fdopen",
            side_effect=OSError("fdopen fault"),
        ), mock.patch.object(
            self.module.os,
            "close",
        ) as close_descriptor:
            with self.assertRaises(self.module.LockDiscoveryError):
                self.module._open_existing_for_cas(self.accepted_path)

        close_descriptor.assert_called_once_with(91)
        kernel32.CloseHandle.assert_not_called()

    def test_accept_extension_candidate_publication_zero_or_two_matches_preserves_files(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        original_identity = self.module.SERIS.PUBLISH_TOOLS._file_identity
        original_publish = self.module._publish_candidate_owner_no_replace
        original_open = self.module._open_existing_for_cas

        for match_count in (0, 2):
            with self.subTest(match_count=match_count):
                case_root = self.root / f"candidate-pending-{match_count}"
                case_root.mkdir()
                accepted_path = case_root / "base-lock.json"
                candidate_path = case_root / "candidate.json"
                accepted_path.write_bytes(old_raw)
                candidate_path.write_bytes(candidate_raw)
                candidate_owners = []
                old_owners = []
                pending_temporary = None
                external_temporary_raw = b"external candidate-temp competitor\n"

                def track_open(path):
                    owned = original_open(path)
                    old_owners.append(owned)
                    return owned

                def capture_publish(owned, destination):
                    candidate_owners.append(owned)
                    return original_publish(owned, destination)

                def force_candidate_match_count(path, label, missing_ok=False):
                    nonlocal pending_temporary
                    if label == "candidate publication path":
                        target = Path(path)
                        if pending_temporary is None and not target.exists():
                            pending_temporary = target
                            if match_count == 0:
                                target.write_bytes(external_temporary_raw)
                            else:
                                os.link(accepted_path, target)
                        if match_count == 0:
                            return None
                        return original_identity(
                            target, label, missing_ok=missing_ok
                        )
                    return original_identity(path, label, missing_ok=missing_ok)

                with mock.patch.object(
                    self.module,
                    "_open_existing_for_cas",
                    side_effect=track_open,
                ), mock.patch.object(
                    self.module,
                    "_publish_candidate_owner_no_replace",
                    side_effect=capture_publish,
                ), mock.patch.object(
                    self.module.SERIS.PUBLISH_TOOLS,
                    "_file_identity",
                    side_effect=force_candidate_match_count,
                ):
                    with self.assertRaises(self.module.LockDiscoveryError) as raised:
                        self.module.accept_extension_candidate(
                            candidate_path,
                            accepted_path,
                            confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                            expected_old_lock_sha256=hashlib.sha256(
                                old_raw
                            ).hexdigest(),
                            expected_candidate_sha256=hashlib.sha256(
                                candidate_raw
                            ).hexdigest(),
                        )

                self.assertEqual(candidate_raw, accepted_path.read_bytes())
                recoveries = list(case_root.glob(".base-lock.json.*.cas-old"))
                self.assertEqual(1, len(recoveries))
                self.assertEqual(old_raw, recoveries[0].read_bytes())
                temporary_files = list(case_root.glob(".base-lock.json.*.tmp"))
                self.assertEqual(1, len(temporary_files))
                self.assertEqual(pending_temporary, temporary_files[0])
                self.assertEqual(
                    external_temporary_raw if match_count == 0 else candidate_raw,
                    temporary_files[0].read_bytes(),
                )
                self.assertEqual(1, len(candidate_owners))
                self.assertTrue(candidate_owners[0].handle.closed)
                self.assertEqual(1, len(old_owners))
                self.assertTrue(old_owners[0].handle.closed)
                notes = getattr(raised.exception, "__notes__", ())
                self.assertTrue(
                    any("existing pending paths=" in note for note in notes), notes
                )

    def test_accept_extension_reconciles_actual_path_on_pre_rename_interrupt(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        original_rename = (
            self.module.SERIS.PUBLISH_TOOLS._rename_staging_handle_no_replace
        )
        original_close = self.module._close_owned_existing
        cases = (
            ("retire", 1, KeyboardInterrupt),
            ("restore", 2, self.module.LockDiscoveryError),
        )
        for name, interrupt_on, expected_error in cases:
            with self.subTest(name=name):
                case_root = self.root / f"pre-rename-{name}"
                case_root.mkdir()
                accepted_path = case_root / "base-lock.json"
                candidate_path = case_root / "candidate.json"
                accepted_path.write_bytes(old_raw)
                candidate_path.write_bytes(candidate_raw)
                rename_count = 0

                def interrupt_before_rename(owned, destination):
                    nonlocal rename_count
                    rename_count += 1
                    if rename_count == interrupt_on:
                        raise KeyboardInterrupt(
                            f"interrupt before {name} handle rename"
                        )
                    return original_rename(owned, destination)

                with mock.patch.object(
                    self.module.SERIS.PUBLISH_TOOLS,
                    "_rename_staging_handle_no_replace",
                    side_effect=interrupt_before_rename,
                ), mock.patch.object(
                    self.module,
                    "_publish_candidate_owner_no_replace",
                    side_effect=self.module.LockDiscoveryError("publish fault"),
                ), mock.patch.object(
                    self.module,
                    "_close_owned_existing",
                    wraps=original_close,
                ) as close_owned:
                    with self.assertRaises(expected_error) as raised:
                        self.module.accept_extension_candidate(
                            candidate_path,
                            accepted_path,
                            confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                            expected_old_lock_sha256=hashlib.sha256(
                                old_raw
                            ).hexdigest(),
                            expected_candidate_sha256=hashlib.sha256(
                                candidate_raw
                            ).hexdigest(),
                        )

                recoveries = list(
                    case_root.glob(".base-lock.json.*.cas-old")
                )
                notes = getattr(raised.exception, "__notes__", ())
                if name == "retire":
                    self.assertEqual(old_raw, accepted_path.read_bytes())
                    self.assertEqual([], recoveries)
                    self.assertTrue(
                        any(
                            Path(call.args[0].path) == accepted_path
                            for call in close_owned.call_args_list
                        )
                    )
                    self.assertFalse(any(".cas-old" in note for note in notes))
                else:
                    self.assertFalse(accepted_path.exists())
                    self.assertEqual(1, len(recoveries))
                    self.assertEqual(old_raw, recoveries[0].read_bytes())
                    self.assertTrue(
                        any(
                            Path(call.args[0].path) == recoveries[0]
                            for call in close_owned.call_args_list
                        )
                    )
                    self.assertTrue(
                        any(str(recoveries[0]) in note for note in notes)
                    )

    def test_accept_extension_retries_pending_paths_after_probe_failure(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        original_identity = self.module.SERIS.PUBLISH_TOOLS._file_identity
        original_close = self.module._close_owned_existing
        cases = (
            ("interrupt", "interrupt", KeyboardInterrupt),
            ("build-error", "build-error", self.module.LockDiscoveryError),
            ("zero-matches", "zero", self.module.LockDiscoveryError),
            ("two-matches", "two", self.module.LockDiscoveryError),
        )
        for name, fault, expected_error in cases:
            with self.subTest(name=name):
                case_root = self.root / f"probe-{name}"
                case_root.mkdir()
                accepted_path = case_root / "base-lock.json"
                candidate_path = case_root / "candidate.json"
                accepted_path.write_bytes(old_raw)
                candidate_path.write_bytes(candidate_raw)
                old_identity = original_identity(
                    accepted_path,
                    "probe fixture",
                )
                probe_calls = 0

                def fail_first_reconcile(path, label, missing_ok=False):
                    nonlocal probe_calls
                    if label == "accepted-lock retirement path":
                        probe_calls += 1
                        if fault == "interrupt" and probe_calls == 1:
                            raise KeyboardInterrupt("retirement probe interrupt")
                        if fault == "build-error" and probe_calls == 1:
                            raise self.module.SERIS.PUBLISH_TOOLS.BuildError(
                                "retirement probe failure"
                            )
                        if fault == "zero" and probe_calls <= 2:
                            return None
                        if fault == "two" and probe_calls <= 2:
                            return old_identity
                    return original_identity(
                        path,
                        label,
                        missing_ok=missing_ok,
                    )

                with mock.patch.object(
                    self.module.SERIS.PUBLISH_TOOLS,
                    "_file_identity",
                    side_effect=fail_first_reconcile,
                ), mock.patch.object(
                    self.module,
                    "_close_owned_existing",
                    wraps=original_close,
                ) as close_owned:
                    with self.assertRaises(expected_error):
                        self.module.accept_extension_candidate(
                            candidate_path,
                            accepted_path,
                            confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                            expected_old_lock_sha256=hashlib.sha256(
                                old_raw
                            ).hexdigest(),
                            expected_candidate_sha256=hashlib.sha256(
                                candidate_raw
                            ).hexdigest(),
                        )

                self.assertGreaterEqual(probe_calls, 2)
                self.assertEqual(old_raw, accepted_path.read_bytes())
                self.assertEqual(
                    [], list(case_root.glob(".base-lock.json.*.cas-old"))
                )
                self.assertTrue(
                    any(
                        Path(call.args[0].path) == accepted_path
                        for call in close_owned.call_args_list
                    )
                )

    def test_accept_extension_settles_restore_pending_after_probe_failure(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        original_identity = self.module.SERIS.PUBLISH_TOOLS._file_identity
        original_open = self.module._open_existing_for_cas
        cases = (
            ("interrupt", "interrupt"),
            ("build-error", "build-error"),
            ("zero-matches", "zero"),
            ("two-matches", "two"),
        )
        for name, fault in cases:
            with self.subTest(name=name):
                case_root = self.root / f"restore-probe-{name}"
                case_root.mkdir()
                accepted_path = case_root / "base-lock.json"
                candidate_path = case_root / "candidate.json"
                accepted_path.write_bytes(old_raw)
                candidate_path.write_bytes(candidate_raw)
                old_identity = original_identity(
                    accepted_path,
                    "restore probe fixture",
                )
                opened = []
                probe_calls = 0

                def track_open(path):
                    owned = original_open(path)
                    opened.append(owned)
                    return owned

                def fail_first_restore_reconcile(path, label, missing_ok=False):
                    nonlocal probe_calls
                    if label == "accepted-lock restoration path":
                        probe_calls += 1
                        if fault == "interrupt" and probe_calls == 1:
                            raise KeyboardInterrupt("restoration probe interrupt")
                        if fault == "build-error" and probe_calls == 1:
                            raise self.module.SERIS.PUBLISH_TOOLS.BuildError(
                                "restoration probe failure"
                            )
                        if fault == "zero" and probe_calls <= 2:
                            return None
                        if fault == "two" and probe_calls <= 2:
                            return old_identity
                    return original_identity(
                        path,
                        label,
                        missing_ok=missing_ok,
                    )

                with mock.patch.object(
                    self.module,
                    "_open_existing_for_cas",
                    side_effect=track_open,
                ), mock.patch.object(
                    self.module.SERIS.PUBLISH_TOOLS,
                    "_file_identity",
                    side_effect=fail_first_restore_reconcile,
                ), mock.patch.object(
                    self.module,
                    "_publish_candidate_owner_no_replace",
                    side_effect=self.module.LockDiscoveryError("publish fault"),
                ):
                    with self.assertRaises(self.module.LockDiscoveryError) as raised:
                        self.module.accept_extension_candidate(
                            candidate_path,
                            accepted_path,
                            confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                            expected_old_lock_sha256=hashlib.sha256(
                                old_raw
                            ).hexdigest(),
                            expected_candidate_sha256=hashlib.sha256(
                                candidate_raw
                            ).hexdigest(),
                        )

                self.assertGreaterEqual(probe_calls, 2)
                self.assertEqual(old_raw, accepted_path.read_bytes())
                self.assertEqual(
                    [], list(case_root.glob(".base-lock.json.*.cas-old"))
                )
                self.assertEqual(1, len(opened))
                self.assertEqual(accepted_path, Path(opened[0].path))
                self.assertTrue(opened[0].handle.closed)
                notes = getattr(raised.exception, "__notes__", ())
                self.assertTrue(any(str(accepted_path) in note for note in notes))

    def test_accept_extension_reports_all_existing_restore_pending_paths(self) -> None:
        base = self.accepted_base()
        candidate = extension_fixture(self.module, base)
        old_raw = self.module._canonical_json_bytes(base)
        candidate_raw = self.module._canonical_json_bytes(candidate)
        competitor_raw = b"external recovery competitor\n"
        self.accepted_path.write_bytes(old_raw)
        self.candidate_path.write_bytes(candidate_raw)
        original_identity = self.module.SERIS.PUBLISH_TOOLS._file_identity
        original_open = self.module._open_existing_for_cas
        old_identity = original_identity(
            self.accepted_path,
            "persistent restore probe fixture",
        )
        opened = []
        recovery_path = None
        probe_calls = 0

        def track_open(path):
            owned = original_open(path)
            opened.append(owned)
            return owned

        def fail_restore_reconcile(path, label, missing_ok=False):
            nonlocal probe_calls, recovery_path
            if label == "accepted-lock restoration path":
                probe_calls += 1
                if recovery_path is None:
                    recovery_path = Path(path)
                    recovery_path.write_bytes(competitor_raw)
                return old_identity
            return original_identity(path, label, missing_ok=missing_ok)

        with mock.patch.object(
            self.module,
            "_open_existing_for_cas",
            side_effect=track_open,
        ), mock.patch.object(
            self.module.SERIS.PUBLISH_TOOLS,
            "_file_identity",
            side_effect=fail_restore_reconcile,
        ), mock.patch.object(
            self.module,
            "_publish_candidate_owner_no_replace",
            side_effect=self.module.LockDiscoveryError("publish fault"),
        ):
            with self.assertRaises(self.module.LockDiscoveryError) as raised:
                self.module.accept_extension_candidate(
                    self.candidate_path,
                    self.accepted_path,
                    confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                    expected_old_lock_sha256=hashlib.sha256(old_raw).hexdigest(),
                    expected_candidate_sha256=hashlib.sha256(
                        candidate_raw
                    ).hexdigest(),
                )

        self.assertGreaterEqual(probe_calls, 4)
        self.assertEqual(old_raw, self.accepted_path.read_bytes())
        self.assertIsNotNone(recovery_path)
        self.assertEqual(competitor_raw, recovery_path.read_bytes())
        self.assertEqual(1, len(opened))
        self.assertTrue(opened[0].handle.closed)
        notes = getattr(raised.exception, "__notes__", ())
        pending_notes = [
            note for note in notes if "existing pending paths=" in note
        ]
        self.assertEqual(1, len(pending_notes))
        self.assertIn(str(self.accepted_path), pending_notes[0])
        self.assertIn(str(recovery_path), pending_notes[0])

    def test_candidate_schema_rejects_bool_counts_and_nonstring_hashes(self) -> None:
        bool_count = deepcopy(self.candidate)
        bool_count["abyss_stage"]["match_count"] = True
        numeric_hash = deepcopy(self.candidate)
        first_site = numeric_hash["site_ids"][0]
        numeric_hash["sites"][first_site]["after_abc_sha256"] = int("1" * 64)
        for value in (bool_count, numeric_hash):
            with self.subTest(value=value), self.assertRaises(
                self.module.LockDiscoveryError
            ):
                self.module.validate_lock_document(
                    value,
                    expected_status="candidate",
                )

    def test_privacy_scan_rejects_paths_timestamps_commands_secrets_and_refresh(self) -> None:
        forbidden = (
            ("debug_path", r"C:\\private\\base.apk"),
            ("created_at", "2026-07-21T10:11:12Z"),
            ("command", "java -jar ffdec.jar"),
            ("keystore", "release.jks"),
            ("refresh_instruction", "recompute hashes"),
        )
        for key, value in forbidden:
            item = deepcopy(self.candidate)
            item[key] = value
            with self.subTest(key=key), self.assertRaises(self.module.LockDiscoveryError):
                self.module.validate_lock_document(item, expected_status="candidate")

    def test_accept_requires_confirmation_is_canonical_and_never_overwrites(self) -> None:
        self.write_candidate()
        with self.assertRaises(self.module.LockDiscoveryError):
            self.module.accept_lock_candidate(
                self.candidate_path,
                self.accepted_path,
                confirmation="wrong",
                expected_candidate_sha256=self.candidate_sha256(),
            )
        accepted = self.module.accept_lock_candidate(
            self.candidate_path,
            self.accepted_path,
            confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
            expected_candidate_sha256=self.candidate_sha256(),
        )
        self.assertEqual("accepted", accepted["status"])
        self.assertEqual(self.module._canonical_json_bytes(accepted), self.accepted_path.read_bytes())
        with self.assertRaises(self.module.LockDiscoveryError):
            self.module.accept_lock_candidate(
                self.candidate_path,
                self.accepted_path,
                confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                expected_candidate_sha256=self.candidate_sha256(),
            )

    def test_accept_binds_the_exact_reviewed_candidate_digest(self) -> None:
        self.write_candidate()
        with self.assertRaises(self.module.LockDiscoveryError):
            self.module.accept_lock_candidate(
                self.candidate_path,
                self.accepted_path,
                confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                expected_candidate_sha256="0" * 64,
            )
        self.assertFalse(self.accepted_path.exists())
        accepted = self.module.accept_lock_candidate(
            self.candidate_path,
            self.accepted_path,
            confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
            expected_candidate_sha256=self.candidate_sha256(),
        )
        self.assertEqual("accepted", accepted["status"])

    def test_accept_rejects_parseable_noncanonical_candidate_bytes(self) -> None:
        variants = (
            json.dumps(self.candidate, separators=(",", ":"), sort_keys=False),
            self.module._canonical_json_bytes(self.candidate).decode("utf-8").rstrip("\n"),
        )
        for raw in variants:
            self.candidate_path.write_text(raw, encoding="utf-8", newline="")
            with self.subTest(length=len(raw)), self.assertRaises(self.module.LockDiscoveryError):
                self.module.accept_lock_candidate(
                    self.candidate_path,
                    self.accepted_path,
                    confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                    expected_candidate_sha256=hashlib.sha256(
                        raw.encode("utf-8")
                    ).hexdigest(),
                )
            self.assertFalse(self.accepted_path.exists())

    def test_accept_external_race_and_keyboard_interrupt_leave_no_owned_partial(self) -> None:
        self.write_candidate()
        original_publish = self.module._publish_staged_exclusive

        def external_then_publish(staging, destination, expected_hash):
            Path(destination).write_bytes(b"external-lock")
            original_publish(staging, destination, expected_hash)

        with mock.patch.object(
            self.module, "_publish_staged_exclusive", side_effect=external_then_publish
        ):
            with self.assertRaises(self.module.LockDiscoveryError):
                self.module.accept_lock_candidate(
                    self.candidate_path,
                    self.accepted_path,
                    confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                    expected_candidate_sha256=self.candidate_sha256(),
                )
        self.assertEqual(b"external-lock", self.accepted_path.read_bytes())
        self.accepted_path.unlink()
        with mock.patch.object(
            self.module, "_stage_output_sibling", side_effect=KeyboardInterrupt("cancel")
        ):
            with self.assertRaises(KeyboardInterrupt):
                self.module.accept_lock_candidate(
                    self.candidate_path,
                    self.accepted_path,
                    confirmation="ACCEPT_OFFLINE_BASE_4F6884F3",
                    expected_candidate_sha256=self.candidate_sha256(),
                )
        self.assertFalse(self.accepted_path.exists())

    def test_fake_discover_extracts_one_swf_and_emits_candidate_only(self) -> None:
        apk = self.root / "base.apk"
        with zipfile.ZipFile(apk, "w") as archive:
            archive.writestr("assets/worldflipper_android_release.swf", b"swf-fixture")
        baseline_fields = {
            key: deepcopy(self.candidate[key])
            for key in (
                "source_swf_sha256",
                "manifest_sha256",
                "dex_sha256",
                "native_aggregate_sha256",
                "native_members",
            )
        }
        evidence = {
            key: deepcopy(self.candidate[key])
            for key in (
                "post_abyss_swf_sha256",
                "abyss_stage",
                "offline_method_sha256",
                "save_method_sha256",
                "sites",
                "native_compatibility",
                "three_way_merges",
            )
        }
        calls = []

        def provider(*, source_swf: Path, transaction_dir: Path):
            calls.append((source_swf.read_bytes(), source_swf.parent == transaction_dir))
            return evidence

        with mock.patch.object(
            self.module,
            "_sha256_file",
            side_effect=lambda path: (
                BASE_APK_SHA256
                if Path(path).suffix == ".apk"
                else self.module.EXPECTED_SWF_SHA256
                if Path(path).name == "source.swf"
                else hashlib.sha256(Path(path).read_bytes()).hexdigest()
            ),
        ), mock.patch.object(
            self.module, "_inspect_base_apk", return_value=baseline_fields
        ):
            result = self.module.discover_lock_candidate(
                apk,
                self.candidate_path,
                work_dir=self.root / "work",
                evidence_provider=provider,
            )
        self.assertEqual([(b"swf-fixture", True)], calls)
        self.assertEqual("candidate", result["status"])
        self.assertEqual(self.module._canonical_json_bytes(result), self.candidate_path.read_bytes())
        self.assertFalse((self.root / "base-lock.json").exists())

    def test_discover_rejects_extracted_swf_that_differs_from_inspected_baseline(self) -> None:
        apk = self.root / "swapped.apk"
        with zipfile.ZipFile(apk, "w") as archive:
            archive.writestr(
                "assets/worldflipper_android_release.swf",
                b"swapped-unreviewed-swf",
            )
        baseline_fields = {
            key: deepcopy(self.candidate[key])
            for key in (
                "source_swf_sha256",
                "manifest_sha256",
                "dex_sha256",
                "native_aggregate_sha256",
                "native_members",
            )
        }
        provider = mock.Mock()

        def fake_hash(path):
            current = Path(path)
            if current.suffix == ".apk":
                return BASE_APK_SHA256
            return hashlib.sha256(current.read_bytes()).hexdigest()

        with mock.patch.object(
            self.module,
            "_sha256_file",
            side_effect=fake_hash,
        ), mock.patch.object(
            self.module,
            "_inspect_base_apk",
            return_value=baseline_fields,
        ):
            with self.assertRaises(self.module.LockDiscoveryError):
                self.module.discover_lock_candidate(
                    apk,
                    self.root / "swapped-candidate.json",
                    work_dir=self.root / "swapped-work",
                    evidence_provider=provider,
                )
        provider.assert_not_called()

    def test_unlocked_discovery_runs_nine_name_based_replace_reopen_stages(self) -> None:
        blocks = fixture_blocks()
        initial = {
            patch.method_name: blocks[patch.site_id].replace(
                'trait method QName(PackageNamespace(""),"fixture")',
                'trait method QName(PackageNamespace(""),"'
                + patch.method_name.rsplit("/", 1)[-1]
                + '")',
                1,
            )
            for patch in self.module.SERIS.PATCHES
        }
        source = self.root / "post-abyss.swf"
        source.write_text(json.dumps(initial, sort_keys=True), encoding="utf-8")
        ffdec = self.root / "ffdec.jar"
        java = self.root / "java.exe"
        ffdec.write_bytes(b"fixture")
        java.write_bytes(b"fixture")
        runner = FakeFfdecRunner(self.module.SERIS, source, initial)
        runner.require_ref_calls = []
        transaction = self.root / "unlocked"
        transaction.mkdir()
        with mock.patch.object(
            self.module.SERIS.ABC_METHODS,
            "index_swf_methods",
            side_effect=runner.index,
        ):
            sites, final_swf = self.module._discover_seris_sites(
                source,
                transaction_dir=transaction,
                ffdec=ffdec,
                java=java,
                profile_dir=self.root / "profile",
                runner=runner,
            )
        self.assertEqual(set(EXPECTED_SITES), set(sites))
        self.assertTrue(final_swf.is_file())
        self.assertEqual(9, sum(kind == "replace" for kind, *_ in runner.calls))
        self.assertGreaterEqual(sum(kind == "export" for kind, *_ in runner.calls), 18)
        for entry in sites.values():
            for field in (
                "before_pcode_sha256",
                "after_pcode_sha256",
                "before_abc_sha256",
                "after_abc_sha256",
            ):
                self.assertRegex(entry[field], r"^[0-9a-f]{64}$")

    def test_discover_cli_wires_explicit_tool_work_and_profile_paths(self) -> None:
        apk = self.root / "base.apk"
        java = self.root / "java.exe"
        ffdec = self.root / "ffdec.jar"
        for path in (apk, java, ffdec):
            path.write_bytes(b"fixture")
        provider = object()
        with mock.patch.object(
            self.module, "build_reviewed_evidence_provider", return_value=provider
        ) as build_provider, mock.patch.object(
            self.module,
            "discover_lock_candidate",
            return_value={"status": "candidate", "site_count": 9},
        ) as discover:
            output = io.StringIO()
            with redirect_stdout(output):
                result = self.module.main(
                    [
                        "discover",
                        "--source-apk", str(apk),
                        "--expected-apk-sha256", BASE_APK_SHA256,
                        "--after-stage", "abyss",
                        "--output", str(self.candidate_path),
                        "--java", str(java),
                        "--ffdec", str(ffdec),
                        "--work-dir", str(self.root / "work"),
                        "--profile-dir", str(self.root / "profile"),
                    ]
                )
        self.assertEqual(0, result)
        self.assertEqual(9, json.loads(output.getvalue())["site_count"])
        build_provider.assert_called_once()
        self.assertIs(provider, discover.call_args.kwargs["evidence_provider"])

    def test_discover_extension_cli_wires_base_hash_and_explicit_provider(self) -> None:
        apk = self.root / "base.apk"
        base_lock = self.root / "base-lock.json"
        java = self.root / "java.exe"
        ffdec = self.root / "ffdec.jar"
        for path in (apk, base_lock, java, ffdec):
            path.write_bytes(b"fixture")
        base = self.accepted_base()
        result_value = extension_fixture(self.module, base)
        provider = object()
        old_digest = "1" * 64
        with mock.patch.object(
            self.module, "build_extension_evidence_provider", return_value=provider
        ) as build_provider, mock.patch.object(
            self.module,
            "discover_extension_candidate",
            return_value=result_value,
        ) as discover:
            output = io.StringIO()
            with redirect_stdout(output):
                result = self.module.main(
                    [
                        "discover-extension",
                        "--source-apk", str(apk),
                        "--base-lock", str(base_lock),
                        "--expected-apk-sha256", BASE_APK_SHA256,
                        "--expected-old-lock-sha256", old_digest,
                        "--output", str(self.candidate_path),
                        "--java", str(java),
                        "--ffdec", str(ffdec),
                        "--work-dir", str(self.root / "work"),
                        "--profile-dir", str(self.root / "profile"),
                    ]
                )
        self.assertEqual(0, result)
        summary = json.loads(output.getvalue())
        self.assertEqual("extension-candidate", summary["status"])
        self.assertEqual(3, summary["render_site_count"])
        self.assertEqual("1.4.196", summary["resource_version"])
        self.assertEqual(old_digest, summary["base_lock_sha256"])
        self.assertEqual(
            hashlib.sha256(self.module._canonical_json_bytes(result_value)).hexdigest(),
            summary["candidate_sha256"],
        )
        build_provider.assert_called_once()
        self.assertIs(provider, discover.call_args.kwargs["evidence_provider"])
        self.assertEqual(base_lock, discover.call_args.args[1])
        self.assertEqual(
            old_digest,
            discover.call_args.kwargs["expected_old_lock_sha256"],
        )

    def test_accept_extension_cli_forwards_both_exact_hashes(self) -> None:
        old_digest = "1" * 64
        candidate_digest = "2" * 64
        accepted = extension_fixture(self.module, self.accepted_base())
        with mock.patch.object(
            self.module,
            "accept_extension_candidate",
            return_value=accepted,
        ) as accept:
            output = io.StringIO()
            with redirect_stdout(output):
                result = self.module.main(
                    [
                        "accept-extension",
                        "--candidate", str(self.candidate_path),
                        "--output", str(self.accepted_path),
                        "--confirm", "ACCEPT_OFFLINE_BASE_4F6884F3",
                        "--expected-old-lock-sha256", old_digest,
                        "--expected-candidate-sha256", candidate_digest,
                    ]
                )
        self.assertEqual(0, result)
        self.assertEqual(
            {
                "status": "accepted",
                "final_sha256": candidate_digest,
                "render_site_count": 3,
                "resource_version": "1.4.196",
            },
            json.loads(output.getvalue()),
        )
        self.assertEqual(
            {
                "confirmation": "ACCEPT_OFFLINE_BASE_4F6884F3",
                "expected_old_lock_sha256": old_digest,
                "expected_candidate_sha256": candidate_digest,
            },
            accept.call_args.kwargs,
        )


if __name__ == "__main__":
    unittest.main()
