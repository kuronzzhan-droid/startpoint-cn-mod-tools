# -*- coding: utf-8 -*-
"""黑 139991 ``outlaw_panther_moon`` 2026-09-27 平衡第二批：无上限成长（技能命中 / 进入 Fever）。

fixture = live 输入快照（``fixtures/balance_20260927b_kuro.json``，BEFORE = make_read 返回值的摘要），
驱动 ``revise()``：每处改动的前后值、未改行逐字保留、trigger 107 不进队长表（能力行 + 前置 42 承载）、
面板与数据一致且守面板规则、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、合法性门禁为空、
生成器装配 == revise() 输出、设计镜像已同步。生成器装配与先例扫描需要 .cdn/cn 官方基线与 live store。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_kuro as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_midautumn_kit_kuro as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927b_kuro.json"
MANIFEST = ROOT / "work/character_packs/ma-kuro/package/manifest.json"


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


def batch3_overlay(live: dict, out: dict) -> dict:
    """第二批输出 + 第三轮覆盖（wf_balance_20260927c_kuro：能力2#3 5%→35%、队长#4 30%→105%、队长面板两行；
    第 6 节作者追加：能力2#0 封顶版 2%×25 → 5%×25、能力2 面板第 1 行）。
    生成器现在产出的是两批依次施工后的结果（第三轮 BEFORE 锁定的正是第二批输出，见其 ChainTests），
    第二批的生成器一致性断言改比这份叠加结果；第三轮没碰的键仍直接等于第二批输出。"""
    import wf_balance_20260927c_kuro as M3
    live3 = deepcopy(live)
    for kind in ("leader", "ability", "cas"):
        live3[kind].update(deepcopy(out[kind]))
    # 第三轮面板合并补读、第二批不涉及的键（能力6 行 / 能力6 面板）取第三轮 fixture（= live）
    fixture3 = json.loads((Path(__file__).parent / "fixtures/balance_20260927c_kuro.json").read_text(encoding="utf-8"))
    for kind, key in M3.BEFORE:
        live3.setdefault(kind, {}).setdefault(key, deepcopy(fixture3[kind][key]))
    out3 = M3.revise(reader(live3))
    merged = deepcopy(out)
    for kind in ("leader", "ability", "cas"):
        merged[kind].update(deepcopy(out3[kind]))
    return merged


_CTX = None


def ctx():
    global _CTX
    if _CTX is None:
        import wf_midautumn_common as MC
        import wf_midautumn_specs as MS
        import wf_seasonal7_build as B
        _CTX = B.KitContext(MC.MAPack(MS.get_spec(K.KEY), record_sources=False))
    return _CTX


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old2, cls.new2 = cls.live["ability"][M.ABILITY2_KEY], cls.out["ability"][M.ABILITY2_KEY]
        cls.old3, cls.new3 = cls.live["ability"][M.ABILITY3_KEY], cls.out["ability"][M.ABILITY3_KEY]
        cls.old_leader, cls.new_leader = cls.live["leader"][M.LEADER_KEY], cls.out["leader"][M.LEADER_KEY]

    # ------------------------------------------------------------ 契约

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys},
                         set(M.BEFORE))

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE, M.ELEMENT, M.ELEMENT_TOKEN),
                         (K.CID_S, K.CODE, K.ELEMENT, K.ELEMENT_TOKEN))
        self.assertEqual((M.CAS_LEADER, M.CAS_ABILITY2, M.CAS_ABILITY3),
                         (K.CAS_LEADER, K.CAS_ABILITY[2], K.CAS_ABILITY[3]))
        self.assertEqual(M.MAIN_ICON, K.MAIN_ICON)
        self.assertEqual(M.PACKAGES, ["ma-kuro"])
        self.assertEqual(M.PACKAGE_VERSION, {"ma-kuro": "1.0.2"})      # 候选现值 1.0.1，只升不降
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["ability"]), {M.ABILITY2_KEY, M.ABILITY3_KEY})
        self.assertEqual(set(out["leader"]), {M.LEADER_KEY})
        self.assertEqual(set(out["cas"]), {M.CAS_LEADER, M.CAS_ABILITY2, M.CAS_ABILITY3})
        for kind in ("text", "table", "action", "dsl", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        for key in out["cas"]:                                          # RevisionCandidate 命名空间
            self.assertTrue(key.startswith("desc_override_" + M.CODE), key)
        json.dumps(out["notes"], ensure_ascii=False)

    # ------------------------------------------------------------ 能力2：技能命中

    def test_skill_hit_row_is_capped_at_25(self):
        self.assertEqual((len(self.old2), len(self.new2)), (3, 4))
        self.assertEqual(self.new2[1:3], self.old2[1:3])                # 豹步两行逐字不动
        old, new = self.old2[0], self.new2[0]
        self.assertEqual([i for i in range(126) if old[i] != new[i]], [34, 51, 52])
        self.assertEqual([old[34], old[51], old[52]], ["(None)", "50000", "50000"])
        self.assertEqual([new[34], new[51], new[52]], ["25", "2000", "2000"])
        self.assertEqual(int(new[34]) * int(new[51]), 50000)            # 满 25 次 = 50%
        self.assertEqual((new[27], new[28], new[47], new[48]), ("107", "0", "32", "2"))
        self.assertEqual(D.describe_line(new, "ability"),
                         "雷·编成≥6 时: 技能Hit≥1(限25次) → 赋予队长 攻击力 2%")

    def test_uncapped_hit_growth_lives_in_a_leader_gated_ability_row(self):
        """口径 A4：trigger 107 队长表零先例 ⇒ 能力行 + 前置 42（仅队长时），不进队长表。"""
        row, source = self.new2[3], self.old2[0]
        self.assertEqual(sorted(i for i in range(126) if row[i] != source[i]),
                         [6, 9, 10, 11, 13, 16, 17, 18, 48, 51, 52])
        self.assertEqual(row[6:13], ["42", "", "", "", "", "", ""])     # 前置1 = 42 Leader（官方写法）
        self.assertEqual(row[13:20], ["2", "", "", "600000", "600000", "Yellow", ""])   # 前置2 雷共鸣
        self.assertEqual(row[20], "0")
        self.assertEqual((row[27], row[28], row[34], row[35]), ("107", "0", "(None)", "0"))
        self.assertEqual((row[47], row[48], row[51], row[52]), ("32", "0", "5000", "5000"))
        self.assertEqual(int(source[51]), 10 * int(row[51]))            # 3 分钟 105–135 hit ⇒ 1/10
        self.assertEqual(row[1], self.old2[0][1])                       # 整键 c1/c2 一致
        self.assertEqual(row[2], self.old2[0][2])
        self.assertEqual(D.describe_line(row, "ability"), "队长 且 雷·编成≥6 时: 技能Hit≥1 → 自身 攻击力 5%")
        self.assertFalse([r for r in self.new_leader if "107" in (r[25], r[95])])

    # ------------------------------------------------------------ 能力3 / 队长：进入 Fever

    def test_fever_row_is_capped_at_three(self):
        self.assertEqual(len(self.new3), 4)
        self.assertEqual([i for i, (a, b) in enumerate(zip(self.old3, self.new3)) if a != b], [1])
        old, new = self.old3[1], self.new3[1]
        self.assertEqual([i for i in range(126) if old[i] != new[i]], [34, 51, 52])
        self.assertEqual([new[34], new[51], new[52]], ["3", "40000", "40000"])
        self.assertEqual(int(new[34]) * int(new[51]), 120000)           # 满 3 次 = 120%
        self.assertEqual((new[1], new[27], new[47], new[48], new[49]), ("false", "8", "33", "5", "Yellow"))
        self.assertEqual(D.describe_line(new, "ability"), "Fever≥1(限3次) → 赋予全队(雷) Direct伤害 40%")

    def test_uncapped_fever_growth_moves_to_the_leader(self):
        self.assertEqual((len(self.old_leader), len(self.new_leader)), (4, 5))
        self.assertEqual(self.new_leader[:4], self.old_leader)
        row, source = self.new_leader[4], self.old3[1]
        self.assertEqual(row[:3], [M.CODE, "0", ""])
        for col in range(5, 126):                                       # 能力 c≥5 → 队长 c−2
            if col - 2 in (49, 50):
                continue
            self.assertEqual(row[col - 2], source[col], f"ability c{col} -> leader c{col - 2}")
        self.assertEqual([row[49], row[50]], ["30000", "30000"])
        self.assertEqual(int(source[51]), 5 * int(row[49]))              # 3 分钟 8–12 次 ⇒ 1/5
        self.assertEqual((row[25], row[26], row[32], row[33], row[45], row[46], row[47]),
                         ("8", "", "(None)", "0", "33", "5", "Yellow"))
        self.assertEqual(D.describe_line(row, "leader_ability"), "Fever≥1 → 赋予全队(雷) Direct伤害 30%")
        # 不合并：队长 #0 是持续 Fever → 直击（during 4），触发不同
        self.assertEqual((self.new_leader[0][3], self.new_leader[0][95]), ("1", "4"))

    def test_native_legality_gates_are_empty(self):
        rows = [("leader_ability", f"leader#{i}", r) for i, r in enumerate(self.new_leader)]
        rows += [("ability", f"{key}#{i}", r) for key, rs in self.out["ability"].items()
                 for i, r in enumerate(rs)]
        for kind, label, row in rows:
            self.assertEqual(L.client_legality_problems(kind, row), [], label)
            self.assertEqual(L.declared_block_field_problems(kind, row), [], label)
            self.assertEqual(L.invoke_skill_string_problems(row, set(), kind=kind), [], label)
            self.assertEqual(L.ability_element_column_problems(kind, row, M.ELEMENT), [], label)
        self.assertEqual(L.required_client_capabilities("leader_ability", self.new_leader[4]), [])
        self.assertEqual(L.required_client_capabilities("ability", self.new2[3]), [])
        self.assertEqual(L.required_client_capabilities("ability", self.new3[1]), [])

    # ------------------------------------------------------------ 面板

    def test_panels_change_only_the_three_places(self):
        old = self.live["cas"][M.CAS_LEADER][0][0].split("\n")
        new = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertEqual(new, old + list(M.LEADER_ADDED_LINES))
        old = self.live["cas"][M.CAS_ABILITY2][0][0].split("\n")
        new = self.out["cas"][M.CAS_ABILITY2][0][0].split("\n")
        self.assertEqual(new, [M.NEW_ABILITY2_LINE, old[1]])
        old = self.live["cas"][M.CAS_ABILITY3][0][0].split("\n")
        new = self.out["cas"][M.CAS_ABILITY3][0][0].split("\n")
        self.assertEqual([i for i, (a, b) in enumerate(zip(old, new)) if a != b], [1])
        self.assertEqual(new[1], M.NEW_ABILITY3_LINE)
        for rows in self.out["cas"].values():
            self.assertEqual((len(rows), len(rows[0])), (1, 1))

    def test_panels_agree_with_the_data(self):
        leader = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertEqual(leader[4], f"雷属性共鸣时，自身技能每命中1次，自身攻击力＋{int(self.new2[3][51]) // 1000}%")
        self.assertEqual(leader[5], f"每次进入Fever：雷属性角色直击伤害＋{int(self.new_leader[4][49]) // 1000}%")
        hit = self.new2[0]
        self.assertEqual(M.NEW_ABILITY2_LINE,
                         f"雷属性共鸣时，自身技能每命中1次，队长攻击力＋{int(hit[51]) // 1000}%，最多{hit[34]}次")
        fever = self.new3[1]
        self.assertEqual(M.NEW_ABILITY3_LINE, M.MAIN_ICON
                         + f"每次进入Fever：雷属性角色直击伤害＋{int(fever[51]) // 1000}%，最多{fever[34]}次")

    def test_new_lines_follow_the_character_style(self):
        """口径 D：共鸣写「X属性共鸣时，」；上限按该角色现有写法——黑的骰运行是「，最多6层」（无括号）。"""
        ability3 = self.live["cas"][M.CAS_ABILITY3][0][0]
        self.assertIn("自身「骰运」＋1层，最多6层", ability3)                   # 现有写法
        written = (*M.LEADER_ADDED_LINES, M.NEW_ABILITY2_LINE, M.NEW_ABILITY3_LINE)
        for line in written:
            self.assertNotIn("（最多", line, line)
            self.assertNotIn("属性共鸣时：", line, line)
        self.assertTrue(M.NEW_ABILITY2_LINE.endswith("，最多25次"))
        self.assertTrue(M.NEW_ABILITY3_LINE.endswith("，最多3次"))
        self.assertTrue(M.LEADER_ADDED_LINES[0].startswith("雷属性共鸣时，"))

    def test_panels_obey_the_project_rules(self):
        for key, rows in self.out["cas"].items():
            for line in rows[0][0].split("\n"):
                self.assertEqual(KL.panel_problems(line.replace(M.MAIN_ICON, "")), [], f"{key}: {line}")
                for word in ("自身为队长时", "觉醒后", "可无限", "无上限", "生命值100%以下"):
                    self.assertNotIn(word, line)
        for line in (*M.LEADER_ADDED_LINES, M.NEW_ABILITY2_LINE, M.NEW_ABILITY3_LINE):
            self.assertNotIn("／", line)                              # 换行分行，不用「／」挤一行
        for line in self.out["cas"][M.CAS_ABILITY3][0][0].split("\n"):
            self.assertTrue(line.startswith(M.MAIN_ICON), line)       # 主位限制槽每行带 Ⓜ
        for key in (M.CAS_LEADER, M.CAS_ABILITY2):
            for line in self.out["cas"][key][0][0].split("\n"):
                self.assertFalse(line.startswith(M.MAIN_ICON), line)

    # ------------------------------------------------------------ fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["ability"][M.ABILITY2_KEY][0][51] = "mutated"
        out["leader"][M.LEADER_KEY][0][0] = "mutated"
        out["cas"][M.CAS_LEADER][0][0] = "mutated"
        self.assertEqual(data, self.live)

    def test_baseline_drift_is_rejected(self):
        for kind, key, mutate in (
                ("leader", M.LEADER_KEY, lambda v: v.append(list(v[0]))),
                ("ability", M.ABILITY2_KEY, lambda v: v[0].__setitem__(34, "10")),
                ("ability", M.ABILITY3_KEY, lambda v: v[1].__setitem__(51, "100000")),
                ("cas", M.CAS_LEADER, lambda v: v[0].__setitem__(0, v[0][0] + "\nx")),
                ("cas", M.CAS_ABILITY2, lambda v: v[0].__setitem__(0, "x")),
                ("cas", M.CAS_ABILITY3, lambda v: v[0].__setitem__(0, "x"))):
            data = deepcopy(self.live)
            mutate(data[kind][key])
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline", msg=f"{kind}:{key}"):
                M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        data = deepcopy(self.live)
        for kind in ("leader", "ability", "cas"):
            data[kind].update(deepcopy(self.out[kind]))
        with self.assertRaises(ValueError):
            M.revise(reader(data))
        with self.assertRaises(ValueError):
            M.ability2_rows(self.new2)
        with self.assertRaises(ValueError):
            M.ability3_rows(self.new3)
        with self.assertRaises(ValueError):
            M.leader_rows(self.new_leader[:4] + [], self.new3)
        with self.assertRaises(ValueError):
            M.leader_text(self.out["cas"][M.CAS_LEADER])
        with self.assertRaises(ValueError):
            M.ability2_text(self.out["cas"][M.CAS_ABILITY2])
        with self.assertRaises(ValueError):
            M.ability3_text(self.out["cas"][M.CAS_ABILITY3])

    def test_row_locators_are_content_based(self):
        for mutate in (lambda r: r[0].__setitem__(48, "5"),
                       lambda r: r[0].__setitem__(80, "x"),
                       lambda r: r.pop()):
            rows = deepcopy(self.old2)
            mutate(rows)
            with self.assertRaises(ValueError):
                M.ability2_rows(rows)
        for mutate in (lambda r: r[1].__setitem__(27, "12"),
                       lambda r: r.insert(0, list(r[0]))):
            rows = deepcopy(self.old3)
            mutate(rows)
            with self.assertRaises(ValueError):
                M.ability3_rows(rows)
        leader = deepcopy(self.old_leader)
        leader.append(list(leader[0]))
        with self.assertRaises(ValueError):
            M.leader_rows(leader, self.old3)


@unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_midautumn_kit_kuro 的行装配（官方 donor + 逐格改）== revise() 输出。

    2026-09-27 第三轮（wf_balance_20260927c_kuro）改了同一生成器的队长#4 / 能力2#0、#3 / 队长面板 / 能力2 面板：
    改比「第二批输出 + 第三轮覆盖」（:func:`batch3_overlay`）；第三轮没碰的键仍等于第二批输出。
    """

    @classmethod
    def setUpClass(cls):
        live = load_fixture()
        cls.out = batch3_overlay(live, M.revise(reader(deepcopy(live))))

    def test_generator_rows_equal_revise_output(self):
        leader = [KL.build_row(ctx(), "leader_ability", donor, cells, expect_describe=expect)[0]
                  for donor, cells, expect in K.LEADER]
        self.assertEqual(leader, self.out["leader"][M.LEADER_KEY])
        for key in (M.ABILITY2_KEY, M.ABILITY3_KEY):
            rows = []
            for donor, cells, expect in K.ABILITY[key]:
                source, _, donor_key = donor.partition("live:")
                source, donor_key = ("live", donor_key) if donor_key else ("official", source)
                rows.append(KL.build_row(ctx(), "ability", donor_key, cells, source=source,
                                         element=K.ELEMENT, expect_describe=expect)[0])
            self.assertEqual(rows, self.out["ability"][key], key)

    def test_generator_panel_equals_revise_output(self):
        for key, rows in self.out["cas"].items():
            self.assertEqual(K.CAS_TEXTS[key], rows[0][0], key)
        # 队长面板前 4 行 + 追加 2 行（第三轮改追加两行的数字，并把前两行同条件合并成一行：拆回后比）
        import wf_balance_20260927c_kuro as M3
        unmerged = tuple(x for line in K.PANEL_LEADER for x in M3.MERGED_LINES.get(line, (line,)))
        self.assertEqual(unmerged[:len(M.LEADER_PANEL_BEFORE)], M.LEADER_PANEL_BEFORE)
        self.assertEqual(len(unmerged), len(M.LEADER_PANEL_BEFORE) + len(M.LEADER_ADDED_LINES))

    def test_leader_precedents(self):
        """队长 trigger 8 / 瞬发 kind 33 target 5 各有官方先例（逐列）；二者组合在官方队长/能力表都是 0 行
        （只有 live 能力行 1399913#1）——notes 如实写明、上线前真机确认；trigger 107 官方与 live 自制队长表都是 0 行。"""
        def rows(flat):
            for key, text in flat.items():
                for row in ctx().csv_split(text):
                    yield key, row
        official = list(rows(ctx().official_flat(KL.LEADER)))
        live = list(rows(ctx().live_flat(KL.LEADER)))
        self.assertGreaterEqual(sum(1 for _k, r in official if r[3] == "0" and r[25] == "8"), 20)
        self.assertGreaterEqual(sum(1 for _k, r in official
                                    if r[3] == "0" and r[45] == "33" and r[46] == "5"), 10)
        self.assertTrue(any(r[3] == "0" and r[25] == "8" and r[46] == "5" and r[47] == "Yellow"
                            for _k, r in official))
        # 带触发的瞬发 kind 33 target 5（trigger 23 / 20）在官方队长表有先例
        self.assertTrue(any(r[3] == "0" and r[25] not in ("", "0") and r[45] == "33" and r[46] == "5"
                            for _k, r in official))
        donor = next(r for k, r in official if k == "131164" and r[25] == "8")
        self.assertEqual((donor[45], donor[46], donor[47]), ("32", "5", "Yellow"))   # 同触发同目标，kind 不同
        # 组合 trigger 8 → kind 33：官方队长表、官方能力表都是 0 行（notes.leader_precedents.combination）
        self.assertEqual([k for k, r in official if r[25] == "8" and r[45] == "33"], [])
        self.assertIn("0 行", self.out["notes"]["leader_precedents"]["combination"])
        self.assertEqual([k for k, r in official + live if r[3] == "0" and r[25] == "107"], [])
        # 前置1 = 42 的官方写法：kind 后 6 格全空（本行同形）
        ability = list(rows(ctx().official_flat(KL.ABILITY)))
        self.assertEqual([k for k, r in ability if r[27] == "8" and r[47] == "33"], [])
        pre42 = [r for _k, r in ability if r[6] == "42"]
        self.assertTrue(pre42)
        self.assertTrue(all(r[7:13] == [""] * 6 for r in pre42))


@unittest.skipUnless((ROOT / M.DESIGN_REL).is_file() and (ROOT / M.PANEL_REL).is_file(),
                     "midautumn design mirrors not present")
class MirrorTests(unittest.TestCase):
    def test_mirrors_are_synced_and_the_sync_is_idempotent(self):
        # 2026-09-27 第三轮（wf_balance_20260927c_kuro）改了生成器的队长面板追加两行：第二批 mirror_updates
        # 按设计拒绝在第三轮生成器上重跑（不会把镜像回退到第二批数字）；镜像同步与幂等移交第三轮
        # （主会话 --write 落盘前在内存里补上，已落盘时为恒等），这里核对第二批的记录仍在、其余与生成器一致。
        import wf_balance_20260927c_kuro as M3
        design = json.loads((ROOT / M.DESIGN_REL).read_text(encoding="utf-8"))
        panel = json.loads((ROOT / M.PANEL_REL).read_text(encoding="utf-8"))
        # 第三轮镜像落盘前拒绝在「生成器面板」处，落盘后（队长面板已合并成 5 行）拒绝在「镜像布局」处
        with self.assertRaisesRegex(ValueError, "batch-b leader panel|leader layout drifted"):
            M.mirror_updates(design, panel)
        design, panel = M3.mirror_updates(design, panel)
        self.assertEqual(design[M.MIRROR_TAG]["module"], "mod-tools/wf_balance_20260927b_kuro.py")
        self.assertIn(M.MIRROR_NOTE, panel["notes"])
        rows = design["plan"]["leader_ability"]["rows"]
        self.assertEqual([r["desc_expected"] for r in rows], [e for _d, _c, e in K.LEADER])
        texts = {r["key"]: r["text"] for r in design["plan"]["texts"]["custom_ability_string"]["rows"]}
        self.assertEqual(texts, K.CAS_TEXTS)
        self.assertEqual([line["text"] for line in panel["leader"]["lines"]], list(K.PANEL_LEADER))


@unittest.skipUnless(MANIFEST.is_file(), "candidate workspace ma-kuro not present")
class CandidateTests(unittest.TestCase):
    def test_package_version_only_goes_up(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        current = manifest["package_version"]
        as_tuple = lambda v: tuple(int(x) for x in v.split("."))        # noqa: E731
        import wf_balance_20260927c_kuro as M3
        if as_tuple(current) >= as_tuple(M3.PACKAGE_VERSION["ma-kuro"]):
            # 第三轮已回写：候选再升号，本批版本在其之前
            self.assertLess(as_tuple(M.PACKAGE_VERSION["ma-kuro"]), as_tuple(current))
            return
        self.assertGreaterEqual(as_tuple(M.PACKAGE_VERSION["ma-kuro"]), as_tuple(current))
        self.assertGreater(as_tuple(M.PACKAGE_VERSION["ma-kuro"]), (1, 0, 1))
        if manifest.get("snapshot", {}).get("revision_20260927b") is not None:
            self.assertEqual(M.PACKAGE_VERSION["ma-kuro"], current)     # 已回写：候选现值 == 本模块版本


if __name__ == "__main__":
    unittest.main()
