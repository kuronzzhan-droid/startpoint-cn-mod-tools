# -*- coding: utf-8 -*-
"""希尔媞·校园 149989 ``wind_spgirl_campus`` 2026-09-27 平衡第三轮（c）：成长复核 + 技能倍率撤封顶。

fixture（``fixtures/balance_20260927c_celtie.json``）= revise() 的 live 输入快照（链尾 1.4.1053，
``stage_batch.make_read(live_only=True)`` 只读），离线驱动：每处改动的前后值、未改行 / 树节点逐字保留、
BEFORE 漂移拒绝、新键已存在拒绝、不改输入、对自身输出重跑拒绝、合法性与 DSL 门禁、AMF3 往返、
vlv 作用域（复核意见）、旗号 2 分支语义、面板规则、生成器输出 == revise() 输出。
技能强化文案规范（作者 2026-09-27「技能里面不要重复描述强化后的效果,规范并简化描述」）：强化条目官方格式、点名『风中快门·十字双空牙』、CAS ↔ 面板同文、技能描述 5 处保持本体原文（不写「不受此限」）、旗号 1 条目的数据依据。
面板共鸣省略：终稿逐字、共鸣省略依据（四个星风状态只由带风共鸣的 629 授予，删前缀行的数据依赖这些状态；
队长第 7 行是能力1 I704 开关行，共鸣是真实条件，保留——主会话口径 2）、数值稿 / live → 终稿过
``mod-tools/wf_panel_merge_check.check``（仓库内校验器，硬依赖，不跳过）。
需要 ``.cdn/cn`` 官方基线的完整装配对比、需要本机候选工作区的检查用 skipUnless。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.
sys.setrecursionlimit(10000)

import wf_balance_20260927b_celtie as B  # noqa: E402
import wf_balance_20260927c_celtie as M  # noqa: E402
import wf_campus_panel_text as P  # noqa: E402
import wf_celtie_fever_abilities as A  # noqa: E402
import wf_celtie_fever_leader as LD  # noqa: E402
import wf_celtie_skill_growth as G  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
from wf_panel_merge_check import check as check_merge  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402
from wf_midautumn_kit_hibiki import dsl_problems as kit_dsl_problems  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927c_celtie.json'
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))
WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]
TABLE = {"ability": "ability", "leader": "leader_ability"}
MAIN = " <icon id='main'>  "
FINAL_PANELS = {
    "desc_override_wind_spgirl_campus": [
        "风属性角色攻击力+200%、能力伤害+400%。",
        "风属性共鸣时，强化弹射变为特殊剑士型，造成风属性伤害，伤害量以能力伤害加成判定。",
        "风属性共鸣时，Fever模式中，强化弹射时，对全场敌人追加10倍风属性能力伤害。",
        "风属性共鸣时，Fever模式中，风属性角色发动技能时，自身获得2层「星风快门」与2层「星风心得」。",
        "Fever模式中，弹射时消耗1层「星风快门」，连击+7。",
        "Fever模式中，每层「星风心得」使风属性角色能力伤害+20%、攻击力+20%。",
        "风属性共鸣时，强化『风中快门·十字双空牙』：技能倍率随「星风心得」层数持续提升。",
    ],
    "desc_override_wind_spgirl_campus_1": [
        MAIN + "战斗开始时：自身技能槽+50%。",
        MAIN + "风属性共鸣时，为『风中快门·十字双空牙』追加「赋予全队贯穿＋风属性角色能力伤害提升效果」"
               "与「赋予命中的敌人风属性抗性降低效果」。",
    ],
    "change_skill_wind_spgirl_campus_fever": [
        "为『风中快门·十字双空牙』追加「赋予全队贯穿＋风属性角色能力伤害提升效果」与「赋予命中的敌人风属性抗性降低效果」",
    ],
    "change_skill_wind_spgirl_campus_leader": [
        "强化『风中快门·十字双空牙』：技能倍率随「星风心得」层数持续提升",
    ],
    "desc_override_wind_spgirl_campus_2": [
        "风属性共鸣时，风属性角色直接攻击分为3次，能力伤害+200%。",
        "Fever模式中，每消耗1层「星风快门」，Fever槽+5%。",
    ],
    "desc_override_wind_spgirl_campus_3": [
        MAIN + "风属性共鸣时，Fever模式中，风属性角色合计每直接攻击35次，对全场敌人造成25倍风属性能力伤害。",
        MAIN + "风属性共鸣时，非Fever模式中，风属性角色合计每直接攻击35次，Fever槽+15%。",
        MAIN + "风属性共鸣时，Fever模式中，连击每达到7的倍数，风属性角色攻击力+70%（最大+700%）、技能槽+0.7%（回槽冷却时间：0.7秒）。",
        MAIN + "风属性共鸣时，Fever模式中，风属性角色发动技能时，自身获得1层「星风快门」。",
        MAIN + "Fever模式中，弹射时消耗1层「星风快门」，连击+7。",
        MAIN + "风属性共鸣时，每获得1层「星风快门」，自身获得1层「星风心得」。",
        MAIN + "Fever模式中，每层「星风心得」使风属性角色能力伤害+8%、攻击力+5%（最多10层）。",
    ],
}
#: 每块面板：数值稿（check_merge 原文）与删共鸣前缀的行号（1 起）。
PANEL_DROPS = {"desc_override_wind_spgirl_campus": (M.LEADER_LINES_NUMERIC, (5, 6)),
               "desc_override_wind_spgirl_campus_2": (M.A2_LINES_BEFORE, (2,)),
               "desc_override_wind_spgirl_campus_3": (M.A3_LINES_BEFORE, (5, 7))}


def load_fixture() -> dict:
    data = {kind: value for kind, value in deepcopy(DATA).items() if not kind.startswith("_")}
    data["action"] = {key: [(inner, fields) for inner, fields in value]
                      for key, value in data["action"].items()}
    return data


def reader(data: dict):
    def read(kind, key):
        return data[kind][key]      # 缺键抛 KeyError（同 stage_batch.make_read）
    return read


def binds(tree) -> list[list]:
    return [args for args in M._commands(tree) if args[0] == "BindConditionAccumulationVariable"]


def as_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(x) for x in version.split("."))


def reachable_attacks(node, *, flag2, fever, winds, layers, scope=None, out=None):
    """独立转录原生分支语义：Block 开局部作用域，Bind 只对其后兄弟可见（min(层/除数, 上限)）；
    Fever / 风共鸣 / 旗号 2 只走选中的一支；旗号 1 两支都走（只含状态，不含 Bind）；其余全部下钻。"""
    scope = {} if scope is None else scope
    out = [] if out is None else out
    if not isinstance(node, list) or not node:
        return out
    kwargs = dict(flag2=flag2, fever=fever, winds=winds, layers=layers, out=out)
    if node[0] == "Block" and len(node) == 2 and isinstance(node[1], list):
        local = dict(scope)
        for child in node[1]:
            reachable_attacks(child, scope=dict(local), **kwargs)
            if (isinstance(child, list) and len(child) == 2 and child[0] == "Command"
                    and child[1][0] == "BindConditionAccumulationVariable"):
                args = child[1]
                local[args[2]] = min(layers / args[4], args[5])
        return out
    if node[0] == "Command" and len(node) == 2 and isinstance(node[1], list):
        args = node[1]
        if args[0] == "ConditionalsFeverMode":
            return reachable_attacks(args[1 if fever else 2], scope=scope, **kwargs)
        if args[0] == "ConditionalsUnifyElement":
            return reachable_attacks(args[3 if winds >= 6 else 4], scope=scope, **kwargs)
        if args[0] == "ConditionalsChangeSkillFlag" and args[1] == 2:
            return reachable_attacks(args[2 if flag2 else 3], scope=scope, **kwargs)
        if args[0] == "CreateNormalAttack":
            out.append((args, dict(scope)))
        for child in args[1:]:
            reachable_attacks(child, scope=scope, **kwargs)
        return out
    for child in node:
        reachable_attacks(child, scope=scope, **kwargs)
    return out


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    # ---- 契约

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
            self.assertRegex(want, r"^[0-9a-f]{64}$")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys},
                         set(M.BEFORE))
        self.assertEqual([tuple(x) for x in DATA["_absent"]], list(M.ABSENT))
        self.assertEqual(DATA["_meta"]["live_tail"], "1.4.1053")
        self.assertEqual(DATA["_meta"]["live_tail_rechecked"], "1.4.1054")

    def test_live_baseline_is_exactly_the_batch2_output(self):
        """第三轮输入 = 第二批 revise() 输出（第二批已上 1.4.1051，1052/1053 未碰本角色）。"""
        import test_balance_20260927b_celtie as TB
        b_out = B.revise(TB.reader(TB.load_fixture()))
        for kind, key in M.BEFORE:
            if kind == "ability" and key == M.ABILITY_KEY or key not in b_out[kind]:
                continue          # 1499891、能力2 面板、四个 629 程序第二批未触碰（面板共鸣省略新读入）
            got = self.live[kind][key]
            want = b_out[kind][key]
            if kind == "action":
                got, want = [list(x) for x in got], [list(x) for x in want]
            self.assertEqual(got, want, f"{kind}:{key}")

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), (A.CID, A.CODE))
        self.assertEqual(M.PACKAGES, ["campus-celtie-20260911"])
        self.assertEqual(M.PACKAGE_VERSION, {"campus-celtie-20260911": "0.20260927.1"})
        # 候选现值（第二批回写）0.20260927，数字点分比较只升不降。
        self.assertGreater(as_tuple(M.PACKAGE_VERSION[M.PACKAGES[0]]), as_tuple(B.PACKAGE_VERSION[M.PACKAGES[0]]))
        self.assertEqual(M.CAPABILITIES, ["panel-description-override-v2"])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertFalse(self.out["notes"]["runtime_verified"])
        json.dumps(self.out["notes"], ensure_ascii=False)

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out), {"ability", "leader", "cas", "text", "table", "action", "dsl",
                                    "server_text", "new_programs", "notes"})
        self.assertEqual(set(out["ability"]), {M.ABILITY_KEY})
        self.assertEqual(set(out["leader"]), {M.CID})
        self.assertEqual(set(out["cas"]), {M.CAS_LEADER, M.CAS_SWITCH, M.CAS_A2, M.CAS_A3, M.CAS_A1, M.CAS_FEVER})
        # 技能描述 5 处只写本体、不改（技能强化文案规范 R3）⇒ 不返回。
        self.assertEqual(out["text"], {})
        self.assertEqual(out["server_text"], {})
        self.assertEqual(out["action"], {})
        self.assertEqual(set(out["dsl"]), set(M.PROGRAMS.values()))
        self.assertEqual(out["table"], {})
        self.assertEqual(out["new_programs"], [M.PROGRAMS["1"], M.PROGRAMS["2"]])
        for key in [*out["ability"], *out["leader"], *out["cas"], *out["text"], *out["action"]]:
            # stage_batch Plan.splice 的候选命名空间断言
            self.assertTrue(key.startswith((M.CID, M.CODE, "desc_override_" + M.CODE,
                                            "change_skill_" + M.CODE)), key)

    # ---- 队长 #6/#7

    def test_leader_only_the_two_insight_growth_strengths_change(self):
        old, new = self.live["leader"][M.CID], self.out["leader"][M.CID]
        self.assertEqual((len(old), len(new)), (8, 8))
        seen = {i: {c: (x, y) for c, (x, y) in enumerate(zip(a, b)) if x != y}
                for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual(seen, {6: {111: ("2500", "20000"), 112: ("2500", "20000")},
                                7: {111: ("2500", "20000"), 112: ("2500", "20000")}})
        for index, content in ((6, "154"), (7, "0")):
            row = new[index]
            self.assertEqual((row[3], row[95], row[100], row[102], row[107]),
                             ("1", "134", "(None)", M.GAIN_UID, content))
        self.assertEqual([row[45] for row in new[:6]], list(M.LEADER_KINDS))
        rendered = [wf_describe.describe_rows([row], "leader_ability")[0] for row in new[6:]]
        self.assertEqual(rendered, [
            "风·编成≥6 且 Fever 时: 持续·状态累积计数固有≥1[固有14998902] → 赋予全队(风) 能力伤害 20%",
            "风·编成≥6 且 Fever 时: 持续·状态累积计数固有≥1[固有14998902] → 赋予全队(风) 攻击力 20%",
        ])

    def test_growth_value_follows_the_two_thirds_tier_and_multiple_of_five(self):
        """作者「可以砍到2/3」「数值尽量取5的倍数」；口径 D1：原 25% 的 2/3 档一律取 20%。"""
        original, new = int(M.GROWTH_TABLE["original"]), int(M.GROWTH_NEW)
        self.assertEqual(int(M.GROWTH_TABLE["batch2"]) * 10, original)   # 第二批 1/10
        self.assertGreaterEqual(new * 3, original * 2)                    # 不低于 2/3 下限
        self.assertEqual(new % 5000, 0)                                   # 5 的倍数（%）
        self.assertEqual(new, 20_000)                                     # 15% 低于下限，17.5% 非 5 的倍数
        self.assertLess(15_000 * 3, original * 2)

    def test_growth_before_and_after_at_fifty_layers(self):
        layers = 50
        ability3 = {154: (8_000, 10), 0: (5_000, 10)}                    # 能力3 封顶版不动（口径 D4）
        after = [int(row[111]) * layers + ability3[int(row[107])][0] * min(layers, ability3[int(row[107])][1])
                 for row in self.out["leader"][M.CID][6:]]
        self.assertEqual(after, [1_000_000 + 80_000, 1_000_000 + 50_000])  # +1080% / +1050%

    # ---- 能力1 开关

    def test_ability1_appends_one_leader_only_flag2_switch(self):
        old, new = self.live["ability"][M.ABILITY_KEY], self.out["ability"][M.ABILITY_KEY]
        self.assertEqual((len(old), len(new)), (2, 3))
        self.assertEqual(new[:2], old)                                     # 原两行逐字保留
        switch = new[2]
        self.assertEqual({c: v for c, v in enumerate(switch) if v}, M.SWITCH_CELLS)
        self.assertEqual((switch[5], switch[27], switch[47]), ("0", "0", "704"))   # 瞬发、无触发、旗号 2
        self.assertEqual((switch[6], switch[13], switch[16], switch[18]), ("42", "2", "600000", "Green"))
        self.assertEqual(switch[70], M.CAS_SWITCH)
        # c1 与键一致（kitlib.check_ability_key 一键 c1 一致约束；先例凯尔 1399903#4/#5）。
        self.assertEqual([row[1] for row in new], ["false", "false", "false"])

    def test_switch_row_matches_the_live_rolf_precedent_shape(self):
        precedent = DATA["_live_precedent"]["ability:1499866#4"]
        switch = self.out["ability"][M.ABILITY_KEY][2]
        differing = {c for c, (a, b) in enumerate(zip(precedent, switch)) if a != b}
        self.assertEqual(differing, {0, 1, 70})                             # 只差 string_id、c1（随键）与文案键
        self.assertEqual(precedent[47], "704")

    def test_switch_row_reads_back_as_leader_and_resonance_gated_flag2(self):
        rendered = wf_describe.describe_rows(self.out["ability"][M.ABILITY_KEY], "ability")
        self.assertEqual(rendered, [
            "自身 技能槽 50%",
            "风·编成≥6 时: 自身 切换技能形态[change_skill_wind_spgirl_campus_fever]",
            "队长 且 风·编成≥6 时: 自身 切换技能Flag2[change_skill_wind_spgirl_campus_leader]",
        ])

    # ---- 面板与技能描述

    def test_leader_panel(self):
        old = self.live["cas"][M.CAS_LEADER][0][0].split("\n")
        new = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertEqual((len(old), len(new)), (6, 7))
        self.assertEqual(new[:4], old[:4])
        self.assertEqual(old[4], "风属性共鸣时，" + new[4])                 # 第 5 行只删共鸣前缀
        self.assertEqual(old[5], "风属性共鸣时，Fever模式中，每层「星风心得」使风属性角色能力伤害+2.5%、攻击力+2.5%。")
        self.assertEqual(new[5], "Fever模式中，每层「星风心得」使风属性角色能力伤害+20%、攻击力+20%。")
        # 第 7 行是能力1 I704 开关行（前置 仅队长 + 风共鸣）：共鸣是真实条件，保留（主会话口径 2）；
        # 技能强化文案规范：点名技能、与 CAS 同文，去「Fever模式中，」（不是开关行前置）。
        self.assertEqual(new[6], "风属性共鸣时，强化『风中快门·十字双空牙』：技能倍率随「星风心得」层数持续提升。")
        self.assertEqual(new[6], "风属性共鸣时，" + self.out["cas"][M.CAS_SWITCH][0][0] + "。")
        # 数值稿（删前缀之前）：第 6 行 +20%，追加第 7 行。
        self.assertEqual(M.LEADER_LINES_NUMERIC[5], "风属性共鸣时，" + new[5])
        self.assertEqual(M.LEADER_LINES_NUMERIC[6], new[6])
        self.assertEqual(M.LEADER_LINE_ADDED, new[6])

    def test_switch_string(self):
        self.assertEqual(self.out["cas"][M.CAS_SWITCH], [["强化『风中快门·十字双空牙』：技能倍率随「星风心得」层数持续提升"]])
        self.assertEqual(KL.panel_problems(M.SWITCH_TEXT, skill_flag=True), [])
        # 能力1 I536 条目同轮改官方格式（live 原文「强化技能：…（均15秒）」带数字与秒数）。
        self.assertTrue(DATA["_live_cas_flag"]["change_skill_wind_spgirl_campus_fever"][0][0].startswith("强化技能："))
        self.assertEqual(self.out["cas"][M.CAS_FEVER], [[M.FEVER_TEXT]])
        self.assertTrue(M.FEVER_TEXT.startswith("为『风中快门·十字双空牙』追加「"))
        self.assertEqual(KL.panel_problems(M.FEVER_TEXT, skill_flag=True), [])

    def test_skill_flag_entries_follow_the_official_format(self):
        """技能强化文案规范 R2：两条强化条目点名技能、定性不写数字与秒数；面板行 = 「风属性共鸣时，」+ CAS +「。」
        （开关行 I536 / I704 都带风共鸣前置）。删判定反例：CAS 与面板不一致 / 泛称「强化技能」/ 带数字 都要报错。"""
        for cas_key, panel_key, index in ((M.CAS_FEVER, M.CAS_A1, 1), (M.CAS_SWITCH, M.CAS_LEADER, 6)):
            cas_text = self.out["cas"][cas_key][0][0]
            line = self.out["cas"][panel_key][0][0].split("\n")[index].replace(MAIN, "")
            self.assertEqual(line, "风属性共鸣时，" + cas_text + "。", cas_key)
            self.assertIn("『风中快门·十字双空牙』", cas_text)
            self.assertFalse(any(ch.isdigit() for ch in line + cas_text), cas_key)
            for word in ("强化技能", "强化自身技能", "秒", "%", "不受此限"):
                self.assertNotIn(word, line + cas_text, cas_key)
        self.assertEqual(self.out["cas"][M.CAS_A1][0][0].split("\n")[0],
                         self.live["cas"][M.CAS_A1][0][0].split("\n")[0], "能力1 第 1 行逐字")
        entries = M.SKILL_FLAG_ENTRIES
        broken = ((M.CAS_FEVER, "强化技能：全队贯穿", M.CAS_A1, entries[0][3]),) + entries[1:]
        with mock.patch.object(M, "SKILL_FLAG_ENTRIES", broken):
            problems = M.text_problems()
        self.assertTrue(any("must name" in p for p in problems))
        self.assertTrue(any("panel entry of" in p for p in problems))
        numeric = ((M.CAS_FEVER, M.FEVER_TEXT + "（15秒）", M.CAS_A1, entries[0][3]),) + entries[1:]
        with mock.patch.object(M, "SKILL_FLAG_ENTRIES", numeric):
            self.assertTrue(any("numbers" in p for p in M.text_problems()))

    def test_fever_entry_follows_the_flag1_branches(self):
        """旗号 1 条目的数据依据：live 技能两档每个 ConditionalsChangeSkillFlag(1) 关支为空，开支只给
        97 贯穿 + 33[风] 能力伤害（一处）与命中块风属性抗性降低（其余）。删判定反例 ⇒ revise() 拒绝。"""
        for program in M.PROGRAMS.values():
            self.assertEqual(M.fever_entry_problems(self.live["dsl"][program]), [], program)
            self.assertEqual(M.fever_entry_problems(self.out["dsl"][program]), [], program)
        flags = [a for a in M._commands(self.live["dsl"][M.PROGRAMS["1"]])
                 if a[0] == "ConditionalsChangeSkillFlag" and a[1] == 1]
        signatures = [tuple(M._signature(c) for c in M._commands(a[2]) if c[0] in ("FindAllSubjects", "CreateCondition"))
                      for a in flags]
        self.assertEqual(sorted(set(signatures)), sorted(M.FEVER_BRANCH_SIGNATURES))
        self.assertEqual(len(signatures), 25)
        for mutate in (
                lambda t: [a for a in M._commands(t) if a[0] == "CreateCondition" and a[2][0][0] == "ACToleranceOfElement"]
                [0][2][0][3][0].update(min=0.25, max=0.25),                                   # 降低 → 提升
                lambda t: [a for a in M._commands(t) if a[0] == "CreateCondition" and a[2][0][0] == "ACPiercing"]
                [0][2][0].__setitem__(0, "ACFloating"),                                        # 贯穿 → 别的状态
                lambda t: [a for a in M._commands(t) if a[0] == "ConditionalsChangeSkillFlag" and a[1] == 1]
                [0][3][1].append(["Command", ["DoNothing"]])):                               # 关支有内容
            data = deepcopy(self.live)
            for program in M.PROGRAMS.values():
                mutate(data["dsl"][program])
            self.assertTrue(M.fever_entry_problems(data["dsl"][M.PROGRAMS["1"]]))
            patch = {("dsl", program): M.digest(data["dsl"][program]) for program in M.PROGRAMS.values()}
            with self.assertRaisesRegex(ValueError, "flat description rejected"), mock.patch.dict(M.BEFORE, patch):
                M.revise(reader(data))

    def test_panel_texts_obey_the_project_rules(self):
        for key, rows in self.out["cas"].items():
            self.assertEqual((len(rows), len(rows[0])), (1, 1), key)
            text = rows[0][0]
            self.assertNotIn("／", text)
            self.assertNotIn("\\n", text)
            for line in text.split("\n"):
                self.assertEqual(KL.panel_problems(line), [], f"{key}: {line}")
                for word in ("无上限", "无限", "可无限累积", "不设上限", "自身为队长时", "觉醒后", "生命值100%以下",
                             "共鸣时："):
                    self.assertNotIn(word, line)
                # 主位图标只在能力1 / 能力3（主位槽）面板，且逐行都有。
                self.assertEqual(line.startswith(MAIN), key in (M.CAS_A3, M.CAS_A1), f"{key}: {line}")
        for line in (M.LEADER_LINE_ADDED, M.SWITCH_TEXT, M.FEVER_TEXT, M.A1_LINES_AFTER[1]):
            self.assertFalse(any(ch.isdigit() for ch in line), line)      # 技能强化条目不写数字
        self.assertEqual(KL.panel_problems(M.SKILL_DESC), [])
        self.assertEqual(M.text_problems(), [])

    def test_skill_description_stays_the_skill_body_in_all_five_places(self):
        """技能强化文案规范 R3：技能描述只写本体（共鸣且 Fever 中随心得成长、最多10层），不写旗号 2 的「不受此限」；
        5 处 live 原文不改、不返回。删判定反例：live 描述带上强化后的效果 ⇒ revise() 拒绝。"""
        descriptions = [fields[1] for _inner, fields in self.live["action"][M.CODE]]
        descriptions += [self.live[kind][M.CID][0][col] for kind in ("text", "server_text") for col in (5, 7)]
        self.assertEqual(descriptions, [M.SKILL_DESC] * 6)
        self.assertEqual(M.SKILL_DESC, B.NEW_DESC)
        self.assertTrue(M.SKILL_DESC.endswith("每层额外增加10倍（最多10层）。"))
        for word in M.ENHANCED_PHRASES:
            self.assertNotIn(word, M.SKILL_DESC)
        self.assertEqual((self.out["text"], self.out["action"], self.out["server_text"]), ({}, {}, {}))
        data = deepcopy(self.live)
        data["text"][M.CID][0][5] = M.SKILL_DESC.replace("（最多10层）", "（最多10层，担任队长且风属性共鸣时不受此限）")
        with self.assertRaisesRegex(ValueError, "skill description rejected"), \
                mock.patch.dict(M.BEFORE, {("text", M.CID): M.digest(data["text"][M.CID])}):
            M.revise(reader(data))

    # ---- 面板共鸣省略 / 同条件合并

    def test_final_panels_are_verbatim(self):
        for key, lines in FINAL_PANELS.items():
            self.assertEqual(self.out["cas"][key], [["\n".join(lines)]], key)
        # 终稿 = 数值稿（能力2/3 = live）逐行，只在登记行删行首（图标之后）「风属性共鸣时，」，其余字面与行序不变。
        for key, (numeric, drops) in PANEL_DROPS.items():
            final = FINAL_PANELS[key]
            self.assertEqual(len(numeric), len(final), key)
            for number, (before, after) in enumerate(zip(numeric, final), 1):
                icon = MAIN if before.startswith(MAIN) else ""
                want = icon + before[len(icon) + len("风属性共鸣时，"):] if number in drops else before
                self.assertEqual(want, after, f"{key} L{number}")
                if number in drops:
                    self.assertTrue(before[len(icon):].startswith("风属性共鸣时，"), f"{key} L{number}")
        self.assertEqual([self.live["cas"][M.CAS_A2][0][0].split("\n"), self.live["cas"][M.CAS_A3][0][0].split("\n")],
                         [list(M.A2_LINES_BEFORE), list(M.A3_LINES_BEFORE)])
        # 获取行保留共鸣：队长第 4 行、能力3 第 4 / 6 行；开关行保留共鸣：队长第 7 行（口径 2）。
        self.assertTrue(FINAL_PANELS[M.CAS_LEADER][3].startswith("风属性共鸣时，"))
        self.assertTrue(FINAL_PANELS[M.CAS_LEADER][6].startswith("风属性共鸣时，"))
        self.assertNotIn(M.LEADER_SWITCH_LINE, M.LEADER_PREFIX_DROPS)
        self.assertTrue(FINAL_PANELS[M.CAS_A3][3].startswith(MAIN + "风属性共鸣时，"))
        self.assertTrue(FINAL_PANELS[M.CAS_A3][5].startswith(MAIN + "风属性共鸣时，"))

    def test_resonance_omission_basis(self):
        """四个星风状态只由四个 629 授予；调用行都带风共鸣前置；删前缀的行数据依赖这些状态。"""
        tables = {("leader", M.CID): self.out["leader"][M.CID],
                  ("ability", M.ABILITY3_KEY): self.live["ability"][M.ABILITY3_KEY],
                  ("ability", M.ABILITY2_KEY): DATA["_context"]["ability"][M.ABILITY2_KEY]}
        trees = {program: self.live["dsl"][program] for program in M.GRANT_PROGRAMS}
        self.assertEqual([], M.resonance_basis_problems(tables, trees))
        grants = {program.rsplit("$", 1)[1]: M.granted_uniques(tree)
                  for program, tree in trees.items()}
        self.assertEqual({"wind_spgirl_campus_flip_stock": ["14998901", "14998902"],
                          "wind_spgirl_campus_flip_stock_ability": ["14998901", "14998902"],
                          "wind_spgirl_campus_flip_stock_spent": ["14998903"],
                          "wind_spgirl_campus_flip_stock_ability_spent": ["14998904"]}, grants)
        invokers = [(t, k, i) for (t, k, i), _uids in M.GRANT_PROGRAMS.values()]
        self.assertEqual([("leader", M.CID, 4), ("ability", M.ABILITY3_KEY, 4),
                          ("leader", M.CID, 5), ("ability", M.ABILITY3_KEY, 5)], invokers)
        for table, key, index in invokers:
            row = tables[table, key][index]
            self.assertEqual(["Green"], M.resonance_tokens(row, table), (table, key, index))
            rendered = wf_describe.describe_rows([row], TABLE[table])[0]
            self.assertTrue(rendered.startswith("风·编成≥6 且 Fever 时: "), rendered)
        self.assertEqual({"14998901", "14998902", "14998903", "14998904"}, set(M.RESONANCE_OMISSION))
        self.assertTrue(all(v["resonance"] == "Green" for v in M.RESONANCE_OMISSION.values()))
        # 队长第 7 行保留共鸣的依据：数据是能力1 末行 I704 开关（前置 仅队长 + 风属性 6 人共鸣），
        # 技能树旗号 2 开支（Bind 读 DCUnique 14998902）在 ConditionalsUnifyElement(4, 6) 共鸣支内。
        ability1 = self.out["ability"][M.ABILITY_KEY]
        self.assertEqual([], M.resonance_basis_problems({**tables, ("ability", M.ABILITY_KEY): ability1}, trees))
        switch = ability1[-1]
        self.assertEqual(("704", "42", ["Green"]), (switch[47], switch[6], M.resonance_tokens(switch, "ability")))
        for program in M.PROGRAMS.values():
            unify = M.unify_command(self.out["dsl"][program])
            self.assertEqual(unify[:3], ["ConditionalsUnifyElement", 4, 6])
            on = M.growth_branches(self.out["dsl"][program])["on"]
            self.assertIs(unify[3][1][0][1][2], on)                          # 旗号 2 开支在共鸣支内
            self.assertEqual(on[1][0][1][3], ["DCUnique", int(M.GAIN_UID)])
        # 负对照：开关行不再带风共鸣 ⇒ 第 7 行保留共鸣的依据不成立，拒绝。
        unresonant = deepcopy(ability1)
        unresonant[-1][13] = ""
        self.assertTrue(M.resonance_basis_problems({**tables, ("ability", M.ABILITY_KEY): unresonant}, trees))
        # 负对照：任一调用行丢掉风共鸣 / 程序多授予别的状态，revise() 拒绝。
        for kind, key, mutate in (
                ("leader", M.CID, lambda v: v[4].__setitem__(7, "500000")),        # 6 人共鸣 → 5 人
                ("ability", M.ABILITY3_KEY, lambda v: v[5].__setitem__(9, "500000")),
                ("dsl", next(iter(M.GRANT_PROGRAMS)), lambda v: v[11][1][0][1][2][0].__setitem__(1, 14998999))):
            data = deepcopy(self.live)
            mutate(data[kind][key])
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "resonance omission basis"), \
                    mock.patch.dict(M.BEFORE, {(kind, key): M.digest(data[kind][key])}):
                M.revise(reader(data))

    def test_panels_pass_check_merge(self):
        """仓库内校验器 wf_panel_merge_check（硬依赖）。三块面板原文都没有「X属性共鸣时：」，无需口径 3 规范化。"""
        check = check_merge
        for key, (numeric, drops) in PANEL_DROPS.items():
            self.assertFalse(any("共鸣时：" in line for line in numeric), key)
            result = check("\n".join(numeric), self.out["cas"][key][0][0],
                           [dict(line=n, resonance="Green") for n in drops])
            self.assertTrue(result["ok"], (key, result["errors"]))
            self.assertEqual([], result["warnings"], key)
            self.assertEqual({n: "prefix_drop" for n in drops},
                             {n: kind for n, kind in result["columns"][0]["kinds"].items() if kind != "verbatim"}, key)
        # 负对照：未授权删获取行（队长第 4 行）/ 开关行（队长第 7 行）的共鸣会被拒。
        leader_drops = [dict(line=n, resonance="Green") for n in (5, 6)]
        for old in ("风属性共鸣时，Fever模式中，风属性角色发动技能时", "风属性共鸣时，强化『风中快门·十字双空牙』"):
            bad = self.out["cas"][M.CAS_LEADER][0][0].replace(old, old[len("风属性共鸣时，"):])
            self.assertNotEqual(bad, self.out["cas"][M.CAS_LEADER][0][0])
            self.assertFalse(check("\n".join(M.LEADER_LINES_NUMERIC), bad, leader_drops)["ok"], old)

    # ---- DSL

    def test_dsl_off_branch_is_the_live_resonant_branch_verbatim(self):
        for program in M.PROGRAMS.values():
            old, new = self.live["dsl"][program], self.out["dsl"][program]
            branches = M.growth_branches(new)
            old_unify = M.unify_command(old)
            self.assertEqual(branches["off"], old_unify[3])
            self.assertEqual(branches["plain"], old_unify[4])
            self.assertEqual(branches["calm"], old[11][1][1][1][2])
            # 开支 = 关支，只有 Bind 上限不同（值与类型）。
            on = deepcopy(branches["on"])
            self.assertEqual(on[1][0][1][5], 2147483647.0)
            self.assertIsInstance(on[1][0][1][5], float)
            self.assertEqual(branches["off"][1][0][1][5], 10)
            self.assertIsInstance(branches["off"][1][0][1][5], int)
            on[1][0][1][5] = 10
            self.assertEqual(json.dumps(on), json.dumps(branches["off"]))
            # 其余节点逐字：把共鸣支换回原支即还原 live 整树。
            restored = deepcopy(new)
            M.unify_command(restored)[3] = branches["off"]
            self.assertEqual(json.dumps(restored), json.dumps(old))
            self.assertEqual([b[5] for b in binds(new)], [2147483647.0, 10, 0, 0])
        self.assertEqual(self.out["dsl"][M.PROGRAMS["1"]], self.out["dsl"][M.PROGRAMS["2"]])

    def test_dsl_command_counts_grow_by_one_route_and_one_flag(self):
        tree = self.out["dsl"][M.PROGRAMS["1"]]
        route = M.command_counts(M.growth_branches(tree)["off"])
        expected = {name: count + route.get(name, 0) for name, count in M.COUNTS_BEFORE.items()}
        expected["ConditionalsChangeSkillFlag"] += 1
        self.assertEqual(M.command_counts(tree), expected)
        self.assertEqual((expected["FindNearSubjects"], expected["CreateNormalAttack"],
                          expected["BindConditionAccumulationVariable"]), (8, 32, 4))
        flags = [a[1] for a in M._commands(tree) if a[0] == "ConditionalsChangeSkillFlag"]
        self.assertEqual((flags.count(1), flags.count(2)), (33, 1))        # 旗号 1 在两支各一份

    def test_dsl_semantics_uncapped_only_with_flag2_in_resonant_fever(self):
        """倍率 = 75 + 10 × 绑定值；旗号 2（队长且风共鸣）时绑定值 = 层数，否则最多 10；非共鸣 / 非 Fever 为 0。"""
        tree = self.out["dsl"][M.PROGRAMS["2"]]
        for flag2 in (True, False):
            for fever in (True, False):
                for winds in (6, 5):
                    for layers in (0, 1, 10, 11, 50, 2147483647):
                        with self.subTest(flag2=flag2, fever=fever, winds=winds, layers=layers):
                            attacks = reachable_attacks(tree, flag2=flag2, fever=fever, winds=winds,
                                                        layers=layers)
                            self.assertEqual(len(attacks), 8)               # 一条路线：Boss / 回退 × 两种落点 × 2
                            if fever and winds >= 6:
                                bound = layers if flag2 else min(layers, 10)
                            else:
                                bound = 0
                            for attack, scope in attacks:
                                term = attack[6][0]
                                self.assertEqual([v["vid"] for v in term["vlv"]], [M.GAIN_FLOAT_ID])
                                self.assertEqual(scope[M.GAIN_FLOAT_ID], bound)
                                base = term["max"]
                                value = base + sum(v["min"] + (v["max"] - v["min"]) * scope[v["vid"]]
                                                   for v in term["vlv"])
                                self.assertAlmostEqual(value / base, (75 + 10 * bound) / 75, places=9)

    def test_vlv_scope_check_holds_and_catches_a_binding_moved_out_of_scope(self):
        for program, tree in self.out["dsl"].items():
            self.assertEqual(M.unbound_variable_references(tree), [], program)
        self.assertEqual(M.unbound_variable_references(self.live["dsl"][M.PROGRAMS["1"]]), [])
        broken = deepcopy(self.out["dsl"][M.PROGRAMS["1"]])
        on = M.growth_branches(broken)["on"]
        del on[1][0]                                                     # 开支丢掉 Bind，路线仍引用变量
        problems = M.unbound_variable_references(broken)
        self.assertEqual(len(problems), 8)
        self.assertTrue(all("14998905" in p for p in problems))

    def test_dsl_gates_and_amf3_roundtrip(self):
        for program, tree in self.out["dsl"].items():
            self.assertEqual(M.dsl_gate_problems(tree), [], program)
            self.assertEqual(L.action_dsl_element_problems(tree, M.ELEMENT), [])
            self.assertEqual(L.action_dsl_subject_binding_problems(tree), [])
            self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [])
            self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [])
            raw = encode_tree(tree)
            back = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
            self.assertEqual(back, tree)
            self.assertEqual(json.dumps(back), json.dumps(tree))             # float 上限经 AMF3 仍是 float
            self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree)
            # 更严的套件门禁：不得新增问题（live 既有「主体绑定号重复」集合不变）。
            self.assertEqual(kit_dsl_problems(tree, element=M.ELEMENT),
                             kit_dsl_problems(self.live["dsl"][program], element=M.ELEMENT), program)

    # ---- 合法性

    def test_native_legality_gates_are_empty(self):
        live_cas = DATA["_live_cas_invoke"]
        self.assertEqual(set(live_cas), set(M.INVOKE_STRING_KEYS))
        self.assertTrue(all(rows and rows[0][0] for rows in live_cas.values()))
        for kind in ("ability", "leader"):
            table = TABLE[kind]
            for key, rows in self.out[kind].items():
                for index, row in enumerate(rows):
                    label = f"{kind}:{key}#{index}"
                    self.assertEqual(L.client_legality_problems(table, row), [], label)
                    self.assertEqual(L.declared_block_field_problems(table, row), [], label)
                    self.assertEqual(L.invoke_skill_string_problems(row, set(live_cas), kind=table), [], label)
                    self.assertEqual(L.ability_element_column_problems(table, row, M.ELEMENT), [], label)
                    self.assertEqual(M.row_gate_problems(table, row), [], label)
        strings = set(self.out["cas"]) | set(DATA["_live_cas_flag"])
        self.assertEqual(M.switch_string_problems(self.out["ability"][M.ABILITY_KEY], strings), [])
        self.assertEqual(M.switch_string_problems(self.out["ability"][M.ABILITY_KEY], set(DATA["_live_cas_flag"])),
                         [f"ability#2 c70 {M.CAS_SWITCH!r} missing from custom_ability_string"])

    def test_required_capabilities_match_the_module_declaration(self):
        caps = M.required_capabilities(self.out["ability"][M.ABILITY_KEY], self.out["leader"][M.CID],
                                       self.out["cas"])
        self.assertEqual(caps, sorted(M.CAPABILITIES))
        self.assertEqual([c for row in self.out["ability"][M.ABILITY_KEY]
                          for c in L.required_client_capabilities("ability", row)], [])

    # ---- fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["ability"][M.ABILITY_KEY][0][1] = "mutated"
        out["leader"][M.CID][6][111] = "mutated"
        out["cas"][M.CAS_LEADER][0][0] = "mutated"
        out["cas"][M.CAS_A3][0][0] = "mutated"
        out["cas"][M.CAS_A1][0][0] = "mutated"
        out["cas"][M.CAS_FEVER][0][0] = "mutated"
        M.growth_branches(out["dsl"][M.PROGRAMS["1"]])["off"][1][0][1][5] = 99
        self.assertEqual(data, self.live)

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            data = deepcopy(self.live)
            value = data[kind][key]
            if kind == "dsl":
                value[10] = 4
            elif kind == "action":
                value[0][1][1] += "。"
            else:
                value[-1][-1] += "x"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))

    def test_new_key_already_in_live_is_rejected(self):
        data = deepcopy(self.live)
        data["cas"][M.CAS_SWITCH] = [["已存在"]]
        with self.assertRaisesRegex(ValueError, "new key already exists"):
            M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        data = deepcopy(self.live)
        for kind in ("ability", "leader", "cas", "text", "server_text", "action", "dsl"):
            data[kind].update(deepcopy(self.out[kind]))
        with self.assertRaises(ValueError):
            M.revise(reader(data))
        with self.assertRaises(ValueError):
            M.leader_rows(self.out["leader"][M.CID])
        with self.assertRaises(ValueError):
            M.ability1_rows(self.out["ability"][M.ABILITY_KEY])
        with self.assertRaises(ValueError):
            M.leader_text(self.out["cas"][M.CAS_LEADER])
        with self.assertRaises(ValueError):
            M.leader_text([["\n".join(M.LEADER_LINES_NUMERIC)]])           # 数值稿同样拒绝
        with self.assertRaises(ValueError):
            M.a2_text(self.out["cas"][M.CAS_A2])
        with self.assertRaises(ValueError):
            M.a3_text(self.out["cas"][M.CAS_A3])
        for level, program in M.PROGRAMS.items():
            with self.assertRaises(ValueError):
                M.revise_tree(self.out["dsl"][program], level)
        with self.assertRaises(ValueError):
            M.a1_text(self.out["cas"][M.CAS_A1])
        with self.assertRaises(ValueError):
            M.fever_text(self.out["cas"][M.CAS_FEVER])

    def test_row_locators_are_content_based(self):
        leader = deepcopy(self.live["leader"][M.CID])
        swapped = leader[:6] + [leader[7], leader[6]]
        with self.assertRaises(ValueError):
            M.leader_rows(swapped)
        drifted = deepcopy(leader)
        drifted[6][111] = drifted[6][112] = "5000"
        with self.assertRaises(ValueError):
            M.leader_rows(drifted)
        ability = deepcopy(self.live["ability"][M.ABILITY_KEY])
        ability[1][70] = "change_skill_other"
        with self.assertRaises(ValueError):
            M.ability1_rows(ability)
        tree = deepcopy(self.live["dsl"][M.PROGRAMS["1"]])
        binds(tree)[0][5] = 10.0                                         # 类型不符也拒绝
        with self.assertRaises(ValueError):
            M.revise_tree(tree, "1")
        tree = deepcopy(self.live["dsl"][M.PROGRAMS["1"]])
        binds(tree)[1][5] = 3                                            # 非共鸣支上限不再是 0
        with self.assertRaises(ValueError):
            M.revise_tree(tree, "1")


class GeneratorSyncTests(unittest.TestCase):
    """生成器重跑不能回退本轮改动：纯函数 / 完整装配输出 == revise() 输出。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_panel_generator_equals_revise_output(self):
        texts = P.panel_descriptions(M.CID)
        self.assertEqual([[texts["leader"]]], self.out["cas"][M.CAS_LEADER])
        self.assertEqual([[texts["a2"]]], self.out["cas"][M.CAS_A2])
        self.assertEqual([[texts["a3"]]], self.out["cas"][M.CAS_A3])
        self.assertEqual([[texts["a1"]]], self.out["cas"][M.CAS_A1])
        self.assertEqual(P.active_description(M.CID), M.SKILL_DESC)
        self.assertNotIn(M.CAS_SWITCH, P.native_flat_string_rows(M.CID))   # 平表文案只由能力生成器给出
        # 旗号 1 条目：装配时 native_flat_string_rows 覆盖 wf_celtie_fever_abilities 的旧平表文案（后者在前）。
        self.assertEqual(P.native_flat_string_rows(M.CID)[M.CAS_FEVER], self.out["cas"][M.CAS_FEVER])

    def test_ability_generator_equals_revise_output_on_fixture_donors(self):
        import test_celtie_fever_abilities as fixture
        built = A.ability_rows(fixture.official_sources())[M.ABILITY_KEY]
        self.assertEqual(built[2], self.out["ability"][M.ABILITY_KEY][2])
        self.assertEqual([row[47] for row in built], ["211", "536", "704"])
        self.assertEqual(A.flat_string_rows()[M.CAS_SWITCH], self.out["cas"][M.CAS_SWITCH])
        self.assertEqual(A.LEADER_UNCAP_STRING_ID, M.CAS_SWITCH)

    def test_leader_generator_equals_revise_output_on_fixture_donors(self):
        import test_celtie_fever_leader as fixture
        case = fixture.CeltieFeverLeaderTest()
        case.setUp()
        self.assertEqual(case.rows[6:], self.out["leader"][M.CID][6:])
        self.assertEqual(LD.GAIN_GROWTH_STRENGTH, {154: 20_000, 0: 20_000})

    def test_skill_growth_generator_equals_revise_output_on_the_live_tree(self):
        self.assertEqual((G.LEADER_FLAG, G.LEADER_MAX_LAYERS, G.GAIN_MAX_LAYERS),
                         (M.LEADER_FLAG, M.UNCAPPED_LAYERS, M.CAPPED_LAYERS))
        for program in M.PROGRAMS.values():
            grown = G.with_leader_uncapped_growth(self.live["dsl"][program])
            self.assertEqual(json.dumps(grown), json.dumps(self.out["dsl"][program]), program)
            with self.assertRaises(ValueError):
                G.with_leader_uncapped_growth(self.out["dsl"][program])      # 生成器同样不重复包裹

    @unittest.skipUnless((ROOT / ".cdn/cn").is_dir() and (ROOT / "mod-tools/profiles.json").is_file(),
                         "需要 .cdn/cn 官方基线")
    def test_full_generator_assembly_equals_revise_output(self):
        import wf_mod_tool as core
        import wf_celtie_fever_skill as S
        from wf_enhancement_policy import OfficialBaseline
        baseline = OfficialBaseline(ROOT / ".cdn/cn", cache_dir=ROOT / "mod-tools/work/official-baseline",
                                    write_cache=False)

        def official(logical):
            digest = core.sha1_path(logical)
            raw = baseline.get("common", digest[:2] + "/" + digest[2:])
            if raw is None:
                raise KeyError(logical)
            return raw

        def rows(logical):
            return {k: core.read_csv_lines(t)
                    for k, t in core.read_orderedmap_file_from_bytes(official(logical)).items()}
        ability = rows("master/ability/ability.orderedmap")
        leaders = rows("master/ability/leader_ability.orderedmap")
        built = A.ability_rows(ability)
        self.assertEqual(built[M.ABILITY_KEY], self.out["ability"][M.ABILITY_KEY])
        led = LD.leader_rows(ability, leaders)
        self.assertEqual(led, self.out["leader"][M.CID])
        overrides = P.override_string_rows(M.CID, built, led)
        for key in (M.CAS_LEADER, M.CAS_A2, M.CAS_A3, M.CAS_A1):
            self.assertEqual(overrides[key], self.out["cas"][key], key)
        strings = {**A.flat_string_rows(), **LD.flat_string_rows(), **P.native_flat_string_rows(M.CID)}
        self.assertEqual(strings[M.CAS_SWITCH], self.out["cas"][M.CAS_SWITCH])
        self.assertEqual(strings[M.CAS_FEVER], self.out["cas"][M.CAS_FEVER])
        for level, program in M.PROGRAMS.items():
            tree = S.build_skill(int(level), official)
            self.assertEqual(json.dumps(tree), json.dumps(self.out["dsl"][program]), program)


class CandidateTests(unittest.TestCase):
    @unittest.skipUnless((WORKSPACE / "package/manifest.json").is_file()
                         and (ROOT / "mod-tools/profiles.json").is_file(),
                         "local candidate workspace required")
    def test_candidate_matches_live_before_and_revise_output_after_writeback(self):
        from wf_character_revision import RevisionCandidate
        import wf_share_update_codec as X
        import wf_mod_tool as core
        manifest = WORKSPACE / "package/manifest.json"
        before = manifest.read_bytes()
        current = json.loads(before)["package_version"]
        target = M.PACKAGE_VERSION[M.PACKAGES[0]]
        if as_tuple(current) > as_tuple(target):
            self.skipTest(f"candidate advanced past batch 3 ({current})")
        candidate = RevisionCandidate(ROOT, WORKSPACE, character_id=M.CID, code_name=M.CODE,
                                      package_version=target, snapshot_key="revision_20260927c",
                                      reviewed_input_drift=M.REVIEWED_DRIFT,
                                      baseline_factory=lambda *a, **k: None)
        out = M.revise(reader(load_fixture()))
        live = load_fixture()
        want = out if current == target else live      # 回写后 = 本轮输出；回写前 = live（第二批已回写）
        ability = X.unpack(candidate.read("common", "master/ability/ability.orderedmap"))
        leader = X.unpack(candidate.read("common", "master/ability/leader_ability.orderedmap"))
        cas = X.unpack(candidate.read("common", "master/string/custom_ability_string.orderedmap"))
        text = X.unpack(candidate.read("common", "master/character/character_text.orderedmap"))
        actions = X.unpack(candidate.read("common", "master/skill/action_skill.orderedmap"))
        server = json.loads(candidate.read("server", "cdndata/character_text.json"))
        self.assertEqual(X.csv_read(leader[M.CID]), want["leader"][M.CID])
        self.assertEqual(X.csv_read(cas[M.CAS_LEADER]), want["cas"][M.CAS_LEADER])
        for key in (M.CAS_A2, M.CAS_A3, M.CAS_A1, M.CAS_FEVER):
            self.assertEqual(X.csv_read(cas[key]), want["cas"][key], key)
        # 技能描述本轮不改：回写前后候选都 == live。
        self.assertEqual(X.csv_read(text[M.CID]), live["text"][M.CID])
        self.assertEqual(server[M.CID], live["server_text"][M.CID])
        self.assertEqual([(inner, list(fields)) for inner, fields in live["action"][M.CODE]],
                         [(inner, list(fields)) for inner, fields in core.decode_action_skill_row(actions[M.CODE])])
        for program in M.PROGRAMS.values():
            raw = candidate.read("common", wf_dsl.dsl_logical(program))
            self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"], want["dsl"][program], program)
        if current == target:
            self.assertEqual(X.csv_read(ability[M.ABILITY_KEY]), out["ability"][M.ABILITY_KEY])
            self.assertEqual(X.csv_read(cas[M.CAS_SWITCH]), out["cas"][M.CAS_SWITCH])
        else:
            self.assertLess(as_tuple(current), as_tuple(target))
            self.assertNotIn(M.CAS_SWITCH, cas)
            # 既有漂移（notes.candidate_preexisting_drift）：候选能力1 仍是初版 2 行。
            self.assertNotEqual(X.csv_read(ability[M.ABILITY_KEY]), live["ability"][M.ABILITY_KEY])
            self.assertEqual(len(X.csv_read(ability[M.ABILITY_KEY])), 2)
            self.assertIn(f"ability:{M.ABILITY_KEY}", out["notes"]["candidate_preexisting_drift"])
        self.assertEqual(before, manifest.read_bytes())


if __name__ == "__main__":
    unittest.main()
