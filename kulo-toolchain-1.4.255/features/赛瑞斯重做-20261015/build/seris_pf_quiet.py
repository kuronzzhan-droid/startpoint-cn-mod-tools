# -*- coding: utf-8 -*-
"""赛瑞斯多类型强化弹射：把官方五种 PF（knight 剑 / fighter 拳 / ranged 射击 / supporter 辅助 / special 特殊）
同档原版动作拼进一棵树。每种保持官方原倍率（作者 10-15 拍板）。

拼法：
- 每棵子树的绑定号整体平移（100×序号），标签加前缀，避免互相串号；
- 子树各自的 SetPowerFilpSuppress / NotifyPowerflipEnd / 只包着 Notify 的超时 Wait / RemoveEvent 全部去掉，
  顶层统一一条 Suppress(S) + Wait(S-1){Notify -18}，S = 各子树最长收尾帧（官方配对律 Notify=Suppress-1）；
- 辅助型的增益（原 FindAllSubjects 33 全队）改成只给自身（-17），作者要求加成纯自身；
- Lv4：倍率 ×LV4_MULT，判定范围 ×LV4_RANGE（矩形长度已是 4000 全场的不动）。

【quiet 版（10-15 作者「音效有点多和吵」）】与 seris_pf.py 唯一差别 = compose() 末尾 quiet_paths()：
- 平时 lv1-3：只保留 KEEP_SOUND 类型（特殊型 special：set + clear 两声）的官方特效路径，其余类型的 ShowEffect
  改指 skill_unique/seris_dragon_king/pfq_<类型>/ 下的静音副本（官方 sheet 原字节复制、parts 只改图名前缀、timeline 清 sounds）；
- Lv4：全部类型都换静音副本，Lv4 只剩苍海怒涛自己的一声；
- 判定/伤害/寿命/HideEffect 一律不动（只改 ShowEffect 第 3 位路径），check() 仍然在 quiet 之后跑。
"""
import copy
import json
from pathlib import Path

SRC = Path(__file__).resolve().parent / "pf_src"
TYPES_HUMAN = ("ranged", "special")
TYPES_DRAGON = ("knight", "fighter", "ranged", "supporter", "special")
LV4_MULT = 2.5
LV4_RANGE = 3.0
# 子树收尾帧（官方原值；碰撞型取「超时 90 帧才撞到 + 碰撞后收尾」的最坏值）
KEEP_SOUND = ("special",)
QUIET_MAP = json.loads((Path(__file__).resolve().parent.parent / "fx" / "pf_quiet" / "path_map.json").read_text("utf-8"))
TYPE_OF_DIR = {"effect_powerflip_attack_spin": "knight", "effect_powerflip_attack_fight": "fighter",
               "effect_powerflip_attack_beam": "ranged", "effect_powerflip_attack_support": "supporter",
               "effect_powerflip_attack_special": "special"}
END = {"knight": 110, "fighter": 90 + 24 + 28, "ranged": 35, "supporter": 30, "special": 90 + 30}


def load(t, lv):
    return json.loads((SRC / f"{t}_lv{lv}.json").read_text(encoding="utf8"))


def is_block(x):
    return isinstance(x, list) and len(x) == 2 and x[0] == "Block" and isinstance(x[1], list)


def nodes(stmts):
    """遍历语句列表，yield (kind, cmd_list)；cmd_list 是 n[1] 本体（可原地改）。"""
    for st in stmts:
        if isinstance(st, list) and len(st) == 2 and st[0] in ("Command", "Event"):
            c = st[1]
            yield st[0], c
            for x in c[1:]:
                if is_block(x):
                    yield from nodes(x[1])


# 每种构造里「绑定号」所在位置：值 ≥0 才平移（负数是内建：-1 场地、-17 自身、-18 球）
ID_POS = {
    "CreateHitArea": (2, 19, 21, 22),
    "CreateNormalAttack": (1,),
    "ShowEffect": (3,),
    "CreateReferencePoint": (1, 10),
    "FindAllSubjects": (1,),
    "CreateCondition": (1,),
    "StopBall": (1,),
    "NotifyPowerflipEnd": (1,),
    "CollisionOfBallAndEnemy": (4,),
}
LABEL_POS = {"ShowEffect": 1, "HideEffect": 1, "RemoveEvent": 1, "Wait": 2}
KNOWN = set(ID_POS) | set(LABEL_POS) | {"SetPowerFilpSuppress", "ShakeCamera"}


def renumber_and_label(stmts, off, prefix):
    for kind, c in nodes(stmts):
        name = c[0]
        assert name in KNOWN, f"未覆盖的构造 {name}（先补 ID_POS/LABEL_POS 再拼）"
        for i in ID_POS.get(name, ()):
            assert isinstance(c[i], int), (name, i, c[i])
            if c[i] >= 0:
                c[i] += off
        for x in c[1:]:                             # 坐标系 ["GH", 主体号] 里也带绑定号
            if isinstance(x, list) and len(x) == 2 and x[0] == "GH" and isinstance(x[1], int) and x[1] >= 0:
                x[1] += off
        j = LABEL_POS.get(name)
        if j is not None and c[j] != "*":
            c[j] = prefix + c[j]


def strip_lifecycle(stmts):
    out = []
    for st in stmts:
        kind, c = st
        if kind == "Command" and c[0] in ("SetPowerFilpSuppress", "NotifyPowerflipEnd", "RemoveEvent"):
            continue
        if kind == "Event" and c[0] == "Wait":
            body = c[3][1]
            if all(b[0] == "Command" and b[1][0] == "NotifyPowerflipEnd" for b in body):
                continue
        st = [kind, [x if not is_block(x) else ["Block", strip_lifecycle(x[1])] for x in c]]
        out.append(st)
    return out


def support_self(stmts):
    """辅助型：FindAllSubjects(id, 33) 全队 → 增益只给自身。演出那支（只有 ShowEffect）一起收成自身。"""
    out = []
    for st in stmts:
        kind, c = st
        if kind == "Command" and c[0] == "FindAllSubjects" and c[2] == 33:
            sid = c[1]
            for b in c[-1][1]:
                bc = b[1]
                if bc[0] in ("CreateCondition",) and bc[1] == sid:
                    if any(x[0] == "ACFlying" for x in bc[2]):
                        continue                         # 作者 10-15：辅助型去掉浮游
                    bc[1] = -17
                elif bc[0] == "ShowEffect" and bc[3] == sid:
                    bc[3] = -17
                out.append(b)
            continue
        out.append([kind, [x if not is_block(x) else ["Block", support_self(x[1])] for x in c]])
    return out


def scale(stmts, mult, rng):
    for kind, c in nodes(stmts):
        if c[0] == "CreateNormalAttack":
            for v in c[6]:                          # 倍率（攻击力倍率）
                v["min"] = round(v["min"] * mult, 6)
                v["max"] = round(v["max"] * mult, 6)
        if c[0] == "CreateHitArea" and rng != 1:
            shape = c[9]
            for k, dim in enumerate(shape[1:], 1):
                for v in dim:
                    if v["max"] >= 1500:            # 已是全场尺寸的不再放大
                        continue
                    v["min"] = min(round(v["min"] * rng), 1500)
                    v["max"] = min(round(v["max"] * rng), 1500)


def compose(types, lv, lv4=False):
    trees = [load(t, lv) for t in types]
    body = []
    end = 0
    for k, (t, tr) in enumerate(zip(types, trees)):
        assert tr[0] == "ActionDsl" and tr[10] == 0 and is_block(tr[11]), t
        stmts = copy.deepcopy(tr[11][1])
        renumber_and_label(stmts, 100 * (k + 1), f"{t}:")
        stmts = strip_lifecycle(stmts)
        if t == "supporter":
            stmts = support_self(stmts)
        if lv4:
            scale(stmts, LV4_MULT, LV4_RANGE)
        body += stmts
        end = max(end, END[t])
    root = copy.deepcopy(trees[0])
    root[1] = max(tr[1] for tr in trees)
    root[11] = ["Block", [["Command", ["SetPowerFilpSuppress", end]]] + body +
                [["Event", ["Wait", end - 1, "*", ["Block", [["Command", ["NotifyPowerflipEnd", -18]]]]]]]]
    quiet_paths(root, keep=() if lv4 else KEEP_SOUND)
    check(root)
    return root


def quiet_paths(root, keep):
    """把非保留类型的官方 PF 特效路径换成静音副本；返回替换条数。"""
    n = 0
    for _kind, c in nodes(root[11][1]):
        if c[0] != "ShowEffect":
            continue
        p = c[2][1]
        if p in QUIET_MAP and TYPE_OF_DIR[p.split("/")[-2]] not in keep:
            c[2] = ["SpecifyEffectDirectly", QUIET_MAP[p]]
            n += 1
        else:
            assert not p.startswith("battle/effect/powerflip/") or TYPE_OF_DIR[p.split("/")[-2]] in keep, p
    return n


def check(root):
    """每个引用的绑定号都必须先由本树创建；不出现两处创建同一号。"""
    made, used = [], []
    for kind, c in nodes(root[11][1]):
        n = c[0]
        if n == "CreateHitArea":
            made += [c[19], c[21], c[22]]; used.append(c[2])
        elif n == "CreateReferencePoint":
            made.append(c[10]); used.append(c[1])
        elif n == "FindAllSubjects":
            made.append(c[1])
        elif n == "CollisionOfBallAndEnemy":
            made.append(c[4])
        elif n in ("CreateNormalAttack", "CreateCondition", "StopBall", "NotifyPowerflipEnd"):
            used.append(c[1])
        elif n == "ShowEffect":
            used.append(c[3])
        used += [x[1] for x in c[1:] if isinstance(x, list) and len(x) == 2 and x[0] == "GH"]
    assert len(made) == len(set(made)), sorted(made)
    bad = [u for u in used if u >= 0 and u not in made]
    assert not bad, bad
    n_notify = sum(1 for _k, c in nodes(root[11][1]) if c[0] == "NotifyPowerflipEnd")
    assert n_notify == 1, n_notify


def total_multiplier(root):
    """粗算：每个 CreateNormalAttack 倍率 × 所在判定区最大命中数（没有判定区包裹的按 1）。"""
    tot = 0.0

    def walk(stmts, hits):
        nonlocal tot
        for st in stmts:
            kind, c = st
            h = hits
            if c[0] == "CreateHitArea":
                h = c[14][1] * (c[12][1] if c[12][0] == "NWay" else 1)
            if c[0] == "CreateNormalAttack":
                tot += c[6][0]["max"] * hits
            for x in c[1:]:
                if is_block(x):
                    walk(x[1], h)
    walk(root[11][1], 1)
    return round(tot, 2)


if __name__ == "__main__":
    for form, types in (("human", TYPES_HUMAN), ("dragon", TYPES_DRAGON)):
        for lv in (1, 2, 3):
            r = compose(types, lv)
            print(form, lv, "suppress", r[11][1][0][1][1], "≈总倍率", total_multiplier(r))
        r = compose(types, 3, lv4=True)
        print(form, "LV4 ≈总倍率", total_multiplier(r))
    for t in TYPES_DRAGON:
        print(t, "lv3 单类型≈", total_multiplier(compose((t,), 3)))
