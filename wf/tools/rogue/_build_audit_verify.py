# Source section of rogue_build; loaded in its shared module namespace.
def verify_hp_audit_document(document: dict, *,
                             expected_tool_sha256: str | None = None) -> list[str]:
    """Independently recompute strict receipt invariants from serialized data."""
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["验收回执根节点不是对象"]
    if document.get("schema") != HP_AUDIT_SCHEMA:
        errors.append(f"验收回执 schema 非法:{document.get('schema')!r}")
    if document.get("verification_scope") != HP_AUDIT_VERIFICATION_SCOPE:
        errors.append(
            "验收回执 verification_scope 非法:"
            f"{document.get('verification_scope')!r}，"
            f"必须为 {HP_AUDIT_VERIFICATION_SCOPE!r}")
    if document.get("gameplay_verified") is not False:
        errors.append(
            "静态验收回执 gameplay_verified 必须严格为 false；"
            "真机结果须由独立证据流程签发")
    claimed_digest = str(document.get("document_sha256") or "")
    try:
        actual_digest = hp_audit_document_digest(document)
    except (TypeError, ValueError) as exc:
        return errors + [f"验收回执不能规范化:{exc}"]
    if claimed_digest != actual_digest:
        errors.append(
            f"验收回执摘要不一致:claimed={claimed_digest or '(missing)'},"
            f"actual={actual_digest}")
    tool = document.get("tool")
    tool_hash = str(tool.get("sha256") or "") if isinstance(tool, dict) else ""
    if expected_tool_sha256 is not None and tool_hash != expected_tool_sha256:
        errors.append(
            f"生成工具哈希不是当前版本:receipt={tool_hash or '(missing)'},"
            f"current={expected_tool_sha256}")
    policy = document.get("selection_policy")
    expected_exclusions = [dict(item) for item in STRICT_HP_EXCLUSION_POLICY]
    expected_native_special = [
        dict(item) for item in STRICT_HP_NATIVE_SPECIAL_POLICY]
    expected_curse_matrix = curse_capability_matrix_receipt()
    expected_bundled_curve = client_bundled_curve_baseline_receipt()
    if not isinstance(policy, dict):
        errors.append("验收回执缺 selection_policy")
    else:
        if policy.get("boss_exclusions") != expected_exclusions:
            errors.append(
                "验收回执 strict Boss 重抽政策不一致:"
                f"receipt={policy.get('boss_exclusions')!r},"
                f"expected={expected_exclusions!r}")
        if policy.get("native_special_only") != expected_native_special:
            errors.append(
                "验收回执 native special 政策不一致:"
                f"receipt={policy.get('native_special_only')!r},"
                f"expected={expected_native_special!r}")
        if policy.get("curse_capability_matrix") != expected_curse_matrix:
            errors.append(
                "验收回执诅咒能力矩阵不一致:"
                f"receipt={policy.get('curse_capability_matrix')!r},"
                f"expected={expected_curse_matrix!r}")
        if policy.get("client_bundled_curve_baseline") != expected_bundled_curve:
            errors.append(
                "验收回执客户端内置曲线基线不一致:"
                f"receipt={policy.get('client_bundled_curve_baseline')!r},"
                f"expected={expected_bundled_curve!r}")
        diversity = policy.get("curse_diversity")
        if (not isinstance(diversity, dict)
                or diversity.get("schema") != CURSE_DIVERSITY_SCHEMA
                or diversity.get("adjacent_cooldown")
                != "strict_for_deep_armor_and_fields"
                or diversity.get("combo_uses_same_gate") is not True
                or diversity.get("static_verified") is not True
                or diversity.get("runtime_simulated") is not False
                or diversity.get("gameplay_verified") is not False):
            errors.append("验收回执诅咒/领域多样性政策非法")
    inputs = document.get("inputs")
    if not isinstance(inputs, dict):
        return errors + ["验收回执缺 inputs"]
    try:
        rounds = int(inputs["rounds"])
    except (KeyError, TypeError, ValueError):
        return errors + ["验收回执 rounds 非法"]
    if rounds < 2 or not inputs.get("strict_target_hp"):
        errors.append("验收回执不是至少 2 层的 strict_target_hp 构建")
    if ("baseline_includes_curse" in inputs
            and inputs.get("baseline_includes_curse") is not False):
        errors.append("验收回执基础 HP 不得包含诅咒倍率")
    floors = document.get("floors")
    if not isinstance(floors, list):
        return errors + ["验收回执 floors 不是数组"]
    expected_rounds = set(range(1 if document.get("event_id") == "700100" else 2, rounds + 1))
    seen_rounds: set[int] = set()
    recomputed_max_error = 0.0
    special_count = 0

    def number(mapping: dict, key: str, label: str) -> float | None:
        try:
            value = float(mapping[key])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{label} 缺数字字段 {key}")
            return None
        if not math.isfinite(value):
            errors.append(f"{label}.{key} 不是有限数:{value}")
            return None
        return value

    for floor in floors:
        if not isinstance(floor, dict):
            errors.append("floors 含非对象条目")
            continue
        try:
            round_no = int(floor["round"])
        except (KeyError, TypeError, ValueError):
            errors.append("楼层 round 非法")
            continue
        label = f"第{round_no}战"
        if round_no in seen_rounds:
            errors.append(f"{label} 重复回执")
        seen_rounds.add(round_no)
        if not floor.get("verified") or not floor.get("absolute_verified"):
            errors.append(f"{label} 不是绝对可回读证据")
        if floor.get("target_exempt"):
            errors.append(f"{label} 仍是 target_exempt")
        if not floor.get("field") or not floor.get("play_field"):
            errors.append(f"{label} 缺 source/play field")
        if not floor.get("source_bosses") or not floor.get("runtime_bosses"):
            errors.append(f"{label} 缺 source/runtime bosses")
        thumbnail = str(floor.get("thumbnail") or "")
        thumbnail_field = str(floor.get("thumbnail_source_field") or "")
        thumbnail_evidence = floor.get("thumbnail_evidence")
        if (not thumbnail or not thumbnail_field
                or not isinstance(thumbnail_evidence, dict)):
            errors.append(f"{label} 缺 Boss 封面来源证据")
        else:
            expected_asset = quest_thumbnail_asset_logical(thumbnail)
            if thumbnail_evidence.get("schema") != THUMBNAIL_EVIDENCE_SCHEMA:
                errors.append(f"{label} Boss 封面证据 schema 非法")
            if (str(thumbnail_evidence.get("field") or "") != thumbnail_field
                    or str(thumbnail_evidence.get("thumbnail") or "") != thumbnail
                    or str(thumbnail_evidence.get("asset_logical") or "")
                    != expected_asset):
                errors.append(f"{label} Boss 封面字段/资源来源不闭合")
            if thumbnail_evidence.get("source_match") not in {
                    "exact_field", "exact_boss_identity",
                    "exact_boss_visual_identity"}:
                errors.append(f"{label} Boss 封面匹配类型非法")
            if thumbnail_evidence.get("source_match") == "floor_host_quest":
                errors.append(f"{label} Boss 封面只证明 floor host，未证明 Boss 身份")
            if (thumbnail_evidence.get("asset_exists") is not True
                    or thumbnail_evidence.get("static_verified") is not True
                    or thumbnail_evidence.get("runtime_simulated") is not False
                    or thumbnail_evidence.get("gameplay_verified") is not False):
                errors.append(f"{label} Boss 封面静态证据等级非法")
        closures = floor.get("identity_reference_closures", [])
        if not isinstance(closures, list):
            errors.append(f"{label} identity reference closures 不是数组")
            closures = []
        seen_closure_keys: set[tuple[str, str, str]] = set()
        source_bosses = set(map(str, floor.get("source_bosses") or ()))
        runtime_bosses = set(map(str, floor.get("runtime_bosses") or ()))
        for closure_index, closure in enumerate(closures, start=1):
            closure_label = f"{label} identity closure {closure_index}"
            if not isinstance(closure, dict):
                errors.append(f"{closure_label} 不是对象")
                continue
            source_code = str(closure.get("source_code") or "")
            clone_code = str(closure.get("clone_code") or "")
            closure_kind = str(closure.get("kind") or "")
            closure_key = (closure_kind, source_code, clone_code)
            if closure_kind not in {
                    "general_enemy_watch.partner_alias",
                    "general_enemy_watch.routine_alias"}:
                errors.append(f"{closure_label} 闭包类型非法")
            if (not source_code or not clone_code or source_code == clone_code
                    or source_code not in source_bosses
                    or clone_code not in runtime_bosses):
                errors.append(f"{closure_label} source/runtime 代号不闭合")
            if closure_key in seen_closure_keys:
                errors.append(f"{closure_label} 重复")
            seen_closure_keys.add(closure_key)
            if closure_kind == "general_enemy_watch.partner_alias":
                try:
                    source_count = int(closure["source_reference_count"])
                    clone_count = int(closure["clone_reference_count"])
                except (KeyError, TypeError, ValueError):
                    source_count = clone_count = 0
                    errors.append(f"{closure_label} 引用计数非法")
                if (source_count <= 0 or clone_count != source_count
                        or closure.get("verified") is not True):
                    errors.append(f"{closure_label} partner 别名未等价回读")
            elif closure_kind == "general_enemy_watch.routine_alias":
                source_routine = str(
                    closure.get("source_routine_id") or "")
                clone_routine = str(
                    closure.get("clone_routine_id") or "")
                if (not source_routine or not clone_routine
                        or source_routine == clone_routine
                        or not clone_routine.startswith(clone_code)
                        or closure.get("verified") is not True):
                    errors.append(f"{closure_label} routine 别名未等价回读")
        field_receipts = floor.get("field_program_receipts")
        if not isinstance(field_receipts, list) or len(field_receipts) > 1:
            errors.append(f"{label} 领域程序回执数量非法（同一时刻最多一个）")
        else:
            curse_description = str(floor.get("curse_description") or "")
            for field_receipt in field_receipts:
                if not isinstance(field_receipt, dict):
                    errors.append(f"{label} 领域程序回执不是对象")
                    continue
                name = str(field_receipt.get("name") or "")
                description = str(field_receipt.get("description") or "")
                declared_program = str(
                    field_receipt.get("declared_program") or "")
                applied_program = str(field_receipt.get("applied_program") or "")
                if (not name or not description or not declared_program
                        or not applied_program
                        or field_receipt.get("readback_match") is not True
                        or name not in curse_description
                        or description not in curse_description):
                    errors.append(f"{label} 领域文案→程序→克隆行回读不一致")
        adapter = floor.get("adapter")
        if not isinstance(adapter, dict):
            errors.append(f"{label} 缺 adapter")
            continue
        quest_plan = floor.get("quest_hp_multipliers")
        if not isinstance(quest_plan, dict):
            errors.append(f"{label} 缺 c86/c87/c88 独立 HP 回执")
        else:
            expected_columns = {
                "enemy": "c86", "device_or_summon": "c87", "boss": "c88"}
            if (quest_plan.get("columns") != expected_columns
                    or quest_plan.get("has_boss") is not True
                    or quest_plan.get("active_target_class") != "boss"
                    or quest_plan.get("independent_verified") is not True
                    or quest_plan.get("mechanism_budget_separate") is not True):
                errors.append(f"{label} c86/c87/c88 分类/独立性声明非法")
            multiplier_maps: dict[str, dict[str, float]] = {}
            for stage in ("baseline", "final", "table_readback"):
                raw_values = quest_plan.get(stage)
                if (not isinstance(raw_values, dict)
                        or set(raw_values) != set(expected_columns)):
                    errors.append(f"{label} {stage} c86/c87/c88 分类不完整")
                    continue
                try:
                    values = {key: float(value)
                              for key, value in raw_values.items()}
                except (TypeError, ValueError):
                    errors.append(f"{label} {stage} c86/c87/c88 含非数字")
                    continue
                if not all(math.isfinite(value) and value > 0
                           for value in values.values()):
                    errors.append(f"{label} {stage} c86/c87/c88 含非正/非有限值")
                    continue
                multiplier_maps[stage] = values
            if set(multiplier_maps) == {"baseline", "final", "table_readback"}:
                baseline_values = multiplier_maps["baseline"]
                final_values = multiplier_maps["final"]
                table_values = multiplier_maps["table_readback"]
                try:
                    adapter_baseline = float(adapter["baseline_c86"])
                    adapter_final = float(adapter["final_c86"])
                except (KeyError, TypeError, ValueError):
                    adapter_baseline = adapter_final = float("nan")
                if (not math.isclose(baseline_values["boss"], adapter_baseline,
                                     rel_tol=0.0, abs_tol=1e-12)
                        or not math.isclose(final_values["boss"], adapter_final,
                                            rel_tol=0.0, abs_tol=1e-12)):
                    errors.append(f"{label} Boss c88 未命中 adapter 倍率")
                for stage, values in (("baseline", baseline_values),
                                      ("final", final_values)):
                    if (not math.isclose(values["enemy"], 1.0,
                                         rel_tol=0.0, abs_tol=1e-12)
                            or not math.isclose(values["device_or_summon"], 1.0,
                                                rel_tol=0.0, abs_tol=1e-12)):
                        errors.append(f"{label} {stage} 错误捆绑小怪或机制单位 HP")
                if any(not math.isclose(table_values[key], final_values[key],
                                        rel_tol=0.0, abs_tol=1e-12)
                       for key in expected_columns):
                    errors.append(f"{label} 任务行 c86/c87/c88 回读与最终计划不一致")
        try:
            adapter_round = int(adapter.get("round_no"))
        except (TypeError, ValueError):
            adapter_round = 0
        if adapter_round != round_no:
            errors.append(f"{label} adapter.round_no={adapter_round} 不一致")
        channel = str(adapter.get("channel") or "")
        if channel not in {"boss_level", "standard_dsl", "mixed_hp",
                           "special_bundle", "c86"}:
            errors.append(f"{label} HP 通道非法:{channel or '(missing)'}")
        if not adapter.get("absolute_verified"):
            errors.append(f"{label} adapter 未标绝对证据")
        family = str(adapter.get("family") or "")
        capability = floor.get("curse_capability_profile")
        used_capabilities = floor.get("curse_used_capabilities")
        matrix_row = CURSE_CAPABILITY_MATRIX.get((channel, family))
        if matrix_row is None:
            errors.append(f"{label} 未声明诅咒能力矩阵:{channel}/{family}")
        if not isinstance(capability, dict):
            errors.append(f"{label} 缺诅咒能力 profile")
        else:
            declared = capability.get("declared")
            effective = capability.get("effective")
            if (capability.get("schema") != CURSE_CAPABILITY_SCHEMA
                    or capability.get("channel") != channel
                    or capability.get("family") != family):
                errors.append(f"{label} 诅咒能力 profile 身份漂移")
            if matrix_row is not None and declared != matrix_row:
                errors.append(f"{label} 诅咒能力声明与矩阵不一致")
            if (not isinstance(effective, dict)
                    or any(effective.get(axis) not in {True, False}
                           for axis in CURSE_CAPABILITY_AXES)
                    or (isinstance(declared, dict)
                        and any(effective.get(axis) and not declared.get(axis)
                                for axis in CURSE_CAPABILITY_AXES))):
                errors.append(f"{label} 诅咒有效能力轴非法")
            if (not isinstance(used_capabilities, list)
                    or len(set(map(str, used_capabilities)))
                    != len(used_capabilities)
                    or any(str(axis) not in CURSE_CAPABILITY_AXES
                           or not isinstance(effective, dict)
                           or effective.get(str(axis)) is not True
                           for axis in (used_capabilities or ()))):
                errors.append(f"{label} 诅咒实际使用能力越过矩阵")
        if family in SPHERE_SPECS:
            phase_behavior = adapter.get("phase_behavior")
            if (not isinstance(phase_behavior, dict)
                    or phase_behavior.get("verified") is not True):
                errors.append(f"{label} Sphere 缺已验证阶段行为闭包")
            else:
                source_budgets = phase_behavior.get("source")
                final_budgets = phase_behavior.get("final_readback")
                if (not isinstance(source_budgets, list) or not source_budgets
                        or not isinstance(final_budgets, list)
                        or len(final_budgets) != len(source_budgets)):
                    errors.append(f"{label} Sphere 阶段预算源/回读数量漂移")
                else:
                    for budget_index, (source_budget, final_budget) in enumerate(
                            zip(source_budgets, final_budgets), start=1):
                        budget_label = f"{label}阶段预算{budget_index}"
                        if (not isinstance(source_budget, dict)
                                or not isinstance(final_budget, dict)):
                            errors.append(f"{budget_label} 不是对象")
                            continue
                        if (source_budget.get("phase")
                                != final_budget.get("phase")):
                            errors.append(f"{budget_label} phase 漂移")
                        if (source_budget.get("verified") is not True
                                or final_budget.get("verified") is not True):
                            errors.append(f"{budget_label} 未通过行为预算")
                        try:
                            source_parent = float(source_budget["parent_hp"])
                            source_required = float(
                                source_budget["required_damage_hp"])
                            source_available = float(
                                source_budget["available_damage_hp"])
                            final_parent = float(final_budget["parent_hp"])
                            final_required = float(
                                final_budget["required_damage_hp"])
                            final_available = float(
                                final_budget["available_damage_hp"])
                            coverage = float(final_budget["coverage_ratio"])
                            completion_raw = final_budget.get(
                                "completion_count")
                            expected_completion_raw = final_budget.get(
                                "expected_completion_count")
                            completion = (
                                None if completion_raw is None
                                else int(completion_raw))
                            expected_completion = (
                                None if expected_completion_raw is None
                                else int(expected_completion_raw))
                            source_model = str(source_budget.get(
                                "budget_model") or "capped_child_hp")
                            final_model = str(final_budget.get(
                                "budget_model") or "capped_child_hp")
                            source_occurrences = int(source_budget.get(
                                "entity_occurrence_count",
                                len(source_budget.get("entity_ids") or ())))
                            final_occurrences = int(final_budget.get(
                                "entity_occurrence_count",
                                len(final_budget.get("entity_ids") or ())))
                            source_per_entity = int(source_budget.get(
                                "occurrences_per_entity", 1))
                            final_per_entity = int(final_budget.get(
                                "occurrences_per_entity", 1))
                        except (KeyError, TypeError, ValueError):
                            errors.append(f"{budget_label} 缺阶段预算数字")
                            continue
                        numbers = (
                            source_parent, source_required, source_available,
                            final_parent, final_required, final_available,
                            coverage)
                        if (not all(math.isfinite(value) and value > 0
                                   for value in numbers)):
                            errors.append(f"{budget_label} 含非正/非有限预算")
                            continue
                        scale = final_parent / source_parent
                        if (not math.isclose(
                                final_required, source_required * scale,
                                rel_tol=HP_TARGET_REL_TOLERANCE,
                                abs_tol=HP_TARGET_ABS_TOLERANCE)
                                or not math.isclose(
                                    final_available, source_available * scale,
                                    rel_tol=HP_TARGET_REL_TOLERANCE,
                                    abs_tol=HP_TARGET_ABS_TOLERANCE)):
                            errors.append(f"{budget_label} 子体未与父体同比伸缩")
                        if source_model != final_model:
                            errors.append(f"{budget_label} 预算模型漂移")
                        if (source_occurrences <= 0
                                or source_occurrences != final_occurrences
                                or source_per_entity <= 0
                                or source_per_entity != final_per_entity):
                            errors.append(f"{budget_label} 子体实际出现次数漂移")
                        if final_model == "capped_child_hp":
                            if (final_available + max(
                                    HP_TARGET_ABS_TOLERANCE,
                                    final_required * HP_TARGET_REL_TOLERANCE)
                                    < final_required):
                                errors.append(f"{budget_label} 最终可传递伤害不足")
                            if (completion is None
                                    or completion != expected_completion):
                                errors.append(f"{budget_label} 击杀次数语义漂移")
                        elif final_model == "raw_hit_overdamage":
                            if (final_budget.get("overdamage") is not True
                                    or source_budget.get("overdamage") is not True
                                    or completion is not None
                                    or expected_completion is not None):
                                errors.append(
                                    f"{budget_label} 原始伤害溢伤语义漂移")
                        else:
                            errors.append(
                                f"{budget_label} 未知预算模型:{final_model}")
                        if not math.isclose(
                                coverage, final_available / final_required,
                                rel_tol=1e-12, abs_tol=1e-12):
                            errors.append(f"{budget_label} coverage 不能回代")
                errors.extend(_verify_sphere_lifecycle_receipt(
                    label, phase_behavior))
        if channel in {"boss_level", "standard_dsl", "mixed_hp"}:
            damage_contracts = adapter.get("damage_checks")
            if not isinstance(damage_contracts, dict):
                errors.append(f"{label} 缺 DamageCheck 回执")
            else:
                seen_damage_schemas: set[str] = set()
                for code, contract in damage_contracts.items():
                    check_label = f"{label} DamageCheck[{code}]"
                    if not isinstance(contract, dict):
                        errors.append(f"{check_label} 静态契约非法")
                        continue
                    schema = str(contract.get("schema") or "")
                    seen_damage_schemas.add(schema)
                    common_invalid = (
                            contract.get("topology_preserved") is not True
                            or contract.get("absolute_thresholds_preserved") is not True
                            or contract.get("static_verified") is not True
                            or contract.get("runtime_simulated") is not False
                            or contract.get("gameplay_verified") is not False)
                    if schema == STANDARD_DAMAGE_CHECK_SCHEMA:
                        if common_invalid:
                            errors.append(f"{check_label} 静态契约非法")
                            continue
                        checks = contract.get("checks")
                        if (not isinstance(checks, list)
                                or int(contract.get("occurrence_count") or 0)
                                != len(checks)):
                            errors.append(f"{check_label} 出现次数回读不一致")
                            continue
                        for occurrence, check in enumerate(checks, start=1):
                            try:
                                expected = float(
                                    check["source_absolute_threshold_hp"])
                                actual = float(
                                    check["final_absolute_threshold_hp"])
                                error = float(check["absolute_error_hp"])
                                window = float(check["duration_frames"])
                            except (KeyError, TypeError, ValueError):
                                errors.append(
                                    f"{check_label}#{occurrence} 字段非法")
                                continue
                            if (not math.isclose(
                                    error, actual - expected,
                                    rel_tol=1e-12, abs_tol=1e-5)
                                    or abs(error) > max(
                                        1e-4, abs(expected) * 1e-12)
                                    or window <= 0
                                    or check.get("success_branch") is None
                                    or check.get("timeout_branch") is None):
                                errors.append(
                                    f"{check_label}#{occurrence} "
                                    "绝对门槛/窗口/分支漂移")
                        continue
                    if schema != GENERAL_DAMAGE_CHECK_SCHEMA:
                        errors.append(f"{check_label} DamageCheck schema 未知")
                        continue
                    if (common_invalid
                            or contract.get(
                                "non_percentage_columns_preserved") is not True
                            or contract.get("materialized") is not True
                            or contract.get(
                                "enemy_watch_lookup_preserved") is not True):
                        errors.append(f"{check_label} 静态契约非法")
                        continue
                    checks = contract.get("checks")
                    if (not isinstance(checks, list)
                            or int(contract.get("occurrence_count") or 0)
                            != len(checks)
                            or bool(contract.get("routine_cloned")) != bool(checks)):
                        errors.append(f"{check_label} 出现次数/routine 回读不一致")
                        continue
                    if checks and not str(
                            contract.get("final_routine_id") or "").startswith(
                                f"{PRIVATE_PREFIX}boss"):
                        errors.append(f"{check_label} 未落私有 c42 routine")
                    for occurrence, check in enumerate(checks, start=1):
                        try:
                            expected = float(
                                check["source_absolute_threshold_hp"])
                            baseline = float(
                                check["baseline_absolute_threshold_hp"])
                            actual = float(
                                check["final_absolute_threshold_hp"])
                            baseline_error = float(
                                check["baseline_absolute_error_hp"])
                            final_error = float(
                                check["final_absolute_error_hp"])
                            options = check["options_c17_c21"]
                        except (KeyError, TypeError, ValueError):
                            errors.append(
                                f"{check_label}#{occurrence} 字段非法")
                            continue
                        tolerance = max(1e-4, abs(expected) * 1e-12)
                        if (not math.isclose(
                                baseline_error, baseline - expected,
                                rel_tol=1e-12, abs_tol=1e-5)
                                or not math.isclose(
                                    final_error, actual - expected,
                                    rel_tol=1e-12, abs_tol=1e-5)
                                or abs(baseline_error) > tolerance
                                or abs(final_error) > tolerance
                                or not isinstance(options, list)
                                or len(options) != 5):
                            errors.append(
                                f"{check_label}#{occurrence} "
                                "基础/诅咒后绝对门槛或状态选项漂移")
                expected_schemas = (
                    {GENERAL_DAMAGE_CHECK_SCHEMA}
                    if channel == "boss_level" else
                    {STANDARD_DAMAGE_CHECK_SCHEMA}
                    if channel == "standard_dsl" else
                    {GENERAL_DAMAGE_CHECK_SCHEMA,
                     STANDARD_DAMAGE_CHECK_SCHEMA})
                if seen_damage_schemas != expected_schemas:
                    errors.append(
                        f"{label} DamageCheck 通道覆盖漂移:"
                        f"expected={sorted(expected_schemas)},"
                        f"actual={sorted(seen_damage_schemas)}")
        baseline_target = number(adapter, "baseline_target_hp", label)
        final_target = number(adapter, "final_target_hp", label)
        baseline_readback = number(adapter, "baseline_readback_hp", label)
        final_readback = number(adapter, "final_readback_hp", label)
        baseline_error = number(adapter, "baseline_error_hp", label)
        final_error = number(adapter, "final_error_hp", label)
        abs_tolerance = number(adapter, "abs_tolerance_hp", label)
        rel_tolerance = number(adapter, "rel_tolerance", label)
        numeric = (baseline_target, final_target, baseline_readback,
                   final_readback, baseline_error, final_error,
                   abs_tolerance, rel_tolerance)
        if any(value is None for value in numeric):
            continue
        assert all(value is not None for value in numeric)
        curse_hp = (number(floor, "curse_hp_multiplier", label)
                    if "curse_hp_multiplier" in floor else None)
        if (curse_hp is None
                and inputs.get("hp_profile") in {"linear_boss_hp_30e8_150e8", "normal_boss_hp_20e8_100e8", "ex_tiered_boss_hp"}):
            errors.append(f"{label} 线性 HP 回执缺 curse_hp_multiplier")
        if curse_hp is not None:
            if curse_hp <= 0:
                errors.append(f"{label} curse_hp_multiplier 必须为正数")
            elif not math.isclose(
                    final_target, baseline_target * curse_hp,
                    rel_tol=1e-12, abs_tol=1e-4):
                errors.append(
                    f"{label} final target 未等于基础HP×诅咒倍率:"
                    f"{final_target:g}!={baseline_target:g}×{curse_hp:g}")
            if (family in SPHERE_SPECS
                    and not math.isclose(
                        curse_hp, 1.0, rel_tol=0.0, abs_tol=1e-12)):
                errors.append(f"{label} Sphere 违反能力矩阵使用了 HP 诅咒")
        if min(baseline_target, final_target, baseline_readback,
               final_readback, abs_tolerance) <= 0 or rel_tolerance < 0:
            errors.append(f"{label} adapter 含非正目标/回读/容差")
        components = adapter.get("components")
        if not isinstance(components, list) or not components:
            errors.append(f"{label} adapter 缺组件")
            continue
        component_baseline_targets: list[float] = []
        component_final_targets: list[float] = []
        component_baseline_readbacks: list[float] = []
        component_final_readbacks: list[float] = []
        phases: list[str] = []
        for expected_occurrence, component in enumerate(components, start=1):
            component_label = f"{label}组件{expected_occurrence}"
            if not isinstance(component, dict):
                errors.append(f"{component_label} 不是对象")
                continue
            if component.get("evidence_kind") != "absolute":
                errors.append(f"{component_label} 不是绝对证据")
            if int(component.get("occurrence") or 0) != expected_occurrence:
                errors.append(f"{component_label} occurrence 不连续")
            if not component.get("code") or not component.get("readback_code"):
                errors.append(f"{component_label} 缺源/回读代号")
            if not component.get("source") or not component.get("destination"):
                errors.append(f"{component_label} 缺证据源/落表目标")
            phases.append(str(component.get("phase") or ""))
            cb_target = number(component, "baseline_target_hp", component_label)
            cf_target = number(component, "final_target_hp", component_label)
            cb_readback = number(component, "baseline_readback_hp", component_label)
            cf_readback = number(component, "final_readback_hp", component_label)
            cb_error = number(component, "baseline_error_hp", component_label)
            cf_error = number(component, "final_error_hp", component_label)
            if any(value is None for value in (
                    cb_target, cf_target, cb_readback, cf_readback,
                    cb_error, cf_error)):
                continue
            assert all(value is not None for value in (
                cb_target, cf_target, cb_readback, cf_readback,
                cb_error, cf_error))
            if not math.isclose(cb_error, cb_readback - cb_target,
                                rel_tol=1e-12, abs_tol=1e-5):
                errors.append(f"{component_label} baseline error 不能回代")
            if not math.isclose(cf_error, cf_readback - cf_target,
                                rel_tol=1e-12, abs_tol=1e-5):
                errors.append(f"{component_label} final error 不能回代")
            if abs(cb_error) > max(abs_tolerance, abs(cb_target) * rel_tolerance):
                errors.append(f"{component_label} baseline 回读超差")
            if abs(cf_error) > max(abs_tolerance, abs(cf_target) * rel_tolerance):
                errors.append(f"{component_label} final 回读超差")
            component_baseline_targets.append(cb_target)
            component_final_targets.append(cf_target)
            component_baseline_readbacks.append(cb_readback)
            component_final_readbacks.append(cf_readback)
        sums = (
            (component_baseline_targets, baseline_target, "baseline target"),
            (component_final_targets, final_target, "final target"),
            (component_baseline_readbacks, baseline_readback, "baseline readback"),
            (component_final_readbacks, final_readback, "final readback"),
        )
        for values, claimed, name in sums:
            if len(values) != len(components) or not math.isclose(
                    math.fsum(values), claimed, rel_tol=1e-12, abs_tol=1e-4):
                errors.append(f"{label} {name} 与组件和不一致")
        if not math.isclose(baseline_error, baseline_readback - baseline_target,
                            rel_tol=1e-12, abs_tol=1e-5):
            errors.append(f"{label} baseline 总误差不能回代")
        if not math.isclose(final_error, final_readback - final_target,
                            rel_tol=1e-12, abs_tol=1e-5):
            errors.append(f"{label} final 总误差不能回代")
        within = (
            abs(baseline_error) <= max(abs_tolerance,
                                       abs(baseline_target) * rel_tolerance)
            and abs(final_error) <= max(abs_tolerance,
                                        abs(final_target) * rel_tolerance))
        if not within or adapter.get("within_tolerance") is not True:
            errors.append(f"{label} adapter 未命中明确容差")
        recomputed_max_error = max(
            recomputed_max_error, abs(baseline_error), abs(final_error))
        if channel == "special_bundle":
            special_count += 1
            if adapter.get("family") == "orochi":
                mechanism = adapter.get("mechanism_budget")
                if len(components) != 1 or phases != ["parent"]:
                    errors.append(
                        f"{label} Orochi 严格目标必须只有中央 parent 胜利血条")
                if (not isinstance(mechanism, dict)
                        or mechanism.get("kind") != "orochi_heads"
                        or mechanism.get("counts_toward_boss_target") is not False
                        or int(mechanism.get("occurrences") or 0) != 8
                        or mechanism.get("static_verified") is not True
                        or mechanism.get("runtime_simulated") is not False
                        or mechanism.get("gameplay_verified") is not False):
                    errors.append(f"{label} Orochi 八蛇头机制预算证据非法")
            elif adapter.get("family") == "orochi_ex":
                if (len(components) != 3
                        or phases != [f"phase[{i}]" for i in range(1, 4)]):
                    errors.append(
                        f"{label} Orochi EX 必须是 phase[1..3] 三组件")
                errors.extend(_verify_orochi_ex_phase_safety_receipt(
                    label, adapter))
            elif adapter.get("family") in SINGLE_BAR_SPECIAL_SPECS:
                if len(components) != 1 or phases != ["main"]:
                    errors.append(
                        f"{label} {adapter.get('family')} 必须是 main 单胜利血条")
            elif adapter.get("family") in SPHERE_SPECS:
                expected_gate_count = sum(
                    len(entry.get("level_columns") or ())
                    for entry in SPHERE_SPECS[adapter["family"]].get("embedded") or ()
                    if entry.get("victory")) + sum(
                    len(entry.get("id_columns") or ())
                    for entry in SPHERE_SPECS[adapter["family"]].get("aux_groups") or ()
                    if entry.get("victory"))
                if (len(components) != expected_gate_count + 1
                        or phases[-1:] != ["main"]
                        or any("crystal" not in phase
                               for phase in phases[:-1])):
                    errors.append(
                        f"{label} {adapter.get('family')} Sphere 胜利组件闭包漂移")
            else:
                errors.append(f"{label} 未知 special_bundle family")
    if seen_rounds != expected_rounds:
        errors.append(
            "Boss 回执轮次不完整:missing="
            + ",".join(map(str, sorted(expected_rounds - seen_rounds)))
            + ";extra=" + ",".join(map(str, sorted(seen_rounds - expected_rounds))))
    chain = document.get("chain_reports")
    if not isinstance(chain, list):
        errors.append("验收回执 chain_reports 不是数组")
        chain = []
    chain_failures = [report for report in chain
                      if not isinstance(report, dict) or not report.get("ok")]
    if len(chain) != rounds + 1:
        errors.append(f"解析链回执数量 {len(chain)} != rounds+endless {rounds + 1}")
    if chain_failures:
        errors.append(f"解析链仍有 {len(chain_failures)} 条失败")
    summary = document.get("summary")
    if not isinstance(summary, dict):
        errors.append("验收回执缺 summary")
        return errors
    expected_summary = {
        "expected_boss_rounds": len(expected_rounds),
        "audited_boss_rounds": len(floors),
        "absolute_boss_rounds": sum(
            1 for floor in floors
            if isinstance(floor, dict) and floor.get("absolute_verified")),
        "proxy_components": sum(
            1 for floor in floors if isinstance(floor, dict)
            for component in ((floor.get("adapter") or {}).get("components") or [])
            if isinstance(component, dict)
            and component.get("evidence_kind") != "absolute"),
        "source_proxy_components": sum(
            1 for floor in floors if isinstance(floor, dict)
            for component in ((floor.get("adapter") or {}).get("components") or [])
            if isinstance(component, dict)
            and component.get(
                "source_evidence_kind",
                component.get("evidence_kind")) != "absolute"),
        "target_exempt_rounds": sum(
            1 for floor in floors
            if isinstance(floor, dict) and floor.get("target_exempt")),
        "special_bundle_rounds": special_count,
        "identity_reference_closure_rounds": sum(
            1 for floor in floors if isinstance(floor, dict)
            and floor.get("identity_reference_closures")),
        "identity_reference_closures": sum(
            len(floor.get("identity_reference_closures") or ())
            for floor in floors if isinstance(floor, dict)),
        "baseline_first_boss_hp": (
            float(floors[0]["adapter"]["baseline_target_hp"])
            if floors and isinstance(floors[0], dict) else 0.0),
        "baseline_last_boss_hp": (
            float(floors[-1]["adapter"]["baseline_target_hp"])
            if floors and isinstance(floors[-1], dict) else 0.0),
        "baseline_strictly_increasing": all(
            float(current["adapter"]["baseline_target_hp"])
            > float(previous["adapter"]["baseline_target_hp"])
            for previous, current in zip(floors, floors[1:])
            if isinstance(previous, dict) and isinstance(current, dict)),
        "chain_reports": len(chain),
        "chain_failures": len(chain_failures),
        "thumbnail_static_verified_floors": sum(
            1 for floor in floors if isinstance(floor, dict)
            and isinstance(floor.get("thumbnail_evidence"), dict)
            and floor["thumbnail_evidence"].get("static_verified") is True),
    }
    # source_proxy_components was added without changing the receipt schema.
    # Older schema-v2 receipts remain independently verifiable: when the field
    # is absent, final evidence is the only source evidence they recorded.
    if "source_proxy_components" not in summary:
        expected_summary.pop("source_proxy_components")
    for optional_key in (
            "baseline_first_boss_hp", "baseline_last_boss_hp",
            "baseline_strictly_increasing"):
        if optional_key not in summary:
            expected_summary.pop(optional_key)
    for key, value in expected_summary.items():
        if summary.get(key) != value:
            errors.append(f"summary.{key}={summary.get(key)!r}，回算应为 {value}")
    summary_max = number(summary, "max_absolute_error_hp", "summary")
    if summary_max is not None and not math.isclose(
            summary_max, recomputed_max_error, rel_tol=1e-12, abs_tol=1e-5):
        errors.append(
            f"summary.max_absolute_error_hp={summary_max:g}，"
            f"回算应为 {recomputed_max_error:g}")
    if inputs.get("hp_profile") in {"linear_boss_hp_30e8_150e8", "normal_boss_hp_20e8_100e8", "ex_tiered_boss_hp"}:
        for floor in floors:
            if not isinstance(floor, dict) or not isinstance(floor.get("adapter"), dict):
                continue
            round_no = int(floor["round"])
            actual_target = float(floor["adapter"]["baseline_target_hp"])
            expected_target = (
                float(abyss_modes.base_hp("ex", round_no)) if inputs["hp_profile"] == "ex_tiered_boss_hp" else
                float(abyss_modes.base_hp("normal", round_no))
                if inputs["hp_profile"] == "normal_boss_hp_20e8_100e8" else
                15_000_000_000.0 if rounds == 2 else
                3_000_000_000.0 + (round_no - 2) * 12_000_000_000.0 / (rounds - 2))
            if not math.isclose(
                    actual_target, expected_target, rel_tol=1e-12, abs_tol=1e-4):
                errors.append(
                    f"第{round_no}战基础HP {actual_target:g} 未命中"
                    f"线性梯度 {expected_target:g}")
    return errors


def write_hp_audit_document(path: str, document: dict) -> None:
    """Atomically write one explicitly requested audit path (or stdout '-')."""
    rendered = json.dumps(
        document, ensure_ascii=False, sort_keys=True, indent=2,
        allow_nan=False) + "\n"
    if path == "-":
        print(rendered, end="")
        return
    target = Path(path).expanduser().resolve()
    if not target.parent.is_dir():
        raise ValueError(f"验收回执父目录不存在:{target.parent}")
    temporary = target.with_name(target.name + ".tmp-wf-rogue-audit")
    temporary.write_text(rendered, encoding="utf-8", newline="\n")
    os.replace(temporary, target)


def _hp_audit_markdown_cell(value) -> str:
    """Escape one compact value for a deterministic Markdown table cell."""

    return (str(value).replace("\\", "\\\\").replace("|", "\\|")
            .replace("\r", " ").replace("\n", " "))


def render_hp_audit_report(
        document: dict, *, expected_tool_sha256: str | None = None) -> str:
    """Render a verified strict receipt as a non-developer Chinese report.

    The renderer refuses an invalid or stale-tool document.  Consequently the
    green conclusion is derived from the same arithmetic/policy/chain proof as
    ``--verify-audit-json`` rather than from untrusted plan text.
    """

    errors = verify_hp_audit_document(
        document, expected_tool_sha256=expected_tool_sha256)
    if errors:
        raise ValueError("验收回执未通过，拒绝生成绿色报告:" + "；".join(errors))
    inputs = document["inputs"]
    summary = document["summary"]
    curve_baseline = document["selection_policy"][
        "client_bundled_curve_baseline"]
    source_proxy_components = int(summary.get(
        "source_proxy_components", summary["proxy_components"]))
    floors = list(document["floors"])
    family_counts: dict[str, int] = {}
    channel_counts: dict[str, int] = {}
    for floor in floors:
        adapter = floor["adapter"]
        family = str(adapter["family"])
        channel = str(adapter["channel"])
        family_counts[family] = family_counts.get(family, 0) + 1
        channel_counts[channel] = channel_counts.get(channel, 0) + 1

    def floor_error(floor: dict) -> float:
        adapter = floor["adapter"]
        return max(abs(float(adapter["baseline_error_hp"])),
                   abs(float(adapter["final_error_hp"])))

    worst = sorted(floors, key=lambda floor: (
        -floor_error(floor), int(floor["round"])))[:10]
    baseline_first = float(summary.get(
        "baseline_first_boss_hp", floors[0]["adapter"]["baseline_target_hp"]))
    baseline_last = float(summary.get(
        "baseline_last_boss_hp", floors[-1]["adapter"]["baseline_target_hp"]))
    baseline_increasing = bool(summary.get(
        "baseline_strictly_increasing",
        all(float(current["adapter"]["baseline_target_hp"])
            > float(previous["adapter"]["baseline_target_hp"])
            for previous, current in zip(floors, floors[1:]))))
    lines = [
        "# 深渊连战 Boss HP 验收报告",
        "",
        "> 结论：**静态严格验收通过**。本报告证明本次构建的表结构、HP 回读公式、"
        "逐组件目标和解析链均通过门禁；**它不等同于真机实战验证，也不证明已经发布或落库**。",
        "",
        "## 一眼结论",
        "",
        f"- 种子：`{int(inputs['seed'])}`；层数：`{int(inputs['rounds'])}`；"
         f"难度：`{_hp_audit_markdown_cell(inputs['difficulty'])}`；"
         f"敌等级：`{_hp_audit_markdown_cell(inputs['enemy_level'])}`",
        f"- HP profile：`{_hp_audit_markdown_cell(inputs.get('hp_profile', 'unspecified'))}`；"
        f"诅咒前基础总HP：`{baseline_first / 100_000_000:g}亿→"
        f"{baseline_last / 100_000_000:g}亿`；"
        f"严格递增：`{'是' if baseline_increasing else '否'}`；"
        "血量诅咒：`基础目标之后单独应用`",
        f"- Boss 关绝对证据：`{int(summary['absolute_boss_rounds'])}/"
        f"{int(summary['expected_boss_rounds'])}`",
        f"- 最终代理组件：`{int(summary['proxy_components'])}`；"
        f"源代理组件：`{source_proxy_components}`；"
        f"未归一豁免：`{int(summary['target_exempt_rounds'])}`；"
        f"解析链失败：`{int(summary['chain_failures'])}`",
        f"- 最大绝对回读误差：`{float(summary['max_absolute_error_hp']):g} HP`",
        f"- identity 引用闭包："
        f"`{int(summary.get('identity_reference_closures', 0))}` 个，"
        f"覆盖 `{int(summary.get('identity_reference_closure_rounds', 0))}` 关",
        f"- Boss 封面静态来源闭包："
        f"`{int(summary['thumbnail_static_verified_floors'])}/"
        f"{int(summary['expected_boss_rounds'])}`",
        f"- 客户端内置 HP 曲线基线："
        f"`{curve_baseline['member_sha256']}`（"
        f"{int(curve_baseline['cross_checked_client_baselines'])} 份客户端交叉核对）",
        f"- 验证范围：`{document['verification_scope']}`；"
        "真机实战验证：`否（gameplay_verified=false）`",
        f"- 回执 SHA-256：`{document['document_sha256']}`",
        f"- 工具 SHA-256：`{document['tool']['sha256']}`",
        "",
        "## 放行红线",
        "",
        "- [x] 每个 Boss 关都有绝对 HP 证据",
        "- [x] 代理证据、target_exempt 与解析链失败均为 0",
        "- [x] 每个组件及整关回读均在回执声明的明确容差内",
        "- [x] Boss 重抽/原生专场政策与当前工具一致",
        "- [ ] 真机进入关卡、阶段切换与胜利结算（本报告无法替代）",
        "",
        "## 覆盖分布",
        "",
        "| 维度 | 数量 |",
        "|---|---:|",
    ]
    lines.extend(
        f"| family `{_hp_audit_markdown_cell(name)}` | {count} |"
        for name, count in sorted(family_counts.items()))
    lines.extend(
        f"| channel `{_hp_audit_markdown_cell(name)}` | {count} |"
        for name, count in sorted(channel_counts.items()))
    lines.extend([
        "",
        "## 逐关逐阶段明细",
        "",
        "第 1 战是无 Boss 小怪房，不进入 Boss HP 绝对证据计数。以下基础 HP 是诅咒前目标，"
        "最终 HP 是血量诅咒之后的目标；阶段栏按实际出现次数列出每个胜利条件组件。",
        "",
        "| 层 | family / 通道 | Boss | 阶段组件（阶段: 最终目标 / 回读 / 误差） | 基础→最终总HP | 诅咒（HP倍率） |",
        "|---:|---|---|---|---:|---|",
    ])
    for floor in floors:
        adapter = floor["adapter"]
        bosses = "、".join(map(str, floor["source_bosses"]))
        components = "<br>".join(
            f"{_hp_audit_markdown_cell(component.get('code') or '?')} "
            f"[{_hp_audit_markdown_cell(component.get('phase') or 'main')}]: "
            f"{float(component['final_target_hp']):g} / "
            f"{float(component['final_readback_hp']):g} / "
            f"{float(component['final_error_hp']):g}"
            for component in adapter["components"])
        curse_description = str(floor.get("curse_description") or "")
        if not curse_description:
            curse_names = list(map(str, floor.get("curse_names") or ()))
            curse_description = "、".join(curse_names) if curse_names else "（无）"
        lines.append(
            f"| {int(floor['round'])} | "
            f"`{_hp_audit_markdown_cell(adapter['family'])}` / "
            f"`{_hp_audit_markdown_cell(adapter['channel'])}` | "
            f"{_hp_audit_markdown_cell(bosses)} | {components} | "
            f"{float(adapter['baseline_target_hp']):g}→"
            f"{float(adapter['final_target_hp']):g} | "
            f"{_hp_audit_markdown_cell(curse_description)} "
            f"(×{float(floor['curse_hp_multiplier']):g}) |")
    lines.extend([
        "",
        "## Boss 封面静态审计",
        "",
        "封面按实际 Boss 来源场地解析官方 240×188 quest 大图；混搭层不使用地形 "
        "donor 的图片。资源存在性已在构建期回读，但这仍不等于真机 UI 验证。",
        "",
        "| 层 | Boss 来源场地 | quest c5 封面 | 证据 |",
        "|---:|---|---|---|",
    ])
    for floor in floors:
        evidence = floor["thumbnail_evidence"]
        source = (
            f"{evidence['source_category']}:"
            f"{evidence['source_match']}"
        )
        lines.append(
            f"| {int(floor['round'])} | "
            f"`{_hp_audit_markdown_cell(floor['thumbnail_source_field'])}` | "
            f"`{_hp_audit_markdown_cell(floor['thumbnail'])}` | "
            f"{_hp_audit_markdown_cell(source)} |")
    lines.extend([
        "",
        "## 最大误差楼层（最多 10 层）",
        "",
        "| 层 | family | Boss | 阶段组件 | 目标 HP（基线→实战） | 回读 HP（基线→实战） | 最大绝对误差 HP | 通道 |",
        "|---:|---|---|---:|---:|---:|---:|---|",
    ])
    for floor in worst:
        adapter = floor["adapter"]
        bosses = "、".join(map(str, floor["source_bosses"]))
        lines.append(
            f"| {int(floor['round'])} | "
            f"`{_hp_audit_markdown_cell(adapter['family'])}` | "
            f"{_hp_audit_markdown_cell(bosses)} | "
            f"{len(adapter['components'])} | "
            f"{float(adapter['baseline_target_hp']):g}→"
            f"{float(adapter['final_target_hp']):g} | "
            f"{float(adapter['baseline_readback_hp']):g}→"
            f"{float(adapter['final_readback_hp']):g} | "
            f"{floor_error(floor):g} | "
            f"`{_hp_audit_markdown_cell(adapter['channel'])}` |")
    lines.extend([
        "",
        "## 当前保守边界",
        "",
        "无法证明身份引用闭包、阶段胜利条件或资源完整性的 Boss 不会被包装成成功；"
        "严格模式会重抽或明确失败。继续增加新家族只提升阵容多样性，不是本报告放行的必要条件。",
        "",
        "## 建议",
        "",
        "此报告适合作为 dry-run、代码审查和金丝雀前置凭据。若要把结论提升为“可正式游玩”，"
        "仍应至少真机抽测普通 Hit/Fix、Standard DSL、多阶段专用 Boss 与 Sphere 各一关。",
        "",
    ])
    return "\n".join(lines)


def write_hp_audit_report(path: str, document: dict, *,
                          expected_tool_sha256: str | None = None) -> None:
    """Atomically write a verified human-readable Markdown audit report."""

    rendered = render_hp_audit_report(
        document, expected_tool_sha256=expected_tool_sha256)
    if path == "-":
        print(rendered, end="")
        return
    target = Path(path).expanduser().resolve()
    if not target.parent.is_dir():
        raise ValueError(f"验收报告父目录不存在:{target.parent}")
    temporary = target.with_name(target.name + ".tmp-wf-rogue-report")
    temporary.write_text(rendered, encoding="utf-8", newline="\n")
    os.replace(temporary, target)


@dataclass(frozen=True)
class OrochiCloneResult:
    ok: bool
    parent_code: str | None = None
    head_codes: tuple[str, ...] = ()
    clone_map: tuple[tuple[rbb.BossRef, rbb.BossRef], ...] = ()
    bundle: rbb.NativeBossBundle | None = None
    expanded: HpExpansionResult | None = None
    touched_tables: tuple[str, ...] = ()
    reason: str | None = None
    detail: str = ""


@dataclass(frozen=True)
class OrochiExGraph:
    """Exact kind-4 parent and six-child closure selected by one native field."""

    ok: bool
    parent_ref: rbb.BossRef | None = None
    selected_level: int | None = None
    child_codes: tuple[str, ...] = ()
    reason: str | None = None
    detail: str = ""


@dataclass(frozen=True)
class OrochiExCloneResult:
    ok: bool
    parent_code: str | None = None
    head_codes: tuple[str, ...] = ()
    clone_map: tuple[tuple[rbb.BossRef, rbb.BossRef], ...] = ()
    bundle: rbb.NativeBossBundle | None = None
    evidence: dict | None = None
    touched_tables: tuple[str, ...] = ()
    reason: str | None = None
    detail: str = ""


@dataclass(frozen=True)
class SingleBarSpecialGraph:
    """One dedicated parent whose only victory HP is boss_level-backed."""

    ok: bool
    family: str | None = None
    parent_ref: rbb.BossRef | None = None
    selected_level: int | None = None
    action_roots: tuple[str, ...] = ()
    auxiliary_refs: tuple[str, ...] = ()
    reason: str | None = None
    detail: str = ""


@dataclass(frozen=True)
class SingleBarSpecialCloneResult:
    ok: bool
    family: str | None = None
    parent_code: str | None = None
    clone_map: tuple[tuple[rbb.BossRef, rbb.BossRef], ...] = ()
    bundle: rbb.NativeBossBundle | None = None
    evidence: dict | None = None
    touched_tables: tuple[str, ...] = ()
    reason: str | None = None
    detail: str = ""


@dataclass(frozen=True)
class SphereAuxiliaryRef:
    """One exact Sphere child occurrence and its client role."""

    entity_id: str
    level_code: str
    selected_level: int
    phase: str
    role: str
    source_table: str
    victory_component: bool = False
    native_hp: float | None = None


@dataclass(frozen=True)
class SpherePhaseBudget:
    """Auditable damage budget for one child-mediated Sphere transition."""

    phase: str
    entry_ratio: float
    exit_ratio: float
    parent_hp: float
    required_damage_hp: float
    available_damage_hp: float
    coverage_ratio: float
    completion_count: int | None
    expected_completion_count: int | None
    entity_ids: tuple[str, ...]
    level_codes: tuple[str, ...]
    occurrences_per_entity: int
    entity_occurrence_count: int
    overdamage: bool
    budget_model: str
    verified: bool


@dataclass(frozen=True)
class SphereLifecycleStep:
    """One statically proved progress edge in the four-phase Sphere client."""

    sequence: int
    source_phase: int
    target_phase: int | None
    trigger: str
    threshold_ratio: float | None
    member_phases: tuple[str, ...]
    expected_entities: int
    expected_completion_count: int | None
    entity_ids: tuple[str, ...]
    budget_phase: str | None
    next_state_entry: str
    verified: bool


@dataclass(frozen=True)
class SphereLifecycleProof:
    """Static liveness contract; deliberately not a gameplay simulation."""

    family: str
    steps: tuple[SphereLifecycleStep, ...]
    victory_component_count: int
    client_contract: str
    static_verified: bool
    runtime_simulated: bool = False
    gameplay_verified: bool = False


@dataclass(frozen=True)
class SphereGraph:
    """One Sphere parent plus every constructor-created child occurrence."""

    ok: bool
    family: str | None = None
    parent_ref: rbb.BossRef | None = None
    selected_level: int | None = None
    parent_hp_kind: str | None = None
    auxiliaries: tuple[SphereAuxiliaryRef, ...] = ()
    phase_budgets: tuple[SpherePhaseBudget, ...] = ()
    lifecycle: SphereLifecycleProof | None = None
    behavior_verified: bool = False
    action_roots: tuple[str, ...] = ()
    action_closure: tuple[str, ...] = ()
    reason: str | None = None
    detail: str = ""


@dataclass(frozen=True)
class SphereCloneResult:
    ok: bool
    family: str | None = None
    parent_code: str | None = None
    clone_map: tuple[tuple[rbb.BossRef, rbb.BossRef], ...] = ()
    bundle: rbb.NativeBossBundle | None = None
    evidence: dict | None = None
    touched_tables: tuple[str, ...] = ()
    reason: str | None = None
    detail: str = ""
