# -*- coding: utf-8 -*-
"""凯尔 139990 ``kyle_moon`` 2026-09-27 平衡批次（方案A：去掉 Down 效果成长）。

fixture = live 输入快照（``fixtures/balance_20260927_kyle.json``），驱动 ``revise()``：
每处删改、未改行逐字保留、BEFORE 漂移拒绝、不改输入、合法性门禁为空、生成器一致。
生成器装配对比需要 ``.cdn/cn`` 官方基线与 live store（缺时跳过）。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927_kyle as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_midautumn_kit_kyle as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927_kyle.json'
TABLE_KIND = {"leader": "leader_ability", "ability": "ability"}


def load_fixture() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {kind: value for kind, value in data.items() if not kind.startswith("_")}


def reader(data: dict):
    def read(kind, key):
        return data[kind][key]
    return read


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys},
                         set(M.BEFORE))

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), (str(K.CID), K.CODE))
        self.assertEqual(M.PACKAGES, ["ma-kyle"])
        self.assertEqual(M.PACKAGE_VERSION, {"ma-kyle": "1.0.2"})   # 候选现值 1.0.1，只升不降
        self.assertEqual(M.CAPABILITIES, [])

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["leader"]), {M.CID})
        self.assertEqual(set(out["ability"]), {M.ABILITY_KEY})
        self.assertEqual(set(out["cas"]), {M.CAS_LEADER, M.CAS_ABILITY5})
        for kind in ("text", "table", "action", "dsl", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        json.dumps(out["notes"], ensure_ascii=False)
        for key in out["cas"]:   # RevisionCandidate 命名空间
            self.assertTrue(key.startswith("desc_override_" + M.CODE), key)

    def test_leader_drops_only_the_crescent_stunify_row(self):
        old, new = self.live["leader"][M.CID], self.out["leader"][M.CID]
        self.assertEqual((len(old), len(new)), (10, 9))
        self.assertEqual(new, old[:4] + old[5:])
        removed = old[4]
        self.assertEqual((removed[95], removed[102], removed[107], removed[111]),
                         ("134", M.UID_CRESCENT, "19", "25000"))
        self.assertFalse([r for r in new if r[107] in ("19", "51") or r[45] in ("19", "51")])
        # 第 9 行（贯穿 → 雷队眩晕畏缩特攻 5%）保留：现为 #7
        pierce = [r for r in new if r[25] == "51"]
        self.assertEqual({r[45]: r[49:51] for r in pierce},
                         {"32": ["25000", "25000"], "53": ["5000", "5000"]})
        self.assertEqual(new[7][45], "53")
        # 月牙其余 4 条 during 134 成长不动
        self.assertEqual([(r[107], r[108], r[111]) for r in new if r[95] == "134"],
                         [("0", "5", "12500"), ("0", "0", "12500"),
                          ("1", "5", "25000"), ("1", "0", "25000")])

    def test_ability5_drops_only_the_direct_hit_stunify_row(self):
        old, new = self.live["ability"][M.ABILITY_KEY], self.out["ability"][M.ABILITY_KEY]
        self.assertEqual((len(old), len(new)), (7, 6))
        self.assertEqual(new, old[:1] + old[2:])
        self.assertEqual((old[1][27], old[1][30], old[1][47], old[1][48], old[1][51]),
                         ("20", "5000000", "51", "5", "100000"))
        gauge = new[0]   # 同触发的充能 +5% 自带完整触发块，保留
        self.assertEqual((gauge[6], gauge[27], gauge[30], gauge[31], gauge[34]),
                         ("2", "20", "5000000", "5000000", "(None)"))
        self.assertEqual((gauge[47], gauge[48], gauge[49], gauge[51]), ("35", "5", "Yellow", "5000"))
        self.assertEqual([r[47] for r in new if r[27] == "20"], ["35"])
        self.assertEqual({r[1] for r in new}, {"true"})             # 仍非主位限制
        self.assertEqual(sorted(r[118] for r in new if r[109] == "422"), ["0", "0", "1", "6"])
        self.assertFalse([r for r in new if r[47] in ("19", "51") or r[109] in ("19", "51")])

    def test_leader_panel_drops_only_the_down_clause(self):
        old = self.live["cas"][M.CAS_LEADER][0][0].split("\n")
        new_rows = self.out["cas"][M.CAS_LEADER]
        self.assertEqual(len(new_rows), 1)
        self.assertEqual(len(new_rows[0]), 1)
        new = new_rows[0][0].split("\n")
        self.assertEqual(len(new), 6)
        self.assertEqual(new[3], "雷属性共鸣时：自身“月牙”每上升1层，自身攻击力＋25%、直击伤害＋50%、"
                                 "直击判定次数＋1；除自身外雷属性角色攻击力＋12.5%、直击伤害＋25%")
        self.assertEqual(new[:3] + new[4:], old[:3] + old[4:])
        self.assertIn("追击伤害＋5%", new[4])
        self.assertNotIn("Down", new_rows[0][0])

    def test_ability5_panel_keeps_only_the_gauge_clause(self):
        self.assertEqual(self.out["cas"][M.CAS_ABILITY5],
                         [["雷属性共鸣时：雷属性角色每造成50次直击，雷属性角色技能充能速度＋5%"]])

    def test_panel_texts_obey_the_project_rules(self):
        for key, rows in self.out["cas"].items():
            text = rows[0][0]
            self.assertNotIn("／", text)
            self.assertNotIn("击倒", text)
            for line in text.split("\n"):
                self.assertEqual(KL.panel_problems(line), [], f"{key}: {line}")
                self.assertFalse(line.startswith(K.MAIN_ICON), "能力5/队长不是主位限制槽")

    def test_native_legality_gates_are_empty(self):
        cas_keys = set(K.CAS_TEXTS)
        for kind in ("leader", "ability"):
            table = TABLE_KIND[kind]
            for key, rows in self.out[kind].items():
                for index, row in enumerate(rows):
                    label = f"{kind}:{key}#{index}"
                    self.assertEqual(L.client_legality_problems(table, row), [], label)
                    self.assertEqual(L.declared_block_field_problems(table, row), [], label)
                    self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, kind=table), [], label)
                    self.assertEqual(KL.row_problems(table, row, K.ELEMENT), {}, label)

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["leader"][M.CID][0][0] = "mutated"
        out["ability"][M.ABILITY_KEY][0][0] = "mutated"
        self.assertEqual(data, self.live)

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            data = deepcopy(self.live)
            if kind == "cas":
                data[kind][key][0][0] += "。"
            else:
                data[kind][key][-1][1] = "drift"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))
            data = deepcopy(self.live)
            data[kind][key] = data[kind][key][:-1]
            with self.assertRaises(ValueError):
                M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        """重跑在已删除的 live 上必须拒绝（fail closed），而不是再删一行。"""
        data = deepcopy(self.live)
        for kind in ("leader", "ability", "cas"):
            data[kind].update(deepcopy(self.out[kind]))
        with self.assertRaises(ValueError):
            M.revise(reader(data))
        with self.assertRaises(ValueError):
            M.leader_rows(self.out["leader"][M.CID])
        with self.assertRaises(ValueError):
            M.ability5_rows(self.out["ability"][M.ABILITY_KEY])
        with self.assertRaises(ValueError):
            M.leader_text(self.out["cas"][M.CAS_LEADER])
        with self.assertRaises(ValueError):
            M.ability5_text(self.out["cas"][M.CAS_ABILITY5])

    def test_row_locators_are_content_based(self):
        old = deepcopy(self.live["leader"][M.CID])
        moved = old[:3] + [old[4], old[3]] + old[5:]           # 目标行不在 #4
        with self.assertRaises(ValueError):
            M.leader_rows(moved)
        changed = deepcopy(old)
        changed[4][111] = changed[4][112] = "30000"            # 数值漂移
        with self.assertRaises(ValueError):
            M.leader_rows(changed)
        ability = deepcopy(self.live["ability"][M.ABILITY_KEY])
        ability[0][51] = ability[0][52] = "6000"                # 保留行被改也要红
        with self.assertRaises(ValueError):
            M.ability5_rows(ability)


def batch2_overlay(out: dict) -> dict:
    """第一批输出 + 第二批覆盖：生成器现在产出的是两批依次施工后的结果（第二批 wf_balance_20260927b_kyle
    的 BEFORE 锁定的正是第一批输出，见其 ChainTests），第一批只核对自己那部分仍由第二批原样继承。
    2026-09-27 第三轮（wf_balance_20260927c_kyle，BEFORE 锁定第二批输出）再覆盖队长 / 队长面板 / 追击树。"""
    import wf_balance_20260927b_kyle as M2
    import wf_balance_20260927c_kyle as M3
    fixture = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_kyle.json'
    live2 = {k: v for k, v in json.loads(fixture.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    assert live2["leader"][M.CID] == out["leader"][M.CID] and live2["cas"][M.CAS_LEADER] == out["cas"][M.CAS_LEADER]
    out2 = M2.revise(reader(deepcopy(live2)))
    for kind in ("leader", "ability", "cas", "dsl"):
        live2[kind].update(deepcopy(out2[kind]))
    # 第三轮面板合并补读、前两批不涉及的键（desc_override_kyle_moon_3）取第三轮 fixture（= live）
    fixture3 = json.loads((Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927c_kyle.json').read_text(encoding="utf-8"))
    for kind, key in M3.BEFORE:
        live2.setdefault(kind, {}).setdefault(key, deepcopy(fixture3[kind][key]))
    out3 = M3.revise(reader(live2))
    for kind in ("leader", "ability", "cas", "dsl"):
        out2[kind].update(out3[kind])
    return out2


class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_midautumn_kit_kyle 重跑不能把本次删掉的行/文案加回去。

    2026-09-27 第二批改了同一生成器（队长月牙/贯穿成长数值、队长面板）：相关断言改为
    「第一批输出 + 第二批覆盖」（:func:`batch2_overlay`）；能力 5 第二批不动，仍直接比第一批输出。
    """

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.out2 = batch2_overlay(cls.out)

    def test_panel_constants_equal_revise_output(self):
        # 第二批覆盖队长面板；第一批删去的 Down 文案在覆盖后仍不存在
        self.assertEqual([[K.PANEL_LEADER]], self.out2["cas"][M.CAS_LEADER])
        self.assertNotIn(M.REMOVED_LEADER_PHRASE, K.PANEL_LEADER)
        self.assertNotIn("Down", K.PANEL_LEADER)
        self.assertEqual([[K.PANEL_ABILITY[5]]], self.out["cas"][M.CAS_ABILITY5])
        self.assertEqual(K.CAS_TEXTS[M.CAS_LEADER], K.PANEL_LEADER)
        self.assertEqual(K.CAS_TEXTS[M.CAS_ABILITY5], K.PANEL_ABILITY[5])

    def test_plan_no_longer_writes_stunify(self):
        self.assertFalse([c for _a, _s, c, _e in K.LEADER if c.get(107) in ("19", "51")])
        self.assertFalse([c for _a, _s, c, _e in K.PLAN[5] if c.get(47) in ("19", "51")])
        self.assertEqual(len(K.LEADER), 6)
        self.assertEqual(len(K.PLAN[5]), 6)
        self.assertFalse([v for v in K.EXPECT.values() if "眩晕蓄积" in v])
        self.assertEqual(sorted(k for k in K.EXPECT if k.startswith("leader#")),
                         [f"leader#{i}" for i in range(8)])
        self.assertEqual(sorted(k for k in K.EXPECT if k.startswith(M.ABILITY_KEY)),
                         [f"{M.ABILITY_KEY}#{i}" for i in range(6)])
        # 第二批把贯穿成长 ×1/10（5% → 0.5%），第三轮改为 ×4/5（→ 4%）；第一批的「保留这一行」仍成立
        self.assertIn("眩晕畏缩特攻 4%", K.EXPECT["leader#7"])

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_rows_equal_revise_output(self):
        import wf_midautumn_common as MC
        import wf_midautumn_specs as MS
        import wf_seasonal7_build as B
        built = K.build_rows(B.KitContext(MC.MAPack(MS.get_spec("kyle"), record_sources=False)))
        self.assertEqual(built["leader"], self.out2["leader"][M.CID])          # 第一批输出 + 第二批 / 第三轮覆盖
        self.assertEqual(built["ability"][M.ABILITY_KEY], self.out["ability"][M.ABILITY_KEY])


class MirrorTests(unittest.TestCase):
    PATHS = (ROOT / M.DESIGN_REL, ROOT / M.PANEL_REL, ROOT / M.DEVIATIONS_REL)

    def setUp(self):
        if not all(path.is_file() for path in self.PATHS):
            self.skipTest("midautumn design mirrors missing")
        self.docs = [json.loads(path.read_text(encoding="utf-8")) for path in self.PATHS]
        # 第三轮（wf_balance_20260927c_kyle）改了同一生成器的队长面板；镜像由主会话 --write 落盘，
        # 落盘前在内存里补上（第三轮 mirror_updates 幂等，已落盘时为恒等）。
        import wf_balance_20260927c_kyle as M3
        self.docs[:2] = M3.mirror_updates(*self.docs[:2])

    def test_mirrors_are_already_synced(self):
        self.assertEqual(M.mirror_updates(*self.docs), tuple(self.docs))
        design, panel, deviations = self.docs
        self.assertEqual(K._design_problems(design), [])
        self.assertEqual([line["text"] for line in panel["leader"]["lines"]],
                         K.PANEL_LEADER.split("\n"))
        five = next(entry for entry in panel["abilities"] if entry["index"] == 5)
        self.assertEqual([line["text"] for line in five["lines"]], [M.NEW_ABILITY5_TEXT])
        voided = [e for e in deviations["kyle"] if M.DOWN_DEVIATION_WORD in e["原话"]]
        self.assertEqual(len(voided), 1)
        self.assertTrue(voided[0]["作废"].startswith("2026-09-27"))
        self.assertIn("revoked", design["plan"]["rework1"]["crescent_stunify_20260923"])

    def test_mirror_update_is_idempotent_and_pure(self):
        before = deepcopy(self.docs)
        once = M.mirror_updates(*self.docs)
        self.assertEqual(self.docs, before)
        self.assertEqual(M.mirror_updates(*once), once)

    def test_down_deviation_must_be_unique(self):
        with self.assertRaises(ValueError):
            M._void_down_deviation([])
        entry = {"原话": M.DOWN_DEVIATION_WORD + "+100%", "落法": "x"}
        with self.assertRaises(ValueError):
            M._void_down_deviation([entry, dict(entry)])


if __name__ == "__main__":
    unittest.main()
