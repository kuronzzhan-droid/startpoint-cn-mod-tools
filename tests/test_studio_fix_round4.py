"""2026-10-18 优化清单 C5 / D1 / D2 / D4：覆盖文案按槽行 c0 精确挂接、档位移动、新建覆盖键、作者规则。"""
from __future__ import annotations

import pytest

import wf_quest_lib as codec
from wf.balance.rows import TABLES, join_leaf, split_leaf
from wf.studio.drafts import DraftError
from wf.studio.text_panel import MAIN_ICON, override_slots
from wf.text.model import CUSTOM

from test_m1_balance import valid_row
from test_studio_ability import full, skill_row
from test_studio_ability_text import compile_text, setup


def field(panel, location):
    return next(f for f in panel["fields"] if f["location"] == location)


def house(field_view):
    return {h["id"]: h for h in field_view["house"]}


# -- C5 ---------------------------------------------------------------------------

def test_override_slot_is_exact_and_unmatched_keys_are_unattached(tmp_path):
    ed, _ = setup(tmp_path)
    ed.source.raw[CUSTOM] = codec.build_node({"desc_override_first": "自身攻击力提升",
                                              "desc_override_hero_extra": "无槽"})
    panel = ed.text_panel("139985")
    assert field(panel, "desc_override.desc_override_first")["slot"] == "能力 1"
    slots = {s["label"]: s for s in panel["slots"]}
    assert slots["能力 1"]["overrideKeys"] == ["desc_override_first", "desc_override_second"]
    assert slots["能力 1"]["existing"] == ["desc_override_first"]
    assert slots["队长技"]["overrideKeys"] == ["desc_override_hero"] and slots["队长技"]["existing"] == []
    lint = ed.text_panel("139985", text={"desc_override": {"desc_override_hero_extra": {"old": "无槽", "new": "x"}}},
                         light=True)
    assert field(lint, "desc_override.desc_override_hero_extra")["slot"] == "未挂接"


def test_real_view_overrides_of_139985_all_attach_exactly():
    try:
        from wf.studio.source import build_source
        source = build_source()
    except (FileNotFoundError, OSError, KeyError) as exc:
        pytest.skip(f"real layered view unavailable: {exc}")
    rows = source.table("character").get("139985")
    if not rows:
        pytest.skip("139985 not in view")
    raw = lambda logical: codec.parse_node(source.raw(logical))  # noqa: E731
    character = rows[0]
    custom = raw("master/string/custom_ability_string.orderedmap")
    slots = override_slots(character, raw("master/ability/leader_ability.orderedmap"),
                           raw("master/ability/ability.orderedmap"), custom)
    keys = [k for k in custom if k.startswith("desc_override_" + character[0])]
    mapped = {k for s in slots for k in s["existing"]}
    assert keys and set(keys) == mapped
    assert [s["label"] for s in slots if s["main"] == "all"] == ["能力 3", "能力 4", "能力 6"]


# -- D2 ---------------------------------------------------------------------------

def test_new_override_key_for_a_slot_goes_through_wf_text(tmp_path):
    ed, server = setup(tmp_path)
    create = {"desc_override": {"desc_override_hero": {"old": None, "new": "队伍全体攻击力+10%"}}}
    lint = ed.text_panel("139985", text=create, light=True)
    new = field(lint, "desc_override.desc_override_hero")
    assert new["slot"] == "队长技" and new["created"] is True
    ed.apply("139985", {"text": create})
    result = compile_text(ed, server)
    assert codec.parse_node(result["client"][CUSTOM])["desc_override_hero"] == "队伍全体攻击力+10%"
    after = ed.text_panel("139985")
    assert field(after, "desc_override.desc_override_hero")["slot"] == "队长技"
    with pytest.raises(DraftError, match="old-value assertion"):  # it exists now: old must be its text
        ed.apply("139985", {"text": create})
    with pytest.raises(DraftError, match="不是本角色任何槽"):
        ed.apply("139985", {"text": {"desc_override": {"desc_override_nobody": {"old": None, "new": "x"}}}})


def test_new_override_on_a_shared_slot_needs_shared_ok(tmp_path):
    ed, _ = setup(tmp_path, shared=True)
    create = {"desc_override": {"desc_override_hero": {"old": None, "new": "队伍全体攻击力+10%"}}}
    with pytest.raises(DraftError, match="shared"):
        ed.apply("139985", {"text": create})
    ed.apply("139985", {"text": create, "shared_ok": True})


# -- D4 ---------------------------------------------------------------------------

def _main_slot(ed):
    rows = [valid_row("first", "false"), valid_row("second", "false")]
    ed.source.raw[TABLES["ability"]] = codec.build_node({"1001": join_leaf("\r\n", rows)})


@pytest.mark.parametrize("text,rule,ok", [
    ("自身攻击力+10%", "house.main-icon", False),                                  # main slot without icon
    (MAIN_ICON + "自身攻击力+10%\n" + MAIN_ICON + "自身技能伤害+10%", "house.main-icon", True),
    ("<icon id='main'> 自身攻击力+10%", "house.main-icon", False),                 # wrong spacing
    (MAIN_ICON + "Ⓜ自身攻击力+10%", "house.main-icon", False),                     # literal Ⓜ
    (MAIN_ICON + "自身攻击力+20%", "house.awaken-dual", True),
    (MAIN_ICON + "自身攻击力+10%（觉醒后 20%）", "house.awaken-dual", False),   # author: one value only
    (MAIN_ICON + "自身攻击力+10%(觉醒后20%)", "house.awaken-dual", False),
    (MAIN_ICON + "自身攻击力+10%／技能伤害+10%", "house.no-slash", False),
])
def test_author_rules_on_overrides(tmp_path, text, rule, ok):
    ed, _ = setup(tmp_path)
    _main_slot(ed)
    lint = ed.text_panel("139985", text={"desc_override": {"desc_override_first": {"old": "自身攻击力提升", "new": text}}},
                         light=True)
    view = field(lint, "desc_override.desc_override_first")
    assert view["main"] == "all"
    assert (house(view)[rule]["state"] == "满足") is ok
    assert view["problems"] >= sum(1 for h in view["house"] if h["state"] == "问题")
    assert (view["problems"] > 0) is (not ok or any(f["state"] == "问题" for f in view["findings"]))


def test_icon_on_a_slot_that_is_not_main_limited(tmp_path):
    ed, _ = setup(tmp_path)
    rows = [valid_row("first", "true"), valid_row("second", "true")]
    ed.source.raw[TABLES["ability"]] = codec.build_node({"1001": join_leaf("\r\n", rows)})
    lint = ed.text_panel("139985", text={"desc_override": {"desc_override_first": {
        "old": "自身攻击力提升", "new": MAIN_ICON + "自身攻击力+10%"}}}, light=True)
    assert house(field(lint, "desc_override.desc_override_first"))["house.main-icon"]["state"] == "问题"


# -- D1 ---------------------------------------------------------------------------

def test_tier_move_reports_tier_references(tmp_path):
    ed, server = setup(tmp_path)
    rows = [skill_row("斩击" + "+" * (i - 1)) for i in (1, 2, 3)]
    move = {"op": "move_row", "table": "action_skill", "key": "hero", "level": "1", "row": 0, "row_count": 3,
            "to_row": 2, "cells": full(rows[0], "move_row")}
    preview = ed.preview("139985", {"operations": [move]})
    assert any(c["rule"] == "ability.skill-tier-references" for c in preview["checks"])
    ed.apply("139985", {"operations": [move]})
    table = codec.parse_node(compile_text(ed, server)["client"][TABLES["action_skill"]])["hero"]
    assert [split_leaf(table[level], "action_skill")[0][0] for level in ("1", "2", "3")] == ["斩击+", "斩击++", "斩击"]
