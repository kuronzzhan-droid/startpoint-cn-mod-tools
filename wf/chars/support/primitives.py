# -*- coding: utf-8 -*-
"""季节换装七角色：规格驱动角色包的共用原语。

写入边界：只写 ``<workspace>/package/roots/**`` 与 ``<workspace>/evidence/**``；
live store、``assets/``、``.cdn/`` 只读。表写入一律「包内已有副本优先，否则 live」，
所以 tables / kit 多次写同一张表时键会累积；认领按 (root, logical_path) 合并并持久化到
``evidence/table_claims.json``（重复运行幂等）。
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import re
import sys
import zlib
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

HERE = Path(__file__).resolve().parent

import wf_assets  # noqa: E402
import wf_dsl  # noqa: E402
import wf_mod_tool as core  # noqa: E402
from . import specs as specs_mod  # noqa: E402
from .specs import SeasonalSpec  # noqa: E402

ROOT = Path(os.environ["WF_S7_ROOT"]).expanduser().resolve() if os.environ.get("WF_S7_ROOT") else core.project_root()
ROOT_NAMES = ("common", "medium", "android", "server")
CLIENT_ROOTS = ("common", "medium", "android")
STORE_ROOT_MAP = {"upload": "common", "medium": "medium", "android": "android",
                  "medium_upload": "medium", "android_upload": "android", "common": "common"}
SUPPORTED_CODECS = ("flat", "raw_outer", "action_nested", "switched_nested", "json_object")
NESTED_CODECS = {core.ACTION_SKILL_LOGICAL: "action_nested",
                 core.SWITCHED_ACTION_SKILL_LOGICAL: "switched_nested"}
DSL_SUFFIX = ".action.dsl.amf3.deflate"
CLAIMS_FILE = "table_claims.json"
OWNED_FILE = "owned_outputs.json"
SOURCES_FILE = "template_sources.json"


class S7Error(RuntimeError):
    pass


# ---------------------------------------------------------------- 纯函数工具

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def csv_join(rows: list[list[str]]) -> str:
    return core.write_csv_lines(rows).rstrip("\n")


def csv_split(text: str) -> list[list[str]]:
    return core.read_csv_lines(text)


def as_text(value: str | list) -> str:
    if isinstance(value, str):
        return value
    if value and isinstance(value[0], str):
        return csv_join([list(value)])
    return csv_join([list(r) for r in value])


def png_open(raw: bytes):
    from PIL import Image
    return Image.open(io.BytesIO(wf_assets.png_decode(raw))).convert("RGBA")


def png_store_bytes(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return wf_assets.png_encode(buf.getvalue())


def amf_parse(raw: bytes):
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


def amf_bytes(tree) -> bytes:
    """单一 compressobj（两个对象会造坏流）；只接受裸树，写后回读自检。"""
    if isinstance(tree, dict) and set(tree) >= {"tree"} and "numbers" in tree:
        raise S7Error("amf_bytes got a {tree,numbers} wrapper; pass the bare tree")
    raw = zlib.compress(wf_dsl.encode_amf3(tree), 9)[2:-4]
    if amf_parse(raw) != tree:
        raise S7Error("AMF3 roundtrip differs")
    return raw


def walk(node):
    yield node
    if isinstance(node, list):
        for child in node:
            yield from walk(child)
    elif isinstance(node, dict):
        for child in node.values():
            yield from walk(child)


def commands(tree, name: str) -> list[list]:
    return [n for n in walk(tree) if isinstance(n, list) and n and n[0] == name]


def replace_strings(node, substitutions: Mapping[str, str]):
    """递归替换字符串（含 dict 键）；数值/布尔原样保留，输入不变。"""
    if isinstance(node, str):
        for old, new in substitutions.items():
            node = node.replace(old, new)
        return node
    if isinstance(node, list):
        return [replace_strings(item, substitutions) for item in node]
    if isinstance(node, dict):
        return {replace_strings(k, substitutions): replace_strings(v, substitutions)
                for k, v in node.items()}
    return node


def dir_prefix_map(old_code: str, new_code: str) -> dict[str, str]:
    """``character/<old>/`` → ``character/<new>/``：带尾斜杠，前缀型 code 也不会误伤。"""
    return {f"character/{old_code}/": f"character/{new_code}/"}


def merge_claims(existing: list[dict], additions: Iterable[dict]) -> list[dict]:
    """按 (root, logical_path) 合并认领：outer/inner/semantic 取并集，codec 冲突报错。

    输出顺序 = 首次出现顺序；outer_keys 排序；inner_keys 按 outer_key 排序、keys 保持首见顺序。
    纯函数，重复合并同一批认领结果不变（幂等）。
    """
    order: list[tuple[str, str]] = []
    table: dict[tuple[str, str], dict] = {}
    for claim in [*existing, *additions]:
        root, logical = claim["root"], claim["logical_path"]
        codec = claim["codec_id"]
        if root not in ROOT_NAMES:
            raise S7Error(f"claim root invalid: {root}")
        if codec not in SUPPORTED_CODECS:
            raise S7Error(f"claim codec invalid: {codec}")
        key = (root, logical)
        if key not in table:
            order.append(key)
            table[key] = {"codec_id": codec, "outer": set(), "inner": {}, "semantic": []}
        entry = table[key]
        if entry["codec_id"] != codec:
            raise S7Error(f"claim codec conflict {root}:{logical}: {entry['codec_id']} vs {codec}")
        entry["outer"].update(str(k) for k in claim.get("outer_keys", []))
        for item in claim.get("inner_keys", []):
            keys = entry["inner"].setdefault(item["outer_key"], [])
            for k in item["keys"]:
                if k not in keys:
                    keys.append(k)
            entry["outer"].add(item["outer_key"])
        for sem in claim.get("semantic_claims", []):
            if sem not in entry["semantic"]:
                entry["semantic"].append(sem)
    result = []
    for root, logical in order:
        entry = table[(root, logical)]
        result.append({
            "codec_id": entry["codec_id"],
            "inner_keys": [{"keys": list(entry["inner"][o]), "outer_key": o}
                           for o in sorted(entry["inner"])],
            "logical_path": logical,
            "outer_keys": sorted(entry["outer"]),
            "root": root,
            "semantic_claims": list(entry["semantic"]),
        })
    return result


# ---------------------------------------------------------------- 元素翻转

# instant content 元素参数（c73）为 1 基的 kind：720 OverrideCharacterElement（写 5=光）。
ONE_BASED_ELEMENT_INSTANT_KINDS = frozenset({"720"})


def _flip_group_cell(value: str, old: str, new: str) -> str:
    parts = value.split(",")
    if old not in parts:
        return value
    return ",".join(new if p == old else p for p in parts)


def flip_ability_row(row: list[str], table: str, old_el: int, new_el: int,
                     label: str = "") -> tuple[list[str], list[dict]]:
    """词条/队长行元素翻转（参照 wf_gui.element_convert）：

    - character_groups 类元素 token（逗号分列，只换旧元素 token）；
    - ability c2 雕像组 ``<prefix>_<oldcolor>``；
    - content 块 element 数值列（instant_content+26 / during_content+10）等于旧元素时。
      例外：instant kind 720 OverrideCharacterElement 的 c73 是 **1 基**元素（记忆卡
      wf-character-groups-semantics），按 old+1 → new+1 比较/改写。
    判他方元素的枚举 kind 不动。
    """
    import wf_describe
    if old_el == new_el:
        return list(row), []
    old_tok, new_tok = specs_mod.ELEMENT_TOKENS[old_el], specs_mod.ELEMENT_TOKENS[new_el]
    old_color, new_color = specs_mod.ELEMENT_COLORS[old_el], specs_mod.ELEMENT_COLORS[new_el]
    blocks = wf_describe.layout(table)["blocks"]
    instant_kind_col = blocks["instant_content"]
    instant_el_col = blocks["instant_content"] + 26
    el_cols = {instant_el_col, blocks["during_content"] + 10}
    instant_kind = row[instant_kind_col] if len(row) > instant_kind_col else ""
    out, changes = list(row), []
    for ci, value in enumerate(out):
        after = value
        if value:
            after = _flip_group_cell(value, old_tok, new_tok)
            if table == "ability" and ci == 2 and value.endswith("_" + old_color):
                after = value[: -len(old_color)] + new_color
            if ci == instant_el_col and instant_kind in ONE_BASED_ELEMENT_INSTANT_KINDS:
                if value == str(old_el + 1):
                    after = str(new_el + 1)
            elif ci in el_cols and value == str(old_el):
                after = str(new_el)
        if after != value:
            changes.append({"cell": label, "col": ci, "before": value, "after": after})
            out[ci] = after
    return out, changes


def flip_dsl_elements(tree, old_el: int, new_el: int) -> tuple[Any, list[dict]]:
    """DSL 显式元素 = 内部+1：CreateNormalAttack[2] 与 FindAllSubjects(33)[3] 旧元素 → 新元素。"""
    if old_el == new_el:
        return tree, []
    tree = copy.deepcopy(tree)
    old_code, new_code = old_el + 1, new_el + 1
    changes: list[dict] = []
    for node in walk(tree):
        if not (isinstance(node, list) and node and isinstance(node[0], str)):
            continue
        if node[0] == "CreateNormalAttack" and len(node) > 2 and node[2] == old_code:
            node[2] = new_code
            changes.append({"node": "CreateNormalAttack[2]", "before": old_code, "after": new_code})
        elif (node[0] == "FindAllSubjects" and len(node) > 3 and node[2] == 33
              and isinstance(node[3], list) and old_code in node[3]):
            before = list(node[3])
            node[3] = [new_code if v == old_code else v for v in node[3]]
            changes.append({"node": "FindAllSubjects(33)[3]", "before": before, "after": node[3]})
        elif node[0] == "ACToleranceOfElement" and len(node) > 2 and node[2] == old_code:
            changes.append({"node": "ACToleranceOfElement[2]", "before": old_code,
                            "after": old_code, "note": "他方/抗性元素，未翻转"})
    return tree, changes


def replace_element_words(text: str, old_el: int, new_el: int) -> str:
    if old_el == new_el or not text:
        return text
    old, new = specs_mod.ELEMENT_WORDS[old_el], specs_mod.ELEMENT_WORDS[new_el]
    return text.replace(f"{old}属性", f"{new}属性")


# ---------------------------------------------------------------- 角色包上下文


__all__ = [name for name in globals() if not name.startswith("__")]
