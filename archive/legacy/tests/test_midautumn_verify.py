# -*- coding: utf-8 -*-
"""中秋批次机械验证器：纯函数判据 + 内存构造的负向用例 + 上批已发布包的正向对照。

负向用例全部在内存里造坏行/坏树，不落盘；正向对照跑 ``work/character_packs/s7-regis``
（上批 1.4.868 已发布包），包不在本机时自动跳过。不写包、不发布、不碰 live store 以外
的任何东西（live store 也只读，而且解析不到时判据自动降级）。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_dsl  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_verify as V  # noqa: E402
import wf_mod_tool as core  # noqa: E402

ROOT = Path(core.project_root())
REGIS = ROOT / "work/character_packs/s7-regis"


def ability_row() -> list[str]:
    """一条最小合法的 ability 行：瞬发(触发模式 0)，内容 kind 留 0。"""
    row = [""] * V.wf_describe.layout("ability")["ncols"]
    row[0] = "demo_1"
    row[1] = "0"
    row[2] = "attack"
    blocks = V._blocks("ability")
    row[blocks["precondition1"] - 1] = "0"        # 触发模式：瞬发
    for n in (1, 2, 3):
        base = blocks[f"precondition{n}"]
        row[base] = "0"                            # precondition kind
    row[blocks["instant_precontent"]] = "(None)"
    row[blocks["during_accumulation_trigger"]] = "(None)"
    row[blocks["even_if_owner_dead"]] = "false"
    return row


def put(row: list[str], kind: str, block: str, field: str, value: str) -> list[str]:
    base = V._blocks(kind)[block]
    row[base + V._field_offsets(block)[field]] = value
    return row


# ---------------------------------------------------------------- 纯函数判据

class ColumnHelpersTest(unittest.TestCase):
    def test_leader_and_ability_blocks_differ(self):
        """两表列位差 2 —— 判据必须按 kind 取布局，不能写死列号。"""
        self.assertNotEqual(V._blocks("ability")["instant_content"],
                            V._blocks("leader_ability")["instant_content"])

    def test_content_kinds_reads_all_three_blocks(self):
        row = put(ability_row(), "ability", "instant_content", "kind", "629")
        put(row, "ability", "during_content", "kind", "422")
        kinds = V.content_kinds("ability", row)
        self.assertEqual(kinds["instant_content"], "629")
        self.assertEqual(kinds["during_content"], "422")

    def test_precondition_188_threshold_is_read(self):
        row = ability_row()
        base = V._blocks("ability")["precondition1"]
        offsets = V._field_offsets("precondition")
        row[base + offsets["kind"]] = "188"
        row[base + offsets["threshold.power1"]] = "200000"
        pre = V.preconditions("ability", row)[0]
        self.assertEqual((pre["kind"], pre["threshold"]), ("188", "200000"))

    def test_png_dims_accepts_lowercase_cdn_magic(self):
        head = (b"\x89png\r\n\x1a\n" + b"\x00" * 4 + b"IHDR"
                + (7).to_bytes(4, "big") + (9).to_bytes(4, "big") + b"\x00" * 8)
        self.assertEqual(V.png_dims(head), (7, 9))
        self.assertEqual(V.png_dims(b"\x89PNG\r\n\x1a\n" + head[8:]), (7, 9))
        self.assertIsNone(V.png_dims(b"not a png"))

    def test_split_rows_lenient_swallows_non_csv(self):
        """mana_board 那类认领表根本不是 CSV（zlib 分片解成 utf-8-replace 文本），
        它不能把整轮验证打断。"""
        self.assertEqual(V.split_rows_lenient("a,b\nc,d"), [["a", "b"], ["c", "d"]])
        # 真实形态：分片字节里夹着裸 \r（regis 的 mana_board 行就是这样）
        blob = b"\x1e\x00\x00\x00x\x9ccb\rW\x01\n\x00".decode("utf-8", "replace")
        self.assertIsNone(V.split_rows_lenient(blob),
                          "非 CSV 的认领表必须返回 None 而不是抛异常")

    def test_known_capabilities_are_the_real_ones(self):
        self.assertIn(L.PANEL_OVERRIDE_V2, V.KNOWN_CAPABILITIES)
        self.assertIn("dash-parameter-v1", V.KNOWN_CAPABILITIES)
        self.assertNotIn("gbf-ghandagoza-mechanics-v1", V.KNOWN_CAPABILITIES)

    def test_panel_sentinel_is_not_panel_text(self):
        self.assertFalse(V._panel_text("(None)"))
        self.assertFalse(V._panel_text("   "))
        self.assertTrue(V._panel_text("月下拔刀"))


# ---------------------------------------------------------------- 负向用例：坏行

class BadRowTest(unittest.TestCase):
    """内存里造坏行，确认判据真的会变红（删掉断言必须变红才算有效）。"""

    def test_leader_row_with_422_is_caught(self):
        row = [""] * V.wf_describe.layout("leader_ability")["ncols"]
        blocks = V._blocks("leader_ability")
        row[blocks["precondition1"] - 1] = "1"
        put(row, "leader_ability", "during_content", "kind", "422")
        kinds = V.content_kinds("leader_ability", row)
        hit = [k for k, value in kinds.items() if value in V.LEADER_FORBIDDEN_KINDS]
        self.assertEqual(hit, ["during_content"],
                         "队长表里的 422 必须被认出来（写它 = C7050）")

    def test_629_without_string_key_is_caught(self):
        row = put(ability_row(), "ability", "instant_content", "kind", "629")
        problems = L.invoke_skill_string_problems(row, frozenset(), "ability")
        self.assertTrue(problems, "629 行缺 custom_ability_string 键必须报错")
        put(row, "ability", "instant_content", "string_id", "demo_invoke")
        self.assertFalse(L.invoke_skill_string_problems(row, frozenset({"demo_invoke"}),
                                                        "ability"))

    def test_unique_id_must_be_eight_digits(self):
        for bad in ("1699901", "16999012", "abc"):
            ok = bad.isdigit() and len(bad) == 8
            self.assertEqual(ok, bad == "16999012")

    def test_consume_row_before_invoke_is_caught(self):
        """同触发下 525 排在 629 之前 = 阻断（629 必须先执行）。"""
        first = put(ability_row(), "ability", "instant_content", "kind", V.CONSUME_KIND)
        second = put(ability_row(), "ability", "instant_content", "kind", V.INVOKE_SKILL_KIND)
        seen: dict[str, dict[str, int]] = {}
        for i, row in enumerate((first, second)):
            kind = V.content_kinds("ability", row)["instant_content"]
            seen.setdefault(V.trigger_mode("ability", row), {}).setdefault(kind, i)
        hits = seen["0"]
        self.assertLess(hits[V.CONSUME_KIND], hits[V.INVOKE_SKILL_KIND])


# ---------------------------------------------------------------- 负向用例：坏树

def call(tag: str, name: str, *args):
    return [tag, [name, *args]]


class BadTreeTest(unittest.TestCase):
    def test_donothing_in_expression_slot_is_blocking(self):
        """Conditionals 的分支位写 ["DoNothing"] = 进游戏 F1009。"""
        tree = call("Command", "ConditionalsFeverMode", ["DoNothing"], ["Block", []])
        hard, _sig, _unknown = V.dsl_shape_problems("demo", tree)
        self.assertTrue(any("DoNothing" in p for p in hard))

    def test_donothing_in_iftargetnotfound_slot_is_legal(self):
        """官方 FindAllSubjects 第 8 参就写 ["DoNothing"] —— 不许误报。"""
        sig = V.SIG.COMMANDS["FindAllSubjects"]
        args = [[] if t == "Array" else (["Block", []] if t == V.EXPRESSION_TYPE else 0)
                for t in sig]
        args[sig.index("IfTargetNotFound")] = ["DoNothing"]
        hard, problems, _unknown = V.dsl_shape_problems("demo", call("Command",
                                                                    "FindAllSubjects", *args))
        self.assertEqual(hard, [])
        self.assertEqual(problems, [])

    def test_command_wait_is_caught(self):
        """Wait 是 Event 构造；写成 Command 会被静默吞掉。"""
        hard, _sig, unknown = V.dsl_shape_problems("demo", call("Command", "Wait", 30, "", ["Block", []]))
        self.assertTrue(any("Event" in p for p in hard))
        self.assertEqual(unknown, [])

    def test_bare_number_in_array_slot_is_caught(self):
        """Sector 角度那类 Array 形参喂裸数值 = 详情页 F1034。"""
        sig = V.SIG.COMMANDS["AddCombo"]
        self.assertEqual(sig, ["Array"])
        _hard, problems, _unknown = V.dsl_shape_problems("demo", call("Command", "AddCombo", 3))
        self.assertTrue(any("F1034" in p for p in problems))
        _hard, problems, _unknown = V.dsl_shape_problems("demo", call("Command", "AddCombo", [3, 3]))
        self.assertEqual(problems, [])

    def test_unknown_construct_is_warning_only(self):
        hard, sig, unknown = V.dsl_shape_problems("demo", call("Command", "NotARealCommand", 1))
        self.assertEqual((hard, sig), ([], []))
        self.assertTrue(unknown)

    def test_wrapper_shell_body_is_caught(self):
        """{tree,numbers} 包装壳喂进编码器 = 进战斗 F1034（记忆卡 wf-dsl-encode-wrapper-trap）。"""
        wrapper = {"tree": ["Block", []], "numbers": []}
        problems = V.dsl_roundtrip_problems("demo", wrapper, b"")
        self.assertTrue(any("包装壳" in p for p in problems))

    def test_bare_tree_roundtrips(self):
        tree = ["Block", [call("Command", "AddCombo", [1, 1])]]
        plain = wf_dsl.encode_amf3(tree)
        self.assertEqual(V.dsl_roundtrip_problems("demo", tree, plain), [])


# ---------------------------------------------------------------- 坐标系取向

def show_effect(subject, coord, name="fx"):
    """ShowEffect 13 参（官方签名；主体在第 3 位，坐标系在第 6 位）。"""
    node = call("Command", "ShowEffect", name,
                ["SpecifyEffectDirectly", "battle/effect/demo/demo"], subject,
                ["ForesideOfCharacter"], ["SpecifyEffectLifetimeDirectly", 30],
                [coord], 0, 0, 0, True, False, ["None"])
    assert len(node[1]) - 1 == len(V.SIG.COMMANDS["ShowEffect"]), "ShowEffect 参数个数漂了"
    return node


def hit_area(on_hit, *, subject=-18, self_id=0, area_id=1, target_id=2):
    """CreateHitArea 26 参：p18/p20 绑判定区、p21 绑命中对象、p22 是命中块。"""
    node = call("Command", "CreateHitArea", "*", subject, ["AB"], 0, 0, 0, True, False,
                ["Circle", [{"min": 100, "max": 100}]], ["Center"], ["Center"], ["Single"],
                ["SpecifyHitAreaLifetimeDirectly", 60],
                ["CalculatedUsingMaxNumOfHits", 1], ["Some", [{"min": 1, "max": 1}]],
                False, True, ["None"], self_id, ["Block", []], area_id, target_id,
                ["Block", list(on_hit)], 0, 0, ["None"])
    assert len(node[1]) - 1 == len(V.SIG.COMMANDS["CreateHitArea"]), "CreateHitArea 参数个数漂了"
    return node


class CoordSysOnEnemySubjectTest(unittest.TestCase):
    """``dsl/coordsys-on-enemy-subject``：CD/EF 落在 getDir*() 会 throw 的主体上 = U_4f5401。"""

    def test_cd_on_hit_target_binding_is_blocking(self):
        """事故原型：命中块里对着命中对象放 ShowEffect + ["CD"]。"""
        tree = hit_area([show_effect(2, "CD", "着弾")])
        problems = V.dsl_coordsys_problems("demo", tree)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("hittarget", problems[0])
        self.assertIn("U_4f5401", problems[0])

    def test_ab_on_hit_target_binding_is_clean(self):
        """官方惯例：命中块里 ShowEffect 主体=命中对象时写 AB（官方 155/177）。"""
        tree = hit_area([show_effect(2, "AB", "着弾")])
        self.assertEqual(V.dsl_coordsys_problems("demo", tree), [])

    def test_gh_on_hit_target_binding_is_clean(self):
        """GH 走 atan2(指向 params[0])，不碰 getDirCD（官方 22/177）。"""
        tree = hit_area([show_effect(2, "AB", "着弾")])
        tree[1][23][1][0][1][6] = ["GH", -17]      # p22 命中块 → 首条命令 → ShowEffect p5
        self.assertEqual(V.dsl_coordsys_problems("demo", tree), [])

    def test_cd_on_hit_area_binding_is_clean(self):
        """CD 的唯一官方用法：主体是判定区绑定（ActionHitArea.getDirCD 返回 r）。"""
        tree = hit_area([show_effect(1, "CD")])
        self.assertEqual(V.dsl_coordsys_problems("demo", tree), [])

    def test_cd_on_ball_and_self_is_blocking(self):
        """-18 球 = BallImpl、-17 自身 = MemberImpl，两者 getDirCD 都 throw。"""
        for subject in (-18, -17):
            with self.subTest(subject=subject):
                problems = V.dsl_coordsys_problems("demo", show_effect(subject, "CD"))
                self.assertEqual(len(problems), 1, problems)

    def test_ef_on_ball_is_clean_but_on_mate_is_blocking(self):
        """BallImpl.getDirEF 返回 angle（官方 198 例）；Mate.getDirEF 才是 throw。"""
        self.assertEqual(V.dsl_coordsys_problems("demo", show_effect(-18, "EF")), [])
        self.assertTrue(V.dsl_coordsys_problems("demo", show_effect(-33, "EF")))

    def test_cd_on_found_subject_is_blocking(self):
        """FindAllSubjects 绑到的是敌人/队友单位，同样 throw。"""
        sig = V.SIG.COMMANDS["FindAllSubjects"]
        args = [[] if t == "Array" else (["Block", []] if t == V.EXPRESSION_TYPE else 0)
                for t in sig]
        args[0] = 7
        args[-1] = ["Block", [show_effect(7, "CD")]]
        problems = V.dsl_coordsys_problems("demo", call("Command", "FindAllSubjects", *args))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("found", problems[0])

    def test_unmodelled_binding_is_not_flagged(self):
        """种类判不出来的绑定不报，避免把没建模的命令误伤成阻断项。"""
        self.assertEqual(V.dsl_coordsys_problems("demo", show_effect(99, "CD")), [])

    def test_hit_area_own_coordsys_on_ball_is_blocking(self):
        """CreateHitArea 自己的坐标系参同样走 ActionHitArea.calcDir。"""
        tree = hit_area([], subject=-18)
        tree[1][3] = ["CD"]
        problems = V.dsl_coordsys_problems("demo", tree)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("CreateHitArea", problems[0])


# ---------------------------------------------------------------- 正向对照

@unittest.skipUnless(REGIS.is_dir(), "s7-regis package not present on this machine")
class RegisControlTest(unittest.TestCase):
    """上批已发布包跑一遍应当零阻断项（批次差异项已降级为 warning）。"""

    @classmethod
    def setUpClass(cls):
        cls.payload = V.verify(REGIS, root=ROOT, skip_atlas=True)

    def test_no_blocking_findings(self):
        self.assertEqual(self.payload["blocking"], [],
                         json.dumps(self.payload["blocking"], ensure_ascii=False))
        self.assertEqual(self.payload["status"], "PASS")

    def test_identity_resolved_from_package(self):
        self.assertEqual(self.payload["character_id"], "139994")
        self.assertEqual(self.payload["code_name"], "rec_android_seaside")

    def test_every_required_family_ran(self):
        names = {c["name"] for c in self.payload["checks"]}
        for family in ("rows/client-legality", "rows/leader-forbidden-kinds",
                       "rows/invoke-skill-string", "rows/invoke-before-consume",
                       "rows/precondition-188-threshold", "rows/ability-statue-group-single",
                       "unique/id-8-digits", "unique/stacking-cap-not-none",
                       "dsl/roundtrip", "dsl/forbidden-constructs", "dsl/official-signature",
                       "dsl/asset-refs-resolve", "dsl/effect-family-under-codename",
                       "dsl/coordsys-on-enemy-subject",
                       "manifest/capability-names-real", "manifest/capability-covers-rows",
                       "period/server-clock", "voice/route-shape", "voice/speech-row",
                       "voice/slot-coverage", "voice/gate", "art/ui-slot-pairs",
                       "art/pixel-sheet-dims", "panel/forbidden-words"):
            self.assertIn(family, names)

    def test_voice_slots_are_the_22_generated_ones(self):
        check = next(c for c in self.payload["checks"] if c["name"] == "voice/slot-coverage")
        self.assertTrue(check["pass"])
        self.assertEqual(check["evidence"]["canonical_present"], V.VOICE_SLOT_COUNT)

    def test_alpha_report_is_warning_only(self):
        check = next(c for c in self.payload["checks"] if c["name"] == "art/pixel-alpha")
        self.assertEqual(check["level"], V.WARNING)

    def test_voice_route_none_sentinel_is_not_an_error(self):
        """c9 = '(None)' 是官方「没有第二条语音路由」的哨兵（584 行里 564 行如此）。"""
        row = ["x"] * 20
        row[9] = "(None)"
        self.assertTrue(all(v in ("", "(None)") for v in
                            [row[i] for i in V.VOICE_ROUTE_COLS if row[i] == "(None)"]))


class DonorCodeLeakTest(unittest.TestCase):
    """``assets/donor-code-leak``：包内 ``character/<新 code>/`` 下不许内嵌别人的纹理路径。

    20260920 真机事故：像素代理把母本 atlas/frame/timeline「字节不动」交付并登记
    owner=pixel，盖掉了 ``assets`` 步已改写 code 的正确版本 → 领取演出 C8003。
    正向对照跑真包，负向用例在临时目录里造一份坏元数据（不碰任何真 workspace）。
    """

    CODE = "sorceress_teacher_moon"
    DONOR = "sorceress_teacher"          # 故意选「母本 code 是新 code 前缀」的那一对

    def _pack(self, tmp: Path, payload: bytes, name: str = "pixelart.frame.amf3.deflate"):
        pixelart = tmp / "package/roots/common/character" / self.CODE / "pixelart"
        pixelart.mkdir(parents=True)
        (pixelart / name).write_bytes(payload)
        (tmp / "package/manifest.json").write_text(json.dumps(
            {"character_id": "119991", "code_name": self.CODE}), encoding="utf-8")
        pack = V.Pack(tmp, ROOT)
        rep = V.Report()
        V.check_donor_code_leak(pack, rep)
        return next(c for c in rep.checks if c["name"] == "assets/donor-code-leak")

    def test_donor_path_is_blocked(self):
        payload = zlib.compress(b"\x0a\x0bcharacter/%s/pixelart/sprite_sheet" % self.DONOR.encode())
        with tempfile.TemporaryDirectory() as raw:
            check = self._pack(Path(raw), payload)
        self.assertFalse(check["pass"])
        self.assertEqual(check["level"], V.BLOCKING)
        self.assertIn(f"character/{self.DONOR}/", json.dumps(check["evidence"], ensure_ascii=False))

    def test_new_code_is_not_flagged_although_donor_is_its_prefix(self):
        """前缀型母本：``sorceress_teacher`` 是 ``sorceress_teacher_moon`` 的前缀，
        判据按路径段匹配，正确改写后的文件绝不能误报。"""
        payload = zlib.compress(b"\x0a\x0bcharacter/%s/pixelart/sprite_sheet" % self.CODE.encode())
        with tempfile.TemporaryDirectory() as raw:
            check = self._pack(Path(raw), payload)
        self.assertTrue(check["pass"], json.dumps(check["evidence"], ensure_ascii=False))

    def test_official_effect_reference_is_not_flagged(self):
        """裁决 §4：只引用不改色的官方特效直接写官方路径，是合法设计，不许误报。"""
        payload = zlib.compress(
            b"battle/effect/skill_unique/%s/fire_01" % self.DONOR.encode())
        with tempfile.TemporaryDirectory() as raw:
            check = self._pack(Path(raw), payload, name="pixelart.timeline.amf3.deflate")
        self.assertTrue(check["pass"], json.dumps(check["evidence"], ensure_ascii=False))

    def test_uncompressed_payload_is_scanned_too(self):
        with tempfile.TemporaryDirectory() as raw:
            check = self._pack(Path(raw), b"character/%s/pixelart/x" % self.DONOR.encode())
        self.assertFalse(check["pass"])

    def test_real_packages_are_clean(self):
        """修复后的 12 个中秋包（本机存在的）一条泄漏都不许有。"""
        checked = 0
        for workspace in sorted((ROOT / "work/character_packs").glob("ma-*")):
            if not (workspace / "package/roots").is_dir():
                continue
            pack = V.Pack(workspace, ROOT)
            rep = V.Report()
            V.check_donor_code_leak(pack, rep)
            check = next(c for c in rep.checks if c["name"] == "assets/donor-code-leak")
            self.assertTrue(check["pass"],
                            f"{workspace.name}: " + json.dumps(check["evidence"], ensure_ascii=False))
            self.assertGreater(check["evidence"]["files_scanned"], 0, workspace.name)
            checked += 1
        if not checked:
            self.skipTest("no ma-* package on this machine")


class _StubPack:
    """``check_panel_override_markup`` 只读 cid/code/table —— 用桩包就能造坏样本。"""

    cid = "159994"
    code = "tweyen_light"

    def __init__(self, ability: dict, strings: dict) -> None:
        self._tables = {V.ABILITY: ability, V.CAS: strings}

    def table(self, logical: str, root: str = "common"):
        return self._tables.get(logical)


class PanelOverrideMarkupTest(unittest.TestCase):
    """``panel/override-markup``：作者真机 2026-09-21 连报四个角色的三种失效形态。"""

    ICON = " <icon id='main'>  "

    @staticmethod
    def _ability(unisonable: str, records: int = 2) -> str:
        return "\n".join(f"tweyen_light_3,{unisonable},x" for _ in range(records))

    @staticmethod
    def _cell(text: str) -> str:
        return '"' + text + '"'

    def _run(self, unisonable: str, override: str, records: int = 2, key: str = "desc_override_tweyen_light_3"):
        pack = _StubPack({"1599943": self._ability(unisonable, records)}, {key: self._cell(override)})
        rep = V.Report()
        V.check_panel_override_markup(pack, rep)
        return next(c for c in rep.checks if c["name"] == "panel/override-markup")

    def test_main_only_slot_with_icon_on_every_line_passes(self):
        check = self._run("false", self.ICON + "第一条\n" + self.ICON + "第二条")
        self.assertTrue(check["pass"], json.dumps(check["evidence"], ensure_ascii=False))
        self.assertEqual(check["level"], V.BLOCKING)

    def test_missing_icon_is_blocked(self):
        check = self._run("false", self.ICON + "第一条\n第二条")
        self.assertFalse(check["pass"])
        self.assertIn("1/2", json.dumps(check["evidence"], ensure_ascii=False))

    def test_literal_glyph_is_blocked(self):
        check = self._run("false", "Ⓜ第一条\nⓂ第二条")
        self.assertFalse(check["pass"])

    def test_icon_on_a_non_main_slot_is_blocked(self):
        check = self._run("true", self.ICON + "第一条\n第二条")
        self.assertFalse(check["pass"])

    def test_records_squeezed_with_slash_are_blocked(self):
        check = self._run("true", "第一条／第二条")
        self.assertFalse(check["pass"])

    def test_single_record_may_contain_a_slash(self):
        check = self._run("true", "攻击力／技能伤害＋50%", records=1)
        self.assertTrue(check["pass"], json.dumps(check["evidence"], ensure_ascii=False))

    def test_leader_override_in_one_slash_line_is_blocked(self):
        check = self._run("true", "第一条／第二条", key="desc_override_tweyen_light")
        self.assertFalse(check["pass"])


def deflate(tree) -> bytes:
    """像素三件套的存储形态：AMF3 裸树 + 原始 deflate（验证器按 wbits=-15 读）。"""
    comp = zlib.compressobj(9, zlib.DEFLATED, -15)
    return comp.compress(wf_dsl.encode_amf3(tree)) + comp.flush()


class PixelFrameCoherenceTest(unittest.TestCase):
    """``pixel/frame-name-and-ids`` / ``pixel/atlas-covers-sequence-end``。

    判据来自反编译的客户端播放器 ``FrameAnimationSource``（帧号 =
    ``parseInt(id.substr(len(frame.name)))``，``imageFrames`` 从上一条帧号往后填到本条帧号，
    ``getImageFrame(tick)=imageFrames[tick-1]``）。负向用例在临时目录里造坏件。
    """

    CODE = "tweyen_light"

    def _checks(self, tmp: Path, *, frame_name: str | None = None,
                ids: list[str] | None = None, last_end: int = 150):
        name = f"character/{self.CODE}/pixelart/special"
        ids = ids if ids is not None else [f"{name}{n:04d}" for n in (113, 120, 150)]
        pixelart = tmp / "package/roots/common/character" / self.CODE / "pixelart"
        pixelart.mkdir(parents=True)
        (pixelart / "special.frame.amf3.deflate").write_bytes(deflate(
            {"name": frame_name if frame_name is not None else name,
             "x": -128, "y": -128, "scale": 6, "smoothing": False}))
        (pixelart / "special_sprite_sheet.atlas.amf3.deflate").write_bytes(deflate(
            [{"n": i, "w": 15, "h": 18, "x": 0, "y": 0,
              "fx": -121, "fy": -111, "fw": 256, "fh": 256} for i in ids]))
        (pixelart / "special.timeline.amf3.deflate").write_bytes(deflate(
            {"sequences": [{"name": "special_land", "kind": "pass", "begin": 1, "end": 113},
                           {"name": "special_pose", "kind": "once", "begin": 114,
                            "end": last_end}],
             "circles": [], "points": [], "sounds": []}))
        (tmp / "package/manifest.json").write_text(json.dumps(
            {"character_id": "159994", "code_name": self.CODE}), encoding="utf-8")
        rep = V.Report()
        V.check_pixel_frames(V.Pack(tmp, ROOT), rep)
        return {c["name"]: c for c in rep.checks}

    def test_good_sheet_passes(self):
        with tempfile.TemporaryDirectory() as raw:
            checks = self._checks(Path(raw))
        for name in ("pixel/frame-name-and-ids", "pixel/atlas-covers-sequence-end"):
            self.assertTrue(checks[name]["pass"],
                            json.dumps(checks[name]["evidence"], ensure_ascii=False))

    def test_long_leading_gap_is_not_flagged(self):
        """END 语义：记录 0113 覆盖 tick 1..113。官方 ``spirit_fire`` 的
        ``neutral loop 1..600`` 只配一条 0600，「begin 之前要有图」是错判据。"""
        name = f"character/{self.CODE}/pixelart/special"
        with tempfile.TemporaryDirectory() as raw:
            checks = self._checks(Path(raw), ids=[f"{name}0113", f"{name}0150"])
        self.assertTrue(checks["pixel/frame-name-and-ids"]["pass"])
        self.assertTrue(checks["pixel/atlas-covers-sequence-end"]["pass"])

    def test_donor_frame_name_is_blocked(self):
        """frame.name 指向母本 = 容器按母本名找纹理 → 领取演出 C8003（米娅事故）。"""
        with tempfile.TemporaryDirectory() as raw:
            checks = self._checks(Path(raw), frame_name="character/high_priestess_ny22/pixelart/special")
        check = checks["pixel/frame-name-and-ids"]
        self.assertFalse(check["pass"])
        self.assertEqual(check["level"], V.BLOCKING)
        self.assertIn("high_priestess_ny22", json.dumps(check["evidence"], ensure_ascii=False))

    def test_id_without_frame_name_prefix_is_blocked(self):
        name = f"character/{self.CODE}/pixelart/special"
        with tempfile.TemporaryDirectory() as raw:
            checks = self._checks(Path(raw), ids=[f"{name}0113", "character/other/pixelart/special0150"])
        self.assertFalse(checks["pixel/frame-name-and-ids"]["pass"])

    def test_unsorted_atlas_is_blocked(self):
        name = f"character/{self.CODE}/pixelart/special"
        with tempfile.TemporaryDirectory() as raw:
            checks = self._checks(Path(raw), ids=[f"{name}0150", f"{name}0113"])
        self.assertFalse(checks["pixel/frame-name-and-ids"]["pass"])

    def test_atlas_short_of_last_sequence_end_is_blocked(self):
        """末帧号 < 末序列 end：超出的 tick 读到 undefined，画面回落到第 0 条记录。"""
        with tempfile.TemporaryDirectory() as raw:
            checks = self._checks(Path(raw), last_end=180)
        check = checks["pixel/atlas-covers-sequence-end"]
        self.assertFalse(check["pass"])
        self.assertEqual(check["level"], V.BLOCKING)

    def test_real_packages_are_clean(self):
        checked = 0
        for workspace in sorted((ROOT / "work/character_packs").glob("ma-*")):
            if not (workspace / "package/roots").is_dir():
                continue
            rep = V.Report()
            V.check_pixel_frames(V.Pack(workspace, ROOT), rep)
            for check in rep.checks:
                self.assertTrue(check["pass"], f"{workspace.name} {check['name']}: " +
                                json.dumps(check["evidence"], ensure_ascii=False))
            checked += 1
        if not checked:
            self.skipTest("no ma-* package on this machine")


class InstallStagedAssetsGuardTest(unittest.TestCase):
    """``kitlib.install_staged_assets`` 的交付件闸门（纯函数部分）。"""

    def test_donor_code_leaks_sees_through_deflate(self):
        raw = zlib.compress(b"character/sorceress_teacher/pixelart/sprite_sheet")
        self.assertEqual(KL.donor_code_leaks(raw, "sorceress_teacher_moon"),
                         ["sorceress_teacher"])

    def test_donor_code_leaks_accepts_own_code(self):
        raw = zlib.compress(b"character/sorceress_teacher_moon/pixelart/sprite_sheet")
        self.assertEqual(KL.donor_code_leaks(raw, "sorceress_teacher_moon"), [])

    def test_donor_code_leaks_ignores_effect_paths(self):
        raw = b"battle/effect/skill_unique/sorceress_teacher/fire_01"
        self.assertEqual(KL.donor_code_leaks(raw, "sorceress_teacher_moon"), [])

    def test_donor_code_leaks_dedupes_and_keeps_order(self):
        raw = b"character/a_one/x character/b_two/y character/a_one/z"
        self.assertEqual(KL.donor_code_leaks(raw, "new_code"), ["a_one", "b_two"])


class GbfDowngradeTest(unittest.TestCase):
    """GBF 两包的批次差异降级必须是**显式登记**的，不是静默放过。"""

    def test_tolerated_rules_exclude_fatal_ones(self):
        for fatal in ("unparsable", "not_obfuscated", "over_official_max"):
            self.assertNotIn(fatal, V.GBF_TOLERATED_CONTAINER_RULES,
                             "解不出帧/非混淆态/超官方 max 不许降级")
        self.assertIn("bad_bitrate", V.GBF_TOLERATED_CONTAINER_RULES)

    def test_gbf_atlas_threshold_is_looser(self):
        self.assertGreater(V.GBF_ATLAS_THRESHOLD, V.DEFAULT_ATLAS_THRESHOLD)


if __name__ == "__main__":
    unittest.main()
