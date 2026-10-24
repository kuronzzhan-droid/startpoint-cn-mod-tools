# -*- coding: utf-8 -*-
"""给五重决战补 boss_battle_stage_node 的 99 号节点,并解开它的前置门。

## 为什么模式没入口
客户端的领主战列表是**枚举 stage_node 的键集**建出来的,不是枚举 quest:
  BossBattleChapterLogic.as:36-49  BossBattleStageNodeTable.get_data().get(1).keys()
                                   每个键 K 变成节点 id 1000*1+K
  BossBattleStageNodeLogic.getQuestIds()  才去读 boss_battle_quest[1][id%1000]
1.4.665 那批只投了 6 张表,`boss_battle_quest[1][99]` 有了(1099001/2/3),
但 `boss_battle_stage_node[1][99]` 没有 —— 没有节点就没有格子,不报错也不崩,
就是**列表里少一格**。该文件 mtime 停在 2026-06-24,整轮施工从没碰过它。

## 第二道门
`boss_battle_quest[1][99][1]` 的 c7-c11 是 `['2','1','1','2','1001002']`,
从 1001003 抄来的发布条件 —— 意思是「打通领主战 1001002 之后才可见」。
官方 1001001 的写法是 `'(None)','','','','(None)'`(无条件可见),改成那个。

两处都做行级增改,不整表覆盖;写完逐层解回来比对。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import zlib
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[3]  # 仓库根（本文件在 wf/tools/<组>/ 下）
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core  # noqa: E402
import wf_offline_pack_apply as apply_tool  # noqa: E402
import wf_pixel_rescale as rescale  # noqa: E402

NODE_LOGICAL = "master/quest/boss_battle_stage_node.orderedmap"
QUEST_LOGICAL = "master/quest/boss_battle_quest.orderedmap"

# 14 列,逐列对照官方节点 1 / 70 / 71 定的:
#  0 大分类名  1 节点名  2 组id(1=boss_battle,该组 game_system_unlock=(None) 恒解锁)
#  3 bgm      4 保留    5 前置节点(空=无)  6 自身节点号
#  7-9 掉落预览道具  10 保留  11 缩略图  12 背景  13 website_event_data_id
#  c13 抄模板('1001'),**不要**写 1099 —— 官方 70/71 都是 '1000',它不跟节点号走。
NODE_99 = [
    "领主战", "五重决战", "1", "(None)", "(None)", "", "99",
    "10000143", "10000095", "10000096", "(None)",
    "quest/thumbnail/multi_battle/super_owl_2",
    "quest/boss_battle/background/boss_battle_owl",
    "1001",
]

# 官方 1001001 的无条件可见写法
OPEN_GATE = ("(None)", "", "", "", "(None)")
GATE_SLICE = slice(7, 12)


class NodeError(RuntimeError):
    pass


def _inner(blob: bytes):
    """内层 orderedmap;行是 zlib CSV。返回 (keys, [text])。"""
    keys, rows = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
        blob, label="inner", compressed_rows=False)
    out = []
    for row in rows:
        try:
            out.append(zlib.decompress(row).decode("utf-8"))
        except Exception:
            out.append(row.decode("utf-8", errors="replace"))
    return keys, out


def _inner_raw(blob: bytes):
    return core._strict_orderedmap_rows(  # type: ignore[attr-defined]
        blob, label="inner", compressed_rows=False)


def _build_inner(keys, raw_rows) -> bytes:
    return apply_tool.build_rows(keys, raw_rows, compressed=False)


def _csv(cells) -> bytes:
    return zlib.compress(core.write_csv_lines([list(cells)]).encode("utf-8"))


def add_node(root: Path, salt: str, apply: bool) -> dict:
    path = rescale.store_path(root, NODE_LOGICAL, salt)
    raw = path.read_bytes()
    outer_keys, outer_rows = apply_tool.read_rows(raw, "raw_outer", "node")
    if outer_keys != ["1"]:
        raise NodeError(f"外层键出乎意料: {outer_keys}")
    inner_keys, inner_raw = _inner_raw(outer_rows[0])
    if "99" in inner_keys:
        return {"table": NODE_LOGICAL, "action": "已存在", "changed": False}
    template_idx = inner_keys.index("1")
    template = core.read_csv_lines(zlib.decompress(inner_raw[template_idx]).decode("utf-8"))[0]
    if len(template) != len(NODE_99):
        raise NodeError(f"列数不符: 模板 {len(template)} vs 新行 {len(NODE_99)}")

    new_keys = list(inner_keys) + ["99"]
    new_raw = list(inner_raw) + [_csv(NODE_99)]
    merged_inner = _build_inner(new_keys, new_raw)
    out = apply_tool.build_rows(outer_keys, [merged_inner], compressed=False)

    # 逐层解回来比对
    ok2, or2 = apply_tool.read_rows(out, "raw_outer", "verify")
    ik2, ir2 = _inner_raw(or2[0])
    if ok2 != outer_keys:
        raise NodeError("外层键变了")
    if ik2 != new_keys:
        raise NodeError("内层键集不符")
    for k, before, after in zip(inner_keys, inner_raw, ir2):
        if before != after:
            raise NodeError(f"原有内层行 {k} 被改动")
    back = core.read_csv_lines(zlib.decompress(ir2[-1]).decode("utf-8"))[0]
    if back != NODE_99:
        raise NodeError(f"新行往返不一致: {back}")

    result = {"table": NODE_LOGICAL, "action": "新增 99",
              "inner_before": len(inner_keys), "inner_after": len(new_keys),
              "row": NODE_99, "changed": True, "applied": False}
    if apply:
        suffix = f".bak-fivebossnode-{time.strftime('%Y%m%d-%H%M%S')}"
        backup = path.with_name(path.name + suffix)
        if not backup.exists():
            backup.write_bytes(raw)
        path.write_bytes(out)
        result["applied"] = True
        result["backup_suffix"] = suffix
    return result


def open_gate(root: Path, salt: str, apply: bool) -> dict:
    path = rescale.store_path(root, QUEST_LOGICAL, salt)
    raw = path.read_bytes()
    outer_keys, outer_rows = apply_tool.read_rows(raw, "raw_outer", "quest")
    node_keys, node_raw = _inner_raw(outer_rows[0])
    if "99" not in node_keys:
        raise NodeError("boss_battle_quest 里没有 node 99")
    ni = node_keys.index("99")
    q_keys, q_raw = _inner_raw(node_raw[ni])
    qi = q_keys.index("1")
    cells = core.read_csv_lines(zlib.decompress(q_raw[qi]).decode("utf-8"))[0]
    before = tuple(cells[GATE_SLICE])
    if before == OPEN_GATE:
        return {"table": QUEST_LOGICAL, "action": "门已是开的", "changed": False}
    new_cells = list(cells)
    new_cells[GATE_SLICE] = list(OPEN_GATE)

    new_q_raw = list(q_raw)
    new_q_raw[qi] = _csv(new_cells)
    new_node_raw = list(node_raw)
    new_node_raw[ni] = _build_inner(q_keys, new_q_raw)
    out = apply_tool.build_rows(
        outer_keys, [_build_inner(node_keys, new_node_raw)], compressed=False)

    # 复核:只有 [99][1] 变了
    ok2, or2 = apply_tool.read_rows(out, "raw_outer", "verify")
    nk2, nr2 = _inner_raw(or2[0])
    if nk2 != node_keys:
        raise NodeError("node 键集变了")
    for k, a, b in zip(node_keys, node_raw, nr2):
        if k != "99" and a != b:
            raise NodeError(f"无关 node {k} 被改动")
    qk2, qr2 = _inner_raw(nr2[ni])
    if qk2 != q_keys:
        raise NodeError("quest 键集变了")
    for k, a, b in zip(q_keys, q_raw, qr2):
        if k != "1" and a != b:
            raise NodeError(f"无关 quest {k} 被改动")
    back = core.read_csv_lines(zlib.decompress(qr2[qi]).decode("utf-8"))[0]
    if back != new_cells:
        raise NodeError("改后行往返不一致")

    result = {"table": QUEST_LOGICAL, "action": "解开 1099001 前置门",
              "gate_before": list(before), "gate_after": list(OPEN_GATE),
              "changed": True, "applied": False}
    if apply:
        suffix = f".bak-fivebossnode-{time.strftime('%Y%m%d-%H%M%S')}"
        backup = path.with_name(path.name + suffix)
        if not backup.exists():
            backup.write_bytes(raw)
        path.write_bytes(out)
        result["applied"] = True
        result["backup_suffix"] = suffix
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--store",
                   default=r"弹国服/WorldFlipper/dummy/download/production/upload")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args(argv)
    salt = rescale.salt()
    root = Path(args.store)
    results = [add_node(root, salt, args.apply), open_gate(root, salt, args.apply)]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    changed = [r["table"] for r in results if r.get("changed")]
    if changed:
        print("\n需要发布:")
        print(",".join(changed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
