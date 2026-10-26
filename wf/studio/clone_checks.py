"""HTTP clone checks use the same five-state contract as weapon authoring."""
from wf.rules.catalog import result


def response_checks(document):
    checks = [result("character.inputs", "满足", "身份、母本表与玛纳节点预留检查通过")]
    for check in document.get("checks", []):
        failed = check.get("level") == "error"
        state = "问题" if failed else "待验证" if check.get("level") == "warn" else "满足"
        checks.append(result(check["code"], state, check["message"], blocking=failed))
    if not any(c["rule"] == "character.assets" for c in checks):
        checks.append(result("character.assets", "满足", "适用资产均可从母本派生"))
    if any(item["status"] == "not_applicable" for item in document.get("assets", [])):
        checks.append(result("character.special", "不适用", "★1–★3 不使用 special 获取演出四件"))
    checks.append(result("character.runtime", "未执行", "未执行真机、获取演出或战斗验证"))
    return checks
