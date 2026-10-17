# -*- coding: utf-8 -*-
"""泽赫尔「今晚由团长买单」159997 · 2026-09-27 平衡调整第二批（无上限成长）修订模块回归。

fixture = live 1.4.1049 只读快照（与候选 s7-zehr 1.0.7 逐字相同）+ kit 改版计划回放行（09-17 灯火修订之前）。
逐项断言：队长 #3 #4 原位 ×1/10、队尾 #6–#8 由能力行派生（灯芯 0.5%、灯火正旺 6%）、能力1/3 限次弱化、
三条覆盖文案逐字、面板数字与行同源、其余行逐字保留、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、
合法性与面板门禁为空、生成器「kit 回放 → 09-17 灯火修订 → 第二批」== revise()，
以及澄波响 kit 借 live 1599971#4 时本批改的格都已显式钉住。
"""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_zehr as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_seasonal7_kit_zehr as K  # noqa: E402
import wf_zehr_lamp_revision as R  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_zehr.json'
ICON = M.MAIN_ICON


def load():
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data = {(kind, tuple(key) if isinstance(key, list) else key): value for kind, key, value in fx["reads"]}
    return data, fx["kit_rows"]


def reader(data):
    return lambda kind, key: data[kind, key]


def diff_cells(a: list[str], b: list[str]) -> dict[int, tuple[str, str]]:
    return {i: (x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y}


LEADER_TEXT_AFTER = "\n".join((
    "光属性共鸣时，光属性角色攻击力＋400%、强化弹射伤害＋200%",
    "赋予专属强化弹射：剑士型与辅助型同时生效，回旋斩持续时间延长、单击威力提升",
    "每达成35连击，强化弹射伤害＋5%",
    "每发动强化弹射，光属性角色攻击力＋3.5%",
    "光属性共鸣时，每发动3次强化弹射，接下来6次弹射各追加9连击",
    "每1层「灯芯」，强化弹射伤害额外乘区＋0.5%",
    "光属性共鸣时，每获得1次「灯火正旺」，光属性角色攻击力＋6%、强化弹射伤害＋6%（CT 5s）",
    "改变冲刺方向：朝点击侧斜下方冲刺，保留头目弱点与传送舱锁定",
))
A1_TEXT_AFTER = "\n".join((
    ICON + "战斗开始时，自身技能槽＋50%",
    ICON + "光属性共鸣时，强化『白银一闪·打烊时刻』的「攻击力提升效果」与「强化弹射伤害提升效果」",
    ICON + "光属性共鸣时，每达成55连击，赋予自身「灯火正旺」15秒，并累积1层「灯芯」（CT 5s）",
    ICON + "每1层「灯芯」，强化弹射伤害额外乘区＋1%（最多10层）",
))
A3_TEXT_AFTER = "\n".join((
    ICON + "光属性共鸣时，每获得1次「灯火正旺」，光属性角色攻击力＋10%（最多8次，CT 5s）",
    ICON + "光属性共鸣时，每获得1次「灯火正旺」，强化弹射伤害＋10%（最多10次，CT 5s）",
    ICON + "持有「灯火正旺」期间，强化弹射伤害额外乘区＋15%",
    ICON + "持有「灯火正旺」期间，每达成35连击，连击＋15",
    ICON + "持有「灯火正旺」期间，强化弹射伤害随连击数提高",
))


def pct(value: str) -> str:
    """数值列（100000 = 100%）→ 面板百分数写法。"""
    number = int(value) / 1000
    return f"{number:g}%"


class ReviseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, _ = load()
        cls.out = M.revise(reader(cls.data))

    def live(self, kind, key):
        return deepcopy(self.data[kind, key])

    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(set(self.data), set(M.BEFORE))
        for key, want in M.BEFORE.items():
            self.assertEqual(M.digest(self.data[key]), want, key)

    def test_leader_slowed_in_place_and_growth_rows_appended(self):
        before, after = self.live("leader", M.CID), self.out["leader"][M.CID]
        self.assertEqual(len(after), 9)
        want = {3: {49: ("50000", "5000"), 50: ("50000", "5000")},
                4: {49: ("35000", "3500"), 50: ("35000", "3500")}}
        for i, (old, new) in enumerate(zip(before, after[:6])):
            self.assertEqual(diff_cells(old, new), want.get(i, {}), i)
        # 每 35 连击 / 每次 PF：3 分钟 ≥30 次 ⇒ ×1/10
        for i in (3, 4):
            self.assertEqual(int(after[i][49]) * 10, int(before[i][49]))
        a1, a3 = self.live("ability", M.A1), self.live("ability", M.A3)
        for li, (_t, key, idx, cells, cols, value) in M.LEADER_NEW_SOURCES.items():
            src = (a1 if key == M.A1 else a3)[idx]
            self.assertEqual(src, M._row(M.ABILITY_NCOLS, cells))
            derived = M.leader_row_from_ability(src)
            self.assertEqual(diff_cells(derived, after[li]),
                             {cols[0]: (derived[cols[0]], value), cols[1]: (derived[cols[1]], value)}, li)
            self.assertEqual(after[li], M._row(M.LEADER_NCOLS, M.LEADER_NEW[li]))
        # 灯芯 3% ×1/5 = 0.6% → 与索利兹同精度取 0.5%；灯火正旺 30% ×1/5 = 6%
        self.assertEqual((after[6][111], after[6][112]), ("500", "500"))
        self.assertEqual(int(after[7][49]) * 5, int(a3[0][51]))
        self.assertEqual(int(after[8][49]) * 5, int(a3[3][51]))
        self.assertEqual(after[6][100], "(None)")                         # 队长灯芯行不设限次（固有 99 层封顶）

    def test_no_merge_candidate_in_leader(self):
        before = self.live("leader", M.CID)
        self.assertFalse([r for r in before if r[3] == "1" and r[107] == "413"])
        self.assertFalse([r for r in before if r[25] == "12" and r[28] == "5500000"])

    def test_ability_rows_capped_in_place(self):
        a1_before, a1 = self.live("ability", M.A1), self.out["ability"][M.A1]
        for i, (old, new) in enumerate(zip(a1_before, a1)):
            want = {102: ("(None)", "10"), 113: ("3000", "1000"), 114: ("3000", "1000")} if i == 4 else {}
            self.assertEqual(diff_cells(old, new), want, i)
        a3_before, a3 = self.live("ability", M.A3), self.out["ability"][M.A3]
        want3 = {0: {34: ("(None)", "8"), 51: ("30000", "10000"), 52: ("30000", "10000")},
                 3: {34: ("(None)", "10"), 51: ("30000", "10000"), 52: ("30000", "10000")}}
        for i, (old, new) in enumerate(zip(a3_before, a3)):
            self.assertEqual(diff_cells(old, new), want3.get(i, {}), i)
        self.assertEqual(len(a1), 5)
        self.assertEqual(len(a3), 7)
        self.assertEqual({r[1] for r in a1 + a3}, {"false"})
        for i in (0, 3):                                                   # 触发 / CT / 共鸣前置不变
            self.assertEqual((a3[i][27], a3[i][30], a3[i][35], a3[i][6], a3[i][11]),
                             ("12", "5500000", "300", "2", "White"))
        # 满叠：灯芯 10%、光队攻 80%、PF 伤 100%
        self.assertEqual(int(a1[4][102]) * int(a1[4][114]) / 1000, 10)
        self.assertEqual(int(a3[0][34]) * int(a3[0][52]) / 1000, 80)
        self.assertEqual(int(a3[3][34]) * int(a3[3][52]) / 1000, 100)
        self.assertEqual(a3[6], a3_before[6])                              # 持有灯火正旺时每 1 连击 PF +5%：keep

    def test_describe_after(self):
        got = {f"leader_ability:{M.CID}#{i}": D.describe_line(self.out["leader"][M.CID][i], "leader_ability")
               for i in (3, 4, 6, 7, 8)}
        got[f"ability:{M.A1}#4"] = D.describe_line(self.out["ability"][M.A1][4], "ability")
        got.update({f"ability:{M.A3}#{i}": D.describe_line(self.out["ability"][M.A3][i], "ability")
                    for i in (0, 3)})
        self.assertEqual(got, M.DESCRIBE_AFTER)
        self.assertEqual(self.out["notes"]["describe_after"], M.DESCRIBE_AFTER)

    def test_panel_texts_exact(self):
        self.assertEqual(self.out["cas"], {M.CAS_LEADER: [[LEADER_TEXT_AFTER]], M.CAS_A1: [[A1_TEXT_AFTER]],
                                           M.CAS_A3: [[A3_TEXT_AFTER]]})
        # 未改的行逐字保留
        old = self.live("cas", M.CAS_A3)[0][0].split("\n")
        self.assertEqual(A3_TEXT_AFTER.split("\n")[2:], old[1:])
        old = self.live("cas", M.CAS_A1)[0][0].split("\n")
        self.assertEqual(A1_TEXT_AFTER.split("\n")[:3], old[:3])

    def test_panel_numbers_match_rows(self):
        leader = self.out["leader"][M.CID]
        a1, a3 = self.out["ability"][M.A1], self.out["ability"][M.A3]
        self.assertIn(f"每达成35连击，强化弹射伤害＋{pct(leader[3][50])}", LEADER_TEXT_AFTER)
        self.assertIn(f"光属性角色攻击力＋{pct(leader[4][50])}", LEADER_TEXT_AFTER)
        self.assertIn(f"额外乘区＋{pct(leader[6][112])}", LEADER_TEXT_AFTER)
        self.assertIn(f"光属性角色攻击力＋{pct(leader[7][50])}、强化弹射伤害＋{pct(leader[8][50])}（CT 5s）",
                      LEADER_TEXT_AFTER)
        self.assertEqual(leader[7][33], "300")
        self.assertIn(f"额外乘区＋{pct(a1[4][114])}（最多{a1[4][102]}层）", A1_TEXT_AFTER)
        self.assertIn(f"光属性角色攻击力＋{pct(a3[0][52])}（最多{a3[0][34]}次，CT 5s）", A3_TEXT_AFTER)
        self.assertIn(f"强化弹射伤害＋{pct(a3[3][52])}（最多{a3[3][34]}次，CT 5s）", A3_TEXT_AFTER)

    def test_panel_rules(self):
        texts = {key: rows[0][0] for key, rows in self.out["cas"].items()}
        self.assertEqual(M.panel_problems(texts), [])
        for key, text in texts.items():
            self.assertEqual(KL.panel_problems(text), [], key)
            self.assertEqual(K.panel_text_problems(text), [], key)
            self.assertNotIn("／", text)
            for word in ("可无限", "无上限", "自身为队长时", "觉醒后", "生命值100%以下", "最多99层"):
                self.assertNotIn(word, text)
        for key in (M.CAS_A1, M.CAS_A3):
            self.assertTrue(all(line.startswith(ICON) for line in texts[key].split("\n")), key)
        self.assertNotIn("icon", texts[M.CAS_LEADER])
        # 阴性对照：禁词 / 缺图标 / 「／」都会被门禁抓住
        bad = dict(texts)
        bad[M.CAS_A1] = texts[M.CAS_A1].replace(ICON + "战斗开始时", "战斗开始时")
        bad[M.CAS_A3] = texts[M.CAS_A3] + "（可无限累积）"
        bad[M.CAS_LEADER] = texts[M.CAS_LEADER].replace("\n改变冲刺方向", "／改变冲刺方向")
        self.assertEqual(len(M.panel_problems(bad)), 4)

    def test_row_legality_and_kit_gates(self):
        rows = [("leader_ability", r) for r in self.out["leader"][M.CID]]
        rows += [("ability", r) for key in (M.A1, M.A3) for r in self.out["ability"][key]]
        for kind, row in rows:
            self.assertEqual(L.client_legality_problems(kind, row), [], row)
            self.assertEqual(L.declared_block_field_problems(kind, row), [], row)
            self.assertEqual(L.invoke_skill_string_problems(row, M.STRINGS, kind), [], row)
            self.assertEqual(L.ability_element_column_problems(kind, row, M.ELEMENT), [], row)
            self.assertEqual(K.trigger_limit_problems(kind, row), [], row)
        for key, idx in K.NO_LEADER_GATE_ROWS:                           # 灯火四行不带 pre42（kit R1 锁）
            self.assertNotEqual(self.out["ability"][key][idx][6], "42", (key, idx))

    def test_no_new_client_capabilities(self):
        for kind, table, key in (("leader_ability", "leader", M.CID), ("ability", "ability", M.A1),
                                 ("ability", "ability", M.A3)):
            self.assertEqual(M.capability_set(kind, self.out[table][key]),
                             M.capability_set(kind, self.live(table, key)), key)
        self.assertEqual({L.panel_override_capability(k) for k in self.out["cas"]},
                         {"panel-description-override-v2"})

    def test_only_changed_keys_are_returned(self):
        self.assertEqual(set(self.out["leader"]), {M.CID})
        self.assertEqual(set(self.out["ability"]), {M.A1, M.A3})
        self.assertEqual(set(self.out["cas"]), {M.CAS_LEADER, M.CAS_A1, M.CAS_A3})
        for kind in ("text", "table", "action", "dsl", "server_text", "new_programs"):
            self.assertFalse(self.out[kind], kind)
        self.assertEqual((M.PACKAGES, M.PACKAGE_VERSION, M.CAPABILITIES, M.REVIEWED_DRIFT),
                         (["s7-zehr"], {"s7-zehr": "1.0.8"}, [], {}))
        self.assertIs(self.out["notes"]["runtime_verified"], False)
        json.dumps(self.out["notes"], ensure_ascii=False)
        for key in list(self.out["cas"]):                    # RevisionCandidate 命名空间
            self.assertTrue(key.startswith(f"desc_override_{M.CODE}"))

    def test_baseline_drift_is_rejected_and_inputs_are_not_mutated(self):
        saved = deepcopy(self.data)
        M.revise(reader(self.data))
        self.assertEqual(self.data, saved)
        for kind, key in M.BEFORE:
            data = deepcopy(self.data)
            data[kind, key][0][0] = data[kind, key][0][0] + "x"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))

    def test_rerun_on_own_output_is_rejected(self):
        data = deepcopy(self.data)
        data["leader", M.CID] = self.out["leader"][M.CID]
        for key, rows in self.out["ability"].items():
            data["ability", key] = rows
        for key, rows in self.out["cas"].items():
            data["cas", key] = rows
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise(reader(data))

    def test_unique_guard(self):
        wick = self.live("table", (M.UNIQUE, M.UID_WICK))
        lamp = self.live("table", (M.UNIQUE, M.UID_LAMP))
        M._unique_guard(wick, lamp)
        bad = deepcopy(wick)
        bad[0][4] = "(None)"
        with self.assertRaises(ValueError):
            M._unique_guard(bad, lamp)
        bad = deepcopy(lamp)
        bad[0][3] = "720"
        with self.assertRaises(ValueError):
            M._unique_guard(wick, bad)

    def test_transforms_are_idempotent_and_reject_unreviewed_shapes(self):
        leader, a1, a3 = (self.out["leader"][M.CID], self.out["ability"][M.A1], self.out["ability"][M.A3])
        self.assertEqual(M.balance_rows(leader, a1, a3), (leader, a1, a3))
        texts = {key: rows[0][0] for key, rows in self.out["cas"].items()}
        self.assertEqual(M.panel_texts(texts), texts)
        cases = [
            (M.leader_rows, self.live("leader", M.CID), 3, 28, "3000000"),     # 阈值漂移
            (M.leader_rows, self.live("leader", M.CID), 4, 49, "30000"),       # 强度漂移
            (M.ability1_rows, self.live("ability", M.A1), 4, 104, "159997"),   # 数错固有
            (M.ability1_rows, self.live("ability", M.A1), 4, 102, "10"),       # 半成品（限次改了强度没改）
            (M.ability3_rows, self.live("ability", M.A3), 0, 35, "600"),       # CT 漂移
            (M.ability3_rows, self.live("ability", M.A3), 3, 51, "50000"),     # 强度漂移
        ]
        for fn, rows, index, col, value in cases:
            rows[index][col] = value
            with self.assertRaises(ValueError, msg=(fn.__name__, index, col)):
                fn(rows)
        tampered = deepcopy(leader)
        tampered[7][33] = "0"
        with self.assertRaises(ValueError):
            M.leader_rows(tampered)
        with self.assertRaises(ValueError):
            M.leader_rows(self.live("leader", M.CID)[:-1])
        with self.assertRaises(ValueError):
            M.ability3_rows(self.live("ability", M.A3)[:-1])
        text = self.live("cas", M.CAS_LEADER)[0][0].replace("＋50%", "＋40%")
        with self.assertRaises(ValueError):
            M.leader_text(text)
        text = self.live("cas", M.CAS_A1)[0][0].replace("＋3%", "＋5%")
        with self.assertRaises(ValueError):
            M.ability1_text(text)
        text = self.live("cas", M.CAS_A3)[0][0].replace("＋30%、", "＋50%、")
        with self.assertRaises(ValueError):
            M.ability3_text(text)


class GeneratorConsistencyTest(unittest.TestCase):
    """生成器：kit 改版计划回放 → 09-17 灯火修订纯函数 → 第二批，产物必须 == revise()。"""

    @classmethod
    def setUpClass(cls):
        cls.data, cls.kit = load()
        cls.out = M.revise(reader(cls.data))

    def test_kit_then_lamp_reproduces_live_before_balance(self):
        a1, a3 = R.revise_rows(deepcopy(self.kit[M.A1]), deepcopy(self.kit[M.A3]))
        self.assertEqual(self.kit["leader"], self.data["leader", M.CID])
        self.assertEqual((a1, a3), (self.data["ability", M.A1], self.data["ability", M.A3]))
        for slot, key in ((1, M.CAS_A1), (3, M.CAS_A3)):
            self.assertEqual(R.revise_text(slot, self.kit["texts"][key]), self.data["cas", key][0][0])
        from wf_seasonal_pf_revision import ZEHR_LEADER_TEXT
        self.assertEqual(ZEHR_LEADER_TEXT, self.data["cas", M.CAS_LEADER][0][0])

    def test_kit_lamp_balance_chain_matches_revise(self):
        from wf_seasonal_pf_revision import ZEHR_LEADER_TEXT
        a1, a3 = R.revise_rows(deepcopy(self.kit[M.A1]), deepcopy(self.kit[M.A3]))
        leader, a1, a3 = M.balance_rows(deepcopy(self.kit["leader"]), a1, a3)
        self.assertEqual(leader, self.out["leader"][M.CID])
        self.assertEqual({M.A1: a1, M.A3: a3}, self.out["ability"])
        texts = M.panel_texts({M.CAS_LEADER: ZEHR_LEADER_TEXT,
                               **{key: R.revise_text(slot, self.kit["texts"][key])
                                  for slot, key in ((1, M.CAS_A1), (3, M.CAS_A3))}})
        self.assertEqual({key: [[text]] for key, text in texts.items()}, self.out["cas"])

    def test_kit_build_applies_batch2_after_lamp(self):
        src = inspect.getsource(K.build)
        lamp = src.index("lamp_rows(")
        batch = src.index("balance_b.balance_rows(")
        self.assertLess(lamp, batch)
        self.assertLess(src.index("revise_text(slot"), src.index("balance_b.panel_texts("))
        self.assertIn("balance_b.CAS_LEADER: ZEHR_LEADER_TEXT", src)
        self.assertLess(batch, src.index('ctx.write_flat(LEADER, {CID: rows["leader"]})', batch))
        tail = src[batch:]
        self.assertIn("(balance_b.CAS_LEADER, balance_b.CAS_A1, balance_b.CAS_A3)", tail)
        self.assertIn("wf_balance_20260927b_zehr", K.__doc__)

    def test_rerunning_lamp_revision_does_not_revert_batch2(self):
        a1, a3 = self.out["ability"][M.A1], self.out["ability"][M.A3]
        self.assertEqual(R.revise_rows(a1, a3), (a1, a3))
        for slot, key in ((1, M.CAS_A1), (3, M.CAS_A3)):
            text = self.out["cas"][key][0][0]
            self.assertEqual(R.revise_text(slot, text), text)

    def test_kit_rows_fixture_matches_live_kit_replay(self):
        try:
            pass  # Imports resolve from this checkout/package, not external source copies.
            import test_seasonal7_kit_zehr as T
            ctx = T._context()
        except unittest.SkipTest:
            raise
        except Exception as exc:                                     # 没有 live profile / 官方基线的机器
            self.skipTest(f"live store / official baseline unavailable: {exc}")
        if not (ctx.root / K.REVISION_REL).is_file():
            self.skipTest("seasonal7 revision plan (gitignored work/) absent")
        plan = K.load_revision(ctx.root)
        rows, _ = K.build_rows(ctx, plan)
        self.assertEqual(rows["leader"], self.kit["leader"])
        self.assertEqual(rows["ability"][M.A1], self.kit[M.A1])
        self.assertEqual(rows["ability"][M.A3], self.kit[M.A3])
        texts = plan["texts"]["custom_ability_string"]
        for key in (M.CAS_A1, M.CAS_A3):
            self.assertEqual(K.rev4_panel_text(key, texts[key]["value"]), self.kit["texts"][key])


class DonorPinTest(unittest.TestCase):
    """澄波响 kit 以 live 1599971#4 为 donor：本批改的每一格都被显式钉住 ⇒ 产物不随本批漂移。"""

    def test_hibiki_pins_every_changed_cell(self):
        import wf_midautumn_kit_hibiki as H
        data, _ = load()
        old = data["ability", M.A1][M.A1_WICK_INDEX]
        new = M.revise(reader(data))["ability"][M.A1][M.A1_WICK_INDEX]
        changed = set(diff_cells(old, new))
        self.assertEqual(changed, {102, 113, 114})
        entries = [e for block in H.PLAN.values() for e in block if e[0] == "1599971#4"]
        self.assertTrue(entries)
        for donor, source, cells, expect in entries:
            self.assertEqual(source, "live")
            pinned = {int(c) for c in cells}
            self.assertLessEqual(changed, pinned)
            self.assertEqual(KL.apply_cells(old, cells, KL.ABILITY_NCOLS),
                             KL.apply_cells(new, cells, KL.ABILITY_NCOLS))
            if expect is not None:
                self.assertEqual(D.describe_line(KL.apply_cells(new, cells, KL.ABILITY_NCOLS), "ability"), expect)

    def test_no_other_donor_uses_changed_rows(self):
        refs = ("1599971#4", "1599973#0", "1599973#3", "1599971#L5", "1599973#L1", "1599973#L4",
                "159997#3", "159997#4", "159997#L4", "159997#L5")
        hits = {}
        for path in (ROOT / "mod-tools").glob("*.py"):
            if path.name in ("wf_balance_20260927b_zehr.py", "wf_midautumn_kit_hibiki.py"):
                continue
            text = path.read_text(encoding="utf-8")
            found = [r for r in refs if any(f"{r}{end}" in text for end in ('"', "'", ",", " ", ")"))]
            if found:
                hits[path.name] = found
        self.assertEqual(hits, {})


if __name__ == "__main__":
    unittest.main()
