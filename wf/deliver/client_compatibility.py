"""Keep the studio client-evidence gate effective during delivery read-back."""
import json

from wf.rules.catalog import result


def compatibility_status(provides, checks):
    if provides is None:
        return "未确认"
    if any(r["blocking"] for r in checks):
        return "问题"
    return "待验证" if any(r["status"] not in ("满足", "不适用") for r in checks) else "满足"


def unknown_client_check(allowed):
    return result("capability.unknown", "待验证", "未提供目标客户端 provides.json，兼容性未确认",
                  blocking=not allowed)


def write_compatibility(directory, requirements, provides, *, allow_unknown_client=False,
                        client_profile=None):
    from wf.caps.compat import check_compat
    from wf.caps.profiles import read_client
    from .changeset import write_json
    if provides is None:
        checks = [unknown_client_check(allow_unknown_client)]
    else:
        evidence = read_client(provides)
        write_json(directory / "provides.json", evidence)
        checks = check_compat(requirements, evidence, delivery_dir=directory)
    write_json(directory / "compat.json", {"schema": "wf-check-results/1", "results": checks})
    declaration = {"status": compatibility_status(provides, checks),
                   "allow_unknown_client": allow_unknown_client, "report": "compat.json"}
    if client_profile is not None:
        declaration["client_profile"] = client_profile
    return declaration


def readback_compatibility(document, directory, local_read, requirements):
    declaration = document.get("client_compatibility")
    if declaration is None:
        return []  # Historical deliveries predate this optional studio contract.
    report = json.loads(local_read(declaration["report"])[1])
    if not isinstance(report, dict) or report.get("schema") != "wf-check-results/1":
        raise ValueError("invalid client compatibility report")
    if declaration["status"] == "未确认":
        checks = [unknown_client_check(declaration["allow_unknown_client"])]
    else:
        from wf.caps.compat import check_compat
        provides = json.loads(local_read("provides.json")[1])
        checks = check_compat(requirements, provides, delivery_dir=directory)
        if compatibility_status(provides, checks) != declaration["status"]:
            raise ValueError("client compatibility status contradicts supplied evidence")
    if report.get("results") != checks:
        raise ValueError("client compatibility report contradicts supplied evidence or waiver")
    return checks


def readback_draft_checks(document, local_read):
    if "draft_checks" not in document:
        return []
    checks = json.loads(local_read(document["draft_checks"])[1])
    if not isinstance(checks, list):
        raise ValueError("draft checks must be an array")
    return [result(c.get("rule", c.get("code", "studio.draft")), c.get("state", c.get("status", "待验证")),
                   c.get("message", "草稿检查"), blocking=bool(c.get("blocking") or c.get("level") == "error"),
                   draft_check=c) for c in checks]
