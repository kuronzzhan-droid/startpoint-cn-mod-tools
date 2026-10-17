"""雷吉斯 139994 · 2026-09-27 平衡第三轮（c：成长复核 4/5 + 技能倍率撤封顶）的修订模块回归。

fixture = live 1.4.1053（链尾；= 第二批输出 = s7-regis 1.0.8）只读快照。逐项断言：队长四条逐层成长 = 原值 4/5、
队长追加的 536 旗号 1 行（与 live 杰拉德 / 官方 dryad_hw23 同形）、旗号 1 空闲、≥5 层档按旗号分两支（关支 == live、
开支只差 Bind 上限 99.0）、光束倍率随层数（开旗号不封顶、关旗号 5 层封顶）、未改行/节点逐字保留、面板与强化条目
（点名『浪花爆破』）、技能描述 5 处保持第二批且不返回（强化后效果只写在队长面板，主会话 2026-09-27 口径 R3）、
BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、合法性与 DSL 门禁（含 vlv 作用域），以及 kit
（wf_seasonal7_kit_regis）按「浪涌 → 第一批 → 第二批 → 第三轮」重跑与 revise() 一致。
暂存前最后一轮：队长面板「非FEVER / FEVER 冲刺时 FEVER槽」一行按数据条件拆两行（口径 5 扩展，能力 6 #1/#2 前置 2 不同）
及其依据（fail closed），返回面板扫共鸣冒号、全角「／」与半角「/」。
"""
from __future__ import annotations

import inspect
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927_regis as B1  # noqa: E402
import wf_balance_20260927b_regis as B2  # noqa: E402
import wf_balance_20260927c_regis as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_regis_surge_stages as R  # noqa: E402
import wf_seasonal7_kit_regis as K  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402
from wf_seasonal7_kit_philia import cmds, dsl_gates  # noqa: E402

HERE = Path(__file__).resolve().parent
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927c_regis.json'
B2_FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_regis.json'
B1_FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927_regis.json'
SURGE_FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'surge_anchor_before.json'
ROOT = HERE.parents[1]
L1, L2 = M.SKILL_PROGRAMS["1"], M.SKILL_PROGRAMS["2"]
CHAR = "master/character/character.orderedmap"
MANIFEST_CAPS = {"kyubi-fever-ratio-v1", "panel-description-override-v2"}
#: 主会话数值表：行号 → (第二批 live 值, 第二批改前原值, 本次 = 原值 4/5 取 5% 倍数)。
TABLE = {0: ("30000", "150000", "120000"),     # 雷队技能伤害（雷共鸣）
         1: ("20000", "100000", "80000"),      # 雷队攻击力（雷共鸣）
         7: ("30000", "150000", "120000"),     # 自身攻击力
         8: ("30000", "150000", "120000")}     # 自身技能伤害
LINE0 = "雷属性共鸣时，每层「浪涌充能」，雷属性角色技能伤害＋120%、攻击力＋80%"
LINE1 = "每层「浪涌充能」，自身攻击力＋120%、技能伤害＋120%"
FLAG_LINE = "雷属性共鸣时，强化『浪花爆破』：光束威力随「浪涌充能」层数持续提升"
#: 口径 5（主会话扩展 B）：第二批队长面板里「；」挤两种数据条件的那一行 → 拆后两行。
SPLIT_BEFORE = "雷属性共鸣时，非FEVER模式中冲刺时FEVER槽＋10%；FEVER模式中冲刺时FEVER槽－10%"
SPLIT_AFTER = ("雷属性共鸣时，非FEVER模式中冲刺时FEVER槽＋10%", "雷属性共鸣时，FEVER模式中冲刺时FEVER槽－10%")
FLAG_TEXT = "强化『浪花爆破』：光束威力随「浪涌充能」层数持续提升"
#: 技能描述只写技能本体（主会话 2026-09-27 口径 R3）：保持第二批原文（本体上限「（最多5层）」照写，不写强化后的不封顶）。
DESCRIPTION = ("向最近的敌人发射光束，造成雷属性伤害／「浪涌充能」达到3层、5层时提升光束形态，基础威力依次为50、75、100倍，"
               "每层额外＋15倍（最多5层）／非FEVER模式中，增加FEVER槽并提升自身攻击力"
               "／提升雷属性角色技能伤害")
FORBIDDEN = ("可无限", "无上限", "无限叠加", "不设上限", "自身为队长时", "觉醒后", "生命值100%以下")


def load(path=FIXTURE, section="reads"):
    fx = json.loads(path.read_bytes())
    return {(kind, tuple(key) if isinstance(key, list) else key): value for kind, key, value in fx[section]}


def reader(data):
    return lambda kind, key: data[kind, key]


def beam_total(tree, stacks: int, flag: bool) -> float:
    """按客户端语义求某层数下命中那一档光束 10 段合计倍率：ConditionalsConditionAccumulationNumber 选档；
    ConditionalsChangeSkillFlag(1) 按旗号取开/关支；var = min(层数/除数, 上限)；vlv = min + (max−min)×var。"""
    branch = tree[11][1][1]
    while branch[0] == "Command":
        c = branch[1]
        branch = c[3] if stacks >= c[2] else c[4]
    if len(branch[1]) == 1 and branch[1][0][1][0] == "ConditionalsChangeSkillFlag":
        flag_cmd = branch[1][0][1]
        branch = flag_cmd[2] if flag else flag_cmd[3]
    bind, = cmds(branch, "BindConditionAccumulationVariable")
    attack, = cmds(branch, "CreateNormalAttack")
    area, = cmds(branch, "CreateHitArea")
    cell = attack[6][0]
    var = min(stacks / bind[4], bind[5])
    vlv = cell["vlv"][0]
    return area[14][1] * (cell["max"] + vlv["min"] + (vlv["max"] - vlv["min"]) * var)


def bound_ids_by_branch(tree):
    """旗号开/关两支各自的主体绑定号（philia ``bound_ids`` 同口径）与整树的绑定号。"""
    import wf_seasonal7_kit_philia as P
    flag, = M.flag_nodes(tree)
    return P.bound_ids(flag[2]), P.bound_ids(flag[3]), P.bound_ids(tree)


class ReviseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.context = load(section="context")
        cls.out = M.revise(reader(cls.data))

    def live(self, kind, key):
        return deepcopy(self.data[kind, key])

    def assertOnly(self, before, after, cells):
        restored = deepcopy(after)
        for col, value in cells.items():
            restored[col] = value
        self.assertEqual(before, restored)

    # ---------------------------------------------------------------- 成长行
    def test_growth_rows_are_four_fifths_of_the_original(self):
        before, after = self.live("leader", M.CID), self.out["leader"][M.CID]
        self.assertEqual((9, 10), (len(before), len(after)))
        for row, (live_value, _original, new) in TABLE.items():
            self.assertEqual([live_value] * 2, before[row][111:113], row)
            self.assertEqual([new] * 2, after[row][111:113], row)
            self.assertEqual(0, int(new) % 5000, row)                          # 5% 的倍数
            self.assertOnly(before[row], after[row], {111: live_value, 112: live_value})
            self.assertEqual(("134", "(None)", M.UID), (after[row][95], after[row][100], after[row][102]))
        self.assertEqual(before[2:7], after[2:7])                              # 充能 / Fever 时间 / 461 行逐字保留
        self.assertEqual({row: new for row, (_l, _o, new) in TABLE.items()}, M.NEW_VALUES)
        self.assertEqual({row: live for row, (live, _o, _n) in TABLE.items()}, M.BATCH2_VALUES)

    def test_original_values_cross_checked_against_pre_batch2_live(self):
        """「原值」对第二批改前 live（1.4.1049 夹具）独立核对：队长 #0/#1 c111/c112、能力 3#3/#4 c113/c114。"""
        b2 = load(B2_FIXTURE)
        leader, third = b2["leader", M.CID], b2["ability", B2.THIRD_KEY]
        originals = {0: leader[0][111:113], 1: leader[1][111:113], 7: third[3][113:115], 8: third[4][113:115]}
        for row, (_live, original, new) in TABLE.items():
            self.assertEqual([original] * 2, originals[row], row)
            self.assertEqual(new, str(int(original) * 4 // 5), row)            # 已是 5% 的倍数，无需取整
            self.assertEqual(new, M.scaled(original), row)
        self.assertEqual({row: o for row, (_l, o, _n) in TABLE.items()}, M.ORIGINAL_VALUES)
        # 取整规则：就近取 5% 的倍数（36→35、39→40 的作者例子）
        self.assertEqual(("35000", "40000"), (M.scaled("45000"), M.scaled("48750")))

    def test_described_rows(self):
        described = wf_describe.describe_rows(self.out["leader"][M.CID], "leader_ability")
        self.assertEqual("雷·编成≥6 时: 持续·状态累积计数固有≥1[固有13999401] → 赋予全队(雷) 技能伤害 120%", described[0])
        self.assertEqual("雷·编成≥6 时: 持续·状态累积计数固有≥1[固有13999401] → 赋予全队(雷) 攻击力 80%", described[1])
        self.assertEqual("持续·状态累积计数固有≥1[固有13999401] → 自身 攻击力 120%", described[7])
        self.assertEqual("持续·状态累积计数固有≥1[固有13999401] → 自身 技能伤害 120%", described[8])
        self.assertEqual(f"雷·编成≥6 时: 自身 切换技能形态[{M.FLAG_KEY}]", described[9])
        before = wf_describe.describe_rows(self.live("leader", M.CID), "leader_ability")
        self.assertEqual(before[2:7], described[2:7])

    def test_after_fingerprints(self):
        leader = self.out["leader"][M.CID]
        for row in M.GROWTH_ROWS:
            self.assertTrue(B2._matches(leader[row], M.LEADER_NCOLS, M.ROWS_AFTER[row]), row)
            self.assertFalse(B2._matches(leader[row], M.LEADER_NCOLS, M.ROWS_BEFORE[row]), row)
        self.assertTrue(B2._matches(leader[M.FLAG_ROW], M.LEADER_NCOLS, M.FLAG_ROW_CELLS))
        self.assertEqual((0, 1, 7, 8), M.GROWTH_ROWS)

    # ---------------------------------------------------------------- 536 旗号行
    def test_flag_row_matches_precedents(self):
        """与 live 杰拉德 149999#11、官方 dryad_hw23 121189#2 逐格同形，只差 c0 / 共鸣颜色 / 文案键。"""
        row = self.out["leader"][M.CID][M.FLAG_ROW]
        self.assertEqual(M.flag_row(), row)
        self.assertEqual(M.FLAG_ROW, len(self.live("leader", M.CID)))           # 追加在末尾
        for key in ("leader:149999#11", "leader:121189#2"):
            precedent = self.context["precedent", key]
            self.assertEqual("536", precedent[45], key)
            diff = [c for c in range(M.LEADER_NCOLS) if precedent[c] != row[c]]
            self.assertEqual(list(M.FLAG_ROW_PRECEDENT_DIFF), diff, key)
        self.assertEqual((M.CODE, "0", "0", "2", "600000", "600000", "Yellow", "0", "536", M.FLAG_KEY),
                         (row[0], row[3], row[25], row[4], row[7], row[8], row[9], row[44], row[45], row[68]))
        self.assertTrue(M.FLAG_KEY.startswith("change_skill_" + M.CODE))       # RevisionCandidate 命名空间

    def test_flag_one_is_free_and_only_the_new_row_opens_it(self):
        leader = self.out["leader"][M.CID]
        self.assertEqual([M.FLAG_ROW], M.flag_rows_in("leader_ability", leader))
        for key in M.ABILITY_KEYS:
            self.assertEqual([], M.flag_rows_in("ability", self.live("ability", key)), key)
        self.assertEqual("1", self.context["table", (CHAR, M.CID)][0][9])       # c9=1：语音路由不读旗号
        for _inner, fields in self.live("action", M.CODE):
            self.assertEqual("(None)", fields[16])                              # 自动施放不按旗号改条件
        ability = {key: self.live("ability", key) for key in M.ABILITY_KEYS}
        ability[M.CID + "1"][0][47] = "536"                                     # 有人先在能力里开了旗号 1
        with self.assertRaisesRegex(ValueError, "not free"):
            M.leader_rows(self.live("leader", M.CID), ability)
        leader = self.live("leader", M.CID)
        leader[3][45] = "704"                                                   # 队长既有行已切旗号
        with self.assertRaisesRegex(ValueError, "not free"):
            M.leader_rows(leader)

    def test_row_legality_and_capabilities(self):
        caps = set()
        for row in self.out["leader"][M.CID]:
            self.assertEqual([], L.client_legality_problems("leader_ability", row))
            self.assertEqual([], L.declared_block_field_problems("leader_ability", row))
            self.assertEqual([], L.invoke_skill_string_problems(row, {B1.STRIKE_KEY}, "leader_ability"))
            caps.update(L.required_client_capabilities("leader_ability", row))
        self.assertLessEqual(caps, MANIFEST_CAPS)
        self.assertEqual([], M.CAPABILITIES)
        self.assertEqual([], M.row_problems(self.out["leader"][M.CID]))
        self.assertIn(M.FLAG_KEY, self.out["cas"])                              # c68 文案键同批写进 cas
        bad = deepcopy(self.out["leader"][M.CID])
        bad[M.FLAG_ROW][68] = "desc_other"
        self.assertTrue(M.row_problems(bad))

    # ---------------------------------------------------------------- DSL
    def test_only_the_top_stage_is_split_by_flag_one(self):
        for program in (L1, L2):
            before, after = self.live("dsl", program), self.out["dsl"][program]
            self.assertEqual(before, M.unwrap(after))                          # 关支 == live 原段，其余节点逐字不变
            flag, = M.flag_nodes(after)
            self.assertEqual(1, flag[1])
            live_body = M.top_branch(before)[1]
            on, off = flag[2], flag[3]
            self.assertEqual(["Block", live_body], off)
            expect_on = deepcopy(live_body)
            expect_on[0][1][5] = 99.0
            self.assertEqual(["Block", expect_on], on)
            self.assertIs(float, type(on[1][0][1][5]))                          # double（第二批改前逐字）
            self.assertEqual([5.0], [b[5] for b in B2.binds(off)])
            caps = sorted(b[5] for b in B2.binds(after))
            self.assertEqual([5.0, 5.0, 5.0, 99.0], caps)                     # 3–4 / 0–2 层档仍 5.0
            self.assertEqual([], M.flag_nodes(before))

    def test_beam_multiplier_by_stacks_and_flag(self):
        """关旗号 = 第二批（≥5 层 175 倍封顶）；开旗号 = 第二批改前（每层 +15 倍不封顶）；低两档不受旗号影响。"""
        for program in (L1, L2):
            before, after = self.live("dsl", program), self.out["dsl"][program]
            for stacks, low in ((0, 50), (2, 80), (3, 120), (4, 135)):
                for flag in (False, True):
                    self.assertAlmostEqual(low, beam_total(after, stacks, flag), places=6)
            for stacks, off, on in ((5, 175, 175), (6, 175, 190), (12, 175, 280), (16, 175, 340), (99, 175, 1585)):
                self.assertAlmostEqual(off, beam_total(after, stacks, False), places=6, msg=(program, stacks))
                self.assertAlmostEqual(on, beam_total(after, stacks, True), places=6, msg=(program, stacks))
                self.assertAlmostEqual(off, beam_total(before, stacks, False), places=6)   # live = 关支

    def test_dsl_gates_are_clean(self):
        for program, tree in self.out["dsl"].items():
            encode_tree(tree)
            self.assertEqual([], M.dsl_problems(tree), program)
            self.assertEqual([], L.action_dsl_element_problems(tree, 2), program)
            self.assertEqual([], L.action_dsl_subject_binding_problems(tree), program)
            self.assertEqual([], L.action_dsl_lookup_scope_problems(tree), program)
            self.assertEqual([], L.action_dsl_hit_area_target_problems(tree), program)
            self.assertEqual([], M.vlv_scope_problems(tree), program)

    def test_philia_gates_only_flag_the_cross_branch_binding_reuse(self):
        """philia dsl_gates 的 dup_bind_ids 不分支：两支复用同一组绑定号（设计做法 A，live 杰拉德先例）会被它列出。
        这里断言：除 dup_bind_ids 外全空，且重复的恰好是旗号两支各绑一次的那组号（支内无重复，支外不复用）。"""
        for program, tree in self.out["dsl"].items():
            gates = dsl_gates(tree, element=2)
            others = {k: gates[k] for k in ("legality_subject", "legality_hit_target", "legality_element",
                                            "player_side", "scope_strict", "signature", "expr_tags")}
            self.assertEqual({k: [] for k in others}, others, program)
            self.assertTrue(gates["roundtrip"] and gates["head_ok"] and not gates["wrapper"])
            on, off, whole = bound_ids_by_branch(tree)
            self.assertEqual(sorted(on), sorted(off))
            self.assertEqual(len(on), len(set(on)))                           # 支内无重复
            outside = list(whole)
            for x in on + off:
                outside.remove(x)
            self.assertFalse(set(outside) & set(on), program)                  # 支外不复用支内的号
            self.assertEqual(sorted({x for x in on if x in off}), gates["dup_bind_ids"])

    def test_kit_blueprint_check_counts_flag_branches_separately(self):
        path = ROOT / K.OFFICIAL_SIG_REL
        if not path.is_file():
            self.skipTest("official DSL signature table (gitignored work/) absent")
        sig = K.load_official_sig(ROOT)
        for program, tree in self.out["dsl"].items():
            self.assertEqual([], K.blueprint_check_with_sig(tree, sig)[0], program)
            checks = K.dsl_problems(ROOT, tree)
            self.assertTrue(checks["all_empty"] and checks["roundtrip"], checks)
        tree = deepcopy(self.out["dsl"][L1])                                   # 负向：支内重复仍要报
        flag, = M.flag_nodes(tree)
        flag[2][1].append(deepcopy(flag[2][1][1]))
        self.assertTrue(any("绑定 id 重复" in p for p in K.blueprint_check_with_sig(tree, sig)[0]))
        tree = deepcopy(self.out["dsl"][L1])                                   # 负向：支外复用仍要报
        tree[11][1].append(deepcopy(M.flag_nodes(tree)[0][2][1][1]))
        self.assertTrue(any("绑定 id 重复" in p for p in K.blueprint_check_with_sig(tree, sig)[0]))

    def test_vlv_scope_negative_control(self):
        """只把 Bind 放进分支、光束留在分支外 ⇒ 光束的 vlv 读不到变量 1，必须报错。"""
        tree = deepcopy(self.out["dsl"][L1])
        block = M.top_branch(tree)
        flag = block[1][0]
        beam = flag[1][2][1].pop()                                             # 开支的 FindNearSubjects 挪出去
        flag[1][3][1].pop()
        block[1].append(beam)
        probs = M.vlv_scope_problems(tree)
        self.assertTrue(probs)
        self.assertTrue(all("vid 1" in p for p in probs), probs)
        self.assertEqual([], M.vlv_scope_problems(self.live("dsl", L1)))

    # ---------------------------------------------------------------- 文案
    def test_descriptions_five_places_stay_batch2(self):
        """口径 R3：技能描述只写技能本体——强化后的不封顶只在队长面板强化条目里写 ⇒ 5 处保持第二批原文、不返回。"""
        self.assertEqual(DESCRIPTION, M.DESCRIPTION)
        self.assertEqual(B2.DESCRIPTION, M.DESCRIPTION)
        self.assertEqual(1, M.DESCRIPTION.count("（最多5层）"))                # 技能本体（关支 5.0）上限照写
        for mark in ("不受此限", "担任队长", "强化后", "共鸣"):
            self.assertNotIn(mark, M.DESCRIPTION)
        for kind in ("text", "server_text"):
            before = self.live(kind, M.CID)
            self.assertEqual([B2.DESCRIPTION] * 2, [before[0][5], before[0][7]])
            self.assertEqual(before, M.text_rows(before))
            self.assertEqual({}, self.out[kind])
        action_before = [(k, list(v)) for k, v in self.live("action", M.CODE)]
        for _k, fields in action_before:
            self.assertEqual(B2.DESCRIPTION, fields[1])
        self.assertEqual(action_before, [(k, list(v)) for k, v in M.action_rows(self.live("action", M.CODE))])
        self.assertEqual({}, self.out["action"])
        self.assertEqual([], K.skill_desc_coverage_problems([self.out["dsl"][p] for p in (L1, L2)], M.DESCRIPTION))
        self.assertEqual([], K.panel_text_problems(M.DESCRIPTION))
        self.assertEqual([], KL.panel_problems(M.DESCRIPTION))

    def test_flag_text_names_the_skill(self):
        """口径 R2：强化条目用官方格式点名技能（技能名 = action_skill 第 1 档 c0），不写「强化自身技能」。"""
        self.assertEqual(self.live("action", M.CODE)[0][1][0], M.SKILL_NAME)
        self.assertTrue(FLAG_TEXT.startswith(f"强化『{M.SKILL_NAME}』："))
        for text in (FLAG_TEXT, M.PANEL_AFTER):
            self.assertNotIn("强化自身技能", text)
        data = deepcopy(self.data)
        data["action", M.CODE][0][1][0] = "别的技能"
        with self.assertRaises(ValueError):
            M.revise(reader(data))

    def test_leader_panel_text(self):
        old = self.live("cas", M.PANEL_LEADER)[0][0].split("\n")
        text = self.out["cas"][M.PANEL_LEADER][0][0]
        new = text.split("\n")
        self.assertEqual((7, 9), (len(old), len(new)))                         # + 旗号行 + 口径 5 拆出的一行
        self.assertEqual("雷属性共鸣时，每层「浪涌充能」，雷属性角色技能伤害＋30%、攻击力＋20%", old[0])
        self.assertEqual("每层「浪涌充能」，自身攻击力＋30%、技能伤害＋30%", old[1])
        self.assertEqual([LINE0, LINE1, FLAG_LINE], new[:3])
        self.assertEqual(old[2:5], new[3:6])                                   # 充能 / Fever 时间 / 进 Fever 三行逐字
        self.assertEqual(SPLIT_BEFORE, old[5])
        self.assertEqual(list(SPLIT_AFTER), new[6:8])                          # 口径 5：按数据条件拆两行
        self.assertEqual(old[6:], new[8:])                                     # Fever 结束行逐字
        self.assertEqual(M.PANEL_AFTER, text)
        leader = self.out["leader"][M.CID]
        pct = {row: f"{int(leader[row][111]) // 1000}%" for row in M.GROWTH_ROWS}
        self.assertEqual(f"雷属性共鸣时，每层「浪涌充能」，雷属性角色技能伤害＋{pct[0]}、攻击力＋{pct[1]}", new[0])
        self.assertEqual(f"每层「浪涌充能」，自身攻击力＋{pct[7]}、技能伤害＋{pct[8]}", new[1])
        self.assertEqual([], KL.panel_problems(text))
        self.assertEqual([], K.panel_text_problems(text))
        self.assertEqual([], M.panel_problems(M.PANEL_LEADER, text))
        self.assertNotIn("／", text)
        self.assertNotIn("/", text)                                            # 半角斜杠同样不许分项 / 分级
        self.assertNotRegex(text, r"属性共鸣时[：:]")
        self.assertFalse(any("；" in line and "FEVER槽" in line for line in new))
        self.assertFalse(any(line.startswith(B2.MAIN_ICON) for line in new))   # 队长面板无主位标记

    def test_dash_fever_line_split_follows_the_data(self):
        """口径 5（主会话扩展 B）：能力 6 #1（非 Fever，前置2 186）/ #2（Fever，前置2 12）共有雷≥6 共鸣、仅队长（42）、
        冲刺触发（4）、724 内容，强度 ±10% ⇒ 两种数据条件，拆两行、各自照写「雷属性共鸣时，」。依据变了 ⇒ revise() 拒绝。"""
        rows = self.live("ability", M.SPLIT_ABILITY_KEY)
        self.assertEqual([], M.split_basis_problems(rows))
        self.assertEqual(["雷·编成≥6 且 非Fever 且 队长 时: 冲刺≥1 → 自身 Fever槽增减(上限比例) 10%",
                          "雷·编成≥6 且 Fever 且 队长 时: 冲刺≥1 → 自身 Fever槽增减(上限比例) -10%"],
                         wf_describe.describe_rows(rows, "ability")[1:3])
        # 拆出的两行：后半行去掉共鸣前缀、以「；」拼回 == 第二批原行；数值记号不变
        first, second = SPLIT_AFTER
        prefix = "雷属性共鸣时，"
        self.assertTrue(first.startswith(prefix) and second.startswith(prefix))
        self.assertEqual(SPLIT_BEFORE, first + "；" + second[len(prefix):])
        self.assertIn(SPLIT_BEFORE, B2.PANEL_AFTER[M.PANEL_LEADER].split("\n"))
        self.assertEqual(M.SPLIT_LINE_BEFORE, SPLIT_BEFORE)
        self.assertEqual(M.SPLIT_LINES_AFTER, SPLIT_AFTER)
        self.assertEqual(self.out["notes"]["panel_split"][f"L{M.SPLIT_PANEL_INDEX + 1}"],
                         {"from": SPLIT_BEFORE, "to": list(SPLIT_AFTER)})
        # 仓库内校验器（口径 7 硬依赖）：拆行前的文案显式拆开后 == 最终文案、逐行 verbatim；不拆就交给校验器 ⇒ 拆出的
        # 第 2 行没有来源，必须拒绝
        import wf_panel_merge_check as PMC
        final = self.out["cas"][M.PANEL_LEADER][0][0]
        joined = final.replace("\n".join(SPLIT_AFTER), SPLIT_BEFORE)
        lines = joined.split("\n")
        at = lines.index(SPLIT_BEFORE)
        head, tail = SPLIT_BEFORE.split("；")
        lines[at:at + 1] = [head, prefix + tail]
        origin = "\n".join(lines)
        self.assertEqual(origin, final)
        result = PMC.check(origin, final, [])
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(set(result["columns"][0]["kinds"].values()), {"verbatim"})
        self.assertFalse(PMC.check(joined, final, [])["ok"])
        self.assertTrue(M.panel_problems(M.PANEL_LEADER, SPLIT_BEFORE))           # 未拆的原行会被规则扫描拦下
        self.assertTrue(M.panel_problems(M.PANEL_LEADER, "Lv1/Lv2/Lv3倍率提升至10倍/20倍/50倍"))
        self.assertTrue(M.panel_problems(M.PANEL_LEADER, "雷属性共鸣时：A＋1%"))
        # 两行条件相同（该合并）/ 丢共鸣 / 不再仅队长 / 强度或内容漂移 ⇒ 依据函数必须报错；revise() 同样拒绝
        # （输入先被 BEFORE 摘要拦下，依据核对是第二道闸）
        mutations = (
            (2, 13, "186"),          # 两行都成了非 Fever ⇒ 同条件
            (1, 6, "0"),             # 丢雷共鸣
            (2, 20, "0"),            # 不再仅队长
            (1, 51, "20000"),        # 强度与面板不符
            (2, 47, "211"),          # 内容不是 Fever 槽
        )
        for index, col, value in mutations:
            data = deepcopy(self.data)
            data["ability", M.SPLIT_ABILITY_KEY][index][col] = value
            self.assertTrue(M.split_basis_problems(data["ability", M.SPLIT_ABILITY_KEY]), (index, col))
            with self.assertRaises(ValueError, msg=(index, col)):
                M.revise(reader(data))

    def test_flag_text(self):
        self.assertEqual({M.PANEL_LEADER, M.FLAG_KEY}, set(self.out["cas"]))
        self.assertEqual([[FLAG_TEXT]], self.out["cas"][M.FLAG_KEY])
        self.assertEqual([], KL.panel_problems(FLAG_TEXT, skill_flag=True))    # 技能强化条目：无数字无时间
        self.assertEqual([], M.panel_problems(M.FLAG_KEY, FLAG_TEXT))
        self.assertTrue(M.panel_problems(M.FLAG_KEY, FLAG_TEXT + "（最多5层）"))
        self.assertNotIn("雷属性共鸣", FLAG_TEXT)                              # 共鸣前缀由前置自动拼（无覆盖时）
        self.assertEqual("雷属性共鸣时，" + FLAG_TEXT, FLAG_LINE)
        for text in (FLAG_TEXT, M.PANEL_AFTER, M.DESCRIPTION):
            for word in FORBIDDEN:
                self.assertNotIn(word, text)

    def test_main_slot_markers_still_match_rows(self):
        rows = {key: self.live("ability", key) for key in M.ABILITY_KEYS}
        cas = {key: [[K.MAIN_ICON + "x"]] if key == K.CAS_KEYS[1] else [["x"]] for key in K.CAS_KEYS}
        cas[B2.PANEL_THIRD] = self.context["cas", B2.PANEL_THIRD]
        cas.update(self.out["cas"])
        self.assertEqual([], K.main_slot_panel_problems(rows, cas))

    # ---------------------------------------------------------------- 契约
    def test_only_changed_keys_are_returned(self):
        norm = lambda v: json.loads(json.dumps(v, ensure_ascii=False))
        seen = set()
        for kind in ("ability", "leader", "cas", "text", "action", "dsl", "server_text", "table"):
            for key, value in self.out[kind].items():
                seen.add((kind, key))
                if (kind, key) == ("cas", M.FLAG_KEY):
                    self.assertNotIn((kind, key), self.data)                   # 新键（live 不存在）
                    continue
                self.assertIn((kind, key), self.data)
                self.assertNotEqual(norm(self.data[kind, key]), norm(value), (kind, key))
        changed = {("leader", M.CID), ("cas", M.PANEL_LEADER), ("dsl", L1), ("dsl", L2)}
        self.assertEqual(changed | {("cas", M.FLAG_KEY)}, seen)
        # 技能描述 3 类键只读核对（口径 R3：不改、不返回）
        read_only = {("text", M.CID), ("action", M.CODE), ("server_text", M.CID)}
        self.assertEqual(changed | read_only | {("ability", key) for key in M.ABILITY_KEYS}, set(M.BEFORE))
        for kind in ("text", "action", "server_text"):
            self.assertEqual({}, self.out[kind], kind)
        self.assertEqual({}, self.out["ability"])                              # 能力栏封顶版不动（口径 D4）
        self.assertEqual([], self.out["new_programs"])
        self.assertFalse(self.out["notes"]["runtime_verified"])
        json.dumps(self.out["notes"], ensure_ascii=False)

    def test_package_identity_and_version(self):
        self.assertEqual(("139994", "rec_android_seaside", ["s7-regis"]), (M.CID, M.CODE, M.PACKAGES))
        prev = tuple(int(x) for x in B2.PACKAGE_VERSION["s7-regis"].split("."))
        new = tuple(int(x) for x in M.PACKAGE_VERSION["s7-regis"].split("."))
        self.assertEqual((1, 0, 8), prev)
        self.assertEqual((1, 0, 9), new)
        self.assertEqual({}, M.REVIEWED_DRIFT)

    def test_baseline_drift_is_rejected_and_inputs_are_not_mutated(self):
        snapshot = deepcopy(self.data)
        M.revise(reader(self.data))
        self.assertEqual(snapshot, self.data)
        for (kind, key) in M.BEFORE:
            drifted = deepcopy(self.data)
            value = drifted[kind, key]
            if kind == "dsl":
                value[1] = 3
            elif kind == "action":
                value[0][1][4] = "601"
            else:
                value[0][0] = value[0][0] + "x"
            with self.assertRaisesRegex(ValueError, "drifted"):
                M.revise(reader(drifted))

    def test_existing_flag_text_key_is_rejected(self):
        staged = dict(self.data)
        staged["cas", M.FLAG_KEY] = [[FLAG_TEXT]]
        with self.assertRaisesRegex(ValueError, "already exists"):
            M.revise(reader(staged))

    def test_rerun_on_own_output_is_rejected(self):
        staged = dict(self.data)
        for kind in ("leader", "cas", "text", "action", "dsl", "server_text"):
            for key, value in self.out[kind].items():
                staged[kind, key] = value
        with self.assertRaisesRegex(ValueError, "drifted"):
            M.revise(reader(staged))
        with self.assertRaisesRegex(ValueError, "10-row|9-row"):
            M.leader_rows(self.out["leader"][M.CID])
        with self.assertRaisesRegex(ValueError, "preimage"):
            M.leader_rows(self.out["leader"][M.CID][:9])
        for program in (L1, L2):
            with self.assertRaisesRegex(ValueError, "already carries ConditionalsChangeSkillFlag"):
                M.skill_tree(self.out["dsl"][program])
        self.assertEqual(M.DESCRIPTION, M.description(M.DESCRIPTION))          # 描述本轮不改（恒等核对）
        with self.assertRaisesRegex(ValueError, "batch-2"):
            M.description(M.DESCRIPTION.replace("（最多5层）", "（最多5层，担任队长且雷属性共鸣时不受此限）"))
        with self.assertRaisesRegex(ValueError, "batch-2"):
            M.panel_text(M.PANEL_LEADER, self.out["cas"][M.PANEL_LEADER][0][0])

    def test_unreviewed_shapes_are_rejected(self):
        leader = self.live("leader", M.CID)
        leader[0][111] = leader[0][112] = "150000"                             # 第二批之前的值
        with self.assertRaisesRegex(ValueError, "preimage"):
            M.leader_rows(leader)
        leader = self.live("leader", M.CID)
        leader[7][100] = "10"                                                  # 有人先给队长自身行加了上限
        with self.assertRaisesRegex(ValueError, "preimage"):
            M.leader_rows(leader)
        with self.assertRaisesRegex(ValueError, "9-row"):
            M.leader_rows(self.live("leader", M.CID)[:7])                      # 第一批 7 行形态
        tree = self.live("dsl", L1)
        B2.binds(tree)[0][5] = 99.0                                            # 第二批之前（未封顶）
        with self.assertRaisesRegex(ValueError, "unreviewed surge layer bindings"):
            M.skill_tree(tree)
        tree = self.live("dsl", L1)
        B2.binds(tree)[0][5] = 5                                               # int 上限（不同 AMF3 编码）
        with self.assertRaisesRegex(ValueError, "unreviewed"):
            M.skill_tree(tree)
        tree = self.live("dsl", L1)
        tree[10] = 2                                                           # 第一批之前的能力伤害树
        with self.assertRaisesRegex(ValueError, "batch-1/2"):
            M.skill_tree(tree)
        b2 = load(B2_FIXTURE)
        with self.assertRaisesRegex(ValueError, "batch-2"):
            M.panel_text(M.PANEL_LEADER, b2["cas", M.PANEL_LEADER][0][0])      # 第一批文案
        with self.assertRaisesRegex(ValueError, "unexpected panel key"):
            M.panel_text(B2.PANEL_THIRD, self.live("cas", M.PANEL_LEADER)[0][0])
        with self.assertRaisesRegex(ValueError, "batch-2"):
            M.description(B1.DESCRIPTION)
        action = self.live("action", M.CODE)
        action[0][1][16] = "1"                                                 # 自动施放按旗号改条件
        with self.assertRaisesRegex(ValueError, "skill flag 1"):
            M.action_rows(action)


class GeneratorConsistencyTest(unittest.TestCase):
    """kit 走「浪涌 → 第一批 → 第二批 → 第三轮 c」同一组函数，产物必须 == revise()；未改键 == live。"""

    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.context = load(section="context")
        cls.out = M.revise(reader(cls.data))
        cls.b1_data = load(B1_FIXTURE)
        cls.surge = json.loads(SURGE_FIXTURE.read_bytes())

    def kit_rows(self):
        leader, third = R.revise_rows(self.surge["139994"], self.surge["1399943"], self.surge["1399941"])
        ability = {M.CID + s: deepcopy(self.b1_data["ability", M.CID + s]) for s in ("2", "5")}
        ability[B2.THIRD_KEY] = third
        return K.balance_b_rows(*K.balance_rows(leader, ability))

    def kit_panel(self):
        cas = {key: deepcopy(self.b1_data["cas", key]) for key in B1.PANEL_KEYS.values()}
        cas[K.CAS_KEYS[4]] = [["雷属性角色攻击力＋100%"]]
        return cas, K.balance_b_panel(K.balance_panel(cas))

    def test_kit_rows_match_revise(self):
        leader, ability = self.kit_rows()
        self.assertEqual(self.data["leader", M.CID], leader)                  # 第二批层输出 == 本批输入
        leader, ability = K.balance_c_rows(leader, ability)
        self.assertEqual(self.out["leader"][M.CID], leader)
        for key in (M.CID + "2", M.CID + "3", M.CID + "5"):
            self.assertEqual(self.data["ability", key], ability[key], key)     # 能力不动（== live）

    def test_kit_skill_trees_match_revise(self):
        matched = set()
        for source in self.surge["regis"]:
            tree = B2.skill_tree(B1.skill_tree(R.revise_skill(source)))
            for level, program in M.SKILL_PROGRAMS.items():
                if tree == self.data["dsl", program]:
                    self.assertEqual(self.out["dsl"][program], M.skill_tree(tree))
                    matched.add(level)
        self.assertEqual({"1", "2"}, matched)

    def test_kit_panel_and_description_match_revise(self):
        cas, panel = self.kit_panel()
        panel = K.balance_c_panel(panel)
        for key, cells in self.out["cas"].items():
            self.assertEqual(cells, panel[key], key)
        self.assertEqual(self.context["cas", B2.PANEL_THIRD], panel[B2.PANEL_THIRD])   # 能力 3 面板不动
        self.assertEqual(cas[K.CAS_KEYS[4]], panel[K.CAS_KEYS[4]])                    # 其余键原样透传
        self.assertEqual(M.DESCRIPTION, M.description(B2.description(B1.description(R.DESCRIPTION))))
        self.assertEqual(self.data["text", M.CID][0][5], M.DESCRIPTION)          # kit 落表描述 == live（本轮不改）

    def test_kit_layer_rejects_double_application(self):
        _cas, panel = self.kit_panel()
        panel = K.balance_c_panel(panel)
        with self.assertRaises(K.KitError):
            K.balance_c_panel(panel)
        rows = K.balance_c_rows(*self.kit_rows())
        with self.assertRaises(K.KitError):
            K.balance_c_rows(*rows)
        with self.assertRaises(K.KitError):
            K.balance_c_panel({B2.PANEL_THIRD: [["x"]]})

    def test_kit_build_applies_batch3_after_batch2(self):
        src = inspect.getsource(K.build)
        self.assertLess(src.index("balance_b_rows("), src.index("balance_c_rows("))
        self.assertLess(src.index("balance_b.skill_tree("), src.index("balance_c.skill_tree("))
        self.assertLess(src.index("cas_rows = balance_b_panel("), src.index("cas_rows = balance_c_panel("))
        self.assertLess(src.index("balance_c_panel("), src.index("main-slot marker mismatch after balance"))
        self.assertIn("balance_c.description(balance_b.description(balance.description(surge.DESCRIPTION)))", src)
        self.assertIs(K.balance_c, M)
        self.assertIn(M.FLAG_KEY, K.SPEC["extra_keys"][K.CAS])                 # 候选认领新文案键
        self.assertIn("balance_c.FLAG_KEY", inspect.getsource(K.kit_fingerprint))

    @unittest.skipUnless((ROOT / K.REVISION_REL).is_file(), "seasonal7 revision plan (gitignored work/) absent")
    def test_kit_chain_from_plan_matches_revise(self):
        revision = K.revision_rows(K.load_revision(ROOT))
        leader = [e["row_built"] for e in revision["leader"]]
        ability = {f"{K.CID}{slot[4:]}": [e["row_built"] for e in entries]
                   for slot, entries in revision["abilities"].items()}
        leader, ability[K.CID + "3"] = R.revise_rows(leader, ability[K.CID + "3"], ability[K.CID + "1"])
        leader, ability = K.balance_c_rows(*K.balance_b_rows(*K.balance_rows(leader, ability)))
        self.assertEqual(self.out["leader"][M.CID], leader)
        for key in M.ABILITY_KEYS:
            self.assertEqual(self.data["ability", key], ability[key], key)
        cas = {item["key"]: [[item["text"]]] for item in revision["custom_strings"]}
        for slot, key in ((0, K.CAS_KEYS[0]), (3, K.CAS_KEYS[3])):
            cas[key][0][0] = R.revise_text(slot, cas[key][0][0])
        cas = K.balance_c_panel(K.balance_b_panel(K.balance_panel(cas)))
        for key, cells in self.out["cas"].items():
            self.assertEqual(cells, cas[key], key)
        self.assertEqual(self.context["cas", B2.PANEL_THIRD], cas[B2.PANEL_THIRD])
        self.assertEqual([], K.main_slot_panel_problems(ability, cas))


if __name__ == "__main__":
    unittest.main()
