# -*- coding: utf-8 -*-
"""索恩 159994 ``tweyen_light`` 2026-09-27 平衡第二批：能力3「自身发动技能时」两行改成真的自身施技。

fixture = live 输入快照（``fixtures/balance_20260927b_thorn.json``，stage_batch.make_read(live_only=True)），
驱动 ``revise()``：逐行核对 c27/c28/c29 与面板、只改 #1/#2 的 c28/c29、其余行与本行其余列逐字保留、
官方自身施技写法先例（同母本 1510813#2、2310012#0、1110813#2）、面板不改且与数据一致、BEFORE 漂移拒绝、
不改输入、对自身输出重跑拒绝、合法性门禁为空、生成器（ABILITY_DONORS + design/thorn.json）一致、
设计镜像已同步、候选干跑。本单元不改 DSL（``out["dsl"] == {}``），故无 AMF3 往返/DSL 门禁项。
生成器装配对比需要 ``.cdn/cn`` 官方基线与 live store（缺时跳过）；镜像与候选在 gitignore 的 work/ 下（缺时跳过）。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_thorn as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_midautumn_kit_thorn as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927b_thorn.json"
WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]
DESIGN_PATH = ROOT / M.DESIGN_REL
#: 候选 ma-thorn manifest 现有的 required_capabilities（改后不新增）。
CANDIDATE_CAPABILITIES = {"panel-description-override-v2"}
ROWS = list(M.ROWS)
DESCRIBE = (
    "技能发动≥1 → 赋予全队(光) 状态技能伤害 200%(10秒)×1次[累积上限99]",
    "技能发动≥1(限10次) → 自身 技能伤害 20%",
    "技能发动≥1(限10次) → 赋予全队(光) 技能槽充能 1.5%",
    "光·编成≥6 时: 持续·任一敌方状态计数减益≥1 → 自身 技能伤害 40%",
    "光·编成≥6 时: 技能发动≥1(限7次) → 赋予全队(光) 技能伤害 50%",
    "光·编成≥6 时: 技能发动≥1(限7次) → 赋予全队(光) 攻击力 50%",
    "光·编成≥6 时: 技能发动≥1 → 自身 追加连击 50",
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
    return B.KitContext(MC.MAPack(MS.get_spec("thorn"), record_sources=False))


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old = cls.live["ability"][M.ABILITY_KEY]
        cls.new = cls.out["ability"][M.ABILITY_KEY]
        cls.panel = cls.live["cas"][M.CAS_SLOT3][0][0].split("\n")

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys},
                         set(M.BEFORE))

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), (str(K.CID), K.CODE))
        self.assertEqual(M.ABILITY_KEY, K.ABILITY_KEYS[2])
        self.assertEqual(M.CAS_SLOT3, K.CAS_ABILITY[3])
        self.assertEqual((M.ELEMENT, M.MAIN_ICON), (K.ELEMENT, K.MAIN_ICON))
        self.assertEqual(M.PACKAGES, ["ma-thorn"])
        self.assertEqual(M.PACKAGE_VERSION, {"ma-thorn": "1.0.1"})   # 候选现值 1.0.0，只升不降
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertFalse(hasattr(M, "UNITS"))

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["ability"]), {M.ABILITY_KEY})
        for kind in ("leader", "cas", "text", "table", "action", "dsl", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        json.dumps(out["notes"], ensure_ascii=False)

    def test_row_audit_before(self):
        """逐行核对（改前）：面板写「自身发动技能时」的三行里，#0 已是自身，#1/#2 是 7+White。"""
        self.assertEqual(M.trigger_of(self.old[0]), ("23", "0", ""))
        self.assertEqual(M.trigger_of(self.old[1]), ("23", "7", "White"))
        self.assertEqual(M.trigger_of(self.old[2]), ("23", "7", "White"))
        self.assertEqual(M.trigger_of(self.old[4]), ("23", "7", "White"))
        self.assertEqual(M.trigger_of(self.old[5]), ("23", "7", "White"))
        self.assertEqual(M.trigger_of(self.old[6]), ("23", "0", ""))
        self.assertEqual(self.old[3][27], "")                           # during 136 行无瞬发触发
        for i in M.SELF_PANEL_ROWS:
            self.assertTrue(self.panel[i].startswith(M.SELF_PANEL_PREFIX), i)

    def test_only_c28_c29_of_rows_1_2_change(self):
        self.assertEqual((len(self.old), len(self.new)), (7, 7))
        self.assertEqual([i for i in range(7) if self.old[i] != self.new[i]], ROWS)
        for i in ROWS:
            old, new = self.old[i], self.new[i]
            self.assertEqual((len(old), len(new)), (126, 126))
            self.assertEqual([c for c in range(126) if old[c] != new[c]], [28, 29], i)
            self.assertEqual((old[28], old[29]), ("7", "White"), i)
            self.assertEqual((new[28], new[29]), ("0", ""), i)

    def test_untouched_rows_are_verbatim(self):
        for i in (0, 3, 4, 5, 6):
            self.assertEqual(self.new[i], self.old[i], i)

    def test_limits_ct_values_and_targets_are_kept(self):
        """作者：充能数值不动；限次 10、CT 0、目标、无前置逐格不动。"""
        self.assertEqual((self.new[1][47], self.new[1][48], self.new[1][51], self.new[1][52]),
                         ("34", "0", "20000", "20000"))
        self.assertEqual((self.new[2][47], self.new[2][48], self.new[2][49], self.new[2][51], self.new[2][52]),
                         ("35", "5", "White", "1500", "1500"))
        for i in ROWS:
            row = self.new[i]
            self.assertEqual((row[30], row[31], row[34], row[35]), ("100000", "100000", "10", "0"), i)
            self.assertEqual((row[6], row[11]), ("0", ""), i)             # 无共鸣前置（面板也没写）

    def test_self_panel_rows_all_trigger_on_self(self):
        for i in M.SELF_PANEL_ROWS:
            self.assertEqual(M.trigger_of(self.new[i]), M.SELF_TRIGGER, i)
        for i in M.PARTY_TRIGGER_ROWS:                                   # 面板第 5 行「光属性角色发动技能时」
            self.assertEqual(M.trigger_of(self.new[i]), ("23", "7", "White"), i)
        self.assertTrue(self.panel[4].startswith(M.PARTY_PANEL_PREFIX))
        self.assertEqual(K.check_self_trigger_rows({M.ABILITY_KEY: self.new}),
                         [f"{M.ABILITY_KEY}#{i}" for i in M.SELF_PANEL_ROWS])
        with self.assertRaises(K.KitError):
            K.check_self_trigger_rows({M.ABILITY_KEY: self.old})

    def test_official_self_trigger_precedent(self):
        """官方自身施技写法 c27=23,c28='0',c29=''；同母本 1510813#0/#1 才是 7+White（本次改掉的来源）。"""
        prec = load_raw()["_official_precedent"]
        self.assertEqual(M.trigger_of(prec["ability:1510813#2"]), M.SELF_TRIGGER)
        self.assertEqual(M.trigger_of(prec["ability:2310012#0"]), M.SELF_TRIGGER)
        self.assertEqual(M.trigger_of(prec["ability:1110813#2"]), M.SELF_TRIGGER)
        self.assertEqual(M.trigger_of(prec["ability:1510813#0"]), ("23", "7", "White"))
        self.assertEqual(M.trigger_of(prec["ability:1510813#1"]), ("23", "7", "White"))
        # 同内容 kind 的官方自身施技先例：自身技伤（34→t0）、全队(属性)充能（35→t5+组）
        self.assertEqual((prec["ability:2310012#0"][47], prec["ability:2310012#0"][48]), ("34", "0"))
        self.assertEqual((prec["ability:1110813#2"][47], prec["ability:1110813#2"][48]), ("35", "5"))
        # 触发块其余格（阈值/CT）与先例同形；donor 其余列（除 0/28/29/51/52）逐字相同
        for i, donor in ((1, "ability:1510813#0"), (2, "ability:1510813#1")):
            row, src = self.new[i], prec[donor]
            self.assertEqual(row[30:32] + row[35:36], src[30:32] + src[35:36], i)
            self.assertEqual([c for c in range(126) if row[c] != src[c]], [0, 28, 29, 51, 52], i)
            self.assertEqual(row[27:30], prec["ability:1510813#2"][27:30], i)

    def test_auto_describe_is_unchanged(self):
        """describe 不渲染 puller；面板走 desc_override，这里只防描述器漂移。"""
        self.assertEqual(tuple(D.describe_line(row, "ability") for row in self.new), DESCRIBE)
        self.assertEqual(tuple(D.describe_line(row, "ability") for row in self.old), DESCRIBE)

    def test_panel_is_unchanged_and_agrees_with_the_data(self):
        self.assertEqual(tuple(self.panel), M.PANEL_LINES)
        self.assertIn("自身技能伤害＋20%（最多叠加10次）", self.panel[1])
        self.assertIn("技能充能速度＋1.5%（最多叠加10次）", self.panel[2])
        self.assertEqual((int(self.new[1][51]) / 1000, self.new[1][34]), (20.0, "10"))
        self.assertEqual((int(self.new[2][51]) / 1000, self.new[2][34]), (1.5, "10"))

    def test_panel_texts_obey_the_project_rules(self):
        text = "\n".join(self.panel)
        self.assertNotIn("／", text)
        for line in self.panel:
            self.assertTrue(line.startswith(M.MAIN_ICON), line)       # 主位限制槽每行带 Ⓜ
            self.assertEqual(KL.panel_problems(line.replace(M.MAIN_ICON, "")), [], line)
        self.assertEqual(L.panel_override_capability(M.CAS_SLOT3), "panel-description-override-v2")
        # 本批面板不改；第三轮面板合并（wf_balance_20260927c_panels）后生成器是合并稿，本批面板 = 合并稿的改前文字。
        import wf_balance_20260927c_panels as P3
        slot3 = P3.PANELS_BY_CAS[M.CAS_SLOT3]
        self.assertEqual(tuple(self.panel), slot3["before"])
        self.assertEqual([line.replace(M.MAIN_ICON, "") for line in slot3["after"]], list(K.PANEL_ABILITY[3]))

    def test_native_legality_gates_are_empty(self):
        cas_keys = {K.CAS_CHANGE_SKILL, *K.CAS_ABILITY.values()}
        for index, row in enumerate(self.new):
            label = f"ability:{M.ABILITY_KEY}#{index}"
            self.assertEqual(L.client_legality_problems("ability", row), [], label)
            self.assertEqual(L.declared_block_field_problems("ability", row), [], label)
            self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, kind="ability"), [], label)
            self.assertEqual(L.ability_element_column_problems("ability", row, M.ELEMENT), [], label)
            self.assertEqual(KL.row_problems("ability", row, K.ELEMENT), {}, label)
            self.assertLessEqual(set(L.required_client_capabilities("ability", row)),
                                 CANDIDATE_CAPABILITIES, label)

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["ability"][M.ABILITY_KEY][1][28] = "mutated"
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
        data = deepcopy(self.live)
        data["ability"].update(deepcopy(self.out["ability"]))
        with self.assertRaises(ValueError):
            M.revise(reader(data))
        with self.assertRaises(ValueError):
            M.ability3_rows(self.new)

    def test_row_locator_is_content_based(self):
        mutations = (
            lambda r: r.__setitem__(slice(1, 3), [r[2], r[1]]),     # 行序对调
            lambda r: r[1].__setitem__(28, "6"),                    # 除自身合计
            lambda r: r[2].__setitem__(34, "7"),                    # 限次漂移
            lambda r: r[1].__setitem__(51, "25000"),                # 数值漂移
            lambda r: r[2].__setitem__(80, "x"),                    # 多出非空列
            lambda r: r[0].__setitem__(28, "7"),                    # #0 不再是自身
            lambda r: r[4].__setitem__(28, "0"),                    # 光属性角色施技行漂移
            lambda r: r[0].pop(),                                   # 列宽不对
            lambda r: r.pop(),                                      # 记录条数不对
        )
        for n, mutate in enumerate(mutations):
            rows = deepcopy(self.old)
            mutate(rows)
            with self.assertRaises(ValueError, msg=str(n)):
                M.ability3_rows(rows)
        text = deepcopy(self.live["cas"][M.CAS_SLOT3])
        text[0][0] = text[0][0].replace("自身发动技能时：自身技能伤害", "光属性角色发动技能时：自身技能伤害")
        with self.assertRaises(ValueError):
            M.check_panel(text)


class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_midautumn_kit_thorn（ABILITY_DONORS + design/thorn.json）重跑不能把 7+White 带回来。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def setUp(self):
        if not DESIGN_PATH.is_file():
            self.skipTest("midautumn design (gitignored work/) absent")
        self.design = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))

    def test_donor_changed_sets_cover_the_puller(self):
        specs = K.ABILITY_DONORS[M.ABILITY_KEY]
        for i in ROWS:
            self.assertEqual(tuple(specs[i]["changed"]), (0, 28, 29, 51, 52), i)
            self.assertIn(specs[i]["donor"], ("1510813#0", "1510813#1"))
        self.assertEqual(K.SELF_TRIGGER_ROWS, tuple((M.ABILITY_KEY, i) for i in M.SELF_PANEL_ROWS))

    def test_design_rows_equal_revise_output(self):
        records = self.design["plan"]["ability"]["keys"][M.ABILITY_KEY]["records"]
        rows = [K.design_row(r["cells"], KL.ABILITY_NCOLS, M.ABILITY_KEY) for r in records]
        self.assertEqual(rows, self.out["ability"][M.ABILITY_KEY])
        for i in ROWS:
            self.assertEqual(records[i]["cells"]["c28"], "0", i)
            self.assertNotIn("c29", records[i]["cells"], i)
            self.assertIn("1510813", records[i]["donor"], i)                # check_design_donor_text
            self.assertEqual(records[i]["desc_expected"], DESCRIBE[i], i)

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_build_equals_revise_output(self):
        ctx = _kit_ctx()
        rows_by_key, evidence = K.build_ability_rows(ctx, K.load_design(ctx.root))
        self.assertEqual(rows_by_key[M.ABILITY_KEY], self.out["ability"][M.ABILITY_KEY])
        self.assertEqual(K.check_self_trigger_rows(rows_by_key),
                         [f"{M.ABILITY_KEY}#{i}" for i in M.SELF_PANEL_ROWS])
        K.check_resonance_rows(rows_by_key)
        described = [ev["describe"] for ev in evidence if ev["label"].startswith(f"{M.ABILITY_KEY}#")]
        self.assertEqual(tuple(described), DESCRIBE)

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_rejects_a_design_that_reverts_to_the_party_trigger(self):
        """design 被旧脚本（design/thorn_rows.py）回写成 7+White ⇒ donor 逐格差对不上 changed，当场炸。"""
        ctx = _kit_ctx()
        design = K.load_design(ctx.root)
        cells = design["plan"]["ability"]["keys"][M.ABILITY_KEY]["records"][1]["cells"]
        cells["c28"], cells["c29"] = "7", "White"
        with self.assertRaises(K.KitError):
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
        self.assertEqual(design[M.MIRROR_TAG]["module"], "mod-tools/wf_balance_20260927b_thorn.py")
        three = next(entry for entry in panel["abilities"] if entry["index"] == 3)
        # 第三轮面板合并（wf_balance_20260927c_panels）同步镜像后，能力3 是合并稿；本批（面板不改）两种形态都接受。
        import wf_balance_20260927c_panels as P3
        lines = (P3.PANELS_BY_CAS[M.CAS_SLOT3]["after"] if P3.MODULE_TAG in panel else M.PANEL_LINES)
        self.assertEqual([line["text"] for line in three["lines"]],
                         [line.replace(M.MAIN_ICON, "") for line in lines])
        self.assertEqual(panel["notes"][-1], M.MIRROR_NOTE)
        rows = {r["key"]: r["text"] for r in design["plan"]["texts"]["custom_ability_string"]["rows"]}
        self.assertEqual(rows[M.CAS_SLOT3], "\n".join(lines))   # 本批面板不改

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
