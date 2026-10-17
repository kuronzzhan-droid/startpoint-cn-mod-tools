"""Deterministic fragments of the panel convention; no gameplay inference."""
from __future__ import annotations

import re

NUMBER = r"\d+(?:\.\d+)?"


def unquote(text):
    """Keep spans aligned while excluding names from terminology replacement."""
    return re.sub(r"「[^」]*」|『[^』]*』", lambda match: " " * len(match[0]), text)


def _matches(pattern, text):
    return [match[0] for match in re.finditer(pattern, text)]


def line_stops(text, key):
    return _matches(r"[。.]\s*(?:\n|$)", text)


def prefix_order(text, key):
    findings = []
    categories = (r"[火水雷风光暗]属性共鸣时", r"(?:非)?Fever模式中|自身处于「[^」]+」状态时|贯穿效果中",
                  r"每(?:发动|达成|直接攻击|经过)\d+|战斗开始时|进入Fever模式时")
    for line in text.splitlines():
        # Only compare condition clauses before the first explicit subject.
        prefix = re.split(r"自身(?!处于)|[火水雷风光暗]属性角色|队伍全体", line)[0]
        ordered = sorted((match.start(), index) for index, pattern in enumerate(categories)
                         for match in re.finditer(pattern, prefix))
        if [index for _, index in ordered] != sorted(index for _, index in ordered):
            findings.append(line)
    return findings


def leader_slot(text, key):
    return _matches(r"自身为队长时", text) if re.search(r"_(?:leader|ls)$", key) else []


def leader_relocation(text, key):
    if not re.search(r"_[1-6]$", key):
        return []
    return _matches(r"(?:担任|作为)队长(?:时)?|[^，。\s「」]{1,12}为队长时", text)


def pursuit(text, key):
    wrong = []
    for line in text.splitlines():
        # Conflicting labels are direct evidence; absent labels need data review.
        if "追击伤害" in line and re.search(r"独立伤害乘区[１２21]", line):
            wrong.append(line)
        if re.search(r"麻痹|气绝", line) and "独立伤害乘区3" in line and "虚弱" not in line:
            wrong.append(line)
    return wrong


def number_format(text, key):
    return _matches(rf"[＋－−]\s*{NUMBER}%|{NUMBER}％|连击(?:增加|提升){NUMBER}|(?<!\d){NUMBER}\s*[xX×]倍率", unquote(text))


def limits(text, key):
    wrong = _matches(rf"（(?:上限|至多)\+?{NUMBER}(?:次|层)）|（累计上限[+\-]?{NUMBER}%）", text)
    wrong += [line for line in text.splitlines()
              if re.search(r"（最多\d+次）", line) and re.search(r"（最大\+" + NUMBER + r"%）", line)]
    return wrong


def timing(text, key):
    return _matches(rf"(?:冷却(?:时间)?[：:]?\s*{NUMBER}\s*秒|CT\s*:\s*{NUMBER}|仅触发一次|仅一次)", text)


def damage_zones(text, key):
    wrong = []
    for match in re.finditer(r"[（(]独立伤害乘区([^）)]+)[）)]", text):
        if match[1] not in (*map(str, range(1, 9)), "９") or not match[0].startswith("（") or not match[0].endswith("）"):
            wrong.append(match[0])
    return wrong


def invoke(text, key):
    if not (key.startswith("ability_skill_") or "发动技能「" in text):
        return []
    wrong = _matches(r"发动技能「", text)
    if key.startswith("ability_skill_") and not re.search(r"发动「[^」]+」", text):
        wrong.append(text)
    if key.startswith("ability_skill_") and not re.search(r"CT：" + NUMBER + r"秒", text):
        wrong.append("缺少CT：N秒")
    return wrong


def special_pf(text, key):
    if "自身的强化弹射变为" not in text:
        return []
    return [] if re.search(r"自身的强化弹射变为「[^」]+」：", text) else [text]


def enhance(text, key):
    wrong = []
    for line in text.splitlines():
        if not re.search(r"强化[『「]", line):
            continue
        phrase = re.search(r"强化『[^』]+』(?:(?:及|、|与)『[^』]+』)*：", line)
        if not phrase:
            wrong.append(line)
        explanation = re.split(r"[；;]", line[phrase.end():] if phrase else line, maxsplit=1)[0]
        if re.search(r"\d", unquote(explanation)):
            wrong.append(explanation)
    return wrong


def tautology(text, key):
    from .rules import _TAUTOLOGY, normalized
    return _matches(_TAUTOLOGY, normalized(text))


def repetition(text, key):
    wrong = []
    for line in re.split(r"[\n；;]", text):
        conditions = re.findall(r"([^，、；]{2,30}(?:时|中))[，、]", line)
        wrong += [value for value in set(conditions) if conditions.count(value) > 1]
    return wrong


def skill_buff_numbers(text, key):
    return _matches(rf"(?:攻击力|技能伤害|直接攻击伤害|强化弹射伤害|全属性抗性|[火水雷风光暗]属性抗性|技能充能速度)"
                    rf"(?:提升|提高|增加|降低|减少|[+＋\-－])\s*{NUMBER}%", unquote(text))


def skill_body(text, key):
    return _matches(r"(?:队长技|能力[一二三四五六123456])(?:强化|赋予|追加)|强化『[^』]+』：", text)


def damage_conversion(text, key):
    wrong = []
    for clause in re.split(r"[\n／；]", text):
        if re.search(r"发动「[^」]+」", clause):
            continue  # §6 explicitly permits this wording for appended skills.
        wrong += _matches(r"以(?:强化弹射|直接攻击|技能|能力)伤害计算|伤害按(?:强化弹射|直接攻击|技能|能力)", clause)
    return wrong


def six_elements(text, key):
    if "六属性能力伤害" not in text:
        return []
    return [] if "（火／水／雷／风／光／暗各结算1次）" in text else ["六属性能力伤害缺各属性结算说明"]


def direct_base(text, key):
    return _matches(r"直接攻击倍率(?:变为|增加)|直接攻击基础倍率", text)


def multi_pf(text, key):
    wrong = _matches(r"强化弹射(?:同时具备|同时生效)", text)
    for line in text.splitlines():
        if "同时发动" not in line:
            continue
        types = re.findall(r"(?:剑士|格斗|射击|辅助|特殊)型", line)
        if len(set(types)) == 5:
            wrong.append("五种类型应写同时发动全部类型")
        if len(types) >= 2 and not re.search(r"与(?:剑士|格斗|射击|辅助|特殊)型", line):
            wrong.append("类型列表最后一项应使用与连接")
        wrong += _matches(r"(?:战士|拳斗|弓箭|支援)型", line)
    return wrong


def pf_lv4(text, key):
    wrong = []
    for line in text.splitlines():
        if not re.search(r"强化弹射.*(?:Lv4|LV4|Lv\.4)", line):
            continue
        if not re.search(r"Lv4「[^」]+」：", line):
            wrong.append("Lv4缺少规范名称或冒号")
        # Threshold/mode applicability is data-dependent; report review, not invention.
    return wrong


def fever_items(text, key):
    if "加速箭头" not in text or "道具" not in text:
        return []
    return [] if "Fever模式中，场上的加速箭头变为随机道具" in text else [text]


CHECKS = {name: value for name, value in list(globals().items())
          if callable(value) and not name.startswith("_") and name not in {"unquote"}}
