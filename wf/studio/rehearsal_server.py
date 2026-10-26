"""Read-only enabled-chain checks and key-level server JSON previews."""
from __future__ import annotations
import re

from wf.view.chain import version

from .drafts import DraftError
from .rehearsal_inputs import digest
from .rehearsal_io import inside, read_json


def chain_tail(manifest):
    if not isinstance(manifest, dict) or not isinstance(manifest.get("patches"), list):
        raise DraftError("服务端 manifest 缺少 patches 数组")
    if any(not isinstance(e, dict) for e in manifest["patches"]):
        raise DraftError("服务端 patches 条目必须是对象")
    enabled = [e for e in manifest["patches"] if e.get("enabled") is True and e.get("type") == "patch"]
    if not enabled:
        raise DraftError("服务端 manifest 没有启用的版本链")
    seen = set()
    previous = None
    for entry in enabled:
        current, parent = entry.get("version"), entry.get("depends_on")
        if any(not isinstance(v, str) or not re.fullmatch(r"\d+\.\d+\.\d+", v) for v in (current, parent)):
            raise DraftError("启用补丁 version / depends_on 必须是三段版本号")
        if current in seen or version(current) <= version(parent):
            raise DraftError("服务端启用链重复版本或版本回退")
        if previous is not None and parent != previous:
            raise DraftError(f"服务端启用链断链或分叉：{parent} → {current}")
        previous = current
        seen.add(current)
    if manifest.get("cdn_version") != previous:
        raise DraftError("服务端 cdn_version 与启用链尾不一致")
    return previous


def _pointer(parent, key):
    return parent + "/" + str(key).replace("~", "~0").replace("/", "~1")


def key_diff(before, after, pointer=""):
    """Missing keys are preserved by the manual merge, never implicit deletes."""
    added, replaced, omitted = [], [], []
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(after):
            p = _pointer(pointer, key)
            if key not in before:
                added.append(p)
            else:
                a, r, o = key_diff(before[key], after[key], p)
                added.extend(a)
                replaced.extend(r)
                omitted.extend(o)
        omitted.extend(_pointer(pointer, k) for k in sorted(before.keys() - after.keys()))
    elif before != after:
        replaced.append(pointer or "/")
    return added, replaced, omitted


def server_preview(folder, root):
    from .rehearsal_targets import entry_targets, unchanged_keys
    candidates = []
    declared = {}
    targets, operations = entry_targets(folder)
    assertion_file = inside(folder, "assert-box.json")
    if assertion_file.is_file():
        for entry in read_json(assertion_file).get("files", []):
            if entry.get("kind") == "server":
                declared[entry["target"]] = entry
    for dirname in ("server", "server-entries"):
        staging = inside(folder, dirname)
        if not staging.is_dir():
            continue
        for file in sorted(staging.rglob("*")):
            if not file.is_file():
                continue
            rel = file.relative_to(staging).as_posix()
            file = inside(staging, rel)
            if dirname == "server-entries" and rel in {"README.md", "merge-manifest.json"}:
                continue
            mapped = [rel] if dirname == "server" else targets(rel)
            candidates.extend((target, file, operations.get(rel, [])) for target in mapped)
    seen, results, snapshots = set(), [], {}
    for target, candidate, operations_for_file in candidates:
        if target in seen:
            raise DraftError(f"重复服务端目标：{target}")
        seen.add(target)
        if not target.startswith(("assets/", "out/")):
            raise DraftError(f"服务端目标只支持 assets/ 或 out/：{target}")
        # Do not read databases even if a malformed candidate names one.
        if any(token in target.lower() for token in (".sqlite", ".db", "asset-patch/")):
            raise DraftError(f"不能预演数据库或补丁发布目录：{target}")
        destination = inside(root, target)
        old_hash = digest(destination) if destination.is_file() else None
        snapshots[target] = old_hash
        new_hash = digest(candidate)
        assertion = declared.get(target, {})
        if assertion.get("sha256", new_hash) != new_hash:
            raise DraftError(f"服务端候选摘要不符：{target}")
        item = {"target": target, "source": str(candidate), "destination": str(destination),
                "beforeSha256": old_hash, "sha256": new_hash,
                "baselineMatches": (old_hash == assertion["before_sha256"]
                                    if "before_sha256" in assertion else None),
                "kind": "json" if target.endswith(".json") else "code",
                "addedKeys": [], "replacedKeys": [], "omittedKeys": [], "unchangedKeys": [],
                "wholeFileOverwriteRisk": old_hash is not None,
                "changed": old_hash != new_hash}
        if item["kind"] == "json":
            before = read_json(destination) if old_hash is not None else {}
            after = read_json(candidate)
            a, r, o = key_diff(before, after)
            item.update(addedKeys=a, replacedKeys=r, omittedKeys=o,
                        unchangedKeys=unchanged_keys(before, after),
                        changed=bool(a or r), mergeMode="按 JSON Pointer 逐键合入，保留 omittedKeys")
            item["existingClaimedKeys"] = []
            for operation in operations_for_file:
                if operation.get("operation") == "append_object_keys":
                    node = before
                    for key in operation.get("object_pointer", "").split("/")[1:]:
                        node = node.get(key.replace("~1", "/").replace("~0", "~"), {})
                    item["existingClaimedKeys"].extend(
                        _pointer(operation.get("object_pointer", ""), k)
                        for k in operation.get("keys", []) if isinstance(node, dict) and k in node)
            if isinstance(before, list) and isinstance(after, list):
                item.update(appendValues=[v for v in after if v not in before],
                            omittedValues=[v for v in before if v not in after],
                            addedKeys=[], replacedKeys=[], changed=any(v not in before for v in after),
                            mergeMode="列表逐项核对，禁止整表覆盖")
        results.append(item)
    if set(declared) - seen:
        raise DraftError("缺少声明的服务端候选文件：" + ", ".join(sorted(set(declared) - seen)))
    return results, snapshots
