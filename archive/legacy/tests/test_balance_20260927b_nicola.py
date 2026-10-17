# -*- coding: utf-8 -*-
"""妮可拉·中秋 119991 ``sorceress_teacher_moon`` 2026-09-27 平衡第二批：能力3 行2–6 限次 "0"→(None)。

fixture = live 输入快照（``fixtures/balance_20260927b_nicola.json``，stage_batch.make_read(live_only=True)），
驱动 ``revise()``：只改五格 c34、其余行与本行其余列逐字保留、层数门契约（受益行与消耗行同形、消耗行最后）、
死限次门禁改前红改后绿、面板不改且与数据一致、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、
合法性门禁为空、官方同形先例、生成器（design/nicola.json 驱动）一致、设计镜像已同步、候选干跑。
本单元不改 DSL（``out["dsl"] == {}``），故无 AMF3 往返/DSL 门禁项。
生成器装配对比需要 ``.cdn/cn`` 官方基线与 live store（缺时跳过）；镜像与候选在 gitignore 的 work/ 下（缺时跳过）。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_nicola as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_midautumn_kit_nicola as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_nicola.json'
WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]
DESIGN_PATH = ROOT / M.DESIGN_REL
#: 候选 ma-nicola manifest 现有的 required_capabilities（改后不新增）。
CANDIDATE_CAPABILITIES = {"panel-description-override-v2"}
ROWS = list(M.ROWS)
DESCRIBE = (
    "火·编成≥6 时: 技能最大≥1 → 自身 状态固有 100%×1次",
    "火·编成≥6 且 状态固有[固有11999101] 时: 技能发动≥1 → 赋予触发者 技能槽 10%",
    "火·编成≥6 且 状态固有[固有11999101] 时: 技能发动≥1 → 赋予触发者 攻击力 50%",
    "火·编成≥6 且 状态固有[固有11999101] 时: 技能发动≥1 → 自身 2号位技能槽 5%",
    "火·编成≥6 且 状态固有[固有11999101] 时: 技能发动≥1 → 自身 技能槽充能 5%",
    "火·编成≥6 且 状态固有[固有11999101] 时: 技能发动≥1 → 自身 消耗固有状态 100%",
    "火·编成≥6 时: 赋予全队(火) 抗性火↓攻击特攻 300%",
    "火·编成≥6 时: 赋予全队(火) 抗性火↓技能特攻 300%",
    "火·编成≥6 时: 赋予全队(火) 独立乘区技能伤害 15%",
)


def load_raw() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def load_fixture() -> dict:
    return {kind: value for kind, value in load_raw().items() if not kind.startswith("_")}


def reader(data: dict):
    def read(kind, key):
        return data[kind][key]
    return read


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


def _kit_ctx():
    import wf_midautumn_common as MC
    import wf_midautumn_specs as MS
    import wf_seasonal7_build as B
    return B.KitContext(MC.MAPack(MS.get_spec("nicola"), record_sources=False))


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old = cls.live["ability"][M.ABILITY_KEY]
        cls.new = cls.out["ability"][M.ABILITY_KEY]

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys},
                         set(M.BEFORE))

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), (str(K.CID), K.CODE))
        self.assertEqual(M.ABILITY_KEY, K.ABILITY_KEYS[2])
        self.assertEqual(M.CAS_SLOT3, K.CAS_OVERRIDE)
        self.assertEqual(M.UID, K.UID)
        self.assertEqual(M.MAIN_ICON, K.MAIN_ICON)
        self.assertEqual(M.ELEMENT, K.ELEMENT)
        self.assertEqual(M.PACKAGES, ["ma-nicola"])
        self.assertEqual(M.PACKAGE_VERSION, {"ma-nicola": "1.0.1"})   # 候选现值 1.0.0，只升不降
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertFalse(hasattr(M, "UNITS"))                        # 单角色模块

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["ability"]), {M.ABILITY_KEY})
        for kind in ("leader", "cas", "text", "table", "action", "dsl", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        json.dumps(out["notes"], ensure_ascii=False)
        for key in out["ability"]:   # RevisionCandidate 命名空间
            self.assertTrue(key.startswith(M.CID), key)

    def test_only_c34_of_rows_1_to_5_change(self):
        self.assertEqual((len(self.old), len(self.new)), (9, 9))
        self.assertEqual([i for i in range(9) if self.old[i] != self.new[i]], ROWS)
        for i in ROWS:
            old, new = self.old[i], self.new[i]
            self.assertEqual((len(old), len(new)), (126, 126))
            self.assertEqual([c for c in range(126) if old[c] != new[c]], [34], i)
            self.assertEqual((old[34], new[34]), ("0", "(None)"), i)

    def test_untouched_rows_are_verbatim(self):
        for i in (0, 6, 7, 8):
            self.assertEqual(self.new[i], self.old[i], i)
        self.assertEqual(self.new[0][34], "(None)")                  # 461 加层行本来就不限次
        self.assertEqual((self.new[0][27], self.new[0][47], self.new[0][68]), ("24", "461", M.UID))

    def test_values_targets_and_gate_are_kept(self):
        """作者：充能数值不动；目标、前置 187、I23 puller 4 + Red、CT 0 逐格不动。"""
        want = {1: ("211", "7", "10000"), 2: ("32", "7", "50000"), 3: ("245", "0", "5000"),
                4: ("35", "0", "5000"), 5: ("525", "0", "100000")}
        for i, (kind, target, value) in want.items():
            row = self.new[i]
            self.assertEqual((row[47], row[48], row[51], row[52]), (kind, target, value, value), i)
            self.assertEqual((row[6], row[9], row[11]), ("2", "600000", "Red"), i)          # 火共鸣
            self.assertEqual((row[13], row[14], row[19]), ("187", "0", M.UID), i)            # 持有月讲
            self.assertEqual((row[27], row[28], row[29]), ("23", "4", "Red"), i)             # 除自身外火角色施技
            self.assertEqual((row[30], row[31], row[35]), ("100000", "100000", "0"), i)
        self.assertEqual(self.new[5][68], M.UID)

    def test_layer_gate_contract_holds(self):
        """受益行与消耗行前置/触发块同形、消耗行排最后（生成器 consume_order_problems）。"""
        self.assertEqual(K.consume_order_problems(self.new), [])
        self.assertEqual(K.consume_order_problems(self.old), [])
        for i in ROWS:
            self.assertEqual(self.new[i][6:35], self.new[M.CONSUME_ROW][6:35], i)

    def test_dead_trigger_limit_gate_is_red_before_and_green_after(self):
        self.assertEqual(len(M.dead_trigger_limit_problems(self.old)), 5)
        self.assertEqual(M.dead_trigger_limit_problems(self.new), [])
        self.assertEqual(len(K.dead_trigger_limit_problems({M.ABILITY_KEY: self.old})), 5)
        self.assertEqual(K.dead_trigger_limit_problems({M.ABILITY_KEY: self.new}), [])
        empty = deepcopy(self.new)
        empty[3][34] = ""                                             # 空串同样 = 0 次
        self.assertEqual(len(K.dead_trigger_limit_problems({M.ABILITY_KEY: empty})), 1)

    def test_auto_describe_is_unchanged(self):
        """(None) 与 "0" 在自动文案里都不显示「限N次」；面板走 desc_override，这里只防描述器漂移。"""
        self.assertEqual(tuple(D.describe_line(row, "ability") for row in self.new), DESCRIBE)
        self.assertEqual(tuple(D.describe_line(row, "ability") for row in self.old), DESCRIBE)

    def test_panel_is_unchanged_and_agrees_with_the_data(self):
        text = self.live["cas"][M.CAS_SLOT3][0][0]
        lines = text.split("\n")
        self.assertEqual(tuple(lines), M.PANEL_LINES)
        line = lines[M.PANEL_TRIGGER_LINE]
        self.assertIn("除自身外的火属性角色发动技能时", line)                     # puller 4 + Red
        self.assertIn("消耗1层「月讲」", line)                                    # 525
        self.assertIn("技能槽＋10%、攻击力＋50%", line)                           # 211 / 32
        self.assertIn("技能槽上限＋5%、技能充能速度＋5%", line)                   # 245 / 35
        self.assertTrue(line.endswith("（可叠加）"), line)                        # (None) 不限次
        self.assertNotIn("最多", line)
        for row in self.new[1:6]:
            self.assertEqual(row[34], "(None)")

    def test_panel_texts_obey_the_project_rules(self):
        text = self.live["cas"][M.CAS_SLOT3][0][0]
        self.assertNotIn("／", text)
        for line in text.split("\n"):
            self.assertTrue(line.startswith(M.MAIN_ICON), line)       # 主位限制槽每行带 Ⓜ
            self.assertEqual(KL.panel_problems(line.replace(M.MAIN_ICON, "")), [], line)
            self.assertTrue(line.replace(M.MAIN_ICON, "").startswith("火属性共鸣时："), line)
        self.assertEqual(L.panel_override_capability(M.CAS_SLOT3), "panel-description-override-v2")

    def test_native_legality_gates_are_empty(self):
        cas_keys = {K.CAS_CHANGE_SKILL, K.CAS_OVERRIDE}
        for index, row in enumerate(self.new):
            label = f"ability:{M.ABILITY_KEY}#{index}"
            self.assertEqual(L.client_legality_problems("ability", row), [], label)
            self.assertEqual(L.declared_block_field_problems("ability", row), [], label)
            self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, kind="ability"), [], label)
            self.assertEqual(L.ability_element_column_problems("ability", row, M.ELEMENT), [], label)
            self.assertEqual(KL.row_problems("ability", row, K.ELEMENT), {}, label)
            self.assertLessEqual(set(L.required_client_capabilities("ability", row)),
                                 CANDIDATE_CAPABILITIES, label)

    def test_official_precedent_shape(self):
        """官方 1510141#0：I23 + puller 4（除自身任一）+ 组 → 触发者 t7，c34 = (None)。"""
        precedent = load_raw()["_official_precedent"]["ability:1510141#0"]
        self.assertEqual((precedent[27], precedent[28], precedent[34], precedent[48]),
                         ("23", "4", "(None)", "7"))
        for i in (1, 2):
            row = self.new[i]
            self.assertEqual((row[27], row[28], row[34], row[48]), ("23", "4", "(None)", "7"), i)
            self.assertEqual(row[30:32], precedent[30:32], i)

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["ability"][M.ABILITY_KEY][1][34] = "mutated"
        out["ability"][M.ABILITY_KEY][0][0] = "mutated"
        self.assertEqual(data, self.live)

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            data = deepcopy(self.live)
            if kind == "cas":
                data[kind][key][0][0] += "。"
            else:
                data[kind][key][1][35] = "60"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))
            data = deepcopy(self.live)
            data[kind][key] = data[kind][key] + [list(data[kind][key][0])]
            with self.assertRaises(ValueError):
                M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        """重跑在已改的 live 上必须拒绝（fail closed）。"""
        data = deepcopy(self.live)
        data["ability"].update(deepcopy(self.out["ability"]))
        with self.assertRaises(ValueError):
            M.revise(reader(data))
        with self.assertRaises(ValueError):
            M.ability3_rows(self.new)

    def test_row_locator_is_content_based(self):
        """绕过 BEFORE 直接调纯函数：目标行形状不对也要拒绝。"""
        mutations = (
            lambda r: r.__setitem__(slice(4, 6), [r[5], r[4]]),     # 消耗行不在最后
            lambda r: r[2].__setitem__(34, "10"),                   # 已有限次
            lambda r: r[2].__setitem__(51, "15000"),                # 数值漂移
            lambda r: r[3].__setitem__(28, "5"),                    # 触发方换成全队任一
            lambda r: r[1].__setitem__(80, "x"),                    # 多出非空列
            lambda r: r[0].__setitem__(34, "0"),                    # 加层行漂移
            lambda r: r[0].pop(),                                   # 列宽不对
            lambda r: r.pop(),                                      # 记录条数不对
        )
        for n, mutate in enumerate(mutations):
            rows = deepcopy(self.old)
            mutate(rows)
            with self.assertRaises(ValueError, msg=str(n)):
                M.ability3_rows(rows)
        text = deepcopy(self.live["cas"][M.CAS_SLOT3])
        text[0][0] = text[0][0].replace("（可叠加）", "（最多10次）")
        with self.assertRaises(ValueError):
            M.check_panel(text)


class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_midautumn_kit_nicola（design/nicola.json 驱动）重跑不能把 "0" 带回来。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old = cls.live["ability"][M.ABILITY_KEY]

    def setUp(self):
        if not DESIGN_PATH.is_file():
            self.skipTest("midautumn design (gitignored work/) absent")
        self.design = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))

    def test_design_row_final_equals_revise_output(self):
        records = self.design["plan"]["ability"]["keys"][M.ABILITY_KEY]["records"]
        self.assertEqual([[str(x) for x in r["row_final"]] for r in records],
                         self.out["ability"][M.ABILITY_KEY])
        for i in ROWS:
            self.assertEqual(records[i]["cells"]["34"], "(None)", i)
            self.assertIn("(None)", records[i]["why"], i)

    def test_design_cells_replay_onto_the_row_final(self):
        """cells 是 donor 之上的逐格改；本批只动 c34 ⇒ 改前 cells 对应的 row_final 只差这一格。"""
        records = self.design["plan"]["ability"]["keys"][M.ABILITY_KEY]["records"]
        for i in ROWS:
            final = [str(x) for x in records[i]["row_final"]]
            self.assertEqual(final[34], records[i]["cells"]["34"], i)
            self.assertEqual(final[:34] + final[35:], self.old[i][:34] + self.old[i][35:], i)

    def test_kit_gate_rejects_the_dead_limit(self):
        records = self.design["plan"]["ability"]["keys"][M.ABILITY_KEY]["records"]
        rows = {M.ABILITY_KEY: [[str(x) for x in r["row_final"]] for r in records]}
        self.assertEqual(K.dead_trigger_limit_problems(rows), [])
        rows[M.ABILITY_KEY][1][34] = "0"
        self.assertEqual(len(K.dead_trigger_limit_problems(rows)), 1)

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_build_equals_revise_output(self):
        ctx = _kit_ctx()
        rows_by_key, evidence = K.build_ability_rows(ctx, K.load_design(ctx.root))
        self.assertEqual(rows_by_key[M.ABILITY_KEY], self.out["ability"][M.ABILITY_KEY])
        self.assertEqual(K.dead_trigger_limit_problems(rows_by_key), [])
        self.assertEqual(K.consume_order_problems(rows_by_key[M.ABILITY_KEY]), [])
        described = [ev["describe"] for ev in evidence if ev["label"].startswith(f"{M.ABILITY_KEY}#")]
        self.assertEqual(tuple(described), DESCRIBE)

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_rejects_a_design_that_reverts_to_zero(self):
        ctx = _kit_ctx()
        design = K.load_design(ctx.root)
        entry = design["plan"]["ability"]["keys"][M.ABILITY_KEY]["records"][1]
        entry["cells"]["34"] = "0"
        with self.assertRaises(K.KitError):                            # row_final 逐格核对先炸
            K.build_ability_rows(ctx, design)


class MirrorTests(unittest.TestCase):
    PATHS = (ROOT / M.DESIGN_REL, ROOT / M.PANEL_REL)

    def setUp(self):
        if not all(path.is_file() for path in self.PATHS):
            self.skipTest("midautumn design mirrors missing")
        self.docs = [json.loads(path.read_text(encoding="utf-8")) for path in self.PATHS]

    def test_mirrors_are_already_synced(self):
        self.assertEqual(M.sync_mirrors(ROOT, write=False), [])
        design, panel = self.docs
        block = design["rework1"][M.MIRROR_TAG]
        self.assertEqual(block["module"], "mod-tools/wf_balance_20260927b_nicola.py")
        three = next(entry for entry in panel["abilities"] if entry["index"] == 3)
        # 第三轮面板合并（wf_balance_20260927c_panels）同步镜像后，能力3 是合并稿；本批（面板不改）两种形态都接受。
        import wf_balance_20260927c_panels as P3
        lines = (P3.PANELS_BY_CAS[M.CAS_SLOT3]["after"] if P3.MODULE_TAG in panel else M.PANEL_LINES)
        self.assertEqual([line["text"] for line in three["lines"]],
                         [line.replace(M.MAIN_ICON, "") for line in lines])
        self.assertEqual(panel["notes"][-1], M.MIRROR_NOTE)
        # 设计稿覆盖串（不带主位图标）＝ live 面板去掉图标（本批面板不改；第三轮合并后 = 合并稿）
        rows = {r["key"]: r["text"] for r in design["plan"]["texts"]["custom_ability_string"]["rows"]}
        self.assertEqual(K._apply_main_icon(rows[M.CAS_SLOT3]), "\n".join(lines))

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
        # 第三轮面板合并（wf_balance_20260927c_panels）暂存回写后，候选再升一版；本批改过的键不受其影响。
        import wf_balance_20260927c_panels as P3
        want = P3.staged_version(current, M.PACKAGES[0]) or M.PACKAGE_VERSION[M.PACKAGES[0]]
        self.assertGreaterEqual(tuple(map(int, want.split("."))),
                                tuple(map(int, current["package_version"].split("."))))
        candidate = RevisionCandidate(ROOT, WORKSPACE, character_id=M.CID, code_name=M.CODE,
                                      snapshot_key="revision_20260927b",
                                      package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
                                      baseline_factory=lambda *a, **k: None,
                                      reviewed_input_drift=M.REVIEWED_DRIFT)
        logical = "master/ability/ability.orderedmap"
        if current.get("snapshot", {}).get("revision_20260927b") is not None:
            # 主会话暂存回写后：候选 = 本批输出。
            self.assertEqual(current["package_version"], want)
            rows = X.unpack(candidate.read("common", logical))
            self.assertEqual(X.csv_read(rows[M.ABILITY_KEY]), out["ability"][M.ABILITY_KEY])
            return
        rows = X.unpack(candidate.read("common", logical))
        self.assertEqual(X.csv_read(rows[M.ABILITY_KEY]), load_fixture()["ability"][M.ABILITY_KEY])
        candidate.splice(logical, out["ability"])
        evidence = candidate.finish({"dry_run": True}, apply=False)
        self.assertFalse(evidence["applied"])
        self.assertEqual(len(evidence["changed_files"]), 1)
        self.assertEqual(before, manifest.read_bytes())


if __name__ == "__main__":
    unittest.main()
