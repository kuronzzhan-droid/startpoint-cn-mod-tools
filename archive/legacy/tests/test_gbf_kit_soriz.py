# -*- coding: utf-8 -*-
"""索利兹 kit 的完成态契约（不是草稿契约）。

断言的是「机制真的落进包里」：行 / DSL 树 / 固有状态 / 面板文案 / 图集预算都按
`design/soriz.json` 定稿的形态存在。每条断言都对应一次真机事故或一条主控裁决，
删掉被测的那一格就必须变红。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_gbf_kit_soriz as KIT  # noqa: E402
import wf_midautumn_kitlib as K  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402

PACK = ROOT / "work/character_packs/gbf-soriz-20260919"
ROOTS = PACK / "package/roots/common"
DESIGN = ROOT / "work/character_packs/midautumn-20260920/design/soriz.json"
LEADER_FORBIDDEN = {"422", "724", "713"}        # 队长表写这三个 kind = C7050

_CACHE: dict[str, object] = {}


def flat(logical: str) -> dict[str, str]:
    import wf_mod_tool as core
    return core.read_orderedmap_file_from_bytes((ROOTS / logical).read_bytes())


def rows(logical: str, key: str) -> list[list[str]]:
    return C.csv_split(flat(logical)[key])


def design() -> dict:
    if "design" not in _CACHE:
        _CACHE["design"] = json.loads(DESIGN.read_text(encoding="utf-8"))
    return _CACHE["design"]


def program(name: str):
    path = ROOTS / f"{name}.action.dsl.amf3.deflate"
    return C.amf_parse(path.read_bytes())


def batch2_written_back() -> bool:
    """2026-09-27 平衡第二批（wf_balance_20260927b_gbf）：design/soriz.json 与生成器已是改后形态，
    候选包要等 stage_batch 回写（manifest.snapshot 出现 revision_20260927b）后才是改后形态。"""
    manifest = json.loads((PACK / "package/manifest.json").read_text(encoding="utf-8"))
    return "revision_20260927b" in (manifest.get("snapshot") or {})


def batch3_written_back() -> bool:
    """2026-09-27 平衡第三轮（wf_balance_20260927c_soriz，extra5 快照键 revision_20260927d）：
    设计镜像 --write 后即为第三轮值，候选包要等 stage_batch 回写后才是。"""
    manifest = json.loads((PACK / "package/manifest.json").read_text(encoding="utf-8"))
    return "revision_20260927d" in (manifest.get("snapshot") or {})


def expected_plan() -> dict:
    """包内行应有的设计格子：回写后 = 设计稿；回写前 = 设计稿去掉第二批覆盖（队长 #9-#11、能力3 #1-#3 改前值）。
    第三轮（c）镜像已写、候选未回写时，队长 #9-#11 强度两格取第二批值。"""
    from copy import deepcopy
    plan = deepcopy(design()["plan"])
    if batch2_written_back():
        if not batch3_written_back() and "balance_20260927c" in design():
            import wf_balance_20260927c_soriz as B3
            for index, _kind, _name, _original, before, _after, _rounding in B3.GROWTH:
                cells = plan["leader_ability"]["rows"][index]["cells"]
                for col in B3.L_STRENGTH:
                    cells[str(col)] = str(before)
        return plan
    import wf_balance_20260927b_gbf as B2
    del plan["leader_ability"]["rows"][9:]
    records = plan["ability"]["keys"][B2.SORIZ_ABILITY3]["records"]
    for index, *_rest in B2.CROWS_ROWS:
        records[index]["cells"] = {str(c): v for c, v in B2.crows_cells(index, capped=False).items()}
    return plan


def find_nodes(tree, name: str) -> list[list]:
    out: list[list] = []

    def walk(node):
        if isinstance(node, list):
            if node and isinstance(node[0], str) and node[0] == name:
                out.append(node)
            for child in node:
                walk(child)
    walk(tree)
    return out


class RowContracts(unittest.TestCase):
    def test_row_counts_and_single_value_head_columns(self):
        leader = rows(KIT.LEADER, KIT.CID_S)
        # 第二批把能力3 三羽乌逐层成长搬进队长 #9-#11（9 → 12 行）；候选回写前仍是 9 行。
        self.assertEqual(len(leader), 12 if batch2_written_back() else 9)
        counts = {key: len(rows(KIT.ABILITY, key)) for key in
                  (f"{KIT.CID}{i}" for i in range(1, 7))}
        self.assertEqual(counts, {"1299861": 6, "1299862": 8, "1299863": 11,
                                  "1299864": 11, "1299865": 3, "1299866": 5})
        for slot in range(1, 7):
            records = rows(KIT.ABILITY, f"{KIT.CID}{slot}")
            # 裁决 §8：c1（主位限制）与 c2（雕像组）每个键必须单值，官方 790 个多记录键 0 个混用。
            self.assertEqual(len({r[1] for r in records}), 1, f"slot {slot} mixed c1")
            self.assertEqual(len({r[2] for r in records}), 1, f"slot {slot} mixed c2")
            self.assertEqual(records[0][2], KIT.STATUE[slot])
            self.assertIn(records[0][2], L.ABILITY_STATUE_GROUPS)

    def test_ability_three_is_the_only_main_slot_key(self):
        # 724 扣 FEVER 与队长保命行都在能力 3；副位装配时前置 42 仍判真，只能靠整键 Ⓜ 挡住。
        mains = {slot for slot in range(1, 7)
                 if rows(KIT.ABILITY, f"{KIT.CID}{slot}")[0][1] == "false"}
        self.assertEqual(mains, {3})

    def test_leader_table_has_no_c7050_kinds_and_no_724(self):
        block = K.donor_row  # 触碰一次以保证 kitlib 可用
        self.assertTrue(callable(block))
        layout = KIT.LAY["leader_ability"]
        for row in rows(KIT.LEADER, KIT.CID_S):
            kind = row[layout["instant_content"]] or row[layout["during_content"]]
            self.assertNotIn(kind, LEADER_FORBIDDEN, f"leader kind {kind} = C7050")
        ability_kinds = [r[KIT.LAY["ability"]["instant_content"]]
                         for r in rows(KIT.ABILITY, "1299863")]
        self.assertIn("724", ability_kinds, "削 FEVER 的 724 必须落在词条表")

    def test_every_row_passes_client_legality_and_invoke_string_gate(self):
        keys = set(flat(KIT.CAS))
        for table, key in [("leader_ability", KIT.CID_S)] + \
                [("ability", f"{KIT.CID}{i}") for i in range(1, 7)]:
            logical = KIT.LEADER if table == "leader_ability" else KIT.ABILITY
            for row in rows(logical, key):
                self.assertEqual(L.client_legality_problems(table, row), [])
                self.assertEqual(L.declared_block_field_problems(table, row), [])
                self.assertEqual(L.ability_element_column_problems(table, row, 1), [])
                # 629 的 string_id 不在 custom_ability_string = 详情页 C8601 并连坐删表文件。
                self.assertEqual(L.invoke_skill_string_problems(row, keys, table), [])

    def test_rows_match_the_design_plan_cells(self):
        plan = expected_plan()              # 第一批/中秋定稿 + 第二批覆盖（按候选是否已回写）
        got = rows(KIT.LEADER, KIT.CID_S)
        self.assertEqual(len(got), len(plan["leader_ability"]["rows"]))
        for want, row in zip(plan["leader_ability"]["rows"], got):
            cells = {str(i): c for i, c in enumerate(row) if c != ""}
            self.assertEqual(cells, want["cells"], want["req"])
        for key in sorted(plan["ability"]["keys"]):
            for want, row in zip(plan["ability"]["keys"][key]["records"], rows(KIT.ABILITY, key)):
                cells = {str(i): c for i, c in enumerate(row) if c != ""}
                self.assertEqual(cells, want["cells"], want["req"])


class UniqueConditionContracts(unittest.TestCase):
    def test_six_states_are_eight_digit_and_never_capped_at_none(self):
        table = flat(KIT.UNIQUE)
        for uid in KIT.UNIQUE_IDS:
            row = C.csv_split(table[str(uid)])[0]
            self.assertEqual(len(str(uid)), 8, "固有 ID 必须 8 位（7 位撞过基诺维）")
            self.assertEqual(len(row), 15)
            # c4 写 (None) 会被读成上限 1 层，during 134 的逐层成长全死。
            self.assertNotIn(row[4], ("", "(None)"))
            self.assertTrue(row[2], "缺图标列")
            self.assertTrue((ROOTS / f"{row[2]}.png").is_file(), row[2])
        caps = {str(uid): C.csv_split(table[str(uid)])[0][4] for uid in KIT.UNIQUE_IDS}
        self.assertEqual(caps["12998601"], "99")
        self.assertEqual(caps["12998604"], "10")

    def test_ability_rows_only_watch_states_the_package_defines(self):
        defined = {str(uid) for uid in KIT.UNIQUE_IDS}
        layout = KIT.LAY["ability"]
        watched = set()
        for slot in range(1, 7):
            for row in rows(KIT.ABILITY, f"{KIT.CID}{slot}"):
                for col in (layout["during_trigger"] + 7, layout["instant_content"] + 21,
                            layout["instant_precontent"] + 6):
                    value = row[col] if col < len(row) else ""
                    if value.startswith("129986"):
                        watched.add(value)
        self.assertTrue(watched <= defined, f"未定义的固有状态 {watched - defined}")


class DslContracts(unittest.TestCase):
    def test_all_fourteen_programs_are_on_disk_and_parse(self):
        names = [KIT.AP.format(n) for n in KIT.PROGRAMS]
        names += [KIT.SKILL_PATH.format(KIT.CODE, lv) for lv in ("1", "2")]
        names += [KIT.PF_PATH.format(k=KIT.PF_KEY, n=n) for n in (1, 2, 3)]
        self.assertEqual(len(names), 14)
        for name in names:
            tree = program(name)
            self.assertEqual(tree[0], "ActionDsl", name)

    def test_assist_trees_are_settled_as_power_flip_damage(self):
        # tree[10] = 伤害归属；3 = 按强化弹射伤害结算（九尾 139995 在线先例）。
        for name in ("soriz_assist_eugen", "soriz_assist_jin", "soriz_assist_duo"):
            self.assertEqual(program(KIT.AP.format(name))[10], 3, name)
        self.assertEqual(program(KIT.SKILL_PATH.format(KIT.CODE, "1"))[10], 0)

    def test_party_effects_include_soriz_himself(self):
        # 35 = 除自身外：禁疗/贯通/二连击/逆境漏掉本人就等于设计没实现（裁决 §8）。
        for name in ("soriz_fever_begin", "soriz_fever_end", "soriz_adversity_tick"):
            for node in find_nodes(program(KIT.AP.format(name)), "FindAllSubjects"):
                self.assertIn(node[2], (KIT.FIND_PARTY, KIT.FIND_ENEMY), name)

    def test_create_condition_target_kind_matches_the_selector(self):
        # 下标 10 错配 = 施法 C16102。官方 rare5 语料：33/49 → 3、97 → 2、自身 -17 → 3。
        for name in KIT.PROGRAMS:
            tree = program(KIT.AP.format(name))
            for node in find_nodes(tree, "CreateCondition"):
                self.assertEqual(node[10], 3, f"{name}: {node[1]}")

    def test_heat_transfer_does_not_clear_the_destination_first(self):
        end = program(KIT.AP.format("soriz_heat_end"))
        begin = program(KIT.AP.format("soriz_heat_begin"))
        self.assertEqual(len(find_nodes(end, "ConditionalsConditionAccumulationNumber")), 10)
        deleted = [node[2][1] for node in find_nodes(end, "DeleteCondition")]
        self.assertNotIn(KIT.HEAT, deleted, "heat_end 不许先删余热（同帧先赋予后删除）")
        self.assertEqual(deleted, [KIT.BURN, KIT.DUO])
        # heat_begin：11 个分档（10 层搬运 + 1 个 ≥5 层的合击预备）后才清源。
        self.assertEqual(len(find_nodes(begin, "ConditionalsConditionAccumulationNumber")), 11)
        self.assertEqual([node[2][1] for node in find_nodes(begin, "DeleteCondition")], [KIT.HEAT])

    def test_pf_resistance_program_deletes_buffs_then_force_applies(self):
        tree = program(KIT.AP.format("soriz_pf_resist"))
        delete = find_nodes(tree, "DeleteCondition")[0]
        create = find_nodes(tree, "CreateCondition")[0]
        self.assertEqual(delete[2], ["DCPowerFlipDamageResistance", 2])
        self.assertEqual(delete[4], 2, "cancelableKind 2 才连不可驱散一起删")
        self.assertFalse(create[5], "抗性 debuff 必须不可驱散")
        self.assertTrue(create[12], "forceApply 必须为真，否则带耐性旗的 boss 静默失效")

    def test_fever_special_override_keeps_lifecycle_nodes_and_twelve_combo(self):
        for level, total in ((1, 10.0), (2, 20.0), (3, 50.0)):
            tree = program(KIT.PF_PATH.format(k=KIT.PF_KEY, n=level))
            self.assertTrue(find_nodes(tree, "SetPowerFilpSuppress"), "缺 suppress = 弹射卡死")
            self.assertTrue(find_nodes(tree, "NotifyPowerflipEnd"), "缺 end 通知 = 弹射卡死")
            fever = find_nodes(tree, "ConditionalsFeverMode")
            self.assertEqual(len(fever), 1)
            areas = find_nodes(fever[0][1], "CreateHitArea")      # 第一分支 = FEVER 中
            hits = [area[14][1] for area in areas]
            self.assertEqual(hits, [11, 1], f"lv{level} 连击数应为 11+1")
            multipliers = [find_nodes(area, "CreateNormalAttack")[0][6][0]["min"] for area in areas]
            self.assertAlmostEqual(multipliers[0] * 11 + multipliers[1], total, places=4)
            normal = find_nodes(fever[0][2], "CreateHitArea")     # 第二分支 = 非 FEVER 原版
            self.assertEqual([area[14][1] for area in normal], [3 if level > 1 else 2, 1])

    def test_batch2_toughness_follows_the_candidate_state(self):
        """第二批削韧：援护 629 p13 30→3；Fever 特殊 PF 分支 60/60/75 → 15/20/25（回写前仍是改前值）。"""
        done = batch2_written_back()
        for name in ("soriz_assist_eugen", "soriz_assist_jin", "soriz_assist_duo"):
            attacks = find_nodes(program(KIT.AP.format(name)), "CreateNormalAttack")
            self.assertEqual([a[13] for a in attacks], [[{"min": 3 if done else 30, "max": 3 if done else 30}]])
        for level, (before, after) in {1: (60, 15), 2: (60, 20), 3: (75, 25)}.items():
            tree = program(KIT.PF_PATH.format(k=KIT.PF_KEY, n=level))
            fever = find_nodes(tree, "ConditionalsFeverMode")[0]
            for branch, want in ((fever[1], after if done else before), (fever[2], after)):
                total = sum(area[14][1] * find_nodes(area, "CreateNormalAttack")[0][13][0]["max"]
                            for area in find_nodes(branch, "CreateHitArea"))
                self.assertEqual(total, want, f"lv{level}")

    def test_skill_hurts_self_and_stacks_three_crows(self):
        tree = program(KIT.SKILL_PATH.format(KIT.CODE, "1"))
        ratio = find_nodes(tree, "CreateRatioAttack")[0]
        self.assertEqual([ratio[1], ratio[2], ratio[3][0]["min"]], [-17, 2, 0.25])
        stacks = [node for node in find_nodes(tree, "ACUnique") if node[1] == KIT.CROWS]
        self.assertEqual(stacks[0][2][0]["min"], 3)
        attack = find_nodes(tree, "CreateNormalAttack")[0]
        self.assertEqual(attack[2], 255, "元素位写 255 才继承角色元素")
        self.assertEqual(attack[6][0]["min"], 40.0)

    def test_skill_effect_is_an_official_path_reference(self):
        """大招演出整路径引用官方 donor，不再往包里塞自绘大表（裁决 §4）。

        跨 code_name 引用官方特效是安全的（记忆卡 wf-effect-family-under-codename
        2026-09-10 更正）；参数整块搬官方节点，只有主体和偏移是我方改的。
        """
        for level in ("1", "2"):
            tree = program(KIT.SKILL_PATH.format(KIT.CODE, level))
            paths = [node[2][-1] for node in find_nodes(tree, "ShowEffect")]
            self.assertEqual(paths, [KIT.FX_OFFICIAL_SKILL])
            node = find_nodes(tree, "ShowEffect")[0]
            self.assertEqual(node[3], 11, "演出挂在判定区绑定的目标上")
            self.assertEqual([node[7], node[8], node[9]], [0, 0, 0])

    def test_no_program_references_a_dropped_effect(self):
        dropped = {f"{KIT.EFFECT_DIR}/{eid}/effect" for eid in KIT.FX_DROP}
        for logical in sorted((ROOTS / "battle/action").rglob("*.action.dsl.amf3.deflate")):
            blob = json.dumps(C.amf_parse(logical.read_bytes()), ensure_ascii=False)
            for path in dropped:
                self.assertNotIn(path, blob, f"{logical.name} 还引着已拿掉的 {path}")


class PanelAndTableContracts(unittest.TestCase):
    def test_every_row_string_id_has_a_custom_ability_string_row(self):
        # 包内表 = live 底表 + 自有键；只断言自有键齐全（认领范围在 manifest 契约里查）。
        keys = set(flat(KIT.CAS))
        self.assertTrue(set(KIT.CAS_KEYS) <= keys, set(KIT.CAS_KEYS) - keys)
        string_ids = {rows(KIT.LEADER, KIT.CID_S)[0][0]}
        string_ids |= {rows(KIT.ABILITY, f"{KIT.CID}{i}")[0][0] for i in range(1, 7)}
        self.assertEqual({f"desc_override_{s}" for s in string_ids}, set(KIT.DESC_KEYS))

    def test_panel_text_obeys_the_batch_rules(self):
        table = flat(KIT.CAS)
        for key in KIT.DESC_KEYS:
            text = C.csv_split(table[key])[0][0]
            self.assertEqual(K.panel_problems(text), [], key)
            self.assertNotIn("生命值100%以下", text)

    def test_power_flip_override_row_points_at_the_three_written_trees(self):
        row = C.csv_split(flat(KIT.PFA)[KIT.PF_KEY])[0]
        self.assertEqual(row[:3], [KIT.PF_PATH.format(k=KIT.PF_KEY, n=n) for n in (1, 2, 3)])
        layout = KIT.LAY["leader_ability"]
        row722 = [r for r in rows(KIT.LEADER, KIT.CID_S)
                  if r[layout["instant_content"]] == "722"][0]
        self.assertEqual(row722[layout["instant_content"] + 35], KIT.PF_KEY)
        self.assertEqual(row722[layout["instant_content"] + 37], KIT.PF_STRING)

    def test_action_skill_keeps_energy_and_uses_the_design_texts(self):
        texts = design()["plan"]["texts"]["character"]
        import wf_gbf_duo as G
        import wf_seasonal7_build as B
        ctx = B.KitContext(G.context(KIT.CODE))
        inner = ctx.pkg_nested(KIT.CODE)
        self.assertEqual(sorted(inner), ["1", "2"])
        for level, cells in inner.items():
            self.assertEqual(cells[4], "550", "技能能量必须是设计稿的 550")
            self.assertEqual(cells[0], texts["skill1"])
            self.assertEqual(cells[1], texts["desc1"])
        text_row = C.csv_split(flat(KIT.TEXT)[KIT.CID_S])[0]
        self.assertEqual(text_row[3], texts["title"])
        self.assertEqual(text_row[5], texts["desc1"])
        self.assertEqual(text_row[10], texts["leader"])


class DonorLookupContracts(unittest.TestCase):
    """store donor 取法（2026-09-27）：键内按内容取第一条匹配，标签不带行号。

    全表「第一条 ck=724」会被别的键抢先（1.4.1050 风巨蜥能力3 改成 724 的事故）；键#行又会随该键增删行漂移
    （稻穗 inaho2 把 1399951 从 6 行删到 4 行，724 行从第 4 行挪到第 2 行）。"""

    @staticmethod
    def _row(ck: str, tk: str, marker: str = "") -> list[str]:
        lay = KIT.LAY["ability"]
        row = [""] * KIT.NCOLS["ability"]
        row[0] = marker
        row[KIT.MODE_COL["ability"]] = "0"                 # 瞬发
        row[lay["instant_trigger"]] = tk
        row[lay["instant_content"]] = ck
        return row

    @staticmethod
    def _rows(store: dict) -> "KIT.Rows":
        class Ctx:
            def live_flat(self, _logical):
                return {key: C.csv_join(rows) for key, rows in store.items()}

            official_flat = live_flat

            def csv_split(self, text):
                return C.csv_split(text)
        return KIT.Rows(Ctx())

    def test_key_scoped_content_lookup_survives_row_moves_in_that_key(self):
        other = self._row("724", "2", "wind_lizard_724")   # 别的键更早出现的 724
        before = {"1499983": [other],
                  "1399951": [self._row("211", "0"), self._row("226", "4"), self._row("211", "65"),
                              self._row("461", "8"), self._row("724", "2", "inaho_724"), self._row("211", "23")]}
        after = {"1499983": [other],
                 "1399951": [self._row("211", "0"), self._row("226", "4"), self._row("724", "2", "inaho_724"),
                             self._row("211", "23")]}
        for store in (before, after):
            name, row = self._rows(store).find("ability", src="store", key="1399951", mode="I", ck=724)
            self.assertEqual(("store:ability[1399951]{mode=I,ck=724}", "inaho_724"), (name, row[0]))
        # 对照：全表检索被别的键抢先；键#行在删行后取不到（或取到别的行）。
        name, row = self._rows(before).find("ability", src="store", mode="I", ck=724)
        self.assertEqual(("store:ability[1499983]#0", "wind_lizard_724"), (name, row[0]))
        self.assertEqual("inaho_724", self._rows(before).find("ability", src="store", key="1399951", idx=4)[1][0])
        with self.assertRaises(KIT.KitError):
            self._rows(after).find("ability", src="store", key="1399951", idx=4)
        # 键内无匹配 / 只给键不给行号也不给条件：拒绝。
        with self.assertRaises(KIT.KitError):
            self._rows(after).find("ability", src="store", key="1399951", mode="I", ck=629)
        with self.assertRaises(KIT.KitError):
            self._rows(after).find("ability", src="store", key="1399951")

    @unittest.skipUnless(DESIGN.is_file(), "design/soriz.json (gitignored work/) absent")
    def test_fever_drain_row_donor_is_recorded_without_a_row_number(self):
        records = design()["plan"]["ability"]["keys"]["1299863"]["records"]
        record = next(r for r in records if r["req"].startswith("A3#8 "))
        self.assertEqual("store:ability[1399951]{mode=I,ck=724}", record["donor"])
        self.assertEqual("724", record["cells"]["47"])


class PackageContracts(unittest.TestCase):
    def test_manifest_declares_the_real_capabilities_and_new_tables(self):
        manifest = json.loads((PACK / "package/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["required_capabilities"],
                         ["kyubi-fever-ratio-v1", "panel-description-override-v2"])
        self.assertNotIn("gbf-soriz-mechanics-v1", manifest["required_capabilities"])
        claimed = {t["logical_path"]: set(t.get("outer_keys") or []) for t in manifest["tables"]}
        # 漏认领的新键会在 rebase 时被静默回滚。
        self.assertEqual(claimed[KIT.UNIQUE], {str(u) for u in KIT.UNIQUE_IDS})
        self.assertEqual(claimed[KIT.CAS], set(KIT.CAS_KEYS))
        self.assertEqual(claimed[KIT.PFA], {KIT.PF_KEY})
        self.assertEqual(len(manifest["skills"]["programs"]), 14)
        self.assertEqual(manifest["qa"]["required_assets_present"], 37)

    def test_effect_tables_are_slim_enough_for_the_atlas_budget(self):
        import wf_atlas_budget_check as A
        for eid in KIT.FX_DROP:
            self.assertFalse((ROOTS / f"{KIT.EFFECT_DIR}/{eid}").exists(), f"{eid} 应已拿掉")
        total = 0
        for path in sorted((ROOTS / KIT.EFFECT_DIR).rglob("*.png")):
            dims = A.png_dims_from_bytes(path.read_bytes()[:64])
            total += dims[0] * dims[1]
            self.assertLessEqual(max(dims), 1024, path.name)
        # 设计稿自己的目标：仁援护 ≤ 0.13 Mpx；连欧根那张 0.016 一起不超过 0.15。
        self.assertLess(total / 1e6, 0.15)

    def test_both_five_boss_rooms_still_fit_with_this_package(self):
        """裁决 §2 的真门槛是「单角色 ≤5% **且** fits」。

        这间房基线本身就已经 92.3% 满（attribution=pre-existing），fits 随货架形状
        非单调翻转，所以只盯 layer0_pct 是抓不住回归的——必须真跑装箱。
        """
        import wf_atlas_budget_check as A
        report = A.evaluate(A.read_pack(str(PACK)), A.load_roster(),
                            A.DimSource(A.load_roster()))
        self.assertLessEqual(report["subject"]["layer0"]["fill_pct"], 5.0)
        for scenario in report["scenarios"]:
            self.assertTrue(scenario["fits"], f"{scenario['scenario']} 装不下")


if __name__ == "__main__":
    unittest.main()
