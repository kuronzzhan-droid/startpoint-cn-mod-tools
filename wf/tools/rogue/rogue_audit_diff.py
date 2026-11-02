#!/usr/bin/env python3
"""Read-only semantic diff for two strict Rogue HP audit receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from wf.tools.rogue import rogue_build as rb


DIFF_SCHEMA = "wf-rogue-hp-audit-diff/v1"


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def receipt_integrity_errors(document: Any) -> list[str]:
    """Check self-contained invariants without assuming the current policy.

    A diff must remain useful across tool revisions, so policy/tool-hash drift
    is reported by the diff instead of making the older receipt unreadable.
    """
    if not isinstance(document, dict):
        return ["root is not an object"]
    errors: list[str] = []
    if document.get("schema") != rb.HP_AUDIT_SCHEMA:
        errors.append(f"schema={document.get('schema')!r}")
    if document.get("verification_scope") != rb.HP_AUDIT_VERIFICATION_SCOPE:
        errors.append(
            f"verification_scope={document.get('verification_scope')!r}")
    if document.get("gameplay_verified") is not False:
        errors.append("gameplay_verified must be false for a static receipt")
    claimed = str(document.get("document_sha256") or "")
    try:
        actual = rb.hp_audit_document_digest(document)
    except (TypeError, ValueError) as exc:
        errors.append(f"canonical digest failed:{exc}")
    else:
        if claimed != actual:
            errors.append(
                f"document_sha256 mismatch:{claimed or '(missing)'}!={actual}")
    if not isinstance(document.get("inputs"), dict):
        errors.append("inputs is not an object")
    if not isinstance(document.get("summary"), dict):
        errors.append("summary is not an object")
    floors = document.get("floors")
    if not isinstance(floors, list):
        errors.append("floors is not an array")
    elif any(not isinstance(floor, dict) for floor in floors):
        errors.append("floors contains a non-object")
    return errors


def _component_semantics(component: dict) -> dict:
    keys = (
        "occurrence", "boss_occurrence", "code", "readback_code", "phase",
        "kind", "source_evidence_kind", "evidence_kind", "native_hp",
        "baseline_target_hp", "baseline_readback_hp", "final_target_hp",
        "final_readback_hp", "destination",
    )
    return {key: component.get(key) for key in keys}


def _floor_semantics(floor: dict) -> dict:
    adapter = floor.get("adapter") or {}
    capability = floor.get("curse_capability_profile") or {}
    phase_behavior = adapter.get("phase_behavior")
    return {
        "field": floor.get("field"),
        "play_field": floor.get("play_field"),
        "thumbnail": {
            "value": floor.get("thumbnail"),
            "source_field": floor.get("thumbnail_source_field"),
            "evidence": floor.get("thumbnail_evidence"),
        },
        "enemy_level": floor.get("enemy_level"),
        "source_bosses": floor.get("source_bosses"),
        "runtime_bosses": floor.get("runtime_bosses"),
        "verified": floor.get("verified"),
        "absolute_verified": floor.get("absolute_verified"),
        "target_exempt": floor.get("target_exempt"),
        "curse": {
            "names": floor.get("curse_names"),
            "combo": floor.get("curse_combo"),
            "description": floor.get("curse_description"),
            "hp_multiplier": floor.get("curse_hp_multiplier"),
            "used_capabilities": floor.get("curse_used_capabilities"),
            "effective_capabilities": capability.get("effective"),
            "field_program_receipts": floor.get("field_program_receipts") or [],
        },
        "quest_hp_multipliers": floor.get("quest_hp_multipliers"),
        "adapter": {
            "channel": adapter.get("channel"),
            "family": adapter.get("family"),
            "baseline_target_hp": adapter.get("baseline_target_hp"),
            "baseline_readback_hp": adapter.get("baseline_readback_hp"),
            "baseline_error_hp": adapter.get("baseline_error_hp"),
            "final_target_hp": adapter.get("final_target_hp"),
            "final_readback_hp": adapter.get("final_readback_hp"),
            "final_error_hp": adapter.get("final_error_hp"),
            "within_tolerance": adapter.get("within_tolerance"),
            "components": [
                _component_semantics(component)
                for component in (adapter.get("components") or ())
                if isinstance(component, dict)
            ],
            "phase_behavior_sha256": (
                _digest(phase_behavior) if isinstance(phase_behavior, dict)
                else None),
            "damage_checks_sha256": (
                _digest(adapter.get("damage_checks"))
                if isinstance(adapter.get("damage_checks"), dict)
                else None),
        },
        "identity_reference_closures": floor.get(
            "identity_reference_closures") or [],
    }


def _changes(before: Any, after: Any, prefix: str = "") -> list[dict]:
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        changes: list[dict] = []
        for key in sorted(set(before) | set(after)):
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in before:
                changes.append({"path": path, "before": None,
                                "after": after[key]})
            elif key not in after:
                changes.append({"path": path, "before": before[key],
                                "after": None})
            else:
                changes.extend(_changes(before[key], after[key], path))
        return changes
    # Lists are intentionally atomic.  Component/curse order is runtime
    # semantics, and an index-by-index diff would obscure insertions.
    return [{"path": prefix or "$", "before": before, "after": after}]


def build_audit_diff(before: dict, after: dict, *,
                     before_label: str = "before",
                     after_label: str = "after") -> dict:
    before_errors = receipt_integrity_errors(before)
    after_errors = receipt_integrity_errors(after)
    if before_errors or after_errors:
        raise ValueError(
            "receipt integrity failed:"
            f"{before_label}={before_errors};{after_label}={after_errors}")
    before_floors = {int(floor["round"]): _floor_semantics(floor)
                     for floor in before["floors"]}
    after_floors = {int(floor["round"]): _floor_semantics(floor)
                    for floor in after["floors"]}
    floor_changes = []
    for round_no in sorted(set(before_floors) | set(after_floors)):
        old = before_floors.get(round_no)
        new = after_floors.get(round_no)
        changes = _changes(old, new)
        if changes:
            floor_changes.append({"round": round_no, "changes": changes})
    before_policy = before.get("selection_policy") or {}
    after_policy = after.get("selection_policy") or {}
    chain_before = before.get("chain_reports") or []
    chain_after = after.get("chain_reports") or []
    result = {
        "schema": DIFF_SCHEMA,
        "before": {
            "label": str(before_label),
            "document_sha256": before.get("document_sha256"),
            "tool_sha256": (before.get("tool") or {}).get("sha256"),
        },
        "after": {
            "label": str(after_label),
            "document_sha256": after.get("document_sha256"),
            "tool_sha256": (after.get("tool") or {}).get("sha256"),
        },
        "input_changes": _changes(before.get("inputs"), after.get("inputs")),
        "summary_changes": _changes(
            before.get("summary"), after.get("summary")),
        "policy_changes": _changes(before_policy, after_policy),
        "floor_changes": floor_changes,
        "chain": {
            "before_count": len(chain_before),
            "after_count": len(chain_after),
            "before_sha256": _digest(chain_before),
            "after_sha256": _digest(chain_after),
            "changed": chain_before != chain_after,
        },
    }
    result["changed"] = any((
        result["input_changes"], result["summary_changes"],
        result["policy_changes"], result["floor_changes"],
        result["chain"]["changed"],
        result["before"]["tool_sha256"] != result["after"]["tool_sha256"],
    ))
    result["diff_sha256"] = _digest(result)
    return result


def render_audit_diff(diff: dict) -> str:
    lines = [
        "# 深渊连战 HP 审计差异",
        "",
        f"- 结果：`{'有语义变化' if diff['changed'] else '无语义变化'}`",
        f"- 基线：`{diff['before']['label']}` / "
        f"`{diff['before']['document_sha256']}`",
        f"- 候选：`{diff['after']['label']}` / "
        f"`{diff['after']['document_sha256']}`",
        f"- 差异 SHA-256：`{diff['diff_sha256']}`",
        "",
        "## 概要",
        "",
        f"- 输入变化：`{len(diff['input_changes'])}`",
        f"- 汇总变化：`{len(diff['summary_changes'])}`",
        f"- 政策变化：`{len(diff['policy_changes'])}`",
        f"- 变化关卡：`{len(diff['floor_changes'])}`",
        f"- 解析链变化：`{'是' if diff['chain']['changed'] else '否'}`",
    ]

    def section(title: str, changes: list[dict]) -> None:
        lines.extend(["", f"## {title}", ""])
        if not changes:
            lines.append("无。")
            return
        for change in changes:
            before = json.dumps(change["before"], ensure_ascii=False,
                                sort_keys=True, separators=(",", ":"))
            after = json.dumps(change["after"], ensure_ascii=False,
                               sort_keys=True, separators=(",", ":"))
            lines.append(f"- `{change['path']}`: `{before}` → `{after}`")

    section("输入", diff["input_changes"])
    section("汇总", diff["summary_changes"])
    section("选择政策", diff["policy_changes"])
    lines.extend(["", "## 逐关变化", ""])
    if not diff["floor_changes"]:
        lines.append("无。")
    else:
        for floor in diff["floor_changes"]:
            lines.append(f"### 第 {floor['round']} 关")
            lines.append("")
            for change in floor["changes"]:
                before = json.dumps(change["before"], ensure_ascii=False,
                                    sort_keys=True, separators=(",", ":"))
                after = json.dumps(change["after"], ensure_ascii=False,
                                   sort_keys=True, separators=(",", ":"))
                lines.append(
                    f"- `{change['path']}`: `{before}` → `{after}`")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="只读对比两份严格 HP 验收回执的语义差异")
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("--json", dest="json_path", metavar="FILE")
    parser.add_argument("--report", metavar="FILE")
    parser.add_argument("--fail-on-change", action="store_true")
    args = parser.parse_args(argv)
    try:
        diff = build_audit_diff(
            _load(args.before), _load(args.after),
            before_label=str(args.before), after_label=str(args.after))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[AUDIT-DIFF-ERR] {exc}", file=sys.stderr)
        return 2
    if args.json_path:
        Path(args.json_path).write_text(
            json.dumps(diff, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    if args.report:
        Path(args.report).write_text(
            render_audit_diff(diff), encoding="utf-8")
    print(
        f"[AUDIT-DIFF] changed={str(diff['changed']).lower()} "
        f"floors={len(diff['floor_changes'])} "
        f"sha256={diff['diff_sha256']}")
    return 1 if args.fail_on_change and diff["changed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
