"""Versioned rule metadata shared by command-line and future studio callers."""
import json
from pathlib import Path

STATES = ("满足", "问题", "待验证", "不适用", "未执行")
EVIDENCE = ("真机实锤", "源码推断", "经验推测", "作者规范", "官方模板引用")


def catalog():
    from wf.text.standard import rule_catalog
    document = json.loads(Path(__file__).with_name("catalog.json").read_text(encoding="utf-8"))
    document["rules"].extend(rule_catalog()["rules"])
    document["version"] = "2.1.0"
    return document


def result(rule, status, message, *, blocking=False, **detail):
    if status not in STATES:
        raise ValueError(f"unknown rule result state: {status}")
    return {"rule": rule, "status": status, "message": message, "blocking": blocking, **detail}


def with_metadata(results, scope):
    by_id = {entry["rule"]: entry for entry in results}
    for rule in catalog()["rules"]:
        if rule["id"] not in by_id:
            applicable = scope in rule["scope"]
            by_id[rule["id"]] = result(rule["id"], "未执行" if applicable else "不适用",
                "缺少该规则所需的完整对象或运行时证据" if applicable else "此输入类型不在规则适用范围")
        by_id[rule["id"]].update({"evidence_nature": rule["evidence_nature"], "source": rule["source"],
                                  "rule_version": catalog()["version"]})
    return list(by_id.values())
