"""Read portable requirements beside loaded ZIPs and compare registered client evidence."""
from __future__ import annotations

import re

from .opening_chain import check
from .rehearsal_io import read_json


def _requirements(edge, paths):
    """No discovery outside the exact archive folders already selected by the view."""
    from wf.caps.scan_binding import verify_declared_archives
    from wf.deliver.changeset import validate_document

    candidates = {paths[name].parent / "requires.json" for name in edge["names"]}
    found = []
    for candidate in sorted(candidates):
        if not candidate.is_file():
            continue
        document = read_json(candidate)
        validate_document(document, "requires.schema.json")
        if any(not re.fullmatch(r"[a-z][a-z0-9_.]*@[1-9][0-9]*", cap)
               for cap in document["requires"]["clientCapabilities"]):
            raise ValueError("依赖能力 ID 无效")
        pack = document["pack"]
        if ((pack["since"], pack["tail"]) != (edge["from"], edge["to"])
                or set(pack["archives"]) != set(edge["names"])):
            continue
        # Bind even resolved reports to all archive members, not just filenames.
        verify_declared_archives(document, candidate.parent)
        found.append((document, candidate.parent))
    if not found:
        return None
    if any(value[0] != found[0][0] for value in found[1:]):
        raise ValueError("同一版本边存在互相冲突的能力依赖报告")
    return found[0]


def client_capabilities(edges, paths, client_profile=None):
    from wf.caps.compat import check_compat
    from wf.caps.profiles import read_client, resolve_client

    result = {"profile": client_profile, "available": False, "status": "unknown",
              "providesCount": 0, "requires": [], "missing": [], "unknownEdges": [], "checks": []}
    try:
        filename, selected = resolve_client(client_profile=client_profile)
        provides = read_client(filename)
        result.update(profile=selected, available=True, providesCount=len(provides["provides"]))
        result["checks"].append(check("client-profile", "满足", "客户端 provides 格式、档案身份与摘要校验通过"))
    except (OSError, ValueError, TypeError, KeyError):
        result["checks"].append(check("client-profile", "问题", "客户端 provides 无法通过档案身份与摘要校验；请检查客户端档案配置", blocking=True))
        return result
    required, missing = set(), set()
    for edge in edges:
        label = edge["from"] + " → " + edge["to"]
        try:
            evidence = _requirements(edge, paths)
            if evidence is None:
                result["unknownEdges"].append(label)
                continue
            requires, directory = evidence
            required.update(requires["requires"]["clientCapabilities"])
            checks = check_compat(requires, provides, delivery_dir=directory)
            for item in checks:
                safe = {key: item[key] for key in ("rule", "status", "blocking", "message", "id") if key in item}
                # Future capability checks may carry file evidence in their messages.
                safe["message"] = re.sub(r"(?:[A-Za-z]:[\\/]|\\\\|https?://)[^\s，；）]+",
                                         "[本机证据已隐藏]", str(safe.get("message", "")))
                safe["edge"] = label
                result["checks"].append(safe)
                if item.get("blocking") and item.get("id"):
                    missing.add(item["id"])
            if any(item.get("status") == "待验证" for item in checks):
                result["unknownEdges"].append(label)
        except (OSError, ValueError, TypeError, KeyError):
            result["unknownEdges"].append(label)
            result["checks"].append(check("requirements", "待验证", f"{label} 的 requires 缺失、损坏或无法与实际 ZIP 成员绑定"))
    result.update(requires=sorted(required), missing=sorted(missing))
    blocked = any(item.get("blocking") for item in result["checks"])
    result["status"] = "mismatch" if blocked else "unknown" if result["unknownEdges"] or not edges else "matched"
    if result["unknownEdges"]:
        result["checks"].append(check("requirements-coverage", "待验证",
            f"{len(result['unknownEdges'])} 条资源边缺少完整可绑定的依赖证据；不能据此确认整个客户端兼容"))
    return result
