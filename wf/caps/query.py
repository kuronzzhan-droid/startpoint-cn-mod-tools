"""Read-only editor queries using the same typed signals and compatibility gate."""
from .compat import check_compat
from .profiles import load_profiles, read_client, resolve_client
from .registry import load_registry
from .signals_v35 import custom_signals, unique_signals
from .surfaces import matches_signal


def requirements_for_signals(signals, registry):
    ids = []
    for cid, cap in registry.items():
        surface = cap["data_surface"]
        if any(matches_signal(surface, kind, value) for kind, value in signals):
            ids.append(cid)
    return ids


def query_requirements(*, kinds=(), unique_strings=(), dsl_markers=(), selectors=(),
                       custom_keys=(), unique_id=None, client_profile=None, registry=None):
    explicit_registry = registry is not None
    registry = load_registry() if registry is None else registry
    signals = [("kinds", value) for value in kinds]
    signals += [("dsl_nodes", value) for value in dsl_markers]
    signals += [("selectors", value) for value in (*dsl_markers, *selectors)]
    for value in unique_strings:
        signals.extend(unique_signals(value, unique_id))
    for value in custom_keys:
        signals.extend(custom_signals(value))
    unsupported = [value for kind, value in signals if kind == "unsupported"]
    ids = sorted(requirements_for_signals(signals, registry))
    patches = sorted({n for cid in ids for n in registry[cid]["provided_by"]["patches"]})
    requires = {"schemaVersion": 2, "pack": {"since": "0.0.0", "tail": "0.0.1",
                "anchor": {"from": "0.0.0", "to": "0.0.1"}, "archives": ["query.zip"]},
                "requires": {"clientCapabilities": ids, "clientPatches": [f"#{n}" for n in patches],
                             "serverFeatures": [], "serverRestart": False, "restartReasons": [],
                             "minServerVersion": None,
                             "capabilityResolution": "partial" if unsupported else "resolved"}}
    default, profiles = load_profiles()
    selected = client_profile or default
    if selected not in profiles:
        raise ValueError(f"未知客户端档案：{selected}")
    reports, compatible = {}, []
    for name, profile in profiles.items():
        if not profile.get("provides"):
            continue
        try:
            path, _ = resolve_client(client_profile=name)
            evidence = read_client(path)
            selected_registry = registry
            if not explicit_registry:
                from wf.apk.local_registry import for_swf
                selected_registry = for_swf(registry, evidence["source"].get("swf_sha256"))
            checks = check_compat(requires, evidence, registry=selected_registry)
        except (OSError, ValueError) as exc:
            reports[name] = {"compatible": False, "error": str(exc), "checks": []}
            continue
        ok = not any(r["blocking"] or r.get("compatibility") in {"degraded", "declared"} for r in checks)
        reports[name] = {"compatible": ok, "checks": checks,
                         "degraded": any(r.get("compatibility") == "degraded" for r in checks)}
        if ok:
            compatible.append(name)
    return {"clientProfile": selected, "capabilities": ids,
            "requiredClientProfiles": compatible, "profiles": reports,
            "selectedCompatible": reports.get(selected, {}).get("compatible", False),
            "recognized": bool(ids) and not unsupported, "unsupported": unsupported,
            "signals": [{"kind": k, "value": v} for k, v in signals],
            "note": ("无表/块的 kind 编号仅查询能力目录，兼容结果不证明该编号在任何具体位置有效。"
                     if kinds else "") +
                    "仅比较已登记能力与离线方法证据；无命中不证明未知标记有效，也不代表设备验收。"}
