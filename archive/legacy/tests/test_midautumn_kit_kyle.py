# -*- coding: utf-8 -*-
"""凯尔 kit（139990 ``kyle_moon``）rework1：行计划自查 + 行装配 + DSL 门禁。

三组用例：

1. **纯静态**（不需要 live / 官方基线）：模块常量与 ``design/kyle.json`` 的互锁、
   裁决 §8 的自查（队长表禁 422/724/713、422 必挂前置 42 且 c118 非空、前置 kind 白名单、
   固有 ID 8 位且上限非 ``(None)``、629 必配字符串键且排在读它的计数行之后、
   面板文案逐行对齐 ``rework1/panel/kyle.json``、面板禁词），以及本模块的小工具
   （判定区/CNA 改格、绑定号平移、图标绘制）。
2. **官方基线**（缺 ``.cdn/cn`` 或 live store 时跳过）：4＋23 行逐行装配并与 ``EXPECT``
   的 ``wf_describe`` 回读逐字比对；两棵主技能树与两棵 629 追击树的装配与全部 DSL 门禁
   （元素、主体绑定、判定区归属、方向、坐标系），母本漂移断言。
3. **已构建的 workspace**（``work/character_packs/ma-kyle`` 不存在时跳过）：包内自有键、
   4 棵 DSL 程序、三个固有状态与图标、三族特效、``custom_ability_string`` 10 键。

不写 live store / ``assets/`` / ``.cdn``，不跑发布；官方基线只读。
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
import zlib
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_common as MC  # noqa: E402
import wf_midautumn_kit_kyle as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_build as B  # noqa: E402

ROOT = core.project_root()
DESIGN = MS.load_design(ROOT, "kyle")
WORKSPACE = ROOT / "work/character_packs/ma-kyle"
PANEL = ROOT / "work/character_packs/midautumn-20260920/rework1/panel/kyle.json"


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


_BASELINE = _baseline_available()
_CTX = None


def ctx():
    """只读上下文：``record_sources=False`` ⇒ 母本取数不写 workspace（框架 §10.2）。"""
    global _CTX
    if _CTX is None:
        _CTX = B.KitContext(MC.MAPack(MS.get_spec("kyle"), record_sources=False))
    return _CTX


def fake_family(src_dir: str, dst_dir: str, sub: str, donor: str, bases: list[str]) -> dict:
    return {"src_dir": src_dir, "dst_dir": dst_dir, "donor": donor,
            "dst_name": sub, "copied_bases": list(bases)}


def blade_family() -> dict:
    return fake_family(K.FX_BLADE_SRC, K.FX_BLADE_DST, K.FX_BLADE_SUB, K.TEMPLATE_CODE,
                       [f"{K.TEMPLATE_CODE}_slash", f"{K.TEMPLATE_CODE}_smash",
                        f"{K.TEMPLATE_CODE}_explosion"])


def bolt_family() -> dict:
    return fake_family(K.FX_BOLT_SRC, K.FX_BOLT_DST, K.FX_BOLT_SUB, K.FX_BOLT_TEMPLATE,
                       [f"{K.FX_BOLT_TEMPLATE}_start", f"{K.FX_BOLT_TEMPLATE}_shock",
                        f"{K.FX_BOLT_TEMPLATE}_shock_ground", f"{K.FX_BOLT_TEMPLATE}_hit"])


def trail_family() -> dict:
    return fake_family(K.FX_TRAIL_SRC, K.FX_TRAIL_DST, K.FX_TRAIL_SUB, K.FX_TRAIL_TEMPLATE,
                       [K.FX_TRAIL_BASE])


def all_rows(context) -> dict:
    return K.build_rows(context)


# ---------------------------------------------------------------- 1. 纯静态

class ConstantTests(unittest.TestCase):
    def test_identity_matches_the_registry(self):
        spec = MS.SPECS["kyle"]
        self.assertEqual((K.CID, K.CODE, K.ELEMENT), (spec.cid, spec.code, spec.element))
        self.assertEqual((K.TEMPLATE_ID, K.TEMPLATE_CODE),
                         (spec.template_id, spec.template_code))

    def test_element_is_not_colorless(self):
        # element=6 是敌专属 Colorless，可玩角色写 6 会 C7050（记忆 wf-element6-colorless-crash）
        self.assertEqual(K.ELEMENT, 2)
        self.assertEqual(K.ELEMENT_TOKEN, "Yellow")

    def test_unique_condition_ids_are_eight_digits_and_distinct(self):
        keys = [key for key, *_ in K.UNIQUES]
        self.assertEqual(len(set(keys)), 3)
        for key in keys:
            self.assertEqual(len(key), 8, key)
            self.assertTrue(key.startswith(str(K.CID)), key)

    def test_unique_cap_is_never_none(self):
        # c4 写 (None) ＝ 上限 1，during 134 / vlv 成长会全死（记忆 wf-unique-cap-none-trap）
        for _key, _sid, _name, cap, frames, _style in K.UNIQUES:
            self.assertNotIn(cap, ("", "(None)"))
            self.assertTrue(cap.isdigit(), cap)
            self.assertTrue(frames.isdigit(), frames)

    def test_spec_declares_every_self_owned_key(self):
        extra = K.SPEC["extra_keys"]
        self.assertEqual(set(extra[MS.UNIQUE_CONDITION_LOGICAL]),
                         {key for key, *_ in K.UNIQUES})
        self.assertEqual(set(extra[KL.CAS]), set(K.CAS_TEXTS))
        self.assertEqual(len(extra[KL.CAS]), 11)

    def test_required_capabilities_cover_dash_and_panel_override(self):
        self.assertEqual(set(K.SPEC["required_capabilities"]),
                         {"dash-parameter-v1", "panel-description-override-v2"})

    def test_ability_keys_are_the_six_slots(self):
        self.assertEqual(K.ABILITY_KEYS, tuple(f"{K.CID}{n}" for n in range(1, 7)))
        self.assertEqual(sorted(K.PLAN), [1, 2, 3, 4, 5, 6])


class PlanSelfCheckTests(unittest.TestCase):
    """不碰基线，只看 PLAN/LEADER 里写死的列值本身是否踩线。"""

    def ability_cells(self, slot: int):
        for _addr, _src, cells, _expect in K.PLAN[slot]:
            yield cells

    def test_leader_plan_writes_no_dash_fever_or_independent_multiplier_kinds(self):
        # LeaderAbilityValues.parseAt107 没打补丁 ⇒ 队长表写 422/724/713 = 角色页 C7050
        for _addr, _src, cells, _expect in K.LEADER:
            self.assertNotIn(cells.get(107), ("422", "724", "713"))

    def test_dash_rows_are_leader_gated_and_carry_a_param_id(self):
        dash = [cells for cells in self.ability_cells(5) if cells.get(118)]
        self.assertEqual(len(dash), 4, "CD / 速度 / 高度 / Swift 抵消")
        ids = sorted(cells["118"] if "118" in cells else cells[118] for cells in dash)
        self.assertEqual(ids, ["0", "0", "1", "6"])
        for cells in dash:
            self.assertEqual(cells.get(6), "42", "422 行必须挂前置 42（持有者为队长）")

    def test_invoke_rows_declare_both_a_string_key_and_a_program(self):
        for slot, rows in K.PLAN.items():
            for addr, _src, cells, _expect in rows:
                if cells.get(71):
                    self.assertTrue(cells.get(70), f"{slot} {addr}: 629 行缺字符串键 c70")
                    ct = cells.get(35)
                    self.assertIsNotNone(ct, f"{slot} {addr}: 629 的 CT 不能留空")
                    self.assertTrue(str(ct).isdigit(), f"{slot} {addr}: CT c35 {ct!r} 不是帧数")

    def test_the_two_cooltimes_from_the_second_feedback_round(self):
        """作者真机反馈轮 2：召唤天雷 CT 3 秒、贯通→技能槽 CT 10 秒（c35 单位帧）。"""
        self.assertEqual((K.THUNDER_COOLTIME, K.PIERCE_GAUGE_COOLTIME), ("180", "600"))
        self.assertEqual(int(K.THUNDER_COOLTIME) / 60, 3)
        self.assertEqual(int(K.PIERCE_GAUGE_COOLTIME) / 60, 10)
        thunder = [cells for _a, _s, cells, _e in K.PLAN[3]
                   if cells.get(70) == K.CAS_THUNDER]
        self.assertEqual(len(thunder), 1)
        self.assertEqual(thunder[0].get(35), K.THUNDER_COOLTIME)
        # 计划层只写非空格：触发 51（获得贯穿）继承自 donor 2110012#0，不在 cells 里，
        # 所以这里按内容 kind 211 定位；触发位的核对留给装配后的 _cooltime_problems。
        gauge = [cells for _a, _s, cells, _e in K.PLAN[3] if cells.get(47) == "211"]
        self.assertEqual(len(gauge), 1)
        self.assertEqual(gauge[0].get(35), K.PIERCE_GAUGE_COOLTIME)

    def test_the_cooltime_guard_locates_rows_by_content_not_by_index(self):
        """守卫必须按 kind/内容找行：记录号会被共享 donor 的插行打漂（1.4.974 实际发生过）。"""
        def blank(kind: str, **cells) -> list[str]:
            row = [""] * KL.ABILITY_NCOLS
            row[47] = kind
            for col, value in cells.items():
                row[int(col)] = value
            return row

        thunder = blank("629", **{"27": "20", "35": K.THUNDER_COOLTIME, "70": K.CAS_THUNDER})
        gauge = blank("211", **{"27": "51", "35": K.PIERCE_GAUGE_COOLTIME})
        # 前面塞两条无关行：按记录号写死的断言会在这里失效，按内容定位的不受影响
        noise = [blank("461", **{"27": "23"}), blank("32", **{"27": "51"})]
        K._cooltime_problems(noise + [thunder, gauge])
        for broken in ("0", "", "300"):
            bad = copy.deepcopy(thunder)
            bad[35] = broken
            with self.assertRaises(KL.KitError):
                K._cooltime_problems(noise + [bad, gauge])
            bad = copy.deepcopy(gauge)
            bad[35] = broken
            with self.assertRaises(KL.KitError):
                K._cooltime_problems(noise + [thunder, bad])
        with self.assertRaises(KL.KitError):   # 锚点丢失（行被删）也要红
            K._cooltime_problems(noise + [gauge])

    def test_main_only_slots_are_one_two_and_three(self):
        """作者真机反馈轮 2：「凯尔的能力1和2都带上主位限制」。"""
        self.assertEqual(K.MAIN_ONLY_SLOTS, {1, 2, 3})
        for slot in range(1, 7):
            self.assertEqual(K._UNISONABLE[slot] == "false", slot in K.MAIN_ONLY_SLOTS, slot)
        # 「切换技能形态」(536) 与技能强化条目在能力 1 ⇒ 这一槽必须是主位限制槽
        switch = [slot for slot, rows in K.PLAN.items()
                  if any(cells.get(70) == K.CAS_SWITCH for _a, _s, cells, _e in rows)]
        self.assertEqual(switch, [1])
        self.assertIn(1, K.MAIN_ONLY_SLOTS)

    def test_invoke_programs_live_under_the_ability_skill_namespace(self):
        for program in (K.PIERCE_PROGRAM, K.THUNDER_PROGRAM):
            self.assertIn("/ability_skill/", program)
            self.assertIn("$", program)

    def test_only_the_main_only_slot_hosts_629(self):
        # 629 在副位不生效 ⇒ 宿主键必须 unisonable=false
        for slot, rows in K.PLAN.items():
            if any(cells.get(71) for _a, _s, cells, _e in rows):
                self.assertEqual(K._UNISONABLE[slot], "false", slot)

    def test_precondition_kinds_stay_inside_the_vetted_set(self):
        for _addr, _src, cells, _expect in K.LEADER:
            for col in (4, 11, 18):
                self.assertIn(str(cells.get(col, "")), K.ALLOWED_PRECONDITION_KINDS + ("",))
        for slot, rows in K.PLAN.items():
            for addr, _src, cells, _expect in rows:
                for col in (6, 13, 20):
                    value = str(cells.get(col, ""))
                    self.assertIn(value, K.ALLOWED_PRECONDITION_KINDS + ("",),
                                  f"{slot} {addr} c{col}")

    def test_condition_unique_preconditions_name_a_unique_and_a_puller(self):
        # 手拼前置 187/188 漏 c7='0' 会 C7050；固有 id 列留空同样会崩
        owned = {key for key, *_ in K.UNIQUES}
        for slot, rows in K.PLAN.items():
            for addr, _src, cells, _expect in rows:
                if cells.get(6) == "187":
                    self.assertEqual(cells.get(7), "0", f"{slot} {addr}: 前置 187 缺 c7 puller")
                    self.assertIn(cells.get(12), owned, f"{slot} {addr}: 前置 187 的固有 id")

    def test_no_precondition_188_or_144(self):
        # 188 数的是实例个数（461 叠层恒为 1），144 官方零先例（裁决 §8）
        for slot, rows in K.PLAN.items():
            for _addr, _src, cells, _expect in rows:
                for col in (6, 13, 20):
                    self.assertNotIn(str(cells.get(col, "")), ("188", "144"), slot)

    def test_unlimited_growth_rows_write_none_not_an_empty_limit(self):
        # during 134 的 limit 留空 = 上限 0（词条全程零收益，面板出「上限 0 次」）
        for _addr, _src, cells, _expect in K.LEADER:
            if cells.get(95) == "134" or cells.get(102):
                self.assertNotEqual(cells.get(100), "")
        # 2026-09-27 第二批：能力 2 两条逐层成长换成有上限的弱化版（c102=10，官方 134 限次族同写法）；
        # 其余读月牙的持续行仍是 (None)。无论哪种都不许留空串（= 上限 0）。
        for slot, rows in K.PLAN.items():
            for addr, _src, cells, _expect in rows:
                if cells.get(104):
                    want = K.CRESCENT_ABILITY_LIMIT if slot == 2 else "(None)"
                    self.assertEqual(cells.get(102), want, f"{slot} {addr}")
                    self.assertTrue(want == "(None)" or int(want) > 0)

    def test_unique_references_point_at_our_own_ids(self):
        owned = {key for key, *_ in K.UNIQUES}
        for slot, rows in K.PLAN.items():
            for addr, _src, cells, _expect in rows:
                for col in (12, 68, 104):
                    value = cells.get(col)
                    if value and str(value).isdigit() and len(str(value)) == 8:
                        self.assertIn(value, owned, f"{slot} {addr} c{col}")


class PanelTextTests(unittest.TestCase):
    def test_panel_text_obeys_the_project_rules(self):
        for line in K.PANEL_LEADER.split("\n"):
            KL.check_panel(line, label="leader")
        for slot, text in K.PANEL_ABILITY.items():
            for line in text.split("\n"):
                KL.check_panel(line.replace(K.MAIN_ICON, ""), label=f"ability {slot}")
        KL.check_panel(K.CAS_TEXTS[K.CAS_SWITCH], skill_flag=True, label="change_skill")

    def test_panel_text_matches_the_author_approved_target(self):
        """逐行对齐 ``rework1/panel/kyle.json``：那是作者已过目并放行的目标面板。"""
        if not PANEL.is_file():
            self.skipTest("rework1/panel/kyle.json missing")
        panel = json.loads(PANEL.read_text(encoding="utf-8"))
        # 2026-09-27 第三轮（wf_balance_20260927c_kyle）改了队长面板；镜像由主会话 --write 落盘，
        # 落盘前按其同步结果比对（mirror_updates 幂等，已落盘时为恒等）
        import wf_balance_20260927c_kyle as C3
        design = json.loads((ROOT / C3.DESIGN_REL).read_text(encoding="utf-8"))
        panel = C3.mirror_updates(design, panel)[1]
        want_leader = [line["text"] for line in panel["leader"]["lines"]]
        self.assertEqual(K.PANEL_LEADER.split("\n"), want_leader)
        for entry in panel["abilities"]:
            slot = int(entry["index"])
            self.assertEqual([line.replace(K.MAIN_ICON, "")
                              for line in K.PANEL_ABILITY[slot].split("\n")],
                             [line["text"] for line in entry["lines"]], f"ability {slot}")

    def test_main_only_slots_carry_the_icon_on_every_line(self):
        """desc_override 整槽接管后客户端不再逐行画 Ⓜ：主位限制槽每行自带图标，其余槽不带。"""
        for slot, text in K.PANEL_ABILITY.items():
            wants = K._UNISONABLE[slot] == "false"
            for line in text.split("\n"):
                self.assertEqual(line.startswith(K.MAIN_ICON), wants, f"ability {slot}: {line[:20]}")
            self.assertNotIn("Ⓜ", text)
            self.assertNotIn("／", text)
        self.assertNotIn("／", K.PANEL_LEADER)

    def test_main_only_slot_matches_the_panel(self):
        if not PANEL.is_file():
            self.skipTest("rework1/panel/kyle.json missing")
        panel = json.loads(PANEL.read_text(encoding="utf-8"))
        for entry in panel["abilities"]:
            slot = int(entry["index"])
            self.assertEqual(K._UNISONABLE[slot] == "false", bool(entry["main_only"]),
                             f"ability {slot} 的主位限制与面板不符")

    #: 作者反馈轮 2：「技能里面也不用描述怎么改的是我描述给你的」——这些是给主控的施工用语，
    #: 不是玩家文案；只许出现在代码注释与 impl 文档里，一律不许进任何会上屏的字符串。
    BUILD_NOTE_WORDS = ("千岳", "梅媞斯", "雷弓", "染色", "冷蓝白", "不做染色", "特效")

    def test_skill_description_mirrors_the_panel_skill_lines(self):
        """技能说明（action_skill desc 列）＝面板 skill.lines 按「／」拼接，逐字。"""
        if not PANEL.is_file() or not DESIGN:
            self.skipTest("panel or design missing")
        panel = json.loads(PANEL.read_text(encoding="utf-8"))
        want = "／".join(line["text"] for line in panel["skill"]["lines"])
        self.assertEqual(DESIGN["texts"]["desc1"], want)
        self.assertEqual(DESIGN["texts"]["desc2"], want)
        self.assertEqual(len(panel["skill"]["lines"]), 2, "施工说明那一句已删，只剩两句")

    def test_no_build_notes_leak_into_player_facing_text(self):
        if not DESIGN:
            self.skipTest("design/kyle.json missing")
        surfaces = {f"design.texts.{name}": DESIGN["texts"][name]
                    for name in ("title", "profile", "leader", "skill1", "desc1",
                                 "skill2", "desc2")}
        surfaces.update({f"cas.{key}": text for key, text in K.CAS_TEXTS.items()})
        surfaces["panel.leader"] = K.PANEL_LEADER
        surfaces.update({f"panel.ability{slot}": text
                         for slot, text in K.PANEL_ABILITY.items()})
        for label, text in surfaces.items():
            for word in self.BUILD_NOTE_WORDS:
                self.assertNotIn(word, text, f"{label} 残留施工用语 {word!r}")

    def test_cooltime_wording_matches_the_panel(self):
        if not PANEL.is_file():
            self.skipTest("rework1/panel/kyle.json missing")
        panel = json.loads(PANEL.read_text(encoding="utf-8"))
        thunder = panel["skill"]["lines"][1]["text"]
        self.assertIn("召唤天雷", thunder)
        self.assertNotIn("秒", thunder)
        # 能力 3 第 1 行 2026-09-27 按数据条件拆成两行（口径 5）⇒ 按内容找贯穿回槽那一行，不按行号
        gauge, = [line["text"] for line in next(e for e in panel["abilities"] if e["index"] == 3)["lines"]
                  if "贯穿效果" in line["text"]]
        self.assertIn(f"（冷却时间：{int(K.PIERCE_GAUGE_COOLTIME) // 60}秒）", gauge)
        self.assertIn(f"（冷却时间：{int(K.PIERCE_GAUGE_COOLTIME) // 60}秒）",
                      K.PANEL_ABILITY[3])

    def test_skill_energy_matches_the_panel(self):
        if not PANEL.is_file() or not DESIGN:
            self.skipTest("panel or design missing")
        panel = json.loads(PANEL.read_text(encoding="utf-8"))
        energy = DESIGN["plan"]["skills"]["energy"]
        for level in ("1", "2"):
            self.assertEqual(int(energy[level]["c4"]), int(panel["skill"]["energy"]))


class DesignMirrorTests(unittest.TestCase):
    def test_design_mirrors_the_module_plan(self):
        if not DESIGN:
            self.skipTest("design/kyle.json missing")
        self.assertEqual(K._design_problems(DESIGN), [])

    def test_a_drifted_mirror_is_rejected(self):
        if not DESIGN:
            self.skipTest("design/kyle.json missing")
        broken = copy.deepcopy(DESIGN)
        broken["plan"]["rework1"]["leader"] = ["official:999999#0"]
        self.assertTrue(K._design_problems(broken))

    def test_design_texts_pass_the_panel_rules(self):
        if not DESIGN:
            self.skipTest("design/kyle.json missing")
        for name in ("title", "profile", "leader", "skill1", "desc1", "skill2", "desc2"):
            KL.check_panel(DESIGN["texts"][name], label=name)


class KindGuardTests(unittest.TestCase):
    def blank(self, ncols: int) -> list[str]:
        return [""] * ncols

    def test_forbidden_content_kind_in_the_leader_table_is_rejected(self):
        row = self.blank(KL.LEADER_NCOLS)
        row[107] = "422"
        with self.assertRaises(KL.KitError):
            K._ban_kinds("leader_ability", [row], "leader")

    def test_dash_row_without_the_leader_precondition_is_rejected(self):
        row = self.blank(KL.ABILITY_NCOLS)
        row[109], row[118] = "422", "0"
        with self.assertRaises(KL.KitError):
            K._ban_kinds("ability", [row], "1399905")

    def test_dash_row_without_a_param_id_is_rejected(self):
        row = self.blank(KL.ABILITY_NCOLS)
        row[6], row[109] = "42", "422"
        with self.assertRaises(KL.KitError):
            K._ban_kinds("ability", [row], "1399905")

    def test_unvetted_precondition_kind_is_rejected(self):
        row = self.blank(KL.ABILITY_NCOLS)
        row[6] = "188"
        with self.assertRaises(KL.KitError):
            K._ban_kinds("ability", [row], "1399903")

    def test_invoke_must_follow_the_counter_row(self):
        rows = []
        for event in (("23", "0", "", "100000", "100000"),
                      ("20", "7", "Yellow", "10000000", "10000000")):
            add = self.blank(KL.ABILITY_NCOLS)
            add[1], add[47], add[68] = "false", "461", K.UID_CRESCENT
            add[27:32] = event
            invoke = self.blank(KL.ABILITY_NCOLS)
            invoke[1], invoke[47] = "false", "629"
            invoke[27:32] = event
            invoke[6], invoke[13], invoke[18] = "42", "2", "Yellow"
            invoke[35], invoke[70], invoke[71] = "0", K.CAS_PIERCE, K.PIERCE_PROGRAM
            rows.extend([add, invoke])
        K._order_problems(rows)
        with self.assertRaises(KL.KitError):
            K._order_problems([rows[1], rows[0], *rows[2:]])
        rows[-1][30] = "5000000"
        with self.assertRaises(KL.KitError):
            K._order_problems(rows)

    def test_invoke_without_a_string_key_is_rejected(self):
        add = self.blank(KL.ABILITY_NCOLS)
        add[1], add[27], add[47] = "false", "51", "461"
        invoke = self.blank(KL.ABILITY_NCOLS)
        invoke[1], invoke[27], invoke[47], invoke[35] = "false", "51", "629", "0"
        with self.assertRaises(KL.KitError):
            K._order_problems([add, invoke])


class DslHelperTests(unittest.TestCase):
    def hit_area(self) -> list:
        body = ["CreateHitArea"] + [None] * 26
        body[9] = ["Circle", [{"min": 225, "max": 225}]]
        body[13] = ["SpecifyHitAreaLifetimeDirectly", 30]
        body[14] = ["CalculatedUsingMaxNumOfHits", 1]
        body[24] = 0
        return body

    def test_hit_area_setter_writes_the_direct_attack_attribution(self):
        body = self.hit_area()
        K._set_hitarea(body, radius=320, lifetime=20, max_hits=1, label="t")
        self.assertEqual(body[9], ["Circle", [{"min": 320, "max": 320}]])
        self.assertEqual(body[24], K.BUFF_TARGET_AS_DIRECT)

    def test_hit_area_setter_rejects_a_drifted_shape(self):
        body = self.hit_area()
        body[9] = ["Rectangle", []]
        with self.assertRaises(KL.KitError):
            K._set_hitarea(body, radius=10, lifetime=1, max_hits=1, label="t")

    def test_create_normal_attack_keeps_the_inherited_element_slot(self):
        body = ["CreateNormalAttack"] + [None] * 16
        body[2] = 255
        K._set_cna(body, K.CNA_SHAPE[0], {"min": 1, "max": 1}, "t", combo_bonus=True)
        self.assertEqual(body[2], 255)
        self.assertIs(body[8], True)
        body[2] = 3
        with self.assertRaises(KL.KitError):
            K._set_cna(body, K.CNA_SHAPE[0], {"min": 1, "max": 1}, "t")

    def test_bind_remap_uses_the_authoritative_slot_table(self):
        node = ["Command", ["FindNearSubjects", -18, 1, 49, ["DoNothing"], 3,
                            ["Block", [["Command", ["CreateCondition", 3, [], [], None, True,
                                                    False, "", None, False, 3, [], False]]]]]]
        K._remap_binds(node, 30)
        self.assertEqual(node[1][5], 33)
        self.assertEqual(node[1][6][1][0][1][1], 33)
        self.assertEqual(node[1][1], -18, "内建主体（球）不许被平移")

    def test_finish_hit_area_binds_do_not_collide_with_the_enemy_block(self):
        self.assertNotIn(K.ENEMY_BIND, K.FINISH_BINDS)

    def test_normal_thunder_is_referenced_not_cloned(self):
        self.assertTrue(K.THUNDER_NORMAL_DONOR.endswith("psychic_tohru_1"))
        self.assertNotIn("psychic_tohru", K.FX_BOLT_DST)

    def test_pierce_growth_is_not_capped_at_three(self):
        self.assertGreater(K.PIERCE_VAR_CEIL, 3)
        # 2026-09-27 第二批（口径 A5）曾封顶 10；第三轮（口径 U1）恢复 99 = 月牙上限
        self.assertEqual(K.PIERCE_VAR_CEIL, 99)
        self.assertEqual(K.PIERCE_BASE_TIMES, 1)
        self.assertEqual(K.PIERCE_TIMES_PER_LAYER, 1)
        # 段数取优不相加：同段数时比伤害% ⇒ 不得低于词条层的 3 段 +300%
        self.assertGreaterEqual(K.PIERCE_DAMAGE, 3.0)

    def test_pierce_condition_carries_a_distinct_key(self):
        # 带 vlv 的 CreateCondition 必须有非空区分键，否则不同层数会叠加
        self.assertTrue(K.PIERCE_CONDITION_KEY)


class IconTests(unittest.TestCase):
    def frame(self):
        from PIL import Image
        image = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
        pixels = image.load()
        for y in range(48):
            for x in range(48):
                pixels[x, y] = (0, 0, 0, 255 if 4 <= x < 44 and 4 <= y < 44 else 0)
        return image

    def test_every_style_keeps_the_official_alpha_and_size(self):
        frame = self.frame()
        for _key, _sid, _name, _cap, _frames, style in K.UNIQUES:
            icon = K.draw_icon(frame, style)
            self.assertEqual(icon.size, (48, 48))
            self.assertEqual(icon.getchannel("A").tobytes(), frame.getchannel("A").tobytes())

    def test_styles_differ_from_each_other(self):
        frame = self.frame()
        blobs = {style: K.draw_icon(frame, style).tobytes()
                 for _k, _s, _n, _c, _f, style in K.UNIQUES}
        self.assertEqual(len(set(blobs.values())), len(blobs))

    def test_unknown_style_is_rejected(self):
        with self.assertRaises(KL.KitError):
            K.draw_icon(self.frame(), "nope")

    def test_icon_rejects_a_wrong_sized_frame(self):
        from PIL import Image
        with self.assertRaises(KL.KitError):
            K.draw_icon(Image.new("RGBA", (32, 32)), "crescent")


# ---------------------------------------------------------------- 2. 官方基线

@unittest.skipUnless(_BASELINE, "需要 .cdn/cn 官方基线与 live store")
class RowBuildTests(unittest.TestCase):
    def test_thunder_ally_skills_add_own_crescent_before_matching_hit_refresh(self):
        rows = self.built['ability']['1399903']
        producer, refresh = rows[0], rows[4]
        self.assertEqual(producer[27:32], ['23', '5', 'Yellow', '100000', '100000'])
        self.assertEqual(refresh[27:32], producer[27:32])
        self.assertEqual((producer[1], producer[6], producer[11]), ('false', '2', 'Yellow'))
        self.assertEqual((producer[47], producer[48], producer[51], producer[68]),
                         ('461', '0', '100000', K.UID_CRESCENT))
        self.assertEqual((refresh[6], refresh[13], refresh[18]), ('42', '2', 'Yellow'))

    @classmethod
    def setUpClass(cls):
        cls.built = all_rows(ctx())

    def test_row_counts(self):
        # 2026-09-27 平衡批次删去队长「月牙 Stunify」与能力5「雷队 Stunify」各 1 行
        self.assertEqual(len(self.built["leader"]), 9)
        self.assertEqual(sum(len(rows) for rows in self.built["ability"].values()), 21)

    def test_piercing_growth_uses_native_down_slayer_and_retains_trigger(self):
        rows = [r for r in self.built["leader"] if r[25] == "51"]
        self.assertEqual(len(rows), 2)
        # 2026-09-27 第二批 ×1/10（25%→2.5%、5%→0.5%）；第三轮改为原值 ×4/5（25%→20%、5%→4%）
        self.assertEqual({r[45]: r[49:51] for r in rows},
                         {"32": ["20000", "20000"], "53": ["4000", "4000"]})
        for row in rows:
            self.assertEqual(row[4], "2")
            self.assertEqual(row[7:10], ["600000", "600000", "Yellow"])
            self.assertEqual(row[26], "")  # Native ConditionPiercing has no puller field.
            self.assertEqual(row[28:30], ["100000", "100000"])
            self.assertEqual(row[32], "(None)")
            self.assertEqual(row[46:48], ["5", "Yellow"])

    def test_ability_one_removes_only_separate_skill_damage_bonus(self):
        rows = self.built["ability"]["1399901"]
        self.assertEqual([r[47] for r in rows], ["211", "211", "536"])
        self.assertTrue(all(r[1] == "false" for r in rows))

    def test_down_growth_stunify_rows_are_removed(self):
        """作者 2026-09-27：去掉队长技和能力里的 Down 效果成长（方案A）。"""
        self.assertFalse([r for r in self.built["leader"] if r[107] in ("19", "51")])
        rows = self.built["ability"]["1399905"]
        self.assertFalse([r for r in rows if r[47] in ("19", "51")])
        self.assertEqual([r[47] for r in rows if r[27] == "20"], ["35"])
        self.assertNotIn("Down", K.PANEL_LEADER)
        self.assertNotIn("击倒", K.PANEL_ABILITY[5])
        self.assertNotIn("状态持续时间", K.PANEL_LEADER)

    def test_every_row_matches_the_baked_describe_readback(self):
        for ev in self.built["evidence"]:
            self.assertEqual(ev["describe"], K.EXPECT[ev["label"]], ev["label"])

    def test_capabilities_are_declared(self):
        self.assertTrue(set(self.built["capabilities"])
                        <= set(K.SPEC["required_capabilities"]))

    def test_first_four_leader_rows_are_crescent_growth(self):
        for row in self.built["leader"][:4]:
            self.assertEqual(row[95], "134")
            self.assertEqual(row[102], K.UID_CRESCENT)
            self.assertEqual(row[100], "(None)")

    def test_self_and_party_layers_sum_to_the_panel_numbers(self):
        """面板（2026-09-27 第三轮 原值×4/5，含能力 2 并入部分）：自身攻击 +60% / 直击 +80%，除自身外 +10% / +60%。"""
        share = {(row[107], row[108]): int(row[111]) for row in self.built["leader"] if row[95] == "134"}
        self.assertEqual(share[("0", "5")] + share[("0", "0")], 60000)
        self.assertEqual(share[("1", "5")] + share[("1", "0")], 80000)
        self.assertEqual(share[("0", "5")], 10000)
        self.assertEqual(share[("1", "5")], 60000)
        line = K.PANEL_LEADER.split("\n")[3]
        self.assertIn("自身攻击力＋60%、直击伤害＋80%", line)
        self.assertIn("除自身外雷属性角色攻击力＋10%、直击伤害＋60%", line)

    def test_crescent_ability_rows_are_capped_at_ten_layers(self):
        """能力 2：月牙每层 雷队直击 +10%、自身攻击 +16%，限 10 层（2026-09-27 第二批）。"""
        rows = self.built["ability"][f"{K.CID}2"]
        self.assertEqual([(r[97], r[102], r[109], r[110], r[113]) for r in rows],
                         [("134", "10", "1", "5", "10000"), ("134", "10", "0", "0", "16000")])
        self.assertIn("（最多10层）", K.PANEL_ABILITY[2])

    def test_direct_attack_stack_row_beats_the_batch_floor(self):
        row = next(r for r in self.built["ability"][f"{K.CID}3"] if r[47] == "202")
        self.assertEqual(row[48], "5")
        self.assertEqual(row[49], K.ELEMENT_TOKEN)
        # 跨角色：全批统一 3 段，主 C 的合计伤害不低于辅助（罗尔夫 200%）
        self.assertGreaterEqual(int(row[51]), 200000)

    def test_built_rows_carry_the_two_cooltimes(self):
        """装配后的实际行（不是计划）：CT 必须落在 c35，且 describe 渲染出 CT 字样。"""
        rows = self.built["ability"][f"{K.CID}3"]
        thunder = [row for row in rows if row[47] == "629" and row[70] == K.CAS_THUNDER]
        gauge = [row for row in rows if row[47] == "211" and row[27] == "51"]
        self.assertEqual((len(thunder), len(gauge)), (1, 1))
        self.assertEqual(thunder[0][35], K.THUNDER_COOLTIME)
        self.assertEqual(gauge[0][35], K.PIERCE_GAUGE_COOLTIME)
        rendered = {ev["label"]: ev["describe"] for ev in self.built["evidence"]}
        self.assertIn("(CT3秒)", rendered[f"{K.CID}3#{rows.index(thunder[0])}"])
        self.assertIn("(CT10秒)", rendered[f"{K.CID}3#{rows.index(gauge[0])}"])

    def test_main_only_slots_write_false_on_every_record(self):
        """c1 是整键语义：主位限制槽的每一条记录都必须是 false，非主位槽都必须是 true。"""
        for slot in range(1, 7):
            rows = self.built["ability"][f"{K.CID}{slot}"]
            want = "false" if slot in K.MAIN_ONLY_SLOTS else "true"
            self.assertEqual({row[1] for row in rows}, {want}, f"ability slot {slot}")

    def test_dash_parameters_match_the_panel(self):
        dash = {row[118]: int(row[113]) for row in self.built["ability"][f"{K.CID}5"]
                if row[109] == "422" and row[97] != "34"}
        self.assertEqual(dash["0"], -50000, "冲刺冷却时间 −50%")
        self.assertGreater(dash["1"], 0, "冲刺弹射速度提升")
        self.assertGreater(dash["6"], 0, "可从更高的位置发动冲刺")


@unittest.skipUnless(_BASELINE, "需要 .cdn/cn 官方基线与 live store")
class SkillTreeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = ctx()
        cls.donor = cls.context.template_dsl(
            f"battle/action/skill/action/rare5/{K.TEMPLATE_CODE}${K.TEMPLATE_CODE}_2")

    def mutated(self, level: str = "2"):
        donor = self.context.template_dsl(
            f"battle/action/skill/action/rare5/{K.TEMPLATE_CODE}${K.TEMPLATE_CODE}_{level}")
        tree, evidence = K.mutate_tree(self.context, donor, level)
        tree, _ = self.context.rewrite_effect_refs(tree, blade_family())
        tree, _ = self.context.rewrite_effect_refs(tree, trail_family())
        return tree, evidence

    def test_donor_fingerprint_is_asserted(self):
        self.assertEqual(K._command_counts(copy.deepcopy(self.donor)), K.DONOR_COMMAND_COUNTS)

    def test_drifted_donor_is_rejected(self):
        broken = copy.deepcopy(self.donor)
        broken[11][1].pop()
        with self.assertRaises(KL.KitError):
            K.mutate_tree(self.context, broken, "2")

    def test_skill_tree_passes_every_dsl_gate(self):
        for level in ("1", "2"):
            tree, _ = self.mutated(level)
            self.assertEqual(K._dsl_problems(tree), [], level)

    def test_dash_replaces_stop_ball(self):
        tree, evidence = self.mutated()
        names = {body[0] for body in
                 (node[1] for node in K._walk(tree) if K._is_command(node))}
        if K.DASH_REPLACES_STOPBALL:
            self.assertIn("MoveBall", names)
            self.assertNotIn("StopBall", names)
            self.assertEqual(evidence["dash"]["with"], K.MOVE_BALL)
        else:
            self.assertIn("StopBall", names)

    def test_trail_effect_is_attached_to_the_dash_block(self):
        tree, _ = self.mutated()
        trail = [body for body in (node[1] for node in K._walk(tree)
                                   if K._is_command(node, "ShowEffect"))
                 if body[1] == K.FX_TRAIL_LABEL]
        self.assertEqual(len(trail), 1)
        self.assertEqual(trail[0][2], ["SpecifyEffectDirectly", K.FX_TRAIL_EFFECT])
        self.assertEqual(trail[0][3], -18)
        self.assertEqual(trail[0][4], ["BacksideOfCharacter"])
        self.assertEqual(trail[0][6], ["AB"])

    def test_blade_effect_names_keep_their_tree_order(self):
        tree, _ = self.mutated()
        shows = [body[1] for body in (node[1] for node in K._walk(tree)
                                      if K._is_command(node, "ShowEffect"))]
        self.assertEqual(shows[:3], [K.EFFECT_NAMES[0], K.EFFECT_NAMES[1], K.EFFECT_NAMES[2]])

    def test_all_three_slashes_settle_as_direct_attack_damage(self):
        tree, _ = self.mutated()
        areas = [body for body in (node[1] for node in K._walk(tree)
                                   if K._is_command(node, "CreateHitArea"))]
        self.assertEqual(len(areas), 3)
        for area in areas:
            self.assertEqual(area[24], K.BUFF_TARGET_AS_DIRECT)

    def test_resonance_branch_carries_the_team_buffs_and_the_enemy_debuffs(self):
        tree, _ = self.mutated()
        flags = [body for body in (node[1] for node in K._walk(tree)
                                   if K._is_command(node, "ConditionalsChangeSkillFlag"))]
        self.assertEqual(len(flags), 1)
        boost, plain = flags[0][2], flags[0][3]
        self.assertEqual(plain, ["Block", []], "非共鸣档不加任何东西")
        kinds = {ac[0] for body in (node[1] for node in K._walk(boost)
                                    if K._is_command(node, "CreateCondition"))
                 for ac in body[2]}
        self.assertTrue({"ACPiercing", "ACDirectDamage", "ACSpeedup", "ACFrozen"} <= kinds)
        dispel = [body for body in (node[1] for node in K._walk(boost)
                                    if K._is_command(node, "DeleteCondition"))]
        self.assertEqual(len(dispel), 1)
        self.assertEqual(dispel[0][2], ["DCAll", 2])
        self.assertEqual(dispel[0][3], K.DISPEL_COUNT)

    def test_skill_detoughness_totals_thirty(self):
        """口径 B1（2026-09-27 第二批）：单目标每次施放 首斩 8 + 连斩 1×14 + 终斩 8 = 30（原 36）。"""
        for level in ("1", "2"):
            tree, _ = self.mutated(level)
            attacks = [node[1] for node in K._walk(tree) if K._is_command(node, "CreateNormalAttack")]
            areas = [node[1] for node in K._walk(tree) if K._is_command(node, "CreateHitArea")]
            self.assertEqual([a[13] for a in attacks],
                             [[{"min": 8, "max": 8}], [{"min": 1, "max": 1}], [{"min": 8, "max": 8}]])
            self.assertEqual([a[14] for a in attacks],
                             [[{"min": 5, "max": 5}], [{"min": 0.5, "max": 0.5}], [{"min": 6, "max": 6}]],
                             "Fever 点不动")
            hits = [a[14][1] for a in areas]
            self.assertEqual(hits, [1, 14, 1])
            self.assertEqual(sum(h * a[13][0]["max"] for h, a in zip(hits, attacks)), 30)

    def test_boost_durations_match_the_panel(self):
        tree, evidence = self.mutated()
        self.assertEqual(evidence["boost"]["piercing_frames"], 330)   # 5.5 秒
        self.assertEqual(evidence["boost"]["speedup_frames"], 900)    # 15 秒

    def test_awake_unique_is_applied_outside_the_branch(self):
        tree, _ = self.mutated()
        awake = [body for body in (node[1] for node in K._walk(tree[11][1][1:2])
                                   if K._is_command(node, "CreateCondition"))]
        self.assertEqual(len(awake), 1)
        self.assertEqual(awake[0][2][0][0], "ACUnique")
        self.assertEqual(awake[0][2][0][1], int(K.UID_AWAKE))

    def test_effect_refs_leave_no_donor_namespace_behind(self):
        for level in ("1", "2"):
            tree, _ = self.mutated(level)
            for path in K.effect_paths(tree):
                self.assertFalse(path.startswith(f"battle/effect/skill_unique/{K.TEMPLATE_CODE}/"),
                                 path)
                self.assertFalse(path.startswith(f"{K.FX_TRAIL_SRC}/"), path)


@unittest.skipUnless(_BASELINE, "需要 .cdn/cn 官方基线与 live store")
class AbilitySkillTreeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = ctx()
        cls.donor = cls.context.template_dsl(
            f"battle/action/skill/action/rare5/{K.TEMPLATE_CODE}${K.TEMPLATE_CODE}_2")

    def test_pierce_tree_binds_and_uses_the_variable_in_one_block(self):
        tree, note = K.build_pierce_tree(self.context, self.donor)
        self.assertEqual(K._dsl_problems(tree), [])
        block = tree[11]
        self.assertEqual(block[0], "Block")
        names = [node[1][0] for node in block[1] if K._is_command(node)]
        self.assertEqual(names, ["BindConditionAccumulationVariable", "CreateCondition"])
        bind = block[1][0][1]
        self.assertEqual(bind[3], ["DCUnique", int(K.UID_CRESCENT)])
        ac = block[1][1][1][2][0]
        self.assertEqual(ac[0], "ACAdditionalDirectAttack")
        self.assertEqual(ac[1], [{"min": int(K.ETERNAL_FRAMES), "max": int(K.ETERNAL_FRAMES)}])
        self.assertEqual(ac[2][0]["vlv"][0]["vid"], bind[2])
        self.assertEqual(note["ceiling"], K.PIERCE_VAR_CEIL)

    def test_pierce_variable_ceiling_is_the_crescent_cap(self):
        """``BindConditionAccumulationVariable`` 第 5 参 = 上限（ActionEvaluator case 101 取 min）。
        2026-09-27 第二批封顶 10，第三轮（wf_balance_20260927c_kyle，口径 U1）恢复 99（int）= 月牙上限。"""
        tree, note = K.build_pierce_tree(self.context, self.donor)
        bind = tree[11][1][0][1]
        self.assertEqual(bind, ["BindConditionAccumulationVariable", -17, K.PIERCE_VAR_ID,
                                ["DCUnique", int(K.UID_CRESCENT)], 1, 99])
        self.assertEqual(note["ceiling"], 99)

    def test_thunder_detoughness_is_at_most_one_per_invoke(self):
        """口径 B3（2026-09-27 第二批）：天雷 CT 3 秒 ⇒ 每次 ≤1：常态 20→1、强化 5 段 3.6→0.2。"""
        tree, note = K.build_thunder_tree(self.context, self.donor, bolt_family())
        flag = [node[1] for node in K._walk(tree)
                if K._is_command(node, "ConditionalsChangeSkillFlag")][0]
        for slot, value, hits in ((2, 0.2, 5), (3, 1, 1)):
            area = [n[1] for n in K._walk(flag[slot]) if K._is_command(n, "CreateHitArea")][0]
            attack = [n[1] for n in K._walk(flag[slot]) if K._is_command(n, "CreateNormalAttack")][0]
            self.assertEqual(attack[13], [{"min": value, "max": value}])
            self.assertEqual(area[14], ["CalculatedUsingMaxNumOfHits", hits])
            self.assertAlmostEqual(hits * value, 1.0)
        self.assertEqual(note["boost"]["detoughness"]["donor"], [{"min": 3.6, "max": 3.6}])
        self.assertEqual(note["normal"]["detoughness"]["donor"], [{"min": 20, "max": 20}])
        self.assertEqual(K.THUNDER_COOLTIME, "180")

    def test_pierce_condition_has_a_non_empty_discriminator(self):
        tree, _ = K.build_pierce_tree(self.context, self.donor)
        condition = tree[11][1][1][1]
        self.assertTrue(condition[7])
        self.assertEqual(condition[10], 3, "付与对象种类必须是 3（Member），否则施法 C16102")

    def test_thunder_tree_has_two_mutually_exclusive_branches(self):
        tree, note = K.build_thunder_tree(self.context, self.donor, bolt_family())
        self.assertEqual(K._dsl_problems(tree), [])
        flags = [body for body in (node[1] for node in K._walk(tree)
                                   if K._is_command(node, "ConditionalsChangeSkillFlag"))]
        self.assertEqual(len(flags), 1)
        boost_paths = K.effect_paths(flags[0][2])
        normal_paths = K.effect_paths(flags[0][3])
        self.assertTrue(all(path.startswith(K.FX_BOLT_DST) for path in boost_paths), boost_paths)
        self.assertTrue(all("psychic_tohru" in path for path in normal_paths), normal_paths)
        self.assertFalse(note["normal"]["direct"])
        self.assertTrue(note["boost"]["direct"])

    def test_boost_thunder_settles_as_direct_attack_and_grows_with_combo(self):
        tree, _ = K.build_thunder_tree(self.context, self.donor, bolt_family())
        flags = [body for body in (node[1] for node in K._walk(tree)
                                   if K._is_command(node, "ConditionalsChangeSkillFlag"))][0]
        area = [body for body in (node[1] for node in K._walk(flags[2])
                                  if K._is_command(node, "CreateHitArea"))][0]
        attack = [body for body in (node[1] for node in K._walk(flags[2])
                                    if K._is_command(node, "CreateNormalAttack"))][0]
        self.assertEqual(area[24], K.BUFF_TARGET_AS_DIRECT)
        self.assertIs(attack[8], True)

    def test_branch_binds_do_not_collide(self):
        tree, _ = K.build_thunder_tree(self.context, self.donor, bolt_family())
        flags = [body for body in (node[1] for node in K._walk(tree)
                                   if K._is_command(node, "ConditionalsChangeSkillFlag"))][0]

        def binds(node):
            out = set()
            for cmd in (n[1] for n in K._walk(node) if K._is_command(n)):
                for ids, _block in L.DSL_SUBJECT_BINDERS.get(cmd[0], ()):
                    for slot in ids:
                        if slot < len(cmd) and isinstance(cmd[slot], int):
                            out.add(cmd[slot])
            return out

        self.assertFalse(binds(flags[2]) & binds(flags[3]),
                         "两个分支的绑定号不能重号（lookup 会解析到错误主体）")

    def test_thunder_tree_keeps_no_reference_to_the_uncloned_donor_family(self):
        tree, _ = K.build_thunder_tree(self.context, self.donor, bolt_family())
        for path in K.effect_paths(tree):
            self.assertFalse(path.startswith(f"{K.FX_BOLT_SRC}/"), path)

    def test_every_lookup_in_the_thunder_tree_resolves(self):
        """1.4.966 事故:强化分支平移了绑定位、引用位留在母本的 0/1 ⇒ 开打 C16103。

        `_dsl_problems` 里已经挂了这条门禁,这里单独再断一次 —— 它是真机崩溃换来的。
        """
        tree, _ = K.build_thunder_tree(self.context, self.donor, bolt_family())
        self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [])

    def test_boost_branch_anchors_on_its_own_bindings_not_the_donor_numbers(self):
        """强化分支的三个引用位必须指向本分支的绑定,而不是常态分支的 0/1。"""
        tree, _ = K.build_thunder_tree(self.context, self.donor, bolt_family())
        flag = [node[1] for node in K._walk(tree)
                if K._is_command(node, "ConditionalsChangeSkillFlag")][0]
        boost, normal = flag[2], flag[3]

        def one(node, name):
            hits = [n[1] for n in K._walk(node) if K._is_command(n, name)]
            self.assertEqual(len(hits), 1, f"{name} 应恰好 1 处")
            return hits[0]

        near = one(boost, "FindNearSubjects")
        rp = one(boost, "CreateReferencePoint")
        area = one(boost, "CreateHitArea")
        self.assertEqual(rp[1], near[5], "CreateReferencePoint 原点必须是 FindNearSubjects 的绑定")
        self.assertEqual(area[2], rp[10], "CreateHitArea 主体必须是 CreateReferencePoint 的绑定")
        anchors = [n[1][3] for n in K._walk(rp[11]) if K._is_command(n, "ShowEffect")]
        self.assertTrue(anchors, "强化分支的参考点块里应有 ShowEffect")
        for anchor in anchors:
            # 要么是内建主体（-18 = 弹射球，射出演出挂在球上），要么是本参考点的绑定；
            # 绝不能是母本遗留的 0/1（那正是 C16103 的签名）。
            self.assertIn(anchor, (rp[10], -1, -2, -17, -18, -33), f"ShowEffect 锚点 {anchor}")
        # 强化分支整体平移过,不能和常态分支撞号(撞号会 lookup 到别的主体,不报错但打错人)
        self.assertNotEqual(near[5], one(normal, "FindNearSubjects")[5])

    def test_mutating_a_lookup_slot_turns_the_gate_red(self):
        """变异检验:把引用位改回母本的 0 必须变红,否则这条门禁等于没接。"""
        tree, _ = K.build_thunder_tree(self.context, self.donor, bolt_family())
        flag = [node[1] for node in K._walk(tree)
                if K._is_command(node, "ConditionalsChangeSkillFlag")][0]
        rp = [n[1] for n in K._walk(flag[2]) if K._is_command(n, "CreateReferencePoint")][0]
        rp[1] = 0
        self.assertNotEqual(K._dsl_problems(tree), [])
        self.assertTrue(any(p.startswith("lookup_scope:") for p in K._dsl_problems(tree)))


# ---------------------------------------------------------------- 3. 已构建的包

@unittest.skipUnless(WORKSPACE.is_dir(), "workspace 尚未构建")
class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads((WORKSPACE / "evidence" / "kit-report.json").read_text("utf-8")) \
            if (WORKSPACE / "evidence" / "kit-report.json").is_file() else {}
        cls.rows = json.loads((WORKSPACE / "evidence" / "kit-rows.json").read_text("utf-8"))
        cls.skills = json.loads((WORKSPACE / "evidence" / "kit-skills.json").read_text("utf-8"))

    def test_skill_and_personal_pf_programs_are_written(self):
        self.assertEqual(len(self.skills["programs"]), 7)
        self.assertIn(K.PIERCE_PROGRAM, self.skills["programs"])
        self.assertIn(K.THUNDER_PROGRAM, self.skills["programs"])

    def test_every_program_file_exists(self):
        for program in self.skills["programs"]:
            path = WORKSPACE / "package" / "roots" / "common" / (
                wf_dsl.dsl_logical(program))
            self.assertTrue(path.is_file(), path)

    def test_three_unique_conditions_with_icons(self):
        self.assertEqual(sorted(self.rows["unique_condition"]),
                         sorted(key for key, *_ in K.UNIQUES))
        for icon in self.rows["icons"]:
            path = WORKSPACE / "package" / "roots" / "common" / icon["logical"]
            self.assertTrue(path.is_file(), path)

    def test_custom_ability_strings_cover_the_panel(self):
        self.assertEqual(sorted(self.rows["custom_ability_string"]), sorted(K.CAS_TEXTS))

    def test_three_effect_families_are_packaged(self):
        for dst in (K.FX_BLADE_DST, K.FX_BOLT_DST, K.FX_TRAIL_DST):
            path = WORKSPACE / "package" / "roots" / "common" / dst
            self.assertTrue(path.is_dir(), path)

    def test_packaged_dsl_has_no_dangling_subject_lookup(self):
        """包里落盘的四棵树都要过作用域门禁 —— 1.4.966 就是这里漏出去的。"""
        root = WORKSPACE / "package" / "roots" / "common"
        programs = sorted(root.rglob("*.action.dsl.amf3.deflate"))
        self.assertTrue(programs, "workspace 里没有 DSL 程序")
        for path in programs:
            tree = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]
            self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [], path.name)

    def test_the_normal_thunder_family_is_not_cloned(self):
        path = WORKSPACE / "package" / "roots" / "common" / "battle/effect/skill_unique/psychic_tohru"
        self.assertFalse(path.exists(), "常态天雷必须只引用官方路径，克隆会让图集 fits=False")

    def test_pixel_and_voice_assets_are_untouched_by_this_rework(self):
        """本轮只改表/DSL/特效/图标；小人与语音一格不改（作者 09-21：凯尔小人不变）。"""
        pixel = WORKSPACE / "package" / "roots" / "common" / "character" / K.CODE / "pixelart"
        self.assertTrue(pixel.is_dir())
        self.assertTrue(any(pixel.iterdir()))


if __name__ == "__main__":
    unittest.main()
