# -*- coding: utf-8 -*-
"""PARADOX 第二轮（作者 1007）：在旧仓生成器副本上定点改写 → wf_paradox_weapon_r2.py。

作者原话：「PARADOX武器的诅咒改为武器本体满额生效,200级属性给的1000%攻击力和全部伤害类型还有乘区改为自身发动技能时获得,
发动10次技能暖满数值改为单个最高800点乘区单个25%其他不变」

读法：
1. 诅咒（自身以外攻击 -800%、充能 -40%、开局「诅咒」+ 持有期间 423 回槽拦截）从强化 Lv120 挪到本体（ability_soul），
   觉醒 0 起满额；强化表不再有诅咒行。衰减分档同样带诅咒（代价不随衰减减轻，原口径）。
2. 攻击力 + 四类伤害（32/33/34/55/388）与五个独立乘区（723/693/694/695/696）不再常驻：本体、强化成长、Lv120→200 续涨
   每一行都改成「自身发动技能时」永久叠加，每行最多 10 次；Lv200 时 10 次叠满 = 每项 +800% / 乘区每项 +25%
   （每次 +80% / +2.5%）。各等级段按原比例缩放（原 Lv200 合计 1000% / 30% → 800% / 25%）。
3. 其余（直击段数、弹射连击、充能、槽上限、弱体无效、合击白值、三人专属、回响、外观、材料、商店）不动。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent.parent / "oldrepo_modtools" / "wf_paradox_weapon.py"
DST = HERE / "wf_paradox_weapon_r2.py"
R: list[tuple[str, str]] = []


def rep(old: str, new: str) -> None:
    R.append((old, new))


rep('''FINAL_LEVEL = 120 ''', '''#: 第二轮（1007）：攻击/四类伤害与五个乘区改为「自身发动技能时」叠加，每行最多 STACKS 次；Lv200 叠满合计
STACKS = 10
WARM_ATK, WARM_MULT = 800, 25
K_ATK, K_MULT = WARM_ATK / ATK_TOTAL200 / STACKS, WARM_MULT / MULT_TOTAL200 / STACKS
FINAL_LEVEL = 120 ''')
rep('''ENH_DESCRIPTION = "强化至120级进入终式：数值全面提升并解放诅咒，除自身外的角色无法获得能力和装备的技能槽增加效果。"''',
    '''ENH_DESCRIPTION = "强化至120级进入终式：数值全面提升，直接攻击段数与弹射连击再提升。"''')

# 本体：攻/伤/乘区改为发动技能时叠加；诅咒四行追加在本体末尾（已发布行的 slot 不动）
rep('''        *(Eff("0", W.stat(k, _target(k), ATK_BASE * r), note=f"{_who(k)}{DAMAGE_LABEL[k]} +{ATK_BASE}%")
          for k in DAMAGE_KINDS),
        *(Eff("0", W.stat(k, _target(k), MULT_BASE * r), note=f"{_who(k)}{MULT_LABEL[k]}独立乘区 +{MULT_BASE}%")
          for k in MULT_KINDS),''',
    '''        *(Eff("0", W.stat(k, _target(k), ATK_BASE * r * K_ATK), trig=WARM,
              note=f"发动技能时{_who(k)}{DAMAGE_LABEL[k]} +{ATK_BASE * K_ATK:g}%（最多 {STACKS} 次）")
          for k in DAMAGE_KINDS),
        *(Eff("0", W.stat(k, _target(k), MULT_BASE * r * K_MULT), trig=WARM,
              note=f"发动技能时{_who(k)}{MULT_LABEL[k]}独立乘区 +{MULT_BASE * K_MULT:g}%（最多 {STACKS} 次）")
          for k in MULT_KINDS),''')
rep('''        *echo_rows(),                                          # 回响固定 25%，不随衰减分档缩放
    ]''', '''        *echo_rows(),                                          # 回响固定 25%，不随衰减分档缩放
        *curse_rows(),                                         # 第二轮：诅咒挪到本体，满额（不随衰减减轻）
    ]


WARM = W.trig(W.IT_SKILL, trigger_puller=W.P_SELF, trigger_limit=str(STACKS))


def curse_rows() -> list[Eff]:
    return [
        Eff("0", W.stat("32", W.T_EXCEPT, CURSE_ATK), note=f"【诅咒】自身以外的角色攻击力 {CURSE_ATK}%（引擎下限 -50%）"),
        Eff("0", W.stat("35", W.T_EXCEPT, CURSE_CHARGE), note=f"【诅咒】自身以外的角色技能充能速度 {CURSE_CHARGE}%"),
        Eff("0", W.unique(CURSE_UID), note="【诅咒】开局给自身刻上「诅咒」（永续、不可驱散）"),
        Eff("1", ("423", {"target": W.T_EXCEPT, "unique_condition_id": str(GAUGE_MASK)}), trig=W.gate_unique(CURSE_UID),
            note="【诅咒】自身持有「诅咒」时，自身以外的角色无法获得能力和装备的技能槽增加效果（423，规则码 8）"),
    ]''')

# 强化：攻/伤/乘区的成长、120 补足、200 续涨都按比例缩放并改为发动技能时叠加
rep('''    for kind, total, total200, base in ((*((k, ATK_TOTAL, ATK_TOTAL200, ATK_BASE) for k in DAMAGE_KINDS),
                                         *((k, MULT_TOTAL, MULT_TOTAL200, MULT_BASE) for k in MULT_KINDS),
                                         ("35", CHARGE_TOTAL, CHARGE_TOTAL200, CHARGE_BASE),
                                         ("245", GAUGE_TOTAL, None, GAUGE_BASE),
                                         ("717", UNISON_TOTAL, UNISON_TOTAL200, UNISON_BASE))):
        lift = None if total200 is None else (total200 - total) * r
        rows += _growth_pair(kind, _target(kind), total * r, base * r, lift=lift)''',
    '''    for kind, total, total200, base, k, kw in (
            *((k, ATK_TOTAL, ATK_TOTAL200, ATK_BASE, K_ATK, {"trig_": WARM}) for k in DAMAGE_KINDS),
            *((k, MULT_TOTAL, MULT_TOTAL200, MULT_BASE, K_MULT, {"trig_": WARM}) for k in MULT_KINDS),
            ("35", CHARGE_TOTAL, CHARGE_TOTAL200, CHARGE_BASE, 1, {}),
            ("245", GAUGE_TOTAL, None, GAUGE_BASE, 1, {}),
            ("717", UNISON_TOTAL, UNISON_TOTAL200, UNISON_BASE, 1, {})):
        lift = None if total200 is None else (total200 - total) * r * k
        rows += _growth_pair(kind, _target(kind), total * r * k, base * r * k, lift=lift, **kw)''')
rep('''        Eff("0", W.stat("32", W.T_EXCEPT, CURSE_ATK), **final,
            note=f"【诅咒】自身以外的角色攻击力 {CURSE_ATK}%（引擎下限 -50%）"),
        Eff("0", W.stat("35", W.T_EXCEPT, CURSE_CHARGE), **final, note=f"【诅咒】自身以外的角色技能充能速度 {CURSE_CHARGE}%"),
        # R3（equipment-rules）：开局刻「诅咒」→ 持有期间 423 拦掉自身以外角色的能力类回槽；新行只追加在末尾，已发布行的 slot 不动
        Eff("0", W.unique(CURSE_UID), **final, note="【诅咒】120 级：开局给自身刻上「诅咒」（永续、不可驱散）"),
        Eff("1", ("423", {"target": W.T_EXCEPT, "unique_condition_id": str(GAUGE_MASK)}), trig=W.gate_unique(CURSE_UID),
            **final, note="【诅咒】自身持有「诅咒」时，自身以外的角色无法获得能力和装备的技能槽增加效果（423，规则码 8）"),
    ]''', '''    ]''')

# 详情覆盖文案
rep('''        f"攻击力与全部伤害类型（{types}）+{_num(ATK_BASE)}%＆全部独立乘区+{_num(MULT_BASE)}%",''',
    '''        f"每次发动技能：攻击力与全部伤害类型（{types}）+{_num(ATK_BASE * K_ATK)}%",
        f"每次发动技能：全部独立乘区+{_num(MULT_BASE * K_MULT)}%（以上各最多叠加{STACKS}次）",''')
rep('''          f"以{ECHO_PERCENT}%的效果回响「{ECHO_SKILL[code]}」" for cid, code, _ in ECHOES),
    ]''', '''          f"以{ECHO_PERCENT}%的效果回响「{ECHO_SKILL[code]}」" for cid, code, _ in ECHOES),
        f"【诅咒】自身以外的角色攻击力{_num(CURSE_ATK)}%＆技能充能速度{_num(CURSE_CHARGE)}%",
        f"【诅咒】开局自身获得「{CURSE_UNIQUE_NAME}」（永续、无法驱散）：自身以外的角色无法获得能力和装备的技能槽增加效果",
    ]''')
rep('''        f"攻击力与全部伤害类型+{_num(grow_value(ATK_TOTAL, ATK_BASE))}%"
        f"＆全部独立乘区+{_num(grow_value(MULT_TOTAL, MULT_BASE))}%",''',
    '''        f"每次发动技能：攻击力与全部伤害类型+{_num(grow_value(ATK_TOTAL * K_ATK, ATK_BASE * K_ATK))}%"
        f"＆全部独立乘区+{_num(grow_value(MULT_TOTAL * K_MULT, MULT_BASE * K_MULT))}%",''')
rep('''        f"每次弹射连击合计+{_num(COMBO_TOTAL)}，并解放【诅咒】",''', '''        f"每次弹射连击合计+{_num(COMBO_TOTAL)}",''')
rep('''        f"终式合计（含本体）：攻击力与全部伤害类型+{_num(ATK_TOTAL200)}%＆全部独立乘区+{_num(MULT_TOTAL200)}%",''',
    '''        f"终式合计（含本体）：每次发动技能攻击力与全部伤害类型+{_num(WARM_ATK / STACKS)}%"
        f"＆全部独立乘区+{_num(WARM_MULT / STACKS)}%",
        f"发动{STACKS}次技能叠满：攻击力与全部伤害类型各+{_num(WARM_ATK)}%＆全部独立乘区各+{_num(WARM_MULT)}%",''')
rep('''        f"【诅咒·Lv{FINAL_LEVEL}起】自身以外的角色攻击力{_num(CURSE_ATK)}%＆技能充能速度{_num(CURSE_CHARGE)}%",
        # 「战斗开始时」会让这行 58 字超出 57 字上限，用「开局」
        f"【诅咒·Lv{FINAL_LEVEL}起】开局自身获得「{CURSE_UNIQUE_NAME}」（永续、无法驱散）："
        "自身以外的角色无法获得能力和装备的技能槽增加效果",''',
    '''        f"【诅咒】自身以外的角色攻击力{_num(CURSE_ATK)}%＆技能充能速度{_num(CURSE_CHARGE)}%",
        f"【诅咒】开局自身获得「{CURSE_UNIQUE_NAME}」（永续、无法驱散）：自身以外的角色无法获得能力和装备的技能槽增加效果",''')


def main() -> None:
    text = SRC.read_text("utf-8")
    for i, (old, new) in enumerate(R):
        n = text.count(old)
        assert n == 1, f"替换 #{i} 命中 {n} 次：{old[:80]!r}"
        text = text.replace(old, new)
    n = text.count("Path(__file__).resolve().parent")
    assert n == 4, n
    text = text.replace("Path(__file__).resolve().parent", f"Path(r\"{SRC.parent}\")")
    DST.write_text(text, "utf-8")
    print(f"wrote {DST} ({len(R)} replacements)")


if __name__ == "__main__":
    main()
