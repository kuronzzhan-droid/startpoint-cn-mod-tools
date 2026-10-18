"""Derive client capabilities from explicit patch and method evidence."""
from __future__ import annotations

import re

from wf.caps.registry import load_registry
from .evidence import read_evidence


def _key(method):
    return method.get("patch"), method.get("abc"), method.get("label")


def _patches(record: dict, registry: dict) -> tuple[dict, list, list]:
    if not isinstance(record.get("patches"), list):
        raise ValueError("patch summary must contain a patches array")
    found, unresolved, warnings = {}, [], []
    seen = set()
    for row in record["patches"]:
        if not isinstance(row, dict) or type(row.get("number")) is not int:
            raise ValueError("patch entries require an integer number")
        n = row["number"]
        if n in seen:
            raise ValueError(f"duplicate patch number: {n}")
        seen.add(n)
        capability = registry.get(f"client.apk.patch{n:03d}@1")
        if not capability:
            unresolved.append({"patch": n, "reason": "补丁未登记，未推导能力"})
            continue
        if row.get("status") not in {"recorded", "declared", "enabled", "applied", "already_present"}:
            unresolved.append({"patch": n, "reason": "补丁没有可用的显式状态"})
            continue
        rows = row.get("methods", [])
        if not isinstance(rows, list) or not all(isinstance(m, dict) for m in rows):
            raise ValueError(f"patch {n}: methods must be an array of objects")
        observed = {}
        for method in rows:
            current = dict(method, patch=method.get("patch", n))
            if current["patch"] != n:
                raise ValueError(f"patch {n}: method belongs to another patch")
            if _key(current) in observed:
                raise ValueError(f"patch {n}: duplicate method evidence")
            value = current.get("sha256")
            if value is not None and (not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value)):
                raise ValueError(f"patch {n}: invalid method sha256")
            observed[_key(current)] = current
        registered = {_key(method) for method in capability["provided_by"]["methods"]}
        for key in sorted(observed.keys() - registered, key=repr):
            warnings.append({"patch": n, "abc": key[1], "label": key[2],
                             "reason": "输入包含注册表未登记的多余方法，未用于能力证明"})
        methods, mismatch, missing = [], [], []
        for expected in capability["provided_by"]["methods"]:
            actual = observed.get(_key(expected), {})
            sha = actual.get("sha256")
            if expected["sha256"] is not None and sha is not None and sha != expected["sha256"]:
                mismatch.append(expected["label"])
            if expected["sha256"] is not None and sha is None:
                missing.append(expected["label"])
            methods.append(dict(expected, sha256=sha, status="已记录" if sha else "待补",
                                source=row.get("basis", "显式输入补丁记录")))
        if mismatch:
            unresolved.append({"patch": n, "reason": "方法哈希不匹配，不能提供此实现版本", "methods": mismatch})
            continue
        if missing:
            unresolved.append({"patch": n, "reason": "缺少注册表要求的方法 SHA-256，不能提供此实现版本",
                               "status": "问题", "methods": missing})
            continue
        found[n] = {"number": n, "status": "recorded" if all(m["sha256"] for m in methods) else "declared",
                    "methods": methods, "basis": row.get("basis", "显式输入补丁记录")}
    return found, unresolved, warnings


def derive_provides(record: dict, source: dict | None = None, registry: dict | None = None) -> dict:
    registry = load_registry() if registry is None else registry
    patches, unresolved, warnings = _patches(record, registry)
    capabilities = []
    for cid, capability in sorted(registry.items()):
        numbers = capability["provided_by"]["patches"]
        if not numbers:
            if capability["layer"] != "B" or record.get("official_systems") is not True:
                continue
        elif not all(n in patches for n in numbers):
            continue
        capabilities.append({"id": cid, "title": capability["title"], "layer": capability["layer"],
                             "patches": list(numbers),
                             "methods": [m for n in numbers for m in patches[n]["methods"]],
                             "basis": "官方系统由输入明确声明" if not numbers else "所需补丁全部由输入记录提供；方法核对状态逐项保留"})
    return {"schema": "wf-apk-provides/1", "source": source or {"kind": "patch-record", "basis": record.get("basis", "显式输入摘要")},
            "patches": [patches[n] for n in sorted(patches)], "provides": capabilities, "unresolved": unresolved,
            "warnings": warnings,
            "limitations": ["静态记录或固定产物匹配不等同设备验收", "客户端能力不证明服务端功能已部署", "null 方法摘要仍为待补，不能当作已验证方法"]}


def build_provides(filename, registry: dict | None = None) -> dict:
    record, source = read_evidence(filename)
    return derive_provides(record, source, registry)
