"""Explain skill-tier dependencies without pretending to inspect player saves."""
from __future__ import annotations

from wf.balance.rows import split_leaf
from wf.rules.catalog import result

MANA_NODE = "master/mana_board/mana_node.orderedmap"
AWAKE_EVENT = "master/mission/character_awake_event.orderedmap"


def _leaves(node, path=()):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _leaves(value, (*path, key))
    elif isinstance(node, str):
        for index, row in enumerate(split_leaf(node, "mana_node")):
            yield path, index, row
    else:
        raise ValueError("技能等级引用表包含无法解析的节点")


def tier_reference_check(state, key, owners, before_count, after_count, operation):
    """The client selects a tier by evolution, independently of numerical SLv.

    GeneralCharacterLogic._getActionSkillEvolution starts at 1, counts learned
    c5=2 mana nodes at the current awakening level, then adds that awakening
    level. c5=1 nodes affect SLv instead; list both to make the distinction clear.
    """
    sources, unavailable = {}, []
    for logical in (MANA_NODE, AWAKE_EVENT):
        try:
            sources[logical] = state.table(logical)
        except (KeyError, FileNotFoundError):
            sources[logical] = {}
            unavailable.append(logical)
    references, required_tiers = [], {}
    for cid in sorted(owners):
        references.append({"kind": "default", "character": cid, "level": 1,
                           "source": "GeneralCharacterLogic._getActionSkillEvolution",
                           "message": "默认档位 1；默认 SLv 1，二者独立"})
        skill_nodes = []
        for path, index, row in _leaves(sources[MANA_NODE].get(cid, {}), (cid,)):
            if len(row) < 7:
                raise ValueError(f"{MANA_NODE}/{'/'.join(path)}: 玛纳节点不足 7 列")
            if row[1] != "0" or row[5] not in {"1", "2"}:
                continue
            ref = {"kind": "mana_skill_level" if row[5] == "1" else "mana_skill_evolution",
                   "character": cid, "source": MANA_NODE, "path": list(path), "row": index,
                   "nodeId": row[0], "effectColumn": 5, "effect": row[5],
                   "message": "技能 SLv 强化（不直接索引档位）" if row[5] == "1" else "技能进化档位 +1"}
            references.append(ref)
            if row[5] == "2":
                skill_nodes.append(ref)
        # With no awakened nodes the client counts every learned evolution node.
        required_tiers[cid] = 1 + len(skill_nodes)
        references.append({"kind": "awakening", "character": cid,
                           "source": "GeneralCharacterLogic.getAwakeLevelByManaNodes",
                           "eventSource": AWAKE_EVENT, "event": sources[AWAKE_EVENT].get(cid),
                           "nodes": [{"path": ref["path"], "nodeId": ref["nodeId"]} for ref in skill_nodes],
                           "message": "觉醒档位读取技能进化节点的 awakeLevel；玩家已学节点和觉醒等级未读取"})
    description = "；".join(
        f"{ref['character']} {ref['kind']} " +
        ("/".join(ref["path"]) if "path" in ref else ref["message"])
        for ref in references)
    return result("ability.skill-tier-references", "待验证",
                  f"技能 {key} 档位 {before_count}→{after_count}（{operation}）；核对全部等级引用：{description}",
                  key=key, beforeCount=before_count, afterCount=after_count,
                  references=references, unavailableSources=unavailable,
                  maxUnawakenedTier=required_tiers,
                  missingUnawakenedTiers={cid: list(range(after_count + 1, tier + 1))
                                          for cid, tier in required_tiers.items() if tier > after_count},
                  runtime="未执行", coverage="引用表缺失" if unavailable else "当前视图全部所有者的玛纳节点；玩家状态未读取")
