#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""只读采集 boss ESDL 引用的 action DSL，并输出归一化 CreateCondition 素材卡。

示例：
  python mod-tools/wf_boss_buff_harvest.py chapter12_boss_story --level 80
  python mod-tools/wf_boss_buff_harvest.py chapter12_boss_main \
    --esdl battle/enemy/boss/chapter12_boss_main.esdl.amf3.deflate \
    --output mod-tools/work/codex_out/chapter12-buffs.json

注意双重扩展名：enemy DSL 是 ``.esdl.amf3.deflate``，action DSL 是
``.action.dsl.amf3.deflate``。本工具默认只写 stdout；只有显式 ``--output`` 才落盘。
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
import re
import sys
import zlib
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wf_dsl  # noqa: E402
import wf_quest_lib as q  # noqa: E402

STANDARD_BOSS = "master/battle/boss/standard_boss.orderedmap"
ACTION_PREFIX_RE = re.compile(r"^battle/action/enemy/action/.+\$$")
ACTION_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")
KNOWN_VALUE_CONSTRUCTORS = {
    "ACAttackPoint",
    "ACAbilityDamageResistance",
    "ACDirectAttackDamageResistance",
    "ACPowerFlipDamageResistance",
    "ACSkillDamageResistance",
    "ACToleranceOfDebuff",
}


def _physical(store_root: Path, logical: str) -> Path:
    return Path(store_root) / q.hashed_rel(logical)


def _load_raw_deflate_dsl(path: Path, logical: str) -> Any:
    try:
        unpacked = zlib.decompress(path.read_bytes(), -15)
    except zlib.error as exc:
        raise ValueError(f"{logical} 不是 raw-deflate DSL") from exc
    parsed = wf_dsl.parse_dsl(unpacked)
    if "tree" not in parsed:
        raise ValueError(f"{logical} 解析结果缺少 tree")
    return parsed["tree"]


def _strings(node: Any) -> Iterable[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for child in node:
            yield from _strings(child)
    elif isinstance(node, dict):
        for child in node.values():
            yield from _strings(child)


def _commands(node: Any) -> Iterable[list]:
    if isinstance(node, list):
        if (len(node) == 2 and node[0] == "Command"
                and isinstance(node[1], list) and node[1]):
            yield node[1]
        for child in node:
            yield from _commands(child)
    elif isinstance(node, dict):
        for child in node.values():
            yield from _commands(child)


def _slv_value(value: Any) -> Any:
    """将单值 SLV 压成标量，范围 SLV 保留 min/max。"""
    if (isinstance(value, list) and len(value) == 1
            and isinstance(value[0], dict)
            and set(value[0]) >= {"min", "max"}):
        lo, hi = value[0]["min"], value[0]["max"]
        return lo if lo == hi else {"min": lo, "max": hi}
    if isinstance(value, list):
        return [_slv_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _slv_value(v) for k, v in sorted(value.items())}
    return value


def _card_from(command: list, ac: list) -> dict:
    if len(command) < 13 or command[0] != "CreateCondition":
        raise ValueError(f"CreateCondition 参数形状非法:{command!r}")
    if not ac or not isinstance(ac[0], str):
        raise ValueError(f"AdditionalConditionKind 形状非法:{ac!r}")
    constructor = ac[0]
    card = {
        "constructor": constructor,
        "params": _slv_value(ac[1:]),
        "subjects": [int(command[1])],
        "hit_rate": _slv_value(command[3]),
        "hit_effect": command[4][0] if isinstance(command[4], list) and command[4]
                      else _slv_value(command[4]),
        "cancelable": bool(command[5]),
        # ActionEvaluator.as:3288-3308: true 跳过相同 CreateCondition 的 hash 去重；
        # 终始之龙重复 99/90/... 次时必须为 true 才能真的逐次累积。
        "allow_same_frame_reapply": bool(command[6]),
        "discrimination_key": str(command[7]),
        "invisible": bool(command[9]),
        "target_kind": int(command[10]),
        "application_magnification": _slv_value(command[11]),
    }
    if len(ac) >= 2:
        card["duration"] = _slv_value(ac[1])
    if constructor == "ACToleranceOfElement" and len(ac) >= 5:
        card["element"] = int(ac[2])
        card["strength"] = _slv_value(ac[3])
        card["max_accumulation"] = _slv_value(ac[4])
    elif constructor in KNOWN_VALUE_CONSTRUCTORS and len(ac) >= 4:
        card["strength"] = _slv_value(ac[2])
        card["max_accumulation"] = _slv_value(ac[3])
    return card


def _card_identity(card: dict) -> str:
    identity = {k: v for k, v in card.items()
                if k not in {"subjects", "count", "actions"}}
    return json.dumps(identity, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def _normalize_esdl(logical: str) -> str:
    logical = str(logical).replace("\\", "/").lstrip("/")
    if logical.endswith(".esdl.amf3.deflate"):
        return logical
    if logical.endswith(".esdl"):
        return logical + ".amf3.deflate"
    return logical + ".esdl.amf3.deflate"


def _csv_cells(row: str | bytes) -> list[str]:
    text = row.decode("utf-8") if isinstance(row, bytes) else str(row)
    return next(csv.reader(io.StringIO(text)))


def resolve_esdl_logicals(boss_code: str, *, store_root: Path,
                          esdl_logical: str | None = None,
                          level: int | None = None) -> list[str]:
    """将资源名或 standard_boss 代号解析成真实 enemy DSL 逻辑名。"""
    store_root = Path(store_root)
    if esdl_logical:
        logical = _normalize_esdl(esdl_logical)
        if not _physical(store_root, logical).is_file():
            raise FileNotFoundError(f"ESDL 不存在:{logical}")
        return [logical]

    raw = str(boss_code).replace("\\", "/").lstrip("/")
    direct = (_normalize_esdl(raw) if raw.startswith("battle/")
              else _normalize_esdl(f"battle/enemy/boss/{raw}"))
    found: list[str] = []
    if _physical(store_root, direct).is_file():
        found.append(direct)

    table_path = _physical(store_root, STANDARD_BOSS)
    if table_path.is_file():
        table = q.load_table(STANDARD_BOSS, path=table_path)
        node = table.get(str(boss_code))
        if isinstance(node, dict):
            rows: list[tuple[int, str | bytes]] = sorted(
                (int(k), v) for k, v in node.items() if str(k).isdigit())
            if level is not None:
                rows = [row for row in rows if row[0] >= int(level)][:1]
                if not rows:
                    raise ValueError(
                        f"{boss_code} standard_boss 无 >=lv{level} 的 ESDL 档")
            for _selected, row in rows:
                cells = _csv_cells(row)
                if len(cells) >= 2 and cells[1].strip():
                    logical = _normalize_esdl(cells[1].strip())
                    if _physical(store_root, logical).is_file() and logical not in found:
                        found.append(logical)
    if not found:
        raise FileNotFoundError(
            f"找不到 boss {boss_code} 的 .esdl.amf3.deflate；可用 --esdl 显式指定")
    return found


def _discover_action_logicals(tree: Any, store_root: Path) -> list[tuple[str, str]]:
    values = sorted(set(_strings(tree)))
    prefixes = sorted(v for v in values if ACTION_PREFIX_RE.fullmatch(v))
    if not prefixes:
        raise ValueError("ESDL 中没有 battle/action/...$ action 前缀")
    names = sorted(v for v in values if ACTION_NAME_RE.fullmatch(v))
    found: list[tuple[str, str]] = []
    for prefix in prefixes:
        for name in names:
            logical = prefix + name + ".action.dsl.amf3.deflate"
            if _physical(store_root, logical).is_file():
                found.append((name, logical))
    # 同一动作名可能在 ESDL 多处出现；只按完整逻辑名去重，保持确定顺序。
    return list(dict.fromkeys(found))


def harvest_boss(boss_code: str, *, store_root: Path,
                 esdl_logical: str | None = None,
                 level: int | None = None) -> dict:
    """只读采集一个 boss，返回可直接 json.dump 的确定性报告。"""
    store_root = Path(store_root).resolve()
    esdls = resolve_esdl_logicals(
        boss_code, store_root=store_root,
        esdl_logical=esdl_logical, level=level)
    actions_by_logical: dict[str, tuple[str, Any]] = {}
    esdl_hashes: dict[str, str] = {}
    for logical in esdls:
        path = _physical(store_root, logical)
        esdl_hashes[logical] = hashlib.sha256(path.read_bytes()).hexdigest()
        tree = _load_raw_deflate_dsl(path, logical)
        for name, action_logical in _discover_action_logicals(tree, store_root):
            if action_logical not in actions_by_logical:
                action_path = _physical(store_root, action_logical)
                actions_by_logical[action_logical] = (
                    name, _load_raw_deflate_dsl(action_path, action_logical))

    aggregate: dict[str, dict] = {}
    action_rows: list[dict] = []
    for logical, (name, tree) in sorted(actions_by_logical.items()):
        counts = collections.Counter()
        create_count = 0
        for command in _commands(tree):
            counts[str(command[0])] += 1
            if command[0] != "CreateCondition":
                continue
            create_count += 1
            acs = command[2] if len(command) > 2 else None
            if not isinstance(acs, list):
                raise ValueError(f"{logical} CreateCondition conditions 不是数组")
            for ac in acs:
                card = _card_from(command, ac)
                key = _card_identity(card)
                if key not in aggregate:
                    aggregate[key] = dict(card, count=0, actions={})
                row = aggregate[key]
                row["count"] += 1
                row["actions"][name] = row["actions"].get(name, 0) + 1
                row["subjects"] = sorted(set(row["subjects"] + card["subjects"]))
        action_rows.append({
            "name": name,
            "logical": logical,
            "command_counts": dict(sorted(counts.items())),
            "create_condition_count": create_count,
        })

    cards = sorted(aggregate.values(), key=lambda card: (
        str(card["constructor"]),
        json.dumps(card["params"], ensure_ascii=False, sort_keys=True),
        str(card["subjects"]),
    ))
    return {
        "schema_version": 1,
        "boss_code": str(boss_code),
        "level": int(level) if level is not None else None,
        "sources": {"esdl": esdls, "sha256": esdl_hashes},
        "actions": action_rows,
        "cards": cards,
    }


def render_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def _default_store() -> Path:
    # wf_quest_lib 的解析链是本仓统一入口；这里只读，不创建目录。
    return q._store_base()  # noqa: SLF001 - 同目录工具共享内部 store resolver


def main(argv: list[str] | None = None) -> int:
    # stdout 是 JSON API；Windows 默认代码页（如 GBK）会让下游按 UTF-8 读取失败。
    # 显式输出文件本来就是 UTF-8，这里把 stdout/stderr 也统一成同一契约。
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="只读采集 boss ESDL/action DSL 的归一化 CreateCondition 素材卡")
    parser.add_argument("boss", help="standard_boss 代号或 battle/enemy/boss 下的资源名")
    parser.add_argument("--level", type=int, help="standard_boss 按首个 >=level 的档取资源")
    parser.add_argument("--esdl", help="显式 enemy DSL 逻辑名")
    parser.add_argument("--store", type=Path, help="显式 store 根；默认走 profiles/WF_TARGET_STORE")
    parser.add_argument("-o", "--output", type=Path,
                        help="输出 JSON 文件；省略时只打印 stdout")
    args = parser.parse_args(argv)
    try:
        report = harvest_boss(
            args.boss, store_root=(args.store or _default_store()),
            esdl_logical=args.esdl, level=args.level)
        text = render_json(report)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
            print(f"[OK] {len(report['actions'])} actions / "
                  f"{len(report['cards'])} cards -> {args.output}")
        else:
            sys.stdout.write(text)
        return 0
    except (OSError, TypeError, ValueError, zlib.error) as exc:
        print(f"[ERR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
