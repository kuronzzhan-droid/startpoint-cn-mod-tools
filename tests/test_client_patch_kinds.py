# -*- coding: utf-8 -*-
"""「只有打了补丁的客户端才认识」的枚举值:注册表一处登记,其余各处必须与它一致。

2026-09-28(扩展词条框架 B1-0)起,补丁构造的唯一真源是 `mod-tools/wfx_registry.json`
的 `patch_content_kinds`:`wf_client_legality.CLIENT_PATCH_CONTENT_KINDS` 与
`wf_client_patch_scope.PATCH_PARSER_TABLES/PATCH_PARSER_CAPABILITIES` 都由它派生。
本文件的 EXPECTED 也从注册表生成(只有 enum_map 的 parseAt 字段表仍手写在 FIELDS),
另用 FROZEN_PATCH_KINDS 钉住「当前恰好这 4 个补丁构造」——加新构造必须有意识地改这里。
下面是 B1-0 之前「四处登记」的原始说明,判据不变:

V12 往两个内容块各塞了一个**非官方**枚举值:

    instant_content 724 AddFeverPointRatio  ← client-patch/kyubi-fever-ratio
    during_content  422 DashParameter       ← client-patch/dash-parameter
    during_content  423 GaugeGainRestriction ← client-patch/battle-rules
    during_content  424 DamageTypeConversion ← client-patch/battle-rules

官方 `AbilityValues.parseAt47` / `parseAt109` 的 else 分支是
`throw new ClientError(7050,"不存在的构造函数。")`,所以这些值在没打补丁的客户端上
= 打开角色详情页即崩。风险不在「能不能写」,而在「写了之后有没有人记得先换 APK」。

因此三处登记必须同时在场、且互相自洽:

  1. `ability_enum_map.json` 的 `enums`(枚举域)—— 决定合法性检查放不放行;
  2. 同一份 JSON 的 `cases`(字段表)—— 决定「声明即必填」通用律管哪几列,
     并且必须带 `requires_client_capability`;
  3. `wf_client_legality.CLIENT_PATCH_CONTENT_KINDS` —— 决定
     `required_client_capabilities()` 报出哪个 capability;
  4. `词条条件代码全表.md` 的对应小节 —— 人读的那一份。

登记须显式列举补丁 kind，不能把新增枚举误当成官方内容。

本文件末尾另有一组用例管 `custom_ability_string` 的 `desc_override_*` 行:那条门禁
与上面三条不同 —— **缺补丁不崩,只是不生效**(行是惰性的)。它要回答的是「这行要
在真机上显示出来,需要哪一版 APK」:V11 的守卫只认 `fox_oracle_autumn`,V14 泛化
成任意 `string_id`。
"""
from __future__ import annotations

from external_sources import client_patch_path, require_external_source

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_client_legality  # noqa: E402
import wf_client_patch_scope as scope  # noqa: E402
import wf_describe  # noqa: E402
import wfx_registry  # noqa: E402
from wf_client_legality import (  # noqa: E402
    CLIENT_PATCH_CONTENT_KINDS, CUSTOM_ABILITY_STRING_KIND,
    PANEL_OVERRIDE_KEY_PREFIX, PANEL_OVERRIDE_V1, PANEL_OVERRIDE_V1_STRING_ID_PREFIX,
    PANEL_OVERRIDE_V2, panel_override_capability, required_client_capabilities,
)

ROOT = Path(__file__).resolve().parents[1]
TABLE_MD = ROOT / "词条条件代码全表.md"

# enum_map 里各补丁构造声明的 parseAt 字段(注册表不存 parseAt 细节,这一份仍手写)。
FIELDS = {
    ("instant_content", "724"): {"strength": "parseAt51"},
    ("during_content", "422"): {"unique_condition_id": "parseAt118", "strength": "parseAt113"},
    ("during_content", "423"): {"target": "parseAt110", "unique_condition_id": "parseAt118"},
    ("during_content", "424"): {"target": "parseAt110", "unique_condition_id": "parseAt118"},
}
# 当前恰好这 4 个补丁构造;注册表多登记/少登记都必须让本文件变红。
FROZEN_PATCH_KINDS = {("instant_content", "724"), ("during_content", "422"),
                      ("during_content", "423"), ("during_content", "424")}
BLOCK_CLASS = {"instant_content": "InstantAbilityContentMasterValue",
               "during_content": "CommonAbilityContentMasterValue"}
EXPECTED: dict[str, dict[str, tuple]] = {}
for _entry in wfx_registry.patch_content_kinds():
    EXPECTED.setdefault(_entry["block"], {})[_entry["value"]] = (
        _entry["ctor"], _entry["capability"], BLOCK_CLASS[_entry["block"]],
        FIELDS[_entry["block"], _entry["value"]])
# 官方枚举的最后一个值(补丁值必须紧接其后,不能占用官方以后可能用的号)。
OFFICIAL_LAST = {"instant_content": 723, "during_content": 421}


def _row(kind: str, trigger_mode: str, block: str, value: str) -> list[str]:
    layout = wf_describe.layout(kind)
    row = [""] * int(layout["ncols"])
    blocks = {name: int(index) for name, index in layout["blocks"].items()}
    row[blocks["precondition1"] - 1] = trigger_mode
    row[blocks[block]] = value
    return row


class ClientPatchKindTests(unittest.TestCase):
    def setUp(self):
        self.enum_map = wf_describe.enum_map()

    def test_the_registry_lists_exactly_the_frozen_patch_kinds(self):
        self.assertEqual(FROZEN_PATCH_KINDS,
                         {(entry["block"], entry["value"]) for entry in wfx_registry.patch_content_kinds()})
        self.assertEqual(set(FIELDS), FROZEN_PATCH_KINDS)

    def test_legality_and_scope_tables_are_derived_from_the_registry(self):
        self.assertEqual(wfx_registry.client_patch_content_kinds(),
                         wf_client_legality.CLIENT_PATCH_CONTENT_KINDS)
        self.assertEqual(wfx_registry.patch_parser_tables(), scope.PATCH_PARSER_TABLES)
        self.assertEqual(wfx_registry.patch_parser_capabilities(), scope.PATCH_PARSER_CAPABILITIES)

    def test_registry_matches_the_enum_map_exactly(self):
        self.assertEqual(sorted(EXPECTED), sorted(CLIENT_PATCH_CONTENT_KINDS))
        for block, expected in EXPECTED.items():
            self.assertEqual(
                {value: capability for value, (_c, capability, _cls, _f) in expected.items()},
                CLIENT_PATCH_CONTENT_KINDS[block], block)
            for value, (ctor, capability, cls, fields) in expected.items():
                case = self.enum_map["cases"][block].get(value)
                self.assertIsNotNone(case, f"{block} {value} is missing from cases")
                self.assertEqual(ctor, case["ctor"])
                self.assertEqual(cls, case["cls"])
                self.assertEqual(fields, case["fields"])
                self.assertEqual(capability, case.get("requires_client_capability"))
                self.assertEqual(ctor, self.enum_map["enums"][cls][value])

    def test_no_official_kind_carries_a_capability_gate(self):
        """反向：只有显式登记的补丁 kind 才能带 requires_client_capability。"""
        gated = []
        for block, cases in self.enum_map["cases"].items():
            for value, case in cases.items():
                if case.get("requires_client_capability"):
                    gated.append((block, value, case["requires_client_capability"]))
        self.assertEqual(
            sorted((block, value, capability)
                   for block, entries in EXPECTED.items()
                   for value, (_c, capability, _cls, _f) in entries.items()),
            sorted(gated))

    def test_each_patch_kind_sits_right_after_the_official_range(self):
        for block, expected in EXPECTED.items():
            cls = next(iter(expected.values()))[2]
            values = sorted(int(v) for v in self.enum_map["enums"][cls])
            official = [v for v in values if str(v) not in expected]
            self.assertEqual(OFFICIAL_LAST[block], max(official), block)
            self.assertEqual(list(range(OFFICIAL_LAST[block]+1, OFFICIAL_LAST[block]+1+len(expected))),
                             sorted(map(int, expected)), block)

    def test_the_gate_reports_the_capability_for_the_parsed_block_only(self):
        # 瞬发行(mode 0)只读 instant_content
        row = _row("ability", "0", "instant_content", "724")
        self.assertEqual(["kyubi-fever-ratio-v1"], required_client_capabilities("ability", row))
        # 持续行(mode 1)只读 during_content
        row = _row("ability", "1", "during_content", "422")
        self.assertEqual(["dash-parameter-v1"], required_client_capabilities("ability", row))
        # 模式不匹配的残值不算数:持续行里的 c47=724 客户端根本不解析
        row = _row("ability", "1", "instant_content", "724")
        self.assertEqual([], required_client_capabilities("ability", row))
        row = _row("ability", "0", "during_content", "422")
        self.assertEqual([], required_client_capabilities("ability", row))
        # 开幕行(mode 2)两个块都不读
        for block, value in (("instant_content", "724"), ("during_content", "422")):
            self.assertEqual([], required_client_capabilities(
                "ability", _row("ability", "2", block, value)))

    def test_official_rows_need_no_capability(self):
        for block, value in (("instant_content", "213"), ("during_content", "421")):
            mode = "0" if block == "instant_content" else "1"
            self.assertEqual([], required_client_capabilities(
                "ability", _row("ability", mode, block, value)))

    def test_dash_parameter_is_accepted_only_by_the_ability_parser(self):
        """422 只由 dash-parameter 扩了 AbilityValues$/parseAt109(2026-09-28 补盲区)。

        B1-0 之前 422 没登记进 PATCH_PARSER_TABLES,patch_parser_supported 对任何表都放行,
        本用例的旧版甚至断言五张表都报 dash-parameter-v1——而队长表写 422 实机 C7050
        (记忆 wf-dash-parameter-leader-table-trap)。现在:ability 报 capability;其余四表
        不把 capability 当解药,且合法性门禁报解析器 C7050。
        """
        for kind in ("ability", "leader_ability", "ability_soul",
                     "equipment_enhancement_ability", "ex_ability"):
            with self.subTest(kind=kind):
                blocks = wf_describe.layout(kind)["blocks"]
                row = [""] * int(wf_describe.layout(kind)["ncols"])
                row[int(blocks["precondition1"]) - 1] = "1"
                row[int(blocks["during_content"])] = "422"
                problems = wf_client_legality.client_legality_problems(kind, row)
                parser_problem = [p for p in problems if "未被当前补丁扩展" in p and "422" in p]
                if kind == "ability":
                    self.assertEqual(["dash-parameter-v1"], required_client_capabilities(kind, row))
                    self.assertEqual([], parser_problem)
                else:
                    self.assertEqual([], required_client_capabilities(kind, row))
                    self.assertEqual(1, len(parser_problem), problems)
                    self.assertIn("C7050", parser_problem[0])

    def test_dash_parameter_negative_control_restores_the_old_blind_spot(self):
        """负对照:拿掉注册表派生的 422 登记,队长表 422 立刻不再被拦(证明拦截来自这一条)。"""
        from unittest import mock
        blocks = wf_describe.layout("leader_ability")["blocks"]
        row = [""] * int(wf_describe.layout("leader_ability")["ncols"])
        row[int(blocks["precondition1"]) - 1] = "1"
        row[int(blocks["during_content"])] = "422"
        self.assertFalse(scope.patch_parser_supported("leader_ability", "during_content", "422"))
        with mock.patch.dict(scope.PATCH_PARSER_TABLES):
            del scope.PATCH_PARSER_TABLES["during_content", "422"]
            self.assertTrue(scope.patch_parser_supported("leader_ability", "during_content", "422"))
            self.assertEqual(["dash-parameter-v1"],
                             required_client_capabilities("leader_ability", row))
            self.assertFalse(any("未被当前补丁扩展" in p for p in
                                 wf_client_legality.client_legality_problems("leader_ability", row)))
        self.assertFalse(scope.patch_parser_supported("leader_ability", "during_content", "422"))

    def test_dash_parameter_table_set_matches_the_patch_parser_targets(self):
        """422 的表范围以 client-patch/dash-parameter/patch.py 自己改的解析器为准。"""
        import ast
        patch = client_patch_path('dash-parameter/patch.py')
        syntax = ast.parse(require_external_source(patch).read_text(encoding="utf-8"))
        targets = next(ast.literal_eval(node.value) for node in syntax.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(name, ast.Name) and name.id == "TARGETS"
                               for name in node.targets))
        parsers = {name for name in targets if "Values$/parseAt" in name}
        self.assertEqual({"AbilityValues$/parseAt109"}, parsers)
        self.assertEqual(frozenset({"ability"}), scope.PATCH_PARSER_TABLES["during_content", "422"])

    def test_the_markdown_table_documents_all_patch_kinds(self):
        text = TABLE_MD.read_text(encoding="utf-8")
        self.assertIn("| 724 | AddFeverPointRatio |", text)
        self.assertIn("kyubi-fever-ratio-v1", text)
        self.assertIn("| 422 | DashParameter |", text)
        self.assertIn("dash-parameter-v1", text)
        self.assertIn("| 423 | GaugeGainRestriction |", text)
        self.assertIn("gauge-gain-rules-v1", text)
        self.assertIn("| 424 | DamageTypeConversion |", text)
        self.assertIn("damage-type-rules-v1", text)
        # 小节标题必须说清「官方 N 种 + 客户端补丁 1 种」,别让人以为是官方枚举
        self.assertIn("### 6.4 瞬发效果 instant_content(官方 724 种 + 客户端补丁 1 种)", text)
        self.assertIn("### 6.5 持续效果 during_content(官方 422 种 + 客户端补丁 3 种)", text)

    def test_the_dash_param_id_column_is_enforced_as_required(self):
        """422 借的是 unique_condition_id 列,「声明即必填」必须照样管得住它。"""
        from wf_client_legality import declared_block_field_problems
        blocks = {name: int(index) for name, index in
                  wf_describe.layout("ability")["blocks"].items()}
        row = _row("ability", "1", "during_content", "422")
        problems = declared_block_field_problems("ability", row)
        self.assertTrue(any("c118" in text for text in problems), problems)
        self.assertTrue(any("c113" in text for text in problems), problems)
        row[blocks["during_content"] + 9] = "0"        # param_id
        row[blocks["during_content"] + 4] = "-30000"   # strength SLv1
        row[blocks["during_content"] + 5] = "-30000"   # strength 满级
        self.assertEqual([], declared_block_field_problems("ability", row))


class PanelDescriptionOverrideGateTests(unittest.TestCase):
    """`custom_ability_string` 的 `desc_override_*` 行需要哪版面板覆盖补丁。

    与 724/422 不同,这里缺补丁**不会 C7050**:没打补丁的客户端根本不查这张键,
    行是惰性的,面板照旧走官方生成器。所以这组断言的意义是「别把已经发了数据、
    但真机上根本不生效的行当成已完成」—— ginovi 的 7 条覆盖行就是这么惰性了一轮。
    """

    def test_the_two_capability_names(self):
        self.assertEqual("desc_override_", PANEL_OVERRIDE_KEY_PREFIX)
        self.assertEqual("fox_oracle_autumn", PANEL_OVERRIDE_V1_STRING_ID_PREFIX)
        self.assertEqual("kyubi-panel-description-override-v1", PANEL_OVERRIDE_V1)
        self.assertEqual("panel-description-override-v2", PANEL_OVERRIDE_V2)
        self.assertEqual("custom_ability_string", CUSTOM_ABILITY_STRING_KIND)

    def test_fox_rows_still_report_v1(self):
        """V11 就能显示的行只要求 v1;V14 同时提供 v1/v2,所以两版都满足。"""
        for key in ("desc_override_fox_oracle_autumn",
                    "desc_override_fox_oracle_autumn_1",
                    "desc_override_fox_oracle_autumn_2",
                    "desc_override_fox_oracle_autumn_6"):
            self.assertEqual([PANEL_OVERRIDE_V1], required_client_capabilities(
                CUSTOM_ABILITY_STRING_KIND, [key, "文案"]), key)

    def test_every_other_override_row_needs_the_generalized_patch(self):
        """基诺维的 7 条(以及以后任何自制角色的)只有 V14 认。"""
        keys = ["desc_override_ginovi"] + [f"desc_override_ginovi_{n}" for n in range(1, 7)]
        self.assertEqual(7, len(keys))
        for key in keys + ["desc_override_gerald_1", "desc_override_seris_dragon_king",
                           "desc_override_null", "desc_override_"]:
            self.assertEqual([PANEL_OVERRIDE_V2], required_client_capabilities(
                CUSTOM_ABILITY_STRING_KIND, [key, "文案"]), key)

    def test_non_override_keys_need_nothing(self):
        """同一张表里的 629 描述键、PF 覆盖文案键不属于这条门禁。"""
        for key in ("ability_skill_fox_oracle_autumn_fever_pf",
                    "override_string_fox_oracle_autumn_dual_pf",
                    "override_string_ginovi_pf", "change_skill_ginovi",
                    "desc_overrid", "", "adesc_override_ginovi"):
            self.assertEqual([], required_client_capabilities(
                CUSTOM_ABILITY_STRING_KIND, [key, "文案"]), key)
        self.assertEqual([], required_client_capabilities(CUSTOM_ABILITY_STRING_KIND, []))

    def test_the_helper_and_the_gate_agree(self):
        for key in ("desc_override_fox_oracle_autumn_2", "desc_override_ginovi_3",
                    "override_string_ginovi_pf"):
            capability = panel_override_capability(key)
            self.assertEqual([capability] if capability else [],
                             required_client_capabilities(CUSTOM_ABILITY_STRING_KIND, [key]))

    def test_the_ability_gate_is_untouched_by_the_string_table_branch(self):
        """反向:词条行的判据不许因为多了这条分支而改变。"""
        row = _row("ability", "0", "instant_content", "724")
        self.assertEqual(["kyubi-fever-ratio-v1"], required_client_capabilities("ability", row))
        row = _row("ability", "0", "instant_content", "213")
        self.assertEqual([], required_client_capabilities("ability", row))


if __name__ == "__main__":
    unittest.main()
