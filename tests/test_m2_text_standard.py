"""Policy counterexamples and honest coverage for every registered clause."""
import copy
import json

import pytest

from test_m1_text import edit_for, workspace  # noqa: F401
from wf.text import TextWorkspace, check_character
from wf.text.edit import prepare_edit
from wf.text.model import ACTION_SKILL, CUSTOM, RANK_TARGET, SERVER_TARGET, replace_cells
from wf.text.standard import check_entry, coverage, rule_catalog


@pytest.mark.parametrize("rule,bad,key,surface", [
    ("no-final-stop", "自身攻击力+10%。", "desc_override_hero_1", "desc_override"),
    ("prefix-order", "Fever模式中，水属性共鸣时，自身攻击力+10%", "hero", "desc_override"),
    ("resonance", "水属性共鸣中，自身攻击力+10%", "hero", "desc_override"),
    ("fever", "非Fever中，自身攻击力+10%", "hero", "desc_override"),
    ("battle-start", "战斗开始后，自身技能槽+10%", "hero", "desc_override"),
    ("count-prefix", "每隔3秒，自身获得1层「月牙」", "hero", "desc_override"),
    ("main-icon", "主位时，自身攻击力+10%", "hero", "desc_override"),
    ("leader-slot", "自身为队长时，自身攻击力+10%", "desc_override_hero_leader", "desc_override"),
    ("leader-relocation", "担任队长时，自身攻击力+10%", "desc_override_hero_1", "desc_override"),
    ("term-pf", "PF伤害+10%", "hero", "desc_override"),
    ("term-direct", "直击伤害+10%", "hero", "desc_override"),
    ("term-fever", "FEVER槽+10%", "hero", "desc_override"),
    ("term-pierce", "贯通中，自身攻击力+10%", "hero", "desc_override"),
    ("term-team", "全体队员攻击力+10%", "hero", "desc_override"),
    ("term-gauge", "技能槽上限+10%", "hero", "desc_override"),
    ("term-charge", "自身充能速度+10%", "hero", "desc_override"),
    ("term-pursuit", "追击伤害+10%（独立伤害乘区2）", "hero", "desc_override"),
    ("term-zone", "自身攻击力+10%（独立乘区）", "hero", "desc_override"),
    ("number-format", "自身攻击力＋10%", "hero", "desc_override"),
    ("limits", "自身攻击力+10%（最多10次）（最大+100%）", "hero", "desc_override"),
    ("timing", "自身攻击力+10%（CT:3秒）", "hero", "desc_override"),
    ("max-level", "觉醒后，自身攻击力+20%", "hero", "desc_override"),
    ("damage-zones", "全伤害+10%（独立伤害乘区9）", "hero", "desc_override"),
    ("named-state", "自身获得1层【月牙】", "hero", "desc_override"),
    ("invoke", "发动技能「月牙」", "desc_override_hero_1", "desc_override"),
    ("special-pf", "自身的强化弹射变为特殊强化弹射", "hero", "desc_override"),
    ("skill-enhance", "强化『月牙』：追加10倍技能伤害", "hero", "desc_override"),
    ("tautology", "生命值100%以下时，自身攻击力+10%", "hero", "desc_override"),
    ("internals", "kind 629发动技能", "hero", "desc_override"),
    ("repetition", "Fever模式中，Fever模式中，自身攻击力+10%", "hero", "desc_override"),
    ("skill-structure", "向前方攻击/赋予队伍贯穿＋浮游效果", "hero", "action_skill"),
    ("skill-branches", "[场上没有协力球时]召唤协力球", "hero", "action_skill"),
    ("skill-damage-numbers", "对敌人造成合计43倍火属性伤害", "hero", "action_skill"),
    ("skill-buff-numbers", "自身攻击力提升50%（持续10秒）", "hero", "action_skill"),
    ("skill-body", "强化『月牙』：范围扩大", "hero", "action_skill"),
    ("damage-conversion", "造成伤害（以直接攻击伤害计算）", "hero", "action_skill"),
    ("six-elements", "对全体敌人造成自身攻击力2倍的六属性能力伤害", "hero", "desc_override"),
    ("direct-base", "自身直接攻击倍率变为3倍", "hero", "desc_override"),
    ("direct-count", "自身直接攻击判定为3次", "hero", "desc_override"),
    ("multi-pf", "自身的强化弹射同时具备剑士型与射击型", "hero", "desc_override"),
    ("pf-lv4", "强化弹射LV4发动：范围扩大", "hero", "desc_override"),
    ("skill-form", "强化『月牙』：追加3次攻击", "hero", "desc_override"),
    ("fever-items", "Fever模式中，加速箭头变成道具", "hero", "desc_override"),
    ("enemy-hp", "造成真伤", "hero", "desc_override"),
    ("charge-cap", "自身技能充能速度上限变为1000%", "hero", "desc_override"),
])
def test_each_implemented_rule_has_a_counterexample(rule, bad, key, surface):
    results = check_entry(key, bad, surface=surface)
    assert any(f["rule"] == "text.standard." + rule and f["state"] == "问题" for f in results)


@pytest.mark.parametrize("good", [
    "水属性共鸣时，水属性角色技能伤害+15%（独立伤害乘区7）",
    "每发动3次强化弹射，自身攻击力+10%（最多10次）",
    "自身攻击力+50%、技能伤害+50%",
    "自身技能充能速度上限提升至1000%",
    "自身全伤害+10%（独立伤害乘区９）",
    "Fever模式中弹射时连击100以上，强化弹射升级为Lv4「苍海怒涛」：范围与威力提升，追加2段强化弹射伤害",
    "「真龙」形态中，强化弹射同时发动射击型与特殊型；「龙人」形态中，同时发动全部类型",
    "发动「PF之舞」：自身攻击力+10%",
    "不消耗技能槽",
    "自身直接攻击的基础伤害变为5倍，每1连击再+10%（无上限）",
    "发动「夜鸦」（以强化弹射伤害计算，CT：5秒）",
    "强化『月牙』及『月光』：范围扩大；每发动1次强化弹射，自身攻击力+10%",
])
def test_valid_examples_and_preserved_names_are_not_rewritten(good):
    assert not check_entry("desc_override_hero_1", good)


def test_skill_numbers_distinguish_allowed_duration_stack_and_threshold():
    good = "【生命值50%以下时】对敌人造成火属性伤害／自身攻击力提升效果（持续10秒，最多3层）"
    assert not check_entry("hero.1", good, surface="action_skill")
    assert check_entry("hero.1", "对敌人造成3段×2倍率的伤害", surface="action_skill")


def test_catalog_covers_every_section_and_cannot_claim_semantics_pass():
    rules = rule_catalog()["rules"]
    assert len(rules) >= 50
    assert {rule["source"].rsplit("§", 1)[1] for rule in rules} == set(map(str, range(1, 11)))
    assert all(rule["evidence_nature"] in {"作者规范", "官方模板引用"} for rule in rules)
    assert all(rule["implementation"]["mode"] in {"automatic", "partial", "review"} for rule in rules)
    states = {entry["rule"]: entry["state"] for entry in coverage({"desc_override", "action_skill"})}
    for rule in rules:
        if rule["implementation"]["mode"] != "automatic":
            assert states[rule["id"]] == "待验证"
        if not any(rule["implementation"].get(key) for key in ("check", "patterns", "document_check")):
            assert rule["implementation"]["mode"] == "review"
    assert all(entry["state"] == "不适用" for entry in coverage(set()))
    assert all("未做自动判定" in entry["boundary"] for entry in coverage({"desc_override"}) if entry["mode"] == "review")


def test_check_character_and_edit_gate_use_the_same_new_rules(workspace):
    document = workspace.read("1")
    key = "desc_override_wolf_1"
    document["desc_override"][key] = "自身PF伤害+20%"
    assert any(f["rule"] == "text.standard.term-pf" for f in check_character(document))
    with pytest.raises(ValueError, match="text.standard.term-pf"):
        prepare_edit(workspace, edit_for(workspace, desc_override={key: {"old": "自身攻击力提升", "new": "自身PF伤害+20%"}}))


def test_skill_edit_updates_both_server_mirrors_without_changing_inputs(workspace):
    before = {target: path.read_bytes() for target, path in workspace.server_paths.items()}
    snapshot = workspace.read("1")
    phrase = "对前方的敌人造成火属性伤害／赋予自身浮游效果（持续10秒）"
    changes = {tier: {"c1": {"old": pair["c1"], "new": phrase}} for tier, pair in snapshot["action_skill"].items()}
    prepared = prepare_edit(workspace, edit_for(workspace, action_skill=changes))
    for target in (SERVER_TARGET, RANK_TARGET):
        row = json.loads(prepared["servers"][target])["1"][0]
        assert [row[index] for index in (5, 7, 9)] == [phrase] * 3
        assert workspace.server_paths[target].read_bytes() == before[target]
    bad = copy.deepcopy(changes)
    bad["2"]["c1"]["new"] = "对敌人造成43倍火属性伤害"
    with pytest.raises(ValueError, match="skill-damage-numbers"):
        prepare_edit(workspace, edit_for(workspace, action_skill=bad))


def test_unrelated_automatic_ability_strings_are_outside_panel_scope():
    document = {"character_id": "1", "action_skill": {}, "desc_override": {},
                "custom_ability_string": {"official_template": "PF伤害+10%"}}
    from wf.text.standard import check_document
    assert check_document(document) == []


def test_leader_substring_in_character_name_is_not_treated_as_a_slot():
    text = "泽赫尔为队长时，强化自身冲刺：威力提升"
    findings = check_entry("desc_override_guildknight_leader_tavern_3", text)
    assert any(f["rule"] == "text.standard.leader-relocation" for f in findings)
    assert not any(f["rule"] == "text.standard.leader-relocation" for f in
                   check_entry("desc_override_guildknight_leader_tavern", text))


def test_check_text_cli_reports_new_rule_and_pending_semantics(workspace, tmp_path, capsys):
    from wf.check import main
    document = workspace.read("1")
    document["desc_override"]["desc_override_wolf_1"] = "自身PF伤害+20%"
    path = tmp_path / "character.json"
    path.write_text(json.dumps(document, ensure_ascii=False), "utf-8")
    assert main(["text", str(path)]) == 1
    report = json.loads(capsys.readouterr().out)
    rows = {entry["rule"]: entry for entry in report["files"][0]["results"]}
    assert rows["text.standard.term-pf"]["status"] == "问题"
    assert rows["text.standard.term-pf"]["evidence_nature"] == "作者规范"
    assert rows["text.standard.preserve-data"]["status"] == "待验证"
