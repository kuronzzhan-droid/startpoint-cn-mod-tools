# -*- coding: utf-8 -*-
"""澄波响 169988 ``psychic_teleport_moon`` 2026-09-27 平衡第三轮（c，成长复核）：
队长累计命中每 4 次自身攻击 5% → 35%、回响每层 2.5% → 20%。

fixture = live 输入快照（``fixtures/balance_20260927c_hibiki.json``，make_read(live_only=True)，本地链尾 1.4.1053），
驱动 ``revise()``：每处改动的前后值、未改行/未改面板行逐字保留、数值按「原值 × 2/3 向上取 5 的倍数」、
fixture 就是第二批输出（b → c 链）、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、合法性门禁为空、面板规则、
生成器输出 == revise() 输出（接管第二批测试的队长/面板一致性断言）、设计镜像已同步、候选干跑。
需要 ``.cdn/cn`` 官方基线与 live store 的用例缺时跳过。
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import re
import sys
import unittest
from unittest import mock

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_hibiki as B  # noqa: E402
import wf_balance_20260927c_hibiki as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_midautumn_kit_hibiki as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402
from wf_panel_merge_check import check as panel_merge_check  # noqa: E402  面板合并校验器（仓库内，硬依赖）

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927c_hibiki.json'
B_FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_hibiki.json'
WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]
#: 候选 ma-hibiki manifest 现有的 required_capabilities（改后不新增）。
CANDIDATE_CAPABILITIES = {"dash-parameter-v1", "panel-description-override-v2", "damage-type-rules-v1"}


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {kind: value for kind, value in data.items() if not kind.startswith("_")}


def load_fixture() -> dict:
    return load(FIXTURE)


def reader(data: dict):
    def read(kind, key):
        return data[kind]["|".join(key) if kind == "table" else key]
    return read


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


_CTX = None


def _kit_ctx():
    global _CTX
    if _CTX is None:
        import wf_midautumn_common as MC
        import wf_midautumn_specs as MS
        import wf_seasonal7_build as BLD
        _CTX = BLD.KitContext(MC.MAPack(MS.get_spec("hibiki"), record_sources=False))
    return _CTX


def _diff(a: list[str], b: list[str]) -> dict[int, tuple[str, str]]:
    return {col: (x, y) for col, (x, y) in enumerate(zip(a, b)) if x != y}


def _inputs(data: dict) -> dict:
    return {(kind, key): value for kind, table in data.items() for key, value in table.items()}


_NUMBER = re.compile(r"[＋+－\-]\d+(?:\.\d+)?%")


def _signed_numbers(text: str) -> Counter:
    return Counter(_NUMBER.findall(text))


# ---- 校验原文的显式规范化（主会话统一口径；每步都写在测试里，不借用模块常量）----

def normalize_resonance_punctuation(text: str) -> str:
    """口径 3：「X属性共鸣时：」→「X属性共鸣时，」（本角色返回面板里没有冒号写法 ⇒ 恒等，测试断言）。"""
    return re.sub(r"(属性共鸣时)[：:]", r"\1，", text)


def normalize_pf_damage_join(text: str) -> str:
    """口径 1：强化弹射伤害是战场级、原文不带对象 ⇒ 与前一个带对象的效果之间「、」改「，」。"""
    return text.replace("、强化弹射伤害", "，强化弹射伤害")


def split_leader_line5(text: str) -> str:
    """口径 5：队长第 5 行「；」前后是两种数据条件 ⇒ 拆成两行，后半行补上同一个共鸣前缀（数据三行都带暗共鸣）。"""
    lines = text.split("\n")
    head, sep, tail = lines[4].partition("；")
    assert sep and head.startswith("暗属性共鸣时，"), lines[4]
    return "\n".join(lines[:4] + [head, "暗属性共鸣时，" + tail] + lines[5:])


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old_leader = cls.live["leader"][M.LEADER_KEY]
        cls.new_leader = cls.out["leader"][M.LEADER_KEY]

    # ------------------------------------------------------------ 契约
    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys}, set(M.BEFORE))

    def test_fixture_is_the_batch2_output(self):
        """b → c 链：本轮的 live 输入 == 第二批模块对其快照的输出（1.4.1051 已发布、此后未再动）。"""
        b_out = B.revise(reader(load(B_FIXTURE)))
        self.assertEqual(self.old_leader, b_out["leader"][B.LEADER_KEY])
        self.assertEqual(self.live["cas"][M.CAS_LEADER], b_out["cas"][B.CAS_LEADER])
        self.assertEqual((B.HIT_NEW, B.ECHO_LEADER), (M.HIT_OLD, M.ECHO_OLD))
        self.assertEqual((B.HIT_OLD, B.ECHO_OLD), (M.HIT_ORIGINAL, M.ECHO_ORIGINAL))
        self.assertEqual(B.NEW_LEADER_LINES, M.OLD_LEADER_LINES)
        for key in M.CAS_INVOKE:
            self.assertEqual(self.live["cas"][key], load(B_FIXTURE)["cas"][key], key)
        # 能力4 面板合并的原像 == 第二批输出（第二批追加了回响那行）
        self.assertEqual(self.live["cas"][M.CAS_SLOT4], b_out["cas"][B.CAS_SLOT4])
        self.assertEqual(B.NEW_SLOT4_LINES, M.OLD_SLOT4_LINES)

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), (str(K.CID), K.CODE))
        self.assertEqual(M.PACKAGES, ["ma-hibiki"])
        self.assertEqual(M.PACKAGE_VERSION, {"ma-hibiki": "1.0.2"})   # 候选现值 1.0.1，只升不降
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertEqual((M.UID, M.UNIQUE_CAP, M.INVOKE_PROGRAM), (K.UID, K.UNIQUE_CAP, K.INVOKE_PROGRAM))
        self.assertEqual(M.CAS_LEADER, K.CAS_LEADER)
        self.assertEqual(M.CAS_INVOKE, (K.CAS_INVOKE_SKILL, K.CAS_INVOKE_DASH))
        self.assertEqual(M.MAIN_ICON, K.MAIN_ICON)

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["leader"]), {M.LEADER_KEY})
        self.assertEqual(set(out["cas"]), {M.CAS_LEADER, M.CAS_SLOT2, M.CAS_SLOT4})   # + 面板同条件合并两键
        for key in out["cas"]:
            self.assertTrue(key.startswith(f"desc_override_{M.CODE}"), key)
        for kind in ("ability", "text", "table", "action", "dsl", "server_text"):
            self.assertEqual(out[kind], {}, kind)                  # D4：能力栏封顶版不动
        self.assertEqual(out["new_programs"], [])
        json.dumps(out["notes"], ensure_ascii=False)
        self.assertFalse(out["notes"]["runtime_verified"])

    # ------------------------------------------------------------ 队长
    def test_leader_changes_only_the_three_growth_strengths(self):
        old, new = self.old_leader, self.new_leader
        self.assertEqual((len(old), len(new)), (12, 12))
        self.assertTrue(all(len(r) == 124 for r in new))
        changed = {i: _diff(a, b) for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual(changed, {
            6: {49: ("5000", "35000"), 50: ("5000", "35000")},
            10: {111: ("2500", "20000"), 112: ("2500", "20000")},
            11: {111: ("2500", "20000"), 112: ("2500", "20000")},
        })
        for i in (0, 1, 2, 3, 4, 5, 7, 8, 9):
            self.assertEqual(new[i], old[i], i)

    def test_growth_rows_keep_trigger_target_and_limits(self):
        row = self.new_leader[6]
        self.assertEqual((row[4], row[25], row[28], row[32], row[33], row[45], row[46]),
                         ("0", "15", "400000", "(None)", "0", "32", "0"))   # 仍不限次、只给自身、无共鸣门（D3）
        for index, kind in ((10, "23"), (11, "0")):
            row = self.new_leader[index]
            self.assertEqual((row[3], row[4], row[95], row[100], row[102], row[107], row[108]),
                             ("1", "0", "134", M.UNIQUE_CAP, M.UID, kind, "0"), index)

    def test_values_follow_the_two_thirds_floor(self):
        """原值 × 2/3 向上取 5 的倍数（下限 2/3，D1：25% 的行取 20% 而非 17.5%）。"""
        for original, value in ((M.HIT_ORIGINAL, M.HIT_NEW), (M.ECHO_ORIGINAL, M.ECHO_NEW)):
            original, value = int(original), int(value)
            self.assertEqual(value % 5000, 0)
            self.assertGreaterEqual(Fraction(value, original), Fraction(2, 3))
            self.assertLess(value - 5000, original * Fraction(2, 3))      # 向上取整的最小 5 的倍数
        self.assertEqual((M.HIT_NEW, M.ECHO_NEW), ("35000", "20000"))

    def test_three_minute_totals_match_the_table(self):
        self.assertEqual(int(M.HIT_NEW) // 1000 * 50, 1750)               # 50 次
        self.assertEqual(int(M.ECHO_NEW) // 1000 * int(M.UNIQUE_CAP), 1980)   # 满 99 层

    def test_leader_describe_readback(self):
        describe = D.describe_rows(self.new_leader, "leader_ability")
        self.assertEqual(describe[6], "强化弹射HitLv1≥4 → 自身 攻击力 35%")
        self.assertEqual(describe[10], "持续·状态累积计数固有≥1(限99次)[固有16998801] → 自身 强化弹射伤害 20%")
        self.assertEqual(describe[11], "持续·状态累积计数固有≥1(限99次)[固有16998801] → 自身 攻击力 20%")

    def test_the_invoke_rows_are_untouched(self):
        invokes = [r for r in self.new_leader if r[45] == "629"]
        self.assertEqual({r[25]: r[33] for r in invokes}, {"23": "0", "4": "90"})

    # ------------------------------------------------------------ 面板
    def test_panel_texts(self):
        leader = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        old = self.live["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertEqual((len(leader), len(old)), (10, 9))                # 第5行拆两行
        self.assertEqual(leader[:3], old[:3])
        self.assertEqual(leader[3], "持有贯穿效果时，暗属性角色攻击力＋300%，强化弹射伤害＋200%")   # 口径 1
        self.assertEqual(old[3], "持有贯穿效果时，暗属性角色攻击力＋300%、强化弹射伤害＋200%")
        self.assertEqual(leader[4:6], ["暗属性共鸣时，贯穿效果持续时间＋30%",                  # 口径 5
                                       "暗属性共鸣时，暗属性角色发动技能时，自身立即获得强化弹射效果"])
        self.assertEqual(old[4], "暗属性共鸣时，贯穿效果持续时间＋30%；暗属性角色发动技能时，自身立即获得强化弹射效果")
        self.assertEqual(leader[6], old[5])
        self.assertEqual(leader[7], "强化弹射每累计命中4次，自身攻击力＋35%")
        self.assertEqual(leader[8], "每1层“回响”，自身强化弹射伤害＋20%、攻击力＋20%")
        self.assertEqual(leader[9], old[8])

    def test_pf_damage_is_not_joined_to_an_object(self):
        """口径 1：「、强化弹射伤害」→「，强化弹射伤害」（队长第4行、能力2、能力4），不补「自身」。"""
        for key, rows in self.out["cas"].items():
            text, before = rows[0][0], self.live["cas"][key][0][0]
            self.assertNotIn("、强化弹射伤害", text, key)
            self.assertEqual(text.count("强化弹射伤害"), before.count("强化弹射伤害"), key)
            self.assertEqual(text.count("自身强化弹射伤害"), before.count("自身强化弹射伤害"), key)   # 没补对象
            self.assertEqual(normalize_pf_damage_join(before).count("，强化弹射伤害"), text.count("，强化弹射伤害"), key)
        self.assertEqual(sum(self.live["cas"][key][0][0].count("、强化弹射伤害") for key in self.out["cas"]), 1)
        self.assertEqual(M.pf_damage_problems(_inputs(self.live)), [])
        # 数据侧：三处都是强化弹射伤害（kind 55 / during 23）；换成别的 kind ⇒ 依据失效，revise 拒绝
        data = deepcopy(self.live)
        data["ability"][M.ABILITY2][1][47] = "32"
        self.assertTrue(M.pf_damage_problems(_inputs(data)))
        with mock.patch.dict(M.BEFORE, {("ability", M.ABILITY2): M.digest(data["ability"][M.ABILITY2])}):
            with self.assertRaisesRegex(ValueError, "panel rewrite basis drifted"):
                M.revise(reader(data))

    def test_leader_line5_is_split_by_data_condition(self):
        """口径 5：#3（暗共鸣常驻 → 贯穿延长）与 #5/#8（暗共鸣且暗属性角色发动技能）是两种数据条件 ⇒ 拆两行，各带共鸣。"""
        leader = self.old_leader
        self.assertEqual(M.split_basis_problems(leader), [])
        self.assertEqual(D.describe_rows([leader[i] for i in (3, 5, 8)], "leader_ability"), [
            "暗·编成≥6 时: 自身 贯通延长 30%",
            "暗·编成≥6 时: 技能发动≥1 → 自身 发动技能动作[ability_skill_psychic_teleport_moon_pf_skill]",
            "暗·编成≥6 时: 技能发动≥1 → 自身 计数+强化弹射 100%"])
        self.assertEqual((leader[5][26], leader[5][27]), ("5", "Black"))       # 暗属性角色发动技能
        text = self.out["cas"][M.CAS_LEADER][0][0]
        self.assertEqual(text.count("暗属性共鸣时，"), self.live["cas"][M.CAS_LEADER][0][0].count("暗属性共鸣时，") + 1)
        self.assertNotIn("；", text)
        # 反例：去掉 #8 的暗共鸣 / 两组条件变成同一个 / 拆行的内容行换了 kind ⇒ 依据失效（revise 拒绝）
        for mutate in (lambda r: r[8].__setitem__(4, "0"),
                       lambda r: r[3].__setitem__(slice(1, 45), r[5][1:45]),
                       lambda r: r[3].__setitem__(45, "32")):
            rows = deepcopy(leader)
            mutate(rows)
            self.assertTrue(M.split_basis_problems(rows))
        self.assertEqual(M.split_basis_problems(leader[:6]), [f"split rows {M.SPLIT_ROWS} out of range (6 rows)"])
        # 接线：依据失效时 revise() 拒绝（即使 BEFORE 已按新值复核）
        data = deepcopy(self.live)
        data["leader"][M.LEADER_KEY][8][4] = "0"
        with mock.patch.dict(M.BEFORE, {("leader", M.LEADER_KEY): M.digest(data["leader"][M.LEADER_KEY])}):
            with self.assertRaisesRegex(ValueError, "panel rewrite basis drifted"):
                M.revise(reader(data))

    def test_panel_agrees_with_the_data(self):
        leader = self.out["cas"][M.CAS_LEADER][0][0]
        hit = self.new_leader[6]
        self.assertIn(f"每累计命中{int(hit[28]) // 100000}次，自身攻击力＋{int(hit[49]) // 1000}%", leader)
        step = int(self.new_leader[10][111]) / 1000
        self.assertEqual(step, int(self.new_leader[11][111]) / 1000)
        self.assertIn(f"强化弹射伤害＋{step:g}%、攻击力＋{step:g}%", leader)

    def test_panel_text_obeys_the_project_rules(self):
        for key, rows in self.out["cas"].items():
            text = rows[0][0]
            self.assertEqual(M.panel_problems(key, text), [], key)
            self.assertEqual(L.panel_override_capability(key), "panel-description-override-v2")
            for line in text.split("\n"):
                self.assertFalse(line.startswith(M.MAIN_ICON), line)
                self.assertEqual(KL.panel_problems(line), [], line)
            for word in ("最多99层", "可无限", "无上限", "／", "属性共鸣时：", "自身为队长时", "觉醒后", "生命值100%以下"):
                self.assertNotIn(word, text)

    # ------------------------------------------------------------ 面板同条件合并 / 共鸣省略
    def test_merged_panels_verbatim(self):
        """合并行逐字；合并行放在组首行位置，其余行逐字保留。"""
        self.assertEqual(self.out["cas"][M.CAS_SLOT2],
                         [["持有贯穿效果时，每发动1次强化弹射，自身攻击力＋8%，强化弹射伤害＋12%（最多25次）"]])
        self.assertEqual(self.out["cas"][M.CAS_SLOT4],
                         [["持有贯穿效果期间，自身攻击力＋200%，强化弹射伤害＋150%\n"
                           "每1层“回响”，自身攻击力＋5%（最多10层）"]])
        self.assertEqual(self.live["cas"][M.CAS_SLOT2][0][0].split("\n"), list(M.OLD_SLOT2_LINES))
        self.assertEqual(self.live["cas"][M.CAS_SLOT4][0][0].split("\n"), list(M.OLD_SLOT4_LINES))
        self.assertEqual(M.NEW_SLOT4_LINES[1], M.OLD_SLOT4_LINES[2])          # 回响行逐字不动

    def test_merged_panels_keep_every_effect_value(self):
        for key in (M.CAS_SLOT2, M.CAS_SLOT4):
            before, after = self.live["cas"][key][0][0], self.out["cas"][key][0][0]
            self.assertEqual(_signed_numbers(before), _signed_numbers(after), key)
            for token in ("（最多25次）", "（最多10层）", "持有贯穿效果"):
                self.assertLessEqual(after.count(token), before.count(token), (key, token))
                self.assertEqual(token in after, token in before, (key, token))
        self.assertEqual(self.out["cas"][M.CAS_SLOT2][0][0].count("（最多25次）"), 1)   # 同后缀只写一次

    def test_merge_groups_are_one_data_condition(self):
        """合并组按数据核对：组内两行除效果列（kind/对象/元素/强度）外逐格相同。"""
        for key, (ability_key, rows, lines, old, new) in M.PANEL_MERGES.items():
            data = self.live["ability"][ability_key]
            self.assertEqual(M.merge_condition_problems("ability", data, rows), [], key)
            self.assertTrue(all(len(r) == M.ABILITY_NCOLS for r in data), key)
            self.assertEqual({r[1] for r in data}, {"true"}, key)                 # 不限主位 ⇒ 面板无 Ⓜ
            self.assertEqual(len(old) - len(new), len(lines) - 1, key)
        a2 = self.live["ability"][M.ABILITY2]
        self.assertEqual([(r[27], r[34], r[47], r[51]) for r in a2],
                         [("2", "25", "32", "8000"), ("2", "25", "55", "12000")])
        a4 = self.live["ability"][M.ABILITY4]
        self.assertEqual([(r[5], r[97], r[109], r[113]) for r in a4[:2]],
                         [("1", "30", "0", "200000"), ("1", "30", "23", "150000")])
        # 条件列任一不同都拒绝（次数上限 / 前置 / 主位 c1）
        for col, value in ((34, "10"), (6, "2"), (1, "false")):
            rows = deepcopy(a2)
            rows[1][col] = value
            self.assertTrue(M.merge_condition_problems("ability", rows, (0, 1)), col)
        # 回响行（能力4 #2）条件不同，不在组里
        self.assertTrue(M.merge_condition_problems("ability", a4, (0, 2)))

    def test_check_merge_passes(self):
        """面板合并校验器（wf_panel_merge_check，硬依赖）：原文先按口径 3/1/5 显式规范化，再与输出比对。

        - 能力2/能力4：原文 = live；只做口径 3（恒等）。口径 1 的「，」落在合并行里，校验器不看分隔符。
        - 队长块：原文 = live 同步数值后（第三轮改数，:data:`M.NUMBER_LEADER_LINES`，另有逐字断言）
          → 口径 3（恒等）→ 口径 1（第4行「、」→「，」）→ 口径 5（第5行按「；」拆两行）；之后逐行 verbatim。
        """
        live = {key: self.live["cas"][key][0][0] for key in self.out["cas"]}
        for key, text in live.items():
            self.assertEqual(normalize_resonance_punctuation(text), text, key)       # 口径 3：本角色无冒号写法
        lines = live[M.CAS_LEADER].split("\n")                                      # 数值同步只动第7/8行
        lines[6] = lines[6].replace("＋5%", "＋35%")
        lines[7] = lines[7].replace("＋2.5%", "＋20%")
        numbers = "\n".join(lines)
        self.assertEqual(tuple(lines), M.NUMBER_LEADER_LINES)
        leader_orig = split_leader_line5(normalize_pf_damage_join(normalize_resonance_punctuation(numbers)))
        cases = {M.CAS_SLOT2: (normalize_resonance_punctuation(live[M.CAS_SLOT2]), {1: "merge"}),
                 M.CAS_SLOT4: (normalize_resonance_punctuation(live[M.CAS_SLOT4]), {1: "merge", 2: "verbatim"}),
                 M.CAS_LEADER: (leader_orig, {j: "verbatim" for j in range(1, 11)})}
        for key, (orig, kinds) in cases.items():
            result = panel_merge_check(orig, self.out["cas"][key][0][0], prefix_drops=[])
            self.assertTrue(result["ok"], (key, result["errors"]))
            self.assertEqual(result["warnings"], [], key)
            self.assertEqual(result["columns"][0]["kinds"], kinds, key)
        # 负对照：不做口径 1/5 的规范化，队长块的改写就是未登记的单来源改写（校验器必须报错）
        self.assertFalse(panel_merge_check(numbers, self.out["cas"][M.CAS_LEADER][0][0])["ok"])
        # 负对照：合并行丢一个效果数值
        broken = self.out["cas"][M.CAS_SLOT2][0][0].replace("，强化弹射伤害＋12%", "")
        self.assertFalse(panel_merge_check(live[M.CAS_SLOT2], broken)["ok"])

    def test_resonance_prefix_is_not_dropped(self):
        """共鸣省略依据：「回响」获取来源里有不带共鸣的队长行（#4，每3次强化弹射 +2 层）⇒ 不省略。"""
        self.assertEqual(M.PREFIX_DROPS, {})
        sources = M.echo_grant_sources(self.new_leader)
        self.assertEqual(sources, [(4, False)])
        row = self.new_leader[4]
        self.assertEqual((row[4], row[11], row[18], row[25], row[45], row[66]), ("0", "0", "0", "2", "461", M.UID))
        for key, rows in self.out["cas"].items():
            before = self.live["cas"][key][0][0]
            split = 1 if key == M.CAS_LEADER else 0                            # 口径 5 拆行：后半行补同一个前缀
            self.assertEqual(rows[0][0].count("属性共鸣时，"), before.count("属性共鸣时，") + split, key)
        # 若队长 #4 也加了暗共鸣，这条依据就不成立（revise 会拒绝，需重审共鸣省略）
        rows = deepcopy(self.new_leader)
        rows[4][4] = "2"
        self.assertEqual(M.echo_grant_sources(rows), [(4, True)])

    def test_merged_panel_rejects_other_layouts(self):
        for key, fn in ((M.CAS_SLOT2, M.slot2_panel), (M.CAS_SLOT4, M.slot4_panel)):
            with self.assertRaises(ValueError):
                fn(self.out["cas"][key][0][0])                                   # 自身输出
            with self.assertRaises(ValueError):
                fn(self.live["cas"][key][0][0] + "\n多一行")

    # ------------------------------------------------------------ 合法性
    def test_native_legality_gates_are_empty(self):
        cas_keys = {M.CAS_LEADER, *M.CAS_INVOKE}
        for index, row in enumerate(self.new_leader):
            label = f"leader#{index}"
            self.assertEqual(L.client_legality_problems("leader_ability", row), [], label)
            self.assertEqual(L.declared_block_field_problems("leader_ability", row), [], label)
            self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, "leader_ability"), [], label)
            self.assertEqual(KL.row_problems("leader_ability", row, None), {}, label)
            self.assertLessEqual(set(L.required_client_capabilities("leader_ability", row)),
                                 CANDIDATE_CAPABILITIES, label)
        K._row_self_check("leader_ability", self.new_leader, "leader")

    # ------------------------------------------------------------ 失败闭合
    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["leader"][M.LEADER_KEY][6][49] = "mutated"
        out["cas"][M.CAS_LEADER][0][0] = "mutated"
        out["cas"][M.CAS_SLOT4][0][0] = "mutated"
        self.assertEqual(data, self.live)

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            data = deepcopy(self.live)
            data[kind][key][0][-1] = data[kind][key][0][-1] + "x"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))
            data = deepcopy(self.live)
            data[kind][key] = None
            with self.assertRaises(ValueError):
                M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        data = deepcopy(self.live)
        for kind in ("leader", "cas"):
            data[kind].update(deepcopy(self.out[kind]))
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise(reader(data))
        with self.assertRaises(ValueError):
            M.leader_rows(self.new_leader)
        with self.assertRaises(ValueError):
            M.leader_text(self.out["cas"][M.CAS_LEADER])
        for key in (M.CAS_SLOT2, M.CAS_SLOT4):
            with self.assertRaises(ValueError):
                M.slot_text(key, self.out["cas"][key])

    def test_batch2_preimage_is_required(self):
        """第二批之前的形状（10 行、50%）不是本轮原像：跳过第二批直接套本轮必须拒绝。"""
        b_live = load(B_FIXTURE)
        with self.assertRaises(ValueError):
            M.leader_rows(b_live["leader"][B.LEADER_KEY])
        with self.assertRaises(ValueError):
            M.leader_text(b_live["cas"][B.CAS_LEADER])

    def test_row_locators_are_content_based(self):
        for mutate in (lambda r: r[6].__setitem__(32, "10"),                   # 命中行已限次
                       lambda r: r[10].__setitem__(100, "10"),                 # 回响行已封顶
                       lambda r: r[11].__setitem__(4, "2"),                    # 回响行多了共鸣门
                       lambda r: r[7].__setitem__(33, "300"),                  # 冲刺 629 CT 5 秒
                       lambda r: r.__setitem__(slice(10, 12), [r[11], r[10]]),  # 两条回响行对调
                       lambda r: r.pop()):
            rows = deepcopy(self.old_leader)
            mutate(rows)
            with self.assertRaises(ValueError):
                M.leader_rows(rows)


class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_midautumn_kit_hibiki 重跑不能把第二批的 5%/2.5% 带回来（接管 b 测试的队长/面板一致性断言）。"""

    @classmethod
    def setUpClass(cls):
        cls.out = M.revise(reader(load_fixture()))

    def test_panel_constants_equal_revise_output(self):
        for key, rows in self.out["cas"].items():
            self.assertEqual([[K.CAS_TEXTS[key]]], rows, key)
        self.assertEqual(tuple(K.PANEL_LEADER.split("\n")), M.NEW_LEADER_LINES)
        # 槽 3 仍是第二批的封顶版文案（D4）；槽 2/槽 4 是面板同条件合并后的文案（槽 4 回响行 = 第二批封顶版）
        self.assertEqual(tuple(K.PANEL_ABILITY[3].split("\n")), B.NEW_SLOT3_LINES)
        self.assertEqual(tuple(K.PANEL_ABILITY[2].split("\n")), M.NEW_SLOT2_LINES)
        self.assertEqual(tuple(K.PANEL_ABILITY[4].split("\n")), M.NEW_SLOT4_LINES)
        self.assertEqual(K.PANEL_ABILITY[4].split("\n")[-1], B.NEW_SLOT4_LINES[-1])
        self.assertNotIn(2, K.MAIN_ONLY_SLOTS)
        self.assertNotIn(4, K.MAIN_ONLY_SLOTS)

    def test_plan_cells_carry_the_new_values(self):
        self.assertEqual(K.LEADER_ROWS, M.LEADER_ROWS)
        self.assertEqual((K.HIT_ATTACK_STEP, K.ECHO_LEADER_STEP), (M.HIT_NEW, M.ECHO_NEW))
        hit = K.LEADER[M.HIT_ROW][2]
        self.assertEqual((hit[25], hit[32], hit[49], hit[50]), ("15", "(None)", M.HIT_NEW, M.HIT_NEW))
        for (_addr, _src, cells, _expect), kind in zip(K.LEADER[10:], ("23", "0")):
            self.assertEqual((cells[95], cells[100], cells[102], cells[107], cells[111], cells[112]),
                             ("134", K.UNIQUE_CAP, K.UID, kind, M.ECHO_NEW, M.ECHO_NEW))
        # 能力侧封顶版不动（D4）
        pfdmg, atk = K.PLAN[3][B.PFDMG_ROW][2], K.PLAN[4][B.ATK_ROW][2]
        self.assertEqual((pfdmg[102], pfdmg[113], pfdmg[114]), ("10", B.ECHO_PFDMG_ABILITY, B.ECHO_PFDMG_ABILITY))
        self.assertEqual((atk[102], atk[113], atk[114]), ("10", B.ECHO_ATK_ABILITY, B.ECHO_ATK_ABILITY))

    def test_leader_plan_describes_the_revised_rows(self):
        self.assertEqual(D.describe_rows(self.out["leader"][M.LEADER_KEY], "leader_ability"),
                         [expect for _a, _s, _c, expect in K.LEADER])

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_rows_equal_revise_output(self):
        rows = K.build_rows(_kit_ctx())
        self.assertEqual(rows["leader"], self.out["leader"][M.LEADER_KEY])
        described = [ev["describe"] for ev in rows["evidence"] if ev["kind"] == "leader_ability"]
        self.assertEqual(described, [e for *_x, e in K.LEADER])


class MirrorTests(unittest.TestCase):
    PATHS = (ROOT / M.DESIGN_REL, ROOT / M.PANEL_REL)

    def setUp(self):
        if not all(path.is_file() for path in self.PATHS):
            self.skipTest("midautumn design mirrors missing")
        self.docs = [json.loads(path.read_text(encoding="utf-8")) for path in self.PATHS]

    def test_mirrors_are_already_synced(self):
        self.assertEqual(M.sync_mirrors(ROOT, write=False), [])
        design, panel = self.docs
        self.assertEqual(K.design_problems(design), [])
        self.assertEqual(design["plan_rework1"]["leader_rows"], M.LEADER_ROWS)
        self.assertEqual([r["describe"] for r in design["plan_rework1"]["leader_records"]],
                         [e for *_x, e in K.LEADER])
        self.assertEqual(design["rework1"][M.MIRROR_TAG]["module"], "mod-tools/wf_balance_20260927c_hibiki.py")
        self.assertIn(B.MIRROR_TAG, design["rework1"])                 # 第二批记录留作历史
        self.assertEqual([line["text"] for line in panel["leader"]["lines"]], K.PANEL_LEADER.split("\n"))
        for block in panel["abilities"]:
            self.assertEqual([line["text"] for line in block["lines"]],
                             K.PANEL_ABILITY[int(block["index"])].split("\n"))
        self.assertEqual(panel["notes"][-1], M.MIRROR_NOTE)
        self.assertIn(B.MIRROR_NOTE, panel["notes"])
        mirror_panel = design["rework1"][M.MIRROR_TAG]["panel"]
        self.assertEqual(mirror_panel[M.CAS_SLOT2], list(M.NEW_SLOT2_LINES))
        self.assertEqual(mirror_panel[M.CAS_SLOT4], list(M.NEW_SLOT4_LINES))

    def test_mirror_update_is_idempotent_and_pure(self):
        before = deepcopy(self.docs)
        once = M.mirror_updates(*self.docs)
        self.assertEqual(self.docs, before)
        self.assertEqual(M.mirror_updates(*once), once)


@unittest.skipUnless((WORKSPACE / "package/manifest.json").is_file()
                     and (ROOT / "mod-tools/profiles.json").is_file(), "local candidate workspace required")
class CandidateTests(unittest.TestCase):
    def test_candidate_accepts_the_revision_dry(self):
        """候选与 live 逐字相同（REVIEWED_DRIFT 为空）；dry-run 回写不落盘。回写后改为逐项比对。"""
        import wf_share_update_codec as X
        from wf_character_revision import RevisionCandidate
        out = M.revise(reader(load_fixture()))
        manifest = WORKSPACE / "package/manifest.json"
        before = manifest.read_bytes()
        current = json.loads(before)
        self.assertLessEqual(set(current["required_capabilities"]), CANDIDATE_CAPABILITIES)
        version = tuple(map(int, M.PACKAGE_VERSION[M.PACKAGES[0]].split(".")))
        have = tuple(map(int, current["package_version"].split(".")))
        candidate = RevisionCandidate(ROOT, WORKSPACE, character_id=M.CID, code_name=M.CODE,
                                      snapshot_key="revision_20260927c", package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
                                      baseline_factory=lambda *a, **k: None, reviewed_input_drift=M.REVIEWED_DRIFT)
        if have >= version:
            for logical, table in (("master/ability/leader_ability.orderedmap", out["leader"]),
                                   ("master/string/custom_ability_string.orderedmap", out["cas"])):
                rows = X.unpack(candidate.read("common", logical))
                for key, value in table.items():
                    self.assertEqual(X.csv_read(rows[key]), value, key)
            return
        candidate.splice("master/ability/leader_ability.orderedmap", out["leader"])
        candidate.splice("master/string/custom_ability_string.orderedmap", out["cas"])
        evidence = candidate.finish({"dry_run": True}, apply=False)
        self.assertFalse(evidence["applied"])
        self.assertEqual(len(evidence["changed_files"]), 2)
        self.assertEqual(before, manifest.read_bytes())


if __name__ == "__main__":
    unittest.main()
