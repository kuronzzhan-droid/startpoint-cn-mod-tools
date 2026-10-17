from __future__ import annotations

from external_sources import client_patch_path, require_external_source

import hashlib
import importlib.util
import inspect
import json
import os
import sys
import tempfile
import textwrap
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = client_patch_path('offline-android/render_scale_pcode.py')

EXPECTED_SITES = ("pixel-art", "member-view", "character-cell")
EXPECTED_IDENTITIES = (
    (
        "pixel-art",
        "pinball.ui.component.pixelArtCharacter.PixelArtCharacterView",
        "pinball.ui.component.pixelArtCharacter:PixelArtCharacterView/spriteSheetLoadCompleted",
    ),
    (
        "member-view",
        "pinball.scene.battle.battle.squad.member.MemberView",
        "pinball.scene.battle.battle.squad.member:MemberView/MemberView",
    ),
    (
        "character-cell",
        "pinball.scene.character.cell.CharacterCellView",
        "pinball.scene.character.cell:CharacterCellView/drawWithAdvanceFlag",
    ),
)
EXPECTED_BASE_ABC_SHA256 = {
    "pixel-art": "9475368c4dd326f0d8230ba724d96a60af5d30dba37ac5d43d5bdd04a85b038b",
    "member-view": "0ca2af059a85e432c9c6dc991126d0eeba57acaa5ecc152aee83e36ed19a9d77",
    "character-cell": "cc64eafcb0bbaeb4f1ae705944da569cc1d59bf9dc7636b1bbfe64342175e3a7",
}
NON_RENDER_CTOR = {
    "method_name": "pinball.scene.character.cell:CharacterCell/CharacterCell",
    "before_abc_sha256": "f1d643128a517f7ae5f6c0628c3d96761254a67f34520a257ab302519329a0b8",
    "reason": "constructor has no character identity or render-scale semantics",
}
LOCK_FIELDS = {
    "class_name",
    "method_name",
    "before_pcode_sha256",
    "after_pcode_sha256",
    "before_abc_sha256",
    "after_abc_sha256",
}


PIXEL_BEFORE = (
    "getlocal 12",
    "pushbyte 1",
    'initproperty QName(PackageNamespace(""),"scale")',
)
PIXEL_AFTER = (
    "getlocal 12",
    "getlocal 12",
    'getproperty QName(PackageNamespace(""),"scale")',
    "pushbyte 6",
    "divide",
    'initproperty QName(PackageNamespace(""),"scale")',
)
MEMBER_SHADOW = (
    'findproperty QName(PackageNamespace(""),"shadow")',
    'getproperty QName(PackageNamespace(""),"shadow")',
    'getlex QName(PackageNamespace("pinball.scene.battle.battle"),"BattleConstants")',
    'getproperty QName(PackageNamespace(""),"SCALE_RENDERER")',
    'initproperty QName(PackageNamespace(""),"scaleX")',
    'findproperty QName(PackageNamespace(""),"shadow")',
    'getproperty QName(PackageNamespace(""),"shadow")',
    'getlex QName(PackageNamespace("pinball.scene.battle.battle"),"BattleConstants")',
    'getproperty QName(PackageNamespace(""),"SCALE_RENDERER")',
    'initproperty QName(PackageNamespace(""),"scaleY")',
)
MEMBER_CHARACTER = (
    'findproperty QName(PackageNamespace(""),"character")',
    'getproperty QName(PackageNamespace(""),"character")',
    'getlex QName(PackageNamespace("pinball.scene.battle.battle"),"BattleConstants")',
    'getproperty QName(PackageNamespace(""),"SCALE_RENDERER")',
    'initproperty QName(PackageNamespace(""),"scaleX")',
    'findproperty QName(PackageNamespace(""),"character")',
    'getproperty QName(PackageNamespace(""),"character")',
    'getlex QName(PackageNamespace("pinball.scene.battle.battle"),"BattleConstants")',
    'getproperty QName(PackageNamespace(""),"SCALE_RENDERER")',
    'initproperty QName(PackageNamespace(""),"scaleY")',
)
CELL_MATRIX = (
    'findproperty QName(PackageNamespace(""),"character")',
    'getproperty QName(PackageNamespace(""),"character")',
    'coerce QName(PackageNamespace("starling.display"),"DisplayObject")',
    "setlocal 43",
    'findproperty QName(PackageNamespace(""),"tempTransformation")',
    'getproperty QName(PackageNamespace(""),"tempTransformation")',
    "coerce_a",
    "setlocal 39",
    "getlocal 43",
    "getlocal 39",
    'getproperty QName(PackageNamespace(""),"matrix")',
    'coerce QName(PackageNamespace("flash.geom"),"Matrix")',
    'initproperty QName(PackageNamespace(""),"transformationMatrix")',
)
CELL_SCALE_X = (
    "getlocal 43",
    "dup",
    'getproperty QName(PackageNamespace(""),"scaleX")',
    "getlocal 43",
    'getproperty QName(PackageNamespace(""),"defaultScale")',
    "pushbyte 6",
    "divide",
    "multiply",
    'initproperty QName(PackageNamespace(""),"scaleX")',
)
CELL_SCALE_Y = (
    "getlocal 43",
    "dup",
    'getproperty QName(PackageNamespace(""),"scaleY")',
    "getlocal 43",
    'getproperty QName(PackageNamespace(""),"defaultScale")',
    "pushbyte 6",
    "divide",
    "multiply",
    'initproperty QName(PackageNamespace(""),"scaleY")',
)


def load_module():
    require_external_source(MODULE_PATH)
    spec = importlib.util.spec_from_file_location("offline_render_scale", require_external_source(MODULE_PATH))
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _code(*lines: str) -> str:
    return "\n".join("   " + line for line in lines)


def _method(
    *parts: str,
    trait_name: str | None = "fixture",
    maxstack: int = 4,
    localcount: int = 49,
) -> str:
    trait = (
        ""
        if trait_name is None
        else f'trait method QName(PackageNamespace(""),"{trait_name}")\n'
    )
    body = "\n".join(part for part in parts if part)
    return (
        trait
        + "method\n"
        + " maxstack "
        + str(maxstack)
        + "\n localcount "
        + str(localcount)
        + "\n initscopedepth 1\n maxscopedepth 2\n code\n"
        + body
        + "\n end ; code\nend ; method\n"
    )


def fixture_blocks() -> dict[str, str]:
    return {
        "pixel-art": _method(
            _code('pushstring "pixel-base-before"'),
            _code(*PIXEL_BEFORE),
            _code('pushstring "pixel-base-after"'),
            maxstack=6,
            localcount=14,
        ),
        "member-view": _method(
            _code('pushstring "member-base-before"'),
            _code(*MEMBER_SHADOW),
            _code('pushstring "member-created-character"'),
            _code(*MEMBER_CHARACTER),
            _code("pushbyte 21", 'initproperty QName(PackageNamespace(""),"zIndex2")'),
            trait_name=None,
            maxstack=5,
            localcount=5,
        ),
        "character-cell": _method(
            _code('pushstring "cell-base-before"'),
            _code(*CELL_MATRIX),
            _code('pushstring "cell-base-after"'),
        ),
    }


def _replace_anchor(block: str, sequence: tuple[str, ...], replacement: str) -> str:
    anchor = _code(*sequence)
    if block.count(anchor) != 1:
        raise AssertionError("fixture anchor mismatch")
    return block.replace(anchor, replacement, 1)


class TestRenderPatchFunctions(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()
        cls.blocks = fixture_blocks()

    def test_schema_is_ordered_immutable_and_uses_corrected_character_cell_site(self) -> None:
        self.assertIsInstance(self.module.RENDER_SITES, tuple)
        self.assertEqual(
            EXPECTED_IDENTITIES,
            tuple(
                (site.site_id, site.class_name, site.method_name)
                for site in self.module.RENDER_SITES
            ),
        )
        self.assertEqual(EXPECTED_BASE_ABC_SHA256, dict(self.module.BASE_BEFORE_ABC_SHA256))
        self.assertEqual(NON_RENDER_CTOR, dict(self.module.NON_RENDER_CHARACTER_CELL_CTOR))
        self.assertNotIn(
            NON_RENDER_CTOR["method_name"],
            tuple(site.method_name for site in self.module.RENDER_SITES),
        )
        with self.assertRaises(FrozenInstanceError):
            self.module.RENDER_SITES[0].site_id = "mutated"
        self.assertTrue(self.module.RenderSite.__dataclass_params__.frozen)
        self.assertIn("__slots__", self.module.RenderSite.__dict__)

    def test_report_is_frozen_slotted_and_exact(self) -> None:
        self.assertEqual(
            (
                "output_path",
                "input_sha256",
                "output_sha256",
                "site_ids",
                "before_hashes",
                "after_hashes",
                "verified",
            ),
            tuple(self.module.RenderPatchReport.__dataclass_fields__),
        )
        self.assertTrue(self.module.RenderPatchReport.__dataclass_params__.frozen)
        self.assertIn("__slots__", self.module.RenderPatchReport.__dict__)

    def test_public_stage_signatures_require_explicit_tools(self) -> None:
        for name in ("apply_render_scale", "verify_render_scale"):
            parameters = inspect.signature(getattr(self.module, name)).parameters
            self.assertEqual(
                ("source_swf", "output_swf", "lock")
                if name == "apply_render_scale"
                else ("output_swf", "lock"),
                tuple(parameters)[: 3 if name == "apply_render_scale" else 2],
            )
            for required in ("ffdec", "java", "profile_dir", "work_dir"):
                self.assertIn(required, parameters)

    def test_production_source_is_pcode_only_and_independent_from_work(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8").replace("\\", "/")
        for forbidden in (
            "work/",
            "render-scale-v1",
            "PixelArtCharacterView.as",
            "-importscript",
            "149999",
        ):
            self.assertNotIn(forbidden, source)

    def test_pixel_art_preserves_base_logic_and_uses_frame_scale(self) -> None:
        output = self.module.patch_pixel_art(self.blocks["pixel-art"])
        self.assertIn('pushstring "pixel-base-before"', output)
        self.assertIn('pushstring "pixel-base-after"', output)
        self.assertNotIn(_code(*PIXEL_BEFORE), output)
        self.assertEqual(1, output.count(_code(*PIXEL_AFTER)))
        self.module.verify_pixel_art(output)

    def test_member_view_removes_only_character_scale_renderer_and_keeps_shadow(self) -> None:
        output = self.module.patch_member_view_ctor(self.blocks["member-view"])
        self.assertNotIn(_code(*MEMBER_CHARACTER), output)
        self.assertEqual(1, output.count(_code(*MEMBER_SHADOW)))
        self.assertIn('pushstring "member-created-character"', output)
        self.assertIn('initproperty QName(PackageNamespace(""),"zIndex2")', output)
        self.module.verify_member_view_ctor(output)

    def test_character_cell_scales_after_matrix_without_overwriting_base_logic(self) -> None:
        output = self.module.patch_character_cell(self.blocks["character-cell"])
        full = _code(*(CELL_MATRIX + CELL_SCALE_X + CELL_SCALE_Y))
        self.assertEqual(1, output.count(full))
        self.assertIn('pushstring "cell-base-before"', output)
        self.assertIn('pushstring "cell-base-after"', output)
        self.assertNotIn("149999", output)
        self.module.verify_character_cell(output)

    def test_all_three_patchers_reject_zero_and_multiple_anchors(self) -> None:
        cases = (
            ("pixel-art", self.module.patch_pixel_art, PIXEL_BEFORE),
            ("member-view", self.module.patch_member_view_ctor, MEMBER_CHARACTER),
            ("character-cell", self.module.patch_character_cell, CELL_MATRIX),
        )
        for site_id, patch, anchor in cases:
            original = self.blocks[site_id]
            with self.subTest(site=site_id, count=0), self.assertRaises(
                self.module.RenderScaleError
            ):
                patch(_replace_anchor(original, anchor, _code("nop")))
            doubled = _code(*anchor) + "\n" + _code(*anchor)
            with self.subTest(site=site_id, count=2), self.assertRaises(
                self.module.RenderScaleError
            ):
                patch(_replace_anchor(original, anchor, doubled))

    def test_all_three_patchers_reject_duplicate_application(self) -> None:
        cases = (
            (self.module.patch_pixel_art, self.blocks["pixel-art"]),
            (self.module.patch_member_view_ctor, self.blocks["member-view"]),
            (self.module.patch_character_cell, self.blocks["character-cell"]),
        )
        for patch, block in cases:
            with self.subTest(patch=patch.__name__), self.assertRaises(
                self.module.RenderScaleError
            ):
                patch(patch(block))

    def test_verifiers_reject_critical_semantic_mutations(self) -> None:
        cases = (
            (
                self.module.verify_pixel_art,
                self.module.patch_pixel_art(self.blocks["pixel-art"]),
                "divide",
            ),
            (
                self.module.verify_member_view_ctor,
                self.module.patch_member_view_ctor(self.blocks["member-view"]),
                'findproperty QName(PackageNamespace(""),"shadow")',
            ),
            (
                self.module.verify_character_cell,
                self.module.patch_character_cell(self.blocks["character-cell"]),
                'getproperty QName(PackageNamespace(""),"defaultScale")',
            ),
        )
        for verify, block, token in cases:
            with self.subTest(verify=verify.__name__), self.assertRaises(
                self.module.RenderScaleError
            ):
                verify(block.replace(token, "nop", 1))

    def test_character_cell_verifier_rejects_header_and_pseudo_local_drift(self) -> None:
        output = self.module.patch_character_cell(self.blocks["character-cell"])
        for mutated in (
            output.replace("maxstack 4", "maxstack 5", 1),
            output.replace(
                'pushstring "cell-base-after"',
                'getlex QName(PackageNamespace(""),"_temp_1")',
                1,
            ),
        ):
            with self.assertRaises(self.module.RenderScaleError):
                self.module.verify_character_cell(mutated)

    def test_canonical_pcode_normalizes_only_valid_offset_label_renumbering(self) -> None:
        left = "method\n ofs0010:\n  jump ofs0020\n ofs0020:\n  returnvoid\nend ; method\n"
        right = "method\n ofs00aa:\n  jump ofs00ff\n ofs00ff:\n  returnvoid\nend ; method\n"
        self.assertEqual(
            self.module.canonical_pcode(left), self.module.canonical_pcode(right)
        )
        with self.assertRaises(self.module.RenderScaleError):
            self.module.canonical_pcode("method\n jump ofs9999\nend ; method\n")


class FakeRef:
    def __init__(self, method_name: str, body_index: int, method_info_index: int, code: bytes):
        self.method_name = method_name
        self.body_index = body_index
        self.method_info_index = method_info_index
        self.code = code


class FakeIndex:
    def __init__(
        self,
        state: dict[str, str],
        identities: dict[str, tuple[int, int]],
        calls: list[str],
    ) -> None:
        self.state = state
        self.identities = identities
        self.calls = calls

    def require_ref(self, method_name: str) -> FakeRef:
        self.calls.append(method_name)
        if method_name not in self.state:
            raise AssertionError(f"unknown fake method {method_name}")
        body_index, method_info_index = self.identities[method_name]
        return FakeRef(
            method_name,
            body_index,
            method_info_index,
            self.state[method_name].encode("utf-8"),
        )


class FakeFfdecRunner:
    def __init__(
        self,
        module,
        source: Path,
        initial: dict[str, str],
        identities: dict[str, tuple[int, int]],
    ) -> None:
        self.module = module
        self.states: dict[Path, dict[str, str]] = {source.resolve(): dict(initial)}
        self.identities = identities
        self.calls: list[tuple[str, tuple[str, ...], Path, str]] = []
        self.require_ref_calls: list[str] = []

    def _state(self, path: Path) -> dict[str, str]:
        resolved = Path(path).resolve()
        if resolved not in self.states:
            self.states[resolved] = json.loads(resolved.read_text(encoding="utf-8"))
        return self.states[resolved]

    def index(self, path: Path) -> FakeIndex:
        return FakeIndex(self._state(path), self.identities, self.require_ref_calls)

    def __call__(self, command, *, cwd: Path, env: dict[str, str], timeout: int):
        del timeout
        argv = tuple(str(part) for part in command)
        kind = "replace" if "-replace" in argv else "export"
        self.calls.append((kind, argv, Path(cwd), env["APPDATA"]))
        if kind == "replace":
            position = argv.index("-replace")
            source = Path(argv[position + 1]).resolve()
            destination = Path(argv[position + 2]).resolve()
            replacement = Path(argv[position + 4]).read_text(encoding="utf-8")
            body_index = int(argv[position + 5])
            inverse = {
                identity[0]: method_name
                for method_name, identity in self.identities.items()
            }
            method_name = inverse[body_index]
            state = dict(self._state(source))
            state[method_name] = replacement
            destination.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
            self.states[destination] = state
        else:
            position = argv.index("-export")
            export_root = Path(argv[position + 2])
            source = Path(argv[position + 3]).resolve()
            class_position = argv.index("-selectclass")
            classes = argv[class_position + 1].split(",")
            state = self._state(source)
            for class_name in classes:
                blocks: list[str] = []
                for site in self.module.RENDER_SITES:
                    if site.class_name != class_name:
                        continue
                    block = state[site.method_name]
                    short_name = site.method_name.rsplit("/", 1)[-1]
                    if short_name == class_name.rsplit(".", 1)[-1]:
                        block = (
                            f"public function {short_name}()\n{{\n"
                            + textwrap.indent(block, "   ")
                            + "}\n"
                        )
                    blocks.append(block)
                target = (
                    export_root
                    / "scripts"
                    / Path(*class_name.split(".")).with_suffix(".pcode")
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("\n".join(blocks), encoding="utf-8")
        return {"returncode": 0, "stdout": "", "stderr": ""}


class TestRenderStage(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source.swf"
        self.output = self.root / "output.swf"
        self.work = self.root / "work"
        self.profile = self.root / "profile"
        self.ffdec = self.root / "ffdec.jar"
        self.java = self.root / "java.exe"
        for path in (self.ffdec, self.java):
            path.write_bytes(b"fixture")

        blocks = fixture_blocks()
        stage_blocks: dict[str, str] = {}
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
            stage_blocks[site.site_id] = block
        self.initial = {
            site.method_name: stage_blocks[site.site_id]
            for site in self.module.RENDER_SITES
        }
        self.identities = {
            site.method_name: (700 + index * 17, 1700 + index * 29)
            for index, site in enumerate(self.module.RENDER_SITES)
        }
        self.source.write_text(json.dumps(self.initial, sort_keys=True), encoding="utf-8")
        self.runner = FakeFfdecRunner(
            self.module, self.source, self.initial, self.identities
        )
        self.before_pcode = {
            site.site_id: self.module._sha256_pcode(stage_blocks[site.site_id])
            for site in self.module.RENDER_SITES
        }
        self.after_pcode = {
            site.site_id: self.module._sha256_pcode(site.patch(stage_blocks[site.site_id]))
            for site in self.module.RENDER_SITES
        }
        self.before_abc = {
            site.site_id: hashlib.sha256(
                stage_blocks[site.site_id].encode("utf-8")
            ).hexdigest()
            for site in self.module.RENDER_SITES
        }
        self.after_abc = {
            site.site_id: hashlib.sha256(
                site.patch(stage_blocks[site.site_id]).encode("utf-8")
            ).hexdigest()
            for site in self.module.RENDER_SITES
        }
        self.lock = {
            "schema_version": 4,
            "status": "accepted",
            "stage": "post-abyss",
            "render_site_ids": list(EXPECTED_SITES),
            "render_sites": {
                site.site_id: {
                    "class_name": site.class_name,
                    "method_name": site.method_name,
                    "before_pcode_sha256": self.before_pcode[site.site_id],
                    "after_pcode_sha256": self.after_pcode[site.site_id],
                    "before_abc_sha256": self.before_abc[site.site_id],
                    "after_abc_sha256": self.after_abc[site.site_id],
                }
                for site in self.module.RENDER_SITES
            },
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def apply(self):
        with (
            mock.patch.object(
                self.module.ABC_METHODS,
                "index_swf_methods",
                side_effect=self.runner.index,
            ),
            mock.patch.object(
                self.module,
                "BASE_BEFORE_ABC_SHA256",
                MappingProxyType(dict(self.before_abc)),
            ),
        ):
            return self.module.apply_render_scale(
                self.source,
                self.output,
                self.lock,
                ffdec=self.ffdec,
                java=self.java,
                profile_dir=self.profile,
                work_dir=self.work,
                runner=self.runner,
            )

    def verify(self):
        with (
            mock.patch.object(
                self.module.ABC_METHODS,
                "index_swf_methods",
                side_effect=self.runner.index,
            ),
            mock.patch.object(
                self.module,
                "BASE_BEFORE_ABC_SHA256",
                MappingProxyType(dict(self.before_abc)),
            ),
        ):
            return self.module.verify_render_scale(
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
        self.assertEqual(self.before_pcode, dict(report.before_hashes))
        self.assertEqual(self.after_pcode, dict(report.after_hashes))

        replacements = [call for call in self.runner.calls if call[0] == "replace"]
        exports = [call for call in self.runner.calls if call[0] == "export"]
        self.assertEqual(3, len(replacements))
        self.assertGreaterEqual(len(exports), 6)
        self.assertTrue(
            any(
                len(call[1][call[1].index("-selectclass") + 1].split(",")) == 3
                for call in exports
            )
        )
        for site in self.module.RENDER_SITES:
            self.assertIn(site.method_name, self.runner.require_ref_calls)
            expected_body = self.identities[site.method_name][0]
            matching = [
                argv
                for _, argv, _, _ in replacements
                if argv[argv.index("-replace") + 3] == site.class_name
            ]
            self.assertEqual(1, len(matching))
            self.assertEqual(expected_body, int(matching[0][-1]))
        commands = "\n".join(" ".join(argv).lower() for _, argv, _, _ in self.runner.calls)
        for forbidden in ("apksigner", "zipalign", "keystore", "-importscript", ".as"):
            self.assertNotIn(forbidden, commands)
        self.assertTrue(
            all(appdata == str(self.profile.resolve()) for *_, appdata in self.runner.calls)
        )
        self.assertTrue(
            all(str(self.source.resolve()) not in argv for _, argv, _, _ in self.runner.calls)
        )
        self.assertFalse(any(self.work.iterdir()))

        state = json.loads(self.output.read_text(encoding="utf-8"))
        for site in self.module.RENDER_SITES:
            site.verify(state[site.method_name])

    def test_verify_reopens_all_sites_and_reports_bound_output_hash(self) -> None:
        self.apply()
        report = self.verify()
        digest = hashlib.sha256(self.output.read_bytes()).hexdigest()
        self.assertEqual(digest, report.input_sha256)
        self.assertEqual(digest, report.output_sha256)
        self.assertEqual(self.after_pcode, dict(report.after_hashes))
        self.assertTrue(report.verified)

    def test_lock_schema_is_exact_and_base_specific(self) -> None:
        with mock.patch.object(
            self.module,
            "BASE_BEFORE_ABC_SHA256",
            MappingProxyType(dict(self.before_abc)),
        ):
            sites = self.module._site_locks(self.lock)
        self.assertEqual(EXPECTED_SITES, tuple(sites))
        self.assertTrue(all(set(entry) == LOCK_FIELDS for entry in sites.values()))

        bad = json.loads(json.dumps(self.lock))
        bad["render_sites"][EXPECTED_SITES[0]]["unexpected"] = "field"
        with (
            mock.patch.object(
                self.module,
                "BASE_BEFORE_ABC_SHA256",
                MappingProxyType(dict(self.before_abc)),
            ),
            self.assertRaises(self.module.RenderScaleError),
        ):
            self.module._site_locks(bad)

        bad = json.loads(json.dumps(self.lock))
        bad["render_site_ids"].reverse()
        with self.assertRaises(self.module.RenderScaleError):
            self.module._site_locks(bad)

    def test_stage_rejects_before_and_after_raw_abc_lock_mismatches(self) -> None:
        first = EXPECTED_SITES[0]
        self.lock["render_sites"][first]["before_abc_sha256"] = "0" * 64
        with self.assertRaises(self.module.RenderScaleError):
            self.apply()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.runner.calls)

        self.lock["render_sites"][first]["before_abc_sha256"] = self.before_abc[first]
        self.lock["render_sites"][first]["after_abc_sha256"] = "0" * 64
        with self.assertRaises(self.module.RenderScaleError):
            self.apply()
        self.assertFalse(self.output.exists())
        self.assertTrue(any(kind == "replace" for kind, *_ in self.runner.calls))

    def test_stage_rejects_canonical_pcode_lock_mismatch(self) -> None:
        first = EXPECTED_SITES[0]
        self.lock["render_sites"][first]["before_pcode_sha256"] = "0" * 64
        with self.assertRaises(self.module.RenderScaleError):
            self.apply()
        self.assertFalse(self.output.exists())

    def test_stage_is_exclusive_and_preserves_existing_output(self) -> None:
        self.output.write_bytes(b"external-sentinel")
        with self.assertRaises(self.module.RenderScaleError):
            self.apply()
        self.assertEqual(b"external-sentinel", self.output.read_bytes())
        self.assertFalse(self.runner.calls)

    def test_member_constructor_is_extracted_without_a_trait(self) -> None:
        site = self.module.RENDER_SITES[1]
        root = self.root / "constructor-export"
        target = root / "scripts" / Path(*site.class_name.split(".")).with_suffix(
            ".pcode"
        )
        target.parent.mkdir(parents=True)
        block = self.initial[site.method_name]
        target.write_text(
            "public function MemberView()\n{\n"
            + textwrap.indent(block, "   ")
            + "}\n",
            encoding="utf-8",
        )
        extracted = self.module._read_exported_method(root, site)
        self.assertEqual(
            self.module.canonical_pcode(block),
            self.module.canonical_pcode(extracted),
        )

    def test_member_constructor_extraction_does_not_fall_through_to_next_method(self) -> None:
        site = self.module.RENDER_SITES[1]
        root = self.root / "broken-constructor-export"
        target = root / "scripts" / Path(*site.class_name.split(".")).with_suffix(
            ".pcode"
        )
        target.parent.mkdir(parents=True)
        target.write_text(
            "public function MemberView()\n{\n}\n"
            "public function unrelated()\n{\n"
            '   trait method QName(PackageNamespace(""),"unrelated")\n'
            "      method\n"
            "      end ; method\n"
            "}\n",
            encoding="utf-8",
        )
        with self.assertRaises(self.module.RenderScaleError):
            self.module._read_exported_method(root, site)


if __name__ == "__main__":
    unittest.main()
