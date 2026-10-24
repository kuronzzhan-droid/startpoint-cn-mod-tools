from __future__ import annotations

import sys
import unittest
from pathlib import Path


MOD_TOOLS = Path(__file__).resolve().parents[1]
pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality  # noqa: E402
import wf_describe  # noqa: E402


# instant_content 块内 multiply_trigger 的列偏移(=28),从逆向布局表里取,
# 免得测试把列号写死后跟着布局一起腐烂。
_MULTIPLY_TRIGGER_OFFSET = next(
    int(offset)
    for offset, field, _label in wf_describe.enum_map()["block_fields"]["instant_content"]
    if field == "multiply_trigger"
)


# 每个块字段的「入口列」填什么才算合法行 —— 取值逐字抄官方行
# (ability 键 84 记录0 / 1210015 记录0,CN store 1.4.559),不是随手编的:
# 客户端对这些列没有空串分支,留空即 C7050 或 Std.parseInt('')=NaN。
_FIELD_FILL = {
    "trigger_puller": "0",
    "threshold": "100000",
    "threshold2": "100000",
    "start_threshold": "100000",
    "trigger_limit": "(None)",
    "cooltime": "0",
    "unique_condition_id": "0",
    "multiball_group_id": "0",
    "target": "0",
    "strength": "10000",
    "strength2": "10000",
    "frame": "90000000",
    "number": "100000",
    "max_accumulation": "(None)",
    "flip_limit": "(None)",
    "power_flip_limit": "(None)",
    "end_power_flip_limit": "(None)",
    "end_power_flip_accepted_levels": "(None)",
    "cancelable": "0",
    "time": "0",
    "element": "0",
    "initial_multiply": "1",
    "multiply_trigger": "0",
    "by_each_trigger_puller": "false",
}

_BLOCK_TO_FIELD_TABLE = {
    "precondition1": "precondition",
    "precondition2": "precondition",
    "precondition3": "precondition",
    "instant_trigger": "instant_trigger",
    "during_accumulation_trigger": "during_accumulation_trigger",
    "during_trigger": "during_trigger",
    "instant_content": "instant_content",
    "during_content": "during_content",
}


def _entry_offset(block: str, field: str) -> int:
    """块内某字段的入口列偏移(复合字段取最小偏移的那一列)。

    测试自己算一遍,不调用被测模块的 helper —— 否则偏移算错时两边一起错。
    """
    offsets = [
        int(offset)
        for offset, name, _label in wf_describe.enum_map()["block_fields"][
            _BLOCK_TO_FIELD_TABLE[block]
        ]
        if name == field or name.startswith(field + ".")
    ]
    if not offsets:
        raise KeyError(f"{block}.{field}")
    return min(offsets)


def _fill_block_fields(kind: str, row: list[str]) -> None:
    """把七个块的入口列全部填成合法值,让 fixture 行本身不违反「声明即必填」。"""
    blocks = {
        name: int(index)
        for name, index in wf_describe.layout(kind)["blocks"].items()
    }
    for block in _BLOCK_TO_FIELD_TABLE:
        base = blocks[block]
        for field, value in _FIELD_FILL.items():
            try:
                offset = _entry_offset(block, field)
            except KeyError:
                continue
            row[base + offset] = value


def _base_row(kind: str, trigger_mode: str) -> list[str]:
    layout = wf_describe.layout(kind)
    blocks = {name: int(index) for name, index in layout["blocks"].items()}
    row = [""] * int(layout["ncols"])
    _fill_block_fields(kind, row)
    row[blocks["precondition1"] - 1] = trigger_mode
    for name in ("precondition1", "precondition2", "precondition3"):
        row[blocks[name]] = "0"
    if trigger_mode == "0":
        row[blocks["instant_trigger"]] = "0"
        row[blocks["instant_precontent"]] = "(None)"
        row[blocks["instant_delay"]] = "0"
        row[blocks["instant_content"]] = "0"
        row[blocks["instant_content"] + _MULTIPLY_TRIGGER_OFFSET] = "0"
    elif trigger_mode == "1":
        row[blocks["during_accumulation_trigger"]] = "(None)"
        row[blocks["during_trigger"]] = "0"
        row[blocks["during_trigger"] + 1] = "0"
        row[blocks["even_if_owner_dead"]] = "false"
        row[blocks["during_content"]] = "0"
    else:
        row[blocks["opening"]] = "0"
    return row


class ClientLegalityTests(unittest.TestCase):
    def test_constructor_kind_columns_require_declared_enum_members(self) -> None:
        cases = (
            ("0", "precondition1", "AbilityPreconditionMasterValue", "precondition1.kind"),
            ("0", "precondition2", "AbilityPreconditionMasterValue", "precondition2.kind"),
            ("0", "precondition3", "AbilityPreconditionMasterValue", "precondition3.kind"),
            ("0", "instant_trigger", "InstantAbilityTriggerMasterValue", "瞬发触发kind"),
            (
                "0", "instant_precontent", "InstantAbilityPrecontentMasterValue",
                "instant_precontent",
            ),
            (
                "1", "during_accumulation_trigger",
                "InstantAbilityTriggerMasterValue", "累积触发",
            ),
            ("1", "during_trigger", "DuringAbilityTriggerMasterValue", "持续触发kind"),
            ("2", "opening", "OpeningAbilityMasterValue", "开幕kind"),
        )
        blocks = {
            name: int(index)
            for name, index in wf_describe.layout("ability")["blocks"].items()
        }
        for mode, block, enum_name, label in cases:
            with self.subTest(block=block):
                row = _base_row("ability", mode)
                if mode == "0":
                    row[72] = "false"
                row[blocks[block]] = "9999"

                problems = wf_client_legality.client_legality_problems(
                    "ability", row,
                )

                self.assertIn(
                    f"c{blocks[block]} {label}='9999' 不属于 {enum_name} 枚举域",
                    problems,
                )

    def test_declared_enum_members_remain_legal_across_trigger_modes(self) -> None:
        for mode in ("0", "1", "2"):
            with self.subTest(mode=mode):
                row = _base_row("ability", mode)
                if mode == "0":
                    row[72] = "false"

                self.assertEqual(
                    wf_client_legality.client_legality_problems("ability", row),
                    [],
                )

        numeric_accumulation = _base_row("ability", "1")
        accumulation_col = int(
            wf_describe.layout("ability")["blocks"]["during_accumulation_trigger"]
        )
        numeric_accumulation[accumulation_col] = "0"
        self.assertEqual(
            wf_client_legality.client_legality_problems(
                "ability", numeric_accumulation,
            ),
            [],
        )

    def test_during_content_rejects_instant_only_constructor(self) -> None:
        """Catches numeric kind 723 reaching parseAt109 where no constructor exists."""
        row = _base_row("ability", "1")
        row[109] = "723"

        problems = wf_client_legality.client_legality_problems("ability", row)

        self.assertIn(
            "c109 持续效果kind='723' 不属于 CommonAbilityContentMasterValue 枚举域",
            problems,
        )

    def test_instant_content_rejects_unknown_numeric_constructor(self) -> None:
        """Catches an all-digit value bypassing the client constructor domain gate."""
        row = _base_row("ability", "0")
        row[47] = "9999"

        problems = wf_client_legality.client_legality_problems("ability", row)

        self.assertIn(
            "c47 瞬发效果kind='9999' 不属于 InstantAbilityContentMasterValue 枚举域",
            problems,
        )

    def test_instant_condition_requires_by_each_trigger_puller_boolean(self) -> None:
        """Catches ConditionAttackPoint reaching parseAt72 with an empty string."""
        row = _base_row("ability", "0")
        row[47] = "0"
        row[72] = ""

        problems = wf_client_legality.client_legality_problems("ability", row)

        self.assertIn(
            "c72 by_each_trigger_puller='' 须为 true/false(否则C7101)",
            problems,
        )

    def test_boolean_requirement_uses_each_table_layout(self) -> None:
        """Catches leader rows being checked at ability c72 instead of leader c70."""
        row = _base_row("leader_ability", "0")
        blocks = wf_describe.layout("leader_ability")["blocks"]
        row[int(blocks["instant_content"])] = "486"
        row[70] = ""

        problems = wf_client_legality.client_legality_problems("leader_ability", row)

        self.assertIn(
            "c70 by_each_trigger_puller='' 须为 true/false(否则C7101)",
            problems,
        )

    def test_required_boolean_accepts_false(self) -> None:
        """Catches a gate that rejects the canonical false sentinel while hardening C7101."""
        row = _base_row("ability", "0")
        row[47] = "0"
        row[72] = "false"

        self.assertEqual(
            wf_client_legality.client_legality_problems("ability", row),
            [],
        )

    def test_during_trigger_requires_a_declared_puller_when_constructor_reads_it(self) -> None:
        """Catches kind 134 reaching parseAt98 with an empty cell (device C7050)."""
        for kind in ("ability", "leader_ability"):
            with self.subTest(kind=kind):
                row = _base_row(kind, "1")
                blocks = {
                    name: int(index)
                    for name, index in wf_describe.layout(kind)["blocks"].items()
                }
                row[blocks["during_trigger"]] = "134"
                puller_col = blocks["during_trigger"] + 1
                row[puller_col] = ""

                problems = wf_client_legality.client_legality_problems(kind, row)

                self.assertIn(
                    f"c{puller_col} during_trigger.trigger_puller='' "
                    "不属于 DuringAbilityTriggerPullerMasterValue 枚举域",
                    problems,
                )

                row[puller_col] = "0"
                self.assertEqual(
                    wf_client_legality.client_legality_problems(kind, row),
                    [],
                )

        count_multiball = _base_row("ability", "1")
        blocks = {
            name: int(index)
            for name, index in wf_describe.layout("ability")["blocks"].items()
        }
        count_multiball[blocks["during_trigger"]] = "208"
        count_multiball[blocks["during_trigger"] + 1] = ""
        self.assertEqual(
            wf_client_legality.client_legality_problems(
                "ability", count_multiball,
            ),
            [],
        )


    def test_instant_content_requires_multiply_trigger(self) -> None:
        """Catches white tiger ability 1699941 kind 461 reaching parseAt75 with ''."""
        for kind, content_kind in (("ability", "461"), ("leader_ability", "461")):
            with self.subTest(kind=kind):
                blocks = {
                    name: int(index)
                    for name, index in wf_describe.layout(kind)["blocks"].items()
                }
                row = _base_row(kind, "0")
                row[blocks["instant_content"]] = content_kind
                mt_col = blocks["instant_content"] + _MULTIPLY_TRIGGER_OFFSET
                row[mt_col] = ""

                problems = wf_client_legality.client_legality_problems(kind, row)

                self.assertIn(
                    f"c{mt_col} multiply_trigger='' 须为 '(None)' 或 "
                    "InstantAbilityMultiplyTriggerMasterValue 枚举域(0/1/2/3)"
                    f";空串=parseAt{mt_col} C7050",
                    problems,
                )

    def test_multiply_trigger_accepts_every_runtime_branch(self) -> None:
        """Catches a gate that only whitelists None and rejects PowerFlip/SkillInvoke/Fever."""
        blocks = {
            name: int(index)
            for name, index in wf_describe.layout("ability")["blocks"].items()
        }
        mt_col = blocks["instant_content"] + _MULTIPLY_TRIGGER_OFFSET
        for value in ("(None)", "0", "1", "2", "3"):
            with self.subTest(value=value):
                row = _base_row("ability", "0")
                row[blocks["instant_content"]] = "461"
                row[mt_col] = value

                self.assertEqual(
                    wf_client_legality.client_legality_problems("ability", row), [])

    def test_multiply_trigger_rejects_an_undefined_constructor(self) -> None:
        """Catches a numeric value outside the four constructors parseAt75 knows."""
        blocks = {
            name: int(index)
            for name, index in wf_describe.layout("ability")["blocks"].items()
        }
        mt_col = blocks["instant_content"] + _MULTIPLY_TRIGGER_OFFSET
        row = _base_row("ability", "0")
        row[blocks["instant_content"]] = "461"
        row[mt_col] = "4"

        problems = wf_client_legality.client_legality_problems("ability", row)

        self.assertIn(
            f"c{mt_col} multiply_trigger='4' 须为 '(None)' 或 "
            "InstantAbilityMultiplyTriggerMasterValue 枚举域(0/1/2/3)"
            f";空串=parseAt{mt_col} C7050",
            problems,
        )

    def test_multiply_trigger_is_ignored_where_the_constructor_never_reads_it(self) -> None:
        """Catches a blanket rule: kind 100 has no multiply_trigger field, empty is legal."""
        blocks = {
            name: int(index)
            for name, index in wf_describe.layout("ability")["blocks"].items()
        }
        cases = wf_describe.enum_map()["cases"]["instant_content"]
        self.assertNotIn("multiply_trigger", cases["100"]["fields"])
        row = _base_row("ability", "0")
        row[blocks["instant_content"]] = "100"
        row[blocks["instant_content"] + _MULTIPLY_TRIGGER_OFFSET] = ""

        self.assertEqual(
            wf_client_legality.client_legality_problems("ability", row), [])

    def test_multiply_trigger_column_follows_each_table_layout(self) -> None:
        """Catches the ability column (75) being hardcoded for ability_soul (72)."""
        blocks = {
            name: int(index)
            for name, index in wf_describe.layout("ability_soul")["blocks"].items()
        }
        mt_col = blocks["instant_content"] + _MULTIPLY_TRIGGER_OFFSET
        self.assertEqual(mt_col, 72)
        row = _base_row("ability_soul", "0")
        row[blocks["instant_content"]] = "461"
        row[mt_col] = ""

        problems = wf_client_legality.client_legality_problems("ability_soul", row)

        self.assertTrue(
            any(problem.startswith("c72 multiply_trigger=") for problem in problems),
            problems,
        )


class DeclaredBlockFieldTests(unittest.TestCase):
    """「声明即必填」通用律。2026-08-28 第二轮实锤:面板重做在三个 boss 角色的
    ability 表里留下 31 行 c28(instant_trigger.trigger_puller)空串 —— kind
    20/23/189 都会走 AbilityValues.parseAt28,该函数只认 "0".."9",落 else 就
    `throw new ClientError(7050)`,打开「查看角色」即崩;而当时的门禁一条都没拦住。
    同批还有 47 行 c34/leader c32(trigger_limit)空串 → Some(Std.parseInt(''))=NaN。"""

    def test_entry_columns_match_the_reverse_engineered_layout(self) -> None:
        """Catches a broken offset derivation by pinning the columns we crashed on."""
        ability = {
            name: int(index)
            for name, index in wf_describe.layout("ability")["blocks"].items()
        }
        leader = {
            name: int(index)
            for name, index in wf_describe.layout("leader_ability")["blocks"].items()
        }
        self.assertEqual(ability["precondition1"] + _entry_offset(
            "precondition1", "trigger_puller"), 7)
        self.assertEqual(ability["instant_trigger"] + _entry_offset(
            "instant_trigger", "trigger_puller"), 28)
        self.assertEqual(ability["instant_trigger"] + _entry_offset(
            "instant_trigger", "trigger_limit"), 34)
        self.assertEqual(ability["instant_content"] + _entry_offset(
            "instant_content", "target"), 48)
        self.assertEqual(ability["instant_content"] + _entry_offset(
            "instant_content", "multiply_trigger"), 75)
        self.assertEqual(ability["during_content"] + _entry_offset(
            "during_content", "target"), 110)
        self.assertEqual(leader["instant_trigger"] + _entry_offset(
            "instant_trigger", "trigger_puller"), 26)
        self.assertEqual(leader["instant_trigger"] + _entry_offset(
            "instant_trigger", "trigger_limit"), 32)

    def test_instant_trigger_puller_is_required_for_declaring_kinds(self) -> None:
        """Catches the 31 rows that crashed 「查看角色」 on 1.4.559 (C7050)."""
        for table, trigger_kind in (
            ("ability", "23"),        # SkillInvoke     — 白虎 1699941#0 等 20 行
            ("ability", "20"),        # MemberDirectAttack — 1699941#5 等 5 行
            ("ability", "189"),       # InvokeGuts      — 1699946#3..6 等 6 行
            ("leader_ability", "23"),
        ):
            with self.subTest(table=table, trigger_kind=trigger_kind):
                blocks = {
                    name: int(index)
                    for name, index in wf_describe.layout(table)["blocks"].items()
                }
                base = blocks["instant_trigger"]
                puller_col = base + _entry_offset("instant_trigger", "trigger_puller")
                self.assertIn(
                    "trigger_puller",
                    wf_describe.enum_map()["cases"]["instant_trigger"][
                        trigger_kind]["fields"],
                )

                row = _base_row(table, "0")
                row[base] = trigger_kind
                row[puller_col] = ""

                problems = wf_client_legality.client_legality_problems(table, row)
                self.assertTrue(
                    any(p.startswith(f"c{puller_col} instant_trigger.trigger_puller 留空")
                        for p in problems),
                    problems,
                )

                row[puller_col] = "0"        # Myself:官方对这三个 kind 的主流写法
                self.assertEqual(
                    wf_client_legality.client_legality_problems(table, row), [])

    def test_instant_trigger_limit_is_required_for_declaring_kinds(self) -> None:
        """Catches the 47 rows left as '' where the client does Std.parseInt('')."""
        for table in ("ability", "leader_ability"):
            with self.subTest(table=table):
                blocks = {
                    name: int(index)
                    for name, index in wf_describe.layout(table)["blocks"].items()
                }
                base = blocks["instant_trigger"]
                limit_col = base + _entry_offset("instant_trigger", "trigger_limit")

                row = _base_row(table, "0")
                row[base] = "23"
                row[limit_col] = ""

                problems = wf_client_legality.client_legality_problems(table, row)
                self.assertTrue(
                    any(p.startswith(f"c{limit_col} instant_trigger.trigger_limit 留空")
                        for p in problems),
                    problems,
                )

                row[limit_col] = "(None)"    # 无次数上限
                self.assertEqual(
                    wf_client_legality.client_legality_problems(table, row), [])
                row[limit_col] = "3"         # 有限次数同样合法
                self.assertEqual(
                    wf_client_legality.client_legality_problems(table, row), [])

    def test_undeclared_field_may_stay_empty(self) -> None:
        """Catches a blanket 'no empty cells' rule: Initial(kind 0) reads no puller."""
        blocks = {
            name: int(index)
            for name, index in wf_describe.layout("ability")["blocks"].items()
        }
        base = blocks["instant_trigger"]
        self.assertEqual(
            wf_describe.enum_map()["cases"]["instant_trigger"]["0"]["fields"], {})
        row = _base_row("ability", "0")
        row[base] = "0"
        for offset in range(1, 12):
            row[base + offset] = ""

        self.assertEqual(
            wf_client_legality.client_legality_problems("ability", row), [])

    def test_subcolumns_of_a_composite_field_may_stay_empty(self) -> None:
        """Catches checking target.multiball_group_id: official leaves it empty 2868x."""
        blocks = {
            name: int(index)
            for name, index in wf_describe.layout("ability")["blocks"].items()
        }
        base = blocks["instant_content"]
        row = _base_row("ability", "0")
        row[base] = "0"
        for field in ("target.character_groups", "target.multiball_group_id",
                      "strength.first_max", "frame.first_max", "number.first_max"):
            offset = next(
                int(o) for o, name, _l in
                wf_describe.enum_map()["block_fields"]["instant_content"]
                if name == field
            )
            row[base + offset] = ""

        self.assertEqual(
            wf_client_legality.client_legality_problems("ability", row), [])

    def test_character_groups_empty_stays_legal(self) -> None:
        """Catches losing the `if(v == "")` exemption: parseAt29/36/66 accept ''."""
        blocks = {
            name: int(index)
            for name, index in wf_describe.layout("ability")["blocks"].items()
        }
        base = blocks["instant_trigger"]
        row = _base_row("ability", "0")
        row[base] = "146"         # 声明 character_groups 的触发 kind
        self.assertIn(
            "character_groups",
            wf_describe.enum_map()["cases"]["instant_trigger"]["146"]["fields"],
        )
        row[base + _entry_offset("instant_trigger", "character_groups")] = ""

        self.assertEqual(
            wf_client_legality.client_legality_problems("ability", row), [])

    def test_main_and_unison_slot_gates_stay_legal_with_empty_tail(self) -> None:
        """Catches over-generalising: precondition 202/203 declare no fields at all."""
        blocks = {
            name: int(index)
            for name, index in wf_describe.layout("ability")["blocks"].items()
        }
        cases = wf_describe.enum_map()["cases"]["precondition"]
        for gate in ("202", "203"):
            with self.subTest(gate=gate):
                self.assertEqual(cases[gate]["fields"], {})
                row = _base_row("ability", "0")
                base = blocks["precondition1"]
                row[base] = gate
                for offset in range(1, 7):
                    row[base + offset] = ""

                self.assertEqual(
                    wf_client_legality.client_legality_problems("ability", row), [])

    def test_precondition_puller_is_required_beyond_the_legacy_whitelist(self) -> None:
        """Catches the rule skipping precondition slots.

        PRECONDITION_KINDS_NEED_NEXT_COL only lists the 8 kinds that were caught the
        hard way; `cases` says 134 precondition kinds read parseAt7.  Kind 100
        (StunifyUp) is one of the 126 the whitelist never covered.
        """
        blocks = {
            name: int(index)
            for name, index in wf_describe.layout("ability")["blocks"].items()
        }
        cases = wf_describe.enum_map()["cases"]["precondition"]
        self.assertIn("trigger_puller", cases["100"]["fields"])
        self.assertNotIn("100", wf_client_legality.PRECONDITION_KINDS_NEED_NEXT_COL)

        for slot in ("precondition1", "precondition2", "precondition3"):
            with self.subTest(slot=slot):
                base = blocks[slot]
                puller_col = base + _entry_offset(slot, "trigger_puller")
                row = _base_row("ability", "0")
                row[base] = "100"
                row[puller_col] = ""

                problems = wf_client_legality.client_legality_problems("ability", row)
                self.assertTrue(
                    any(p.startswith(f"c{puller_col} {slot}.trigger_puller 留空")
                        for p in problems),
                    problems,
                )

                row[puller_col] = "0"
                self.assertEqual(
                    wf_client_legality.client_legality_problems("ability", row), [])

    def test_rule_follows_each_table_layout(self) -> None:
        """Catches the ability column (28) being hardcoded for ability_soul (25)."""
        blocks = {
            name: int(index)
            for name, index in wf_describe.layout("ability_soul")["blocks"].items()
        }
        base = blocks["instant_trigger"]
        puller_col = base + _entry_offset("instant_trigger", "trigger_puller")
        self.assertEqual(puller_col, 25)
        row = _base_row("ability_soul", "0")
        row[base] = "23"
        row[puller_col] = ""

        problems = wf_client_legality.client_legality_problems("ability_soul", row)
        self.assertTrue(
            any(p.startswith("c25 instant_trigger.trigger_puller 留空")
                for p in problems),
            problems,
        )

    def test_during_blocks_are_covered_too(self) -> None:
        """Catches a rule wired only into the instant branch."""
        blocks = {
            name: int(index)
            for name, index in wf_describe.layout("ability")["blocks"].items()
        }
        row = _base_row("ability", "1")
        base = blocks["during_content"]
        row[base] = "0"
        target_col = base + _entry_offset("during_content", "target")
        row[target_col] = ""

        problems = wf_client_legality.client_legality_problems("ability", row)
        self.assertTrue(
            any(p.startswith(f"c{target_col} during_content.target 留空")
                for p in problems),
            problems,
        )

    def test_opening_rows_read_no_blocks(self) -> None:
        """Catches checking precondition/content blocks on trigger_mode 2 rows."""
        layout = wf_describe.layout("ability")
        row = [""] * int(layout["ncols"])
        blocks = {name: int(index) for name, index in layout["blocks"].items()}
        row[blocks["precondition1"] - 1] = "2"
        row[blocks["opening"]] = "0"

        self.assertEqual(
            wf_client_legality.client_legality_problems("ability", row), [])


class CharacterStanceTest(unittest.TestCase):
    def test_stance_outside_runtime_union_is_flagged(self) -> None:
        """Catches maou2's 'Special' (device C8601 on character detail, 2026-08-26)."""
        row = [""] * 40
        row[wf_client_legality.CHARACTER_STANCE_COL] = "Special"
        problems = wf_client_legality.character_stance_problems(row)
        self.assertEqual(len(problems), 1)
        self.assertIn("C8601", problems[0])

    def test_all_six_runtime_keys_are_legal(self) -> None:
        for stance in sorted(wf_client_legality.CHARACTER_STANCES):
            with self.subTest(stance=stance):
                row = [""] * 40
                row[wf_client_legality.CHARACTER_STANCE_COL] = stance
                self.assertEqual(
                    wf_client_legality.character_stance_problems(row), [])


class InvokeSkillStringTest(unittest.TestCase):
    def test_missing_string_key_is_flagged(self) -> None:
        """Catches maou2's dash row whose key was silently dropped by rebase claims."""
        row = [""] * 126
        row[47] = "629"
        row[70] = "ability_skill_ghost"
        probs = wf_client_legality.invoke_skill_string_problems(
            row, frozenset({"ability_skill_real"}))
        self.assertEqual(len(probs), 1)
        self.assertIn("C8601", probs[0])

    def test_present_key_passes(self) -> None:
        row = [""] * 126
        row[47] = "629"
        row[70] = "ability_skill_real"
        self.assertEqual(wf_client_legality.invoke_skill_string_problems(
            row, frozenset({"ability_skill_real"})), [])

    def test_non_629_rows_are_ignored(self) -> None:
        row = [""] * 126
        row[47] = "32"
        self.assertEqual(
            wf_client_legality.invoke_skill_string_problems(row, frozenset()), [])

    def test_leader_layout_reads_c45_and_c68(self) -> None:
        """队长表 629 行(基诺维冲刺 / 深渊之兽觉醒)的列位比词条表左移 2;
        写死 47/70 会让整条漏检(2026-09-08 复核工作流实锤)。"""
        row = [""] * 124
        row[45] = "629"
        row[68] = "ability_skill_abyss_beast_awaken"
        probs = wf_client_legality.invoke_skill_string_problems(
            row, frozenset({"something_else"}), kind="leader_ability")
        self.assertEqual(len(probs), 1)
        self.assertIn("c68", probs[0])
        self.assertEqual(wf_client_legality.invoke_skill_string_problems(
            row, frozenset({"ability_skill_abyss_beast_awaken"}), kind="leader_ability"), [])
        # 同一行按 ability 布局读不到 629 ⇒ 静默通过,正是旧实现的漏洞形状
        self.assertEqual(
            wf_client_legality.invoke_skill_string_problems(row, frozenset()), [])


def _element_column(kind: str, block: str) -> int:
    """element 列号:测试自己按布局表算一遍,不调用被测模块的 helper。"""
    base = int(wf_describe.layout(kind)["blocks"][block])
    offset = next(
        int(o)
        for o, field, _label in wf_describe.enum_map()["block_fields"][block]
        if field == "element"
    )
    return base + offset


def _override_element_row(element: str, *, kind: str = "ability") -> list[str]:
    """官方唯一先例 ability:1612011 记录[1](蕾薇)的逐列形状。

    c27=198 UnisonWithMain + c36 主位角色组 + c47=720 OverrideCharacterElement,
    其余列全空 —— 两个 kind 都只声明一个字段,客户端在这两个分支上不读别的列。
    """
    layout = wf_describe.layout(kind)
    blocks = {n: int(i) for n, i in layout["blocks"].items()}
    row = [""] * int(layout["ncols"])
    row[0] = "stella_copy_4anv_1"
    row[1] = "true"
    row[2] = "action_skill"
    row[3] = "0"
    row[blocks["precondition1"] - 1] = "0"
    for slot in ("precondition1", "precondition2", "precondition3"):
        row[blocks[slot]] = "0"
    row[blocks["instant_trigger"]] = "198"
    row[blocks["instant_trigger"] + 9] = "White"       # character_groups
    row[blocks["instant_precontent"]] = "(None)"
    row[blocks["instant_delay"]] = "0"
    row[blocks["instant_content"]] = "720"
    row[_element_column(kind, "instant_content")] = element
    return row


class AbilityElementColumnTests(unittest.TestCase):
    """element 列 = ElementTargetKind(1-based),0=全属性、1火…6暗。

    定案证据:ElementTargetKind_Impl_.toElementKind(0 抛异常 / 1..6 -> 0..5) +
    官方 1.4.0 全量 5012 行里唯一一条 720(1612011#1,暗角色写 5 = 光)。
    """

    def test_official_precedent_row_is_clean(self) -> None:
        """蕾薇(内部元素 5=暗)写 5,1-based 读作光 —— 官方合法写法不许判红。"""
        row = _override_element_row("5")
        self.assertEqual(
            wf_client_legality.client_legality_problems("ability", row), [])
        self.assertEqual(
            wf_client_legality.ability_element_column_problems(
                "ability", row, character_element=5), [])

    def test_all_elements_sentinel_is_rejected_for_override(self) -> None:
        """0 = ElementTargetKind.All;toElementKind(0) 直接 throw。"""
        probs = wf_client_legality.ability_element_column_problems(
            "ability", _override_element_row("0"))
        self.assertEqual(len(probs), 1)
        self.assertIn("INTERNAL ERROR", probs[0])

    def test_empty_element_is_reported_for_override(self) -> None:
        """空串 -> Std.parseInt('')=NaN -> int 0 -> 同一个 throw。"""
        probs = wf_client_legality.ability_element_column_problems(
            "ability", _override_element_row(""))
        self.assertEqual(len(probs), 1)
        self.assertIn("留空", probs[0])

    def test_out_of_range_is_flagged(self) -> None:
        for value in ("7", "9", "36"):
            with self.subTest(value=value):
                probs = wf_client_legality.ability_element_column_problems(
                    "ability", _override_element_row(value))
                self.assertEqual(len(probs), 1)
                self.assertIn("越界", probs[0])

    def test_zero_based_value_that_lands_on_the_owner_is_flagged(self) -> None:
        """把 0-based 内部元素直接填进来的典型症状:覆盖后还是自己 = 空转。

        真实案例:3610031#2 / 1610041#3(暗角色写 6)—— 两条都是我们自己
        1.4.60 发出去的,官方 1.4.0 全量里零条。
        """
        probs = wf_client_legality.ability_element_column_problems(
            "ability", _override_element_row("6"), character_element=5)
        self.assertEqual(len(probs), 1)
        self.assertIn("空转", probs[0])

    def test_no_owner_element_means_no_no_op_check(self) -> None:
        self.assertEqual(
            wf_client_legality.ability_element_column_problems(
                "ability", _override_element_row("6")), [])

    def test_white_tiger_wind_unison_row_is_clean(self) -> None:
        """白虎(内部元素 2=雷)写 4 = 风:既不越界也不空转。"""
        row = _override_element_row("4")
        row[wf_describe.layout("ability")["blocks"]["instant_trigger"] + 9] = "Green"
        self.assertEqual(
            wf_client_legality.client_legality_problems("ability", row), [])
        self.assertEqual(
            wf_client_legality.ability_element_column_problems(
                "ability", row, character_element=2), [])

    def test_resistance_family_may_use_the_all_sentinel(self) -> None:
        """630 ElementResistanceToAllConditionEnemy 族里 0 = 全属性,是合法键
        (MemberAbilityTotalizerImpl.getElementResistanceToConditionEnemies
         恒查 key 0),所以 0 只对 720 违法。"""
        row = _base_row("ability", "0")
        blocks = {n: int(i) for n, i in
                  wf_describe.layout("ability")["blocks"].items()}
        row[blocks["instant_content"]] = "630"
        row[_element_column("ability", "instant_content")] = "0"
        self.assertEqual(
            wf_client_legality.ability_element_column_problems(
                "ability", row, character_element=5), [])

    def test_rule_follows_each_table_layout(self) -> None:
        """列号必须跟着表布局走:ability c73 / leader_ability c71
        (对应 AbilityValues.parseAt73 / LeaderAbilityValues.parseAt71)。"""
        self.assertEqual(_element_column("ability", "instant_content"), 73)
        self.assertEqual(_element_column("leader_ability", "instant_content"), 71)
        row = _override_element_row("0", kind="leader_ability")
        probs = wf_client_legality.ability_element_column_problems(
            "leader_ability", row)
        self.assertEqual(len(probs), 1)
        self.assertIn("c71", probs[0])

    def test_kinds_without_an_element_field_are_ignored(self) -> None:
        row = _base_row("ability", "0")
        row[_element_column("ability", "instant_content")] = "9"
        self.assertEqual(
            wf_client_legality.ability_element_column_problems("ability", row), [])

    def test_during_content_element_is_range_checked(self) -> None:
        """持续侧 351 ElementResistanceToAllConditionEnemy 同吃这一列(c119)。"""
        row = _base_row("ability", "1")
        blocks = {n: int(i) for n, i in
                  wf_describe.layout("ability")["blocks"].items()}
        row[blocks["during_content"]] = "351"
        col = _element_column("ability", "during_content")
        row[col] = "9"
        probs = wf_client_legality.ability_element_column_problems("ability", row)
        self.assertEqual(len(probs), 1)
        self.assertIn("c{}".format(col), probs[0])
        row[col] = "0"          # 抗性族里 0 = 全属性,合法
        self.assertEqual(
            wf_client_legality.ability_element_column_problems("ability", row), [])

    def test_blocks_the_trigger_mode_never_parses_are_skipped(self) -> None:
        """从别的模式克隆行时留下的残值不算缺陷 —— 客户端在该模式下根本不读那一块。

        瞬发行只 parseAt47/73(instant_content),持续行只 parseAt109/119,
        开幕行两块都不读(TRIGGER_MODE_BLOCKS)。
        """
        blocks = {n: int(i) for n, i in
                  wf_describe.layout("ability")["blocks"].items()}
        during = _base_row("ability", "1")
        during[blocks["instant_content"]] = "720"
        during[_element_column("ability", "instant_content")] = "0"
        self.assertEqual(
            wf_client_legality.ability_element_column_problems("ability", during), [])

        opening = _base_row("ability", "2")
        opening[blocks["instant_content"]] = "720"
        opening[_element_column("ability", "instant_content")] = "0"
        self.assertEqual(
            wf_client_legality.ability_element_column_problems("ability", opening), [])


# 官方 pixelart.timeline 的九段布局(逐字取自 CN store 的 white_wolf_gerald /
# alk,1151 个官方时间轴的 kind 分布也与之一致:neutral/walk_*/ghost_neutral/
# kachidoki 是 loop,skill_ready/revive 是 once,into_coffin/ghost_raise 是 pass)。
_OFFICIAL_SEQUENCES = (
    ("neutral", "loop", 1, 2),
    ("walk_back", "loop", 3, 26),
    ("walk_front", "loop", 27, 50),
    ("skill_ready", "once", 51, 110),
    ("kachidoki", "loop", 111, 158),
    ("into_coffin", "pass", 159, 200),
    ("ghost_raise", "pass", 201, 225),
    ("ghost_neutral", "loop", 226, 386),
    ("revive", "once", 387, 428),
)


def _timeline(sequences=_OFFICIAL_SEQUENCES, *, points=None, circles=None):
    seqs = [{"name": n, "kind": k, "begin": b, "end": e}
            for n, k, b, e in sequences]
    if points is None:
        points = [{"path": "hp_gauge",
                   "frames": [{"begin": 1, "data": [{"x": 0, "y": -10}]}]}]
    if circles is None:
        body = wf_client_legality.PIXELART_BODY_SEQUENCES
        circles = [{"path": "unit_body", "frames": [
            {"begin": s["begin"] + 1,
             "data": [{"x": 0, "y": 0, "r": 8.3}] if s["name"] in body else []}
            for s in seqs]}]
    return {"sequences": seqs, "sounds": [], "points": points,
            "circles": circles, "rectangles": [], "matrices": []}


class PixelArtTimelineTests(unittest.TestCase):
    """Gates for character/<code>/pixelart/pixelart.timeline.amf3.deflate."""

    def test_official_shape_is_clean(self) -> None:
        self.assertEqual(
            wf_client_legality.pixelart_timeline_problems(_timeline()), [])

    def test_missing_required_sequence_is_flagged(self) -> None:
        seqs = tuple(s for s in _OFFICIAL_SEQUENCES if s[0] != "revive")
        probs = wf_client_legality.pixelart_timeline_problems(
            _timeline(seqs, circles=[]))
        self.assertTrue(any("revive" in p for p in probs))

    def test_last_sequence_without_terminator_is_flagged(self) -> None:
        """pass on the final sequence runs the playhead past totalFrames."""
        seqs = list(_OFFICIAL_SEQUENCES)
        seqs[-1] = ("revive", "pass", 387, 428)
        probs = wf_client_legality.pixelart_timeline_problems(_timeline(tuple(seqs)))
        self.assertTrue(any("INTERNAL ERROR" in p for p in probs))

    def test_kachidoki_once_is_flagged(self) -> None:
        seqs = [list(s) for s in _OFFICIAL_SEQUENCES]
        for s in seqs:
            if s[0] == "kachidoki":
                s[1] = "once"
        probs = wf_client_legality.pixelart_timeline_problems(
            _timeline(tuple(tuple(s) for s in seqs)))
        self.assertTrue(any("kachidoki" in p for p in probs))

    def test_gap_between_sequences_is_flagged(self) -> None:
        seqs = [list(s) for s in _OFFICIAL_SEQUENCES]
        seqs[1][2] = 5          # walk_back begins at 5 while neutral ends at 2
        probs = wf_client_legality.pixelart_timeline_problems(
            _timeline(tuple(tuple(s) for s in seqs), circles=[]))
        self.assertTrue(any("不连续" in p for p in probs))

    def test_duplicate_sequence_name_is_flagged(self) -> None:
        seqs = list(_OFFICIAL_SEQUENCES) + [("neutral", "once", 429, 430)]
        probs = wf_client_legality.pixelart_timeline_problems(
            _timeline(tuple(seqs), circles=[]))
        self.assertTrue(any("重复" in p for p in probs))

    def test_empty_markers_are_flagged(self) -> None:
        """The boss-trio packs shipped points/circles as bare []."""
        probs = wf_client_legality.pixelart_timeline_problems(
            _timeline(points=[], circles=[]))
        self.assertTrue(any("hp_gauge" in p for p in probs))
        self.assertTrue(any("unit_body" in p for p in probs))

    def test_unit_body_begin_offset_must_be_sequence_begin_plus_one(self) -> None:
        tl = _timeline()
        tl["circles"][0]["frames"][0]["begin"] = 1
        probs = wf_client_legality.pixelart_timeline_problems(tl)
        self.assertTrue(any("序列begin+1" in p for p in probs))

    def test_unit_body_must_be_empty_outside_the_three_ground_sequences(self) -> None:
        tl = _timeline()
        tl["circles"][0]["frames"][4]["data"] = [{"x": 0, "y": 0, "r": 8.3}]
        probs = wf_client_legality.pixelart_timeline_problems(tl)
        self.assertTrue(any("应为空数组" in p for p in probs))

    def test_enemy_side_sequences_keep_their_solid_circles(self) -> None:
        """敌我两用角色(white_tiger 等 15 个)的时间轴带敌方那 7 段。

        wince_ready / stun_ready / attack_* 官方**就是**实体圆
        (EnemyImpl.as:2296 getCircleByPath 真的读它们),不能按队友判据判空。
        """
        seqs = list(_OFFICIAL_SEQUENCES) + [
            ("wince_ready", "stop", 429, 433),
            ("stun_ready", "stop", 434, 438),
            ("attack_initial", "pass", 439, 450),
            ("attack_charge", "loop", 451, 474),
            ("attack_action", "pass", 475, 542),
            ("attack_fire", "once", 543, 566),
            ("dead", "stop", 567, 571),
        ]
        tl = _timeline(tuple(seqs))
        solid = [{"x": 0, "y": 0, "r": 8.3}]
        for frame, seq in zip(tl["circles"][0]["frames"], tl["sequences"]):
            if seq["name"].startswith("attack_") or seq["name"].endswith("_ready"):
                if seq["name"] != "skill_ready":
                    frame["data"] = solid
        self.assertEqual(wf_client_legality.pixelart_timeline_problems(tl), [])

    def test_empty_sequences_is_fatal(self) -> None:
        probs = wf_client_legality.pixelart_timeline_problems({"sequences": []})
        self.assertEqual(len(probs), 1)


class PixelArtVisibilityTests(unittest.TestCase):
    """Blank frames inside a continuously played sequence = the 1.4.560 flicker."""

    def _alpha(self, blank=()):
        return {f: (0 if f in blank else 500) for f in range(1, 429)}

    def test_all_visible_passes(self) -> None:
        self.assertEqual(
            wf_client_legality.pixelart_visibility_problems(
                _timeline(), self._alpha()), [])

    def test_blank_walk_frames_are_flagged(self) -> None:
        probs = wf_client_legality.pixelart_visibility_problems(
            _timeline(), self._alpha(blank={30, 31, 32}))
        self.assertEqual(len(probs), 1)
        self.assertIn("walk_front", probs[0])

    def test_blank_frames_in_death_sequences_are_ignored(self) -> None:
        """into_coffin/ghost_raise legitimately dissolve to nothing."""
        self.assertEqual(
            wf_client_legality.pixelart_visibility_problems(
                _timeline(), self._alpha(blank={199, 200, 201, 202})), [])

    def test_threshold_is_configurable(self) -> None:
        alpha = {f: 30 for f in range(1, 429)}
        self.assertEqual(
            wf_client_legality.pixelart_visibility_problems(
                _timeline(), alpha, min_alpha_pixels=10), [])
        self.assertTrue(
            wf_client_legality.pixelart_visibility_problems(
                _timeline(), alpha, min_alpha_pixels=40))

    def test_missing_frame_counts_as_blank(self) -> None:
        probs = wf_client_legality.pixelart_visibility_problems(_timeline(), {})
        self.assertTrue(probs)


def _attack(element: int):
    """Minimal CreateNormalAttack node (16 params, official arity)."""
    return ["Command", ["CreateNormalAttack", 12, element, [], [], 0,
                        [{"min": 2.0, "max": 2.0}], [{"min": 0.0, "max": 0.0}],
                        False, False, False, False, False,
                        [{"min": 0.0, "max": 0.0}], [{"min": 0.0, "max": 0.0}],
                        ["Fine"], True]]


class ActionDslElementTests(unittest.TestCase):
    """DSL element codes are 1-based; master/character c3 is 0-based."""

    def test_context_element_is_always_clean(self) -> None:
        tree = ["Block", [_attack(255)]]
        self.assertEqual(
            wf_client_legality.action_dsl_element_problems(tree, 2), [])

    def test_correct_one_based_code_passes(self) -> None:
        """A thunder character (c3=2) writes 3, exactly like the 24 official rows."""
        tree = ["Block", [_attack(3)]]
        self.assertEqual(
            wf_client_legality.action_dsl_element_problems(tree, 2), [])

    def test_off_by_one_signature_is_flagged(self) -> None:
        """White Tiger 1.4.560: thunder segments wrote 2 -> resolved to blue/water."""
        tree = ["Block", [_attack(2)]]
        probs = wf_client_legality.action_dsl_element_problems(tree, 2)
        self.assertEqual(len(probs), 1)
        self.assertIn("1-based", probs[0])

    def test_out_of_range_code_is_flagged(self) -> None:
        tree = ["Block", [_attack(0)]]
        self.assertTrue(
            wf_client_legality.action_dsl_element_problems(tree, None))
        tree = ["Block", [_attack(9)]]
        self.assertTrue(
            wf_client_legality.action_dsl_element_problems(tree, None))

    def _selector_tree(self, element: int):
        return ["Block", [
            ["Command", ["CreateCondition", 12, [
                ["ACToleranceOfElement", [{"min": 1200, "max": 1200}], element,
                 [{"min": -0.3, "max": -0.3}], [{"min": 0, "max": 0}]]]]],
            ["Command", ["FindAllSubjects", 400, 33, [element], [], [], [], [],
                         ["DoNothing"], ["Block", []]]],
        ]]

    def test_selector_slots_are_range_checked(self) -> None:
        """选择器槽位仍然吃 1..7/254/255 的范围校验。"""
        probs = wf_client_legality.action_dsl_element_problems(
            self._selector_tree(0), 2)
        self.assertEqual(len(probs), 2)
        self.assertTrue(any("ACToleranceOfElement" in p for p in probs))
        self.assertTrue(any("FindAllSubjects(33)" in p for p in probs))

    def test_selector_slots_may_equal_the_casters_own_element(self) -> None:
        """官方反例:walking_armor(暗)降光抗、touyakiren_ceo(暗)筛光同伴。

        两者的元素位都写 5,而角色内部元素也是 5 —— 差一签名在选择器槽位上
        会误报,所以它只作用于 CreateNormalAttack。
        """
        self.assertEqual(
            wf_client_legality.action_dsl_element_problems(
                self._selector_tree(5), 5), [])

    def test_off_by_one_signature_is_limited_to_the_damage_element_slot(self) -> None:
        self.assertEqual(
            wf_client_legality.DSL_ELEMENT_STRICT_CONSTRUCTS,
            frozenset({"CreateNormalAttack"}),
        )
        mixed = ["Block", [_attack(5)] + self._selector_tree(5)[1]]
        probs = wf_client_legality.action_dsl_element_problems(mixed, 5)
        self.assertEqual(len(probs), 1)
        self.assertIn("CreateNormalAttack", probs[0])

    def test_all_elements_sentinel_is_ignored(self) -> None:
        tree = ["Block", [
            ["Command", ["CreateCondition", 12, [
                ["ACToleranceOfElement", [{"min": 1, "max": 1}], 254,
                 [{"min": 0, "max": 0}], [{"min": 0, "max": 0}]]]]]]]
        self.assertEqual(
            wf_client_legality.action_dsl_element_problems(tree, 2), [])

    def test_find_all_subjects_other_kinds_are_ignored(self) -> None:
        """Search kind 49 (enemies) has no element filter list."""
        tree = ["Block", [["Command", ["FindAllSubjects", 64, 49, [], [], [], [],
                                       [], ["DoNothing"], ["Block", []]]]]]
        self.assertEqual(
            wf_client_legality.action_dsl_element_problems(tree, 2), [])

    def test_without_character_element_only_range_is_checked(self) -> None:
        tree = ["Block", [_attack(2)]]
        self.assertEqual(
            wf_client_legality.action_dsl_element_problems(tree), [])


class EquipmentDescriptionOverrideGateTests(unittest.TestCase):
    """`desc_override_equipment_*` = 装备详情覆盖(client-patch/equipment-description-override)。

    同样是惰性行:缺补丁只是显示生成文案、不崩。要守的是分类不串线 —— 这些键以
    `desc_override_` 开头,旧判据会把它们全归 V2,可 V14 的 AbilityLogic 探针永远不读它们;
    反过来,新分支也不许吃掉任何 V1/V2 键。
    """

    L = wf_client_legality
    PARADOX = ("desc_override_equipment_5920001",
               "desc_override_equipment_enhancement_5920001",
               "desc_override_equipment_enhancement_5920001_final")

    def test_names(self) -> None:
        self.assertEqual("desc_override_equipment_", self.L.EQUIPMENT_DESC_OVERRIDE_KEY_PREFIX)
        self.assertEqual("equipment-description-override-v1", self.L.EQUIPMENT_DESC_OVERRIDE)
        self.assertNotIn(self.L.EQUIPMENT_DESC_OVERRIDE, (self.L.PANEL_OVERRIDE_V1, self.L.PANEL_OVERRIDE_V2))
        self.assertTrue(self.L.EQUIPMENT_DESC_OVERRIDE_KEY_PREFIX.startswith(self.L.PANEL_OVERRIDE_KEY_PREFIX))

    def test_paradox_keys_need_the_equipment_patch(self) -> None:
        for key in self.PARADOX:
            self.assertEqual(self.L.EQUIPMENT_DESC_OVERRIDE, self.L.panel_override_capability(key), key)
            self.assertEqual([self.L.EQUIPMENT_DESC_OVERRIDE], self.L.required_client_capabilities(
                self.L.CUSTOM_ABILITY_STRING_KIND, [key, "文案"]), key)
            self.assertEqual([], self.L.equipment_desc_override_key_problems(key), key)

    def test_v1_and_v2_keys_are_unchanged(self) -> None:
        """负对照:新分支之前归 V1/V2 的键一个都不许改判;没有尾部下划线的近名仍是 V2。"""
        v1 = ("desc_override_fox_oracle_autumn", "desc_override_fox_oracle_autumn_1",
              "desc_override_fox_oracle_autumn_6")
        v2 = ("desc_override_ginovi", "desc_override_ginovi_3", "desc_override_seris_dragon_king",
              "desc_override_null", "desc_override_", "desc_override_equipment", "desc_override_equipmentx_5920001",
              "desc_override_equip_5920001", "desc_override_enhancement_5920001", "desc_override_Equipment_5920001")
        for key in v1:
            self.assertEqual([self.L.PANEL_OVERRIDE_V1], self.L.required_client_capabilities(
                self.L.CUSTOM_ABILITY_STRING_KIND, [key]), key)
        for key in v2:
            self.assertEqual([self.L.PANEL_OVERRIDE_V2], self.L.required_client_capabilities(
                self.L.CUSTOM_ABILITY_STRING_KIND, [key]), key)
        for key in v1 + v2:
            self.assertEqual([], self.L.equipment_desc_override_key_problems(key), key)
        for key in ("equipment_5920001", "adesc_override_equipment_5920001", "paradox_hits", ""):
            self.assertIsNone(self.L.panel_override_capability(key), key)
            self.assertEqual([], self.L.required_client_capabilities(self.L.CUSTOM_ABILITY_STRING_KIND, [key]), key)
            self.assertEqual([], self.L.equipment_desc_override_key_problems(key), key)

    def test_malformed_equipment_keys_are_problems(self) -> None:
        """补丁只拼 <id> / enhancement_<id> / enhancement_<id>_final;其余带前缀的键是读不到的死行。
        分类仍按前缀归装备覆盖(V14 不读它们),键形错误由 problems 报。"""
        bad = ("desc_override_equipment_", "desc_override_equipment_0", "desc_override_equipment_05920001",
               "desc_override_equipment_abc", "desc_override_equipment_5920001_final",
               "desc_override_equipment_enhancement_", "desc_override_equipment_enhancement_5920001_final_x",
               "desc_override_equipment_enhancement_5920001_", "desc_override_equipment_-5920001",
               "desc_override_equipment_5920001\n", " desc_override_equipment_5920001",
               "desc_override_equipment_５９２")                # 全角数字
        for key in bad:
            problems = self.L.equipment_desc_override_key_problems(key)
            self.assertEqual(1, len(problems), key)
            self.assertIn(repr(key), problems[0])
            self.assertEqual(self.L.EQUIPMENT_DESC_OVERRIDE, self.L.panel_override_capability(key), key)

    def test_ability_string_ids_may_not_enter_the_equipment_namespace(self) -> None:
        """V14 探测 desc_override_ + c0;c0 以 equipment_ 开头会与装备覆盖键相撞。"""
        for kind in ("ability", "leader_ability"):
            row = _base_row(kind, "0")
            row[0] = "fox_oracle_autumn_1"
            clean = wf_client_legality.client_legality_problems(kind, row)
            self.assertFalse(any("string_id" in p for p in clean), (kind, clean))
            row[0] = "equipment_5920001"
            dirty = wf_client_legality.client_legality_problems(kind, row)
            self.assertEqual([p for p in dirty if p not in clean],
                             [p for p in dirty if "c0 string_id='equipment_5920001'" in p], kind)
            self.assertEqual(1, len(dirty) - len(clean), (kind, dirty))
        # ability_soul 的 c0 是 slot,不查
        row = _base_row("ability_soul", "0")
        self.assertEqual(wf_client_legality.client_legality_problems("ability_soul", row),
                         wf_client_legality.client_legality_problems("ability_soul", ["0", *row[1:]]))

    def test_pack_verifier_knows_the_capability(self) -> None:
        import wf_midautumn_verify as V
        for key in self.PARADOX:
            self.assertIn(self.L.panel_override_capability(key), V.KNOWN_CAPABILITIES)


class EquipmentEnhancedLookGateTests(unittest.TestCase):
    """`enhanced_pixelart_tier2_*` / `enhanced_frame_override_*` = 装备强化外观(client-patch/equipment-enhanced-look)。

    行为型:缺补丁只是显示原图标与粉框。门禁要守的是键尾是图标路径、值是客户端真会接受的形状
    (第二图标档 "<正整数>,<路径>"),以及不串进面板覆盖的分类。
    """

    L = wf_client_legality
    TIER2 = "enhanced_pixelart_tier2_item/equipment/mod/paradox/paradox_lv120"
    FRAME = "enhanced_frame_override_item/equipment/mod/paradox/paradox_lv200"
    LV200 = "item/equipment/mod/paradox/paradox_lv200"
    BLUEGOLD = "item/equipment/mod/paradox/paradox_frame_bluegold"

    def test_names(self) -> None:
        self.assertEqual("equipment-enhanced-look-v1", self.L.EQUIPMENT_ENHANCED_LOOK)
        self.assertEqual(("enhanced_pixelart_tier2_", "enhanced_frame_override_"), self.L.ENHANCED_LOOK_KEY_PREFIXES)
        self.assertNotIn(self.L.EQUIPMENT_ENHANCED_LOOK, (self.L.PANEL_OVERRIDE_V1, self.L.PANEL_OVERRIDE_V2,
                                                          self.L.EQUIPMENT_DESC_OVERRIDE))

    def test_paradox_keys_need_the_enhanced_look_patch(self) -> None:
        for key, value in ((self.TIER2, "200," + self.LV200), (self.FRAME, self.BLUEGOLD)):
            self.assertEqual(self.L.EQUIPMENT_ENHANCED_LOOK, self.L.enhanced_look_capability(key), key)
            self.assertIsNone(self.L.panel_override_capability(key), key)
            self.assertEqual([self.L.EQUIPMENT_ENHANCED_LOOK], self.L.required_client_capabilities(
                self.L.CUSTOM_ABILITY_STRING_KIND, [key, value]), key)
            self.assertEqual([], self.L.enhanced_look_problems(key), key)
            self.assertEqual([], self.L.enhanced_look_problems(key, value), key)

    def test_other_keys_are_not_this_gates_business(self) -> None:
        for key in ("desc_override_equipment_5920001", "desc_override_ginovi", "paradox_hits",
                    "enhanced_pixelart_tier2", "Enhanced_frame_override_x", "xenhanced_frame_override_a", ""):
            self.assertIsNone(self.L.enhanced_look_capability(key), key)
            self.assertEqual([], self.L.enhanced_look_problems(key, "whatever,value\n"), key)
        # 面板覆盖键的分类不变
        self.assertEqual([self.L.EQUIPMENT_DESC_OVERRIDE], self.L.required_client_capabilities(
            self.L.CUSTOM_ABILITY_STRING_KIND, ["desc_override_equipment_5920001"]))

    def test_malformed_keys_are_problems(self) -> None:
        for key in ("enhanced_pixelart_tier2_", "enhanced_frame_override_", " enhanced_frame_override_item/a",
                    "enhanced_frame_override_item/a ", "enhanced_frame_override_item/a\n",
                    "enhanced_frame_override_/item/a", "enhanced_frame_override_item/a/",
                    "enhanced_frame_override_item//a", "enhanced_frame_override_item/a,b",
                    "enhanced_pixelart_tier2_item/a.png", "enhanced_pixelart_tier2_道具/a"):
            problems = self.L.enhanced_look_problems(key)
            self.assertEqual(1, len(problems), key)
            self.assertIn(repr(key), problems[0])
            self.assertEqual(self.L.EQUIPMENT_ENHANCED_LOOK, self.L.enhanced_look_capability(key), key)

    def test_tier2_values(self) -> None:
        good = ("200," + self.LV200, "1,a", "999999999,a/b_c-d")
        bad = ("", None, "200", self.LV200, "," + self.LV200, "200,", "abc," + self.LV200, "200.5," + self.LV200,
               "0200," + self.LV200, "0," + self.LV200, "-1," + self.LV200, "+200," + self.LV200,
               " 200," + self.LV200, "200 ," + self.LV200, "2e2," + self.LV200, "0xC8," + self.LV200,
               "1000000000," + self.LV200, "4294967496," + self.LV200, "200," + self.LV200 + ",x",
               "200;" + self.LV200, "200|" + self.LV200, "200," + self.LV200 + "\n", "２００," + self.LV200)
        for value in good:
            self.assertEqual([], self.L.enhanced_look_problems(self.TIER2, value), value)
        for value in bad:
            if value is None:
                continue                                   # None = 只查键
            problems = self.L.enhanced_look_problems(self.TIER2, value)
            self.assertEqual(1, len(problems), value)

    def test_frame_values(self) -> None:
        self.assertEqual([], self.L.enhanced_look_problems(self.FRAME, self.BLUEGOLD))
        for value in ("", "a\nb", "a,b", " a", "a/", "a.png", "200," + self.BLUEGOLD):
            self.assertEqual(1, len(self.L.enhanced_look_problems(self.FRAME, value)), value)

    def test_pack_verifier_knows_the_capability(self) -> None:
        import wf_midautumn_verify as V
        self.assertIn(self.L.EQUIPMENT_ENHANCED_LOOK, V.KNOWN_CAPABILITIES)


class ItemRarityFrameOverrideGateTests(unittest.TestCase):
    """`rarity_frame_override_*` = 物品品质底色覆盖(client-patch/item-rarity-frame-override)。

    独立 capability:补丁只在非强化态读这个键(强化态仍归 v1 的 enhanced_frame_override_),只装 v1 / 编成槽框的
    客户端不读它。门禁要守的是:它不被归到 v1 / 编成槽框、键尾是缩略图图标路径、值是一个路径,
    以及原有三个外观前缀的分类不变。缺补丁只显示原生稀有度底色 = cosmetic。
    """

    L = wf_client_legality
    STEEL = "rarity_frame_override_item/materials/mod/cursed/forbidden_star_steel"
    BLUEGOLD = "item/equipment/mod/paradox/paradox_frame_bluegold"

    def test_names(self) -> None:
        self.assertEqual("item-rarity-frame-override-v1", self.L.ITEM_RARITY_FRAME_OVERRIDE)
        self.assertEqual("rarity_frame_override_", self.L.ITEM_RARITY_FRAME_OVERRIDE_KEY_PREFIX)
        self.assertNotIn(self.L.ITEM_RARITY_FRAME_OVERRIDE_KEY_PREFIX, self.L.ENHANCED_LOOK_KEY_PREFIXES)
        self.assertEqual(self.L.ITEM_RARITY_FRAME_OVERRIDE, self.L.ENHANCED_LOOK_PREFIX_CAPABILITIES[
            self.L.ITEM_RARITY_FRAME_OVERRIDE_KEY_PREFIX])
        self.assertNotIn(self.L.ITEM_RARITY_FRAME_OVERRIDE, (
            self.L.EQUIPMENT_ENHANCED_LOOK, self.L.EQUIPMENT_ENHANCED_PARTY_FRAME, self.L.EQUIPMENT_DESC_OVERRIDE,
            self.L.PANEL_OVERRIDE_V1, self.L.PANEL_OVERRIDE_V2))

    def test_forbidden_star_steel_key_needs_its_own_patch(self) -> None:
        cas = self.L.CUSTOM_ABILITY_STRING_KIND
        self.assertEqual(self.L.ITEM_RARITY_FRAME_OVERRIDE, self.L.enhanced_look_capability(self.STEEL))
        self.assertIsNone(self.L.panel_override_capability(self.STEEL))
        self.assertEqual([self.L.ITEM_RARITY_FRAME_OVERRIDE],
                         self.L.required_client_capabilities(cas, [self.STEEL, self.BLUEGOLD]))
        self.assertEqual([], self.L.enhanced_look_problems(self.STEEL))
        self.assertEqual([], self.L.enhanced_look_problems(self.STEEL, self.BLUEGOLD))
        # 同一个图标路径的强化框键仍归 v1,编成槽框键仍归编成槽框:互不回退
        tail = self.STEEL[len(self.L.ITEM_RARITY_FRAME_OVERRIDE_KEY_PREFIX):]
        self.assertEqual([self.L.EQUIPMENT_ENHANCED_LOOK], self.L.required_client_capabilities(
            cas, [self.L.ENHANCED_FRAME_OVERRIDE_KEY_PREFIX + tail]))
        self.assertEqual([self.L.EQUIPMENT_ENHANCED_PARTY_FRAME], self.L.required_client_capabilities(
            cas, [self.L.ENHANCED_PARTY_FRAME_OVERRIDE_KEY_PREFIX + tail]))

    def test_near_names_are_not_rarity_keys(self) -> None:
        for key in ("rarity_frame_override", "Rarity_frame_override_x", "xrarity_frame_override_a",
                    "rarity_frame_x", "item_rarity_frame_override_a", ""):
            self.assertNotEqual(self.L.ITEM_RARITY_FRAME_OVERRIDE, self.L.enhanced_look_capability(key), key)

    def test_malformed_keys_are_problems(self) -> None:
        for key in ("rarity_frame_override_", " rarity_frame_override_item/a", "rarity_frame_override_item/a ",
                    "rarity_frame_override_/item/a", "rarity_frame_override_item/a/", "rarity_frame_override_item//a",
                    "rarity_frame_override_item/a,b", "rarity_frame_override_item/a.png", "rarity_frame_override_道具/a"):
            problems = self.L.enhanced_look_problems(key)
            self.assertEqual(1, len(problems), key)
            self.assertIn(repr(key), problems[0])
            self.assertEqual(self.L.ITEM_RARITY_FRAME_OVERRIDE, self.L.enhanced_look_capability(key), key)

    def test_values(self) -> None:
        for value in ("", "a\nb", "a,b", " a", "a/", "a.png", "200," + self.BLUEGOLD):
            self.assertEqual(1, len(self.L.enhanced_look_problems(self.STEEL, value)), value)

    def test_pack_verifier_knows_the_capability(self) -> None:
        """整包核验器认得这个 capability(声明它不会被当成伪造能力);外观族四个 capability 都在全集里。"""
        import wf_midautumn_verify as V
        self.assertIn(self.L.ITEM_RARITY_FRAME_OVERRIDE, V.KNOWN_CAPABILITIES)
        for capability in self.L.ENHANCED_LOOK_PREFIX_CAPABILITIES.values():
            self.assertIn(capability, V.KNOWN_CAPABILITIES)


class EquipmentEnhancedPartyFrameGateTests(unittest.TestCase):
    """`enhanced_party_frame_override_*` = 编成装备槽强化框(client-patch/equipment-enhanced-party-frame)。

    独立 capability:只装 v1(equipment-enhanced-look-v1)的客户端不读这个键,编成槽仍是粉框。门禁要守的是
    它不被归到 v1、键尾是图标路径、值是一个路径,以及 v1 两个前缀的分类不变。
    """

    L = wf_client_legality
    PARTY = "enhanced_party_frame_override_item/equipment/mod/paradox/paradox_lv200"
    PARTY_FRAME = "item/equipment/mod/paradox/paradox_party_frame_bluegold"

    def test_names(self) -> None:
        self.assertEqual("equipment-enhanced-party-frame-v1", self.L.EQUIPMENT_ENHANCED_PARTY_FRAME)
        self.assertEqual("enhanced_party_frame_override_", self.L.ENHANCED_PARTY_FRAME_OVERRIDE_KEY_PREFIX)
        self.assertNotIn(self.L.ENHANCED_PARTY_FRAME_OVERRIDE_KEY_PREFIX, self.L.ENHANCED_LOOK_KEY_PREFIXES)
        self.assertEqual({"enhanced_pixelart_tier2_": "equipment-enhanced-look-v1",
                          "enhanced_frame_override_": "equipment-enhanced-look-v1",
                          "enhanced_party_frame_override_": "equipment-enhanced-party-frame-v1",
                          "rarity_frame_override_": "item-rarity-frame-override-v1"},
                         self.L.ENHANCED_LOOK_PREFIX_CAPABILITIES)
        # 四个前缀互不为前缀:一个键至多归一个补丁
        prefixes = list(self.L.ENHANCED_LOOK_PREFIX_CAPABILITIES)
        for a in prefixes:
            for b in prefixes:
                self.assertTrue(a == b or not a.startswith(b), (a, b))

    def test_party_key_needs_its_own_patch_not_v1(self) -> None:
        self.assertEqual(self.L.EQUIPMENT_ENHANCED_PARTY_FRAME, self.L.enhanced_look_capability(self.PARTY))
        self.assertIsNone(self.L.panel_override_capability(self.PARTY))
        self.assertEqual([self.L.EQUIPMENT_ENHANCED_PARTY_FRAME], self.L.required_client_capabilities(
            self.L.CUSTOM_ABILITY_STRING_KIND, [self.PARTY, self.PARTY_FRAME]))
        self.assertNotIn(self.L.EQUIPMENT_ENHANCED_LOOK, self.L.required_client_capabilities(
            self.L.CUSTOM_ABILITY_STRING_KIND, [self.PARTY]))
        self.assertEqual([], self.L.enhanced_look_problems(self.PARTY))
        self.assertEqual([], self.L.enhanced_look_problems(self.PARTY, self.PARTY_FRAME))
        # v1 两键的分类不变
        for key in ("enhanced_frame_override_item/equipment/mod/paradox/paradox_lv200",
                    "enhanced_pixelart_tier2_item/equipment/mod/paradox/paradox_lv120"):
            self.assertEqual([self.L.EQUIPMENT_ENHANCED_LOOK], self.L.required_client_capabilities(
                self.L.CUSTOM_ABILITY_STRING_KIND, [key]), key)

    def test_near_names_are_not_party_keys(self) -> None:
        for key in ("enhanced_party_frame_override", "Enhanced_party_frame_override_x", "xenhanced_party_frame_override_a",
                    "enhanced_party_frame_x", ""):
            self.assertNotEqual(self.L.EQUIPMENT_ENHANCED_PARTY_FRAME, self.L.enhanced_look_capability(key), key)

    def test_malformed_keys_are_problems(self) -> None:
        for key in ("enhanced_party_frame_override_", " enhanced_party_frame_override_item/a",
                    "enhanced_party_frame_override_item/a ", "enhanced_party_frame_override_/item/a",
                    "enhanced_party_frame_override_item/a/", "enhanced_party_frame_override_item//a",
                    "enhanced_party_frame_override_item/a,b", "enhanced_party_frame_override_item/a.png",
                    "enhanced_party_frame_override_道具/a"):
            problems = self.L.enhanced_look_problems(key)
            self.assertEqual(1, len(problems), key)
            self.assertIn(repr(key), problems[0])
            self.assertEqual(self.L.EQUIPMENT_ENHANCED_PARTY_FRAME, self.L.enhanced_look_capability(key), key)

    def test_values(self) -> None:
        for value in ("", "a\nb", "a,b", " a", "a/", "a.png", "200," + self.PARTY_FRAME):
            self.assertEqual(1, len(self.L.enhanced_look_problems(self.PARTY, value)), value)

    def test_pack_verifier_knows_the_capability(self) -> None:
        import wf_midautumn_verify as V
        self.assertIn(self.L.EQUIPMENT_ENHANCED_PARTY_FRAME, V.KNOWN_CAPABILITIES)


class EquipmentBehaviourKeyGateTests(unittest.TestCase):
    """`awakening_material_*` = 觉醒专属素材(client-patch/equipment-awakening-material,semantic);
    `equipment_sort_pin_*` = 装备列表置顶(client-patch/equipment-sort-pin,cosmetic)。

    两个补丁都按 int 装备 ID 逐字拼键、按 String(int(s)) === s 且 > 0 认值;门禁要守的是:两个前缀各归自己的
    capability、不与面板覆盖 / 外观族前缀互相认领,键尾与值都是规范十进制正整数(门禁可以比客户端更严,不能更松)。
    """

    L = wf_client_legality
    AWAKEN = "awakening_material_5910101"
    PIN = "equipment_sort_pin_5920001"

    def test_names(self) -> None:
        self.assertEqual("equipment-awakening-material-v1", self.L.EQUIPMENT_AWAKENING_MATERIAL)
        self.assertEqual("equipment-sort-pin-v1", self.L.EQUIPMENT_SORT_PIN)
        self.assertEqual({"awakening_material_": "equipment-awakening-material-v1",
                          "equipment_sort_pin_": "equipment-sort-pin-v1"},
                         self.L.EQUIPMENT_KEY_PREFIX_CAPABILITIES)
        # 与面板覆盖、外观族所有前缀互不为前缀:一个键至多归一个补丁
        prefixes = [*self.L.EQUIPMENT_KEY_PREFIX_CAPABILITIES, *self.L.ENHANCED_LOOK_PREFIX_CAPABILITIES,
                    self.L.PANEL_OVERRIDE_KEY_PREFIX]
        for a in prefixes:
            for b in prefixes:
                self.assertTrue(a == b or not a.startswith(b), (a, b))

    def test_each_prefix_needs_its_own_patch(self) -> None:
        cas = self.L.CUSTOM_ABILITY_STRING_KIND
        self.assertEqual([self.L.EQUIPMENT_AWAKENING_MATERIAL],
                         self.L.required_client_capabilities(cas, [self.AWAKEN, "10000311"]))
        self.assertEqual([self.L.EQUIPMENT_SORT_PIN], self.L.required_client_capabilities(cas, [self.PIN, "1000"]))
        for key in (self.AWAKEN, self.PIN):
            self.assertIsNone(self.L.panel_override_capability(key))
            self.assertIsNone(self.L.enhanced_look_capability(key))
        self.assertEqual([], self.L.equipment_key_problems(self.AWAKEN, "10000311"))
        self.assertEqual([], self.L.equipment_key_problems(self.PIN, "1000"))
        self.assertEqual([], self.L.equipment_key_problems(self.PIN, "999999999"))
        # 其他键不归这里管
        self.assertEqual([], self.L.equipment_key_problems("enhanced_frame_override_item/a", "x"))
        self.assertIsNone(self.L.equipment_key_capability("desc_override_equipment_5910101"))

    def test_near_names_are_not_behaviour_keys(self) -> None:
        for key in ("awakening_material", "Awakening_material_1", "xawakening_material_1", "awakening_materials_1",
                    "equipment_sort_pin", "equipment_sort_pins_1", "Equipment_sort_pin_1", ""):
            self.assertIsNone(self.L.equipment_key_capability(key), key)
            self.assertEqual([], self.L.required_client_capabilities(self.L.CUSTOM_ABILITY_STRING_KIND, [key]), key)

    def test_malformed_keys_are_problems(self) -> None:
        for prefix in self.L.EQUIPMENT_KEY_PREFIX_CAPABILITIES:
            for tail in ("", "0", "05910101", "+5910101", "5910101 ", "-1", "5910101.0", "1e6", "0x10",
                         "12345678901", "abc", "5910101/x"):
                key = prefix + tail
                problems = self.L.equipment_key_problems(key)
                self.assertEqual(1, len(problems), key)
                self.assertIn(repr(key), problems[0])
                self.assertEqual(self.L.EQUIPMENT_KEY_PREFIX_CAPABILITIES[prefix],
                                 self.L.equipment_key_capability(key), key)

    def test_values_the_client_would_not_accept_are_problems(self) -> None:
        for key in (self.AWAKEN, self.PIN):
            for value in ("", "0", "-5", "+1", "01000", " 1000", "1000 ", "1.5", "2e3", "0x3e8", "1000,1",
                          "abc", "1000000000", "2147483648", "99999999999", "1000\n"):
                self.assertEqual(1, len(self.L.equipment_key_problems(key, value)), (key, value))

    def test_pack_verifier_knows_both_capabilities(self) -> None:
        import wf_midautumn_verify as V
        self.assertIn(self.L.EQUIPMENT_AWAKENING_MATERIAL, V.KNOWN_CAPABILITIES)
        self.assertIn(self.L.EQUIPMENT_SORT_PIN, V.KNOWN_CAPABILITIES)


if __name__ == "__main__":
    unittest.main()
