# Source section of rogue_build; loaded in its shared module namespace.
def build_hp_adaptation_audit(
        round_no: int, native: dict, *, family: str, channel: str,
        destination: str | dict[str, str],
        baseline_target_hp: float, final_target_hp: float,
        baseline_c86: float, final_c86: float,
        readback_native: dict | None = None,
        baseline_component_hp: tuple[float, ...] | list[float] | None = None,
        baseline_component_target_hp: tuple[float, ...] | list[float] | None = None,
        final_component_target_hp: tuple[float, ...] | list[float] | None = None,
        abs_tolerance_hp: float = HP_TARGET_ABS_TOLERANCE,
        rel_tolerance: float = HP_TARGET_REL_TOLERANCE) -> HpAdaptationAudit:
    """Build a per-occurrence/per-phase plan and read it back like the client.

    ``native`` is immutable source evidence. ``readback_native`` is the final
    cloned/rewritten representation.  Their component order is an occurrence
    contract: duplicates are deliberately retained and count mismatches fail
    closed instead of being reconciled by boss code.
    """
    source_components = list(native.get("components") or [])
    final_native = native if readback_native is None else readback_native
    final_components = list(final_native.get("components") or [])
    if not native.get("verified") or not source_components:
        raise ValueError(
            f"第{round_no}战 HP adapter 缺可验证组件:{native.get('reason') or 'unknown'}")
    if not final_native.get("verified") or len(final_components) != len(source_components):
        raise ValueError(
            f"第{round_no}战 HP adapter 回读组件数不一致:"
            f"source={len(source_components)},readback={len(final_components)}")
    numeric = (float(baseline_target_hp), float(final_target_hp),
               float(baseline_c86), float(final_c86),
               float(abs_tolerance_hp), float(rel_tolerance))
    if (not all(math.isfinite(value) for value in numeric)
            or any(value <= 0 for value in numeric[:-1])
            or numeric[-1] < 0):
        raise ValueError(f"第{round_no}战 HP adapter 输入必须为有限正数:{numeric}")
    native_total = math.fsum(float(part["native_hp"])
                             for part in source_components)
    if not math.isfinite(native_total) or native_total <= 0:
        raise ValueError(f"第{round_no}战 HP adapter 原生总量非法:{native_total}")
    if baseline_component_hp is None:
        baseline_values = _hp_component_readback_values(native, baseline_c86)
    else:
        baseline_values = tuple(float(value) for value in baseline_component_hp)
        if len(baseline_values) != len(source_components):
            raise ValueError(
                f"第{round_no}战 HP adapter 基线组件数不一致:"
                f"source={len(source_components)},baseline={len(baseline_values)}")
    final_values = _hp_component_readback_values(final_native, final_c86)
    if not all(math.isfinite(value) and value > 0
               for value in baseline_values + final_values):
        raise ValueError(f"第{round_no}战 HP adapter 回读含非法组件")
    baseline_total = math.fsum(baseline_values)
    final_total = math.fsum(final_values)
    if baseline_component_target_hp is None:
        baseline_targets = tuple(
            float(baseline_target_hp) * float(source["native_hp"]) / native_total
            for source in source_components)
    else:
        baseline_targets = tuple(map(float, baseline_component_target_hp))
    if final_component_target_hp is None:
        final_targets = tuple(
            float(final_target_hp) * float(source["native_hp"]) / native_total
            for source in source_components)
    else:
        final_targets = tuple(map(float, final_component_target_hp))
    if (len(baseline_targets) != len(source_components)
            or len(final_targets) != len(source_components)
            or not math.isclose(math.fsum(baseline_targets),
                                float(baseline_target_hp),
                                rel_tol=1e-12, abs_tol=1e-4)
            or not math.isclose(math.fsum(final_targets), float(final_target_hp),
                                rel_tol=1e-12, abs_tol=1e-4)):
        raise ValueError(
            f"第{round_no}战 HP adapter 逐组件目标与整关目标不一致")
    destination_map = (dict(destination)
                       if isinstance(destination, dict) else {})
    floor_destination = ("/".join(sorted(set(destination_map.values())))
                         if destination_map else str(destination))
    component_audits: list[HpComponentAudit] = []
    for index, (source, readback, baseline_value, final_value,
                baseline_target, final_target) in enumerate(
            zip(source_components, final_components,
                baseline_values, final_values,
                baseline_targets, final_targets), start=1):
        evidence = source.get("evidence")
        selected_level = source.get("selected_level")
        if selected_level is None and isinstance(evidence, dict):
            selected_level = evidence.get("selected_level")
        phase = source.get("phase")
        component_audits.append(HpComponentAudit(
            occurrence=index,
            boss_occurrence=int(source.get("boss_occurrence") or index),
            code=str(source.get("code") or ""),
            readback_code=str(readback.get("code") or ""),
            phase=str(phase if phase is not None else "main"),
            kind=str(source.get("kind") or "unknown"),
            source_evidence_kind=str(
                source.get("evidence_kind") or "unknown"),
            # Strict proof belongs to the rewritten representation.  Keep the
            # source evidence alongside it so a proxy-origin adapter is never
            # reported as if its original curve had become known retroactively.
            evidence_kind=str(readback.get("evidence_kind") or "unknown"),
            source=_hp_evidence_source(source),
            native_hp=float(source["native_hp"]),
            baseline_target_hp=baseline_target,
            final_target_hp=final_target,
            baseline_readback_hp=baseline_value,
            final_readback_hp=final_value,
            baseline_error_hp=baseline_value - baseline_target,
            final_error_hp=final_value - final_target,
            channel=str(channel), destination=str(
                destination_map.get(str(source.get("code") or ""),
                                    floor_destination)),
            selected_level=(int(selected_level)
                            if selected_level is not None else None),
        ))
    return HpAdaptationAudit(
        round_no=int(round_no), family=str(family), channel=str(channel),
        destination=floor_destination,
        absolute_verified=bool(final_native.get("absolute_verified")),
        baseline_target_hp=float(baseline_target_hp),
        final_target_hp=float(final_target_hp),
        baseline_readback_hp=baseline_total,
        final_readback_hp=final_total,
        baseline_error_hp=baseline_total - float(baseline_target_hp),
        final_error_hp=final_total - float(final_target_hp),
        baseline_c86=float(baseline_c86), final_c86=float(final_c86),
        abs_tolerance_hp=float(abs_tolerance_hp),
        rel_tolerance=float(rel_tolerance),
        components=tuple(component_audits),
    )


def strict_hp_candidate_error(metrics: dict | None) -> str | None:
    """Return why a boss candidate cannot enter strict target-HP mode."""
    if not isinstance(metrics, dict):
        return "strict-no-hp-plan"
    native = metrics.get("native")
    if not isinstance(native, dict) or not native.get("verified"):
        return "strict-no-absolute-readback"
    if (not native.get("absolute_verified")
            and not metrics.get("absolute_after_adaptation")):
        return "strict-proxy-evidence"
    if metrics.get("hp_channel") not in {"boss_level", "c86", "standard_dsl",
                                          "mixed_hp", "special_bundle"}:
        return f"strict-unsupported-channel:{metrics.get('hp_channel')}"
    return None


def strict_target_hp_errors(audits: list[dict]) -> list[str]:
    """Final strict gate: every boss floor must be absolute and on target."""
    errors: list[str] = []
    for audit in audits:
        round_no = int(audit.get("r") or 0)
        if round_no < first_boss_round():
            continue
        if not audit.get("verified"):
            errors.append(f"第{round_no}战没有可回读的 Boss HP")
            continue
        if audit.get("target_exempt"):
            errors.append(f"第{round_no}战仍是 target_exempt")
        if not audit.get("absolute_verified"):
            errors.append(f"第{round_no}战仍含代理 HP 证据")
        receipt = audit.get("adapter_audit")
        if not isinstance(receipt, HpAdaptationAudit):
            errors.append(f"第{round_no}战缺统一 HP adapter 回执")
            continue
        if receipt.channel in {"none", "unscaled"}:
            errors.append(f"第{round_no}战没有实际 HP 落表通道:{receipt.channel}")
        if (receipt.family == "orochi_ex"
                and not isinstance(
                    audit.get("orochi_ex_phase_safety"), dict)):
            errors.append(
                f"第{round_no}战 Orochi EX 缺 signed-int32/阶段图标门禁")
        proxy_parts = [part.occurrence for part in receipt.components
                       if part.evidence_kind != "absolute"]
        if proxy_parts:
            errors.append(
                f"第{round_no}战组件 {','.join(map(str, proxy_parts))} 不是绝对证据")
        if not receipt.within_tolerance:
            errors.append(
                f"第{round_no}战 HP 回读超差:baseline={receipt.baseline_error_hp:g}/"
                f"±{receipt.baseline_tolerance_hp:g},final={receipt.final_error_hp:g}/"
                f"±{receipt.final_tolerance_hp:g}")
    return errors


def hp_component_audit_lines(receipt: HpAdaptationAudit) -> list[str]:
    """Render compact, machine-greppable per-component audit evidence."""
    lines = []
    for part in receipt.components:
        level = f"@lv{part.selected_level}" if part.selected_level is not None else ""
        lines.append(
            f"    [HP组件] occ={part.occurrence}/boss#{part.boss_occurrence} "
            f"{part.code}{level} phase={part.phase} "
            f"evidence={part.source_evidence_kind}→{part.evidence_kind} "
            f"native={part.native_hp:g} target={part.baseline_target_hp:g}→"
            f"{part.final_target_hp:g} channel={part.channel} dest={part.destination} "
            f"readback={part.baseline_readback_hp:g}→{part.final_readback_hp:g} "
            f"error={part.baseline_error_hp:g}→{part.final_error_hp:g} "
            f"source={part.source}")
    lines.append(
        f"    [HP回读] target={receipt.baseline_target_hp:g}→"
        f"{receipt.final_target_hp:g} actual={receipt.baseline_readback_hp:g}→"
        f"{receipt.final_readback_hp:g} error={receipt.baseline_error_hp:g}→"
        f"{receipt.final_error_hp:g} tolerance=±max({receipt.abs_tolerance_hp:g},"
        f"target×{receipt.rel_tolerance:g})")
    return lines


HP_AUDIT_SCHEMA = "wf-rogue-hp-audit/v4"
HP_AUDIT_VERIFICATION_SCOPE = "static_dry_run"


def hp_audit_document_digest(document: dict) -> str:
    """Return the canonical SHA-256 of an audit document without its digest."""
    payload = dict(document)
    payload.pop("document_sha256", None)
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_hp_audit_document(*, seed: int, rounds: int,
                            difficulty: str, enemy_level: str,
                            hp_audits: list[dict], floor_records: list[dict],
                            chain_reports: list[dict],
                            hp_profile: str = "unspecified",
                            curse_diversity: dict | None = None) -> dict:
    """Serialize the strict in-memory result into a self-contained receipt.

    This is deliberately built only from the final adapter receipts and the
    final exact-kind chain reports.  It does not trust the human-readable plan
    lines and it never reads or writes the runtime mirror/database.
    """
    records = {int(record["r"]): record for record in floor_records}
    floors: list[dict] = []
    for audit in sorted(hp_audits, key=lambda item: int(item["r"])):
        round_no = int(audit["r"])
        if round_no < first_boss_round():
            continue
        receipt = audit.get("adapter_audit")
        if not isinstance(receipt, HpAdaptationAudit):
            raise ValueError(f"第{round_no}战缺 HpAdaptationAudit，不能生成验收回执")
        record = records.get(round_no) or {}
        pick = record.get("pick") or {}
        serialized = asdict(receipt)
        serialized["components"] = [
            dict(component) for component in serialized["components"]]
        serialized["within_tolerance"] = bool(receipt.within_tolerance)
        if isinstance(audit.get("phase_behavior"), dict):
            serialized["phase_behavior"] = copy.deepcopy(
                audit["phase_behavior"])
        if isinstance(audit.get("orochi_ex_phase_safety"), dict):
            serialized["phase_safety"] = copy.deepcopy(
                audit["orochi_ex_phase_safety"])
        if isinstance(audit.get("mechanism_budget"), dict):
            serialized["mechanism_budget"] = copy.deepcopy(
                audit["mechanism_budget"])
        if isinstance(audit.get("damage_checks"), dict):
            serialized["damage_checks"] = copy.deepcopy(
                audit["damage_checks"])
        curse = record.get("curse") or {}
        curse_capability = curse.get("capability_profile")
        if not isinstance(curse_capability, dict):
            # Unit-level receipt builders may omit the random curse object;
            # synthesize the conservative carrier-less realization, never a
            # more permissive one.
            curse_capability = resolve_curse_capabilities(
                str(serialized.get("channel") or ""),
                str(serialized.get("family") or ""), {})
        curse_picks = list(curse.get("picks") or ())
        curse_names = [str(item.get("name") or "") for item in curse_picks]
        if any(not name for name in curse_names):
            raise ValueError(f"第{round_no}战诅咒条目缺名称，不能生成验收回执")
        curse_hp_multiplier = float(
            audit["curse_hp"] if audit.get("curse_hp") is not None else
            receipt.final_target_hp / receipt.baseline_target_hp)
        quest_hp_multipliers = copy.deepcopy(
            audit.get("quest_hp_multipliers"))
        if not isinstance(quest_hp_multipliers, dict):
            raise ValueError(
                f"第{round_no}战缺 c86/c87/c88 独立 HP 计划，不能生成验收回执")
        quest_row = record.get("row")
        if not isinstance(quest_row, list) or len(quest_row) <= 88:
            raise ValueError(
                f"第{round_no}战缺任务行 c86/c87/c88 最终回读，不能生成验收回执")
        try:
            table_readback = {
                "enemy": float(quest_row[86]),
                "device_or_summon": float(quest_row[87]),
                "boss": float(quest_row[88]),
            }
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"第{round_no}战任务行 c86/c87/c88 最终回读非法") from exc
        if not all(math.isfinite(value) and value > 0
                   for value in table_readback.values()):
            raise ValueError(
                f"第{round_no}战任务行 c86/c87/c88 必须为有限正数")
        quest_hp_multipliers["table_readback"] = table_readback
        thumbnail_evidence = copy.deepcopy(pick.get("thumbnail_evidence"))
        floors.append({
            "round": round_no,
            "field": str(pick.get("field") or ""),
            "play_field": str(pick.get("play_field") or pick.get("field") or ""),
            "thumbnail": str(pick.get("thumb") or ""),
            "thumbnail_source_field": str(
                pick.get("thumbnail_field") or pick.get("field") or ""),
            "thumbnail_evidence": thumbnail_evidence,
            "enemy_level": int(pick.get("level") or 0),
            "source_bosses": list(map(str, pick.get("bosses") or ())),
            "runtime_bosses": list(map(
                str, pick.get("runtime_bosses") or pick.get("bosses") or ())),
            "verified": bool(audit.get("verified")),
            "absolute_verified": bool(audit.get("absolute_verified")),
            "target_exempt": bool(audit.get("target_exempt")),
            # Keep the final post-band-gate curse choices in the machine
            # receipt.  ``desc`` is derived by ``apply_picks`` from the same
            # final picks that produced hp/atk/conditions, so the detailed
            # report cannot accidentally describe the pre-downgrade roll.
            "curse_names": curse_names,
            "curse_combo": (str(curse.get("combo"))
                            if curse.get("combo") else None),
            "curse_description": str(curse.get("desc") or ""),
            "curse_hp_multiplier": curse_hp_multiplier,
            **({"ex_lanes": copy.deepcopy(curse["ex_lanes"]),
                "ex_native_evidence": copy.deepcopy(curse["ex_native_evidence"]),
                "ex_attack": {"base": float(record["atk"]),
                              "factor": abyss_modes.attack_factor("ex", round_no),
                              "actual": float(quest_row[91])}}
               if BUILD_MODE == "ex" else {}),
            "curse_capability_profile": copy.deepcopy(curse_capability),
            "curse_used_capabilities": list(map(
                str, curse.get("used_capabilities") or ())),
            "field_program_receipts": copy.deepcopy(
                curse.get("field_program_receipts") or []),
            "quest_hp_multipliers": quest_hp_multipliers,
            "identity_reference_closures": list(copy.deepcopy(
                record.get("identity_reference_closures") or ())),
            "adapter": serialized,
        })
    max_error = max((
        max(abs(float(floor["adapter"]["baseline_error_hp"])),
            abs(float(floor["adapter"]["final_error_hp"])))
        for floor in floors), default=0.0)
    chain = [dict(report) for report in chain_reports]
    document = {
        "schema": HP_AUDIT_SCHEMA,
        # 这份回执只能证明构建期静态解析/回读。字段故意放在顶层并纳入
        # document_sha256，让下游不能把“全绿”误写成已经真机实战通过。
        "verification_scope": HP_AUDIT_VERIFICATION_SCOPE,
        "gameplay_verified": False,
        "event_id": EVENT_ID,
        "inputs": {
            "seed": int(seed), "rounds": int(rounds),
            "difficulty": str(difficulty), "enemy_level": str(enemy_level),
            "strict_target_hp": True,
            "hp_profile": str(hp_profile),
            "baseline_includes_curse": False,
        },
        "tool": {
            "name": Path(__file__).name,
            "sha256": tool_source_sha256(),
        },
        "selection_policy": {
            "boss_exclusions": [dict(item) for item in STRICT_HP_EXCLUSION_POLICY],
            "native_special_only": [
                dict(item) for item in STRICT_HP_NATIVE_SPECIAL_POLICY],
            "curse_capability_matrix": curse_capability_matrix_receipt(),
            "client_bundled_curve_baseline": (
                client_bundled_curve_baseline_receipt()),
            "curse_diversity": (copy.deepcopy(curse_diversity)
                                 if curse_diversity is not None
                                 else curse_diversity_receipt(
                                     new_curse_diversity_state())),
        },
        "floors": floors,
        "chain_reports": chain,
        "summary": {
            "expected_boss_rounds": max(0, int(rounds) - first_boss_round() + 1),
            "audited_boss_rounds": len(floors),
            "absolute_boss_rounds": sum(
                1 for floor in floors if floor["absolute_verified"]),
            "proxy_components": sum(
                1 for floor in floors
                for component in floor["adapter"]["components"]
                if component.get("evidence_kind") != "absolute"),
            "source_proxy_components": sum(
                1 for floor in floors
                for component in floor["adapter"]["components"]
                if component.get(
                    "source_evidence_kind",
                    component.get("evidence_kind")) != "absolute"),
            "target_exempt_rounds": sum(
                1 for floor in floors if floor["target_exempt"]),
            "special_bundle_rounds": sum(
                1 for floor in floors
                if floor["adapter"].get("channel") == "special_bundle"),
            "identity_reference_closure_rounds": sum(
                1 for floor in floors
                if floor.get("identity_reference_closures")),
            "identity_reference_closures": sum(
                len(floor.get("identity_reference_closures") or ())
                for floor in floors),
            "baseline_first_boss_hp": (
                float(floors[0]["adapter"]["baseline_target_hp"])
                if floors else 0.0),
            "baseline_last_boss_hp": (
                float(floors[-1]["adapter"]["baseline_target_hp"])
                if floors else 0.0),
            "baseline_strictly_increasing": all(
                float(current["adapter"]["baseline_target_hp"])
                > float(previous["adapter"]["baseline_target_hp"])
                for previous, current in zip(floors, floors[1:])),
            "max_absolute_error_hp": max_error,
            "chain_reports": len(chain),
            "chain_failures": sum(1 for report in chain if not report.get("ok")),
            "thumbnail_static_verified_floors": sum(
                1 for floor in floors
                if isinstance(floor.get("thumbnail_evidence"), dict)
                and floor["thumbnail_evidence"].get("static_verified") is True),
        },
    }
    document["document_sha256"] = hp_audit_document_digest(document)
    return document


def _verify_sphere_lifecycle_receipt(
        label: str, phase_behavior: dict) -> list[str]:
    """Independently verify serialized static Sphere liveness evidence."""

    errors: list[str] = []
    if phase_behavior.get("static_verified") is not True:
        errors.append(f"{label} Sphere 静态阶段存活闭包未验证")
    if phase_behavior.get("runtime_simulated") is not False:
        errors.append(f"{label} Sphere 不得把静态闭包标成运行时模拟")
    if phase_behavior.get("gameplay_verified") is not False:
        errors.append(f"{label} Sphere 不得把离线审计标成真机通过")
    source = phase_behavior.get("source_lifecycle")
    final = phase_behavior.get("final_lifecycle")
    if not isinstance(source, dict) or not isinstance(final, dict):
        return errors + [f"{label} Sphere 缺源/回读阶段存活契约"]
    for name, proof in (("源", source), ("回读", final)):
        if proof.get("static_verified") is not True:
            errors.append(f"{label} Sphere {name}存活契约未静态验证")
        if proof.get("runtime_simulated") is not False:
            errors.append(f"{label} Sphere {name}存活契约误标运行时模拟")
        if proof.get("gameplay_verified") is not False:
            errors.append(f"{label} Sphere {name}存活契约误标真机通过")
    if (not source.get("client_contract")
            or source.get("client_contract") != final.get("client_contract")):
        errors.append(f"{label} Sphere 客户端阶段契约来源漂移")
    if (not source.get("family")
            or source.get("family") != final.get("family")):
        errors.append(f"{label} Sphere 存活契约家族漂移")
    try:
        source_victory = int(source["victory_component_count"])
        final_victory = int(final["victory_component_count"])
    except (KeyError, TypeError, ValueError):
        source_victory = final_victory = 0
        errors.append(f"{label} Sphere 存活契约缺胜利组件数")
    if source_victory <= 0 or source_victory != final_victory:
        errors.append(f"{label} Sphere 胜利组件数量漂移")
    source_steps = source.get("steps")
    final_steps = final.get("steps")
    if (not isinstance(source_steps, (list, tuple))
            or not isinstance(final_steps, (list, tuple))
            or len(source_steps) != 4 or len(final_steps) != 4):
        return errors + [f"{label} Sphere 阶段存活边数量不是4"]

    source_budgets = {
        str(item.get("phase")): item
        for item in (phase_behavior.get("source") or ())
        if isinstance(item, dict)
    }
    final_budgets = {
        str(item.get("phase")): item
        for item in (phase_behavior.get("final_readback") or ())
        if isinstance(item, dict)
    }
    expected_targets = (2, 3, 4, None)
    allowed_triggers = {
        "mandatory_gate_clear", "parent_hp_threshold",
        "child_damage_threshold", "parent_hp_depleted",
    }
    mandatory_entities = 0
    used_budget_phases: set[str] = set()
    for sequence, (source_step, final_step, expected_target) in enumerate(
            zip(source_steps, final_steps, expected_targets), start=1):
        edge_label = f"{label}阶段存活边{sequence}"
        if not isinstance(source_step, dict) or not isinstance(final_step, dict):
            errors.append(f"{edge_label} 不是对象")
            continue
        try:
            source_phase = int(source_step["source_phase"])
            final_phase = int(final_step["source_phase"])
            source_sequence = int(source_step["sequence"])
            final_sequence = int(final_step["sequence"])
            source_target_raw = source_step.get("target_phase")
            final_target_raw = final_step.get("target_phase")
            source_target = (None if source_target_raw is None
                             else int(source_target_raw))
            final_target = (None if final_target_raw is None
                            else int(final_target_raw))
            source_entities = int(source_step.get("expected_entities", 0))
            final_entities = int(final_step.get("expected_entities", 0))
        except (KeyError, TypeError, ValueError):
            errors.append(f"{edge_label} 缺阶段拓扑数字")
            continue
        source_trigger = str(source_step.get("trigger") or "")
        final_trigger = str(final_step.get("trigger") or "")
        source_members = tuple(map(
            str, source_step.get("member_phases") or ()))
        final_members = tuple(map(
            str, final_step.get("member_phases") or ()))
        source_ids = tuple(map(str, source_step.get("entity_ids") or ()))
        final_ids = tuple(map(str, final_step.get("entity_ids") or ()))
        source_completion = source_step.get("expected_completion_count")
        final_completion = final_step.get("expected_completion_count")
        source_budget_phase = source_step.get("budget_phase")
        final_budget_phase = final_step.get("budget_phase")
        source_entry = str(source_step.get("next_state_entry") or "")
        final_entry = str(final_step.get("next_state_entry") or "")
        expected_entry = (
            f"getInitialStateByNextPhase({expected_target})"
            if expected_target is not None else "Sphere.enterDeadState")
        if (source_sequence != sequence or final_sequence != sequence
                or source_phase != sequence or final_phase != sequence
                or source_target != expected_target
                or final_target != expected_target):
            errors.append(f"{edge_label} 1→2→3→4→胜利拓扑漂移")
        if (source_trigger not in allowed_triggers
                or source_trigger != final_trigger):
            errors.append(f"{edge_label} 触发方式漂移")
        if (source_members != final_members
                or source_entities != final_entities
                or source_completion != final_completion
                or source_budget_phase != final_budget_phase
                or source_entry != expected_entry or final_entry != expected_entry
                or source_step.get("verified") is not True
                or final_step.get("verified") is not True):
            errors.append(f"{edge_label} 静态推进契约漂移")
        if (len(source_ids) != source_entities
                or len(final_ids) != final_entities
                or len(set(source_ids)) != len(source_ids)
                or len(set(final_ids)) != len(final_ids)):
            errors.append(f"{edge_label} 子体数量/唯一性漂移")
        source_ratio = source_step.get("threshold_ratio")
        final_ratio = final_step.get("threshold_ratio")
        if source_ratio is None or final_ratio is None:
            if source_ratio is not None or final_ratio is not None:
                errors.append(f"{edge_label} 阈值有无漂移")
        else:
            try:
                source_ratio_value = float(source_ratio)
                final_ratio_value = float(final_ratio)
                if (not math.isfinite(source_ratio_value)
                        or not math.isfinite(final_ratio_value)
                        or not math.isclose(
                            source_ratio_value, final_ratio_value,
                            rel_tol=1e-12, abs_tol=1e-12)):
                    errors.append(f"{edge_label} 阈值漂移")
            except (TypeError, ValueError):
                errors.append(f"{edge_label} 阈值非法")

        if source_trigger == "mandatory_gate_clear":
            mandatory_entities += source_entities
            if (sequence != 1 or not source_members
                    or source_entities <= 0
                    or source_completion != source_entities):
                errors.append(f"{edge_label} 必杀门槛计数不闭合")
        elif source_trigger == "parent_hp_threshold":
            if source_entities != 0 or source_ids or source_ratio is None:
                errors.append(f"{edge_label} 父体阈值边混入子体门槛")
        elif source_trigger == "child_damage_threshold":
            phase = str(source_budget_phase or "")
            source_budget = source_budgets.get(phase)
            final_budget = final_budgets.get(phase)
            used_budget_phases.add(phase)
            if not isinstance(source_budget, dict) or not isinstance(
                    final_budget, dict):
                errors.append(f"{edge_label} 缺对应子体伤害预算")
            else:
                source_budget_ids = tuple(map(
                    str, source_budget.get("entity_ids") or ()))
                final_budget_ids = tuple(map(
                    str, final_budget.get("entity_ids") or ()))
                if (len(source_budget_ids) != source_entities
                        or len(final_budget_ids) != final_entities
                        or source_budget.get("expected_completion_count")
                        != source_completion
                        or final_budget.get("expected_completion_count")
                        != final_completion):
                    errors.append(f"{edge_label} 子体预算计数不闭合")
        elif source_trigger == "parent_hp_depleted":
            if sequence != 4 or expected_target is not None:
                errors.append(f"{edge_label} 父体死亡边位置非法")
    if source_victory != 1 + mandatory_entities:
        errors.append(f"{label} Sphere 胜利组件数不能由必杀门槛回代")
    if used_budget_phases != set(source_budgets):
        errors.append(f"{label} Sphere 存活契约未覆盖全部源阶段预算")
    if used_budget_phases != set(final_budgets):
        errors.append(f"{label} Sphere 存活契约未覆盖全部回读阶段预算")
    return errors


def _verify_orochi_ex_phase_damage_capacity_contract(
        label: str, contract: object, *,
        expected_phase1_hp: float,
        expected_phase3_hp: float) -> list[str]:
    """Independently replay the two head-capacity phase gates."""

    errors: list[str] = []
    if not isinstance(contract, dict):
        return [f"{label} 缺蛇头阶段承伤容量回执"]
    if contract.get("schema") != OROCHI_EX_PHASE_CAPACITY_SCHEMA:
        errors.append(f"{label} 蛇头阶段承伤容量 schema 非法")
    if (contract.get("absolute_verified") is not True
            or contract.get("static_verified") is not True
            or contract.get("runtime_simulated") is not False
            or contract.get("gameplay_verified") is not False):
        errors.append(f"{label} 蛇头阶段承伤容量证据等级非法")
    try:
        selected_level = int(contract["selected_level"])
        coverage = float(contract["required_coverage_ratio"])
        format_margin = float(contract["format_margin"])
        minimum_scale = float(contract["minimum_scale"])
    except (KeyError, TypeError, ValueError):
        selected_level = 0
        coverage = float("nan")
        format_margin = float("nan")
        minimum_scale = float("nan")
    if selected_level <= 0:
        errors.append(f"{label} 蛇头阶段档位非法")
    if (not math.isfinite(coverage)
            or not math.isclose(
                coverage, OROCHI_EX_PHASE_CARRIER_COVERAGE_RATIO,
                rel_tol=1e-12, abs_tol=1e-12)):
        errors.append(f"{label} 蛇头阶段安全余量漂移")
    if (not math.isfinite(format_margin)
            or not math.isclose(
                format_margin, OROCHI_EX_PHASE_CARRIER_FORMAT_MARGIN,
                rel_tol=1e-12, abs_tol=1e-15)
            or not math.isfinite(minimum_scale) or minimum_scale <= 0):
        errors.append(f"{label} 蛇头阶段计划倍率/格式余量非法")
    phases = contract.get("phases")
    if not isinstance(phases, list) or len(phases) != 2:
        return errors + [f"{label} 蛇头阶段承伤容量必须覆盖 phase1/phase3"]
    expected = ((1, float(expected_phase1_hp)),
                (3, float(expected_phase3_hp)))
    for record, (phase, expected_required) in zip(phases, expected):
        prefix = f"{label} phase{phase}"
        if not isinstance(record, dict):
            errors.append(f"{prefix} 蛇头承伤记录不是对象")
            continue
        try:
            actual_phase = int(record["phase"])
            required_hp = float(record["required_hp"])
            required_ratio = float(record["required_coverage_ratio"])
            required_capacity = float(record["required_capacity_hp"])
            claimed_total = float(record["total_carrier_hp"])
            claimed_total_ratio = float(record["total_coverage_ratio"])
            claimed_primary_hp = float(record["primary_carrier_hp"])
            claimed_primary_ratio = float(record["primary_coverage_ratio"])
            planned_scale = float(record["planned_scale"])
            phase_minimum_scale = float(record["minimum_scale"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{prefix} 蛇头承伤数字不可解析")
            continue
        head_codes = tuple(map(str, record.get("head_codes") or ()))
        carrier_hp = record.get("carrier_hp")
        carrier_c2 = record.get("boss_level_c2")
        primary = str(record.get("primary_carrier") or "")
        source_head_codes = tuple(map(
            str, record.get("source_head_codes") or ()))
        source_to_target = record.get("source_to_target")
        source_hp = record.get("source_carrier_hp")
        source_c2 = record.get("source_boss_level_c2")
        planned_c2 = record.get("planned_boss_level_c2")
        if (actual_phase != phase or len(head_codes) != 3
                or len(set(head_codes)) != 3 or primary != head_codes[1]):
            errors.append(f"{prefix} 三蛇头顺序/中心载体漂移")
            continue
        if (not isinstance(carrier_hp, dict)
                or set(map(str, carrier_hp)) != set(head_codes)
                or not isinstance(carrier_c2, dict)
                or set(map(str, carrier_c2)) != set(head_codes)):
            errors.append(f"{prefix} 三蛇头 HP/c2 键不闭合")
            continue
        if (len(source_head_codes) != 3
                or len(set(source_head_codes)) != 3
                or not isinstance(source_to_target, dict)
                or set(map(str, source_to_target)) != set(source_head_codes)
                or not isinstance(source_hp, dict)
                or set(map(str, source_hp)) != set(source_head_codes)
                or not isinstance(source_c2, dict)
                or set(map(str, source_c2)) != set(source_head_codes)
                or not isinstance(planned_c2, dict)
                or set(map(str, planned_c2)) != set(source_head_codes)):
            errors.append(f"{prefix} 源蛇头 HP/c2/代号映射键不闭合")
            continue
        try:
            hp_values = tuple(float(carrier_hp[code]) for code in head_codes)
            c2_values = tuple(float(carrier_c2[code]) for code in head_codes)
            mapped_targets = tuple(
                str(source_to_target[code]) for code in source_head_codes)
            source_hp_values = tuple(
                float(source_hp[code]) for code in source_head_codes)
            source_c2_values = tuple(
                float(source_c2[code]) for code in source_head_codes)
            planned_c2_values = tuple(
                float(planned_c2[code]) for code in source_head_codes)
        except (KeyError, TypeError, ValueError):
            errors.append(f"{prefix} 三蛇头 HP/c2 值不可解析")
            continue
        if (mapped_targets != head_codes
                or str(source_to_target.get(source_head_codes[1])) != primary):
            errors.append(f"{prefix} 源蛇头到克隆蛇头代号映射漂移")
            continue
        if (len(source_hp_values) != 3 or len(source_c2_values) != 3
                or len(planned_c2_values) != 3
                or not all(math.isfinite(value) and value > 0 for value in (
                    *hp_values, *c2_values, *source_hp_values,
                    *source_c2_values, *planned_c2_values,
                    planned_scale, phase_minimum_scale))):
            errors.append(f"{prefix} 三蛇头 HP/c2/倍率不是有限正数")
            continue
        total = math.fsum(hp_values)
        primary_hp = hp_values[1]
        expected_capacity = required_hp * required_ratio
        if (not math.isclose(required_hp, expected_required,
                             rel_tol=1e-12, abs_tol=1e-5)
                or not math.isclose(required_ratio, coverage,
                                    rel_tol=1e-12, abs_tol=1e-12)
                or not math.isclose(required_capacity, expected_capacity,
                                    rel_tol=1e-12, abs_tol=1e-5)
                or not math.isclose(claimed_total, total,
                                    rel_tol=1e-12, abs_tol=1e-5)
                or not math.isclose(claimed_primary_hp, primary_hp,
                                    rel_tol=1e-12, abs_tol=1e-5)
                or not math.isclose(claimed_total_ratio, total / required_hp,
                                    rel_tol=1e-12, abs_tol=1e-12)
                or not math.isclose(
                    claimed_primary_ratio, primary_hp / required_hp,
                    rel_tol=1e-12, abs_tol=1e-12)):
            errors.append(f"{prefix} 蛇头承伤容量不能独立回代")
        if total + 1e-6 < expected_capacity:
            errors.append(f"{prefix} 三蛇头总容量不足阶段门槛")
        if primary_hp + 1e-6 < expected_capacity:
            errors.append(f"{prefix} 中心蛇头容量不足阶段门槛")
        for index, source_code in enumerate(source_head_codes):
            target_code = mapped_targets[index]
            realized_scale = planned_c2_values[index] / source_c2_values[index]
            expected_carrier_hp = source_hp_values[index] * realized_scale
            if (not math.isclose(
                    c2_values[index], planned_c2_values[index],
                    rel_tol=1e-12, abs_tol=1e-12)
                    or not math.isclose(
                        realized_scale, planned_scale,
                        rel_tol=HP_TARGET_REL_TOLERANCE,
                        abs_tol=1e-12)
                    or not math.isclose(
                        hp_values[index], expected_carrier_hp,
                        rel_tol=HP_TARGET_REL_TOLERANCE,
                        abs_tol=1e-5)):
                errors.append(
                    f"{prefix} {source_code}->{target_code} c2/HP 不能回代")
        if planned_scale + 1e-12 < phase_minimum_scale:
            errors.append(f"{prefix} 蛇头计划倍率低于父体最终倍率")
        if (record.get("absolute_verified") is not True
                or record.get("static_verified") is not True):
            errors.append(f"{prefix} 蛇头承伤容量未静态绝对验证")
    return errors


def _verify_orochi_ex_phase_safety_receipt(
        label: str, adapter: dict) -> list[str]:
    """Independently replay signed-int32 and PhaseThresholdIcon invariants."""

    errors: list[str] = []
    receipt = adapter.get("phase_safety")
    if not isinstance(receipt, dict):
        return [f"{label} Orochi EX 缺 signed-int32/阶段图标安全回执"]
    if receipt.get("static_verified") is not True:
        errors.append(f"{label} Orochi EX 阶段安全未静态验证")
    if receipt.get("runtime_simulated") is not False:
        errors.append(f"{label} Orochi EX 不得冒充运行时模拟")
    if receipt.get("gameplay_verified") is not False:
        errors.append(f"{label} Orochi EX 不得冒充真机通过")
    components = adapter.get("components")
    if not isinstance(components, list) or len(components) != 3:
        return errors + [f"{label} Orochi EX 阶段安全缺三组件"]

    contracts: list[tuple[str, dict, tuple[float, ...]]] = []
    for name, component_key in (
            ("baseline", "baseline_readback_hp"),
            ("final", "final_readback_hp")):
        contract = receipt.get(name)
        if not isinstance(contract, dict):
            errors.append(f"{label} Orochi EX 缺 {name} 阈值契约")
            continue
        try:
            values = tuple(float(component[component_key])
                           for component in components)
        except (KeyError, TypeError, ValueError):
            errors.append(f"{label} Orochi EX {name} 组件回读非法")
            continue
        contracts.append((name, contract, values))

    client_contract: str | None = None
    for name, contract, values in contracts:
        phase1, middle, phase3 = values
        prefix = f"{label} Orochi EX {name}"
        claimed_contract = str(contract.get("client_contract") or "")
        if not claimed_contract:
            errors.append(f"{prefix} 缺客户端字段/图标契约")
        elif client_contract is None:
            client_contract = claimed_contract
        elif claimed_contract != client_contract:
            errors.append(f"{prefix} 客户端契约漂移")
        if (contract.get("signed_int32_verified") is not True
                or contract.get("static_verified") is not True
                or contract.get("runtime_simulated") is not False
                or contract.get("gameplay_verified") is not False):
            errors.append(f"{prefix} 静态验证标签非法")
        try:
            claimed_phase1 = int(contract["phase1_hp"])
            claimed_phase3 = int(contract["phase3_hp"])
            claimed_middle = float(contract["middle_hp"])
            claimed_total = float(contract["total_hp"])
            threshold1 = float(contract["phase1_hp_threshold"])
            threshold2 = float(contract["phase2_hp_threshold"])
            icon_numbers = tuple(map(int, contract["icon_numbers"]))
            icon_frames = tuple(tuple(map(int, pair))
                                for pair in contract["icon_frames_tens_ones"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{prefix} 阈值数字不可解析")
            continue
        if (claimed_phase1 != phase1 or claimed_middle != middle
                or claimed_phase3 != phase3):
            errors.append(f"{prefix} 阈值输入与三阶段回读不一致")
        if (not 1 <= claimed_phase1 <= wf_orochi_ex.CLIENT_SIGNED_INT_MAX
                or not 1 <= claimed_phase3
                <= wf_orochi_ex.CLIENT_SIGNED_INT_MAX):
            errors.append(f"{prefix} c24/c25 超 signed int32")
        total = math.fsum((float(claimed_phase1), claimed_middle,
                           float(claimed_phase3)))
        expected_thresholds = (
            math.fsum((claimed_middle, float(claimed_phase3))) / total,
            float(claimed_phase3) / total,
        ) if total > 0 else (float("nan"), float("nan"))
        expected_icons = tuple(int(value * 100)
                               for value in expected_thresholds)
        expected_frames = tuple((number // 10 % 10, number % 10)
                                for number in expected_icons)
        if (not math.isfinite(claimed_middle) or claimed_middle <= 0
                or not math.isclose(
                    claimed_total, total, rel_tol=1e-12, abs_tol=1e-5)
                or not all(math.isfinite(value) and 0 < value < 1
                           for value in expected_thresholds)
                or not math.isclose(
                    threshold1, expected_thresholds[0],
                    rel_tol=1e-12, abs_tol=1e-12)
                or not math.isclose(
                    threshold2, expected_thresholds[1],
                    rel_tol=1e-12, abs_tol=1e-12)):
            errors.append(f"{prefix} 阶段阈值不能按客户端公式回代")
        if (icon_numbers != expected_icons or icon_frames != expected_frames
                or not all(0 <= number <= 99 for number in icon_numbers)
                or not all(0 <= frame <= 9
                           for pair in icon_frames for frame in pair)):
            errors.append(f"{prefix} PhaseThresholdIcon 帧号越界/不能回代")

    phase_damage_capacity = receipt.get("phase_damage_capacity")
    if not isinstance(phase_damage_capacity, dict):
        errors.append(f"{label} Orochi EX 缺阶段蛇头承伤容量回执")
    else:
        capacity_expected: dict[str, tuple[float, float]] = {}
        for name, component_key in (
                ("baseline", "baseline_readback_hp"),
                ("final", "final_readback_hp")):
            try:
                capacity_expected[name] = (
                    float(components[0][component_key]),
                    float(components[2][component_key]),
                )
            except (KeyError, TypeError, ValueError):
                errors.append(f"{label} Orochi EX {name} 蛇头门槛不可解析")
        for name in ("baseline", "final"):
            expected_values = capacity_expected.get(name)
            if expected_values is None:
                continue
            errors.extend(
                _verify_orochi_ex_phase_damage_capacity_contract(
                    f"{label} Orochi EX {name}",
                    phase_damage_capacity.get(name),
                    expected_phase1_hp=expected_values[0],
                    expected_phase3_hp=expected_values[1],
                )
            )
        final_expected = capacity_expected.get("final")
        if final_expected is not None:
            errors.extend(
                _verify_orochi_ex_phase_damage_capacity_contract(
                    f"{label} Orochi EX clone readback",
                    phase_damage_capacity.get("clone_readback"),
                    expected_phase1_hp=final_expected[0],
                    expected_phase3_hp=final_expected[1],
                )
            )

    semantics = receipt.get("clone_semantics")
    required_semantics = (
        "parent_only_hp_and_child_columns_changed",
        "parent_boss_level_only_c2_changed",
        "six_head_nodes_equal_source",
        "six_head_boss_level_only_c2_planned",
        "phase1_and_phase3_carriers_cover_gate",
        "six_child_attack_target_references_closed",
        "phase_spawn_topology_preserved",
        "static_verified",
    )
    if (not isinstance(semantics, dict)
            or any(semantics.get(key) is not True
                   for key in required_semantics)
            or semantics.get("runtime_simulated") is not False
            or semantics.get("gameplay_verified") is not False):
        errors.append(f"{label} Orochi EX 克隆/生成/攻击目标闭包不完整")
    elif (not isinstance(phase_damage_capacity, dict)
            or semantics.get("phase_damage_capacity")
            != phase_damage_capacity.get("clone_readback")):
        errors.append(f"{label} Orochi EX 克隆蛇头容量与阶段回执不一致")
    for key in (
            "baseline_fixed_phase_scale", "baseline_middle_scale",
            "final_fixed_phase_scale", "final_middle_scale",
            "max_safe_fixed_phase_scale"):
        try:
            value = float(receipt[key])
        except (KeyError, TypeError, ValueError):
            value = float("nan")
        if not math.isfinite(value) or value <= 0:
            errors.append(f"{label} Orochi EX {key} 非有限正数")
    for key in (
            "baseline_fixed_phase_int32_capped",
            "final_fixed_phase_int32_capped"):
        if receipt.get(key) not in {True, False}:
            errors.append(f"{label} Orochi EX {key} 不是布尔值")
    return errors


