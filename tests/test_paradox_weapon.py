# -*- coding: utf-8 -*-
"""PARADOX（wf_paradox_weapon）生成器离线测试。fixture = live 1.4.1059 的模板行 + 四名角色行 + 角色标签表。"""
from __future__ import annotations

from external_sources import client_patch_path, require_external_source

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wf_battle_rules as BR  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_client_patch_scope as S  # noqa: E402
import wf_cursed_weapons as W  # noqa: E402
import wf_dsl  # noqa: E402
import wf_paradox_weapon as P  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures/paradox_templates.json"
#: 新材料的克隆模板（live 1.4.1067 的五重材料行原样；fixture 文件是 1.4.1059 快照，不含它们）
MATERIAL_TEMPLATES = {
    "10000145": [["five_boss_10000145", "10000145", "深界结晶", "item/materials/mod/five_boss/deep_crystal",
                  "item_icon/materials/mod/five_boss/deep_crystal", "在五重决战深处凝结的强化素材。", "1", "", "", "",
                  "", "", "", "", "9", "(None)", "300", "4", "9999", "2025-06-19 12:00:00", "(None)", "true", ""]],
    "10000147": [["five_boss_10000147", "10000147", "五王心核", "item/materials/mod/five_boss/five_king_core",
                  "item_icon/materials/mod/five_boss/five_king_core", "五名强敌力量汇聚而成的稀有强化核心。", "1", "", "",
                  "", "", "", "", "", "9", "(None)", "500", "5", "9999", "2025-06-19 12:00:00", "(None)", "true", ""]],
}
#: live 图集 item_icon/sprite_sheet 在 wf_weapon_awaken 边 E1 之前 / 之后含的材料子纹理（1.4.1067 实测前者只有五重两件）
PRE_E1_ATLAS = frozenset(rows[0][4] for rows in MATERIAL_TEMPLATES.values())
E1_ATLAS = PRE_E1_ATLAS | {small for *_, small in P.MATERIALS}
#: live 1.4.1067 的两行材料（E1 之前：c3 旧独立 PNG、c4 借五重子纹理）
LIVE_MATERIAL_ROWS = {
    P.SHARD: [["mod_paradox_10000301", "10000301", "矛盾结晶", "item/materials/mod/paradox/contradiction_crystal",
               "item_icon/materials/mod/five_boss/deep_crystal", P.MATERIALS[0][3], "1", "", "", "", "", "", "", "",
               "9", "(None)", "300", "4", "9999", W.START_TIME, "(None)", "true", ""]],
    P.PARADOX_CORE: [["mod_paradox_10000302", "10000302", "悖论之核", "item/materials/mod/paradox/paradox_core",
                      "item_icon/materials/mod/five_boss/five_king_core", P.MATERIALS[1][3], "1", "", "", "", "", "", "",
                      "", "9", "(None)", "500", "5", "9999", W.START_TIME, "(None)", "true", ""]],
}
#: live 1.4.1064 起的强化 Lv120 合计（含本体）——Lv200 续涨不许改动它们（已有存档零变化）
LV120_TOTALS = {("32", "0"): 800, ("33", "0"): 800, ("34", "0"): 800, ("55", "0"): 800, ("388", "0"): 800,
                ("723", "0"): 20, ("693", "0"): 20, ("694", "0"): 20, ("695", "0"): 20, ("696", "0"): 20,
                ("35", "0"): 30, ("245", "0"): 100, ("717", "0"): 150, ("32", P.PRE_MY_SELF): 250, ("226", "0"): 50}
#: 作者 0928 方案甲：强化 Lv200 合计（含本体）；槽上限已顶 +100% 钳制、弹射连击与直击段数不续涨
LV200_TOTALS = {**LV120_TOTALS, **{(k, "0"): 1000 for k in ("32", "33", "34", "55", "388")},
                **{(k, "0"): 30 for k in ("723", "693", "694", "695", "696")},
                ("35", "0"): 50, ("717", "0"): 200, ("32", P.PRE_MY_SELF): 350}


def fixture_data() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["flat"][P.ITEM].update(copy.deepcopy(MATERIAL_TEMPLATES))
    return data


def fixture_reader() -> W.LiveReader:
    data = fixture_data()
    return W.LiveReader(lambda logical: data["flat"].get(logical, {}),
                        lambda logical: data["nested"].get(logical, {}),
                        lambda name: {})


def value_at(row: list[str], table: str, level: int) -> float | None:
    """客户端 MinToMaxLevelScale（AbilityPowerValue.resolve case 1）：未习得 None；≤learn 取 power1、≥max 取 first_max、
    其间线性（只用于端点核对）。强化表 c1 = learn、c2 = max。"""
    learn, top = int(row[1]), int(row[2])
    if level < learn:
        return None
    lo = float(row[W._col(table, "instant_content", "strength.power1")])
    hi = float(row[W._col(table, "instant_content", "strength.first_max")])
    if lo == hi or level >= top:
        return hi
    if level <= learn:
        return lo
    return lo + (hi - lo) * (level - learn) / (top - learn)


def status_at(table: dict[str, str], level: int) -> tuple[int, int] | None:
    """客户端 EquipmentEnhancementStatusLogic.getParameterAt：键排序；低于首键从 0 插值；落在最后一个键的下标时
    按等级精确取（取不到 = null → 空引用崩，这里返回 None）；否则相邻两键间 ceil 插值。"""
    import math
    keys = sorted(int(k) for k in table)
    pairs = {k: tuple(int(x) for x in table[str(k)].split(",")) for k in keys}
    if level < keys[0]:
        return tuple(math.ceil(v * level / keys[0]) for v in pairs[keys[0]])
    index = max(i for i, k in enumerate(keys) if k <= level)
    if index == len(keys) - 1:
        return pairs.get(level)
    a, b = keys[index], keys[index + 1]
    t = (level - a) / (b - a)
    return tuple(y if x == y else math.ceil(x * (1 - t) + y * t) for x, y in zip(pairs[a], pairs[b]))


def _cell(row: list[str], block: str, name: str) -> str:
    return row[W._col(W.SOUL_T, block, name)]


class ParadoxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
        # 目标客户端 = 装了 equipment-rules 补丁 APK；默认 1047 基线的拦截见 test_capability_gate_blocks_unpatched_clients。
        # 图集 = E1 已上线（材料改指重画版）；E1 之前的暂缓见 test_material_icons_wait_for_e1_atlas
        cls.out = P.build(fixture_reader(), client_capabilities=P.PATCHED_CLIENT_CAPABILITIES, atlas_names=E1_ATLAS)
        cls.rows = cls.out["flat"][P.SOUL][P.ID]

    def test_no_problems(self):
        self.assertEqual(self.out["problems"], [])

    def test_stat_values_are_constant_and_as_designed(self):
        expect = {("32", ""): "550000", ("33", ""): "550000", ("34", ""): "550000", ("55", ""): "550000",
                  ("388", ""): "550000", ("723", ""): "10000", ("693", ""): "10000", ("694", ""): "10000",
                  ("695", ""): "10000", ("696", ""): "10000", ("35", ""): "20000", ("245", ""): "50000",
                  ("717", ""): "100000", ("32", P.PRE_MY_SELF): "150000"}
        seen = {}
        for r in self.rows:
            kind = _cell(r, "instant_content", "kind")
            if kind in ("629", "226", "58"):
                continue
            lo, hi = _cell(r, "instant_content", "strength.power1"), _cell(r, "instant_content", "strength.first_max")
            self.assertEqual(lo, hi, kind)                      # 觉醒 1→5 不变
            pre = _cell(r, "precondition1", "kind")
            seen[(kind, "" if pre == "0" else pre)] = lo
        self.assertEqual(seen, expect)

    def test_debuff_immunity_uses_bad_direction_only(self):
        # 58 DebuffPrevent = ConditionPrevent(All(1))；57 是 All(2)（好坏都挡，会挡掉自身增益）——不许用
        kinds = [_cell(r, "instant_content", "kind") for r in self.rows]
        self.assertEqual(kinds.count("58"), 1)
        self.assertNotIn("57", kinds)
        row = next(r for r in self.rows if _cell(r, "instant_content", "kind") == "58")
        self.assertEqual(_cell(row, "instant_content", "target"), W.T_SELF)

    def test_combo_on_every_flip(self):
        row = next(r for r in self.rows if _cell(r, "instant_content", "kind") == "226")
        self.assertEqual(_cell(row, "instant_trigger", "kind"), "6")
        self.assertEqual(_cell(row, "instant_trigger", "threshold.power1"), W.times(1))
        self.assertEqual(_cell(row, "instant_content", "strength.power1"), W.times(35))

    def test_chosen_three_gate(self):
        row = next(r for r in self.rows if _cell(r, "precondition1", "kind") == P.PRE_MY_SELF)
        self.assertEqual(_cell(row, "precondition1", "character_groups").split(","), [t for _, t, _ in P.TAGS])
        self.assertEqual(set(self.out["flat"][P.CHARACTER_TAG]), {t for _, t, _ in P.TAGS})

    def test_character_rows_only_gain_the_tag(self):
        for cid, tag, _ in P.TAGS:
            before = self.fx["flat"][P.CHARACTER][cid][0]
            after = self.out["flat"][P.CHARACTER][cid][0]
            diff = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
            self.assertEqual((len(before), diff), (len(after), [P.TAG_COLUMN]), cid)
            old = [t for t in before[P.TAG_COLUMN].split(",") if t]
            self.assertEqual(after[P.TAG_COLUMN].split(","), old + [tag], cid)
        self.assertEqual(len(P.TAGS), 3)
        self.assertNotIn("129999", self.out["flat"][P.CHARACTER])        # 赛瑞斯按作者 0928 要求移出
        self.assertEqual(self.out["delete"], {P.CHARACTER_TAG: []})

    def test_stale_tags_are_cleaned_after_1060(self):
        # 1.4.1060 曾给赛瑞斯发过 tag_paradox_seris：同步时要把它从角色行和标签表清掉，其余三人不动
        data = fixture_data()
        chars = data["flat"][P.CHARACTER]
        for cid, tag, label in P.TAGS:
            chars[cid][0][P.TAG_COLUMN] = P.retag(chars[cid][0], tag)[P.TAG_COLUMN]
            data["flat"][P.CHARACTER_TAG][tag] = [[label]]
        chars["129999"][0][P.TAG_COLUMN] = "ModDualForm,tag_paradox_seris"
        data["flat"][P.CHARACTER_TAG]["tag_paradox_seris"] = [["赛瑞斯"]]
        read = W.LiveReader(lambda lg: data["flat"].get(lg, {}), lambda lg: data["nested"].get(lg, {}), lambda n: {})
        out = P.build(read, allow_existing=True)
        self.assertEqual(out["flat"][P.CHARACTER]["129999"][0][P.TAG_COLUMN], "ModDualForm")
        self.assertEqual(out["delete"], {P.CHARACTER_TAG: ["tag_paradox_seris"]})
        for cid, tag, _ in P.TAGS:
            self.assertEqual(out["flat"][P.CHARACTER][cid], chars[cid])
        with self.assertRaises(W.CursedWeaponError):
            P.build(read)                                                    # 首发口径：已存在即撞键

    def test_hits_dsl(self):
        tree = self.out["dsl"][P.HITS]
        self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree)
        self.assertEqual(W.dsl_signature_problems(tree), [])
        self.assertEqual(W.colorless_hit_effect_problems(tree), [])
        text = json.dumps(tree)
        self.assertIn('"ACAdditionalDirectAttack"', text)
        self.assertIn('{"min": 6, "max": 6}', text)
        invoke = next(r for r in self.rows if _cell(r, "instant_content", "kind") == "629")
        self.assertEqual(_cell(invoke, "instant_content", "action_path"), P.HITS)
        self.assertIn(_cell(invoke, "instant_content", "string_id"), self.out["flat"][P.CAS])

    def test_weapon_rows_and_server(self):
        equip = self.out["flat"][P.EQUIPMENT][P.ID][0]
        self.assertEqual((equip[1], equip[6], equip[10]), (P.NAME, P.ICON, P.ID))
        self.assertLessEqual(len(equip[7]), W.DESC_LIMITS["equipment"])
        # 衰减规则只能写在说明里（详情页显示满档）：风味句保留，后接规则
        self.assertEqual(equip[7], P.FLAVOR + P.DECAY_RULE)
        self.assertIn("同队每多1件其他武器或魂珠效果-25%", equip[7])
        self.assertNotIn(",", equip[7])
        self.assertNotIn("\n", equip[7])
        self.assertEqual(self.out["nested"][P.EQUIPMENT_STATUS], {P.ID: {"1": "330,148", "5": "495,221"}})
        srv = self.out["server"]
        self.assertEqual(srv["equipment_ids.json"], [int(P.ID)])
        self.assertEqual(srv["equipment_max_level.json"], {P.ID: 5})

    def _ea(self, row: list[str], block: str, name: str) -> str:
        return row[W._col(W.EA_T, block, name)]

    def test_curses_only_at_120_and_base_positive(self):
        # 作者 0928：强化 120 级解放诅咒；本体（满破）只有正面
        for r in self.rows:
            if _cell(r, "instant_content", "kind") in ("629", "226", "58"):
                continue
            self.assertGreater(float(_cell(r, "instant_content", "strength.power1")), 0)
        self.assertNotIn(P.CURSE_UID, json.dumps(self.rows))              # 「诅咒」只在强化 120 级刻
        curses = []
        for r in self.out["flat"][P.EA][P.ID]:
            kind = self._ea(r, "instant_content", "kind")
            negative = kind in ("32", "35") and self._ea(r, "instant_content", "target") == W.T_EXCEPT
            during = self._ea(r, "during_content", "kind")
            if negative or kind in ("209", "461") or during == "423":
                curses.append(kind or during)
                self.assertEqual((r[1], r[2]), ("120", "120"), kind or during)      # learn = max = 120
        # 作者 0928 定稿：-800% 攻击、-40% 充能、无法获得能力和装备的技能槽增加（423 + 开局刻「诅咒」）
        self.assertEqual(sorted(curses), ["32", "35", "423", "461"])

    def _gauge_row(self, key: str = P.ID) -> list[str]:
        rows = [r for r in self.out["flat"][P.EA][key] if self._ea(r, "during_content", "kind") == "423"]
        self.assertEqual(len(rows), 1, key)
        return rows[0]

    def test_gauge_restriction_row_matches_readme(self):
        # client-patch/equipment-rules/README.md「R3 行」逐格核对（equipment_enhancement_ability 126 列）
        row = self._gauge_row()
        slots = [r[0] for r in self.out["flat"][P.EA][P.ID]]
        self.assertEqual(slots, [str(i) for i in range(len(slots))])     # 空闲 slot，追加在末尾
        self.assertEqual(len(row), 126)
        self.assertEqual(row[0:6], [row[0], "120", "120", "48", "48", "1"])
        self.assertEqual((row[6], row[13], row[20]), ("0", "0", "0"))   # 三个前置都是 Always
        self.assertEqual(row[85], "(None)")                               # 持续累计触发
        # 持续触发 = 134「自身持有固有状态」≥1 层、不随层数倍乘；不是 HpHigh 0（面板会显示「生命值0%以上时」）
        self.assertEqual((row[97], row[98], row[100], row[101], row[102], row[104]),
                         (W.DT_UNIQUE, W.P_SELF, W.times(1), W.times(1), "1", P.CURSE_UID))
        self.assertNotEqual(row[97], W.DT_HP_HIGH)
        self.assertEqual(row[108], "false")                               # 持有者阵亡后诅咒解除
        self.assertEqual((row[109], row[110], row[111]), ("423", W.T_EXCEPT, "(None)"))
        self.assertEqual(row[118], "8")
        self.assertEqual(P.GAUGE_MASK, 8)
        self.assertEqual(P.GAUGE_MASK, BR.gauge_mask(["ability"]))
        # 除上面这些格与 c99（来源 Self 不带角色组）外，其余全部留空：瞬发块不残留
        filled = {i for i, v in enumerate(row) if v != ""}
        self.assertEqual(filled, {0, 1, 2, 3, 4, 5, 6, 13, 20, 85, 97, 98, 100, 101, 102, 104, 108, 109, 110, 111, 118})

    def test_curse_unique_condition(self):
        # 开局 461 刻「诅咒」：永续、坏状态、不可驱散、强制付与（c10 短路自身 58 弱体无效的 ConditionPrevent）。
        # 叠层上限必须 >1：R3 的持续触发 134 按层数读，上限 1 时层数恒 0（1.4.1067 首发即失效）
        self.assertEqual(self.out["flat"][P.UNIQUE], {P.CURSE_UID: [P.curse_unique_row()]})
        u = self.out["flat"][P.UNIQUE][P.CURSE_UID][0]
        self.assertEqual(len(u), 15)
        self.assertEqual(u[:5], [f"paradox_curse_{P.CURSE_UID}", "诅咒",
                                 "battle/common/unique_condition/paradox_curse", "99999999", "2"])
        self.assertTrue(P.CURSE_ICON_SRC.is_file())
        # 负对照：上限改回 1，build 必须报出 R3 门禁读不到层数
        from unittest import mock
        original = W.unique_row
        with mock.patch.object(W, "unique_row", lambda sid, name, icon, duration, cap, **kw:
                               original(sid, name, icon, duration, "1" if name == P.CURSE_UNIQUE_NAME else cap, **kw)):
            probs = P.build(fixture_reader(), client_capabilities=P.PATCHED_CLIENT_CAPABILITIES)["problems"]
        self.assertTrue(probs and all(P.CURSE_UID in p and "134" in p for p in probs), probs)
        self.assertEqual((u[9], u[10], u[11], u[13]), ("false", "true", "1", "false"))
        # ID 段：59200000 +（ID−5920000）×10 + k，与诅咒武器 59100000 + 行号×10 + k（行号 ≤ 99）不相交
        self.assertEqual(P.CURSE_UID, "59200011")
        cursed = {w.uid(k) for w in W.weapons() for k in range(10)}
        self.assertNotIn(P.CURSE_UID, cursed)
        self.assertFalse(W.UNIQUE_BASE <= int(P.CURSE_UID) < W.UNIQUE_BASE + 1000)
        grant = [r for r in self.out["flat"][P.EA][P.ID] if self._ea(r, "instant_content", "kind") == "461"]
        self.assertEqual(len(grant), 1)
        g = grant[0]
        self.assertEqual((g[1], g[2], g[5]), ("120", "120", "0"))          # Lv120 瞬发
        self.assertEqual(self._ea(g, "instant_trigger", "kind"), W.IT_INITIAL)
        self.assertEqual((self._ea(g, "instant_content", "target"), self._ea(g, "instant_content", "unique_condition_id"),
                          self._ea(g, "instant_content", "strength.power1")), (W.T_SELF, P.CURSE_UID, W.times(1)))
        self.assertEqual(self._gauge_row()[104], P.CURSE_UID)

    def test_unique_refs_gate(self):
        # 分档行引用的固有状态必须存在：没有 59200011 时 461 与 134 两行都要报；有时不报；423 的规则码 8 不当固有状态查
        for key in (P.ID, *(P.tier_id(n) for n in P.TIERS)):
            missing = [p for r in self.out["flat"][P.EA][key] for p in P.unique_ref_problems(W.EA_T, r, set())]
            self.assertEqual(missing, [f"固有状态 {P.CURSE_UID} 不存在"] * 2, key)
            present = [p for r in self.out["flat"][P.EA][key]
                       for p in P.unique_ref_problems(W.EA_T, r, {P.CURSE_UID})]
            self.assertEqual(present, [], key)
        self.assertNotIn(P.CURSE_UID, fixture_reader().flat(P.UNIQUE))    # fixture 无此键：build 不报 = 自带的行被计入

    def test_capability_gate_blocks_unpatched_clients(self):
        # R3 的 423 行在 1047 = C7050：默认按 1047 基线构建，满档与三个分档的 423 行各报一条缺口，其余行（含魂表）不报
        gauge = self._gauge_row()
        index = self.out["flat"][P.EA][P.ID].index(gauge)
        keys = (P.ID, *(P.tier_id(n) for n in P.TIERS))
        miss = "目标客户端缺 capability {}（未打补丁读到即 C7050）"
        base = P.build(fixture_reader())
        self.assertEqual(base["problems"], [f"{W.EA_T}[{k}]#{index}: {miss.format(S.EQUIPMENT_GAUGE_CAP)}" for k in keys])
        # 需求并集：legality 只报运行时 gauge-gain-rules-v1，解析器的 equipment-gauge-gain-rules-v1 由生成器补齐；
        # 另加装备详情覆盖三键的 equipment-description-override-v1、200 级外观两键的 equipment-enhanced-look-v1
        # 与编成槽框键的 equipment-enhanced-party-frame-v1 —— 都是行为型，两个目标客户端都没有它们，却不进 problems
        want = sorted([BR.GAUGE_CAP, S.EQUIPMENT_GAUGE_CAP, L.EQUIPMENT_DESC_OVERRIDE, P.ENHANCED_LOOK_CAP,
                       P.PARTY_FRAME_CAP])
        self.assertEqual(base["capabilities"], want)
        self.assertEqual(self.out["capabilities"], want)
        self.assertNotIn(L.EQUIPMENT_DESC_OVERRIDE, P.PATCHED_CLIENT_CAPABILITIES)
        self.assertNotIn(P.ENHANCED_LOOK_CAP, P.PATCHED_CLIENT_CAPABILITIES)
        self.assertNotIn(P.PARTY_FRAME_CAP, P.PATCHED_CLIENT_CAPABILITIES)
        self.assertEqual(P.ENHANCED_LOOK_CAP, "equipment-enhanced-look-v1")
        self.assertEqual(P.PARTY_FRAME_CAP, "equipment-enhanced-party-frame-v1")
        self.assertEqual(self.out["problems"], [])
        self.assertEqual(P.row_capabilities(W.EA_T, gauge), [BR.GAUGE_CAP, S.EQUIPMENT_GAUGE_CAP])
        # 没有任何补丁的客户端：423 行两项都缺，仍只有这 4 行
        bare = P.build(fixture_reader(), client_capabilities=())
        self.assertEqual(bare["problems"], [f"{W.EA_T}[{k}]#{index}: {miss.format(c)}"
                                            for k in keys for c in (BR.GAUGE_CAP, S.EQUIPMENT_GAUGE_CAP)])
        # 单个字符串会被拆成字符集合、静默放空门禁：直接拒绝
        with self.assertRaises(W.CursedWeaponError):
            P.build(fixture_reader(), client_capabilities=S.EQUIPMENT_GAUGE_CAP)

    def test_client_capability_sets_match_equipment_rules_patch(self):
        # 1047 基线与补丁 APK 新增的两项以 client-patch/equipment-rules/rules.py 为准
        path = client_patch_path('equipment-rules/rules.py')
        name = "_equipment_rules_for_paradox_test"
        spec = importlib.util.spec_from_file_location(name, require_external_source(path))
        rules = importlib.util.module_from_spec(spec)
        sys.modules[name] = rules  # dataclass 注解解析需要模块已登记
        try:
            spec.loader.exec_module(rules)
        finally:
            sys.modules.pop(name, None)
        self.assertEqual(P.BASE_CLIENT_CAPABILITIES, frozenset(rules.INHERITED_CAPABILITIES))
        self.assertEqual(P.PATCHED_CLIENT_CAPABILITIES - P.BASE_CLIENT_CAPABILITIES,
                         {rules.CAPABILITY_RULES, rules.CAPABILITY_GAUGE})
        self.assertNotIn(rules.CAPABILITY_GAUGE, P.BASE_CLIENT_CAPABILITIES)

    def _totals_at(self, key: str, level: int) -> dict:
        """本体（满破）+ 强化 Lv<level> 已习得行按客户端插值的合计（%；226 为次数）；诅咒（自身以外）不计。"""
        total: dict = {}
        for table, logical in ((W.SOUL_T, P.SOUL), (W.EA_T, P.EA)):
            for r in self.out["flat"][logical][key]:
                mode = r[2] if table == W.SOUL_T else r[5]
                kind = r[W._col(table, "instant_content", "kind")]
                if mode != "0" or r[W._col(table, "instant_content", "target")] == W.T_EXCEPT:
                    continue
                if kind in ("629", "58", "461"):
                    continue
                value = (float(r[W._col(table, "instant_content", "strength.first_max")]) if table == W.SOUL_T
                         else value_at(r, table, level))
                if value is None:
                    continue
                pk = (kind, r[W._col(table, "precondition1", "kind")])
                total[pk] = total.get(pk, 0) + value / (100000 if kind == "226" else 1000)
        return {k: round(v, 6) for k, v in total.items()}

    def test_enhancement_reaches_lv200_totals(self):
        # 方案甲：Lv200 合计 攻击/四类伤害 1000%、独立乘区 30%、充能 50%、槽上限 100%（钳制不涨）、合击 200%、三人 350%
        self.assertEqual(self._totals_at(P.ID, P.MAX_LEVEL), LV200_TOTALS)
        # W.growth_pair 自 d63896fd 起按诅咒武器口径扣「设计值 × 0.2」；PARADOX 本体满额，须折回（= live 1.4.1064 的形状）；
        # 补足行 power1 不动、first_max 抬到 Lv200（20% + 200%）
        first = [(self._ea(r, "instant_content", "strength.power1"), self._ea(r, "instant_content", "strength.first_max"))
                 for r in self.out["flat"][P.EA][P.ID][:2]]
        self.assertEqual(first, [("1933", "230000"), ("20000", "220000")])
        combo = [r for r in self.out["flat"][P.EA][P.ID] if self._ea(r, "instant_content", "kind") == "226"]
        self.assertEqual([(self._ea(r, "instant_content", "strength.power1"), r[1], r[2]) for r in combo],
                         [(W.times(15), "120", "120")])

    def test_lv120_totals_unchanged_regression_lock(self):
        # 已有存档零变化：Lv119 / Lv120 按客户端插值的合计与 live 1.4.1064 起完全一致；满档与三个分档都锁
        self.assertEqual(self._totals_at(P.ID, P.FINAL_LEVEL), LV120_TOTALS)
        for n, ratio in P.TIERS.items():
            got = self._totals_at(P.tier_id(n), P.FINAL_LEVEL)
            for key, want in LV120_TOTALS.items():
                if key == ("226", "0"):
                    continue                                          # 连击按 _half_up 取整，见 test_decay_tier_discrete_rounding
                self.assertAlmostEqual(got[key], want * ratio, delta=0.01, msg=(n, key))
        # 续涨行 = live 的补足行只把 c2 120→200、c4 战力 48→96、first_max 抬高；power1（Lv120 取值）逐字节是 live 值
        topups = {"32": "20000", "33": "20000", "34": "20000", "55": "20000", "388": "20000", "723": "500",
                  "693": "500", "694": "500", "695": "500", "696": "500", "35": "750", "717": "3750"}
        ea = self.out["flat"][P.EA][P.ID]
        continued = [r for r in ea if (r[1], r[2]) == (str(P.FINAL_LEVEL), str(P.MAX_LEVEL))]
        self.assertEqual([r[0] for r in continued], [str(s) for s in (1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 25, 27)])
        for r in continued:
            kind = self._ea(r, "instant_content", "kind")
            want = "6250" if self._ea(r, "precondition1", "kind") == P.PRE_MY_SELF else topups[kind]
            self.assertEqual((self._ea(r, "instant_content", "strength.power1"), r[3], r[4], r[5]),
                             (want, "48", "96", "0"), r[0])
        # 槽上限补足行（slot 23）与直击 / 连击 / 诅咒（slot 28–33）仍是 learn = max = 120
        fixed = [r for r in ea if (r[1], r[2]) == (str(P.FINAL_LEVEL), str(P.FINAL_LEVEL))]
        self.assertEqual([r[0] for r in fixed], ["23", "28", "29", "30", "31", "32", "33"])
        self.assertEqual(self._ea(ea[23], "instant_content", "kind"), "245")

    def test_one_row_per_slot(self):
        # C2324 只在同一 slot 多行时检查成长次序：满档与分档每个 slot 都只一行，续涨不新增行
        for key, rows in self.out["flat"][P.EA].items():
            self.assertEqual([r[0] for r in rows], [str(i) for i in range(34)], key)
            for r in rows:
                self.assertLessEqual(int(r[1]), int(r[2]))
                self.assertLessEqual(int(r[2]), P.MAX_LEVEL)

    def test_enhancement_entry_shop_and_server(self):
        enh = self.out["flat"][P.ENH][P.ID][0]
        # c0 = 200；名字 / 图标 / 说明 / 框仍在 120 级切换（200 级图标与蓝金框走外观两键）
        self.assertEqual(enh[:8], [str(P.MAX_LEVEL), "120", P.NAME120, "120", P.ICON120, "120", P.ENH_DESCRIPTION, "120"])
        self.assertLessEqual(len(enh[6]), W.DESC_LIMITS["enhancement"])
        # 面板上 423 只有通用的「限制技能槽增加」：作者原话写在强化说明里
        self.assertIn("除自身外的角色无法获得能力和装备的技能槽增加效果", enh[6])
        self.assertNotIn(",", enh[6])
        self.assertNotIn("\n", enh[6])
        shop = self.out["flat"][P.ENH_SHOP]
        self.assertEqual(sorted(shop), [f"{P.ID}{s:02d}" for s in range(1, 11)])
        caps = [int(shop[f"{P.ID}{s:02d}"][0][30]) for s in range(1, 11)]
        self.assertEqual(caps, [69, 70, 98, 99, 119, 120, 159, 160, 199, 200])
        self.assertEqual(caps[-1], int(enh[0]))                           # 最后一阶上限 = c0（服务端上限来自末阶）
        costs = {}
        for s in range(1, 11):
            r = shop[f"{P.ID}{s:02d}"][0]
            self.assertEqual((r[0], r[2], r[3], r[29], r[31]), (W.ENH_CATEGORY_KEY, P.ID, str(s), P.ID, "5"))
            costs[s] = tuple((r[i], int(r[i + 1])) for i in (14, 16, 18, 20) if r[i] not in ("", "(None)"))
        # 1–6 阶与 live 1.4.1063 一致（五重材料）；7–10 阶只收新材料
        crystal, core, blueprint = "10000145", "10000147", "10000144"
        self.assertEqual([costs[s] for s in range(1, 7)],
                         [((crystal, 1),), ((crystal, 10), (core, 1)), ((crystal, 2),), ((crystal, 10), (core, 2)),
                          ((crystal, 3), (core, 1)), ((core, 3), (blueprint, 2))])
        self.assertEqual([costs[s] for s in range(7, 11)],
                         [((P.SHARD, 3),), ((P.SHARD, 10), (P.PARADOX_CORE, 1)), ((P.SHARD, 5),), ((P.PARADOX_CORE, 3),)])
        # 7–10 阶用第 6 阶模板：与第 6 阶行只差阶段号 / 费用 / 上限
        template = shop[f"{P.ID}06"][0]
        for s in range(7, 11):
            row = shop[f"{P.ID}{s:02d}"][0]
            self.assertEqual(len(row), len(template))
            self.assertLessEqual({i for i, (a, b) in enumerate(zip(template, row)) if a != b}, {3, *range(14, 22), 30})
        self.assertEqual(self.out["nested"][P.ENH_STATUS], {P.ID: dict(P.PARADOX_ENH_STATUS_ROWS)})

    def test_server_shop_mirrors_client(self):
        # 服务端 equipment_enhancement_shop.json 与客户端商店行一一对应（上限 / 阶段 / 费用 / 分组）
        shop = self.out["flat"][P.ENH_SHOP]
        srv = self.out["server"]["equipment_enhancement_shop.json"]
        self.assertEqual(sorted(srv), sorted(shop))
        for key, rows in shop.items():
            r, v = rows[0], srv[key]
            self.assertEqual((v["enhancementMaxLevel"], v["stage"], v["groupId"], v["equipmentId"], v["shopCategoryId"],
                              v["requireAwakeningLevel"], v["stock"], v["rewards"], v["availableFrom"]),
                             (int(r[30]), int(r[3]), int(P.ID), int(P.ID), 6, 5, -1, [], W.START_TIME), key)
            self.assertEqual([(c["id"], c["amount"]) for c in v["costs"]],
                             [(int(r[i]), int(r[i + 1])) for i in (14, 16, 18, 20) if r[i] not in ("", "(None)")], key)
        self.assertEqual(max(v["enhancementMaxLevel"] for v in srv.values()), P.MAX_LEVEL)
        # 与 live 592000106 的服务端行同形（键序无关）
        self.assertEqual(srv[f"{P.ID}06"], {"availableFrom": W.START_TIME, "availableUntil": None,
                                             "costs": [{"id": 10000147, "amount": 3}, {"id": 10000144, "amount": 2}],
                                             "enhancementMaxLevel": 120, "equipmentId": 5920001, "groupId": 5920001,
                                             "requireAwakeningLevel": 5, "rewards": [], "shopCategoryId": 6,
                                             "stage": 6, "stock": -1})

    def test_status_table_covers_lv200(self):
        # 缺 200 键时 Lv121+ 按等级精确取到 null（客户端空引用崩）；有 200 键时 121 / 160 / 200 插值非空
        table = self.out["nested"][P.ENH_STATUS][P.ID]
        self.assertEqual(table, {"98": "0,0", "99": "50,10", "120": "50,10", "200": "100,40"})
        got = {lv: status_at(table, lv) for lv in (1, 98, 99, 120, 121, 160, 199, 200)}
        self.assertEqual(got, {1: (0, 0), 98: (0, 0), 99: (50, 10), 120: (50, 10), 121: (51, 11), 160: (75, 25),
                               199: (100, 40), 200: (100, 40)})
        self.assertEqual(max(map(int, table)), int(self.out["flat"][P.ENH][P.ID][0][0]))
        old = {k: v for k, v in table.items() if k != "200"}
        self.assertIsNone(status_at(old, 121))                            # 负对照：旧表在 121 级取不到
        with mock.patch.object(P, "PARADOX_ENH_STATUS_ROWS", old), self.assertRaises(W.CursedWeaponError):
            P.build(fixture_reader(), client_capabilities=P.PATCHED_CLIENT_CAPABILITIES)

    def test_paradox_uses_own_copies_of_cursed_constants(self):
        # PARADOX 的阶段 / 数值表是自己的副本：诅咒武器共用常量（29 把在用）改动不连带 PARADOX，反之亦然
        self.assertIsNot(P.PARADOX_ENH_STAGES, W.ENH_STAGES)
        self.assertIsNot(P.PARADOX_ENH_STATUS_ROWS, W.ENH_STATUS_ROWS)
        with mock.patch.object(W, "ENH_STAGES", ((1, ((W.CRYSTAL, 1),)),)), \
                mock.patch.object(W, "ENH_STATUS_ROWS", {"1": "0,0"}):
            again = P.build(fixture_reader(), client_capabilities=P.PATCHED_CLIENT_CAPABILITIES)
        self.assertEqual(again["flat"][P.ENH_SHOP], self.out["flat"][P.ENH_SHOP])
        self.assertEqual(again["nested"], self.out["nested"])
        # 共用 growth_pair 仍写死 119/120（诅咒武器口径）；PARADOX 的续涨只在本模块里改补足行
        rows = W.growth_pair("32", W.T_SELF, 100, 50)
        self.assertEqual([(e.learn, e.maxlvl) for e in rows], [(1, 119), (120, 120)])

    def test_materials(self):
        # 新材料照五重材料行克隆：只换 c0–c5 与开始时间；c3/c4 是重画版（c4 = 图集里 PARADOX 专属子纹理，由 wf_weapon_awaken E1 追加）
        items = self.out["flat"][P.ITEM]
        self.assertEqual(sorted(items), sorted([P.ID, P.SHARD, P.PARADOX_CORE]))
        for iid, template, name, text, thumb, src, small in P.MATERIALS:
            row, base = items[iid][0], MATERIAL_TEMPLATES[template][0]
            self.assertEqual(row[:6], [f"mod_paradox_{iid}", iid, name, thumb, small, text])
            self.assertEqual({i for i, (a, b) in enumerate(zip(base, row)) if a != b}, {0, 1, 2, 3, 4, 5, 19})
            self.assertEqual(row[19], W.START_TIME)
            self.assertNotEqual(small, base[4])                             # 不再借五重的子纹理
            self.assertTrue(small.startswith("item_icon/materials/mod/paradox/"))
            self.assertTrue(thumb.startswith("item/materials/mod/paradox/") and thumb.endswith("_v2"))
            self.assertNotIn(",", text)
            self.assertLessEqual(len(text), P.MATERIAL_DESC_LIMIT)
            self.assertIn(thumb + ".png", self.out["files"])
            self.assertEqual(self.out["files"][thumb + ".png"]["src"], str(src))
            self.assertTrue(Path(src).is_file())
            self.assertEqual(Path(src).parent, P.AWAKEN_ICON_DIR)
        self.assertEqual(self.out["atlas_requires"], sorted(small for *_, small in P.MATERIALS))
        self.assertEqual(self.out["icons_deferred"], {})
        self.assertEqual((P.SHARD, P.PARADOX_CORE), ("10000301", "10000302"))
        # 远离五重 v2 正在用的 10000143–10000147 与武器卡池 999019/999020
        for iid in (P.SHARD, P.PARADOX_CORE):
            self.assertNotIn(int(iid), range(10000140, 10000200))
        srv = self.out["server"]
        self.assertEqual(srv["item_ids.json"], [int(P.ID), 10000301, 10000302])
        self.assertEqual(srv["item_lookup.json"], {"10000301": "矛盾结晶", "10000302": "悖论之核"})
        self.assertEqual({k: v for k, v in srv["item_sale.json"].items() if k != P.ID},
                         {"10000301": {"category": 9, "sale_price": 300, "sellable": True},
                          "10000302": {"category": 9, "sale_price": 500, "sellable": True}})
        # 商店 7–10 阶只用这两种材料
        used = {r[0][i] for k, r in self.out["flat"][P.ENH_SHOP].items() if int(k[-2:]) >= 7
                for i in (14, 16, 18, 20) if r[0][i] not in ("", "(None)")}
        self.assertEqual(used, {P.SHARD, P.PARADOX_CORE})

    def test_english_name_only_in_name_cells(self):
        """作者 0928「武器PARADOX归类为悖论武器，除了武器名字，其他地方都不要英文的，写悖论」。"""
        self.assertEqual("悖论武器", P.CLASS_NAME)
        texts = {iid: text for iid, _t, _n, text, *_ in P.MATERIALS}
        self.assertEqual({P.SHARD: "光与影在同一晶面上互相否定而凝成的结晶。用于将悖论武器强化至121级以上。",
                          P.PARADOX_CORE: "首尾相接、永无终点的悖论之环的核心。用于突破悖论武器的强化上限。"}, texts)
        self.assertEqual([], P.english_name_problems(self.out["flat"]))
        hits = sorted((logical, key, col) for logical, rows in self.out["flat"].items() for key, rs in rows.items()
                      for r in rs for col, cell in enumerate(r) if P.NAME in cell)
        # 英文只剩名字格：装备名、强化名（PARADOX·终式）、魂珠名（PARADOX魂珠）
        self.assertEqual([(P.ENH, P.ID, 2), (P.EQUIPMENT, P.ID, 1), (P.ITEM, P.ID, 2)], hits)
        self.assertEqual((P.NAME, P.NAME120), ("PARADOX", "PARADOX·终式"))
        # 负对照：说明 / 覆盖文案 / 材料说明里写回英文都报红
        for logical, key, col in ((P.ITEM, P.SHARD, 5), (P.EQUIPMENT, P.ID, 7), (P.ENH, P.ID, 6),
                                  (P.CAS, P.OVERRIDE_BASE, 0)):
            with self.subTest(table=logical, key=key, col=col):
                flat = {logical: {key: [list(self.out["flat"][logical][key][0])]}}
                flat[logical][key][0][col] += "PARADOX"
                self.assertTrue(P.english_name_problems(flat))

    def test_lv200_look_keys(self):
        cas = self.out["flat"][P.CAS]
        self.assertEqual(cas[P.LOOK_TIER2_KEY], [["200,item/equipment/mod/paradox/paradox_lv200"]])
        self.assertEqual(cas[P.LOOK_FRAME_KEY], [["item/equipment/mod/paradox/paradox_frame_bluegold"]])
        self.assertEqual(cas[P.LOOK_PARTY_FRAME_KEY], [["item/equipment/mod/paradox/paradox_party_frame_bluegold"]])
        self.assertEqual(P.LOOK_TIER2_KEY, "enhanced_pixelart_tier2_item/equipment/mod/paradox/paradox_lv120")
        self.assertEqual(P.LOOK_FRAME_KEY, "enhanced_frame_override_item/equipment/mod/paradox/paradox_lv200")
        self.assertEqual(P.LOOK_PARTY_FRAME_KEY,
                         "enhanced_party_frame_override_item/equipment/mod/paradox/paradox_lv200")
        enh = self.out["flat"][P.ENH][P.ID][0]
        self.assertEqual(P.look_problems(P.look_texts(), enh, self.out["files"]), [])
        # 单元格里的半角逗号靠 CSV 引号保住一格（客户端 format.csv.Reader 认引号）
        import csv
        import io
        import wf_share_update_codec as X
        raw = X.csv_write(cas[P.LOOK_TIER2_KEY])
        self.assertEqual(X.csv_read(raw), cas[P.LOOK_TIER2_KEY])
        self.assertEqual(next(csv.reader(io.StringIO(__import__("zlib").decompress(raw).decode()))),
                         ["200,item/equipment/mod/paradox/paradox_lv200"])
        files = self.out["files"]
        self.assertEqual(files[P.ICON200 + ".png"]["size"], [20, 20])
        self.assertEqual(files[P.FRAME_BLUEGOLD + ".png"]["size"], [144, 144])
        self.assertFalse(files[P.FRAME_BLUEGOLD + ".png"]["required"])     # 另一执行者在画，缺图时暂存跳过
        self.assertEqual(files[P.PARTY_FRAME_BLUEGOLD + ".png"]["size"], [72, 72])   # 官方 party 框原尺寸
        self.assertTrue(files[P.PARTY_FRAME_BLUEGOLD + ".png"]["required"])
        bad = {
            "level at c3": {**P.look_texts(), P.LOOK_TIER2_KEY: f"120,{P.ICON200}"},
            "level above c0": {**P.look_texts(), P.LOOK_TIER2_KEY: f"201,{P.ICON200}"},
            "no level": {**P.look_texts(), P.LOOK_TIER2_KEY: P.ICON200},
            "png suffix": {**P.look_texts(), P.LOOK_FRAME_KEY: P.FRAME_BLUEGOLD + ".png"},
            "foreign path": {**P.look_texts(), P.LOOK_FRAME_KEY: "item/equipment/mod/cursed/x"},
            "newline": {**P.look_texts(), P.LOOK_FRAME_KEY: P.FRAME_BLUEGOLD + "\n"},
            "missing key": {P.LOOK_TIER2_KEY: P.look_texts()[P.LOOK_TIER2_KEY]},
            "missing party key": {k: v for k, v in P.look_texts().items() if k != P.LOOK_PARTY_FRAME_KEY},
            "party reuses list frame": {**P.look_texts(), P.LOOK_PARTY_FRAME_KEY: P.FRAME_BLUEGOLD},
            "party png suffix": {**P.look_texts(), P.LOOK_PARTY_FRAME_KEY: P.PARTY_FRAME_BLUEGOLD + ".png"},
            "party foreign path": {**P.look_texts(), P.LOOK_PARTY_FRAME_KEY: "item/equipment/mod/cursed/x"},
        }
        for label, texts in bad.items():
            with self.subTest(label):
                self.assertTrue(P.look_problems(texts, enh, files), label)
        wrong_icon = list(enh)
        wrong_icon[4] = P.ICON
        self.assertTrue(P.look_problems(P.look_texts(), wrong_icon, files))
        # legality 只能报各键自己的补丁 capability，不许落进面板覆盖；编成槽框不许归到 v1
        for key in P.LOOK_KEYS:
            self.assertEqual(L.required_client_capabilities(L.CUSTOM_ABILITY_STRING_KIND, [key]), [P.LOOK_CAPS[key]])
        self.assertEqual({P.LOOK_TIER2_KEY: P.ENHANCED_LOOK_CAP, P.LOOK_FRAME_KEY: P.ENHANCED_LOOK_CAP,
                          P.LOOK_PARTY_FRAME_KEY: P.PARTY_FRAME_CAP}, P.LOOK_CAPS)

    def test_look_keys_match_client_patch(self):
        # 键前缀 / capability / 第二档值格式以 client-patch/equipment-enhanced-look/rules.py 为准
        path = client_patch_path('equipment-enhanced-look/rules.py')
        if not path.exists():
            self.skipTest("client-patch/equipment-enhanced-look 尚未落地")
        name = "_equipment_enhanced_look_rules_for_paradox_test"
        spec = importlib.util.spec_from_file_location(name, require_external_source(path))
        rules = importlib.util.module_from_spec(spec)
        sys.modules[name] = rules
        try:
            spec.loader.exec_module(rules)
        finally:
            sys.modules.pop(name, None)
        self.assertEqual((rules.CAPABILITY, rules.TIER2_PREFIX, rules.FRAME_PREFIX),
                         (P.ENHANCED_LOOK_CAP, P.LOOK_TIER2_PREFIX, P.LOOK_FRAME_PREFIX))
        value = P.look_texts()[P.LOOK_TIER2_KEY]
        level, path_ = value.split(rules.TIER2_SEPARATOR)                  # 补丁要求恰好一个逗号
        self.assertEqual(str(int(level)), level)                            # 规范十进制整数
        self.assertTrue(path_)
        self.assertEqual(int(level), P.MAX_LEVEL)

    def test_party_frame_key_matches_client_patch(self):
        # 编成槽框键前缀 / capability 以 client-patch/equipment-enhanced-party-frame/rules.py 为准，叠在 v1 之上
        root = Path(__file__).resolve().parents[2] / "client-patch"
        path = root / "equipment-enhanced-party-frame/rules.py"
        if not path.exists():
            self.skipTest("client-patch/equipment-enhanced-party-frame 尚未落地")
        name = "_equipment_enhanced_party_frame_rules_for_paradox_test"
        spec = importlib.util.spec_from_file_location(name, require_external_source(path))
        rules = importlib.util.module_from_spec(spec)
        sys.modules[name] = rules
        try:
            spec.loader.exec_module(rules)
        finally:
            sys.modules.pop(name, None)
        self.assertEqual((rules.CAPABILITY, rules.PREFIX), (P.PARTY_FRAME_CAP, P.LOOK_PARTY_FRAME_PREFIX))
        self.assertEqual(rules.party_frame_key(P.ICON200), P.LOOK_PARTY_FRAME_KEY)
        self.assertIn(P.ENHANCED_LOOK_CAP, rules.INHERITED_CAPABILITIES)         # 底包 = v1 APK
        # 补丁把框图归一到 72×72 再套 rarity 容器矩阵：PNG 按这个尺寸交付
        size = next(s for logical, _src, s, _req in P.ASSET_FILES if logical == P.PARTY_FRAME_BLUEGOLD + ".png")
        self.assertEqual((rules.FRAME_SIZE, rules.FRAME_SIZE), tuple(size))

    def test_material_icons_wait_for_e1_atlas(self):
        """c4 子纹理不在 live 图集时绝不改指（否则掉落展示 / 图鉴 C8004）：沿用 live 行、不出 c3 图、记 icons_deferred。"""
        smalls = {iid: small for iid, *_, small in P.MATERIALS}
        thumbs = {iid: thumb + ".png" for iid, *_, thumb, _src, _small in P.MATERIALS}

        def with_live_rows():
            data = fixture_data()
            data["flat"][P.ITEM].update(copy.deepcopy(LIVE_MATERIAL_ROWS))
            return W.LiveReader(lambda lg: data["flat"].get(lg, {}), lambda lg: data["nested"].get(lg, {}),
                                lambda n: {})

        # live 1.4.1067 口径（E1 未上线，行已在 live）：不传图集 / 传 E1 前的图集 → 行与 live 逐格相同，stage 零差异
        for atlas in (None, PRE_E1_ATLAS):
            with self.subTest(atlas=atlas):
                out = P.build(with_live_rows(), allow_existing=True, client_capabilities=P.PATCHED_CLIENT_CAPABILITIES,
                              atlas_names=atlas)
                self.assertEqual(out["problems"], [])
                for iid in smalls:
                    self.assertEqual(out["flat"][P.ITEM][iid], LIVE_MATERIAL_ROWS[iid])
                    self.assertNotIn(thumbs[iid], out["files"])
                self.assertEqual(sorted(out["icons_deferred"]), sorted(smalls))
                self.assertTrue(all("沿用 live 行" in r for r in out["icons_deferred"].values()))
        # 首发口径（live 无该行）：沿用模板五重材料行的 c3/c4（已上线子纹理）
        first = P.build(fixture_reader(), client_capabilities=P.PATCHED_CLIENT_CAPABILITIES, atlas_names=PRE_E1_ATLAS)
        self.assertEqual(first["problems"], [])
        for iid, template, *_ in P.MATERIALS:
            self.assertEqual(first["flat"][P.ITEM][iid][0][3:5], MATERIAL_TEMPLATES[template][0][3:5])
        # 只上线一件：只改指那一件
        one = P.build(with_live_rows(), allow_existing=True, client_capabilities=P.PATCHED_CLIENT_CAPABILITIES,
                      atlas_names=PRE_E1_ATLAS | {smalls[P.SHARD]})
        self.assertEqual(one["problems"], [])
        self.assertEqual(one["flat"][P.ITEM][P.SHARD][0][4], smalls[P.SHARD])
        self.assertIn(thumbs[P.SHARD], one["files"])
        self.assertEqual(one["flat"][P.ITEM][P.PARADOX_CORE], LIVE_MATERIAL_ROWS[P.PARADOX_CORE])
        self.assertEqual(list(one["icons_deferred"]), [P.PARADOX_CORE])
        # E1 上线后：改指重画版
        done = P.build(with_live_rows(), allow_existing=True, client_capabilities=P.PATCHED_CLIENT_CAPABILITIES,
                       atlas_names=E1_ATLAS)
        self.assertEqual((done["problems"], done["icons_deferred"]), ([], {}))
        for iid, *_, thumb, _src, small in P.MATERIALS:
            self.assertEqual(done["flat"][P.ITEM][iid][0][3:5], [thumb, small])
        # 给了图集、沿用的 c4 也不在其中（live 本身就坏）→ 报红，暂存的 problems == [] 断言拦下
        bad = P.build(fixture_reader(), client_capabilities=P.PATCHED_CLIENT_CAPABILITIES, atlas_names=())
        self.assertEqual(len([p for p in bad["problems"] if "C8004" in p]), len(P.MATERIALS))
        # 单个字符串会被拆成字符集合：直接拒绝
        with self.assertRaises(W.CursedWeaponError):
            P.build(fixture_reader(), atlas_names=smalls[P.SHARD])

    def test_atlas_names_from_raw(self):
        # 与图集的唯一写入方 wf_weapon_awaken（边 E1）同一逻辑路径、同一编码
        import wf_weapon_awaken as WA
        self.assertEqual(P.MATERIAL_ATLAS_MAP, WA.ATLAS_MAP)
        entries = [{"n": name, "x": 1 + 20 * i, "y": 1, "w": 16, "h": 16} for i, name in enumerate(sorted(E1_ATLAS))]
        raw = WA.encode_atlas(entries)
        self.assertEqual(P.atlas_names_from_raw(raw), E1_ATLAS)
        self.assertEqual(P.atlas_names_from_raw(raw), {str(e["n"]) for e in WA.decode_atlas(raw)})
        self.assertEqual(P.atlas_names_from_raw(None), frozenset())

    def test_materials_track_the_weapon_awaken_redraw(self):
        """材料 c3/c4 与源图跟图标单元的交付合同（manifest.json）逐项一致：下一次暂存不会把道具行改回旧图。"""
        from PIL import Image
        manifest = json.loads((P.AWAKEN_ICON_DIR.parent / "manifest.json").read_text(encoding="utf-8"))
        entries = {e["item_id"]: e for e in manifest["icons"]}
        for iid, _template, _name, _text, thumb, src, small in P.MATERIALS:
            with self.subTest(iid):
                entry = entries[iid]
                self.assertEqual((thumb, small), (entry["c3_logical"], entry["c4_logical"]))
                self.assertEqual(Path(src), P.AWAKEN_ICON_DIR.parent / entry["c3_file"])
                with Image.open(src) as image:
                    pixels = image.convert("RGBA").tobytes()
                self.assertEqual(hashlib.sha256(pixels).hexdigest(), entry["c3_rgba_sha256"])
        # 旧图不再被引用（旧逻辑名留作 live 孤儿；源图文件本身不删）
        sources = {Path(src).name for *_, src, _ in P.MATERIALS}
        self.assertFalse({"paradox_shard.png"} & sources)
        self.assertFalse(any("five_boss" in small for *_, small in P.MATERIALS))

    def test_asset_files_have_the_declared_size(self):
        from PIL import Image
        for logical, src, size, required in P.ASSET_FILES:
            if not src.is_file():
                self.assertFalse(required, logical)
                continue
            with Image.open(src) as image:
                self.assertEqual((tuple(size), "RGBA"), (image.size, image.mode), logical)
        with Image.open(P.ASSET_DIR / "paradox_party_frame_bluegold.png") as image:
            corners = [image.getpixel(xy)[3] for xy in ((0, 0), (71, 0), (0, 71), (71, 71))]
        self.assertEqual([0, 0, 0, 0], corners)                                # 圆角透明（α 照抄官方）

    def test_final_hits_dsl(self):
        tree = self.out["dsl"][P.HITS_FINAL]
        self.assertEqual(W.dsl_signature_problems(tree), [])
        self.assertIn('{"min": 8, "max": 8}', json.dumps(tree))
        paths = [self._ea(r, "instant_content", "action_path") for r in self.out["flat"][P.EA][P.ID]
                 if self._ea(r, "instant_content", "kind") == "629"]
        self.assertEqual(paths, [P.HITS_FINAL])

    def test_decay_tiers_mirror_full_rows(self):
        # client-patch/equipment-rules 按 ID+1000·n 选档：分档行与满档逐行同构，只许强度 / 629 段数 / 连击数不同
        flat = self.out["flat"]
        for logical, table in ((P.SOUL, W.SOUL_T), (P.EA, W.EA_T)):
            full = flat[logical][P.ID]
            strength = {W._col(table, "instant_content", c) for c in ("strength.power1", "strength.first_max")}
            invoke = {W._col(table, "instant_content", c) for c in ("string_id", "action_path")}
            head = 3 if table == W.SOUL_T else 6                          # slot / learn /（max / 战力）/ 触发模式
            for n, ratio in P.TIERS.items():
                tier = flat[logical][P.tier_id(n)]
                self.assertEqual(len(tier), len(full), (logical, n))
                self.assertEqual([r[:head] for r in tier], [r[:head] for r in full], (logical, n))
                for a, b in zip(full, tier):
                    diff = {j for j, (x, y) in enumerate(zip(a, b)) if x != y}
                    if a[head - 1] == "1":                                # 持续行（R3 的 423）：原样
                        self.assertEqual(a, b, (logical, n, "during"))
                        continue
                    kind = a[W._col(table, "instant_content", "kind")]
                    allowed = invoke if kind == "629" else strength
                    self.assertLessEqual(diff, allowed, (logical, n, kind))
                    curse = kind in ("209", "461") or a[W._col(table, "instant_content", "target")] == W.T_EXCEPT
                    if curse or kind == "58":
                        self.assertEqual(a, b, (logical, n, kind))        # 诅咒不缩放、弱体无效保留
                    elif kind not in ("629", "226"):
                        col = W._col(table, "instant_content", "strength.first_max")
                        self.assertAlmostEqual(float(b[col]), float(a[col]) * ratio, delta=1, msg=(logical, n, kind))
        self.assertFalse({P.tier_id(n) for n in P.TIERS} & (set(flat[P.EQUIPMENT]) | set(flat[P.ITEM])))

    def test_decay_tiers_keep_curse_rows_verbatim(self):
        # R3 的 423 行与刻「诅咒」的 461 行在三个分档里逐字相同（诅咒不缩放）；满档 4 行诅咒在各档同一 slot
        ea = self.out["flat"][P.EA]
        full = ea[P.ID]

        def curse_rows(rows: list[list[str]]) -> list[list[str]]:
            return [r for r in rows if self._ea(r, "during_content", "kind") == "423"
                    or self._ea(r, "instant_content", "kind") == "461"
                    or self._ea(r, "instant_content", "target") == W.T_EXCEPT]

        self.assertEqual(len(curse_rows(full)), 4)
        for n in P.TIERS:
            tier = ea[P.tier_id(n)]
            self.assertEqual(curse_rows(tier), curse_rows(full), n)
            self.assertEqual(self._gauge_row(P.tier_id(n)), self._gauge_row(), n)
        self.assertNotIn(P.tier_id(4), ea)                                  # n≥4 整件失效：5924001 不得出现
        self.assertNotIn(P.tier_id(4), self.out["flat"][P.SOUL])

    def test_decay_tier_discrete_rounding(self):
        self.assertEqual([P.hits_segments(n, False) for n in (0, 1, 2, 3)], [6, 5, 4, 2])
        self.assertEqual([P.hits_segments(n, True) for n in (0, 1, 2, 3)], [8, 6, 5, 3])
        combos = []
        for n in (0, 1, 2, 3):
            rows = self.out["flat"][P.SOUL][P.tier_id(n) if n else P.ID]
            combos.append(next(_cell(r, "instant_content", "strength.power1") for r in rows
                               if _cell(r, "instant_content", "kind") == "226"))
        self.assertEqual(combos, [W.times(x) for x in (35, 26, 18, 9)])
        for n in (0, 1, 2, 3):
            for final in (False, True):
                tree = self.out["dsl"][P.hits_program(n, final)]
                seg = P.hits_segments(n, final)
                self.assertIn(f'{{"min": {seg}, "max": {seg}}}', json.dumps(tree))
                self.assertEqual(self.out["flat"][P.CAS][P.hits_key(n, final)], [[P.hits_text(n, final)]])

    def test_skill_echoes(self):
        # 三人专属 25% 回响：自身发动技能 + 自身是该角色（标签）→ 629；分档里原样；DSL 过全部门禁
        tag_of = {cid: tag for cid, tag, _ in P.TAGS}
        for key in (P.ID, *(P.tier_id(n) for n in P.TIERS)):
            rows = [r for r in self.out["flat"][P.SOUL][key]
                    if _cell(r, "instant_content", "kind") == "629" and "echo" in _cell(r, "instant_content", "action_path")]
            self.assertEqual(len(rows), len(P.ECHOES), key)
            for r, (cid, code, _) in zip(rows, P.ECHOES):
                self.assertEqual(_cell(r, "instant_trigger", "kind"), W.IT_SKILL)
                self.assertEqual(_cell(r, "instant_trigger", "trigger_puller"), W.P_SELF)
                self.assertEqual((_cell(r, "precondition1", "kind"), _cell(r, "precondition1", "character_groups")),
                                 (P.PRE_MY_SELF, tag_of[cid]))
                self.assertEqual(_cell(r, "instant_content", "action_path"), P.echo_program(code))
        for cid, code, text in P.ECHOES:
            tree = self.out["dsl"][P.echo_program(code)]
            self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree)
            self.assertEqual(W.dsl_signature_problems(tree), [])
            self.assertEqual(W.colorless_hit_effect_problems(tree), [])
            self.assertEqual(self.out["flat"][P.CAS][f"paradox_echo_{code}"], [[text]])
            self.assertNotIn(",", text)

    def test_deterministic(self):
        again = P.build(fixture_reader(), atlas_names=E1_ATLAS)
        self.assertEqual(json.dumps(again["flat"], sort_keys=True), json.dumps(self.out["flat"], sort_keys=True))
        self.assertEqual(again["dsl"], self.out["dsl"])



# ---------------------------------------------------------------------------
# 装备详情覆盖（desc_override_equipment_*）
# ---------------------------------------------------------------------------

_NUMBER = re.compile(r"[+-]?\d+(?:\.\d+)?")
ROOT = Path(__file__).resolve().parents[2]

#: 作者口径定稿文案（设计稿 text_draft）；生成器任何改动若改了措辞或数字，这里先红。
GOLDEN = {
    P.OVERRIDE_BASE: "\n".join((
        "攻击力与全部伤害类型（直接攻击／技能／能力／强化弹射）+550%＆全部独立乘区+10%",
        "直接攻击判定额外+5次（共6段）",
        "每次弹射时连击数+35",
        "技能充能速度+20%＆技能槽上限+50%",
        "弱体无效（异常状态与数值降低全部无效）",
        "攻击力追加合击角色攻击力的100%",
        "自身为基诺维／杰拉德／凯尔时攻击力再+150%",
        "自身为基诺维时：发动技能1秒后以25%的效果回响「掠影协奏」",
        "自身为杰拉德时：发动技能1.5秒后以25%的效果回响「月耀一闪」",
        "自身为凯尔时：发动技能约1.7秒后以25%的效果回响「月华·狼牙连斩」",
    )),
    P.OVERRIDE_GROWTH: "\n".join((
        "强化Lv1→119逐级提升，强化Lv119时追加：",
        "攻击力与全部伤害类型+230%＆全部独立乘区+9.5%",
        "技能充能速度+9.25%＆技能槽上限+47.5%",
        "合击角色攻击力的追加比例+46.25%",
        "自身为基诺维／杰拉德／凯尔时攻击力再+93.75%",
        "强化Lv120进入终式：数值补足、直接攻击共8段、每次弹射连击合计+50，并解放【诅咒】",
        "强化Lv121→200继续逐级提升，强化Lv200时达到下方合计值",
    )),
    # 补丁把终式块放在「强化Lv<c0>」下：c0 = 200，所以这里是 Lv200 合计（作者 0928 方案甲，只续涨成长行）
    P.OVERRIDE_FINAL: "\n".join((
        "终式合计（含本体）：攻击力与全部伤害类型+1000%＆全部独立乘区+30%",
        "直接攻击判定额外+7次（共8段）",
        "每次弹射时连击数合计+50",
        "技能充能速度合计+50%＆技能槽上限合计+100%",
        "攻击力追加合击角色攻击力的200%",
        "自身为基诺维／杰拉德／凯尔时攻击力合计+350%",
        "【诅咒·Lv120起】自身以外的角色攻击力-800%＆技能充能速度-40%",
        "【诅咒·Lv120起】开局自身获得「诅咒」（永续、无法驱散）：自身以外的角色无法获得能力和装备的技能槽增加效果",
    )),
}


def _find(node, name: str) -> list:
    """DSL 树里第一个以 name 开头的列表节点。"""
    if isinstance(node, list):
        if node and node[0] == name:
            return node
        for child in node:
            hit = _find(child, name)
            if hit:
                return hit
    return []


def _row_totals(out: dict, level: int | None) -> dict:
    """按行重新求和（与生成器常量无关）：键 = (kind, 前置1, 是否「自身以外」)，值 = %（226 为次数）。
    level=None 只算魂表（满破，觉醒 1→5 不变）；否则只算该强化等级已习得的强化行，按客户端 MinToMaxLevelScale 取值
    （≤learn 取 power1、≥max 取 first_max）；要求落在端点上（Lv119 / Lv120 / Lv200 都不落在插值段）。"""
    tables = ((W.SOUL_T, P.SOUL),) if level is None else ((W.EA_T, P.EA),)
    totals: dict = {}
    for table, logical in tables:
        for r in out["flat"][logical][P.ID]:
            mode = r[2] if table == W.SOUL_T else r[5]
            if mode != "0":
                continue
            kind = r[W._col(table, "instant_content", "kind")]
            if kind in ("629", "58", "461"):
                continue
            if table == W.EA_T:
                if int(r[1]) > level:
                    continue
                assert level == int(r[1]) or level >= int(r[2]), (kind, r[1], r[2], level)
                hi = value_at(r, table, level)
            else:
                hi = float(r[W._col(table, "instant_content", "strength.first_max")])
            value = hi / 100000 if kind == "226" else hi / 1000
            key = (kind, r[W._col(table, "precondition1", "kind")],
                   r[W._col(table, "instant_content", "target")] == W.T_EXCEPT)
            totals[key] = totals.get(key, 0.0) + value
    return totals


def _segments(out: dict, table: str, logical: str, *, final: bool) -> int:
    paths = [r[W._col(table, "instant_content", "action_path")] for r in out["flat"][logical][P.ID]
             if r[W._col(table, "instant_content", "kind")] == "629"
             and "$echo_" not in r[W._col(table, "instant_content", "action_path")]]
    assert len(paths) == 1, paths
    node = _find(out["dsl"][paths[0]], "ACAdditionalDirectAttack")
    return int(node[2][0]["min"])


def _echo_scale() -> float:
    """derive_echo.SCALE（按源码读：导入该脚本会解析本机 store）。"""
    src = (Path(__file__).resolve().parents[1] / "assets/paradox/echo/derive_echo.py").read_text(encoding="utf-8")
    return float(re.search(r"^SCALE = ([0-9.]+)$", src, re.M).group(1))


def _expected_numbers(out: dict) -> dict[str, list[float]]:
    """三段文案里应出现的每个数字，全部按生成出的行 / DSL 重新求出（不读生成器的数值常量）。
    终式块由补丁放在「强化Lv<c0>」下，所以它的合计按 c0（强化主表）级取值。"""
    ea = out["flat"][P.EA][P.ID]
    max_lv = int(out["flat"][P.ENH][P.ID][0][0])
    growth_learn = {int(r[1]) for r in ea if int(r[1]) < int(r[2]) and r[5] == "0" and int(r[2]) < max_lv}
    growth_max = {int(r[2]) for r in ea if r[1] == "1" and r[5] == "0"}
    final_learn = {int(r[1]) for r in ea if r[W._col(W.EA_T, "instant_content", "kind")] == "629"}
    continued = {(int(r[1]), int(r[2])) for r in ea if int(r[1]) > 1 and int(r[1]) < int(r[2])}
    curse_learn = {int(r[1]) for r in ea if r[W._col(W.EA_T, "instant_content", "target")] == W.T_EXCEPT}
    assert len(growth_learn) == len(growth_max) == len(final_learn) == len(continued) == len(curse_learn) == 1, \
        (growth_learn, growth_max, final_learn, continued, curse_learn)
    assert continued == {(next(iter(final_learn)), max_lv)}, (continued, max_lv)
    soul, ea119 = _row_totals(out, None), _row_totals(out, growth_max.copy().pop())
    ea120, ea200 = _row_totals(out, next(iter(final_learn))), _row_totals(out, max_lv)

    def same(totals: dict, kinds: tuple, pre: str = "0") -> float:
        values = {round(totals.get((k, pre, False), 0.0), 6) for k in kinds}
        assert len(values) == 1, (kinds, values)
        return values.pop()

    def total(key: tuple, ea_at: dict | None = None) -> float:
        return soul.get(key, 0.0) + (ea200 if ea_at is None else ea_at).get(key, 0.0)

    damage, mult = ("32", "33", "34", "55", "388"), ("723", "693", "694", "695", "696")
    chosen = ("32", P.PRE_MY_SELF, False)
    seg, seg_final = _segments(out, W.SOUL_T, P.SOUL, final=False), _segments(out, W.EA_T, P.EA, final=True)
    at200 = {k: total(k) for k in set(soul) | set(ea200)}
    echoes = []
    for r in out["flat"][P.SOUL][P.ID]:
        path = r[W._col(W.SOUL_T, "instant_content", "action_path")]
        if "$echo_" in path:
            wait = out["dsl"][path][11][1][0][1]
            assert wait[0] == "Wait", wait
            echoes += [round(wait[1] / 60, 1), _echo_scale() * 100]
    return {
        P.OVERRIDE_BASE: [same(soul, damage), same(soul, mult), seg - 1, seg, soul[("226", "0", False)],
                          soul[("35", "0", False)], soul[("245", "0", False)], soul[("717", "0", False)],
                          soul[chosen], *echoes],
        P.OVERRIDE_GROWTH: [growth_learn.pop(), *(growth_max.copy().pop(),) * 2,
                            same(ea119, damage), same(ea119, mult), ea119[("35", "0", False)],
                            ea119[("245", "0", False)], ea119[("717", "0", False)], ea119[chosen],
                            next(iter(final_learn)), seg_final, total(("226", "0", False), ea120),
                            next(iter(final_learn)) + 1, max_lv, max_lv],
        P.OVERRIDE_FINAL: [same(at200, damage), same(at200, mult), seg_final - 1, seg_final,
                           total(("226", "0", False)), total(("35", "0", False)), total(("245", "0", False)),
                           total(("717", "0", False)), total(chosen),
                           next(iter(curse_learn)), ea200[("32", "0", True)], ea200[("35", "0", True)],
                           next(iter(curse_learn))],
    }


def assert_texts_follow_rows(tc: unittest.TestCase, out: dict) -> None:
    """发出去的三段文案（out.flat[CAS]）里的数字 == 按行重算的数字，逐个、按顺序。"""
    expected = _expected_numbers(out)
    for key in P.OVERRIDE_KEYS:
        text = out["flat"][P.CAS][key][0][0]
        got = [round(float(x), 6) for x in _NUMBER.findall(text)]
        tc.assertEqual(got, [round(float(x), 6) for x in expected[key]], key)


class ParadoxDescriptionOverrideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = P.build(fixture_reader(), client_capabilities=P.PATCHED_CLIENT_CAPABILITIES)
        cls.cas = cls.out["flat"][P.CAS]

    def test_three_keys_exactly(self):
        prefixed = sorted(k for k in self.cas if k.startswith(L.EQUIPMENT_DESC_OVERRIDE_KEY_PREFIX))
        self.assertEqual(prefixed, sorted(P.OVERRIDE_KEYS))
        self.assertEqual(P.OVERRIDE_KEYS, ("desc_override_equipment_5920001",
                                           "desc_override_equipment_enhancement_5920001",
                                           "desc_override_equipment_enhancement_5920001_final"))
        for key in P.OVERRIDE_KEYS:
            self.assertEqual(self.cas[key], [[P.override_texts()[key]]], key)
            self.assertEqual(L.equipment_desc_override_key_problems(key), [], key)
            self.assertEqual(L.panel_override_capability(key), L.EQUIPMENT_DESC_OVERRIDE, key)
        # 键里的 ID：本体键按魂 ID（equipment c10）、强化键按装备 ID —— PARADOX 两者都是 5920001
        self.assertEqual(self.out["flat"][P.EQUIPMENT][P.ID][0][10], P.ID)
        self.assertEqual(set(self.out["flat"][P.ENH]), {P.ID})
        self.assertIn(P.ID, self.out["flat"][P.SOUL])
        # 其余 CAS 键（段数 / 回响说明 / 200 级外观）不属于任何面板覆盖
        for key in set(self.cas) - set(P.OVERRIDE_KEYS):
            self.assertIn(L.panel_override_capability(key), (None, P.ENHANCED_LOOK_CAP), key)
            if key not in P.LOOK_KEYS:
                self.assertIsNone(L.panel_override_capability(key), key)

    def test_golden_texts(self):
        self.assertEqual(P.override_texts(), GOLDEN)

    def test_texts_follow_the_rows(self):
        assert_texts_follow_rows(self, self.out)

    def test_drift_check_catches_text_or_row_edits(self):
        # 负对照：只改文案、或只改行，按行重算的核对都必须红
        tampered = copy.deepcopy(self.out)
        text = tampered["flat"][P.CAS][P.OVERRIDE_BASE][0][0]
        tampered["flat"][P.CAS][P.OVERRIDE_BASE] = [[text.replace("+550%", "+551%", 1)]]
        with self.assertRaises(AssertionError):
            assert_texts_follow_rows(self, tampered)
        tampered = copy.deepcopy(self.out)
        row = tampered["flat"][P.SOUL][P.ID][0]
        self.assertEqual(row[W._col(W.SOUL_T, "instant_content", "kind")], "32")
        row[W._col(W.SOUL_T, "instant_content", "strength.first_max")] = "551000"
        with self.assertRaises(AssertionError):
            assert_texts_follow_rows(self, tampered)
        tampered = copy.deepcopy(self.out)
        for r in tampered["flat"][P.EA][P.ID]:
            if r[W._col(W.EA_T, "instant_content", "kind")] == "723" and r[1] == "1":
                r[W._col(W.EA_T, "instant_content", "strength.first_max")] = "9000"
        with self.assertRaises(AssertionError):
            assert_texts_follow_rows(self, tampered)

    def test_changing_a_value_changes_rows_and_text(self):
        cases = (
            ("ATK_BASE", 600, P.OVERRIDE_BASE, "+600%"),
            ("ATK_BASE", 600, P.OVERRIDE_GROWTH, "攻击力与全部伤害类型+180%"),
            ("MULT_TOTAL", 25, P.OVERRIDE_GROWTH, "全部独立乘区+14.375%"),
            ("MULT_TOTAL200", 40, P.OVERRIDE_FINAL, "全部独立乘区+40%"),
            ("ATK_TOTAL200", 1200, P.OVERRIDE_FINAL, "攻击力与全部伤害类型+1200%"),
            ("CHARGE_TOTAL200", 60, P.OVERRIDE_FINAL, "技能充能速度合计+60%"),
            ("UNISON_TOTAL200", 250, P.OVERRIDE_FINAL, "合击角色攻击力的250%"),
            ("CHOSEN_TOTAL200", 400, P.OVERRIDE_FINAL, "攻击力合计+400%"),
            ("CHARGE_BASE", 25, P.OVERRIDE_GROWTH, "技能充能速度+4.25%"),
            ("GAUGE_TOTAL", 120, P.OVERRIDE_FINAL, "技能槽上限合计+120%"),
            ("UNISON_BASE", 80, P.OVERRIDE_BASE, "合击角色攻击力的80%"),
            ("CHOSEN_TOTAL", 300, P.OVERRIDE_GROWTH, "攻击力再+142.5%"),
            ("HITS_EXTRA_BASE", 4, P.OVERRIDE_BASE, "额外+4次（共5段）"),
            ("HITS_EXTRA_FINAL", 9, P.OVERRIDE_FINAL, "额外+9次（共10段）"),
            ("COMBO_BASE", 30, P.OVERRIDE_BASE, "连击数+30"),
            ("COMBO_TOTAL", 60, P.OVERRIDE_FINAL, "连击数合计+60"),
            ("CURSE_ATK", -500, P.OVERRIDE_FINAL, "攻击力-500%"),
            ("CURSE_CHARGE", -30, P.OVERRIDE_FINAL, "技能充能速度-30%"),
        )
        for name, value, key, needle in cases:
            with self.subTest(name=name, key=key), mock.patch.object(P, name, value):
                out = P.build(fixture_reader(), client_capabilities=P.PATCHED_CLIENT_CAPABILITIES)
                self.assertEqual(out["problems"], [])
                self.assertIn(needle, out["flat"][P.CAS][key][0][0])
                self.assertNotEqual(out["flat"][P.CAS][key], self.cas[key])
                assert_texts_follow_rows(self, out)                   # 行跟着变，文案仍与行一致

    def test_constants_match_the_row_machinery(self):
        # 成长行 1→FINAL_LEVEL−1、终式 / 诅咒行 FINAL_LEVEL（W.growth_pair 写死 119/120）、续涨行 FINAL_LEVEL→MAX_LEVEL；
        # 强化 c0 = MAX_LEVEL，名/图/说明/框仍在 FINAL_LEVEL 切换
        ea = self.out["flat"][P.EA][P.ID]
        self.assertEqual({(r[1], r[2]) for r in ea}, {("1", str(P.FINAL_LEVEL - 1)),
                                                        (str(P.FINAL_LEVEL), str(P.FINAL_LEVEL)),
                                                        (str(P.FINAL_LEVEL), str(P.MAX_LEVEL))})
        enh = self.out["flat"][P.ENH][P.ID][0]
        self.assertEqual((enh[0], enh[1], enh[3], enh[5], enh[7]),
                         (str(P.MAX_LEVEL), *(str(P.FINAL_LEVEL),) * 4))
        self.assertEqual(P.PARADOX_ENH_STAGES[-1][0], P.MAX_LEVEL)
        self.assertIn(str(P.MAX_LEVEL), P.PARADOX_ENH_STATUS_ROWS)
        # 只改 c0 不配套加阶段 / 数值表键 = build 硬拦（Lv121+ 空引用崩 / 服务端上限对不上）
        with mock.patch.object(P, "MAX_LEVEL", 180), self.assertRaises(W.CursedWeaponError):
            P.build(fixture_reader(), client_capabilities=P.PATCHED_CLIENT_CAPABILITIES)
        self.assertEqual(set(P.DAMAGE_KINDS), {"32", *(k for k, _ in P.DAMAGE_TYPE_TEXT)})
        self.assertEqual(len(P.MULT_KINDS), 5)
        # 回响比例 = derive_echo.SCALE；回响短名与延迟和已发布的 629 说明一致
        self.assertEqual(P.ECHO_PERCENT, round(_echo_scale() * 100))
        self.assertEqual(set(P.ECHO_SKILL), {code for _, code, _ in P.ECHOES})
        self.assertEqual([P.echo_delay_frames(code) for _, code, _ in P.ECHOES], [60, 90, 100])
        for _, code, text in P.ECHOES:
            head = f"「{P.ECHO_SKILL[code]}」回响：{P.seconds_text(P.echo_delay_frames(code))}后以{P.ECHO_PERCENT}%的效果"
            self.assertTrue(text.startswith(head), (code, text))

    def test_no_override_for_decay_tiers(self):
        tiers = [P.tier_id(n) for n in (*P.TIERS, 4)]
        for key in self.cas:
            for tid in tiers:
                self.assertNotIn(tid, key)
        texts = P.override_texts()
        equip = self.out["flat"][P.EQUIPMENT][P.ID][0]
        for tid in tiers:
            for key in (f"desc_override_equipment_{tid}", f"desc_override_equipment_enhancement_{tid}",
                        f"desc_override_equipment_enhancement_{tid}_final"):
                problems = P.override_text_problems({key: texts[P.OVERRIDE_BASE]}, equip)
                self.assertTrue(any("分档" in p for p in problems), (key, problems))

    def test_validator_negative_controls(self):
        texts = P.override_texts()
        equip = self.out["flat"][P.EQUIPMENT][P.ID][0]
        self.assertEqual(P.override_text_problems(texts, equip), [])
        base = texts[P.OVERRIDE_BASE]
        bad = {
            "comma": {P.OVERRIDE_BASE: base + ",x"},
            "cr": {P.OVERRIDE_BASE: base.replace("\n", "\r\n", 1)},
            "empty line": {P.OVERRIDE_BASE: base.replace("\n", "\n\n", 1)},
            "trailing newline": {P.OVERRIDE_BASE: base + "\n"},
            "leading space": {P.OVERRIDE_BASE: " " + base},
            "long line": {P.OVERRIDE_BASE: "攻" * (P.OVERRIDE_LINE_LIMIT + 1)},
            "hp low": {P.OVERRIDE_BASE: "生命值100%以下时攻击力+10%"},
            "hp high": {P.OVERRIDE_GROWTH: "生命值0%以上时攻击力+10%"},
            "leader": {P.OVERRIDE_FINAL: "自身为队长时攻击力+10%"},
            "self pf": {P.OVERRIDE_BASE: "自身的强化弹射伤害+550%"},
            "pf self": {P.OVERRIDE_BASE: "强化弹射伤害+550%（仅自身）"},
            "empty text": {P.OVERRIDE_BASE: ""},
            "foreign id": {"desc_override_equipment_5910101": base},
            "malformed key": {"desc_override_equipment_5920001_final": base},
        }
        for label, case in bad.items():
            with self.subTest(label):
                self.assertTrue(P.override_text_problems(case, equip), label)
        wrong = list(equip)
        wrong[10] = P.tier_id(1)
        self.assertTrue(P.override_text_problems(texts, wrong))
        # build 硬拦：坏文案不出行
        with mock.patch.object(P, "override_texts", lambda: {**texts, P.OVERRIDE_BASE: base + ",x"}):
            with self.assertRaises(W.CursedWeaponError):
                P.build(fixture_reader(), client_capabilities=P.PATCHED_CLIENT_CAPABILITIES)

    def test_capability_is_behaviour_only(self):
        # 缺 equipment-description-override-v1 的客户端（1047 / equipment-rules / 无补丁）只是显示原文案：
        # capabilities 报它，problems 永远不报它；加上它也不改变 problems
        for have in ((), P.BASE_CLIENT_CAPABILITIES, P.PATCHED_CLIENT_CAPABILITIES):
            out = P.build(fixture_reader(), client_capabilities=have)
            self.assertIn(L.EQUIPMENT_DESC_OVERRIDE, out["capabilities"])
            self.assertFalse(any(L.EQUIPMENT_DESC_OVERRIDE in p for p in out["problems"]), have)
            more = P.build(fixture_reader(), client_capabilities=set(have) | {L.EQUIPMENT_DESC_OVERRIDE})
            self.assertEqual(more["problems"], out["problems"])
        self.assertNotIn(L.EQUIPMENT_DESC_OVERRIDE, P.PATCHED_CLIENT_CAPABILITIES)

    def test_capability_name_matches_client_patch(self):
        path = client_patch_path('equipment-description-override/rules.py')
        if not path.exists():
            self.skipTest("client-patch/equipment-description-override 尚未落地")
        name = "_equipment_description_override_rules_for_paradox_test"
        spec = importlib.util.spec_from_file_location(name, require_external_source(path))
        rules = importlib.util.module_from_spec(spec)
        sys.modules[name] = rules
        try:
            spec.loader.exec_module(rules)
        finally:
            sys.modules.pop(name, None)
        self.assertEqual(rules.CAPABILITY, L.EQUIPMENT_DESC_OVERRIDE)
        # 补丁拼键用的三段字面量 = 这里发出的三键
        self.assertEqual((rules.BASE_PREFIX + P.ID, rules.ENH_PREFIX + P.ID, rules.ENH_PREFIX + P.ID + rules.FINAL_SUFFIX),
                         P.OVERRIDE_KEYS)
        self.assertEqual(rules.BASE_PREFIX, L.EQUIPMENT_DESC_OVERRIDE_KEY_PREFIX)


if __name__ == "__main__":
    unittest.main()
