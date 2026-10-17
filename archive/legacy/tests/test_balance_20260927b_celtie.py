# -*- coding: utf-8 -*-
"""希尔媞·校园 149989 ``wind_spgirl_campus`` 2026-09-27 平衡第二批（星风心得无上限成长）。

fixture（``fixtures/balance_20260927b_celtie.json``）= revise() 的 live 输入快照（1.4.1049 只读），
离线驱动：每处改动的前后值、未改行/树节点逐字保留、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、
合法性与四道 DSL 门禁、AMF3 往返、面板规则、生成器常量一致。需要 ``.cdn/cn`` 官方基线的完整
生成器装配对比、需要本机候选工作区的检查用 skipUnless。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.
sys.setrecursionlimit(10000)

import wf_balance_20260927b_celtie as M  # noqa: E402
import wf_balance_20260927c_celtie as C3  # noqa: E402  第三轮（c）接管队长成长 / 面板 / 技能树
import wf_campus_panel_text as P  # noqa: E402
import wf_celtie_fever_abilities as A  # noqa: E402
import wf_celtie_fever_leader as LD  # noqa: E402
import wf_celtie_skill_growth as G  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_celtie.json'
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))
WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]
TABLE = {"ability": "ability", "leader": "leader_ability"}


def load_fixture() -> dict:
    data = {kind: value for kind, value in deepcopy(DATA).items() if not kind.startswith("_")}
    data["action"] = {key: [(inner, fields) for inner, fields in value]
                      for key, value in data["action"].items()}
    return data


def reader(data: dict):
    def read(kind, key):
        return data[kind][key]
    return read


def binds(tree) -> list[list]:
    return [args for args in M._commands(tree) if args[0] == "BindConditionAccumulationVariable"]


def _baseline_available() -> bool:
    return (ROOT / ".cdn/cn").is_dir() and (ROOT / "mod-tools/profiles.json").is_file()


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

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), (A.CID, A.CODE))
        self.assertEqual(M.PACKAGES, ["campus-celtie-20260911"])
        self.assertEqual(M.PACKAGE_VERSION, {"campus-celtie-20260911": "0.20260927"})
        self.assertGreater(M.PACKAGE_VERSION[M.PACKAGES[0]], "0.20260925")   # 候选现值，只升不降
        self.assertEqual(M.CAPABILITIES, ["kyubi-fever-ratio-v1", "panel-description-override-v2"])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertFalse(self.out["notes"]["runtime_verified"])
        json.dumps(self.out["notes"], ensure_ascii=False)

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out), {"ability", "leader", "cas", "text", "table", "action", "dsl",
                                    "server_text", "new_programs", "notes"})
        self.assertEqual(set(out["ability"]), {M.ABILITY_KEY})
        self.assertEqual(set(out["leader"]), {M.CID})
        self.assertEqual(set(out["cas"]), {M.CAS_LEADER, M.CAS_A3})
        self.assertEqual(set(out["text"]), {M.CID})
        self.assertEqual(set(out["server_text"]), {M.CID})
        self.assertEqual(set(out["action"]), {M.CODE})
        self.assertEqual(set(out["dsl"]), set(M.PROGRAMS.values()))
        self.assertEqual(out["table"], {})
        self.assertEqual(out["new_programs"], [M.PROGRAMS["1"], M.PROGRAMS["2"]])
        for key in [*out["ability"], *out["leader"], *out["cas"], *out["text"], *out["action"]]:
            # stage_batch Plan.splice 的候选命名空间断言
            self.assertTrue(key.startswith((M.CID, M.CODE, "desc_override_" + M.CODE,
                                            "change_skill_" + M.CODE)), key)

    # ---- 能力3

    def test_ability3_caps_only_the_two_insight_rows(self):
        old, new = self.live["ability"][M.ABILITY_KEY], self.out["ability"][M.ABILITY_KEY]
        self.assertEqual((len(old), len(new)), (8, 8))
        self.assertEqual(new[:6], old[:6])                                  # #0–#5 逐字保留
        for index, content, before, after in ((6, "154", "25000", "8000"), (7, "0", "25000", "5000")):
            self.assertEqual((old[index][109], old[index][102], old[index][113], old[index][114]),
                             (content, "(None)", before, before))
            self.assertEqual((new[index][109], new[index][102], new[index][113], new[index][114]),
                             (content, "10", after, after))
            changed = {c for c, (a, b) in enumerate(zip(old[index], new[index])) if a != b}
            self.assertEqual(changed, {102, 113, 114})
        self.assertEqual({row[1] for row in new}, {"false"})                # 整键仍仅主位
        self.assertEqual(new[6][104], M.GAIN_UID)

    def test_ability3_rows_read_back_as_capped(self):
        rendered = [wf_describe.describe_rows([row], "ability")[0] for row in self.out["ability"][M.ABILITY_KEY][6:]]
        self.assertEqual(rendered, [
            "风·编成≥6 且 Fever 时: 持续·状态累积计数固有≥1(限10次)[固有14998902] → 赋予全队(风) 能力伤害 8%",
            "风·编成≥6 且 Fever 时: 持续·状态累积计数固有≥1(限10次)[固有14998902] → 赋予全队(风) 攻击力 5%",
        ])

    # ---- 队长

    def test_leader_appends_two_uncapped_rows_derived_from_the_old_ability_rows(self):
        old, new = self.live["leader"][M.CID], self.out["leader"][M.CID]
        self.assertEqual((len(old), len(new)), (6, 8))
        self.assertEqual(new[:6], old)
        before = self.live["ability"][M.ABILITY_KEY]
        for row, source in zip(new[6:], before[6:]):
            expected = [M.CODE, "0", ""] + source[5:]                     # 口径 A3 行形
            expected[111] = expected[112] = "2500"
            self.assertEqual(row, expected)
            # 口径 A2：每层一步，3 分钟约 40–60 层 ≥30 ⇒ ×1/10（25% → 2.5%）。
            self.assertEqual(int(row[111]) * 10, int(source[113]))
            self.assertEqual((row[100], row[102], row[107]), ("(None)", M.GAIN_UID, source[109]))
        rendered = [wf_describe.describe_rows([row], "leader_ability")[0] for row in new[6:]]
        self.assertEqual(rendered, [
            "风·编成≥6 且 Fever 时: 持续·状态累积计数固有≥1[固有14998902] → 赋予全队(风) 能力伤害 2.5%",
            "风·编成≥6 且 Fever 时: 持续·状态累积计数固有≥1[固有14998902] → 赋予全队(风) 攻击力 2.5%",
        ])

    def test_leader_has_no_mergeable_row(self):
        """队长原 6 行没有 D134/同内容 kind 的持续行 ⇒ 按口径另起两行，不合并。"""
        old = self.live["leader"][M.CID]
        self.assertFalse([row for row in old if row[95] or row[3] == "1"])
        self.assertEqual([row[45] for row in old], list(M.LEADER_KINDS))

    def test_growth_before_and_after_at_fifty_layers(self):
        layers = 50
        old = self.live["ability"][M.ABILITY_KEY]
        new_a, new_l = self.out["ability"][M.ABILITY_KEY], self.out["leader"][M.CID]
        before = [int(row[113]) * layers for row in old[6:]]
        after = [int(a[113]) * min(layers, int(a[102])) + int(l[111]) * layers
                 for a, l in zip(new_a[6:], new_l[6:])]
        self.assertEqual(before, [1_250_000, 1_250_000])                  # +1250% / +1250%
        self.assertEqual(after, [80_000 + 125_000, 50_000 + 125_000])     # +205% / +175%

    # ---- 面板与技能描述

    def test_leader_panel(self):
        old = self.live["cas"][M.CAS_LEADER][0][0].split("\n")
        new = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertEqual((len(old), len(new)), (5, 6))
        self.assertEqual(new[:3] + [new[4]], old[:3] + [old[4]])
        self.assertEqual(new[3], "风属性共鸣时，Fever模式中，风属性角色发动技能时，自身获得2层「星风快门」与2层「星风心得」。")
        self.assertEqual(new[5], "风属性共鸣时，Fever模式中，每层「星风心得」使风属性角色能力伤害+2.5%、攻击力+2.5%。")

    def test_a3_panel(self):
        old = self.live["cas"][M.CAS_A3][0][0].split("\n")
        new = self.out["cas"][M.CAS_A3][0][0].split("\n")
        self.assertEqual((len(old), len(new)), (7, 7))
        self.assertEqual(new[:6], old[:6])
        self.assertEqual(new[6], " <icon id='main'>  风属性共鸣时，Fever模式中，每层「星风心得」使风属性角色能力伤害+8%、攻击力+5%（最多10层）。")
        self.assertTrue(all(line.startswith(M.MAIN_ICON) for line in new))

    def test_panel_texts_obey_the_project_rules(self):
        for key, rows in self.out["cas"].items():
            self.assertEqual((len(rows), len(rows[0])), (1, 1), key)
            text = rows[0][0]
            self.assertNotIn("／", text)
            self.assertNotIn("\\n", text)
            for line in text.split("\n"):
                self.assertEqual(KL.panel_problems(line), [], f"{key}: {line}")
                for word in ("无上限", "无限", "可无限累积", "自身为队长时", "觉醒后", "生命值100%以下"):
                    self.assertNotIn(word, line)
            self.assertEqual(key == M.CAS_A3, "<icon id='main'>" in text)      # 只有能力3 整键仅主位
        self.assertEqual(KL.panel_problems(M.NEW_DESC), [])

    def test_skill_description_is_synced_in_all_five_places(self):
        for inner, fields in self.out["action"][M.CODE]:
            self.assertEqual(fields[1], M.NEW_DESC, inner)
        old_action = dict(self.live["action"][M.CODE])
        for inner, fields in self.out["action"][M.CODE]:
            changed = {c for c, (a, b) in enumerate(zip(old_action[inner], fields)) if a != b}
            self.assertEqual(changed, {1}, inner)
        for rows, old in ((self.out["text"][M.CID], self.live["text"][M.CID]),
                          (self.out["server_text"][M.CID], self.live["server_text"][M.CID])):
            self.assertEqual((rows[0][5], rows[0][7]), (M.NEW_DESC, M.NEW_DESC))
            self.assertEqual({c for c, (a, b) in enumerate(zip(old[0], rows[0])) if a != b}, {5, 7})
        self.assertTrue(M.NEW_DESC.endswith("每层额外增加10倍（最多10层）。"))
        self.assertEqual(M.NEW_DESC.replace("（最多10层）", ""), M.OLD_DESC)

    # ---- DSL

    def test_dsl_only_the_resonant_fever_bind_cap_changes(self):
        for program in M.PROGRAMS.values():
            old, new = self.live["dsl"][program], self.out["dsl"][program]
            self.assertEqual([b[5] for b in binds(old)], [2147483647, 0, 0])
            self.assertEqual([b[5] for b in binds(new)], [10, 0, 0])
            restored = deepcopy(new)
            binds(restored)[0][5] = 2147483647.0
            self.assertEqual(restored, old, "every other node must stay verbatim")
            self.assertEqual(M.command_counts(new), M.COUNTS)
            resonant, plain, calm = M.growth_bindings(new)
            self.assertEqual((resonant[1][0][1][5], plain[1][0][1][5], calm[1][0][1][5]), (10, 0, 0))
        self.assertEqual(self.out["dsl"][M.PROGRAMS["1"]], self.out["dsl"][M.PROGRAMS["2"]])

    def test_dsl_cap_semantics_ten_layers(self):
        """原生 Bind：min(层数 / 1, 上限)；倍率 = 75 + 10 × 绑定值（仅共鸣∧Fever 支）。"""
        tree = self.out["dsl"][M.PROGRAMS["2"]]
        args = binds(tree)[0]
        attacks = [a for a in M._commands(M.growth_bindings(tree)[0]) if a[0] == "CreateNormalAttack"]
        self.assertTrue(attacks)
        per_layer = {term["vid"]: term["max"] for a in attacks for t in a[6] for term in t.get("vlv", [])}
        self.assertEqual(set(per_layer), {M.GAIN_FLOAT_ID})
        for layers, bound in ((0, 0), (5, 5), (10, 10), (11, 10), (2147483647, 10)):
            self.assertEqual(min(layers / args[4], args[5]), bound)

    def test_dsl_gates_and_amf3_roundtrip(self):
        for program, tree in self.out["dsl"].items():
            self.assertEqual(M.dsl_gate_problems(tree), [], program)
            self.assertEqual(L.action_dsl_element_problems(tree, M.ELEMENT), [])
            self.assertEqual(L.action_dsl_subject_binding_problems(tree), [])
            self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [])
            self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [])
            raw = encode_tree(tree)
            self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"], tree)
            self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree)

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

    def test_required_capabilities_match_the_module_declaration(self):
        caps = M.required_capabilities(self.out["ability"][M.ABILITY_KEY], self.out["leader"][M.CID],
                                       self.out["cas"])
        self.assertEqual(caps, sorted(M.CAPABILITIES))
        self.assertEqual([c for row in self.out["leader"][M.CID]
                          for c in L.required_client_capabilities("leader_ability", row)], [])

    # ---- fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["ability"][M.ABILITY_KEY][6][102] = "mutated"
        out["leader"][M.CID][6][111] = "mutated"
        out["cas"][M.CAS_LEADER][0][0] = "mutated"
        out["text"][M.CID][0][5] = "mutated"
        out["server_text"][M.CID][0][5] = "mutated"
        out["action"][M.CODE][0][1][1] = "mutated"
        binds(out["dsl"][M.PROGRAMS["1"]])[0][5] = 99
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

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        data = deepcopy(self.live)
        for kind in ("ability", "leader", "cas", "text", "server_text", "action", "dsl"):
            data[kind].update(deepcopy(self.out[kind]))
        with self.assertRaises(ValueError):
            M.revise(reader(data))
        with self.assertRaises(ValueError):
            M.ability3_rows(self.out["ability"][M.ABILITY_KEY])
        with self.assertRaises(ValueError):
            M.leader_rows(self.out["leader"][M.CID], self.live["ability"][M.ABILITY_KEY])
        with self.assertRaises(ValueError):
            M.leader_rows(self.live["leader"][M.CID], self.out["ability"][M.ABILITY_KEY])
        with self.assertRaises(ValueError):
            M.leader_text(self.out["cas"][M.CAS_LEADER])
        with self.assertRaises(ValueError):
            M.a3_text(self.out["cas"][M.CAS_A3])
        for level, program in M.PROGRAMS.items():
            with self.assertRaises(ValueError):
                M.revise_tree(self.out["dsl"][program], level)
        with self.assertRaises(ValueError):
            M._replace_desc(M.NEW_DESC, "again")

    def test_row_locators_are_content_based(self):
        rows = deepcopy(self.live["ability"][M.ABILITY_KEY])
        swapped = rows[:6] + [rows[7], rows[6]]
        with self.assertRaises(ValueError):
            M.ability3_rows(swapped)
        drifted = deepcopy(rows)
        drifted[6][113] = drifted[6][114] = "30000"
        with self.assertRaises(ValueError):
            M.ability3_rows(drifted)
        other = deepcopy(rows)
        other[2][51] = other[2][52] = "80000"                          # 保留行的漂移由 BEFORE 兜底
        self.assertEqual(M.ability3_rows(other)[2], other[2])
        tree = deepcopy(self.live["dsl"][M.PROGRAMS["1"]])
        binds(tree)[1][5] = 3                                          # 非共鸣支上限不再是 0
        with self.assertRaises(ValueError):
            M.revise_tree(tree, "1")


class GeneratorSyncTests(unittest.TestCase):
    """生成器重跑不能回退本批改动：常量 / 纯函数输出 == revise() 输出。

    2026-09-27 第三轮（c）改了队长 #6/#7 强度、队长面板、技能描述和技能树（旗号 2 撤封顶）：
    这些项的生成器输出允许是第二批或「第三轮作用于第二批输出」两种状态，第三轮一致性由
    test_balance_20260927c_celtie 断言；第三轮未碰的项（能力3、GAIN_MAX_LAYERS）仍严格等于第二批。
    a3 面板第三轮只删共鸣前缀（面板共鸣省略，数值不变），同样允许两种状态。
    """

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_panel_generator_equals_revise_output(self):
        texts = P.panel_descriptions(M.CID)
        leader = self.out["cas"][M.CAS_LEADER]
        self.assertIn([[texts["leader"]]], (leader, C3.leader_text(leader)))
        a3 = self.out["cas"][M.CAS_A3]
        self.assertIn([[texts["a3"]]], (a3, C3.a3_text(a3)))
        # 第三轮技能强化文案规范：技能描述只写本体，保持第二批原文（C3.SKILL_DESC == 第二批 NEW_DESC）。
        self.assertIn(P.active_description(M.CID), (M.NEW_DESC, C3.SKILL_DESC))
        for slot in ("a1", "a2", "a4", "a5", "a6"):
            self.assertNotIn("星风心得", texts[slot])

    def test_ability_generator_equals_revise_output_on_fixture_donors(self):
        import test_celtie_fever_abilities as fixture
        built = A.ability_rows(fixture.official_sources())[M.ABILITY_KEY]
        self.assertEqual(built[6:], self.out["ability"][M.ABILITY_KEY][6:])
        self.assertEqual((A.GAIN_BONUS_LIMIT, A.GAIN_BONUS_STRENGTH), (10, {154: 8_000, 0: 5_000}))

    def test_leader_generator_equals_revise_output_on_fixture_donors(self):
        import test_celtie_fever_leader as fixture
        case = fixture.CeltieFeverLeaderTest()
        case.setUp()
        leader = self.out["leader"][M.CID]
        self.assertIn(case.rows[6:], (leader[6:], C3.leader_rows(leader)[6:]))
        self.assertIn(LD.GAIN_GROWTH_STRENGTH, ({154: 2_500, 0: 2_500}, {154: 20_000, 0: 20_000}))

    def test_skill_growth_constant_equals_revise_cap(self):
        self.assertEqual(G.GAIN_MAX_LAYERS, M.NEW_SKILL_CAP)
        self.assertEqual(G.GAIN_FLOAT_ID, M.GAIN_FLOAT_ID)
        near = ["FindNearSubjects",
                ["Block", [["Command", ["CreateNormalAttack", 0, 4, 0, 0, 0,
                                        [{"min": w * 75 / 70, "max": w * 75 / 70}]]] for w in (25, 45)]],
                ["Block", [["Command", ["CreateNormalAttack", 0, 4, 0, 0, 0,
                                        [{"min": w * 75 / 70, "max": w * 75 / 70}]]] for w in (25, 45)]]]
        grown = G.with_starwind_growth(near)
        self.assertEqual([b[5] for b in binds(grown)], [10, 0, 0])

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线")
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
        self.assertIn(led, (self.out["leader"][M.CID], C3.leader_rows(self.out["leader"][M.CID])))
        overrides = P.override_string_rows(M.CID, built, led)
        for key, value in self.out["cas"].items():
            third = {M.CAS_LEADER: C3.leader_text, M.CAS_A3: C3.a3_text}
            allowed = (value, third[key](value)) if key in third else (value,)
            self.assertIn(overrides[key], allowed, key)
        for level, program in M.PROGRAMS.items():
            tree = self.out["dsl"][program]
            self.assertIn(S.build_skill(int(level), official), (tree, C3.revise_tree(tree, level)[0]), program)


class CandidateTests(unittest.TestCase):
    @unittest.skipUnless((WORKSPACE / "package/manifest.json").is_file()
                         and (ROOT / "mod-tools/profiles.json").is_file(),
                         "local candidate workspace required")
    def test_candidate_has_no_file_drift_and_version_moves_forward(self):
        from wf_character_revision import RevisionCandidate
        import wf_share_update_codec as X
        manifest = WORKSPACE / "package/manifest.json"
        before = manifest.read_bytes()
        current = json.loads(before)
        as_tuple = lambda v: tuple(int(x) for x in v.split("."))        # noqa: E731
        if as_tuple(current["package_version"]) > as_tuple(M.PACKAGE_VERSION[M.PACKAGES[0]]):
            self.skipTest("候选已前进到第三轮（c）；回写一致性见 test_balance_20260927c_celtie")
        candidate = RevisionCandidate(ROOT, WORKSPACE, character_id=M.CID, code_name=M.CODE,
                                      package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
                                      snapshot_key="revision_20260927b",
                                      reviewed_input_drift=M.REVIEWED_DRIFT,
                                      baseline_factory=lambda *a, **k: None)
        out = M.revise(reader(load_fixture()))
        written_back = current.get("snapshot", {}).get("revision_20260927b") is not None
        if written_back:
            # 主会话暂存回写后：候选 = live + 本批，版本等于本模块声明。revise() 的每一类输出
            # （能力/队长/面板/角色文案/技能表/两档技能树/服务端文案）都已进候选。
            self.assertEqual(current["package_version"], M.PACKAGE_VERSION[M.PACKAGES[0]])
            ability = X.unpack(candidate.read("common", "master/ability/ability.orderedmap"))
            self.assertEqual(X.csv_read(ability[M.ABILITY_KEY]), out["ability"][M.ABILITY_KEY])
            leader = X.unpack(candidate.read("common", "master/ability/leader_ability.orderedmap"))
            self.assertEqual(X.csv_read(leader[M.CID]), out["leader"][M.CID])
            cas = X.unpack(candidate.read("common", "master/string/custom_ability_string.orderedmap"))
            for key, value in out["cas"].items():
                self.assertEqual(X.csv_read(cas[key]), value, key)
            text = X.unpack(candidate.read("common", "master/character/character_text.orderedmap"))
            for key, value in out["text"].items():
                self.assertEqual(X.csv_read(text[key]), value, key)
            import wf_mod_tool as core
            actions = X.unpack(candidate.read("common", "master/skill/action_skill.orderedmap"))
            for code, value in out["action"].items():
                self.assertEqual([(inner, list(fields)) for inner, fields in value],
                                 [(inner, list(fields)) for inner, fields in
                                  core.decode_action_skill_row(actions[code])], code)
            for program, tree in out["dsl"].items():
                raw = candidate.read("common", wf_dsl.dsl_logical(program))
                self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"], tree, program)
            server = json.loads(candidate.read("server", "cdndata/character_text.json"))
            for key, value in out["server_text"].items():
                self.assertEqual(server[key], value, key)
        else:
            self.assertLess(as_tuple(current["package_version"]), as_tuple(M.PACKAGE_VERSION[M.PACKAGES[0]]))
            live = load_fixture()
            ability = X.unpack(candidate.read("common", "master/ability/ability.orderedmap"))
            self.assertEqual(X.csv_read(ability[M.ABILITY_KEY]), live["ability"][M.ABILITY_KEY])
            cas = X.unpack(candidate.read("common", "master/string/custom_ability_string.orderedmap"))
            for key in (M.CAS_LEADER, M.CAS_A3):
                self.assertEqual(X.csv_read(cas[key]), live["cas"][key], key)
            for program in M.PROGRAMS.values():
                raw = candidate.read("common", wf_dsl.dsl_logical(program))
                self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"], live["dsl"][program])
            # 既有漂移（notes.candidate_preexisting_drift）：候选队长仍是初版 3 行。
            leader = X.unpack(candidate.read("common", "master/ability/leader_ability.orderedmap"))
            self.assertEqual(len(X.csv_read(leader[M.CID])), 3)
            self.assertIn(f"leader_ability:{M.CID}", out["notes"]["candidate_preexisting_drift"])
        self.assertEqual(before, manifest.read_bytes())


if __name__ == "__main__":
    unittest.main()
