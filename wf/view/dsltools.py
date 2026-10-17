import json
def walk(n, path=()):
    if isinstance(n, list):
        yield path, n
        for i, x in enumerate(n):
            yield from walk(x, path + (i,))
def commands(tree, name=None):
    for p, n in walk(tree):
        if len(n) >= 2 and n[0] == 'Command' and isinstance(n[1], list) and n[1] and isinstance(n[1][0], str):
            if name is None or n[1][0] == name:
                yield p, n[1]
def get(tree, path):
    for i in path: tree = tree[i]
    return tree
def summary(tree):
    out = []
    for p, c in commands(tree):
        if c[0] == 'CreateCondition':
            out.append((p, 'CreateCondition', c[1], [(a[0], a[1:]) for a in c[2]], c[7]))
        elif c[0] in ('CreateNormalAttack', 'CreateRatioAttack', 'AddSkillPoint', 'CreateRatioHeal', 'ConsumeUniqueCondition', 'DeleteCondition'):
            out.append((p, c[0], c[1:8]))
        elif c[0].startswith('Conditionals') or c[0] in ('FindAllSubjects',):
            out.append((p, c[0], c[1:3]))
    return out

from typing import Any
NULLABLE_DSL_ENUMS = frozenset({"HitCountCheckTargetKind"})

def dsl_signature_problems(tree: list) -> list[str]:
    """按 wf_dsl_sig（反编译生成的白名单）逐参核对：命令/事件名、参数个数、枚举构造名与嵌套参数、
    CreateCondition 的 AC 构造名与参数个数。编码器对拼错的构造名不报错（静默吞节点），必须在这里拦住。"""
    import wf_dsl_sig as SIG
    probs: list[str] = []
    enums = SIG.ENUMS

    def value(typ: str, v: Any, where: str) -> None:
        if v is None and typ in NULLABLE_DSL_ENUMS:
            return
        if typ in enums:
            if not (isinstance(v, list) and v and isinstance(v[0], str)):
                probs.append(f"{where}: {typ} 需要构造 [名, …]，得到 {v!r:.60}")
                return
            ctor = v[0]
            if ctor not in enums[typ]:
                probs.append(f"{where}: {typ}.{ctor} 不在白名单")
                return
            args = enums[typ][ctor]
            if len(v) - 1 != len(args):
                probs.append(f"{where}: {typ}.{ctor} 参数 {len(v) - 1} != {len(args)}")
                return
            for i, (t, x) in enumerate(zip(args, v[1:])):
                value(t, x, f"{where}.{ctor}[{i}]")
        elif typ == "ActionDslExpression" and v is not None:     # 官方 44 处可空表达式（如召唤球回调）
            expr(v, where)

    def expr(node: Any, where: str) -> None:
        if not (isinstance(node, list) and node and node[0] in ("Block", "Command", "Event")):
            probs.append(f"{where}: 不是 Block/Command/Event：{node!r:.60}")
            return
        if node[0] == "Block":
            for i, child in enumerate(node[1]):
                expr(child, f"{where}/{i}")
            return
        table = SIG.COMMANDS if node[0] == "Command" else SIG.EVENTS
        name, params = node[1][0], node[1][1:]
        if name not in table:
            probs.append(f"{where}: 未知 {node[0]} {name}")
            return
        sig = table[name]
        if sig is None:
            sig = {"Wait": ["int", "String", "ActionDslExpression"]}.get(name)
            if sig is None:
                return
        if len(params) != len(sig):
            probs.append(f"{where}: {name} 参数 {len(params)} != {len(sig)}")
            return
        for i, (t, x) in enumerate(zip(sig, params)):
            if name == "CreateCondition" and i == 1:
                for j, acv in enumerate(x):
                    value("AdditionalConditionKind", acv, f"{where}:{name}.ac{j}")
            else:
                value(t, x, f"{where}:{name}[{i}]")

    _require(isinstance(tree, list) and tree[0] == "ActionDsl" and len(tree) == 12, "DSL 根形状不对")
    expr(tree[11], "root")
    return probs
