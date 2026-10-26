# -*- coding: utf-8 -*-
"""特克托 139993 ``super_robot_tailcoat`` 2026-09-27 平衡第三批：成长复核 + 技能倍率撤封顶（U4）。

fixture = live 输入快照（``fixtures/balance_20260927c_tekuto.json``，BEFORE = make_read 返回值的摘要；
``_precedent`` 是只读的对照行，不参与 revise），驱动 ``revise()``：每处改动的前后值、未改行/树外节点逐字保留、
旗号 3 分支关支 == live 原段且开支只差 Bind 上限、vlv 作用域与按分支的绑定号唯一、BEFORE 漂移拒绝、不改输入、
对自身输出重跑拒绝、合法性门禁为空、DSL AMF3 往返 + 四道门禁、生成器输出 == revise() 输出。
生成器一致性需要 work/ 下的 seasonal7 设计稿与改版 plan（gitignore，缺时跳过）。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_tekuto as B  # noqa: E402
import wf_balance_20260927c_tekuto as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402
import wf_seasonal7_kit_philia as PH  # noqa: E402
import wf_seasonal7_kit_tekuto as K  # noqa: E402
import wf_tekuto_low_hp as LOW_HP  # noqa: E402
import wf_tekuto_no_endlag_revision as NE  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927c_tekuto.json'
DESIGN = ROOT / K.DESIGN_REL
PLAN = ROOT / K.REVISION_REL
MANIFEST = ROOT / "work/character_packs/s7-tekuto/package/manifest.json"
BIND = "BindConditionAccumulationVariable"
#: 读主体绑定号的参数位（同 wf_seasonal7_kit_philia.scope_problems 的 lookup 表，另加 RotateHitArea[1]）。
LOOKUP_SLOTS = {"ShowEffect": (3,), "CreateHitArea": (2,), "FindNearSubjects": (1,), "CreateReferencePoint": (1,),
                "CreateNormalAttack": (1,), "CreateCondition": (1,), "CreateRatioHeal": (1,), "MoveHitArea": (1,),
                "StopBall": (1,), "RotateHitArea": (1,)}


def _raw_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def load_fixture() -> dict:
    return {kind: value for kind, value in _raw_fixture().items() if not kind.startswith("_")}


def _fkey(kind, key):
    return "|".join(key) if kind == "table" else key


def reader(data: dict, extra: dict | None = None):
    def read(kind, key):
        if extra and (kind, key) in extra:
            return deepcopy(extra[kind, key])
        value = data[kind][_fkey(kind, key)]              # 缺键 ⇒ KeyError（与暂存脚本的 make_read 一致）
        if kind == "action":                              # contract：list[(inner_key, fields)]
            return [(inner, fields) for inner, fields in value]
        return value
    return read


def diff_paths(a, b, path="$", out=None) -> list[str]:
    """两棵 JSON 形树的逐叶差异路径（类型或值不同都算）。"""
    out = [] if out is None else out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            diff_paths(x, y, f"{path}[{i}]", out)
    elif isinstance(a, dict) and isinstance(b, dict) and a.keys() == b.keys():
        for k in a:
            diff_paths(a[k], b[k], f"{path}.{k}", out)
    elif type(a) is not type(b) or a != b:
        out.append(path)
    return out


def choose_branch(tree, which: str):
    """把每个旗号 3 分支就地换成所选一侧的语句（``open``=担任队长且雷共鸣 / ``closed``=其余情况）。"""
    out = deepcopy(tree)

    def walk(node):
        if isinstance(node, list):
            if len(node) == 2 and node[0] == "Block" and isinstance(node[1], list):
                items = []
                for st in node[1]:
                    if (isinstance(st, list) and len(st) == 2 and st[0] == "Command"
                            and st[1][:2] == [M.FLAG_COMMAND, M.LEADER_FLAG]):
                        items.extend(st[1][2 if which == "open" else 3][1])
                    else:
                        items.append(st)
                node[1] = items
            for child in node:
                walk(child)
        elif isinstance(node, dict):
            for child in node.values():
                walk(child)

    walk(out)
    return out


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.precedent = _raw_fixture()["_precedent"]
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old_leader = cls.live["leader"][M.LEADER_KEY]
        cls.new_leader = cls.out["leader"][M.LEADER_KEY]
        cls.old_ab1 = cls.live["ability"][M.ABILITY1_KEY]
        cls.new_ab1 = cls.out["ability"][M.ABILITY1_KEY]

    # ------------------------------------------------------------ 契约

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][_fkey(kind, key)]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys},
                         {(kind, _fkey(kind, key)) for kind, key in M.BEFORE})
        self.assertNotIn(M.LEADER_CAS_KEY, self.live.get("cas", {}))

    def test_live_is_the_batch2_output(self):
        """输入基线 = 第二批 revise() 的输出（live 1.4.1053 上特克托这几项自第二批发布后没动过）。"""
        b_live = json.loads((Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_tekuto.json')
                            .read_text(encoding="utf-8"))
        b_live = {k: v for k, v in b_live.items() if not k.startswith("_")}
        b_out = B.revise(reader(deepcopy(b_live)))
        self.assertEqual(b_out["leader"][B.LEADER_KEY], self.old_leader)
        self.assertEqual(b_out["ability"][B.ABILITY2_KEY], self.live["ability"][B.ABILITY2_KEY])
        for program in M.PROGRAMS.values():
            self.assertEqual(b_out["dsl"][program], self.live["dsl"][program])
        self.assertEqual([[i, f] for i, f in b_out["action"][M.CODE]], self.live["action"][M.CODE])
        self.assertEqual(b_out["text"][M.CID], self.live["text"][M.CID])
        self.assertEqual(M.OLD_DESC, B.NEW_DESC)

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE, M.ELEMENT), (K.CID, K.CODE, K.ELEMENT))
        self.assertEqual((M.UID_ENGINE, M.UID_CANNON), (K.UID_ENGINE, K.UID_CANNON))
        self.assertEqual(M.PACKAGES, ["s7-tekuto"])
        self.assertEqual(M.PACKAGE_VERSION, {"s7-tekuto": "1.0.10"})   # 候选现值 1.0.9，只升不降
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertEqual(M.PROGRAMS, B.PROGRAMS)
        # 暂存脚本 splice 的命名空间断言：新 CAS 键必须以 change_skill_<code> 开头
        self.assertTrue(M.LEADER_CAS_KEY.startswith(f"change_skill_{M.CODE}"))

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["ability"]), {M.ABILITY1_KEY})
        self.assertEqual(set(out["leader"]), {M.LEADER_KEY})
        self.assertEqual(set(out["cas"]), {M.LEADER_CAS_KEY})
        self.assertEqual(out["cas"][M.LEADER_CAS_KEY], [[M.CAS_TEXT]])
        self.assertEqual(set(out["dsl"]), set(M.PROGRAMS.values()))
        # 技能说明只读核对（主会话 2026-09-27 口径 R3：不改 ⇒ 不返回）
        self.assertEqual(out["action"], {})
        self.assertEqual(out["text"], {})
        self.assertEqual(out["server_text"], {})
        self.assertEqual(out["table"], {})
        self.assertEqual(out["new_programs"], [])        # 候选 manifest 已认领两档技能树
        json.dumps(out["notes"], ensure_ascii=False)

    # ------------------------------------------------------------ 队长（成长复核）

    def test_leader_growth_rows_follow_the_table(self):
        """表 table.rows 特克托：L#0 80%、L#1 160%、L#2 3.5%、L#8 70%、L#10/L#11 35%（原值 × 档位，按规则取整）。"""
        self.assertEqual((len(self.old_leader), len(self.new_leader)), (12, 12))
        want = {0: ((111, 112), "100000", "10000", "80000"), 1: ((111, 112), "200000", "20000", "160000"),
                2: ((111, 112), "5000", "500", "3500"), 8: ((49, 50), "100000", "10000", "70000"),
                10: ((111, 112), "50000", "5000", "35000"), 11: ((111, 112), "50000", "5000", "35000")}
        self.assertEqual(set(want), set(M.LEADER_EDITS))
        for index, (cols, original, batch2, new) in want.items():
            before, after = self.old_leader[index], self.new_leader[index]
            self.assertEqual([i for i in range(124) if before[i] != after[i]], list(cols), index)
            self.assertEqual([before[c] for c in cols], [batch2, batch2], index)
            self.assertEqual([after[c] for c in cols], [new, new], index)
            self.assertEqual(M.LEADER_EDITS[index][2:4], (original, batch2), index)
            # 第二批 = 原值 ×1/10（B 模块的放缓倍率），本批回到原值 × 档位
            self.assertEqual(int(original), 10 * int(batch2), index)
        tiers = {i: M.TIER_NAMES[M.LEADER_EDITS[i][4]] for i in want}
        self.assertEqual(tiers, {0: "4/5", 1: "4/5", 2: "2/3", 8: "7/10", 10: "2/3", 11: "2/3"})

    def test_rounding_rule(self):
        """原值 ≥20% 取 5 的倍数（就近）、≤10% 取 0.5 的倍数；2/3 档向上取且不跌出下限（D1/D2）。"""
        for index, (_c, _cols, original, _b, tier, new, _w) in M.LEADER_EDITS.items():
            num, den = tier
            self.assertEqual(int(new), M.tier_value(int(original), tier), index)
            step = 5000 if int(original) >= 20000 else 500
            self.assertEqual(int(new) % step, 0, index)
            if tier == (2, 3):
                self.assertGreaterEqual(int(new) * den, int(original) * num, index)
            self.assertLessEqual(abs(int(new) * den - int(original) * num), step * den, index)
        # D1：原值 25% 的 2/3 档取 20%（不用 17.5%）；D2：<10% 按 .5 取
        self.assertEqual(M.tier_value(25000, (2, 3)), 20000)
        self.assertEqual(M.tier_value(5000, (2, 3)), 3500)
        with self.assertRaises(ValueError):
            M.tier_value(15000, (2, 3))

    def test_other_leader_rows_are_byte_identical(self):
        for index in M.LEADER_KEPT:
            self.assertEqual(self.new_leader[index], self.old_leader[index], index)
        self.assertEqual(sorted(M.LEADER_KEPT), [3, 4, 5, 6, 7, 9])
        # D3：不给成长行新增共鸣前置——#10/#11 仍是自身、无前置
        for index in (10, 11):
            self.assertEqual((self.new_leader[index][4], self.new_leader[index][9]), ("0", ""))

    def test_leader_panel_renders_the_new_values(self):
        lines = D.describe_rows(self.new_leader, "leader_ability")
        self.assertEqual(lines[0], "雷·编成≥6 时: 持续·状态累积计数固有≥1[固有13999301] → 赋予全队(雷) 攻击力 80%")
        self.assertEqual(lines[1], "雷·编成≥6 时: 持续·状态累积计数固有≥1[固有13999301] → 赋予全队(雷) 技能伤害 160%")
        self.assertEqual(lines[2], "雷·编成≥6 时: 持续·状态累积计数固有≥1[固有13999301] → 自身 独立乘区技能伤害 3.5%")
        self.assertTrue(lines[8].endswith("Elapsed时间≥120 → 自身 技能伤害 70%"), lines[8])
        self.assertEqual(lines[10:], ["持续·状态累积计数固有≥1[固有13999301] → 自身 攻击力 35%",
                                      "持续·状态累积计数固有≥1[固有13999301] → 自身 技能伤害 35%"])
        old_lines = D.describe_rows(self.old_leader, "leader_ability")
        for index in M.LEADER_KEPT:
            self.assertEqual(lines[index], old_lines[index], index)
        for line in lines:
            for word in ("无上限", "可无限", "上限"):
                self.assertNotIn(word, line)

    # ------------------------------------------------------------ 能力1（旗号 3 开关行）

    def test_switch_row_is_the_536_row_with_leader_precondition(self):
        self.assertEqual((len(self.old_ab1), len(self.new_ab1)), (2, 3))
        self.assertEqual(self.new_ab1[:2], self.old_ab1)
        row, flag1 = self.new_ab1[2], self.old_ab1[1]
        self.assertEqual(len(row), 126)
        self.assertEqual([i for i in range(126) if row[i] != flag1[i]], [6, 47, 70])
        self.assertEqual((flag1[6], flag1[47], flag1[70]), ("202", "536", f"change_skill_{M.CODE}"))
        self.assertEqual((row[6], row[47], row[70]), ("42", "705", M.LEADER_CAS_KEY))
        # 前置 1 = 42 仅队长；前置 2 = 2 元素编成 雷≥6；瞬发、无触发（c27=0）
        self.assertEqual((row[1], row[2], row[5], row[13], row[16], row[17], row[18], row[27]),
                         (self.old_ab1[0][1], self.old_ab1[0][2], "0", "2", "600000", "600000", "Yellow", "0"))
        self.assertEqual(D.describe_line(row, "ability"),
                         f"队长 且 雷·编成≥6 时: 自身 切换技能Flag3[{M.LEADER_CAS_KEY}]")

    def test_switch_row_has_the_live_leader_flag_shape(self):
        """与 live 罗尔夫中秋 1499866#4（704 + 前置 42 + 共鸣）逐格同形，只差归属/元素/kind/文案键。"""
        rolf = self.precedent["ability:1499866#4"]
        row = self.new_ab1[2]
        self.assertEqual((rolf[6], rolf[13], rolf[47]), ("42", "2", "704"))
        self.assertEqual([i for i in range(126) if row[i] != rolf[i]], [0, 2, 18, 47, 70])
        nao = self.precedent["ability:1530016#0"]
        self.assertEqual(nao[47], "705")                   # 官方 705 能力行先例（psychic_nao_3halfanv_6）

    def test_flag_three_was_free_and_is_now_leader_only(self):
        abilities = {key: self.live["ability"][key] for key in M.ABILITY_KEYS}
        before = M.flag_occupancy(abilities, self.old_leader)
        self.assertEqual(before, {1: [f"ability:{M.ABILITY1_KEY}#1"], 2: [f"ability:{M.CID}3#1"]})
        after = M.flag_occupancy({**abilities, M.ABILITY1_KEY: self.new_ab1}, self.new_leader)
        self.assertEqual(after, {**before, 3: [f"ability:{M.ABILITY1_KEY}#2"]})
        # 旗号 1（536 主位＋雷共鸣）与旗号 2（704 雷共鸣）都不是队长门控 ⇒ 只能另起旗号 3
        self.assertEqual(self.old_ab1[1][6], "202")
        self.assertEqual(self.live["ability"][f"{M.CID}3"][1][6], "2")
        # 队长表不写 705（U6：零先例 kind 进队长表会崩）
        self.assertFalse([r for r in self.new_leader if r[45] in M.FLAG_KINDS])

    def test_native_legality_gates_are_empty(self):
        for kind, rows in (("leader_ability", self.new_leader), ("ability", self.new_ab1)):
            for index, row in enumerate(rows):
                label = f"{kind}#{index}"
                self.assertEqual(L.client_legality_problems(kind, row), [], label)
                self.assertEqual(L.declared_block_field_problems(kind, row), [], label)
                self.assertEqual(L.invoke_skill_string_problems(row, {M.LEADER_CAS_KEY}, kind=kind), [], label)
                self.assertEqual(L.ability_element_column_problems(kind, row, M.ELEMENT), [], label)
                self.assertEqual(L.required_client_capabilities(kind, row), M.CAPABILITIES, label)

    def test_skill_flag_panel_rules(self):
        """kitlib.SKILL_FLAG_KINDS 补了 705 ⇒ 新开关行的「技能强化」条目同样受「不写数字/时间」约束。"""
        self.assertEqual(KL.SKILL_FLAG_KINDS[:2], ("536", "704"))           # 只追加
        self.assertIn("705", KL.SKILL_FLAG_KINDS)
        flagged = [row[70] for row in self.new_ab1 if row[47] in KL.SKILL_FLAG_KINDS]
        self.assertEqual(flagged, [f"change_skill_{M.CODE}", M.LEADER_CAS_KEY])
        self.assertEqual(KL.panel_problems(M.CAS_TEXT, skill_flag=True), [])
        self.assertTrue(KL.panel_problems(M.CAS_TEXT + "（最多10层）", skill_flag=True))
        self.assertEqual(PH.text_rule_problems({"cas": M.CAS_TEXT}), [])
        self.assertTrue(M.CAS_TEXT.startswith("强化『多重爆破·礼装重炮』"))
        self.assertNotIn("共鸣", M.CAS_TEXT)

    # ------------------------------------------------------------ 技能 DSL

    def test_closed_branch_is_the_live_tree(self):
        """关支（非队长或不共鸣）逐字就是 live（第二批）树：U7 封顶 10 层不变。"""
        for program in M.PROGRAMS.values():
            self.assertEqual(choose_branch(self.out["dsl"][program], "closed"), self.live["dsl"][program])

    def test_open_branch_differs_only_at_the_bind_cap(self):
        """开支（担任队长且雷共鸣）：只有 11 个 Bind[5] 10 → int 99；第二批的激光削韧 0.3 保留。"""
        for level, program in M.PROGRAMS.items():
            live, opened = self.live["dsl"][program], choose_branch(self.out["dsl"][program], "open")
            paths = diff_paths(live, opened)
            self.assertEqual(len(paths), 11, level)
            self.assertTrue(all(p.endswith("[5]") for p in paths), paths)
            binds = list(wf_dsl.iter_dsl_commands(opened, BIND))
            self.assertEqual(binds, [M.BIND_UNCAPPED] * 11, level)
            self.assertTrue(all(type(b[5]) is int for b in binds))
            self.assertEqual(M.BIND_UNCAPPED, B.BIND_BEFORE)                  # 第二批前原值（逐字含类型）
            self.assertEqual(B.down_census(opened), B.DOWN_AFTER)             # 削韧每次施放 ≤30 仍成立
            self.assertEqual(B.down_census(live), B.DOWN_AFTER)

    def test_each_segment_is_wrapped_in_place(self):
        for level, program in M.PROGRAMS.items():
            tree = self.out["dsl"][program]
            branches = M.flag_branches(tree, M.LEADER_FLAG)
            self.assertEqual(len(branches), 11, level)
            for (path, shape), branch in zip(M.SEGMENTS, branches):
                block = M._at(tree, path)
                self.assertEqual(block, ["Block", [["Command", branch]]], path)
                opened, closed = branch[2][1], branch[3][1]
                self.assertEqual(closed, M._at(self.live["dsl"][program], path)[1], path)
                self.assertEqual([M._shape(s) for s in closed], list(shape), path)
                self.assertEqual(opened[0], ["Command", M.BIND_UNCAPPED])
                self.assertEqual(closed[0], ["Command", M.BIND_CAPPED])
                self.assertEqual(opened[1:], closed[1:])
                self.assertIsNot(opened[1], closed[1])                     # 两侧不共享对象
            # 旗号：11 个旗号 3（FindNearSubjects 体内）+ 根部最后一句的护盾旗号 2；根语句不动
            self.assertEqual([c[1] for c in M.flag_branches(tree)], [3] * 11 + [2])
            self.assertEqual(tree[11][1][-1], M.SHIELD_BRANCH)
            self.assertEqual(tree[:11], self.live["dsl"][program][:11])
        # 两档同构：差异位置与 live 两档之间一致
        live_pair = [self.live["dsl"][p] for p in M.PROGRAMS.values()]
        out_pair = [choose_branch(self.out["dsl"][p], "closed") for p in M.PROGRAMS.values()]
        self.assertEqual(diff_paths(*live_pair), diff_paths(*out_pair))

    def test_vlv_scope_and_branch_aware_binding_ids(self):
        """复核 minor：Bind 挪进分支后分支外看不到它 ⇒ 每个 vlv 消费点都必须在同一分支、Bind 之后。"""
        for program in M.PROGRAMS.values():
            tree = self.out["dsl"][program]
            self.assertEqual(M.vid_scope_problems(tree), [])
            self.assertEqual(M.vid_scope_problems(self.live["dsl"][program]), [])
            self.assertEqual(K.balance_c_vid_scope_problems(tree), [])
            self.assertEqual(M.dup_bound_ids(tree), [])
            self.assertEqual(K.balance_c_dup_bound_ids(tree), [])
            vids = {v["vid"] for a in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack")
                    for term in a[6] for v in term.get("vlv", [])}
            self.assertEqual(vids, {M.VID_ENGINE})
            # 全树计数（不分支）时，重复的正好是两侧各一份的判定区绑定号 ⇒ 只有 philia 的 dup_bind_ids 一项红
            gates = PH.dsl_gates(tree, element=M.ELEMENT)
            self.assertEqual([f.split("=")[0] for f in PH.dsl_gate_failures(gates)], ["dup_bind_ids"])
            mirrored = sorted({i for b in M.flag_branches(tree, M.LEADER_FLAG)
                               for i in M.path_bound_ids(["Command", ["X", b[3]]])})
            self.assertEqual(gates["dup_bind_ids"], mirrored)
            self.assertEqual(K.balance_c_tree_problems(tree), [])
            # 分支外不得 lookup 分支内绑定的主体（判定区自己的 cid/hid/tid 只在本分支里被读）
            outside = deepcopy(tree)
            for block in [M._at(outside, path) for path, _shape in M.SEGMENTS]:
                block[1] = []
            refs = [c[slot] for c in PH.cmds(outside) for slot in LOOKUP_SLOTS.get(c[0], ())
                    if isinstance(c[slot], int) and not isinstance(c[slot], bool)]
            self.assertFalse(set(refs) & set(mirrored), sorted(set(refs) & set(mirrored)))
        # 负向：把一个判定区挪到分支外（Bind 留在分支里）⇒ vlv 作用域报错
        tree = deepcopy(self.out["dsl"][M.PROGRAMS["2"]])
        block = M._at(tree, M.SEGMENTS[1][0])
        branch = block[1][0][1]
        block[1].append(branch[3][1].pop())                                 # 关支的判定区挪出分支
        branch[2][1].pop()
        self.assertTrue(M.vid_scope_problems(tree))
        self.assertTrue(K.balance_c_vid_scope_problems(tree))
        # 负向：同一执行路径上重复绑定号
        tree = deepcopy(self.out["dsl"][M.PROGRAMS["2"]])
        block = M._at(tree, M.SEGMENTS[1][0])
        block[1].append(deepcopy(block[1][0][1][3][1][1]))
        self.assertTrue(M.dup_bound_ids(tree))
        self.assertTrue(K.balance_c_dup_bound_ids(tree))

    def test_dsl_roundtrip_and_native_gates(self):
        from wf_character_revision import encode_tree
        for level, program in M.PROGRAMS.items():
            tree = self.out["dsl"][program]
            self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree, level)
            # 暂存脚本落盘用的编码（裸 deflate）同样往返一致
            self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))["tree"], tree, level)
            self.assertEqual(L.action_dsl_element_problems(tree, M.ELEMENT), [], level)
            self.assertEqual(L.action_dsl_subject_binding_problems(tree), [], level)
            self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [], level)
            self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [], level)
            self.assertEqual(M.dsl_problems(tree), [], level)
            self.assertEqual(K.dsl_quick_problems(tree), [], level)
            self.assertEqual(NE.hold_statements(tree), [], level)              # 不带回停球

    def test_uncapped_branch_is_bounded_by_the_engine_unique(self):
        """开支上限 99 = 固有「引擎启动」c4 叠层上限：状态本身叠不过 99，所以开支等于不封顶。"""
        unique = self.live["table"][f"{M.UNIQUE}|{M.UID_ENGINE}"]
        self.assertEqual(unique[0][:2], ["unique_super_robot_tailcoat_engine", "引擎启动"])
        self.assertEqual(unique[0][M.UNIQUE_ENGINE_MAX_COL], str(M.BIND_UNCAPPED_CAP))
        self.assertEqual(K.UNIQUE_META[M.UID_ENGINE]["max"], str(M.BIND_UNCAPPED_CAP))

    # ------------------------------------------------------------ 文案

    def test_skill_description_in_all_five_places_stays_batch2(self):
        """口径 R3：技能说明只写技能本体（关支上限「（最多10层）」照写）；强化后的不封顶只由 CAS 强化条目描述
        ⇒ 5 处保持第二批原文，revise() 不返回。"""
        self.assertEqual(M.NEW_DESC, M.OLD_DESC)
        self.assertEqual(M.NEW_DESC.count("（最多10层）"), 1)
        action, text, server = M.revise_texts(deepcopy(self.live["action"][M.CODE]),
                                              deepcopy(self.live["text"][M.CID]),
                                              deepcopy(self.live["server_text"][M.CID]))
        for (inner, old), (inner2, new) in zip(self.live["action"][M.CODE], action):
            self.assertEqual((inner, list(old)), (inner2, list(new)))
            self.assertEqual(old[1], M.OLD_DESC)
        for kind, new in (("text", text), ("server_text", server)):
            old = self.live[kind][M.CID]
            self.assertEqual(old, new, kind)
            self.assertEqual([old[0][5], old[0][7]], [M.OLD_DESC] * 2, kind)
        self.assertEqual(KL.panel_problems(M.NEW_DESC), [])
        self.assertEqual(NE.text_problems("skill", M.NEW_DESC), [])
        for word in ("自身为队长时", "无上限", "不设上限", "不受此限", "担任队长", "强化后", "共鸣"):
            self.assertNotIn(word, M.NEW_DESC)

    def test_enhancement_entry_names_the_skill(self):
        """口径 R2：强化条目官方格式「强化『<技能名>』：…」，技能名 = action_skill 第 1 档 c0；技能名漂移 ⇒ 拒绝。"""
        self.assertEqual(self.live["action"][M.CODE][0][1][0], M.SKILL_NAME)
        self.assertTrue(M.CAS_TEXT.startswith(f"强化『{M.SKILL_NAME}』："))
        self.assertEqual(KL.panel_problems(M.CAS_TEXT, skill_flag=True), [])
        self.assertNotIn("强化自身技能", M.CAS_TEXT)
        action = deepcopy(self.live["action"][M.CODE])
        action[0][1][0] = "多重爆破"
        with self.assertRaisesRegex(ValueError, "skill name"):
            M.revise_texts(action, deepcopy(self.live["text"][M.CID]), deepcopy(self.live["server_text"][M.CID]))

    # ------------------------------------------------------------ fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["leader"][M.LEADER_KEY][0][111] = "mutated"
        out["ability"][M.ABILITY1_KEY][0][0] = "mutated"
        next(iter(out["dsl"].values()))[11] = "mutated"
        self.assertEqual(data, self.live)

    def test_baseline_drift_is_rejected(self):
        program = M.PROGRAMS["1"]
        for kind, key, mutate in (
                ("leader", M.LEADER_KEY, lambda v: v[0].__setitem__(111, "90000")),
                ("leader", M.LEADER_KEY, lambda v: v.pop()),
                ("ability", M.ABILITY1_KEY, lambda v: v[1].__setitem__(6, "0")),
                ("ability", f"{M.CID}3", lambda v: v[1].__setitem__(47, "705")),
                ("ability", f"{M.CID}6", lambda v: v[0].__setitem__(51, "10000")),
                ("table", f"{M.UNIQUE}|{M.UID_ENGINE}", lambda v: v[0].__setitem__(4, "(None)")),
                ("dsl", program, lambda v: v.__setitem__(10, 4)),
                ("action", M.CODE, lambda v: v[0][1].__setitem__(4, "600")),
                ("text", M.CID, lambda v: v[0].__setitem__(0, "X")),
                ("server_text", M.CID, lambda v: v[0].__setitem__(7, "X"))):
            data = deepcopy(self.live)
            mutate(data[kind][key])
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline", msg=f"{kind}:{key}"):
                M.revise(reader(data))

    def test_new_string_key_must_be_absent(self):
        with self.assertRaisesRegex(ValueError, "already exists"):
            M.revise(reader(deepcopy(self.live), {("cas", M.LEADER_CAS_KEY): [[M.CAS_TEXT]]}))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        data = deepcopy(self.live)
        for kind in ("leader", "ability", "dsl"):
            data[kind].update(deepcopy(self.out[kind]))
        with self.assertRaises(ValueError):
            M.revise(reader(data))
        with self.assertRaises(ValueError):
            M.leader_rows(self.new_leader)
        with self.assertRaises(ValueError):
            M.ability1_rows(self.new_ab1)
        for program in M.PROGRAMS.values():
            with self.assertRaises(ValueError):
                M.revise_tree(self.out["dsl"][program], "x")
        # 技能说明本轮不改：带强化后描述的说明（旧第三批文案）⇒ 拒绝
        bad = deepcopy(self.live["text"][M.CID])
        bad[0][5] = M.OLD_DESC.replace("（最多10层）", "（最多10层，担任队长且雷属性共鸣时不受此限）")
        with self.assertRaises(ValueError):
            M.revise_texts(deepcopy(self.live["action"][M.CODE]), bad, deepcopy(self.live["server_text"][M.CID]))

    def test_row_and_tree_locators_are_content_based(self):
        """绕过 BEFORE 直接调纯函数：行形状/树形状不对也要拒绝。"""
        for index, col, value in ((0, 108, "0"), (2, 111, "5000"), (8, 49, "100000"), (10, 4, "2"),
                                  (11, 107, "0"), (3, 111, "6000")):
            rows = deepcopy(self.old_leader)
            rows[index][col] = value
            with self.assertRaises(ValueError, msg=(index, col)):
                M.leader_rows(rows)
        for mutate in (lambda r: r[1].__setitem__(80, "x"), lambda r: r.append(list(r[1])),
                       lambda r: r.reverse(), lambda r: r[1].__setitem__(47, "704")):
            rows = deepcopy(self.old_ab1)
            mutate(rows)
            with self.assertRaises(ValueError):
                M.ability1_rows(rows)
        tree = deepcopy(self.live["dsl"][M.PROGRAMS["2"]])
        next(wf_dsl.iter_dsl_commands(tree, BIND))[5] = 50
        with self.assertRaises(ValueError):
            M.revise_tree(tree, "2")
        tree = deepcopy(self.live["dsl"][M.PROGRAMS["2"]])
        M._at(tree, M.SEGMENTS[3][0])[1].pop(1)                             # 某段少了 charge_core
        with self.assertRaises(ValueError):
            M.revise_tree(tree, "2")
        tree = deepcopy(self.live["dsl"][M.PROGRAMS["2"]])
        tree[11][1].pop()                                                   # 根部护盾分支没了
        with self.assertRaises(ValueError):
            M.revise_tree(tree, "2")


def fake_families():
    """与 clone_effect_family 返回形状一致（同 test_seasonal7_kit_tekuto.fake_families）。"""
    out = []
    for src_dir, sub, fx in K.FAMILIES:
        out.append({"src_dir": src_dir, "dst_dir": f"battle/effect/skill_unique/{K.CODE}/{sub}",
                    "donor": src_dir.rsplit("/", 1)[-1], "dst_name": sub, "copied_bases": sorted(fx)})
    return out


@unittest.skipUnless(DESIGN.is_file() and PLAN.is_file(), "seasonal7 design/revision json not present")
class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_seasonal7_kit_tekuto（第七轮 apply_balance_c / balance_c_skill_tree）重跑 == revise() 输出。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.plan = K.load_revision_plan(ROOT)
        design = json.loads(DESIGN.read_text(encoding="utf-8"))
        cls.pre = {}
        for slot in range(1, 7):                  # 同 test_seasonal7_kit_tekuto._design_ability_rows
            key = design["ability_keys"][f"slot{slot}"]["key"]
            cls.pre[key] = [list(rec["row"]) for rec in design["abilities"][f"slot{slot}"]]

    def _generator_rows(self, current):
        """build() 里的同一串：revision rows → low_hp → 第六轮 apply_balance_b → 第七轮 apply_balance_c。"""
        ability, _trace = K.revision_ability_rows(self.plan, deepcopy(current))
        leader = K.revision_leader_rows(self.plan)
        leader, ability[f"{K.CID}3"] = LOW_HP.revise_rows(leader, ability[f"{K.CID}3"])
        leader, ability[K.REV5_ABILITY_KEY], _b = K.apply_balance_b(leader, ability[K.REV5_ABILITY_KEY])
        leader, ability[K.BALANCE_C_SWITCH_ABILITY_KEY], trace = K.apply_balance_c(
            leader, ability[K.BALANCE_C_SWITCH_ABILITY_KEY])
        return leader, ability, trace

    def test_generator_rows_equal_revise_output(self):
        leader, ability, trace = self._generator_rows(self.pre)
        self.assertEqual(leader, self.out["leader"][M.LEADER_KEY])
        self.assertEqual(ability[M.ABILITY1_KEY], self.out["ability"][M.ABILITY1_KEY])
        self.assertEqual(ability[f"{M.CID}2"], self.live["ability"][f"{M.CID}2"])    # D4：能力2 保持第二批
        self.assertEqual(ability[f"{M.CID}3"], self.live["ability"][f"{M.CID}3"])
        self.assertEqual(len(trace), 7)
        self.assertEqual((K.BALANCE_C_SWITCH_ABILITY_KEY, K.BALANCE_C_SWITCH_KIND, K.BALANCE_C_LEADER_ONLY),
                         (M.ABILITY1_KEY, M.SWITCH_KIND, M.LEADER_ONLY_PRECONDITION))

    def test_rerun_from_the_written_back_package_is_stable(self):
        """候选回写后包内能力1 是 3 行、能力2 是第二批封顶行：重跑结果不变、不叠改。"""
        current = {key: deepcopy(self.live["ability"][key]) for key in M.ABILITY_KEYS}
        current[M.ABILITY1_KEY] = deepcopy(self.out["ability"][M.ABILITY1_KEY])
        leader, ability, _trace = self._generator_rows(current)
        self.assertEqual(leader, self.out["leader"][M.LEADER_KEY])
        for key in M.ABILITY_KEYS:
            want = self.out["ability"].get(key, self.live["ability"][key])
            self.assertEqual(ability[key], want, key)

    def test_generator_rejects_reapplying_or_drifted_input(self):
        leader, ability, _trace = self._generator_rows(self.pre)
        with self.assertRaises(K.KitError):
            K.apply_balance_c(leader, ability[K.BALANCE_C_SWITCH_ABILITY_KEY][:2])     # 队长已是第三批值
        with self.assertRaises(K.KitError):
            K.apply_balance_c(self.live["leader"][M.LEADER_KEY], ability[K.BALANCE_C_SWITCH_ABILITY_KEY])
        for program in M.PROGRAMS.values():
            with self.assertRaises(K.KitError):
                K.balance_c_skill_tree(self.out["dsl"][program])

    def test_generator_trees_equal_revise_output(self):
        from wf_tekuto_fast_release import final_tree
        for level, program in M.PROGRAMS.items():
            tree = K.donor_tree(level, self.plan)
            for fam in fake_families():
                tree, _info = C.rewrite_effect_refs(tree, fam)
            probs, _facts = K.revision_tree_problems(tree, level, self.plan)
            self.assertEqual(probs, [], level)
            tree = final_tree(LOW_HP.revise_skill(tree))
            self.assertEqual(tree, self.live["dsl"][program], level)            # 第六轮为止 == live
            tree = K.balance_c_skill_tree(tree)
            self.assertEqual(tree, self.out["dsl"][program], level)
        self.assertEqual((K.LEADER_SKILL_FLAG, K.ENGINE_CAP, K.ENGINE_CAP_LEADER),
                         (M.LEADER_FLAG, M.BIND_CAPPED[5], M.BIND_UNCAPPED_CAP))
        self.assertEqual(K.BALANCE_C_SEGMENTS, len(M.SEGMENTS))

    def test_generator_texts_and_strings_equal_revise_output(self):
        for level in ("1", "2"):
            self.assertEqual(K.TEXTS[f"desc{level}"], M.NEW_DESC)
        self.assertEqual(K._DESC_BALANCE_C, M.NEW_DESC)
        self.assertEqual(K._DESC_BALANCE_B, M.OLD_DESC)
        self.assertEqual(K._DESC_BALANCE_C, K._DESC_BALANCE_B)                 # 口径 R3：第三批不改技能说明
        self.assertEqual((K.TEXTS["skill1"], K.CHANGE_SKILL_LEADER_TEXT), (M.SKILL_NAME, M.CAS_TEXT))
        self.assertEqual((K.CHANGE_SKILL_LEADER_KEY, K.CHANGE_SKILL_LEADER_TEXT), (M.LEADER_CAS_KEY, M.CAS_TEXT))
        self.assertIn(M.LEADER_CAS_KEY, K.SPEC["extra_keys"][K.CAS])


@unittest.skipUnless(MANIFEST.is_file(), "candidate workspace s7-tekuto not present")
class CandidateTests(unittest.TestCase):
    def test_package_version_only_goes_up(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        current = manifest["package_version"]
        as_tuple = lambda v: tuple(int(x) for x in v.split("."))        # noqa: E731
        self.assertGreaterEqual(as_tuple(M.PACKAGE_VERSION["s7-tekuto"]), as_tuple(current))
        self.assertGreater(as_tuple(M.PACKAGE_VERSION["s7-tekuto"]), as_tuple(B.PACKAGE_VERSION["s7-tekuto"]))


if __name__ == "__main__":
    unittest.main()
