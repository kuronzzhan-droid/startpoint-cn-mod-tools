"""Auditable wording policy, with incomplete semantic checks kept explicit."""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re

from .standard_checks import CHECKS, unquote


@lru_cache(maxsize=1)
def rule_catalog():
    return json.loads((Path(__file__).parents[1] / "rules/text_standard.json").read_text("utf-8"))


def check_entry(key, text, *, surface="desc_override", location=None):
    """Return proven violations only. Use coverage() for nonautomatic obligations."""
    if not isinstance(text, str):
        raise ValueError(f"{key}: text must be a string")
    if surface not in {"desc_override", "action_skill", "custom_ability_string"}:
        raise ValueError(f"unsupported standard text surface: {surface}")
    findings = []
    for rule in rule_catalog()["rules"]:
        if surface not in rule["surfaces"]:
            continue
        spec = rule["implementation"]
        # Quoted names are explicitly preserved by §8, including names like PF.
        searchable = unquote(text) if rule["id"].split(".")[-1].startswith("term-") else text
        matches = [match[0] for pattern in spec["patterns"] for match in re.finditer(pattern, searchable)]
        if spec["check"]:
            matches.extend(CHECKS[spec["check"]](text, key))
        if matches:
            findings.append({"rule": rule["id"], "state": "问题", "location": location or f"{surface}.{key}",
                "message": rule["requirement"], "evidence_nature": rule["evidence_nature"],
                "source": rule["source"], "evidence": {"text": text, "matches": list(dict.fromkeys(matches))}})
    return findings


def coverage(surfaces, findings=()):
    """Every clause receives an explicit state; regex absence proves no semantics."""
    failing = {finding["rule"] for finding in findings if finding["state"] == "问题"}
    records = []
    for rule in rule_catalog()["rules"]:
        applies = bool(set(rule["surfaces"]) & set(surfaces))
        mode = rule["implementation"]["mode"]
        state = "不适用" if not applies else "问题" if rule["id"] in failing else "待验证" if mode != "automatic" else "满足"
        boundary = {"review": "此条未做自动判定；须核对原数据、DSL或完整语义",
                    "partial": "仅列举写法已自动检查；未命中不代表全面符合，完整语义、数据和效果保留须核对",
                    "automatic": "已扫描规则列出的确定性写法"}[mode]
        records.append({"rule": rule["id"], "state": state, "mode": mode,
            "evidence_nature": rule["evidence_nature"], "source": rule["source"],
            "requirement": rule["requirement"],
            "boundary": boundary})
    return records


def check_document(document):
    findings, surfaces = [], set()
    for surface in ("desc_override",):
        for key, text in document.get(surface, {}).items():
            surfaces.add(surface)
            findings.extend(check_entry(key, text, surface=surface))
    for tier, pair in document.get("action_skill", {}).items():
        surfaces.add("action_skill")
        findings.extend(check_entry(f"{document.get('skill_key', '')}.{tier}", pair["c1"],
                                   surface="action_skill", location=f"action_skill.{tier}.c1"))
    pending = [entry["rule"] for entry in coverage(surfaces, findings) if entry["state"] == "待验证"]
    if pending:
        findings.append({"rule": "text.standard.coverage", "state": "待验证", "location": document["character_id"],
            "message": "确定性写法已检查；以下条款仍需原数据、DSL或语义核对，不作全面通过",
            "evidence": {"pending_rules": pending, "source_sha256": rule_catalog()["source_sha256"]}})
    return findings
