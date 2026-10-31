"""Check concrete table/kind uses against the selected binary, never decompiled AS."""
from wf.rules.catalog import result


def _sites(required):
    from .surfaces import ABILITY_TABLES

    sites = list(required.get("kindSites", []))
    incomplete = []
    # Pre-M2.3 requires already recorded concrete table/kind evidence. Retain
    # its checks on read-back rather than silently trusting the old registry.
    for entry in required.get("capabilityEvidence", []):
        for evidence in entry["evidence"]:
            table = ABILITY_TABLES.get(evidence["logical_path"])
            kind = str(evidence["value"])
            if evidence["signal"] != "kinds":
                continue
            block = evidence.get("block")
            if not table or not block:
                incomplete.append(evidence)
            else:
                site = {"logical_path": evidence["logical_path"], "key": evidence.get("key", ""),
                        "row": evidence.get("row", 0), "table": table, "block": block, "kind": kind}
                if not any(all(existing.get(k) == v for k, v in site.items()) for existing in sites):
                    sites.append(site)
    return sites, incomplete


def check_kind_sites(required, provides, registry):
    sites, incomplete = _sites(required)
    checks = []
    if incomplete:
        checks.append(result("capability.kind-evidence", "待验证",
                             "旧 kind 证据缺少表或块，不能按编号猜测；请重新推导内容依赖",
                             blocking=True, evidence=incomplete))
    if not sites:
        return checks
    from wf.apk.kinds import inspect_provides, kind_supported
    try:
        report = inspect_provides(provides, registry=registry)
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        return checks + [result("capability.kind-evidence", "待验证",
                               f"无法核对真实 SWF 的 kind 分支：{error}", blocking=True)]
    for mismatch in report.get("mismatches", []):
        used_extra = any(str(site["kind"]) == str(mismatch["kind"])
                         and site["block"] == mismatch["block"]
                         and site["table"] in mismatch.get("unregistered_tables", [])
                         for site in sites)
        if not mismatch.get("missing_branches") and not used_extra:
            continue  # An unused parser branch is not a runtime capability grant.
        checks.append(result("capability.kind-registry", "问题",
                             "注册表 allowed_tables 与真实 SWF 的 kind 分支不一致",
                             blocking=True, mismatch=mismatch))
    for site in sites:
        if not kind_supported(report, site["table"], site["block"], site["kind"]):
            checks.append(result("capability.kind-unsupported", "问题",
                                 f"真实 SWF 不支持 {site['table']}.{site['block']} 的 kind {site['kind']}",
                                 blocking=True, site=site))
    if not checks:
        checks.append(result("capability.kind-supported", "满足",
                             "能力行使用的 kind 均有真实 SWF 方法分支，注册表表范围一致",
                             sites=len(sites), swf_sha256=report["source"]["swf_sha256"]))
    return checks
