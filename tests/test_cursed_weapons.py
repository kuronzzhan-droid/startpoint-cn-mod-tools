# -*- coding: utf-8 -*-
"""诅咒武器 29 把生成器（wf_cursed_weapons）的离线测试。

fixture 只含模板行（live 1.4.1056 快照）；与 live 的撞键检查在暂存脚本里对真 store 做。
锁定：口径（本体只正面且很弱、诅咒强化 1 级起全额、120 级终值）、强化/商店/上架形状、客户端合法性与 DSL 签名、
服务端镜像与客户端行一致；作者 0928 数值预算（刃 ≤1000%、乘区 ≤50%、不要脸的提案 ≤600%）及其负对照。
"""
from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wf_battle_rules as BR  # noqa: E402
import wf_cursed_weapons as W  # noqa: E402
import wf_dsl  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures/cursed_weapons_templates.json"
NEGATIVE_KINDS = {"19", "219", "209", "208", "479", "475"}      # 麻痹/封印/比例伤害/增益无效/回复无效
CURSE_COMMANDS = {"SubtractSkillPoint", "RemoveMultiball", "SuppressBallActivity", "DeleteCondition"}
#: ACFixedSpeed：被诅咒的面具的「弹球速度固定 200%」作者 0928 定为负面（强制付与）
CURSE_ACS = {"ACParalysis", "ACComboRestriction", "ACHealRejection", "ACPoison", "ACSilence", "ACBuffRejection",
             "ACFixedSpeed"}
FIVE_BOSS_MATERIALS = {W.BLUEPRINT, W.CRYSTAL, W.CORE}


def fixture_reader() -> W.LiveReader:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return W.LiveReader(lambda logical: data["flat"].get(logical, {}),
                        lambda logical: data["nested"].get(logical, {}),
                        lambda name: {})


def _col(table: str, block: str, name: str) -> int:
    return W._col(table, block, name)


def _strengths(table: str, row: list[str]) -> list[float]:
    block = "instant_content" if row[W._LAYOUT[table]["blocks"]["precondition1"] - 1] == "0" else "during_content"
    lo, hi = row[_col(table, block, "strength.power1")], row[_col(table, block, "strength.first_max")]
    return [float(x) for x in (lo, hi) if x not in ("", "(None)")]


def _kind(table: str, row: list[str]) -> str:
    mode = row[W._LAYOUT[table]["blocks"]["precondition1"] - 1]
    return row[_col(table, "instant_content" if mode == "0" else "during_content", "kind")]


def _walk(node):
    yield node
    if isinstance(node, list):
        for child in node:
            yield from _walk(child)
    elif isinstance(node, dict):
        for child in node.values():
            yield from _walk(child)


def _dsl_is_curse(tree) -> bool:
    for node in _walk(tree):
        if isinstance(node, list) and len(node) == 2 and node[0] == "Command" and node[1][0] in CURSE_COMMANDS:
            return True
        if isinstance(node, list) and node and isinstance(node[0], str) and node[0] in CURSE_ACS:
            return True
        if isinstance(node, list) and len(node) >= 3 and isinstance(node[0], str) and node[0].startswith("AC"):
            for part in node[1:]:
                if isinstance(part, list) and part and isinstance(part[0], dict) and part[0].get("min", 0) < 0:
                    return True
    return False


class CursedWeaponTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 本机已装 equipment-rules 补丁（封能风笛的装备表 423 行需要它）；默认 1047 基线的拦截见 test_capability_gate
        cls.out = W.build(fixture_reader(), client_capabilities=W.PATCHED_CLIENT_CAPABILITIES)
        cls.ws = cls.out["weapons"]

    def test_no_legality_or_dsl_problems(self):
        self.assertEqual(self.out["problems"], [])

    def test_weapon_set_matches_sheet(self):
        self.assertEqual([w.row for w in self.ws], list(range(1, 30)))
        self.assertEqual([w.id for w in self.ws], [str(5910100 + r) for r in range(1, 30)])
        for logical in (W.ITEM, W.EQUIPMENT, W.SOUL, W.ENH, W.EA):
            self.assertEqual(sorted(self.out["flat"][logical]), sorted(w.id for w in self.ws), logical)

    def test_base_is_positive_only(self):
        dsl = self.out["dsl"]
        for w in self.ws:
            for index, row in enumerate(self.out["flat"][W.SOUL][w.id]):
                where = f"{w.name} S{index}"
                self.assertNotIn(_kind(W.SOUL_T, row), NEGATIVE_KINDS, where)
                self.assertTrue(all(v >= 0 for v in _strengths(W.SOUL_T, row)), where)
                if _kind(W.SOUL_T, row) == "629":
                    program = row[_col(W.SOUL_T, "instant_content", "action_path")]
                    self.assertFalse(_dsl_is_curse(dsl[program]), where)

    def test_curses_full_from_level_1(self):
        # 作者 0928：强化 1 级后诅咒直接给满 ⇒ 负面行一律 learn=1、max=120、两端同值（不随等级成长）
        dsl = self.out["dsl"]
        for w in self.ws:
            for index, row in enumerate(self.out["flat"][W.EA][w.id]):
                learn, maxlvl = int(row[1]), int(row[2])
                kind = _kind(W.EA_T, row)
                negative = kind in NEGATIVE_KINDS or any(v < 0 for v in _strengths(W.EA_T, row))
                if kind == "629":
                    negative = negative or _dsl_is_curse(dsl[row[_col(W.EA_T, "instant_content", "action_path")]])
                if negative:
                    self.assertEqual((learn, maxlvl), (1, 120), f"{w.name} E{index}")
                    self.assertLessEqual(len(set(_strengths(W.EA_T, row))), 1, f"{w.name} E{index}")

    def test_base_is_weak(self):
        # 作者 0928「要的就是强化前非常弱」：本体满破 = 设计值 × BASE_SCALE，成长行补回，120 级终值不变；
        # 觉醒分级（满破锚定）：觉醒 0 = 满破 × AWAKEN_FLOOR，设计区间下限不再使用
        w01 = next(w for w in self.ws if w.row == 1)
        soul = self.out["flat"][W.SOUL][w01.id][0]
        self.assertEqual(soul[_col(W.SOUL_T, "instant_content", "strength.first_max")], "8000")      # 设计 40% × 0.2
        self.assertEqual(soul[_col(W.SOUL_T, "instant_content", "strength.power1")], "1600")         # 满破 8% × 0.2
        ea = [r for r in self.out["flat"][W.EA][w01.id] if _kind(W.EA_T, r) == "32"]
        # 作者 0928「尽量还原原本设计」：去掉实现方加的常驻攻击力强化成长，强化表不再有 32 行（只剩吞噬 629）
        self.assertEqual(ea, [])
        eff = W.Eff("0", W.stat("32", W.T_SELF, 20, 40), note="HP≥50% 时自身攻击力 +20%→40%")
        weak = W._weaken(eff)
        self.assertEqual(weak.content[1]["strength"], ("1600", "8000"))
        self.assertEqual(weak.note, "HP≥50% 时自身攻击力 +1.6%→8%")
        # 单值计时状态（蛰龙之心、人格召唤枪的写法）同样分级：单值 → (觉醒 0, 满破) 区间
        timed = W.Eff("0", W.condition("0", W.T_PARTY, 100, 600), note="第 50 秒起全队攻击力 +100%（10 秒）")
        weak = W._weaken(timed)
        self.assertEqual(weak.content[1]["strength"], ("4000", "20000"))
        self.assertEqual(weak.note, "第 50 秒起全队攻击力 +4%→20%（10 秒）")
        self.assertEqual(W.condition("0", W.T_PARTY, (4, 20), 600)[1]["strength"], ("4000", "20000"))
        mech = W.Eff("0", W.stat("245", W.T_SELF, 100, 100))
        self.assertIs(W._weaken(mech), mech)                    # 机制类不缩
        # 负对照：满破值小到觉醒 0 取整后五级不可区分、说明里两处强度（改写有歧义）必须拦下
        with self.assertRaises(W.CursedWeaponError):
            W._weaken(W.Eff("0", ("32", {"target": W.T_SELF, "strength": ("1", "1")})))
        with self.assertRaises(W.CursedWeaponError):
            W._weaken(W.Eff("0", W.stat("32", W.T_SELF, 20, 40), note="攻击力 +20%→40%，技能伤害 +10%"))
        # 负对照：满破不是 0.5% 的倍数（设计 41.25% × 0.2 = 8.25% ⇒ 1.65/3.3/4.95/6.6/8.25%）必须在生成器里拦下
        with self.assertRaises(W.CursedWeaponError):
            W._weaken(W.Eff("0", W.stat("32", W.T_SELF, 20, 41.25), note="攻击力 +20%→41.25%"))

    # ------------------------------------------------------------------
    # 觉醒分级（作者 0928「每个等级也要设计区分数值」；设计 武器觉醒与新掉落-20260928 §3.3 / 附录 A）
    # ------------------------------------------------------------------

    #: 满破（觉醒 4）值，单位 %，按本体行序只列数值行（WEAK_KINDS）。满破锚定：与改前逐字节相同，预算不变。
    FULL_AWAKENING_PCT = {
        1: (8, 2), 2: (40,), 3: (20,), 4: (12, 12, 8), 5: (10,), 6: (40, 40), 7: (30,) * 6, 8: (12, 12), 9: (20, 20),
        10: (), 11: (12, 10), 12: (10, 10), 13: (6,), 14: (60,), 15: (24, 72), 16: (3, 24, 24), 17: (50,),
        18: (20, 100, 4, 8, 16, 60, 40, 20), 19: (35, 65), 20: (48, 48), 21: (48, 48), 22: (30, 30), 23: (7.5, 9),
        24: (10,) * 4, 25: (5, 60), 26: (10, 5), 27: (14,) * 3, 28: (10, 40), 29: (5, 20)}
    #: 机制行：不随觉醒变化；206（被诅咒的面具吸血）例外——不缩 BASE_SCALE，但作者 0928 要求同样按觉醒 0 = 满破 20% 分级
    MECHANISM_KINDS = {"245", "461", "525", "26", "226", "58", "629", "206"}

    def _numeric_soul_rows(self):
        for w in self.ws:
            for index, row in enumerate(self.out["flat"][W.SOUL][w.id]):
                if _kind(W.SOUL_T, row) in W.WEAK_KINDS and _strengths(W.SOUL_T, row):
                    yield w, index, row

    @staticmethod
    def _content_block(row: list[str]) -> str:
        return "instant_content" if row[2] == "0" else "during_content"

    def test_awakening_ladder_numeric_rows(self):
        # 每条本体数值行：power1 = round(0.2 × first_max) < first_max；觉醒 0–4 五级互不相同、显示不超过 1 位小数
        self.assertEqual(W.AWAKEN_FLOOR, 0.2)
        count = 0
        for w, index, row in self._numeric_soul_rows():
            where = f"{w.name} S{index}"
            block = self._content_block(row)
            p1 = int(row[_col(W.SOUL_T, block, "strength.power1")])
            fm = int(row[_col(W.SOUL_T, block, "strength.first_max")])
            self.assertLess(p1, fm, where)
            self.assertEqual(p1, round(0.2 * fm), where)
            self.assertEqual(p1 * 5, fm, where)                  # 满破都是 0.5% 的倍数 ⇒ 取整无损
            # 客户端 AbilityPowerValue.resolve：觉醒 N = p1 + (fm − p1) × N/4（存储值 1000 = 1%）
            levels = [Fraction(p1) + Fraction(fm - p1) * n / 4 for n in range(5)]
            self.assertEqual(len(set(levels)), 5, where)
            self.assertEqual(levels, [Fraction(fm * (n + 1), 5) for n in range(5)], where)     # 20/40/60/80/100%
            self.assertTrue(all((v / 100).denominator == 1 for v in levels), (where, levels))   # 0.1% 粒度
            count += 1
        # 设计 §3.2/§3.3 的 62 条 + 评分审查 0928 新增 3 条（超频芯片技能伤害、肉斩骨断全队直击、面具攻击力）
        self.assertEqual(count, 65)

    def test_full_awakening_values_unchanged(self):
        got = {w.row: () for w in self.ws}
        for w, _index, row in self._numeric_soul_rows():
            got[w.row] += (int(row[_col(W.SOUL_T, self._content_block(row), "strength.first_max")]),)
        self.assertEqual(got, {row: tuple(v * 1000 for v in pcts) for row, pcts in self.FULL_AWAKENING_PCT.items()})

    def test_awakening_mechanism_rows_stay_flat(self):
        # 机制行（245/461/525/26/226/629/206）强度与所有前置/触发阈值不随觉醒变化；唯一例外是赌注已下本体的触发周期
        mechanism = 0
        for w in self.ws:
            for index, row in enumerate(self.out["flat"][W.SOUL][w.id]):
                where = f"{w.name} S{index}"
                kind = _kind(W.SOUL_T, row)
                values = _strengths(W.SOUL_T, row)
                if kind not in W.WEAK_KINDS or not values:
                    mechanism += 1
                    self.assertIn(kind, self.MECHANISM_KINDS, where)
                    if kind == "206":
                        self.assertEqual(values, [200.0, 1000.0], where)      # 觉醒 0 = 满破 1% 的 20%
                    elif values:
                        self.assertEqual(values[0], values[1], where)
                trigger = "instant_trigger" if row[2] == "0" else "during_trigger"
                for blk in (trigger, "precondition1", "precondition2", "precondition3"):
                    try:
                        lo, hi = (row[_col(W.SOUL_T, blk, f"threshold.{n}")] for n in ("power1", "first_max"))
                    except KeyError:
                        continue
                    if (w.row, index, blk) == (10, 0, "instant_trigger"):
                        continue
                    self.assertEqual(lo, hi, (where, blk))
        self.assertEqual(mechanism, 17)                           # 245/461×2/525（咸鱼 0928 两层）、629×3、26/226×2、461×4、206×2

    def test_wager_body_period_ladder(self):
        # 赌注已下本体只有 629（无强度）：用 ElapsedTime 周期分级 45/40/35/30/25 秒；强化表的完整老虎机仍 25 秒
        (row,) = self.soul(10)
        self.assertEqual(_kind(W.SOUL_T, row), "629")
        self.assertEqual(self.cell(W.SOUL_T, row, "instant_trigger", "kind"), W.IT_ELAPSED)
        lo = int(self.cell(W.SOUL_T, row, "instant_trigger", "threshold.power1"))
        hi = int(self.cell(W.SOUL_T, row, "instant_trigger", "threshold.first_max"))
        self.assertEqual((lo, hi), (int(W.frames(2700)), int(W.frames(1500))))
        seconds = [(Fraction(lo) + Fraction(hi - lo) * n / 4) / 100000 / 60 for n in range(5)]
        self.assertEqual(seconds, [45, 40, 35, 30, 25])
        self.assertEqual(self.cell(W.SOUL_T, row, "instant_trigger", "trigger_limit"), "(None)")
        roll = [r for r in self.ea(10) if self.cell(W.EA_T, r, "instant_trigger", "kind") == W.IT_ELAPSED]
        self.assertEqual([(self.cell(W.EA_T, r, "instant_trigger", "threshold.power1"),
                           self.cell(W.EA_T, r, "instant_trigger", "threshold.first_max")) for r in roll],
                         [(W.frames(1500), W.frames(1500))])

    def test_awakening_ladder_matches_design_examples(self):
        # 设计 §3.4 / 附录 A 的示例（觉醒 0 值, 满破值；存储值 1000 = 1%）
        def pair(row_no, slot):
            r = self.soul(row_no)[slot]
            block = self._content_block(r)
            return (self.cell(W.SOUL_T, r, block, "strength.power1"), self.cell(W.SOUL_T, r, block, "strength.first_max"))
        expect = {(1, 0): ("1600", "8000"), (1, 1): ("400", "2000"), (9, 0): ("4000", "20000"), (9, 1): ("4000", "20000"),
                  (12, 0): ("2000", "10000"), (12, 3): ("2000", "10000"), (14, 0): ("12000", "60000"),
                  (18, 0): ("4000", "20000"), (18, 1): ("20000", "100000"), (18, 2): ("800", "4000"),
                  (18, 3): ("1600", "8000"), (18, 5): ("12000", "60000"), (18, 6): ("8000", "40000"),
                  (19, 0): ("7000", "35000"), (19, 1): ("13000", "65000"), (29, 0): ("1000", "5000"),
                  (29, 1): ("200", "1000"), (29, 2): ("200", "1000"), (29, 3): ("4000", "20000"),
                  (23, 0): ("1500", "7500"), (23, 1): ("1800", "9000"), (16, 1): ("4800", "24000"),
                  (22, 0): ("6000", "30000"), (25, 1): ("12000", "60000"), (28, 1): ("8000", "40000")}
        self.assertEqual({k: pair(*k) for k in expect}, expect)
        # 说明同步改写成「+觉醒0%→满破%」
        self.assertEqual(self.weapon(1).soul[0].note, "自身攻击力 +1.6%→8%")
        self.assertEqual(self.weapon(9).soul[0].note, "火属性共鸣时：第 50 秒起全队攻击力 +4%→20%（10 秒）")
        self.assertIn("每 45→25 秒", self.weapon(10).soul[0].note)
        self.assertIn("箭头左值 = 觉醒 0", W.design_markdown(self.ws))

    def test_budget_ignores_awakening_floor(self):
        # 预算只读满破/120 级（first_max）：把本体 power1 抹回满破（改前的「恒定」形状），预算必须逐项相同
        for w in self.ws:
            flat = json.loads(json.dumps(self.soul(w.row)))
            for r in flat:
                for block in ("instant_content", "during_content", "instant_trigger", "during_trigger"):
                    for name in ("strength", "threshold"):
                        try:
                            lo, hi = (_col(W.SOUL_T, block, f"{name}.{n}") for n in ("power1", "first_max"))
                        except KeyError:
                            continue
                        r[lo] = r[hi]
            self.assertEqual(self.budget(w.row, soul=flat), self.out["budgets"][w.row], w.name)

    def test_lone_wolf_cancels_exactly_at_120(self):
        w26 = next(w for w in self.ws if w.row == 26)
        soul = self.out["flat"][W.SOUL][w26.id]
        ea = self.out["flat"][W.EA][w26.id]
        hi = lambda t, r: float(r[_col(t, "instant_content", "strength.first_max")])
        def pos_neg(kind):
            pos = sum(hi(W.SOUL_T, r) for r in soul if _kind(W.SOUL_T, r) == kind)                 + sum(hi(W.EA_T, r) for r in ea if _kind(W.EA_T, r) == kind and hi(W.EA_T, r) > 0)
            return pos, [hi(W.EA_T, r) for r in ea if _kind(W.EA_T, r) == kind and hi(W.EA_T, r) < 0]
        # 提案表「建议」0928：删去全部刃值，只留充能 +100% 与增伤乘区（按作者上限 50%）；抵消仍在 120 级正好归零
        self.assertEqual(pos_neg("35"), (100000, [-100000]))
        self.assertEqual(pos_neg("723"), (50000, [-50000]))
        self.assertFalse({_kind(W.EA_T, r) for r in ea} & {"32", "33", "34", "388", "55"})

    def test_enhancement_rows_shape(self):
        for w in self.ws:
            rows = self.out["flat"][W.EA][w.id]
            self.assertEqual([int(r[0]) for r in rows], list(range(len(rows))), w.name)      # 每行独占 slot
            for r in rows:
                learn, maxlvl = int(r[1]), int(r[2])
                self.assertIn((learn, maxlvl), {(1, 119), (120, 120), (1, 120)}, w.name)
                if learn == maxlvl:
                    self.assertEqual(r[3], r[4])
                    self.assertEqual(len(set(_strengths(W.EA_T, r))), 1 if _strengths(W.EA_T, r) else 0)
            soul = self.out["flat"][W.SOUL][w.id]
            self.assertEqual([int(r[0]) for r in soul], list(range(len(soul))), w.name)
            self.assertTrue(all(r[1] == "1" for r in soul), w.name)

    def test_growth_pairs_reach_totals(self):
        self.assertAlmostEqual(W._grow(500, 240) + W._topup(500, 240) + W.weak(240), 500)
        self.assertAlmostEqual(W._grow(1000, 50) + W._topup(1000, 50) + W.weak(50), 1000)
        w20 = next(w for w in self.ws if w.row == 20)
        rows = [r for r in self.out["flat"][W.EA][w20.id] if r[_col(W.EA_T, "instant_content", "target")] == W.T_SECOND
                and _kind(W.EA_T, r) == "32"]
        soul = self.out["flat"][W.SOUL][w20.id][0]
        total = float(soul[_col(W.SOUL_T, "instant_content", "strength.first_max")]) \
            + sum(float(r[_col(W.EA_T, "instant_content", "strength.first_max")]) for r in rows)
        self.assertEqual(total, 550000)       # 提案：120 级除队长外攻击力 +550%

    def test_enhancement_meta_and_status(self):
        for w in self.ws:
            enh = self.out["flat"][W.ENH][w.id][0]
            self.assertEqual(enh[0], "120")
            self.assertEqual(enh[4], w.icon120)
            self.assertEqual(max(self.out["nested"][W.ENH_STATUS][w.id], key=int), "120")
            self.assertEqual(self.out["nested"][W.EQUIPMENT_STATUS][w.id], W.EQUIPMENT_STATUS_ROWS)
            eq = self.out["flat"][W.EQUIPMENT][w.id][0]
            self.assertEqual((eq[2], eq[6], eq[8], eq[10], eq[11]), ("0", w.icon, "5", w.id, "5"))
            item = self.out["flat"][W.ITEM][w.id][0]
            self.assertEqual((item[1], item[3]), (w.id, w.icon))

    def test_shop_uses_five_boss_materials_only(self):
        shop = self.out["flat"][W.ENH_SHOP]
        for w in self.ws:
            keys = [f"{w.id}{s:02d}" for s in range(1, 7)]
            self.assertTrue(all(k in shop for k in keys), w.name)
            caps = [int(shop[k][0][30]) for k in keys]
            self.assertEqual(caps, [69, 70, 98, 99, 119, 120])
            for k in keys:
                r = shop[k][0]
                self.assertEqual((r[0], r[2], r[29], r[31]), ("6", w.id, w.id, "5"))
                used = {r[i] for i in (14, 16, 18, 20) if r[i] not in ("", "(None)")}
                self.assertTrue(used and used <= FIVE_BOSS_MATERIALS, (k, used))
        # 作者 0928：诅咒武器不可兑换，本体从五重商店撤下（改由武器扭蛋 990003 获取）——生成器不得再产出商店行，
        # 否则下一条诅咒补丁边会把 990099003–031 悄悄重新上架
        self.assertNotIn(W.BOSS_COIN_SHOP, self.out["flat"])
        self.assertNotIn(W.BOSS_COIN_SHOP, W.FLAT_TABLES)

    def test_descriptions_credit_the_proposer(self):
        # 作者 0928：武器介绍带上提案表里的提案人（本体说明 / 强化说明两处；五重商店本体已撤下）
        for w in self.ws:
            credit = f"提案：{w.author}"
            self.assertTrue(self.out["flat"][W.EQUIPMENT][w.id][0][7].endswith(credit), w.name)
            # 客户端补丁 R2（同队 ≥2 件诅咒装备全部失效）只能写在本体说明里：风味 + 规则 + 提案人，≤57 字
            self.assertEqual(self.out["flat"][W.EQUIPMENT][w.id][0][7], f"{w.flavor}{W.CURSE_RULE}{credit}", w.name)
            self.assertIn("同队两件以上（含魂珠）全部失效", W.CURSE_RULE)     # R2 连魂珠槽一起数，不能只写「两把」
            self.assertLessEqual(len(self.out["flat"][W.EQUIPMENT][w.id][0][7]), W.DESC_LIMITS["equipment"], w.name)
            self.assertTrue(self.out["flat"][W.ENH][w.id][0][6].endswith(credit), w.name)

    def test_server_delta_mirrors_client(self):
        srv = self.out["server"]
        ids = sorted(int(w.id) for w in self.ws)
        self.assertEqual(sorted(srv["equipment_ids.json"]), ids)
        self.assertEqual(sorted(srv["equipment_enhancement_shop.json"]), sorted(self.out["flat"][W.ENH_SHOP]))
        for key, v in srv["equipment_enhancement_shop.json"].items():
            r = self.out["flat"][W.ENH_SHOP][key][0]
            self.assertEqual(v["enhancementMaxLevel"], int(r[30]))
            self.assertEqual([c["id"] for c in v["costs"]], [int(r[i]) for i in (14, 16, 18, 20) if r[i] != "(None)"])
            self.assertEqual(v["shopCategoryId"], 6)
        # 本体不再上架五重商店：服务端片段里不得出现商店/类目映射
        self.assertNotIn("boss_coin_shop.json", srv)
        self.assertNotIn("boss_coin_shop_item_category_map.json", srv)

    def test_dsl_roundtrip_and_references(self):
        referenced = set()
        for table, logical in ((W.SOUL_T, W.SOUL), (W.EA_T, W.EA)):
            for rows in self.out["flat"][logical].values():
                for r in rows:
                    if _kind(table, r) == "629":
                        referenced.add(r[_col(table, "instant_content", "action_path")])
                        self.assertIn(r[_col(table, "instant_content", "string_id")], self.out["flat"][W.CAS])
        self.assertEqual(referenced, set(self.out["dsl"]))
        for program, tree in self.out["dsl"].items():
            self.assertTrue(program.startswith(W.DSL_DIR + "$"))
            self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree, program)
            self.assertEqual(W.dsl_signature_problems(tree), [], program)

    def test_hit_effects_load_for_colorless_owner(self):
        # 1.4.1057 实机：终焉拳套 255 属性 + Fine 命中特效 → 进战斗 C10013。正向对照：旧写法必须被拦下。
        for program, tree in self.out["dsl"].items():
            self.assertEqual(W.colorless_hit_effect_problems(tree), [], program)
        old = json.loads(json.dumps(W._full_screen_attack(5.0)).replace('"Explosion"', '"Fine"'))
        self.assertEqual(len(W.colorless_hit_effect_problems(old)), 1)

    def test_group_pullers_carry_character_groups(self):
        # 1.4.1057 实机：协力球来源（puller 9）角色组空串 → 说明显示「null角色」
        for table, logical in ((W.SOUL_T, W.SOUL), (W.EA_T, W.EA)):
            puller = _col(table, "instant_trigger", "trigger_puller")
            groups = _col(table, "instant_trigger", "trigger_puller.character_groups")
            for key, rows in self.out["flat"][logical].items():
                for r in rows:
                    if r[puller] in ("4", "5", "6", "7", "9"):
                        self.assertNotEqual(r[groups], "", (logical, key))

    def test_mul_conditions_have_unique_keys(self):
        for program, tree in self.out["dsl"].items():
            for node in _walk(tree):
                if isinstance(node, list) and node and node[0] == "Command" and node[1][0] == "CreateCondition":
                    has_mul = any(isinstance(n, dict) and "mul" in n for n in _walk(node[1][2]))
                    if has_mul:
                        self.assertTrue(node[1][7], program)

    def test_unique_references_resolve(self):
        uniques = self.out["flat"][W.UNIQUE]
        for key, rows in uniques.items():
            self.assertEqual(len(rows[0]), 15)
            self.assertTrue(rows[0][2].startswith("battle/common/unique_condition/"))
        for table, logical in ((W.SOUL_T, W.SOUL), (W.EA_T, W.EA)):
            for rows in self.out["flat"][logical].values():
                for r in rows:
                    for block in ("instant_content", "during_trigger", "precondition1", "precondition2", "precondition3"):
                        try:
                            col = _col(table, block, "unique_condition_id")
                        except KeyError:
                            continue
                        if r[col] not in ("", "(None)"):
                            self.assertIn(r[col], uniques, (block, r[col]))

    def test_capability_gate(self):
        # 默认目标 = 1047 基线：装备表 423 行（封能风笛 1 行；0928 起柴油引擎「断油」2 行、超频芯片「过载」1 行）
        # 缺 equipment-gauge-gain-rules-v1；声明补丁后放行
        default = W.build(fixture_reader())["problems"]
        self.assertEqual(sorted(p.split(" equipment_enhancement_ability#")[0] for p in default),
                         ["13 封能风笛", "22 柴油引擎", "22 柴油引擎", "25 超频芯片"], default)
        self.assertTrue(all("equipment-gauge-gain-rules-v1" in p for p in default), default)
        self.assertEqual(self.out["capabilities"],
                         ["gauge-gain-rules-v1", "equipment-gauge-gain-rules-v1", BR.DAMAGE_CAP])
        with self.assertRaises(W.CursedWeaponError):
            W.build(fixture_reader(), client_capabilities="equipment-gauge-gain-rules-v1")
        # 第三轮：赌注已下的复读、像素城之环刃的 30 倍终结技根头 133（PF3），目标客户端没有 damage-type-rules 时报出
        no_damage = W.build(fixture_reader(), client_capabilities=W.PATCHED_CLIENT_CAPABILITIES - {BR.DAMAGE_CAP})
        self.assertEqual(sorted(p.split(":")[0] for p in no_damage["problems"]),
                         [f"DSL {W.dsl_program('dance_finale')}", f"DSL {W.dsl_program('fate_echo')}"])

    def test_flute_seals_ability_gauge_gain(self):
        # 作者 0928「补」：封能风笛「无法因能力和被动得到充能」= 全队 423 规则码 8，强化 1 级起、持有者阵亡后仍生效
        w13 = next(w for w in self.ws if w.row == 13)
        rows = self.out["flat"][W.EA][w13.id]
        seal = [r for r in rows if _kind(W.EA_T, r) == "423"]
        self.assertEqual(len(seal), 1)
        r = seal[0]
        self.assertEqual((r[1], r[2]), ("1", "120"))
        self.assertEqual(r[_col(W.EA_T, "during_content", "target")], W.T_PARTY)
        self.assertEqual(r[_col(W.EA_T, "during_content", "unique_condition_id")], "8")
        self.assertEqual(r[_col(W.EA_T, "even_if_owner_dead", "even_if_owner_dead")], "true")
        uid = r[_col(W.EA_T, "during_trigger", "unique_condition_id")]
        self.assertEqual(uid, w13.uid(1))
        self.assertEqual(self.out["flat"][W.UNIQUE][uid][0][1], "封能")

    # ------------------------------------------------------------------
    # 第三轮修订（提案表「修改建议」「建议」两列，2026-09-28）
    # ------------------------------------------------------------------

    def weapon(self, row: int) -> W.Weapon:
        return next(w for w in self.ws if w.row == row)

    def ea(self, row: int) -> list[list[str]]:
        return self.out["flat"][W.EA][self.weapon(row).id]

    def soul(self, row: int) -> list[list[str]]:
        return self.out["flat"][W.SOUL][self.weapon(row).id]

    def dsl_of(self, name: str) -> list:
        return self.out["dsl"][W.dsl_program(name)]

    @staticmethod
    def cell(table: str, row: list[str], block: str, name: str) -> str:
        return row[_col(table, block, name)]

    def total(self, row: int, kind: str, target: str | None = None) -> float:
        """本体满破 + 强化（正值行）的终值合计（存储值，1000 = 1%）。"""
        out = 0.0
        for table, rows in ((W.SOUL_T, self.soul(row)), (W.EA_T, self.ea(row))):
            for r in rows:
                if _kind(table, r) != kind:
                    continue
                mode = r[W._LAYOUT[table]["blocks"]["precondition1"] - 1]
                block = "instant_content" if mode == "0" else "during_content"
                if target is not None and self.cell(table, r, block, "target") != target:
                    continue
                hi = float(self.cell(table, r, block, "strength.first_max"))
                out += hi if hi > 0 else 0
        return out

    def test_round3_renames_keep_ids_and_slugs(self):
        expect = {7: ("氪金的力量", "finality_gauntlet", "镶有星导石的拳套"),
                  10: ("赌注已下", "fate_dice", "黑色的老虎机，屏幕上停着头奖"),
                  12: ("像素城之环刃", "dancer_chakram", "金色的像素环刃")}
        for row, (name, slug, look) in expect.items():
            w = self.weapon(row)
            self.assertEqual((w.name, w.slug, w.look, w.id), (name, slug, look, str(W.ID_BASE + row)))
            self.assertEqual(self.out["flat"][W.EQUIPMENT][w.id][0][1], name)
            self.assertEqual(self.out["flat"][W.ENH][w.id][0][2], f"{name}·解咒")
            self.assertEqual(self.out["server"]["equipment_lookup.json"][w.id]["name"], name)
            self.assertEqual(w.icon, f"{W.IMAGE_DIR}/{slug}_lv0")
        self.assertNotIn("骰", self.weapon(10).flavor)
        self.assertEqual(self.weapon(12).elements, ("light", "dark"))

    def test_gluttony_devours_for_attack_only(self):
        tree = self.dsl_of("gluttony_devour")
        self.assertEqual(len(list(W._commands(tree, "RemoveMultiball"))), 1)
        acs = [ac for params in W._commands(tree, "CreateCondition") for ac in params[1]]
        self.assertEqual([ac[0] for ac in acs], ["ACAttackPoint"])            # 技能伤害半边去掉
        self.assertEqual(acs[0][2], [{"min": 1.0, "max": 1.0, "mul": 1}])     # 每个球 +100%
        self.assertEqual(acs[0][1], W.P(1800))                                 # 评分审查 0928：15 → 30 秒
        self.assertIn("30秒", self.out["flat"][W.CAS]["cursed_gluttony_devour"][0][0])
        self.assertIn("30 秒", self.weapon(1).summary_120)

    def test_feast_drum_drains_full_gauge_and_only_buffs_attack(self):
        drain = list(W._commands(self.dsl_of("feast_drain"), "SubtractSkillPoint"))
        self.assertEqual(drain, [[0, W.P(1.0)]])
        kinds = {_kind(W.EA_T, r) for r in self.ea(2)}
        self.assertEqual(kinds, {"0", "629", "56"})                            # 技伤/PF 两项去掉；0928 加 Fever 时间
        self.assertEqual(self.total(2, "0", W.T_PARTY), 1000000)
        # 评分审查 0928：Fever 时间 +100%（瞬发 56 无目标字段，成长 + 120 补足）
        fever = [r for r in self.ea(2) if _kind(W.EA_T, r) == "56"]
        self.assertEqual([(r[1], r[2]) for r in fever], [("1", "119"), ("120", "120")])
        self.assertEqual(self.total(2, "56"), 100000)

    def test_salted_fish_crown_flips_on_two_charge_stacks(self):
        """作者 0928「只有 2 层才触发消耗增伤」：每次施放 +1 层蓄力，满 2 层的那次施放消耗 2 层并获得翻身。"""
        w03 = self.weapon(3)
        flip, charge = w03.uid(1), w03.uid(2)
        uniques = self.out["flat"][W.UNIQUE]
        # 叠层上限 2：134 计层（翻身）、144/199/525 读层与消耗（蓄力）都要求可叠层（上限 1 = 整套静默失效）
        self.assertEqual(uniques[flip][0][1:5], ["咸鱼翻身", "battle/common/unique_condition/cursed_saltfish_flip", "600", "2"])
        self.assertEqual(uniques[charge][0][1:5],
                         ["咸鱼蓄力", "battle/common/unique_condition/cursed_saltfish_charge", "99999999", "2"])
        self.assertEqual(uniques[charge][0][9:12], ["false", "true", "0"])      # 不可驱散、强制、非负面
        soul = self.soul(3)
        self.assertEqual([_kind(W.SOUL_T, r) for r in soul], ["245", "461", "461", "525", "2"])
        add, grant, consume = soul[1], soul[2], soul[3]
        # 行序：+1 → 翻身 → 消耗（消耗若当场生效，前两行已按施放前层数判定完）
        for r in (add, grant, consume):
            self.assertEqual(self.cell(W.SOUL_T, r, "instant_trigger", "kind"), W.IT_SKILL)
            self.assertEqual(self.cell(W.SOUL_T, r, "instant_trigger", "trigger_puller"), W.P_SELF)
            self.assertEqual(self.cell(W.SOUL_T, r, "precondition2", "unique_condition_id"), charge)
            self.assertEqual(self.cell(W.SOUL_T, r, "precondition2", "trigger_puller"), W.P_SELF)
        self.assertEqual(self.cell(W.SOUL_T, add, "instant_content", "unique_condition_id"), charge)
        self.assertEqual(self.cell(W.SOUL_T, add, "instant_content", "strength.power1"), W.times(1))
        self.assertEqual(self.cell(W.SOUL_T, grant, "instant_content", "unique_condition_id"), flip)
        self.assertEqual(self.cell(W.SOUL_T, consume, "instant_content", "unique_condition_id"), charge)
        self.assertEqual(self.cell(W.SOUL_T, consume, "instant_content", "strength.power1"), W.times(2))
        # 两组前置互斥且覆盖：≤1 层（199）/ ≥2 层（144）
        pre = lambda r: (self.cell(W.SOUL_T, r, "precondition2", "kind"),  # noqa: E731
                         self.cell(W.SOUL_T, r, "precondition2", "threshold.power1"))
        self.assertEqual(pre(add), (W.PRE_UNIQUE_LE, W.times(1)))
        self.assertEqual(pre(grant), (W.PRE_UNIQUE_GE, W.times(2)))
        self.assertEqual(pre(consume), (W.PRE_UNIQUE_GE, W.times(2)))
        # 不再看技能槽 200%（前置 119/120 全部去掉）
        for table, rows in ((W.SOUL_T, soul), (W.EA_T, self.ea(3))):
            for r in rows:
                for block in ("precondition1", "precondition2", "precondition3"):
                    self.assertNotIn(self.cell(table, r, block, "kind"), ("119", "120"))
        # 施放前 0/1/2 层 → +1/+1/翻身并清空：每 3 次施放翻身 1 次
        stacks, flips = 0, []
        for _ in range(9):
            fired = {r_i for r_i, r in enumerate((add, grant, consume))
                     if (stacks <= 1) == (pre(r)[0] == W.PRE_UNIQUE_LE)}
            flips.append(1 in fired)
            stacks = 0 if 2 in fired else min(2, stacks + (1 if 0 in fired else 0))
        self.assertEqual(flips, [False, False, True] * 3)
        kinds = [_kind(W.EA_T, r) for r in self.ea(3)]
        self.assertNotIn("34", kinds)
        self.assertNotIn("694", kinds)
        sep = [r for r in self.ea(3) if _kind(W.EA_T, r) == "411"]
        self.assertEqual(len(sep), 1)
        self.assertEqual((sep[0][1], sep[0][2]), ("120", "120"))
        self.assertEqual(self.cell(W.EA_T, sep[0], "during_trigger", "unique_condition_id"), flip)
        self.assertEqual(self.total(3, "2", W.T_SELF), 800000)                 # 评分审查 0928：+500% → +800%
        self.assertEqual(_kind(W.SOUL_T, soul[0]), "245")

    def test_rebel_banner_shared_one_second_gate(self):
        w04 = self.weapon(4)
        self.assertEqual(self.total(4, "32", W.T_MULTIBALL), 350000)
        self.assertEqual(self.total(4, "33", W.T_MULTIBALL), 350000)
        rows = self.ea(4)
        kinds = [_kind(W.EA_T, r) for r in rows]
        self.assertEqual(kinds[-2:], ["209", "461"])                          # 上锁行排在扣血行之后
        for r in rows[-2:]:
            self.assertEqual(self.cell(W.EA_T, r, "instant_trigger", "trigger_puller"), W.P_ONE_OF_MULTIBALL)
            self.assertEqual((self.cell(W.EA_T, r, "precondition1", "kind"),
                              self.cell(W.EA_T, r, "precondition1", "unique_condition_id")), (W.PRE_UNIQUE_LE, w04.uid(1)))
        self.assertEqual(self.cell(W.EA_T, rows[-2], "instant_content", "strength.first_max"), "2000")
        # 1 秒锁；叠层上限 2（199「层数 ≤0」在上限 1 时恒真，共用 CT 形同虚设）
        self.assertEqual(self.out["flat"][W.UNIQUE][w04.uid(1)][0][3:5], ["60", "2"])

    def test_sisyphus_curse_is_party_wide_and_survives_death(self):
        curses = [r for r in self.ea(8) if r[5] == "1" and float(self.cell(W.EA_T, r, "during_content", "strength.power1")) < 0]
        self.assertEqual(sorted(_kind(W.EA_T, r) for r in curses), ["0", "2"])
        for r in curses:
            self.assertEqual(self.cell(W.EA_T, r, "during_content", "target"), W.T_PARTY)
            self.assertEqual(self.cell(W.EA_T, r, "during_content", "strength.power1"), "-100000")
            self.assertEqual(self.cell(W.EA_T, r, "during_trigger", "kind"), W.DT_HP_LOW_EX)
            self.assertEqual(self.cell(W.EA_T, r, "during_trigger", "trigger_puller"), W.P_SELF)
            self.assertEqual(self.cell(W.EA_T, r, "even_if_owner_dead", "even_if_owner_dead"), "true")
        self.assertEqual(self.total(8, "0", W.T_SELF), 500000)                 # 评分审查 0928：+350% → +500%
        self.assertEqual(self.total(8, "2", W.T_SELF), 500000)
        # 方案②：正面与诅咒的 HP 分界 50% → 40%（本体、强化、诅咒三处同一阈值）
        thresholds = {self.cell(t, r, "during_trigger", "threshold.first_max")
                      for t, rows in ((W.SOUL_T, self.soul(8)), (W.EA_T, self.ea(8))) for r in rows
                      if r[W._LAYOUT[t]["blocks"]["precondition1"] - 1] == "1"}
        self.assertEqual(thresholds, {W.pct(40)})
        self.assertEqual(sum(1 for r in self.ea(8) if _kind(W.EA_T, r) in ("209", "227")), 2)   # 满血 99.9% + 护盾保留

    def test_wager_echo_uses_pf_invocation_not_pf_hit(self):
        w10 = self.weapon(10)
        echo = W.dsl_program("fate_echo")
        rows = [r for r in self.ea(10) if _kind(W.EA_T, r) == "629"
                and self.cell(W.EA_T, r, "instant_content", "action_path") == echo]
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(self.cell(W.EA_T, r, "instant_trigger", "kind"), W.IT_PF)      # 2，不是 183
        self.assertEqual(self.cell(W.EA_T, r, "precondition1", "unique_condition_id"), w10.uid(3))
        tree = self.out["dsl"][echo]
        self.assertEqual(tree[10], W.PF3_BTA)
        self.assertEqual(W.pf_echo_trigger_problems(W.EA_T, r, self.out["dsl"]), [])
        # 负对照：换成强化弹射命中(183)必须被拦下（复读命中按 PF Lv3 计，会自我连锁）
        bad = list(r)
        bad[_col(W.EA_T, "instant_trigger", "kind")] = W.IT_PF_HIT
        self.assertEqual(len(W.pf_echo_trigger_problems(W.EA_T, bad, self.out["dsl"])), 1)
        # 同一行若树按技能伤害结算（根头 0），183 不构成自我触发
        plain = {**self.out["dsl"], echo: [*tree[:10], 0, tree[11]]}
        self.assertEqual(W.pf_echo_trigger_problems(W.EA_T, bad, plain), [])

    def test_wager_branches(self):
        w10 = self.weapon(10)
        full = self.dsl_of("fate_roll")
        acs = {ac[0]: ac for params in W._commands(full, "CreateCondition") for ac in params[1]}
        for name in ("ACDirectDamage", "ACPowerFlipDamage", "ACSkillDamage"):
            self.assertEqual(acs[name][2], W.P(5.0), name)                       # 三种增益刃值 +500%
        self.assertIn("ACSwift", acs)                                           # 冲刺冷却
        self.assertIn("ACFlying", acs)
        self.assertIn("ACBuffRejection", acs)
        self.assertEqual(acs["ACComboRestriction"][2], W.P(1))
        self.assertEqual(list(W._commands(full, "AddCombo")), [])               # 强化弹射增益不再 +40 连击
        speeds = sorted(ac[2][0]["min"] for params in W._commands(full, "CreateCondition")
                        for ac in params[1] if ac[0] == "ACSpeedup")
        self.assertEqual(speeds, [-0.35, 0.3])
        self.assertEqual([p[1] for p in W._commands(full, "SubtractSkillPoint")], [W.P(0.8)])
        self.assertEqual([p[1] for p in W._commands(full, "AddSkillPoint")], [W.P(1.0)])
        uniques = sorted(ac[1] for params in W._commands(full, "CreateCondition") for ac in params[1] if ac[0] == "ACUnique")
        self.assertEqual(uniques, [int(w10.uid(3)), int(w10.uid(4))])
        bust = [r for r in self.ea(10) if _kind(W.EA_T, r) == "411"]
        self.assertEqual(len(bust), 1)
        self.assertEqual((self.cell(W.EA_T, bust[0], "during_content", "target"),
                          self.cell(W.EA_T, bust[0], "during_content", "strength.power1"),
                          self.cell(W.EA_T, bust[0], "during_trigger", "unique_condition_id")),
                         (W.T_PARTY, "-100000", w10.uid(4)))
        opening = [r for r in self.ea(10) if r[5] == "1"
                   and self.cell(W.EA_T, r, "during_trigger", "unique_condition_id") == w10.uid(2)]
        self.assertEqual(sorted((_kind(W.EA_T, r), self.cell(W.EA_T, r, "during_content", "strength.power1"))
                                for r in opening), [("0", "20000"), ("421", "2000")])
        self.assertEqual(self.out["flat"][W.UNIQUE][w10.uid(2)][0][1:4:2], ["开局赌注", "900"])
        # 被 134/199 读层数的三个固有上限 2；「复读弹射」只被 187（按个数）读，保持 1
        caps = {self.out["flat"][W.UNIQUE][w10.uid(k)][0][1]: self.out["flat"][W.UNIQUE][w10.uid(k)][0][4] for k in (1, 2, 3, 4)}
        self.assertEqual(caps, {"赌局": "2", "开局赌注": "2", "复读弹射": "1", "血本无归": "2"})
        echo_gate = [r for r in self.ea(10) if self.cell(W.EA_T, r, "precondition1", "unique_condition_id") == w10.uid(3)]
        self.assertEqual([self.cell(W.EA_T, r, "precondition1", "kind") for r in echo_gate], [W.PRE_HAS_UNIQUE])
        # 设计文档：直击诅咒的麻痹与不受控制是 5 秒（数据 300 帧），不能写成统一 10 秒
        paralysis = [ac for params in W._commands(full, "CreateCondition") for ac in params[1] if ac[0] == "ACParalysis"]
        self.assertTrue(paralysis and all(ac[1] == W.P(300) for ac in paralysis))
        self.assertEqual([p[1] for p in W._commands(full, "SuppressBallActivity")], [W.P(300)])
        self.assertIn("麻痹与弹球不受控制为 5 秒", w10.summary_120)
        roll = next(e for e in w10.ea if e.content[0] == "629" and e.content[1]["string_id"] == "cursed_fate_roll")
        self.assertIn("麻痹与弹球不受控制 5 秒", roll.note)
        # 周期与本体温和转轮不变
        self.assertIn(W.dsl_program("fate_roll_lite"), self.out["dsl"])
        every25 = [r for r in self.ea(10) if self.cell(W.EA_T, r, "instant_trigger", "kind") == W.IT_ELAPSED]
        self.assertEqual([self.cell(W.EA_T, r, "instant_trigger", "threshold.power1") for r in every25], [W.frames(1500)])

    def test_chakram_unlock_deletes_only_its_own_lock(self):
        lock_key = "cursed_dance_lock"
        locks = [p for p in W._commands(self.dsl_of("dance_lock"), "CreateCondition") if p[1][0][0] == "ACComboRestriction"]
        self.assertEqual(len(locks), 1)
        lock = locks[0]
        self.assertEqual((lock[1][0][2], lock[4], lock[6], lock[11]), (W.P(9), False, lock_key, True))
        deletes = list(W._commands(self.dsl_of("dance_awaken"), "DeleteCondition"))
        self.assertEqual(deletes, [[-17, ["DCComboRestriction"], 99, W.DELETE_NON_CANCELABLE_ONLY, lock_key, ["Default"]]])
        self.assertEqual(W.own_lock_delete_problems(self.out["dsl"]), [])
        # 负对照：旧 dance_release 写法（cancelableKind 0 / 空键）必须被拦下
        for kind, key in ((0, lock_key), (1, ""), (1, "cursed_dance_typo")):
            mutated = json.loads(json.dumps(self.out["dsl"]))
            node = next(n for n in _walk(mutated[W.dsl_program("dance_awaken")])
                        if isinstance(n, list) and n and n[0] == "DeleteCondition")
            node[4], node[5] = kind, key                                        # [名, 主体, DC, 次数, cancelableKind, 键串, 同步]
            self.assertEqual(len(W.own_lock_delete_problems(mutated)), 1, (kind, key))
        # AddCombo 必须等删锁处理完（Wait）；否则被还在的上限 9 钳住
        waits = [n for n in _walk(self.dsl_of("dance_awaken")) if isinstance(n, list) and n and n[0] == "Wait"]
        self.assertEqual(len(waits), 1)
        self.assertEqual(len(list(W._commands(waits[0], "AddCombo"))), 1)

    def test_chakram_states_and_rows(self):
        w12 = self.weapon(12)
        u_clever, u_dance = w12.uid(1), w12.uid(2)
        uniques = self.out["flat"][W.UNIQUE]
        # c4 叠层上限 2：-666%/+500% 的 134 门禁与 ConsumeUniqueCondition 都只认可叠层状态
        self.assertEqual([uniques[u_clever][0][i] for i in (1, 3, 4, 11)], ["伶俐准备", "99999999", "2", "1"])
        self.assertEqual([uniques[u_dance][0][i] for i in (1, 3, 4, 11)], ["剑舞准备", "99999999", "2", "0"])
        consume = list(W._commands(self.dsl_of("dance_awaken"), "ConsumeUniqueCondition"))
        self.assertEqual(consume, [[-17, int(u_clever), ["Some", 1]]])
        finale = self.dsl_of("dance_finale")
        self.assertEqual(finale[10], W.PF3_BTA)
        attacks = list(W._commands(finale, "CreateNormalAttack"))
        self.assertEqual([(a[5], a[14]) for a in attacks], [(W.P(30.0), ["Explosion"])])
        rows = self.ea(12)
        for group in ("White", "Black"):                                         # 光/暗共鸣各一套
            mine = [r for r in rows if self.cell(W.EA_T, r, "precondition1", "character_groups") == group]
            sep = [r for r in mine if _kind(W.EA_T, r) == "413"]
            self.assertEqual(len(sep), 1, group)
            self.assertEqual((self.cell(W.EA_T, sep[0], "during_content", "strength.power1"),
                              self.cell(W.EA_T, sep[0], "during_trigger", "unique_condition_id"),
                              self.cell(W.EA_T, sep[0], "even_if_owner_dead", "even_if_owner_dead")),
                             ("-666000", u_clever, "true"))
            convert = [r for r in mine if _kind(W.EA_T, r) == "629"
                       and self.cell(W.EA_T, r, "instant_trigger", "kind") == W.IT_PF]
            self.assertEqual(len(convert), 2, group)
            for r in convert:
                self.assertEqual((self.cell(W.EA_T, r, "instant_trigger", "threshold.power1"),
                                  self.cell(W.EA_T, r, "instant_trigger", "trigger_limit"),
                                  self.cell(W.EA_T, r, "precondition2", "unique_condition_id")),
                                 (W.times(10), "1", u_clever))
            pf = [r for r in mine if _kind(W.EA_T, r) == "23"]
            self.assertEqual(sum(float(self.cell(W.EA_T, r, "during_content", "strength.first_max")) for r in pf), 500000)
            self.assertTrue(all(self.cell(W.EA_T, r, "during_trigger", "unique_condition_id") == u_dance for r in pf))

    def test_all_in_silence_is_forced_per_slot(self):
        rows = [r for r in self.ea(16) if _kind(W.EA_T, r) == "629"]
        self.assertEqual([self.cell(W.EA_T, r, "instant_trigger", "trigger_puller") for r in rows],
                         [W.P_LEADER, W.P_SECOND, W.P_THIRD])
        self.assertNotIn("219", [_kind(W.EA_T, r) for r in self.ea(16)])        # 普通封印行删除
        for tag, selector in (("1", 83), ("2", 84), ("3", 85)):
            tree = self.dsl_of(f"allin_silence_{tag}")
            finds = list(W._commands(tree, "FindAllSubjects"))
            self.assertEqual([f[1] for f in finds], [selector])
            (cc,) = W._commands(tree, "CreateCondition")
            self.assertEqual((cc[1], cc[4], cc[11]), ([["ACSilence", W.P(1800)]], False, True))
            self.assertIn(f"cursed_allin_silence_{tag}", self.out["flat"][W.CAS])
        self.assertEqual(self.total(16, "35", W.T_PARTY), 50000)
        self.assertEqual(self.total(16, "32", W.T_PARTY), 250000)               # 评分审查 0928：+500% → +250%
        self.assertEqual(self.total(16, "34", W.T_PARTY), 250000)
        self.assertEqual(self.total(16, "694", W.T_PARTY), 10000)

    def test_lone_star_permanent_forced_cap(self):
        w19 = self.weapon(19)
        (cc,) = W._commands(self.dsl_of("lonestar_lock"), "CreateCondition")
        self.assertEqual((cc[1], cc[4], cc[6], cc[11]),
                         ([["ACComboRestriction", W.P(9999999), W.P(15)]], False, "cursed_lonestar", True))
        lock = W.dsl_program("lonestar_lock")
        triggers = sorted(self.cell(W.EA_T, r, "instant_trigger", "kind") for r in self.ea(19)
                          if _kind(W.EA_T, r) == "629" and self.cell(W.EA_T, r, "instant_content", "action_path") == lock)
        self.assertEqual(triggers, sorted([W.IT_INITIAL, W.IT_PF, W.IT_REVIVAL]))
        pf_row = next(r for r in self.ea(19) if _kind(W.EA_T, r) == "696")
        self.assertEqual((pf_row[1], pf_row[2], self.cell(W.EA_T, pf_row, "instant_content", "strength.power1")),
                         ("120", "120", "30000"))
        self.assertNotIn("三秒", w19.flavor)
        self.assertNotIn("3 秒", w19.summary_120)

    def test_master_eater_unison_only_for_owner(self):
        unison = [r for r in self.ea(20) if _kind(W.EA_T, r) == "717"]
        self.assertEqual(len(unison), 1)
        r = unison[0]
        self.assertEqual((self.cell(W.EA_T, r, "instant_content", "target"),
                          self.cell(W.EA_T, r, "instant_content", "strength.power1"), r[1], r[2]),
                         (W.T_SELF, "50000", "120", "120"))
        self.assertEqual(self.total(20, "32", W.T_THIRD), 550000)

    def test_coral_venom_is_a_forced_unique_switch(self):
        w23 = self.weapon(23)
        uid = w23.uid(1)
        u = self.out["flat"][W.UNIQUE][uid][0]
        # c4 必须 >1：207「层数 ≤0」在上限 1 时层数恒 0 ⇒ 恒真，持有珊瑚毒也照样 -99%
        self.assertEqual([u[i] for i in (1, 3, 4, 9, 10, 11, 13)], ["珊瑚毒", "600", "2", "false", "true", "1", "true"])
        for tree in self.out["dsl"].values():                                  # 中毒 DSL 整条去掉
            self.assertFalse(any(isinstance(n, list) and n and n[0] == "ACPoison" for n in _walk(tree)))
        gated = [r for r in self.ea(23) if r[5] == "1"]
        self.assertEqual(sorted(_kind(W.EA_T, r) for r in gated), ["410", "411"])
        for r in gated:
            self.assertEqual([self.cell(W.EA_T, r, "during_trigger", k) for k in
                              ("kind", "trigger_puller", "threshold.power1", "unique_condition_id")],
                             [W.DT_UNIQUE_LOW, W.P_SELF, "0", uid])              # 阈值必须 0（≤0 层 = 没有）
            self.assertEqual(self.cell(W.EA_T, r, "during_content", "strength.power1"), "-99000")
        self.assertNotIn("693", [_kind(W.EA_T, r) for r in self.ea(23)])        # 旧「常驻 -99% + 中毒 +99%」拆写去掉
        self.assertEqual(self.total(23, "32", W.T_SELF), 75000)                  # 每次 +75%（5 次共 +375%）
        self.assertEqual(self.total(23, "34", W.T_SELF), 90000)                  # 每次 +90%（4 次共 +360%）

    def test_reverse_hourglass_curse_split(self):
        charging = sorted((self.cell(W.EA_T, r, "instant_content", "target"),
                           self.cell(W.EA_T, r, "instant_content", "strength.power1"))
                          for r in self.ea(24) if _kind(W.EA_T, r) == "35")
        self.assertEqual(charging, [(W.T_SELF, "-90000")] * 2 + [(W.T_EXCEPT, "-45000")] * 2)

    def test_triphase_transfer_grows_to_30(self):
        transfers = [r for r in self.ea(27) if r[5] == "0"
                     and self.cell(W.EA_T, r, "instant_trigger", "kind") in (W.IT_PF_HIT, W.IT_DIRECT, W.IT_SKILL_HIT)]
        gains = [r for r in transfers if float(self.cell(W.EA_T, r, "instant_content", "strength.power1")) > 0]
        losses = [r for r in transfers if float(self.cell(W.EA_T, r, "instant_content", "strength.power1")) < 0]
        self.assertEqual(len(gains), 3)
        self.assertEqual(len(losses), 3)
        for r in gains:
            self.assertEqual((r[1], r[2], self.cell(W.EA_T, r, "instant_content", "strength.power1"),
                              self.cell(W.EA_T, r, "instant_content", "strength.first_max")), ("1", "120", "20000", "30000"))
            self.assertEqual(self.cell(W.EA_T, r, "instant_trigger", "cooltime"), "60")
        for r in transfers:
            self.assertEqual(self.cell(W.EA_T, r, "instant_trigger", "trigger_limit"), "2")    # 0928：20 → 6 → 2（方案 A）
        # 方案 A：每项补 +140% 底数（含本体满破 14%）
        for kind, target in (("33", W.T_SELF), ("34", W.T_SELF), ("55", None)):
            base = [r for r in self.ea(27) if _kind(W.EA_T, r) == kind and (r[1], r[2]) in {("1", "119"), ("120", "120")}]
            self.assertEqual(len(base), 2, kind)
            got = sum(float(self.cell(W.EA_T, r, "instant_content", "strength.first_max")) for r in base)
            soul = sum(float(self.cell(W.SOUL_T, r, "instant_content", "strength.first_max"))
                       for r in self.soul(27) if _kind(W.SOUL_T, r) == kind)
            self.assertEqual(got + soul, 140000, kind)
        for r in losses:
            self.assertEqual((r[1], r[2], self.cell(W.EA_T, r, "instant_content", "strength.first_max")), ("1", "120", "-20000"))

    def test_flesh_for_bone_round3(self):
        # 评分审查 0928：补回提案人第一轮写过的全队直击，取 40%（终值 +400%）
        self.assertEqual(self.total(28, "33", W.T_PARTY), 400000)
        self.assertEqual(self.total(28, "717", W.T_PARTY), 100000)
        self.assertEqual(self.total(28, "723", W.T_PARTY), 10000)
        self.assertEqual(self.total(28, "693", W.T_PARTY), 10000)
        cursed = [r for r in self.ea(28) if _kind(W.EA_T, r) in ("209", "226", "461")]
        self.assertEqual([_kind(W.EA_T, r) for r in cursed], ["209", "226", "461"] * 3)   # 上锁行在每组最后
        self.assertEqual({self.cell(W.EA_T, r, "instant_content", "strength.power1") for r in cursed},
                         {"8000", W.times(10), W.times(1)})
        uid = self.weapon(28).uid(1)
        self.assertEqual(self.out["flat"][W.UNIQUE][uid][0][3:5], ["120", "2"])     # 2 秒锁，上限 2 才能被 199 读到
        for r in cursed:
            self.assertEqual((self.cell(W.EA_T, r, "precondition2", "kind"),
                              self.cell(W.EA_T, r, "precondition2", "unique_condition_id")), (W.PRE_UNIQUE_LE, uid))

    def test_accumulation_cap_gate(self):
        # 客户端 Condition.get_accumulatable() = maxAccumulation > 1：按层数读/消耗的固有上限 1 时静默失效
        uniques = self.out["flat"][W.UNIQUE]
        rows = [(f"{w.row:02d} {table}#{i}", table, r) for w in self.ws
                for table, logical in ((W.SOUL_T, W.SOUL), (W.EA_T, W.EA))
                for i, r in enumerate(self.out["flat"][logical][w.id])]
        flagged = {uid for uid, _ in W.unique_accumulation_problems(rows, self.out["dsl"], uniques)}
        # 全部修好（09 蛰龙之心 / 13 封能风笛在第三轮一并改为上限 2），不再有待决条目
        self.assertEqual(flagged, set())
        self.assertEqual(W.ACCUMULATION_CAP_PENDING, {})
        self.assertEqual(self.out["accumulation_pending"], [])
        # 负对照：把本轮修过的固有改回上限 1，每一种读法都必须被拦下
        cases = {self.weapon(3).uid(1): {"持续触发 134"},                             # 咸鱼翻身
                 self.weapon(3).uid(2): {"前置 144", "前置 199", "瞬发 525"},       # 咸鱼蓄力
                 self.weapon(4).uid(1): {"前置 199"},                                   # 叛旗
                 self.weapon(10).uid(2): {"持续触发 134"},                              # 开局赌注
                 self.weapon(12).uid(1): {"持续触发 134", "ConsumeUniqueCondition"},    # 伶俐准备（含 DSL 消耗）
                 self.weapon(23).uid(1): {"持续触发 207"},                              # 珊瑚毒
                 self.weapon(28).uid(1): {"前置 199"},                                  # 骨断
                 self.weapon(9).uid(1): {"持续触发 134"},                               # 蛰伏
                 self.weapon(9).uid(4): {"持续触发 134"},                               # 枯竭
                 self.weapon(13).uid(1): {"持续触发 134"}}                              # 封能
        for uid, kinds in cases.items():
            mutated = {**uniques, uid: [[*uniques[uid][0][:4], "1", *uniques[uid][0][5:]]]}
            probs = [p for u, p in W.unique_accumulation_problems(rows, self.out["dsl"], mutated) if u == uid]
            self.assertTrue(probs, uid)
            for kind in kinds:
                self.assertTrue(any(kind in p for p in probs), (uid, kind, probs))
            # 写 (None) 同样是上限 1（记忆卡 wf-unique-cap-none-trap）
            none = {**uniques, uid: [[*uniques[uid][0][:4], "(None)", *uniques[uid][0][5:]]]}
            self.assertTrue(any(u == uid for u, _ in W.unique_accumulation_problems(rows, self.out["dsl"], none)), uid)
        # 只按个数读（前置 187）的固有不受上限约束：复读弹射 / 终焉保持 1 不报
        for uid in (self.weapon(10).uid(3), self.weapon(7).uid(1)):
            self.assertEqual(uniques[uid][0][4], "1")
            self.assertNotIn(uid, flagged)
        # 瞬发前置消耗（三重咒钥 2 层咒钥）同样在门禁里：改成上限 1 必须报
        key = self.weapon(14).uid(1)
        mutated = {**uniques, key: [[*uniques[key][0][:4], "1", *uniques[key][0][5:]]]}
        self.assertTrue(any(u == key and "瞬发前置 2" in p
                            for u, p in W.unique_accumulation_problems(rows, self.out["dsl"], mutated)))

    def test_accumulation_pending_must_be_pruned(self):
        # 登记在 ACCUMULATION_CAP_PENDING 里但已经不触发门禁的条目，build 报出来要求删掉（防止白名单掩盖新问题）
        from unittest import mock
        fixed = self.weapon(23).uid(1)
        with mock.patch.dict(W.ACCUMULATION_CAP_PENDING, {fixed: "23 珊瑚毒爪「珊瑚毒」"}):
            probs = W.build(fixture_reader(), client_capabilities=W.PATCHED_CLIENT_CAPABILITIES)["problems"]
        self.assertEqual(len(probs), 1)
        self.assertIn(f"ACCUMULATION_CAP_PENDING 残留：{fixed}", probs[0])
        # 反过来：把某个固有改回上限 1（不登记待决），死行进 problems
        uid = self.weapon(13).uid(1)
        original = W.unique_row
        with mock.patch.object(W, "unique_row", lambda sid, name, icon, duration, cap, **kw:
                               original(sid, name, icon, duration, "1" if name == "封能" else cap, **kw)):
            probs = W.build(fixture_reader(), client_capabilities=W.PATCHED_CLIENT_CAPABILITIES)["problems"]
        self.assertEqual({p.split("按层数读固有 ")[1][:8] for p in probs}, {uid})

    # ------------------------------------------------------------------
    # 作者 0928「要求全部诅咒武器带的负面都是强制赋予，角色免疫也会生效」（强制赋予方案 §2 / §7）
    # ------------------------------------------------------------------

    def test_every_curse_condition_is_forced(self):
        # DSL 里所有负面 CreateCondition 一律 forceApply（params[11]），命中率固定 1（强制不跳过命中抽签本身）；
        # ACUnique 由 unique_condition c10 决定（ActionEvaluator.as:3367）：坏方向固有必须 c10=true
        forced = 0
        for program, tree in self.out["dsl"].items():
            for cc in W._commands(tree, "CreateCondition"):
                acs = [ac for ac in cc[1] if ac[0] != "ACUnique"]
                if acs and _dsl_is_curse(acs):
                    self.assertIs(cc[11], True, program)
                    self.assertEqual(cc[2], W.P(1), program)
                    self.assertIs(cc[4], program.endswith("watch_curse"), program)   # 只有停摆怀表的随机减益保持可驱散
                    forced += 1
        self.assertGreaterEqual(forced, 30)
        for uid, (row, *_rest) in self.out["flat"][W.UNIQUE].items():
            if row[11] == "1":
                self.assertEqual((row[9], row[10]), ("false", "true"), uid)             # 不可驱散 + 强制

    def test_curse_rows_avoid_unforceable_ability_states(self):
        # 能力表计时状态没有强制付与列（MemberImpl.as:8526）：诅咒不得再用瞬发 19/219/688 或负值计时状态
        for w in self.ws:
            for index, row in enumerate(self.out["flat"][W.EA][w.id]):
                if row[5] != "0":
                    continue
                kind = _kind(W.EA_T, row)
                self.assertNotIn(kind, {"19", "219", "688"}, f"{w.name} E{index}")
                if kind in {"0", "1", "28", "228", "470", "486", "701"}:
                    self.assertTrue(all(v >= 0 for v in _strengths(W.EA_T, row)), f"{w.name} E{index} {kind}")

    def _forced(self, name: str) -> list[list]:
        return list(W._commands(self.dsl_of(name), "CreateCondition"))

    def _invocations(self, row: int, name: str) -> list[list[str]]:
        program = W.dsl_program(name)
        return [r for r in self.ea(row) if _kind(W.EA_T, r) == "629"
                and self.cell(W.EA_T, r, "instant_content", "action_path") == program]

    def test_watch_curse_is_forced(self):
        ccs = self._forced("watch_curse")
        self.assertEqual(len(ccs), 5)
        self.assertTrue(all(cc[11] is True and cc[6] == "" for cc in ccs))    # 同种减益再抽中只刷新（空键）
        self.assertIn("强制付与", self.out["flat"][W.CAS]["cursed_watch_curse"][0][0])

    def test_finality_doom_is_one_forced_dsl(self):
        # 氪金的力量：每属性原 10 行（19/219/0/1/486 × 8 秒 + 复活）→ 2 行 629 调同一棵强制 DSL
        ccs = self._forced("finality_doom")
        self.assertEqual([(cc[1][0][0], cc[6]) for cc in ccs],
                         [("ACParalysis", "cursed_finality_para"), ("ACSilence", "cursed_finality_seal"),
                          ("ACAttackPoint", "cursed_finality_atk"), ("ACSkillDamage", "cursed_finality_skill"),
                          ("ACAbilityDamage", "cursed_finality_ability")])
        for cc in ccs:
            self.assertEqual((cc[1][0][1], cc[4], cc[11]), (W.P(W.DSL_FOREVER), False, True))
        self.assertEqual(ccs[0][1][0][2], True)                                  # 引擎取反 ⇒ Paralysis(false)，同能力表 19
        self.assertEqual({cc[1][0][2][0]["max"] for cc in ccs[2:]}, {-8.86})
        self.assertEqual([f[1] for f in W._commands(self.dsl_of("finality_doom"), "FindAllSubjects")], [82])
        rows = self._invocations(7, "finality_doom")
        self.assertEqual(sorted(self.cell(W.EA_T, r, "instant_trigger", "kind") for r in rows),
                         sorted([W.IT_ELAPSED, W.IT_REVIVAL] * 2))                # 火/水各 8 秒一次 + 复活重挂
        uid = self.weapon(7).uid(1)
        for r in rows:
            if self.cell(W.EA_T, r, "instant_trigger", "kind") == W.IT_REVIVAL:
                self.assertEqual(self.cell(W.EA_T, r, "precondition2", "unique_condition_id"), uid)   # 「终焉」后才重挂
        self.assertEqual(self.total(7, "32", W.T_PARTY), 400000)                 # 火/水两套各 +200%（按属性分支计刃）

    def test_hokuto_split_is_forced_and_reapplied(self):
        (cc,) = self._forced("hokuto_hundred")
        self.assertEqual((cc[1][0][0], cc[4], cc[6], cc[11]), ("ACAdditionalDirectAttack", False, "cursed_hokuto", True))
        triggers = sorted(self.cell(W.EA_T, r, "instant_trigger", "kind") for r in self._invocations(11, "hokuto_hundred"))
        self.assertEqual(triggers, sorted([W.IT_INITIAL, W.IT_REVIVAL]))        # 阵亡入棺清掉后复活重挂
        buffs = [r for r in self.ea(11) if _kind(W.EA_T, r) in ("0", "1")]
        self.assertEqual({self.cell(W.EA_T, r, "instant_content", "strength.first_max") for r in buffs}, {W.pct(150)})

    def test_gasoline_slow_is_forced(self):
        (cc,) = self._forced("gasoline_slow")
        self.assertEqual((cc[1][0][0], cc[1][0][1], cc[1][0][2], cc[4], cc[6], cc[11]),
                         ("ACSpeedup", W.P(W.DSL_FOREVER), W.P(-0.5), False, "cursed_gasoline_slow", True))
        self.assertNotIn("228", [_kind(W.EA_T, r) for r in self.ea(15)])
        triggers = sorted(self.cell(W.EA_T, r, "instant_trigger", "kind") for r in self._invocations(15, "gasoline_slow"))
        self.assertEqual(triggers, sorted([W.IT_INITIAL, W.IT_REVIVAL]))
        self.assertEqual(self.total(15, "32", W.T_LEADER), 100000)               # 评分审查 0928：+250% → +150% → 兜底 +100%

    def test_force_apply_gaps_are_recorded(self):
        # 强制赋予方案 §5.3：209 扣血按友伤结算，强制不了 —— 每把带 209 的武器都要在偏差里写明
        ff = [w.row for w in self.ws
              if any(_kind(t, r) == "209" for t, rows in ((W.SOUL_T, self.soul(w.row)), (W.EA_T, self.ea(w.row)))
                     for r in rows)]
        self.assertEqual(ff, [4, 8, 18, 28, 29])
        for row in ff:
            self.assertTrue(any(d.startswith(W.FRIENDLY_FIRE_NOTE) for d in self.weapon(row).deviations), row)
        # §5.1：坏方向计时固有「断油」「过载」的持续帧会被「弱体时间缩短」缩短
        for row, name, seconds in ((22, "断油", 10), (25, "过载", 20)):
            self.assertIn(W.timed_curse_unique_note(name, seconds), self.weapon(row).deviations)

    def test_persona_thunder_uses_cooldown_not_limit(self):
        # 评分审查 0928（按表改，表第 18 行）：雷模式队长 HP<20% 触发「限 2 次」→ 冷却 15 秒；本体 4 行 + 强化 8 行共用
        rows = [(W.SOUL_T, r) for r in self.soul(18)] + [(W.EA_T, r) for r in self.ea(18)]
        leader = [(t, r) for t, r in rows if self.cell(t, r, "instant_trigger", "kind") == W.IT_HP_LOW
                  and self.cell(t, r, "instant_trigger", "trigger_puller") == W.P_LEADER]
        self.assertEqual(len(leader), 12)
        for t, r in leader:
            self.assertEqual((self.cell(t, r, "instant_trigger", "cooltime"),
                              self.cell(t, r, "instant_trigger", "trigger_limit")), ("900", "(None)"))
        self.assertEqual(self.out["budgets"][18]["unbounded"], [])

    def test_capacitor_paralysis_is_forced_per_slot(self):
        rows = [r for r in self.ea(17) if _kind(W.EA_T, r) == "629"]
        self.assertEqual([(self.cell(W.EA_T, r, "instant_trigger", "trigger_puller"),
                           self.cell(W.EA_T, r, "instant_trigger", "threshold.first_max")) for r in rows],
                         [(W.P_LEADER, W.times(2)), (W.P_SECOND, W.times(2)), (W.P_THIRD, W.times(2))])
        for tag, selector in (("1", 83), ("2", 84), ("3", 85)):
            tree = self.dsl_of(f"capacitor_paralysis_{tag}")
            self.assertEqual([f[1] for f in W._commands(tree, "FindAllSubjects")], [selector])
            (cc,) = W._commands(tree, "CreateCondition")
            self.assertEqual((cc[1], cc[4], cc[11]), ([["ACParalysis", W.P(600), True]], False, True))
        self.assertEqual(self.total(17, "34", W.T_PARTY), 600000)

    def test_silent_bell_and_mask_seals_are_forced(self):
        (cc,) = self._forced("silentbell_seal")
        self.assertEqual((cc[1], cc[4], cc[11]), ([["ACSilence", W.P(W.DSL_FOREVER)]], False, True))
        self.assertEqual([f[1] for f in W._commands(self.dsl_of("silentbell_seal"), "FindAllSubjects")], [82])
        self.assertEqual(len(self._invocations(21, "silentbell_seal")), 4)       # 风/暗 × 开局 + 复活
        self.assertNotIn("219", [_kind(W.EA_T, r) for r in self.ea(21)])
        # 面具：封印与速度固定（作者 0928 定为负面）都强制，开局 + 复活各一行
        (seal,) = self._forced("mask_silence")
        (speed,) = self._forced("mask_speed")
        self.assertEqual((seal[0], seal[1], seal[11]), (-17, [["ACSilence", W.P(W.DSL_FOREVER)]], True))
        self.assertEqual((speed[0], speed[1], speed[4], speed[11]),
                         (-17, [["ACFixedSpeed", W.P(W.DSL_FOREVER), W.P(2.0), W.P(0), W.P(1)]], False, True))
        for name in ("mask_silence", "mask_speed"):
            triggers = sorted(self.cell(W.EA_T, r, "instant_trigger", "kind") for r in self._invocations(29, name))
            self.assertEqual(triggers, sorted([W.IT_INITIAL, W.IT_REVIVAL]), name)
        self.assertFalse({"219", "688"} & {_kind(W.EA_T, r) for r in self.ea(29)})

    # ------------------------------------------------------------------
    # 作者 0928「无法获得能量」= 固有状态计时 + 423 回槽拦截规则码 78（超频芯片 / 柴油引擎）
    # ------------------------------------------------------------------

    def test_energy_lock_code(self):
        self.assertEqual(W.GAUGE_LOCK, BR.gauge_mask(["movement", "skill", "ability", "other_action"]))
        self.assertEqual(W.GAUGE_LOCK, 2 + 4 + 8 + 64)                           # 只放行开局槽（1）
        self.assertEqual(W.GAUGE_MASK, 8)                                        # 封能风笛 / PARADOX 的只拦能力回槽不变

    def _lock_rows(self, row: int) -> list[list[str]]:
        return [r for r in self.ea(row) if _kind(W.EA_T, r) == "423"]

    def test_overclock_overload_blocks_all_gauge_gain(self):
        w25 = self.weapon(25)
        uid = w25.uid(1)
        u = self.out["flat"][W.UNIQUE][uid][0]
        # 134 按层数读 ⇒ c4 ≥ 2；不可驱散、c10 强制、坏方向、专属图标
        self.assertEqual([u[i] for i in (1, 2, 3, 4, 9, 10, 11)],
                         ["过载", "battle/common/unique_condition/cursed_chip_overload", "1200", "2", "false", "true", "1"])
        grant = [r for r in self.ea(25) if _kind(W.EA_T, r) == "461"]
        self.assertEqual(len(grant), 1)
        self.assertEqual((self.cell(W.EA_T, grant[0], "instant_trigger", "kind"),
                          self.cell(W.EA_T, grant[0], "instant_trigger", "trigger_puller"),
                          self.cell(W.EA_T, grant[0], "instant_content", "target"),
                          self.cell(W.EA_T, grant[0], "instant_content", "unique_condition_id"),
                          grant[0][1], grant[0][2]), (W.IT_SKILL, W.P_SELF, W.T_SELF, uid, "1", "120"))
        (lock,) = self._lock_rows(25)
        self.assertEqual((self.cell(W.EA_T, lock, "during_content", "target"),
                          self.cell(W.EA_T, lock, "during_content", "unique_condition_id"),
                          self.cell(W.EA_T, lock, "during_trigger", "kind"),
                          self.cell(W.EA_T, lock, "during_trigger", "unique_condition_id"), lock[1], lock[2]),
                         (W.T_SELF, str(W.GAUGE_LOCK), W.DT_UNIQUE, uid, "1", "120"))
        self.assertNotIn("701", [_kind(W.EA_T, r) for r in self.ea(25)])       # 旧「充能速度 -100%」删掉
        self.assertEqual(self.total(25, "34", W.T_SELF), 600000)                 # 评分审查 0928：补技能伤害刃 600
        self.assertEqual(self.total(25, "694", W.T_SELF), 50000)

    def test_diesel_cutoff_locks_second_and_third(self):
        w22 = self.weapon(22)
        uid = w22.uid(1)
        u = self.out["flat"][W.UNIQUE][uid][0]
        self.assertEqual([u[i] for i in (1, 2, 3, 4, 9, 10, 11)],
                         ["断油", "battle/common/unique_condition/cursed_diesel_cutoff", "600", "2", "false", "true", "1"])
        grant = [r for r in self.ea(22) if _kind(W.EA_T, r) == "461"]
        self.assertEqual([(self.cell(W.EA_T, r, "instant_trigger", "trigger_puller"),
                           self.cell(W.EA_T, r, "instant_content", "unique_condition_id")) for r in grant],
                         [(W.P_LEADER, uid)])
        locks = self._lock_rows(22)
        self.assertEqual(sorted(self.cell(W.EA_T, r, "during_content", "target") for r in locks), [W.T_SECOND, W.T_THIRD])
        for r in locks:
            self.assertEqual((self.cell(W.EA_T, r, "during_content", "unique_condition_id"),
                              self.cell(W.EA_T, r, "during_trigger", "kind"),
                              self.cell(W.EA_T, r, "during_trigger", "unique_condition_id"),
                              self.cell(W.EA_T, r, "even_if_owner_dead", "even_if_owner_dead"), r[1], r[2]),
                             (str(W.GAUGE_LOCK), W.DT_UNIQUE, uid, "true", "1", "120"))
        # 原诅咒保留：队长施技时 2/3 号位攻击 -200%、技能槽 -50%
        self.assertEqual(sorted(self.cell(W.EA_T, r, "instant_content", "strength.first_max") for r in self.ea(22)
                                if _kind(W.EA_T, r) == "32" and r[1] == "1" and r[2] == "120"), ["-200000", "-200000"])
        self.assertEqual(len(self._invocations(22, "diesel_drain")), 1)
        self.assertEqual(self.total(22, "32", W.T_LEADER), 300000)               # 评分审查 0928：+500% → +300%
        self.assertEqual(self.total(22, "34", W.T_LEADER), 300000)

    def test_new_uniques_are_readable_by_layer_gates(self):
        # 0928 新增的两个计时固有被 134 按层数读：c4 必须 >1，改回 1 必须被门禁拦下
        uniques = self.out["flat"][W.UNIQUE]
        rows = [(f"{w.row:02d} {table}#{i}", table, r) for w in self.ws
                for table, logical in ((W.SOUL_T, W.SOUL), (W.EA_T, W.EA))
                for i, r in enumerate(self.out["flat"][logical][w.id])]
        for uid in (self.weapon(22).uid(1), self.weapon(25).uid(1)):
            self.assertEqual(uniques[uid][0][4], "2", uid)
            mutated = {**uniques, uid: [[*uniques[uid][0][:4], "1", *uniques[uid][0][5:]]]}
            self.assertTrue(any(u == uid and "持续触发 134" in p
                                for u, p in W.unique_accumulation_problems(rows, self.out["dsl"], mutated)), uid)

    # ------------------------------------------------------------------
    # 评分审查 0928（作者「按表改吧，拍板项也按方案做」）的其余机制改动
    # ------------------------------------------------------------------

    def test_dragon_wrath_lasts_twenty_seconds(self):
        w09 = self.weapon(9)
        uniques = self.out["flat"][W.UNIQUE]
        self.assertEqual(uniques[w09.uid(3)][0][1:4:2], ["龙怒", "1200"])
        self.assertEqual(uniques[w09.uid(2)][0][1:4:2], ["苏醒", "600"])
        at = {}
        for r in self.ea(9):
            if _kind(W.EA_T, r) == "461":
                at.setdefault(self.cell(W.EA_T, r, "instant_content", "unique_condition_id"), set()).add(
                    self.cell(W.EA_T, r, "instant_trigger", "threshold.first_max"))
        self.assertEqual(at[w09.uid(3)], {W.frames(6600)})                       # 第 110 秒起 20 秒
        self.assertEqual(at[w09.uid(4)], {W.frames(7860)})                       # 「枯竭」顺延到第 131 秒

    def test_wager_weights_and_buff_duration(self):
        full = self.dsl_of("fate_roll")
        # 根块的唯一一条命令就是六支转盘：[ProbabilityWeight(w), 分支体] × 6
        (outer,) = full[11][1]
        weights = [branch[1][0][1][1] for branch in outer[1][1][1]]
        self.assertEqual(weights, [3, 3, 3, 1, 1, 1])                           # 每种增益 1/4、每种诅咒 1/12
        frames = {ac[0]: ac[1] for params in W._commands(full, "CreateCondition") for ac in params[1] if ac[0] != "ACUnique"}
        for name in ("ACFlying", "ACSwift", "ACDirectDamage", "ACPiercing", "ACPowerFlipDamage", "ACSkillDamage",
                     "ACSkillGaugeCharging"):
            self.assertEqual(frames[name], W.P(1200), name)                      # 增益 20 秒
        for name in ("ACComboRestriction", "ACBuffRejection"):
            self.assertEqual(frames[name], W.P(600), name)                       # 诅咒 10 秒不动
        self.assertEqual(self.out["flat"][W.UNIQUE][self.weapon(10).uid(3)][0][1:4:2], ["复读弹射", "1200"])

    def test_triple_key_attack_goes_to_each_caster(self):
        for table, rows in ((W.SOUL_T, self.soul(14)), (W.EA_T, self.ea(14))):
            buffs = [r for r in rows if _kind(table, r) == "0"]
            self.assertEqual(len(buffs), 1 if table == W.SOUL_T else 2, table)
            for r in buffs:
                self.assertEqual([self.cell(table, r, "instant_trigger", "kind"),
                                  self.cell(table, r, "instant_trigger", "trigger_puller"),
                                  self.cell(table, r, "instant_content", "target"),
                                  self.cell(table, r, "instant_content", "by_each_trigger_puller"),
                                  self.cell(table, r, "instant_content", "frame.first_max")],
                                 [W.IT_SKILL, W.P_ONE_OF_PARTY, W.T_TRIGGER, "true", W.frames(2400)], table)
        self.assertEqual(self.total(14, "0", W.T_TRIGGER), 1000000)
        # 咒钥回充仍只给装备者
        refill = [r for r in self.ea(14) if _kind(W.EA_T, r) == "211"]
        self.assertEqual([self.cell(W.EA_T, r, "instant_trigger", "trigger_puller") for r in refill], [W.P_SELF])

    # ------------------------------------------------------------------
    # 数值预算（作者 0928：基线死亡使者 500% 刃；刃合计 ≤1000%、乘区 ≤50%；不要脸的提案压到常规深渊水准）
    # ------------------------------------------------------------------

    #: 120 级 + 满破时单个角色能同时拿到的最大值（刃 %, 乘区 %），与人工对账表一致
    #: 评分审查 0928（作者「按表改」）：3 500→800、7 900→600、8 700→1000、11 350→450、15 1000→850（表内兜底）、16 1000→500、
    #: 22 1000→600、23 490→735、25 0→600、27 582→600、28 0→400、29 0→500；其余不变
    EXPECTED_BUDGETS = {
        1: (920, 0), 2: (1000, 0), 3: (800, 30), 4: (700, 0), 5: (0, 0), 6: (1000, 0), 7: (600, 0), 8: (1000, 0),
        9: (1000, 50), 10: (500, 2), 11: (450, 0), 12: (510, 0), 13: (1000, 0), 14: (1000, 0), 15: (850, 15),
        16: (500, 10), 17: (600, 0), 18: (1000, 20), 19: (1000, 30), 20: (550, 0), 21: (500, 50), 22: (600, 20),
        23: (735, 0), 24: (1000, 0), 25: (600, 50), 26: (0, 50), 27: (600, 0), 28: (400, 20), 29: (500, 50)}

    def budget(self, row: int, *, soul=None, ea=None, dsl=None) -> dict:
        return W.weapon_budget(self.soul(row) if soul is None else soul, self.ea(row) if ea is None else ea,
                               self.out["flat"][W.UNIQUE], self.out["dsl"] if dsl is None else dsl)

    def test_every_weapon_within_budget(self):
        self.assertEqual(sorted(self.out["budgets"]), list(range(1, 30)))
        got = {row: (b["blades"], b["multipliers"]) for row, b in self.out["budgets"].items()}
        self.assertEqual(got, self.EXPECTED_BUDGETS)
        for row, b in self.out["budgets"].items():
            self.assertLessEqual(b["blades"], W.BLADE_CAP, row)
            self.assertLessEqual(b["multipliers"], W.MULTIPLIER_CAP, row)
            self.assertEqual(b["unbounded"], [], row)
        self.assertEqual((W.BLADE_CAP, W.MULTIPLIER_CAP), (1000, 50))

    def test_regular_abyss_rows_for_buyaolian(self):
        # 作者 0928「不要脸写的数值都太高了，降低到其他深渊武器的常规水准」
        rows = sorted(w.row for w in self.ws if w.author in W.REGULAR_ABYSS_AUTHORS)
        self.assertEqual(rows, [25, 26, 27, 29])
        for row in rows:
            b = self.out["budgets"][row]
            self.assertLessEqual(b["blades"], W.REGULAR_ABYSS_BLADE_CAP, row)
            self.assertLessEqual(b["multipliers"], W.MULTIPLIER_CAP, row)
        self.assertEqual(W.budget_caps("不要脸"), (600, 50))
        self.assertEqual(W.budget_caps("脆脆鲨"), (1000, 50))
        # 诅咒与机制保留：孤狼的抵消、超频的过载（0928 起 = 无法获得能量 423）、三相的转出、面具的封印（0928 起 629 强制）
        self.assertEqual(sorted(_kind(W.EA_T, r) for r in self.ea(26) if min(_strengths(W.EA_T, r) or [0]) < 0),
                         sorted(["35", "723"]))
        self.assertIn("423", [_kind(W.EA_T, r) for r in self.ea(25)])
        self.assertIn(W.dsl_program("mask_silence"), [self.cell(W.EA_T, r, "instant_content", "action_path")
                                                      for r in self.ea(29) if _kind(W.EA_T, r) == "629"])
        self.assertEqual(sum(1 for r in self.ea(27) if min(_strengths(W.EA_T, r) or [0]) < 0), 3)

    def test_budget_counts_exclusive_windows_and_single_roulette_branch(self):
        # 蛰龙之心「苏醒」50–59 秒（+本体第 50 秒的弱加成）与「龙怒」110–119 秒不重叠：取较大的龙怒窗口 +1000%，不是两窗相加
        b9 = self.out["budgets"][9]
        self.assertEqual((b9["blades"], b9["multipliers"]), (1000, 50))
        # 赌注已下：开局赌注（0–15 秒）与第一次转盘（25 秒）不重叠；转盘每次只中一支（+500%）
        self.assertEqual(self.out["budgets"][10]["blades"], 500)
        # 负对照：把「龙怒」挪到第 50 秒与「苏醒」同时，两窗必须相加（窗口不是漏洞）
        w09 = self.weapon(9)
        ea = json.loads(json.dumps(self.ea(9)))
        moved = 0
        for r in ea:
            if (_kind(W.EA_T, r) == "461" and self.cell(W.EA_T, r, "instant_content", "unique_condition_id") == w09.uid(3)):
                for name in ("threshold.power1", "threshold.first_max"):
                    r[_col(W.EA_T, "instant_trigger", name)] = W.frames(3000)
                moved += 1
        self.assertEqual(moved, 2)                                               # 火/雷共鸣各一行
        b = self.budget(9, ea=ea)
        self.assertEqual((b["blades"], b["multipliers"]), (20 + 500 + 1000, 30 + 50))   # 本体第 50 秒弱加成 + 苏醒 + 龙怒
        self.assertEqual(len(W.budget_problems("09", w09.author, b)), 2)
        # 门禁窗口只约束触发时刻，触发后的计时效果不随门禁结束截断（保守）
        self.assertEqual(W._gated(((600, 1200),), ((0, 700),), 600), ((600, 1200),))
        self.assertEqual(W._gated(((800, 1400),), ((0, 700),), 600), ())
        self.assertEqual(W._gated(None, ((0, 100),), 600), ((0, 700),))
        self.assertIsNone(W._gated(None, None, 600))

    def test_budget_guard_negative_controls(self):
        top = lambda r: _col(W.EA_T, "during_content" if r[5] == "1" else "instant_content", "strength.first_max")
        # 1) 刃值抬 1%：狂宴战鼓 1000% → 1001% 必须报
        ea = json.loads(json.dumps(self.ea(2)))
        row = next(r for r in ea if _kind(W.EA_T, r) == "0" and r[1] == "120")
        row[top(row)] = str(int(row[top(row)]) + 1000)
        b = self.budget(2, ea=ea)
        self.assertEqual(b["blades"], 1001)
        probs = W.budget_problems("02", self.weapon(2).author, b)
        self.assertEqual(len(probs), 1)
        self.assertIn("刃合计 1001% 超过上限 1000%", probs[0])
        # 2) 加一行乘区：失声之钟已在 50%，再加 723 +1% 必须报；停摆怀表 0% 加 51% 也必须报
        for row_no, extra in ((21, 1), (5, 51)):
            ea = json.loads(json.dumps(self.ea(row_no)))
            ea.append(W.build_row(W.EA_T, len(ea), W.Eff("0", W.stat("723", W.T_SELF, extra), **W.FINAL)))
            b = self.budget(row_no, ea=ea)
            self.assertEqual(b["multipliers"], self.EXPECTED_BUDGETS[row_no][1] + extra)
            self.assertTrue(any("乘区合计" in p for p in W.budget_problems(str(row_no), "x", b)), row_no)
        # 3) DSL 数值：饕餮吞噬上限 9 → 10 个球（每球 +100%）必须报
        dsl = json.loads(json.dumps(self.out["dsl"]))
        node = next(n for n in _walk(dsl[W.dsl_program("gluttony_devour")])
                    if isinstance(n, list) and n and n[0] == "MultiballNumberVariable")
        node[-1] = 10
        b = self.budget(1, dsl=dsl)
        self.assertEqual(b["blades"], 1020)
        self.assertTrue(W.budget_problems("01", self.weapon(1).author, b))
        # 4) 不要脸的常规水准上限 600%：孤狼加一行攻击 +601% 对不要脸报，对一般提案不报
        ea = json.loads(json.dumps(self.ea(26)))
        ea.append(W.build_row(W.EA_T, len(ea), W.Eff("0", W.stat("32", W.T_SELF, 601), **W.FINAL)))
        b = self.budget(26, ea=ea)
        self.assertEqual(b["blades"], 601)
        self.assertEqual(len(W.budget_problems("26", "不要脸", b)), 1)
        self.assertEqual(W.budget_problems("26", "脆脆鲨", b), [])
        # 5) 永久叠加去掉次数上限：珊瑚毒爪每次强化弹射 +50% 无封顶必须报
        ea = json.loads(json.dumps(self.ea(23)))
        for r in ea:
            if _kind(W.EA_T, r) == "32":
                r[_col(W.EA_T, "instant_trigger", "trigger_limit")] = "(None)"
        b = self.budget(23, ea=ea)
        self.assertTrue(b["unbounded"])
        self.assertTrue(any("无次数上限" in p for p in W.budget_problems("23", "阿关", b)))
        # 6) 随机分支：赌注已下的转盘三支增益都给 +500%，按单支计；把某支抬到 +600% 必须看到 600
        dsl = json.loads(json.dumps(self.out["dsl"]))
        ac = next(n for n in _walk(dsl[W.dsl_program("fate_roll")])
                  if isinstance(n, list) and n and n[0] == "ACSkillDamage")
        ac[2] = W.P(6.0)
        self.assertEqual(self.budget(10, dsl=dsl)["blades"], 600)

    def test_budget_counts_counting_during_triggers(self):
        # 倒流沙漏的「逆沙」按层 134 读；换成别的计数型持续触发（202 CountAttackUp）也必须按倍乘上限 × 数值计，不能只算 1 次
        kind_at = _col(W.EA_T, "during_trigger", "kind")
        limit_at = _col(W.EA_T, "during_trigger", "trigger_limit")
        ea = json.loads(json.dumps(self.ea(24)))
        swapped = [r for r in ea if r[5] == "1" and r[kind_at] == W.DT_UNIQUE]
        self.assertEqual(len(swapped), 12)                                      # 雷/风 × (攻击 2 + 技能 2 + 第 5 层 2)
        for r in swapped:
            r[kind_at] = "202"
        b = self.budget(24, ea=ea)
        self.assertEqual((b["blades"], b["unbounded"]), (1000, []))
        # 负对照：倍乘上限写 (None) = 不封顶，必须报
        for r in swapped:
            r[limit_at] = "(None)"
        b = self.budget(24, ea=ea)
        self.assertTrue(b["unbounded"])
        self.assertTrue(any("没有倍乘上限" in p for p in W.budget_problems("24", "阿关", b)))

    def test_budget_reads_dsl_ac_by_signature(self):
        import wf_dsl_sig
        sig = wf_dsl_sig.ENUMS["AdditionalConditionKind"]
        counted = {n for n in sig if n in W.BLADE_ACS or W._is_mult_ac(n)}
        self.assertEqual(set(W._AC_SHAPES), counted)
        for name, (value_at, stacks_at) in W._AC_SHAPES.items():
            self.assertEqual(stacks_at, len(sig[name]), name)                   # 层数总在最后一个数组
            self.assertTrue(all(1 < i < stacks_at for i in value_at), name)
        # 逆境是 帧 / 最小 / 最大 / 层数 四数组：按最大值计，不能把最大值当层数
        dsl = json.loads(json.dumps(self.out["dsl"]))
        acs = next(n for n in _walk(dsl[W.dsl_program("gluttony_devour")])
                   if isinstance(n, list) and n and n[0] == "Command" and n[1][0] == "CreateCondition")[1][2]
        acs.append(["ACAdversity", W.P(900), W.P(0.2), W.P(0.6), W.P(1)])
        self.assertEqual(self.budget(1, dsl=dsl)["multipliers"], 60)
        acs[-1] = ["ACAdversity", W.P(900), W.P(0.2), W.P(0.6), W.P(2)]
        self.assertEqual(self.budget(1, dsl=dsl)["multipliers"], 120)
        # 没登记形状的刃/乘区 AC 不猜，报 unbounded
        acs[-1] = ["ACSeparatedTermUnknown", W.P(900), W.P(0.2), W.P(1)]
        b = self.budget(1, dsl=dsl)
        self.assertTrue(any("形状未登记" in u for u in b["unbounded"]), b["unbounded"])

    def test_budget_flags_overlapping_roulette_firings(self):
        # 赌注已下每 25 秒转一次、每支 10 秒：两次不重叠，按单支计是准的
        w10 = self.weapon(10)
        ea = json.loads(json.dumps(self.ea(10)))
        roll = next(r for r in ea if _kind(W.EA_T, r) == "629"
                    and self.cell(W.EA_T, r, "instant_content", "action_path") == W.dsl_program("fate_roll"))
        self.assertEqual(self.cell(W.EA_T, roll, "instant_trigger", "threshold.first_max"), W.frames(1500))
        self.assertEqual(self.budget(10, ea=ea)["unbounded"], [])
        # 负对照：周期缩到 5 秒，前一支还没结束又转出另一支，必须报
        for name in ("threshold.power1", "threshold.first_max"):
            roll[_col(W.EA_T, "instant_trigger", name)] = W.frames(300)
        b = self.budget(10, ea=ea)
        self.assertTrue(any("同时存活" in u for u in b["unbounded"]), b["unbounded"])
        self.assertTrue(W.budget_problems("10", w10.author, b))
        # 时机由战斗决定的触发：只触发 1 次或 CT 不短于持续时间才不重叠
        base = {"trig": W.IT_SKILL, "threshold": W.times(1), "delay": 0}
        self.assertTrue(W._refires_while_live({**base, "limit": "(None)", "cooltime": "0"}, 600))
        self.assertFalse(W._refires_while_live({**base, "limit": "1", "cooltime": "0"}, 600))
        self.assertFalse(W._refires_while_live({**base, "limit": "(None)", "cooltime": "600"}, 600))

    def test_budget_is_wired_into_build(self):
        from unittest import mock
        with mock.patch.object(W, "BLADE_CAP", 999), mock.patch.object(W, "MULTIPLIER_CAP", 49):
            probs = W.build(fixture_reader(), client_capabilities=W.PATCHED_CLIENT_CAPABILITIES)["problems"]
        blade_rows = {row for row, (blades, _m) in self.EXPECTED_BUDGETS.items() if blades > 999}
        mult_rows = {row for row, (_b, mults) in self.EXPECTED_BUDGETS.items() if mults > 49}
        self.assertEqual({int(p[:2]) for p in probs if "刃合计" in p}, blade_rows)
        self.assertEqual({int(p[:2]) for p in probs if "乘区合计" in p}, mult_rows)
        self.assertEqual(len(probs), len(blade_rows) + len(mult_rows))

    def test_rebalanced_summaries_match_values(self):
        # 0928 改过数值的武器：强化 120 说明里的数字要跟着改（旧数字不能残留）
        # 评分审查 0928（作者「按表改」）同批：1/2/3/7/8/9/10/11/14/15/16/18/22/23/25/27/28/29
        stale = {1: ["+80%", "15 秒"], 3: ["+500%"], 7: ["+600%", "+300%"], 8: ["+350%", "HP≥50%", "HP<50%"],
                 9: ["+750%", "每 10 秒", "+300%", "伤害独立 +500%", "110–119 秒", "121 秒"], 11: ["+100%"],
                 14: ["+1500%", "10 秒", "自身发动技能时攻击力"], 15: ["+250%", "+150%", "-30%"], 16: ["+500%"], 18: ["+700%", "×2", "限 2 次"],
                 19: ["+500%", "+1000%"], 21: ["+100%"], 22: ["+500%"], 23: ["+50%", "+250%", "+60%", "+240%"],
                 24: ["+160%", "+800%", "+150%", "+700%"], 25: ["+400%", "充能速度 -100%"],
                 26: ["+1000%", "伤害独立乘区 +100%"], 27: ["+500%", "20 次", "最多 6 次"], 29: ["+100%"]}
        fresh = {1: ["+100%", "30 秒"], 2: ["Fever 时间 +100%"], 3: ["+800%"], 7: ["+200%"], 8: ["+500%", "HP≥40%", "HP<40%"],
                 9: ["+1000%", "+500%", "+30%", "+50%", "110–129 秒", "131 秒"], 10: ["3:1", "增益持续 20 秒"],
                 11: ["+150%"], 14: ["+1000%", "40 秒", "任一角色"], 15: ["+100%", "-50%", "-35%"], 16: ["+250%"],
                 18: ["+1000%", "+600%", "+400%", "冷却 15 秒"], 19: ["+350%", "+650%", "+30%"], 21: ["+50%"], 22: ["+300%", "无法获得能量"],
                 23: ["+75%", "+375%", "+90%", "+360%"], 24: ["+100%（最多 +500%）"],
                 25: ["+600%", "+50%", "无法获得能量"], 26: ["+100%", "+50%"], 27: ["+140%", "最多 2 次"],
                 28: ["直接攻击伤害 +400%"], 29: ["攻击力 +500%", "+50%"]}
        for row in sorted(set(stale) | set(fresh)):
            text = self.weapon(row).summary_120
            for old in stale.get(row, ()):
                self.assertNotIn(old, text, row)
            for new in fresh[row]:
                self.assertIn(new, text, row)
            self.assertTrue(any("0928" in d for d in self.weapon(row).deviations), row)

    def test_uniques_use_dedicated_status_icons(self):
        # 作者 0928「武器专属效果的图标做了吗」：每个诅咒武器固有状态都用自己的 48×48 图标，源图在仓库里
        from PIL import Image
        for w in self.ws:
            for uid, row in w.uniques.items():
                name = row[2].rsplit("/", 1)[1]
                self.assertTrue(row[2].startswith("battle/common/unique_condition/cursed_"), (w.name, uid, row[2]))
                src = W.STATUS_ICON_DIR / f"{name}.png"
                self.assertTrue(src.is_file(), src)
                with Image.open(src) as im:
                    self.assertEqual((im.size, im.mode), ((48, 48), "RGBA"), src)

    def test_deterministic(self):
        again = W.build(fixture_reader(), client_capabilities=W.PATCHED_CLIENT_CAPABILITIES)
        self.assertEqual(again["flat"], self.out["flat"])
        self.assertEqual(again["dsl"], self.out["dsl"])
        self.assertEqual(again["server"], self.out["server"])

    def test_design_doc_covers_every_weapon(self):
        text = W.design_markdown(self.ws)
        for w in self.ws:
            self.assertIn(f"{w.row:02d}. {w.name}", text)


if __name__ == "__main__":
    unittest.main()
