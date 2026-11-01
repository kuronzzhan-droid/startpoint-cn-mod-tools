"""Source-evidenced multiplayer hints for decoded client DSL and selected rows."""
from __future__ import annotations

import hashlib
import json

from wf.boss.esdl import ROOT_TYPE, _TYPES
from .catalog import result

_ENEMY = "pinball/scene/battle/battle/enemy/"
_SCRIPT = "pinball/common/data/battle/script/"
_ACTION = "pinball/scene/battle/battle/action/"
_STANDARD = "pinball.scene.battle.battle.enemy.standard."
_EXPRESSION = "pinball.common.data.battle.script.BattleScriptExpression"
_STATE_TABLES = {
    "general_boss_state.orderedmap": "GeneralBossStateValues",
    "general_funnel_state.orderedmap": "GeneralFunnelStateValues",
    "general_zako_state.orderedmap": "GeneralZakoStateValues",
}
BASIS = (
    "官方基线也会命中；这些是非阻断静态复核点，优先检查与草稿改动相关的新增或变化。"
    "状态选择使用共享基种及同步计数，不等同本机独立随机。"
    "synchronization=false 仅不在该次切换主动发包，不能据此认定状态未同步；"
    "SetVariableValue 的值可进入 EnemySync，因此不按赋值构造报警。"
    f"依据：{_ENEMY}GeneralEnemyStateChooser.as:30,54-57；"
    f"{_ENEMY}EnemyImpl.as:4550-4552,4573-4575；"
    f"{_ENEMY}GeneralEnemy.as:4523-4525,6647-6648。静态命中不能替代三开联机验证。"
)
_SEEDED = (
    f"{_ENEMY}GeneralEnemy.as:1580-1582,5587-5636；"
    f"{_ENEMY}GeneralEnemyStateChooser.as:30,54-62；"
    "pinball/scene/battle/battle/Battle.as:1172；"
    "pinball/scene/battle/battle/random/RandomSeedFactoryImpl.as:21-22,35-42"
)
_STATE_MESSAGE = ("状态转移有多个候选，使用共享基种/敌人地址/同步计数的随机序列；"
                  "官方配置也使用此机制。改动候选、权重或调用次数/顺序时需复核，不能仅凭命中认定分叉。")
_LOCAL_SOURCE = (
    "pinball/battle/action/dsl/ActionDslCommand.as:212-214,462-464；"
    f"{_ACTION}ActionEvaluator.as:4940-5016；{_ACTION}ActionManagerImpl.as:154-159；"
    "pinball/scene/battle/battle/Battle.as:1172；"
    "pinball/scene/battle/battle/random/RandomSeedFactoryImpl.as:21-32"
)


def _walk(node, path=""):
    yield path, node
    values = node.items() if isinstance(node, dict) else enumerate(node) if isinstance(node, list) else ()
    for key, value in values:
        escaped = str(key).replace("~", "~0").replace("/", "~1")
        yield from _walk(value, path + "/" + escaped)


def _typed(node, typename=ROOT_TYPE, path=""):
    """Use the existing client schema so unrelated one-letter enums never match."""
    if node is None:
        return
    info = _TYPES.get(typename, {})
    yield path, node, typename
    kind = info.get("kind")
    if kind == "ABSTRACT":
        yield from _typed(node, info["item"], path)
    elif kind == "COLLECTION" and isinstance(node, list):
        for index, item in enumerate(node):
            yield from _typed(item, info["item"], f"{path}/{index}")
    elif kind in {"MAP", "DYNAMIC_ACCESS"} and isinstance(node, dict):
        for key, item in node.items():
            yield from _typed(item, info["item"], f"{path}/{key}")
    elif kind == "ANONYMOUS":
        fields = info["fields"]
        values = enumerate(node) if info["array"] and isinstance(node, list) else node.items() if isinstance(node, dict) else ()
        for key, item in values:
            field = info["order"][key] if info["array"] else key
            if field in fields:
                yield from _typed(item, fields[field], f"{path}/{key}")
    elif kind == "ENUM" and isinstance(node, list) and node and isinstance(node[0], str):
        index = info["constructors"].get(node[0])
        for arg, argtype in enumerate(info["arguments"].get(str(index), []), 1):
            if arg < len(node):
                yield from _typed(node[arg], argtype, f"{path}/{arg}")


def _multiple(values):
    return isinstance(values, list) and len({json.dumps(v, sort_keys=True) for v in values}) > 1


def _script(node, typename=_EXPRESSION):
    """Table JSON uses enum indexes; EnemyDsl wire uses separate short aliases.

    boot_ffc6.as:1292-1295 sets useEnumIndex; DataConcreter.as:245-284
    resolves each argument by its declared type, never by arbitrary integers.
    """
    if node is None:
        return None
    info = _TYPES[typename]
    kind = info["kind"]
    if kind == "ABSTRACT":
        return _script(node, info["item"])
    if kind == "COLLECTION":
        if not isinstance(node, list):
            raise ValueError(f"{typename} requires array")
        return [_script(item, info["item"]) for item in node]
    if kind != "ENUM":
        return node
    if not isinstance(node, list) or not node:
        raise ValueError(f"{typename} requires constructor array")
    if type(node[0]) is int:
        name = next((name for name, index in info["constructors"].items() if index == node[0]), None)
    else:
        aliases = {alias: name for name, alias in info["aliases"].items()}
        name = aliases.get(node[0], node[0]) if isinstance(node[0], str) else None
    if name not in info["constructors"]:
        raise ValueError(f"unknown {typename} constructor: {node[0]}")
    arguments = info["arguments"][str(info["constructors"][name])]
    if len(node) != len(arguments) + 1:
        raise ValueError(f"{typename}/{name}: incorrect argument count")
    return [name, *[_script(value, arg) for value, arg in zip(node[1:], arguments)]]


def _standard(tree, emit, *, typename=ROOT_TYPE, path=""):
    for here, node, kind in _typed(tree, typename, path):
        if kind == _STANDARD + "Transition" and isinstance(node, list) and len(node) == 2:
            values = [item.get("state") for item in node[1]] if node[0] == "D" else node[1]
            if _multiple(values):
                emit("state_random", here, _STATE_MESSAGE, node,
                     f"{_ENEMY}standard/Transition.as:29-47；" + _SEEDED)
        elif kind == _STANDARD + "NextState" and isinstance(node, list) and node:
            for index in (1,) if node[0] == "Always" else (1, 2):
                if len(node) > index and _multiple(node[index]):
                    emit("state_random", f"{here}/{index}", _STATE_MESSAGE, node[index],
                         f"{_ENEMY}standard/NextState.as:29-31,79-81；" + _SEEDED)
            if node[0] == "GeneralFunnelDead":
                emit("death_event", here, "GeneralFunnelDead 根据漏斗存活查询选择分支；改动召唤、消失或死亡时序时需联机复核。",
                     node, f"{_ENEMY}standard/NextState.as:79-81；{_ENEMY}GeneralEnemy.as:1453,3109-3125")
        elif kind == _STANDARD + "FormEvent" and isinstance(node, dict) and node.get("kind") == ["SomebodyDead"]:
            emit("death_event", here, "SomebodyDead 触发表单死亡事件；事件队列按成员死亡序号去重，executedDeadEvents 随 EnemySync 同步。改动事件副作用或执行时序时需复核。",
                 node, f"{_ENEMY}standard/FormEventKind.as:10-12；{_ENEMY}GeneralEnemy.as:663-709,2214-2237,4332,6647")
        elif (kind == _STANDARD + "WatchContent" and isinstance(node, list) and len(node) == 3
              and node[0] == "ChangeState" and _multiple(node[1])):
            emit("state_random", here, _STATE_MESSAGE, node,
                 f"{_ENEMY}standard/WatchContent.as:30-32；{_ENEMY}GeneralEnemy.as:6782-6800,6953-6955；" + _SEEDED)
        elif kind == _EXPRESSION and isinstance(node, list) and len(node) == 3 and node[:2] == ["FunctionCall", ["GetFunnelDeadCount"]]:
            emit("death_event", here, "GetFunnelDeadCount 对漏斗死亡计数表达式求和；改动死亡计数依赖或触发时序时需复核。",
                 node, f"{_SCRIPT}IntrinsicFunction.as:24；{_SCRIPT}BattleScriptEvaluator.as:151-160；"
                 f"{_ENEMY}GeneralEnemy.as:1944-1957")


def _table(tree, logical, emit, incomplete):
    parser = _STATE_TABLES.get(logical.rsplit("/", 1)[-1])
    state = parser is not None
    source = f"pinball/master/generated/{parser}.as:261-293,384-450,777-833,1400-1500"
    for path, row in _walk(tree):
        if not isinstance(row, list) or not row or not all(isinstance(v, str) for v in row):
            continue
        cell = lambda index: row[index] if index < len(row) else ""
        if state:
            columns = [40, 41, 42, 43]
            if cell(16) not in {"", "(None)"}:
                columns.append(21)
            if cell(22) not in {"", "(None)"}:
                columns.append(26)
            if cell(29) not in {"", "(None)"}:
                # Backtrack constructors consume only the alternate/fallback c32.
                if cell(29) not in {"11", "18"}:
                    columns.append(31)
                if cell(29) != "0":
                    columns.append(32)
            scripts = [27, 28] + ([30] if cell(29) == "10" else [])
            if cell(29) == "17":
                emit("death_event", f"{path}/29", "状态表的 GeneralFunnelDead 条件依赖漏斗存活；改动召唤、消失或死亡时序时需复核。",
                     row[29:33], source + f"；{_ENEMY}GeneralEnemy.as:1453,3109-3125")
        else:
            columns = [15] if cell(14) == "0" else []
            scripts = ([8] if cell(7) == "7" else []) + ([22] if cell(14) == "3" else [])
            source = "pinball/master/generated/GeneralEnemyWatchValues.as:225,329-379,390-392"
        for column in columns:
            values = cell(column).split(",")
            if _multiple(values):
                emit("state_random", f"{path}/{column}", _STATE_MESSAGE, values,
                     source + f"；{_ENEMY}GeneralEnemy.as:6782-6800,6953-6955；" + _SEEDED)
        for column in scripts:
            value = cell(column)
            if value and value != "(None)":
                # The client parses these cells as typed JSON, never arbitrary text.
                try:
                    expression = _script(json.loads(value))
                    _standard(expression, emit, typename=_EXPRESSION, path=f"{path}/{column}")
                except Exception as exc:  # noqa: BLE001 - one bad cell must not discard other rows.
                    incomplete(f"{path}/{column}", exc)


def scan_tree(tree, logical):
    """Return individual evidenced hits; callers aggregate and compare baselines."""
    hits = []

    def emit(kind, path, message, construct, source):
        fingerprint = hashlib.sha256(json.dumps(construct, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
        hits.append(result("multiplayer." + kind, "待验证", message, category="联机风险",
                           location=f"{logical}#{path or '/'}", logical=logical, source=source,
                           fingerprint=fingerprint, evidence_nature="源码推断"))

    def incomplete(path, exc):
        location = f"{logical}#{path}"
        reason = f"{location}: {type(exc).__name__}: {exc}"
        hits.append(result("multiplayer.incomplete", "待验证", "联机风险扫描不完整：" + reason,
                           category="联机风险", location=location, logical=logical, issues=[reason],
                           source="boot_ffc6.as:1292-1295；typepacker/core/DataConcreter.as:245-284"))

    if logical.rsplit("/", 1)[-1] in {*_STATE_TABLES, "general_enemy_watch.orderedmap"}:
        _table(tree, logical, emit, incomplete)
    elif isinstance(tree, dict) and "forms" in tree:
        _standard(tree, emit)
    else:
        for path, node in _walk(tree):
            if (isinstance(node, list) and len(node) == 2 and node[0] == "Command"
                    and isinstance(node[1], list) and len(node[1]) == 2
                    and node[1][0] == "ConditionalsProbability"):
                emit("random", path + "/1", "ConditionalsProbability 使用本机 battle ID 派生的独立随机流选择动作分支；官方动作也可能使用。改动分支副作用时需检查各端一致性。",
                     node[1], _LOCAL_SOURCE)
    return hits
