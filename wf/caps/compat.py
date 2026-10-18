"""Compare capability identity, required patch sets and recorded method hashes."""
from __future__ import annotations

import re

from wf.deliver.changeset import validate_document
from wf.rules.catalog import result
from .method_evidence import accepted_hashes, selected_method_hash


def check_compat(requires, provides, *, registry=None, delivery_dir=None):
    if registry is None:
        from .registry import load_registry
        registry = load_registry()
    validate_document(requires, "requires.schema.json")
    validate_document(provides, "provides.schema.json")
    required = requires["requires"]
    results = []
    if required["capabilityResolution"] == "declared":
        from .scan_binding import verify_declared_archives
        try:
            verify_declared_archives(requires, delivery_dir)
        except (ValueError, OSError) as error:
            results.append(result("capability.scan-members", "问题", str(error), blocking=True))
    if required["capabilityResolution"] not in {"resolved", "declared"} or required.get("unresolved"):
        results.append(result("capability.resolution", "待验证", "内容依赖推导尚不完整，不能确认兼容",
                              blocking=True, unresolved=required.get("unresolved", [])))
    available = {entry["id"]: entry for entry in provides["provides"]}
    if len(available) != len(provides["provides"]):
        raise ValueError("duplicate capability IDs in provides")
    patches = {entry["number"] for entry in provides["patches"]}
    patch_records = {entry["number"]: entry for entry in provides["patches"]}
    if len(patches) != len(provides["patches"]):
        raise ValueError("duplicate patch numbers in provides")
    capability_ids = list(required["clientCapabilities"])
    covered = {n for cid in capability_ids if cid in registry for n in registry[cid]["provided_by"]["patches"]}
    for patch in required["clientPatches"]:
        match = re.fullmatch(r"#?([1-9][0-9]*)", patch)
        if not match:
            raise ValueError(f"unknown required patch notation: {patch}")
        number = int(match[1])
        patch_id = f"client.apk.patch{number:03d}@1"
        if patch_id not in registry:
            raise ValueError(f"unregistered required patch: {patch}")
        if number not in covered and patch_id not in capability_ids:
            capability_ids.append(patch_id)
    for cap_id in capability_ids:
        cap = registry.get(cap_id)
        if cap is None:
            results.append(result("capability.unknown", "问题", f"注册表没有能力 {cap_id}", blocking=True, id=cap_id))
            continue
        needed = cap["provided_by"]["patches"]
        missing_patches = sorted(set(needed) - patches)
        entry = available.get(cap_id)
        patch_label = ", ".join(f"#{number}" for number in needed) or "官方客户端系统"
        if entry is None or missing_patches:
            results.append(result("capability.missing", "问题", f"缺 {cap['title']}（{cap_id}）；需要 {patch_label}",
                                  blocking=True, id=cap_id, patches=needed, missing_patches=missing_patches))
            continue
        if set(entry["patches"]) != set(needed):
            results.append(result("capability.patch-evidence", "问题", f"{cap['title']} 的补丁依据与注册表不符",
                                  blocking=True, id=cap_id, patches=needed))
            continue
        expected = cap["provided_by"]["methods"]
        actual = {(m["patch"], m["abc"], m["label"]): m.get("sha256") for m in entry["methods"]}
        if len(actual) != len(entry["methods"]):
            raise ValueError(f"duplicate method evidence: {cap_id}")
        recorded = {}
        for number in needed:
            for method in patch_records[number]["methods"]:
                key = method["patch"], method["abc"], method["label"]
                if method["patch"] != number or key in recorded:
                    raise ValueError(f"invalid or duplicate patch method evidence: {cap_id}")
                recorded[key] = method.get("sha256")
        if actual != recorded:
            results.append(result("capability.method-hash", "问题", f"{cap['title']} 能力方法哈希与补丁方法记录不一致",
                                  blocking=True, id=cap_id))
            continue
        mismatches, missing, pending = [], [], []
        for method in expected:
            key = (method["patch"], method["abc"], method["label"])
            recorded = actual.get(key)
            if method.get("sha256") is None and method["status"] == "待补":
                pending.append(method["label"])
            elif recorded is None:
                missing.append(method["label"])
            elif recorded not in accepted_hashes(method, provides["source"].get("swf_sha256")):
                mismatches.append({"method": method["label"], "expected": selected_method_hash(
                    method, provides["source"].get("swf_sha256")), "actual": recorded})
        if missing:
            results.append(result("capability.method-hash", "问题", f"{cap['title']} 缺少注册表要求的方法 SHA-256",
                                  blocking=True, id=cap_id, missing_methods=missing))
        elif mismatches:
            results.append(result("capability.method-hash", "问题", f"{cap['title']} 方法哈希不匹配",
                                  blocking=True, id=cap_id, mismatches=mismatches))
        else:
            results.append(result("capability.provided", "待验证" if pending else "满足",
                                  f"{cap['title']}：能力与补丁记录匹配" + ("；部分方法哈希待补" if pending else ""),
                                  id=cap_id, pending_methods=pending, basis=entry["basis"]))
    if not results:
        results.append(result("capability.provided", "满足", "已扫描的变更内容未使用已登记客户端扩展能力"))
    return results
