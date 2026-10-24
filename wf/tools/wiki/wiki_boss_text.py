"""Player-facing five-boss explanations, parameterized by the current spec."""
from __future__ import annotations

import re


def percent(value):
    return f"{value * 100:g}%"


def seconds(frames):
    return f"{frames / 60:g} 秒"


def affix_texts(params):
    result = {}
    for key in ("enrage_r0", "enrage_r1"):
        p = params[key]
        result[key] = {"name": "狂暴", "description":
            f"每 {seconds(p['interval'])}，敌方攻击力增加 {percent(p['atk'])}，最多 {p['atk_layers']} 层；"
            f"全属性耐性增加 {percent(p['res'])}，最多 {p['res_layers']} 层。"}
    p = params["weaken_rotation"]
    result["weaken_rotation"] = {"name": "轮换虚弱", "description":
        f"攻击力、技能伤害、直接攻击伤害依次降低 {percent(abs(p['value']))}，"
        f"各持续 {seconds(p['frames'])}；各项每 {seconds(p['period'])} 重复，彼此错开 {seconds(p['period'] / 3)}。"}
    p = params["heal_seal"]
    result["heal_seal"] = {"name": "治疗封锁", "description":
        f"场地阻止回复；全队累计 {p['cancel_direct_hits']} 次直接攻击命中后解除。"}
    p = params["combo_cap"]
    result["combo_cap"] = {"name": "连击限制", "description":
        f"连击数上限 {p['cap']}；完成 {p['cancel_powerflips']} 次强化弹射后解除。"}
    p = params["slow_charge"]
    result["slow_charge"] = {"name": "充能迟滞", "description":
        f"技能充能速度降低 {percent(abs(p['value']))}；全队累计 {p['cancel_direct_hits']} 次直接攻击命中后解除。"}
    p = params["slip"]
    result["slip"] = {"name": "持续损伤", "description":
        f"场地持续造成损伤；全队累计获得 {p['cancel_conditions']} 次攻击力提升状态后解除。"}
    p = params["silence_waves"]
    result["silence_waves"] = {"name": "沉默波", "description":
        f"每 {seconds(p['interval'])} 强制施加一次持续 {seconds(p['frames'])} 的沉默。"}
    p = params["fever_drain"]
    result["fever_drain"] = {"name": "Fever 抑制", "description":
        f"Fever 获取量降低 {percent(abs(p['value']))}，持续生效且无法驱散。"}
    p = params["purge_r1"]
    result["purge_r1"] = {"name": "王座入场清算", "description":
        f"入场强制清除增益、扣除 100% 技能槽，并禁止获得增益 {seconds(p['buff_reject_frames'])}；"
        f"此后每 {seconds(p['periodic_interval'])} 强制清除最新 {p['periodic_limit']} 个增益。"}
    names = {"sig_abyss_curse": "深渊诅咒", "sig_blood_tide": "血潮", "sig_king_seal": "王之封印",
             "sig_king_purge": "王之肃清"}
    effects = {"ACSkillDamage": "技能伤害", "ACFeverPoint": "Fever 获取量", "ACDirectDamage": "直接攻击伤害"}
    for key, name in names.items():
        p, clauses = params[key], []
        for kind, frames, value in p.get("effects", []):
            clauses.append(f"{effects[kind]}降低 {percent(abs(value))}，持续 {seconds(frames)}")
        if p.get("silence"):
            clauses.append(f"强制沉默 {seconds(p['silence'])}")
        if p.get("drain"):
            clauses.append(f"扣除 {percent(p['drain'])} 技能槽")
        if p.get("purge"):
            clauses.append("强制清除增益（包括通常无法驱散的状态）")
        result[key] = {"name": name, "description":
            ("登场时及" if p.get("on_entry") else "") + f"每 {seconds(p['interval'])}：" + "；".join(clauses) + "。"}
    return result


def enemy_conditions(states):
    names = {0: "能力伤害耐性", 1: "直接攻击伤害耐性", 2: "强化弹射伤害耐性", 3: "技能伤害耐性"}
    return ["敌方弱体耐性" if kind == 4 else f"敌方{names[kind]} {value * 100:+g}%"
            for kind, value in states]


def reward_text(rewards, item_names):
    def number(name):
        match = re.search(r"export const " + name + r"\s*=\s*([\d.]+)", rewards)
        if not match:
            raise ValueError("五重决战奖励常量缺失，不能生成当前攻略")
        return float(match[1])

    # Non-constant reward quantities must still match the implementation we explain.
    for expected in ("amount: 10 * input.rewardMultiplier", "< 0.25", "let fiveKingCoreAmount = input.rewardMultiplier"):
        if expected not in rewards:
            raise ValueError("五重决战奖励公式已变化，请更新说明")
    low = int(number("FIVE_BOSS_KING_COIN_MIN"))
    high = low + int(number("FIVE_BOSS_KING_COIN_SPAN")) - 1
    return [
        {"name": item_names["10000144"], "description": f"每次通关 {percent(number('FIVE_BOSS_BLUEPRINT_DROP_RATE'))} 概率获得 1 张，不受手动倍率影响。"},
        {"name": item_names["10000145"], "description": "每次通关 10 × 奖励倍率。"},
        {"name": item_names["10000147"], "description": "必得 1 × 奖励倍率；另有 25% 概率再得 1 × 奖励倍率。"},
        {"name": item_names["10000310"], "description": f"每次通关随机获得 {low}–{high} 枚，不受手动倍率影响。"},
        {"name": item_names["10000146"], "description": "首次有效通关额外获得 1 枚。"},
        {"name": "诅咒武器", "description": f"每次判定 {percent(number('FIVE_BOSS_CURSED_WEAPON_DROP_RATE'))} 概率随机获得 1 件；手动判定 2 次，AUTO 判定 1 次，可能重复。"},
    ]
