"""Derive client capabilities from explicit patch and method evidence."""
from __future__ import annotations

import re

from wf.caps.registry import load_registry
from wf.caps.method_evidence import accepted_hashes
from .evidence import read_evidence


def _key(method):
    return method.get("patch"), method.get("abc"), method.get("label")


def _standalone(record, registry, unresolved):
    """Recognize explicitly recorded methods without inventing archive numbers."""
    found = {}
    rows = record.get("method_capabilities", [])
    if not isinstance(rows, list):
        raise ValueError("method_capabilities must be an array")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("method capability requires an explicit ID")
        cid = row["id"]
        if cid in seen:
            raise ValueError(f"duplicate method capability: {cid}")
        seen.add(cid)
        cap = registry.get(cid)
        provider = cap["provided_by"] if cap else {}
        if provider.get("patches") or not provider.get("methods"):
            unresolved.append({"id": cid, "reason": "未登记独立方法能力，未推导能力"})
            continue
        if record.get("swf_sha256") not in provider.get("swf_sha256", []):
            unresolved.append({"id": cid, "reason": "SWF 不在该独立方法能力的已核实清单中"})
            continue
        methods = row.get("methods", [])
        if not isinstance(methods, list) or not all(isinstance(m, dict) for m in methods):
            raise ValueError(f"{cid}: methods must be an array of objects")
        actual = {_key(m): m for m in methods}
        if len(actual) != len(methods):
            raise ValueError(f"{cid}: duplicate method evidence")
        expected = provider["methods"]
        if set(actual) != {_key(m) for m in expected} or any(
                actual[_key(m)].get("sha256") not in accepted_hashes(m, record["swf_sha256"])
                for m in expected if _key(m) in actual):
            unresolved.append({"id": cid, "reason": "缺少或不匹配独立方法 SHA-256，不能提供此能力"})
            continue
        found[cid] = [{**{k: v for k, v in m.items() if k != "accepted_variants"},
                       "sha256": actual[_key(m)]["sha256"], "status": "已记录",
                       "source": actual[_key(m)].get("source", row.get("basis", "显式方法记录"))}
                      for m in expected]
    return found


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
            if expected["sha256"] is not None and sha is not None and sha not in accepted_hashes(expected, record.get("swf_sha256")):
                mismatch.append(expected["label"])
            if expected["sha256"] is not None and sha is None:
                missing.append(expected["label"])
            clean_expected = {k: v for k, v in expected.items() if k != "accepted_variants"}
            methods.append(dict(clean_expected, sha256=sha, status="已记录" if sha else "待补",
                                source=actual.get("source", row.get("basis", "显式输入补丁记录"))))
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
    if registry is None:
        from .local_registry import for_swf
        registry = for_swf(load_registry(), record.get("swf_sha256"))
    patches, unresolved, warnings = _patches(record, registry)
    warnings.extend(record.get("local_withheld", []))
    standalone = _standalone(record, registry, unresolved)
    capabilities = []
    for cid, capability in sorted(registry.items()):
        numbers = capability["provided_by"]["patches"]
        methods = [m for n in numbers if n in patches for m in patches[n]["methods"]]
        basis = "所需补丁全部由输入记录提供；方法核对状态逐项保留"
        if not numbers:
            if capability["provided_by"]["methods"]:
                if cid not in standalone:
                    continue
                methods = standalone[cid]
                basis = "已核实 SWF 及独立方法 SHA-256 全部匹配；未分配或推断补丁归档号"
            elif capability["layer"] == "B" and record.get("official_systems") is True:
                basis = "官方系统由输入明确声明"
            else:
                continue
        elif not all(n in patches for n in numbers):
            continue
        capabilities.append({"id": cid, "title": capability["title"], "layer": capability["layer"],
                             "patches": list(numbers),
                             "methods": methods, "basis": basis})
    return {"schema": "wf-apk-provides/1", "source": source or {"kind": "patch-record", "basis": record.get("basis", "显式输入摘要"), "swf_sha256": record.get("swf_sha256")},
            "patches": [patches[n] for n in sorted(patches)], "provides": capabilities, "unresolved": unresolved,
            "warnings": warnings,
            "limitations": ["静态记录或固定产物匹配不等同设备验收", "客户端能力不证明服务端功能已部署", "null 方法摘要仍为待补，不能当作已验证方法"]}


def build_provides(filename, registry: dict | None = None) -> dict:
    record, source = read_evidence(filename)
    return derive_provides(record, source, registry)
