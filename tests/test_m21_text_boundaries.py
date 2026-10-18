"""M3: enumerated patterns never prove semantic coverage or numeric intent."""
import pytest

from wf.text.standard import check_entry, coverage


@pytest.mark.parametrize("text,rule", [
    ("Fever状态下，自身攻击力+10%", "fever"),
    ("水属性共鸣后，自身攻击力+10%", "resonance"),
    ("战斗开始以后，自身技能槽+10%", "battle-start"),
])
def test_unlisted_wording_cannot_receive_satisfied_coverage(text, rule):
    findings = check_entry("hero", text)
    record = next(r for r in coverage({"desc_override"}, findings)
                  if r["rule"] == "text.standard." + rule)
    assert record["state"] == "待验证"
    assert record["mode"] == "partial"
    assert "仅列举写法" in record["boundary"]


@pytest.mark.parametrize("text", [
    "赋予浮游效果，持续时间变为2倍",
    "层数上限变为2倍",
    "速度提升至2倍，对敌人造成火属性伤害",
    "对敌人造成火属性伤害／持续时间和层数上限变为2倍",
    "自身速度变为1.5倍",
])
def test_duration_stack_speed_multipliers_are_not_damage(text):
    assert not any(f["rule"] == "text.standard.skill-damage-numbers"
                   for f in check_entry("hero", text, surface="action_skill"))


@pytest.mark.parametrize("text", [
    "对敌人造成合计43倍火属性伤害", "造成2.5倍的技能伤害",
    "伤害倍率提升至3倍", "造成3段×2倍率的伤害",
])
def test_explicit_damage_multipliers_still_fail(text):
    assert any(f["rule"] == "text.standard.skill-damage-numbers"
               for f in check_entry("hero", text, surface="action_skill"))
