"""Apply pure variant rules inside the existing clone transaction, before any writes."""
from __future__ import annotations

import re

import wf_quest_lib as codec
from wf.balance.rows import join_leaf, split_leaf
from wf.text.edit import _encode

from .ability_engine import describe, EditState
from .character_clone import clone
from .clone_tables import T
from .deliver_media import tree, encode_tree
from .drafts import DraftError, sha256
from .variant_rules import CROSS_ELEMENT, ZONES, transform_row, transform_skill, remove_main_restriction


def _rewrite(client, logical, document):
    original = client[logical]
    client[logical] = _encode(original, codec.parse_node(original), document)


def transformer(source, spec, zone, store, server_dir=None):
    def apply(client, tables, assets, inputs, checks):
        from .ids import collect_occupancy, check_id
        from .clone_ids import draft_keys
        changes, manual, string_ids = [], [], []
        occupancy = collect_occupancy(source, store.root, server_dir)
        _, reserved_paths = draft_keys(store)
        cid = spec["to"]
        for table, logical, keys in (("ability", T.ABILITY, [cid + str(i) for i in range(1, 7)]),
                                     ("leader_ability", T.LEADER, [cid])):
            if logical not in client:
                continue
            document = codec.parse_node(client[logical])
            for key in keys:
                if key not in document:
                    continue
                before_rows = split_leaf(document[key], table)
                after_rows = []
                protected = any(r[0].startswith("wfx_") for r in before_rows)
                for i, before in enumerate(before_rows):
                    after, reasons = transform_row(before, table, zone)
                    if protected:
                        after, reasons = list(before), ["扩展文本键可能参与客户端机制分派，不能自动改写身份或效果"]
                    if not protected:
                        after = remove_main_restriction(after, table)
                    manual.extend({"table": table, "key": key, "row": i + 1, "reason": reason} for reason in reasons)
                    after_rows.append(after)
                if after_rows != before_rows:
                    sid = f"{spec['code']}_{key}"
                    for identity in (sid, "desc_override_" + sid):
                        if not check_id(source, "string_id", identity, occupancy=occupancy)["available"]:
                            raise DraftError(f"变体文本键已占用：{identity}")
                    string_ids.extend([sid, "desc_override_" + sid])
                    for after in after_rows:
                        after[0] = sid
                    custom = source.table("strings")
                    if any(custom.get(r[0]) or custom.get("desc_override_" + r[0]) for r in before_rows):
                        manual.append({"table": table, "key": key, "row": 1, "textKey": "desc_override_" + sid,
                                       "reason": "母本包含自定义覆盖文案，请在文案页为独立文本键同步描述"})
                for i, (before, after) in enumerate(zip(before_rows, after_rows)):
                    if after != before:
                        changes.append({"table": table, "key": key, "row": i + 1,
                            "beforeDescription": describe(before, table), "afterDescription": describe(after, table),
                            "cells": [{"column": n, "old": a, "new": b} for n, (a, b) in enumerate(zip(before, after)) if a != b]})
                leaf = join_leaf(document[key], after_rows)
                EditState(source).validate_rows(table, key, leaf)
                document[key] = leaf
            _rewrite(client, logical, document)
        # Clone main skill programs to independent paths; never change a donor DSL in place.
        action = codec.parse_node(client[T.ACTION])
        programs = {}
        for level, leaf in action[spec["code"]].items():
            rows = split_leaf(leaf, "action_skill")
            if len(rows) != 1 or len(rows[0]) <= 7 or not rows[0][7]:
                manual.append({"table": "action_skill", "key": level, "reason": "主技能程序路径不明确"})
                continue
            row = rows[0]
            logical = row[7] + ".action.dsl.amf3.deflate"
            raw = source.raw(logical)
            if raw is None:
                manual.append({"table": "action_skill", "key": level, "reason": "技能 DSL 缺失"})
                continue
            before = tree(raw)
            after, reasons = transform_skill(before, zone)
            # Program indirections require closure analysis; preserve rather than guess.
            def refs(node):
                if isinstance(node, str):
                    return [node] if node.startswith("battle/action/") else []
                if isinstance(node, (list, dict)):
                    return [r for v in (node.values() if isinstance(node, dict) else node) for r in refs(v)]
                return []
            if refs(before):
                reasons.append("技能引用外部动作程序，乘区效果闭包需人工核对")
            manual.extend({"table": "action_skill", "key": level, "reason": r} for r in reasons)
            inputs[f"common:{logical}"] = sha256(raw)
            if after != before:
                path = f"battle/action/skill/{spec['code']}_variant_{level}"
                target = path + ".action.dsl.amf3.deflate"
                if source.raw(target) is not None or target in reserved_paths:
                    raise DraftError("目标技能程序路径已经存在")
                assets["common", target] = encode_tree(after)
                programs[level] = target
                row[7] = path
                changes.append({"table": "skill_dsl", "key": level, "beforeDescription": "原技能限时伤害加成",
                                "afterDescription": f"{ZONES[zone][0]}限时加成；时长、强度、次数不变"})
                # Existing action text is retained for manual review, never silently presented as updated.
                manual.append({"table": "action_skill", "key": level, "skillText": row[1],
                               "reason": "技能效果已转换，请在文案页同步该档技能描述后交付"})
                action[spec["code"]][level] = join_leaf(leaf, [row])
        _rewrite(client, T.ACTION, action)
        for item in manual:
            checks.append({"level": "warn", "code": "variant.manual", "message": item["reason"]})
        if manual:
            checks.append({"level": "error", "code": "variant.incomplete", "message": "变体有需人工条目，只能保存草稿，生成交付被阻断"})
        return {"rule": "zone", "zone": zone, "changes": changes, "manual": manual,
                "programs": programs, "stringIds": string_ids}
    return apply


def variant_spec(source, body, target):
    if not isinstance(body, dict) or body.get("rule") not in ("zone", "element"):
        raise DraftError("规则必须是 zone 或 element")
    cid = body.get("from")
    donor = source.table("character").get(cid)
    if not donor:
        raise DraftError("母本角色不存在")
    if not isinstance(target, dict) or set(target) - {"to", "code", "zone", "element"}:
        raise DraftError("变体目标字段不合法")
    if body["rule"] == "element":
        raise DraftError(CROSS_ELEMENT)
    zone = target.get("zone")
    if zone not in ZONES:
        raise DraftError("目标乘区不合法")
    to = target.get("to")
    if not isinstance(to, str) or not re.fullmatch(r"[1-9]\d{0,8}", to):
        raise DraftError("目标 ID 必须为 1–9 位正整数")
    if target.get("element", int(donor[0][3])) != int(donor[0][3]):
        raise DraftError(CROSS_ELEMENT)
    texts = source.table("text").get(cid)
    name = texts[0][0] if texts else cid
    suffix, number = ZONES[zone]
    return {"from": cid, "to": to, "code": target.get("code") or f"variant_{cid}_{to}",
            "name": f"{name}・乘区{number}{suffix}", "skill": "copy"}, zone


def run_variant(ops, body, target, *, preview=True, server_dir=None):
    spec, zone = variant_spec(ops.source, body, target)
    return clone(ops, spec, preview=preview, server_dir=server_dir,
                 transform=transformer(ops.source, spec, zone, ops.store, server_dir))
