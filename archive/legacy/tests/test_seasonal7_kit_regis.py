"""雷吉斯 kit 的纯函数与特效换色钩子（需要 live store / 官方基线的用例自动跳过）。

- fx manifest 三种写法解析、缺文件报错、越界 sheet 报错；
- 换色钩子：尺寸不符报错；按 manifest 替换后包内 sheet 像素 = 染色 PNG（临时 workspace，不碰真实包）；
- kit-report 状态只在 gates.json 全过且指纹一致时为 ready-for-review；换色未落包 / 缺 manifest 时强制 draft；
- recolor_problems：审查复现态（manifest 已出、包内仍母本原色）、report 陈旧、alpha 被改、manifest 不全；
- 指纹换色输入随染色 PNG 字节变化；未跟踪 work/ 输入清单；移植的设计期静态校验与原模块逐字相同；
- 严格树比较区分 int/float；面板禁词（含第二轮规则①的「无上限」族）；
- 第二轮改版（2026-09-16 晚）：rev2_panel_text 删「（无上限）」并给主位键逐行补 <icon id='main'>、
  主位限制 c1 与面板 Ⓜ 双向一致（main_slot_panel_problems）、ChangeSkillFlag 规则②空过断言、
  叠加后行的其余 125 格与固有上限 99 不变；
- 改版（2026-09-16）：revision_rows 适配器形状/行数、固有状态行（上限 99 / 入棺不清除）、
  apply_revision 的 D1–D5 增量与参考树逐节点相等、Bind/vlv 的 int/float 形状、图标 48×48 与 alpha；
- 像素小人：产物就绪判定（report/复核/sha 漂移）、装包幂等与母本字节负向对照（临时 workspace）。
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_assets  # noqa: E402
import wf_seasonal7_build as B  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402
import wf_seasonal7_kit_regis as K  # noqa: E402
import wf_seasonal7_specs as S  # noqa: E402


def _png_bytes(size=(4, 3), color=(10, 20, 30, 255)) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, format="PNG")
    return buf.getvalue()


class _Ctx:
    png_open = staticmethod(C.png_open)


def _live_available() -> bool:
    try:
        pack = C.S7Pack(S.get_spec("regis", with_kit=False))
        return pack.store.is_dir() and pack.official_read(
            "battle/effect/skill_unique/rec_android/rec_android.atlas.amf3.deflate") is not None
    except Exception:
        return False


class FxManifestTests(unittest.TestCase):
    def _write(self, root: Path, payload) -> Path:
        path = root / K.FX_MANIFEST_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_absent_manifest_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(K.load_fx_manifest(Path(tmp)), ({}, None))

    def test_three_layouts(self):
        sheet = "battle/effect/skill_unique/rec_android/rec_android.png"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for payload in ({sheet: "dyed.png"}, {"sheets": {sheet: "dyed.png"}},
                            {"sheets": [{"source": sheet, "png": "dyed.png"}]}):
                path = self._write(root, payload)
                (path.parent / "dyed.png").write_bytes(_png_bytes())
                mapping, info = K.load_fx_manifest(root)
                self.assertEqual(list(mapping), [sheet])
                self.assertEqual(mapping[sheet], path.parent / "dyed.png")
                self.assertEqual(info["entries"], 1)

    def test_missing_png_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(Path(tmp), {"battle/effect/skill_unique/rec_android/rec_android.png": "nope.png"})
            with self.assertRaises(K.KitError):
                K.load_fx_manifest(Path(tmp))

    def test_transform_rejects_size_mismatch_and_logs(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            dyed = Path(tmp) / "d.png"
            dyed.write_bytes(wf_assets.png_encode(_png_bytes((4, 3), (1, 2, 3, 128))))   # 存储态魔数也接受
            log: list = []
            fn = K.recolor_transform(_Ctx(), "s.png", {"s.png": dyed}, log)
            out = fn(Image.new("RGBA", (4, 3), (0, 0, 0, 255)))
            self.assertEqual(out.getpixel((0, 0)), (1, 2, 3, 128))
            self.assertEqual(log[0]["alpha_pixels_changed"], 12)
            with self.assertRaises(K.KitError):
                fn(Image.new("RGBA", (5, 3)))
            self.assertIsNone(K.recolor_transform(_Ctx(), "other.png", {"s.png": dyed}, log))


class _FakePack:
    """recolor_problems 只用到 pkg_has / pkg_path / template_asset。"""

    def __init__(self, base: Path, donors: dict[str, bytes]):
        self.base, self.donors = base, donors

    def pkg_path(self, root: str, logical: str) -> Path:
        return self.base / root / logical

    def pkg_has(self, root: str, logical: str) -> bool:
        return self.pkg_path(root, logical).is_file()

    def template_asset(self, logical: str):
        return "common", self.donors[logical], "official"


class _FakeCtx:
    png_open = staticmethod(C.png_open)

    def __init__(self, root: Path, pack: _FakePack):
        self.root, self.pack = root, pack


class RecolorFreshnessTests(unittest.TestCase):
    """审查 major/minor：染色产物晚于 kit 出现时，包内 sheet 仍是母本原色，旧指纹与状态都看不出来。"""

    def setUp(self):
        from PIL import Image
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.sheets = K.family_sheets()
        self.donor_img, self.dyed_img, donors = {}, {}, {}
        for i, src in enumerate(self.sheets):
            alpha = Image.new("L", (6, 4), 0)
            alpha.putpixel((1, 1), 255)
            alpha.putpixel((2 + i, 2), 128)
            donor = Image.new("RGBA", (6, 4), (0, 255, 255, 255))
            donor.putalpha(alpha)
            dyed = Image.new("RGBA", (6, 4), (242, 193, 78, 255))
            dyed.putalpha(alpha)
            self.donor_img[src], self.dyed_img[src] = donor, dyed
            donors[src] = C.png_store_bytes(donor)
        self.ctx = _FakeCtx(self.root, _FakePack(self.root / "pkg", donors))

    def tearDown(self):
        self.tmp.cleanup()

    def _manifest(self, sheets=None, **extra):
        out = (self.root / K.FX_MANIFEST_REL).parent
        out.mkdir(parents=True, exist_ok=True)
        mapping = {}
        for src in (sheets if sheets is not None else self.sheets):
            path = out / src.replace("/", "__")
            self.dyed_img[src].save(path)
            mapping[src] = str(path)
        (out / "manifest.json").write_text(json.dumps({"sheets": mapping, **extra}), encoding="utf-8")

    def _package(self, which: str):
        for src, dst in self.sheets.items():
            path = self.ctx.pack.pkg_path("common", dst)
            path.parent.mkdir(parents=True, exist_ok=True)
            img = self.dyed_img[src] if which == "dyed" else self.donor_img[src]
            path.write_bytes(C.png_store_bytes(img))

    def _report(self):
        fx_map, info = K.load_fx_manifest(self.root)
        return {"effects": {"fx_manifest": info,
                            "recolor": [{"source_sheet": s, "png_sha256": info["png_sha256"][s]} for s in fx_map]}}

    def test_manifest_absent_blocks(self):
        self._package("donor")
        probs = K.recolor_problems(self.ctx)
        self.assertTrue(probs and "absent" in probs[0])
        self.assertEqual(K.fx_input_state(self.root), None)

    def test_review_state_donor_sheets_with_manifest_is_caught(self):
        self._manifest()
        self._package("donor")
        probs = K.recolor_problems(self.ctx)
        self.assertEqual(len([p for p in probs if "still donor colours" in p]), 2, probs)

    def test_applied_recolor_passes_and_report_freshness_checked(self):
        self._manifest()
        self._package("dyed")
        self.assertEqual(K.recolor_problems(self.ctx), [])
        self.assertEqual(K.recolor_problems(self.ctx, report=self._report()), [])
        stale = {"effects": {"fx_manifest": None, "recolor": []}}
        probs = K.recolor_problems(self.ctx, report=stale)
        self.assertTrue(any("fx_manifest sha256" in p for p in probs))
        self.assertEqual(len([p for p in probs if "lacks" in p]), 2)

    def test_sheet_bytes_override_and_alpha_change(self):
        from PIL import Image
        self._manifest()
        self._package("dyed")
        src, dst = next(iter(self.sheets.items()))
        donor_raw = self.ctx.pack.template_asset(src)[1]
        self.assertTrue(K.recolor_problems(self.ctx, sheet_bytes={dst: donor_raw}))
        bad = self.dyed_img[src].copy()
        bad.putalpha(Image.new("L", bad.size, 255))
        probs = K.recolor_problems(self.ctx, sheet_bytes={dst: C.png_store_bytes(bad)})
        self.assertTrue(any("alpha differs" in p for p in probs), probs)

    def test_partial_manifest_blocks(self):
        first = next(iter(self.sheets))
        self._manifest(sheets=[first])
        self._package("dyed")
        self.assertTrue(any("does not cover" in p for p in K.recolor_problems(self.ctx)))

    def test_fx_input_state_changes_with_png_bytes(self):
        self._manifest()
        before = K.fx_input_state(self.root)
        src = next(iter(self.sheets))
        Path(K.load_fx_manifest(self.root)[0][src]).write_bytes(_png_bytes((6, 4), (1, 1, 1, 255)))
        after = K.fx_input_state(self.root)
        self.assertEqual(before["manifest_sha256"], after["manifest_sha256"])
        self.assertNotEqual(before["png_sha256"][src], after["png_sha256"][src])

    def test_gates_false_manifest_rejected(self):
        self._manifest(gates_ok=False)
        with self.assertRaises(K.KitError):
            K.load_fx_manifest(self.root)

    def test_clone_section_must_match_families(self):
        self._manifest(clone=[{"src": s, "dst": d, "fx_names": sorted(b)} for (s, d), (_x, _y, b)
                              in zip(self.sheets.items(), K.EFFECT_FAMILIES)])
        self.assertEqual(K.fx_manifest_clone_problems(self.root), [])
        src = next(iter(self.sheets))
        self._manifest(clone=[{"src": src, "dst": "battle/effect/skill_unique/rec_android_seaside_beam/x.png"}])
        self.assertTrue(K.fx_manifest_clone_problems(self.root))


class UntrackedInputsTests(unittest.TestCase):
    def test_lists_missing_work_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(len(K.untracked_input_problems(root)), 7)
            for rel in (K.DESIGN_REL, K.DESIGN_TREE_REL.format(level="1"), K.DESIGN_TREE_REL.format(level="2"),
                        K.REVISION_REL, K.REV_TREE_REL.format(level="1"), K.REV_TREE_REL.format(level="2"),
                        K.OFFICIAL_SIG_REL):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text("{}", encoding="utf-8")
            self.assertEqual(K.untracked_input_problems(root), [])
            with self.assertRaises(K.KitError):
                K.load_official_sig(root / "nowhere")

    def test_ported_checker_matches_design_blueprint(self):
        """移植的 blueprint_check 与 research/_tmp/blueprint_build.check 输出逐字相同（子进程：原模块会换 stdout）。"""
        import subprocess
        root = Path(__file__).resolve().parents[2]
        bp = root / K.BATCH / "research/_tmp/blueprint_build.py"
        if not bp.is_file() or not (root / K.DESIGN_TREE_REL.format(level="1")).is_file():
            self.skipTest("design _tmp blueprint / final trees absent")
        script = (
            "import sys, json, copy\n"
            f"sys.path.insert(0, {str(root / 'mod-tools')!r}); sys.path.insert(0, {str(bp.parent)!r})\n"
            "import wf_seasonal7_kit_regis as K\n"          # 先导入被测模块：blueprint_build 会把 cwd 下 mod-tools 插到 sys.path 首位
            "import blueprint_build as BP\n"
            "from pathlib import Path\n"
            f"root = Path({str(root)!r}); sig = K.load_official_sig(root)\n"
            "trees = [json.loads((root / K.DESIGN_TREE_REL.format(level=lv)).read_text(encoding='utf-8')) for lv in '12']\n"
            "t = copy.deepcopy(trees[0])\n"
            "for c in K.iter_commands(t, 'CreateNormalAttack'):\n"
            "    c[1] = 99 if c[1] == 11 else c[1]\n"
            "trees += [t, BP.blueprint_a(), BP.blueprint_b(), BP.blueprint_c()]\n"
            "out = [[list(BP.check(x)[0]), K.blueprint_check_with_sig(x, sig)[0]] for x in trees]\n"
            "print(json.dumps(out, ensure_ascii=False))\n")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        proc = subprocess.run([sys.executable, "-c", script], cwd=root, capture_output=True, env=env, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        pairs = json.loads(proc.stdout.decode("utf-8").strip().splitlines()[-1])
        for original, ported in pairs:
            self.assertEqual(original, ported)
        self.assertEqual(pairs[0][1], [])
        self.assertTrue(pairs[2][1], "negative control (scope 99) must be caught")


class StatusAndHelpersTests(unittest.TestCase):
    def test_blockers_force_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / K.GATES_REL
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"all_pass": True, "kit_fingerprint": "abc"}), encoding="utf-8")
            self.assertEqual(K.gates_status(root, "abc", ["fx manifest absent"])[0], "draft")
            self.assertEqual(K.gates_status(root, "abc", [])[0], "ready-for-review")

    def test_gates_status_requires_matching_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(K.gates_status(root, "abc")[0], "draft")
            path = root / K.GATES_REL
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"all_pass": True, "kit_fingerprint": "abc"}), encoding="utf-8")
            self.assertEqual(K.gates_status(root, "abc")[0], "ready-for-review")
            self.assertEqual(K.gates_status(root, "xyz")[0], "draft")
            path.write_text(json.dumps({"all_pass": False, "kit_fingerprint": "abc"}), encoding="utf-8")
            self.assertEqual(K.gates_status(root, "abc")[0], "draft")

    def test_strict_equal_distinguishes_int_float_bool(self):
        self.assertTrue(K.strict_equal([{"min": 1.0}], [{"min": 1.0}]))
        self.assertFalse(K.strict_equal([{"min": 1}], [{"min": 1.0}]))
        self.assertFalse(K.strict_equal([True], [1]))
        self.assertIn("$[0].min", K.first_difference([{"min": 1}], [{"min": 1.0}]))

    def test_panel_forbidden_words(self):
        self.assertTrue(K.panel_text_problems("自身为队长时，攻击力＋10%"))
        self.assertTrue(K.panel_text_problems("生命值100%以下时"))
        self.assertEqual(K.panel_text_problems("雷属性共鸣时，FEVER时间＋50%"), [])
        # 第二轮规则①：面板不许出现「无上限」，也不许换成「可无限叠加」之类的说法
        self.assertTrue(K.panel_text_problems("每层「浪涌充能」，自身攻击力＋150%（无上限）"))
        self.assertTrue(K.panel_text_problems("每层「浪涌充能」，自身攻击力＋150%，可无限叠加"))
        self.assertEqual(K.panel_text_problems("每层「浪涌充能」，自身攻击力＋150%"), [])
        # 有上限的照旧要写出来
        self.assertEqual(K.panel_text_problems("雷属性角色能力伤害＋10%（最多10次）"), [])

    def test_texts_constant_matches_design_and_revision(self):
        root = Path(__file__).resolve().parents[2]
        if not (root / K.DESIGN_REL).is_file() or not (root / K.REVISION_REL).is_file():
            self.skipTest("design / revision json absent")
        design = K.load_design(root)
        revision = K.revision_rows(K.load_revision(root))
        self.assertEqual(K.check_texts_constant(design, revision), [])
        rows = K.design_text_rows(design, revision)
        self.assertEqual(rows["character_text"][5], revision["skill_desc"])
        self.assertEqual(rows["character_text"][7], revision["skill_desc"])
        self.assertEqual([v[1] for v in rows["action"].values()],
                         [revision["skill_desc"], revision["skill_desc"]])
        self.assertEqual(len(revision["skill_desc"].split("\n")), 3)
        # 面板禁词不得出现在任何一条覆盖文案里
        for item in revision["custom_strings"]:
            self.assertEqual(K.panel_text_problems(item["text"]), [], item["key"])

    def test_rev2_panel_text_drops_the_no_cap_clause(self):
        """规则①：删「（无上限）」，句子写到效果为止，后面什么都不跟。"""
        got = K.rev2_panel_text(K.CAS_KEYS[0], "雷属性角色能力伤害＋150%（无上限）\n第二行")
        self.assertEqual(got, "雷属性角色能力伤害＋150%\n第二行")
        self.assertEqual(K.panel_text_problems(got), [])

    def test_rev2_panel_text_tags_main_slot_keys_only(self):
        """能力 1 / 3 是主位限制键：覆盖文案整段替换官方生成器 ⇒ Ⓜ 必须写进文本，每行都要有。"""
        self.assertEqual(K.rev2_main_slot_cas_keys(), (K.CAS_KEYS[1], K.CAS_KEYS[3]))
        got = K.rev2_panel_text(K.CAS_KEYS[1], "战斗开始时，自身技能槽＋50%\n自身「浪涌充能」＋1层（无上限）")
        self.assertEqual(got.split("\n"),
                         [K.MAIN_ICON + "战斗开始时，自身技能槽＋50%",
                          K.MAIN_ICON + "自身「浪涌充能」＋1层"])
        # 幂等：已经带 Ⓜ 的行不再重复加
        self.assertEqual(K.rev2_panel_text(K.CAS_KEYS[1], got), got)
        # 非主位键不加
        self.assertEqual(K.rev2_panel_text(K.CAS_KEYS[2], "雷属性角色攻击力＋100%"), "雷属性角色攻击力＋100%")

    def test_rev2_skill_flag_problems_flags_change_skill_rows(self):
        """规则②在本角色空过，但 ChangeSkillFlag 行一旦出现必须被门禁点名。"""
        row = ["x"] * 126
        self.assertEqual(K.rev2_skill_flag_problems("ability", row), [])
        row[47] = "536"
        self.assertTrue(K.rev2_skill_flag_problems("ability", row))
        lrow = ["x"] * 124
        lrow[107] = "704"
        self.assertTrue(K.rev2_skill_flag_problems("leader_ability", lrow))
        self.assertEqual(K.rev2_skill_flag_problems("leader_ability", ["x"] * 124), [])

    def test_main_slot_panel_problems_both_directions(self):
        def rows(c1_by_slot):
            return {f"{K.CID}{slot}": [["code", c1] + ["x"] * 124] for slot, c1 in c1_by_slot.items()}

        def cas(texts):
            return {k: [[v]] for k, v in texts.items()}

        good_rows = rows({1: "false", 2: "true", 3: "false", 4: "true", 5: "true", 6: "true"})
        good_cas = cas({K.CAS_KEYS[1]: K.MAIN_ICON + "一行", K.CAS_KEYS[2]: "一行",
                        K.CAS_KEYS[3]: K.MAIN_ICON + "一行\n" + K.MAIN_ICON + "二行",
                        K.CAS_KEYS[4]: "一行", K.CAS_KEYS[5]: "一行", K.CAS_KEYS[6]: "一行"})
        self.assertEqual(K.main_slot_panel_problems(good_rows, good_cas), [])
        # 主位键漏了 Ⓜ
        bad_cas = dict(good_cas, **{K.CAS_KEYS[3]: [[K.MAIN_ICON + "一行\n二行"]]})
        self.assertTrue(any("lack" in p for p in K.main_slot_panel_problems(good_rows, bad_cas)))
        # 非主位键多了 Ⓜ
        bad_cas2 = dict(good_cas, **{K.CAS_KEYS[2]: [[K.MAIN_ICON + "一行"]]})
        self.assertTrue(any("not a main-slot" in p for p in K.main_slot_panel_problems(good_rows, bad_cas2)))
        # 能力 1 忘了加主位限制
        bad_rows = rows({1: "true", 2: "true", 3: "false", 4: "true", 5: "true", 6: "true"})
        self.assertTrue(any("main_only=True" in p for p in K.main_slot_panel_problems(bad_rows, good_cas)))

    def test_skill_desc_covers_every_effect_in_the_tree(self):
        """说明 / 树 / upskill 标签三方一致（审查 20260916 minor 7 的回归闸）。"""
        tree = ["X", ["Block", [["Command", ["AddFeverPoint", [{"min": 80, "max": 80}]]],
                                ["Command", ["CreateCondition", -17,
                                             [["ACAttackPoint", [{"min": 600}], [{"min": 0.5}], [{"min": 1}]]]]],
                                ["Command", ["CreateCondition", 12,
                                             [["ACAbilityDamage", [{"min": 900}], [{"min": 1.5}], [{"min": 1}]]]]]]]]
        up = ["common_attack_up", "condition_attack_up", "ability_damage_up",
              "condition_add_fever_point_up", "(None)", "(None)"]
        self.assertEqual(K.skill_effect_tokens(tree),
                         {"AddFeverPoint", "ACAttackPoint", "ACAbilityDamage"})
        self.assertEqual(K.skill_desc_coverage_problems([tree], K.SKILL_DESC, up), [])
        # 审查发现的那版说明（漏写攻击力 / FEVER 槽）必须报两条
        short = ("向最近的敌人释放激光炮与光束，造成雷属性伤害（FEVER模式中威力提升）\n"
                 "发动时赋予雷属性角色能力伤害提升效果\n"
                 "伤害以能力伤害判定；每层「浪涌充能」威力＋10倍")
        probs = K.skill_desc_coverage_problems([tree], short, up)
        self.assertTrue(any("'攻击力'" in p for p in probs), probs)
        self.assertTrue(any("'FEVER槽'" in p for p in probs), probs)
        # 反向：树里没有的效果却挂着标签
        bare = ["X", ["Block", [["Command", ["CreateCondition", 12,
                                             [["ACAbilityDamage", [{"min": 900}], [{"min": 1.5}], [{"min": 1}]]]]]]]]
        probs2 = K.skill_desc_coverage_problems([bare], K.SKILL_DESC, up)
        self.assertTrue(any("condition_attack_up" in p and "no matching effect" in p for p in probs2), probs2)
        # 未知标签也要报
        probs3 = K.skill_desc_coverage_problems([tree], K.SKILL_DESC, up + ["something_else_up"])
        self.assertTrue(any("something_else_up" in p for p in probs3), probs3)

    def test_skill_desc_constant_covers_package_effects(self):
        """常量 SKILL_DESC 本身必须覆盖三个效果（不依赖 live）。"""
        tree = ["X", ["Block", [["Command", ["AddFeverPoint", [{"min": 1}]]],
                                ["Command", ["CreateCondition", -17, [["ACAttackPoint"]]]],
                                ["Command", ["CreateCondition", 12, [["ACAbilityDamage"]]]]]]]
        self.assertEqual(K.skill_desc_coverage_problems([tree], K.SKILL_DESC), [])
        self.assertEqual(len(K.SKILL_DESC.split("\n")), 3)

    def test_texts_constant_catches_drift(self):
        root = Path(__file__).resolve().parents[2]
        if not (root / K.DESIGN_REL).is_file() or not (root / K.REVISION_REL).is_file():
            self.skipTest("design / revision json absent")
        design = K.load_design(root)
        revision = dict(K.revision_rows(K.load_revision(root)))
        revision["skill_desc"] = revision["skill_desc"] + "X"
        probs = K.check_texts_constant(design, revision)
        self.assertTrue(any("desc1" in p for p in probs), probs)
        self.assertIn("SKILL_DESC != revision plan action_skill c1", probs)


class RevisionPlanTests(unittest.TestCase):
    """改版方案适配器：行数、键、固有状态、面板文案。"""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        if not (cls.root / K.REVISION_REL).is_file():
            raise unittest.SkipTest("revision plan absent")
        cls.plan = K.load_revision(cls.root)
        cls.rev = K.revision_rows(cls.plan)

    def test_shape(self):
        self.assertEqual(len(self.rev["leader"]), 6)
        self.assertEqual(self.rev["ability_record_count"], 16)
        self.assertEqual(sorted(self.rev["abilities"]), [f"slot{i}" for i in range(1, 7)])
        self.assertEqual([len(self.rev["abilities"][f"slot{i}"]) for i in range(1, 7)], [3, 2, 5, 1, 2, 3])
        self.assertEqual(sorted(x["key"] for x in self.rev["custom_strings"]), sorted(K.CAS_KEYS))
        for entry in self.rev["leader"]:
            self.assertEqual(len(entry["row_built"]), 124)
        for slot in range(1, 7):
            for entry in self.rev["abilities"][f"slot{slot}"]:
                self.assertEqual(len(entry["row_built"]), 126)
                self.assertEqual(entry["row_built"][0], f"{K.CODE}_{slot}")

    def test_revision2_layer_is_applied_on_top_of_the_plan(self):
        """第二轮增量（能力 1 主位限制 + 文案规则①）必须已经叠在 plan 解析结果上。"""
        rev2 = self.rev["revision2"]
        self.assertEqual(sorted(rev2["main_slot_ability_keys"]), [f"{K.CID}1", f"{K.CID}3"])
        for slot in range(1, 7):
            want = "false" if slot in K.REV2_MAIN_SLOT_SLOTS else "true"
            for e in self.rev["abilities"][f"slot{slot}"]:
                self.assertEqual(e["row_built"][1], want, f"slot{slot}#{e['record']}")
                if slot in K.REV2_MAIN_SLOT_SLOTS:
                    self.assertEqual(e["edits"]["1"], "false")
        # 文案：全部覆盖键零「无上限」、零禁词；主位键每行带 Ⓜ、非主位键一行都不带
        for item in self.rev["custom_strings"]:
            self.assertNotIn("无上限", item["text"], item["key"])
            self.assertEqual(K.panel_text_problems(item["text"]), [], item["key"])
            tagged = [ln.startswith(K.MAIN_ICON) for ln in item["text"].split("\n")]
            if item["key"] in K.rev2_main_slot_cas_keys():
                self.assertTrue(all(tagged), item["key"])
            else:
                self.assertFalse(any(tagged), item["key"])
        self.assertNotIn("无上限", self.rev["skill_desc"])

    def test_revision2_does_not_touch_the_plan_baseline(self):
        """机制不动：删的只是「（无上限）」四个字 + 加 Ⓜ，行的其余 125 格与固有上限都不变。"""
        plan_rows = {e["record"]: e["row_built"]
                     for e in self.plan["tables"]["ability"]["keys"][f"{K.CID}1"]["rows"]}
        for e in self.rev["abilities"]["slot1"]:
            before, after = plan_rows[e["record"]], e["row_built"]
            self.assertEqual([i for i, (a, b) in enumerate(zip(before, after)) if a != b], [1])
        self.assertEqual(self.rev["unique_conditions"][0]["row_built"][4], "99")
        plan_text = self.plan["tables"]["custom_ability_string"]["rows"]
        for item in self.rev["custom_strings"]:
            stripped = item["text"].replace(K.MAIN_ICON, "")
            want = plan_text[item["key"]].replace("（无上限）", "").replace(K.MAIN_ICON, "")
            self.assertEqual(stripped, want, item["key"])

    def test_unique_condition_entry(self):
        u = self.rev["unique_conditions"]
        self.assertEqual(len(u), 1)
        self.assertEqual(u[0]["key"], K.UID)
        self.assertEqual(u[0]["icon"], K.ICON_LOGICAL)
        row = u[0]["row_built"]
        self.assertEqual(len(row), 15)
        self.assertEqual(row[1], K.UNIQUE_NAME)
        self.assertEqual(row[2], K.ICON_ROW_PATH)
        self.assertEqual(row[4], "99")            # 无上限的官方写法；(None) = 上限 1
        self.assertNotEqual(row[4], "(None)")
        self.assertEqual(row[13], "false")        # 入棺不清除

    def test_plan_rejects_foreign_identity(self):
        import copy as _copy
        bad = _copy.deepcopy(self.plan)
        bad["tables"]["leader_ability"]["rows"][0]["key"] = "139995"
        with self.assertRaises(K.KitError):
            K.revision_rows(bad)
        bad2 = _copy.deepcopy(self.plan)
        bad2["tables"]["ability"]["keys"]["1399943"]["new_row_count"] = 4
        with self.assertRaises(K.KitError):
            K.revision_rows(bad2)


class RevisionSkillTests(unittest.TestCase):
    """apply_revision 的 D1–D5：从上一轮定稿树出发必须逐节点等于改版参考树。"""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        for rel in (K.DESIGN_TREE_REL.format(level="1"), K.REV_TREE_REL.format(level="1")):
            if not (cls.root / rel).is_file():
                raise unittest.SkipTest("design / revision trees absent")

    def _trees(self, level):
        base = json.loads((self.root / K.DESIGN_TREE_REL.format(level=level)).read_text(encoding="utf-8"))
        want = json.loads((self.root / K.REV_TREE_REL.format(level=level)).read_text(encoding="utf-8"))
        return base, want

    def test_apply_revision_reproduces_reference_tree(self):
        for level in ("1", "2"):
            base, want = self._trees(level)
            edits = K.apply_revision(base, level)
            self.assertIsNone(K.first_difference(base, want), level)
            self.assertEqual(len(edits), 5, edits)

    def test_bind_and_vlv_shapes(self):
        base, _ = self._trees("2")
        K.apply_revision(base, "2")
        binds = list(K.iter_commands(base, "BindConditionAccumulationVariable"))
        self.assertEqual(len(binds), 2)
        for c in binds:
            self.assertEqual(c[1], -17)
            self.assertEqual(c[3], ["DCUnique", int(K.UID)])
            self.assertIsInstance(c[3][1], int)
            self.assertIsInstance(c[4], int)             # 除数是 int
            self.assertIsInstance(c[5], float)           # 上限是 double（AMF3 编码不同）
        grown = [c[6][0] for c in K.iter_commands(base, "CreateNormalAttack") if "vlv" in c[6][0]]
        self.assertEqual(len(grown), 2)
        for cell in grown:
            self.assertIsInstance(cell["min"], float)
            self.assertIsInstance(cell["max"], float)
            self.assertEqual(cell["vlv"][0]["max"], K.REV_GROWTH)
            self.assertIsInstance(cell["vlv"][0]["vid"], int)

    def test_totals_match_the_plan(self):
        if not (self.root / K.REVISION_REL).is_file():
            self.skipTest("revision plan absent")
        totals = K.load_revision(self.root)["skill_dsl"]["totals"]
        for level in ("1", "2"):
            base, _ = self._trees(level)
            K.apply_revision(base, level)
            cfm = K.cmd(base[11][1][1])
            got = {}
            for label, blk in (("fever", cfm[1]), ("normal", cfm[2])):
                acc = [0.0, 0.0]
                for c in K.iter_commands(blk, "CreateHitArea"):
                    n = c[14][1]
                    for a in K.iter_commands(c[23], "CreateNormalAttack"):
                        acc[0] += a[6][0]["min"] * n
                        acc[1] += a[6][0]["max"] * n
                got[label] = [round(v, 3) for v in acc]
            want = totals[level]
            for label in ("fever", "normal"):
                w = want[label]
                self.assertEqual(got[label], [w, w] if isinstance(w, float) else w, (level, label))

    def test_rejects_an_unexpected_branch_layout(self):
        base, _ = self._trees("1")
        cfm = K.cmd(base[11][1][1])
        del cfm[2][1][1]                                  # 删掉通常分支的光束节点
        with self.assertRaises(K.KitError):
            K.apply_revision(base, "1")

    def test_applying_twice_is_caught(self):
        base, want = self._trees("1")
        K.apply_revision(base, "1")
        with self.assertRaises(K.KitError):
            K.apply_revision(base, "1")                    # 分支头已不再是 FindNearSubjects


class UniqueIconTests(unittest.TestCase):
    def test_icon_is_48_and_keeps_the_official_alpha(self):
        from PIL import Image
        frame = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
        px = frame.load()
        for y in range(48):
            for x in range(48):
                edge = x in (0, 47) or y in (0, 47)
                px[x, y] = (0, 0, 0, 0 if (edge and (x + y) % 2 == 0) else 255)
        icon = K.draw_icon(frame)
        self.assertEqual(icon.size, (48, 48))
        self.assertEqual(icon.mode, "RGBA")
        self.assertEqual(icon.getchannel("A").tobytes(), frame.getchannel("A").tobytes())
        self.assertGreater(len({icon.getpixel((x, y))[:3] for x in range(8, 40) for y in range(8, 40)}), 8)

    def test_icon_rejects_a_wrong_sized_frame(self):
        from PIL import Image
        with self.assertRaises(K.KitError):
            K.draw_icon(Image.new("RGBA", (32, 32), (0, 0, 0, 255)))


class PixelInputsTests(unittest.TestCase):
    """像素产物就绪判定：report 门禁 + 复核 verify_all + sha 与盘上一致，任一不符 = pending。"""

    def _stage(self, root: Path, *, gates_passed=True, review_pass=True, drift=None):
        base = root / K.PIXEL_DIR_REL
        (base / "out").mkdir(parents=True, exist_ok=True)
        outputs, detail = {}, {}
        for i, name in enumerate(K.PIXEL_SHEETS):
            raw = _png_bytes((4 + i, 3))
            (base / "out" / f"{name}.png").write_bytes(raw)
            digest = C.sha256(raw)
            outputs[name] = {"sha256": digest}
            detail[name] = {"sha256": digest}
        (base / "report.json").write_text(json.dumps({
            "key": "regis", "gates_passed": gates_passed, "gates": {"G1": {"ok": gates_passed}},
            "outputs": outputs}), encoding="utf-8")
        verify = root / K.PIXEL_VERIFY_REL
        verify.parent.mkdir(parents=True, exist_ok=True)
        verify.write_text(json.dumps({"regis": {"pass": review_pass, "hard": {
            "H1_size": {"ok": review_pass}, "H8_png_roundtrip": {"ok": True, "detail": detail}}}}), encoding="utf-8")
        if drift:
            (base / "out" / f"{drift}.png").write_bytes(_png_bytes((9, 9)))

    def test_absent_report_is_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            pngs, probs = K.pixel_inputs(Path(tmp))
            self.assertEqual(pngs, {})
            self.assertTrue(probs and "absent" in probs[0])

    def test_ready_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._stage(Path(tmp))
            pngs, probs = K.pixel_inputs(Path(tmp))
            self.assertEqual(probs, [])
            self.assertEqual(sorted(pngs), sorted(K.PIXEL_SHEETS))

    def test_gate_or_review_failure_and_sha_drift_block(self):
        for kw, needle in (({"gates_passed": False}, "gates"), ({"review_pass": False}, "review failed"),
                           ({"drift": "sprite_sheet"}, "sha256")):
            with tempfile.TemporaryDirectory() as tmp:
                self._stage(Path(tmp), **kw)
                _pngs, probs = K.pixel_inputs(Path(tmp))
                self.assertTrue(any(needle in p for p in probs), (kw, probs))


def _pixel_ready() -> bool:
    root = Path(__file__).resolve().parents[2]
    try:
        return _live_available() and not K.pixel_inputs(root)[1]
    except Exception:
        return False


@unittest.skipUnless(_pixel_ready(), "live store or reviewed pixel outputs unavailable")
class PixelInstallIntegrationTests(unittest.TestCase):
    def test_install_is_idempotent_and_checks_donor(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = S.get_spec("regis")
            pack = C.S7Pack(spec, workspace=Path(tmp) / "s7-regis")
            B.step_init(pack)
            ctx = B.KitContext(pack)
            prefix = {f"character/{spec.template_code}/": f"character/{spec.code}/"}
            for name, metas in K.PIXEL_SHEETS.items():
                for meta in metas:
                    raw = pack.template_asset(f"character/{spec.template_code}/pixelart/{meta}")[1]
                    pack.write_pkg("common", f"character/{spec.code}/pixelart/{meta}",
                                   C.amf_bytes(C.replace_strings(C.amf_parse(raw), prefix)))
            first = K.install_pixel(ctx)
            self.assertEqual(first["status"], "installed")
            self.assertEqual(K.pixel_problems(ctx), [])
            logical = f"character/{spec.code}/pixelart/sprite_sheet.png"
            mtime = pack.pkg_path("common", logical).stat().st_mtime_ns
            self.assertEqual(K.install_pixel(ctx)["sheets"], first["sheets"])
            self.assertEqual(pack.pkg_path("common", logical).stat().st_mtime_ns, mtime)
            self.assertEqual(pack.owner_of("common", logical), "pixel")
            donor = pack.template_asset(f"character/{spec.template_code}/pixelart/sprite_sheet.png")[1]
            self.assertTrue(K.pixel_problems(ctx, sheet_bytes={logical: donor}))
            # 元数据仍带母本路径（未改写前缀）→ 必须报
            meta = f"character/{spec.code}/pixelart/pixelart.frame.amf3.deflate"
            pack.write_pkg("common", meta, pack.template_asset(
                f"character/{spec.template_code}/pixelart/pixelart.frame.amf3.deflate")[1])
            self.assertTrue(any("metadata" in p for p in K.pixel_problems(ctx)))
            self.assertTrue(str(pack.workspace).startswith(tmp))


@unittest.skipUnless(_live_available(), "live store / official baseline unavailable")
class RecolorCloneIntegrationTests(unittest.TestCase):
    def test_manifest_png_replaces_cloned_sheet(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            spec = S.get_spec("regis")
            pack = C.S7Pack(spec, workspace=Path(tmp) / "s7-regis")
            B.step_init(pack)
            ctx = B.KitContext(pack)
            src_dir, sub, bases = K.EFFECT_FAMILIES[1]
            sheet = f"{src_dir}/rec_android.png"
            _root, raw, _src = pack.template_asset(sheet)
            donor = C.png_open(raw)
            dyed = Image.new("RGBA", donor.size, (200, 150, 50, 255))
            dyed.putalpha(donor.getchannel("A"))
            dyed_path = Path(tmp) / "dyed.png"
            dyed.save(dyed_path)
            log: list = []
            fam = ctx.clone_effect_family(src_dir, sub, fx_names=list(bases),
                                          png_transform=K.recolor_transform(ctx, sheet, {sheet: dyed_path}, log))
            out = C.png_open(pack.pkg_path("common", f"{fam['dst_dir']}/{sub}.png").read_bytes())
            self.assertEqual(out.tobytes(), dyed.tobytes())
            self.assertEqual(log[0]["alpha_pixels_changed"], 0)
            self.assertTrue(str(pack.workspace).startswith(tmp))


if __name__ == "__main__":
    unittest.main()
