# Source section of rogue_build; loaded in its shared module namespace.
def orochi_hp_scale_plan(native: dict, boss_level: dict, *, target_hp: float,
                         curse_hp: float) -> dict:
    """Plan central victory HP and a separate eight-head mechanism budget.

    The parent alone must hit the strict floor target.  Heads follow the same
    safe relative scale so the official encounter topology remains usable, but
    their HP is never added to ``baseline_true_hp``/``true_hp``.  Baseline and
    curse-final targets stay separate so HP curses cannot be applied twice.
    """
    components = list(native.get("components") or [])
    mechanism_components = list(native.get("mechanism_components") or [])
    if (not native.get("verified") or not native.get("absolute_verified")
            or len(components) != 1 or len(mechanism_components) != 8
            or components[0].get("phase") != "parent"
            or any(component.get("special_family") != "orochi"
                   for component in components + mechanism_components)):
        raise ValueError(
            "Orochi HP 伸缩缺中央胜利血条/八蛇头机制预算绝对证据:"
            f"{native.get('reason') or 'unknown'}")
    try:
        wanted = float(target_hp)
        hp_mult = float(curse_hp)
        native_total = float(components[0]["native_hp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Orochi HP 伸缩输入含非数字") from exc
    if not all(math.isfinite(value) and value > 0
               for value in (wanted, hp_mult, native_total)):
        raise ValueError(
            f"Orochi HP 伸缩输入非法:target={target_hp},"
            f"curse={curse_hp},native={native_total}")
    baseline_scale = wanted / native_total
    final_scale = baseline_scale * hp_mult
    factor_cache: dict[tuple[str, float], float] = {}

    def realized_factor(code: str, requested: float) -> float:
        key = (code, requested)
        if key in factor_cache:
            return factor_cache[key]
        source_leaf = boss_level.get(code)
        if source_leaf is None:
            raise ValueError(f"Orochi boss_level[{code}] 缺失")
        row = cells(source_leaf)
        if len(row) < 13 or row[0] != "0":
            raise ValueError(f"Orochi boss_level[{code}] 不是 Hit c2 行")
        old_c2 = float(row[2])
        staged = clone_hit_boss_level_c2(source_leaf, requested)
        factor_cache[key] = float(cells(staged)[2]) / old_c2
        return factor_cache[key]

    baseline_component_hp = tuple(
        float(component["native_hp"]) * realized_factor(
            str(component["code"]), baseline_scale)
        for component in components)
    final_component_hp = tuple(
        float(component["native_hp"]) * realized_factor(
            str(component["code"]), final_scale)
        for component in components)
    baseline_mechanism_hp = tuple(
        float(component["native_hp"]) * realized_factor(
            str(component["code"]), baseline_scale)
        for component in mechanism_components)
    final_mechanism_hp = tuple(
        float(component["native_hp"]) * realized_factor(
            str(component["code"]), final_scale)
        for component in mechanism_components)
    ordered_codes = list(dict.fromkeys(
        str(component["code"])
        for component in components + mechanism_components))
    selected_levels = {
        code: int(next(component["selected_level"]
                       for component in components + mechanism_components
                       if str(component["code"]) == code))
        for code in ordered_codes
    }
    destinations = {
        code: (f"{OROCHI}.c24 + {BOSS_LEVEL}.c2"
               if index == 0 else f"{BOSS_LEVEL}.c2")
        for index, code in enumerate(ordered_codes)
    }
    return {
        "channel": "special_bundle", "family": "orochi",
        "c86": 1.0, "curse_hp": hp_mult,
        "baseline_scale": baseline_scale, "final_scale": final_scale,
        "baseline_component_hp": baseline_component_hp,
        "final_component_hp": final_component_hp,
        "baseline_true_hp": math.fsum(baseline_component_hp),
        "true_hp": math.fsum(final_component_hp),
        "mechanism_budget": {
            "kind": "orochi_heads",
            "counts_toward_boss_target": False,
            "victory_condition": "central_parent_only",
            "source_components": tuple(
                float(component["native_hp"])
                for component in mechanism_components),
            "baseline_components": baseline_mechanism_hp,
            "final_components": final_mechanism_hp,
            "source_hp": math.fsum(
                float(component["native_hp"])
                for component in mechanism_components),
            "baseline_hp": math.fsum(baseline_mechanism_hp),
            "final_hp": math.fsum(final_mechanism_hp),
            "occurrences": len(mechanism_components),
            "static_verified": True,
            "runtime_simulated": False,
            "gameplay_verified": False,
        },
        "selected_levels": selected_levels,
        "destinations": destinations,
    }


def orochi_ex_hp_scale_plan(native: dict, dedicated: dict, boss_level: dict, *,
                            target_hp: float, curse_hp: float) -> dict:
    """Plan all three Orochi EX bars without overflowing client ``int`` HP.

    The first and third bars are ActionScript ``int`` fields while the middle
    bar is a floating ``boss_level.c2`` channel.  Uniform scaling is retained
    while both fixed bars fit signed int32; above that boundary, the fixed
    scale is capped and the middle bar absorbs the remaining target HP.
    """
    components = list(native.get("components") or [])
    graph = native.get("graph")
    if (not native.get("verified") or not native.get("absolute_verified")
            or not isinstance(graph, OrochiExGraph) or not graph.ok
            or graph.parent_ref is None or graph.selected_level is None
            or len(components) != 3
            or [component.get("phase") for component in components]
            != ["phase[1]", "phase[2]", "phase[3]"]
            or any(component.get("special_family") != "orochi_ex"
                   for component in components)):
        raise ValueError(
            f"Orochi EX HP 伸缩缺三阶段绝对证据:"
            f"{native.get('reason') or 'unknown'}")
    try:
        wanted = float(target_hp)
        hp_mult = float(curse_hp)
        native_values = tuple(float(component["native_hp"])
                              for component in components)
        native_total = math.fsum(native_values)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Orochi EX HP 伸缩输入含非数字") from exc
    if not all(math.isfinite(value) and value > 0
               for value in (wanted, hp_mult, native_total)):
        raise ValueError(
            f"Orochi EX HP 伸缩输入非法:target={target_hp},"
            f"curse={curse_hp},native={native_total}")
    baseline_scale = wanted / native_total
    final_scale = baseline_scale * hp_mult
    source_code = graph.parent_ref.code
    phase1_native, middle_native, phase3_native = native_values
    max_safe_fixed_scale = math.nextafter(min(
        wf_orochi_ex.CLIENT_SIGNED_INT_MAX / phase1_native,
        wf_orochi_ex.CLIENT_SIGNED_INT_MAX / phase3_native,
    ), 0.0)
    if not math.isfinite(max_safe_fixed_scale) or max_safe_fixed_scale <= 0:
        raise ValueError(
            f"Orochi EX signed int32 固定阶段上限非法:{max_safe_fixed_scale}")

    def staged(target_total: float, uniform_scale: float, suffix: str) -> tuple:
        fixed_scale = min(uniform_scale, max_safe_fixed_scale)
        phase1_target = int(round(phase1_native * fixed_scale))
        phase3_target = int(round(phase3_native * fixed_scale))
        if (phase1_target <= 0 or phase3_target <= 0
                or phase1_target > wf_orochi_ex.CLIENT_SIGNED_INT_MAX
                or phase3_target > wf_orochi_ex.CLIENT_SIGNED_INT_MAX):
            raise ValueError(
                "Orochi EX 固定阶段 int32 分配失败:"
                f"phase1={phase1_target},phase3={phase3_target},"
                f"scale={fixed_scale}")
        middle_target = math.fsum((
            float(target_total), -float(phase1_target), -float(phase3_target)))
        middle_scale = middle_target / middle_native
        if not math.isfinite(middle_scale) or middle_scale <= 0:
            raise ValueError(
                "Orochi EX 中段剩余 HP 无法安全分配:"
                f"target={target_total},fixed={phase1_target + phase3_target},"
                f"middle_scale={middle_scale}")
        target_code = f"__wf_rogue_orochi_ex_{suffix}__"
        if target_code in dedicated or target_code in boss_level:
            raise ValueError(f"Orochi EX 计划临时代号冲突:{target_code}")
        node, level_leaf, report = wf_orochi_ex.build_scaled_hp_rows(
            dedicated, boss_level, source_code, target_code,
            fixed_phase_scale=fixed_scale, middle_scale=middle_scale)
        dedicated_overlay = dict(dedicated)
        level_overlay = dict(boss_level)
        dedicated_overlay[target_code] = node
        level_overlay[target_code] = level_leaf
        readback = floor_native_hp(
            [target_code], graph.selected_level, standard_boss={},
            boss_level=level_overlay, orochi_ex=dedicated_overlay)
        if (not readback.get("verified")
                or not readback.get("absolute_verified")
                or len(readback.get("components") or []) != 3):
            raise ValueError(
                "Orochi EX 三阶段计划回读失败:"
                f"{readback.get('reason') or 'unknown'}")
        readback_components = tuple(
            float(component["native_hp"])
            for component in readback["components"])
        if not math.isclose(
                math.fsum(readback_components), float(target_total),
                rel_tol=HP_TARGET_REL_TOLERANCE,
                abs_tol=HP_TARGET_ABS_TOLERANCE):
            raise ValueError(
                "Orochi EX 约束分配未命中总 HP:"
                f"readback={math.fsum(readback_components)},"
                f"target={target_total}")
        try:
            threshold_contract = wf_orochi_ex.phase_threshold_icon_contract(
                *readback_components)
        except wf_orochi_ex.OrochiExHpError as exc:
            raise ValueError(
                f"Orochi EX PhaseThresholdIcon 静态契约失败:{exc}") from exc
        if (not threshold_contract.get("static_verified")
                or threshold_contract.get("gameplay_verified")):
            raise ValueError("Orochi EX PhaseThresholdIcon 静态契约缺失")
        try:
            _carrier_leaves, phase_damage_capacity = (
                plan_orochi_ex_phase_damage_capacity(
                    graph.child_codes, graph.selected_level, boss_level,
                    phase1_required_hp=readback_components[0],
                    phase3_required_hp=readback_components[2],
                    minimum_scale=fixed_scale,
                )
            )
        except (KeyError, TypeError, ValueError,
                wf_orochi_ex.OrochiExHpError) as exc:
            raise ValueError(
                f"Orochi EX 阶段蛇头承伤容量计划失败:{exc}") from exc
        capped = fixed_scale < uniform_scale and not math.isclose(
            fixed_scale, uniform_scale, rel_tol=1e-15, abs_tol=0.0)
        component_targets = (
            float(phase1_target), middle_target, float(phase3_target))
        report.update({
            "target_total_hp": float(target_total),
            "uniform_scale": float(uniform_scale),
            "max_safe_fixed_phase_scale": max_safe_fixed_scale,
            "fixed_phase_int32_capped": capped,
            "component_targets": component_targets,
            "phase_threshold_contract": threshold_contract,
            "phase_damage_capacity": phase_damage_capacity,
            "runtime_simulated": False,
            "gameplay_verified": False,
        })
        return (readback, report, fixed_scale, middle_scale,
                component_targets, threshold_contract)

    (baseline_readback, baseline_report, baseline_fixed_scale,
     baseline_middle_scale, baseline_targets,
     baseline_threshold_contract) = staged(
        wanted, baseline_scale, "baseline")
    final_target = wanted * hp_mult
    (final_readback, final_report, final_fixed_scale,
     final_middle_scale, final_targets, final_threshold_contract) = staged(
        final_target, final_scale, "final")
    baseline_components = tuple(
        float(component["native_hp"])
        for component in baseline_readback["components"])
    final_components = tuple(
        float(component["native_hp"])
        for component in final_readback["components"])
    return {
        "channel": "special_bundle", "family": "orochi_ex",
        "c86": 1.0, "curse_hp": hp_mult,
        "baseline_scale": baseline_scale, "final_scale": final_scale,
        "baseline_fixed_phase_scale": baseline_fixed_scale,
        "baseline_middle_scale": baseline_middle_scale,
        "final_fixed_phase_scale": final_fixed_scale,
        "final_middle_scale": final_middle_scale,
        "max_safe_fixed_phase_scale": max_safe_fixed_scale,
        "baseline_fixed_phase_int32_capped": bool(
            baseline_report["fixed_phase_int32_capped"]),
        "final_fixed_phase_int32_capped": bool(
            final_report["fixed_phase_int32_capped"]),
        "baseline_component_hp": baseline_components,
        "final_component_hp": final_components,
        "baseline_component_target_hp": baseline_targets,
        "final_component_target_hp": final_targets,
        "baseline_true_hp": math.fsum(baseline_components),
        "true_hp": math.fsum(final_components),
        "selected_levels": {source_code: graph.selected_level},
        "destinations": {
            source_code: f"{OROCHI_EX}.c24/c25 + {BOSS_LEVEL}.c2",
        },
        "baseline_report": baseline_report,
        "final_report": final_report,
        "baseline_phase_threshold_contract": baseline_threshold_contract,
        "final_phase_threshold_contract": final_threshold_contract,
        "baseline_phase_damage_capacity": copy.deepcopy(
            baseline_report["phase_damage_capacity"]),
        "final_phase_damage_capacity": copy.deepcopy(
            final_report["phase_damage_capacity"]),
        "runtime_simulated": False,
        "gameplay_verified": False,
    }


def single_bar_special_hp_scale_plan(
        native: dict, boss_level: dict, *, target_hp: float,
        curse_hp: float) -> dict:
    """Plan one dedicated constructor's boss_level.c2 clone and readback."""

    components = list(native.get("components") or [])
    graph = native.get("graph")
    if (not native.get("verified") or not native.get("absolute_verified")
            or not isinstance(graph, SingleBarSpecialGraph) or not graph.ok
            or graph.parent_ref is None or graph.selected_level is None
            or graph.family not in SINGLE_BAR_SPECIAL_SPECS
            or len(components) != 1
            or components[0].get("phase") != "main"
            or components[0].get("special_family") != graph.family):
        raise ValueError(
            "专用单血条伸缩缺完整绝对证据:"
            f"{native.get('reason') or 'unknown'}")
    try:
        wanted = float(target_hp)
        hp_mult = float(curse_hp)
        native_total = float(native["native_hp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("专用单血条伸缩输入含非数字") from exc
    if not all(math.isfinite(value) and value > 0
               for value in (wanted, hp_mult, native_total)):
        raise ValueError(
            f"专用单血条伸缩输入非法:target={target_hp},"
            f"curse={curse_hp},native={native_total}")
    source_code = graph.parent_ref.code
    source_leaf = boss_level.get(source_code)
    source_row = cells(source_leaf)
    if len(source_row) != 13 or source_row[0] != "0":
        raise ValueError(f"{graph.family} boss_level[{source_code}] 不是 Hit 行")
    old_c2 = float(source_row[2])
    baseline_scale = wanted / native_total
    final_scale = baseline_scale * hp_mult

    def realized(scale: float) -> tuple[str | bytes, float]:
        staged = clone_hit_boss_level_c2(source_leaf, scale)
        factor = float(cells(staged)[2]) / old_c2
        return staged, native_total * factor

    baseline_leaf, baseline_hp = realized(baseline_scale)
    final_leaf, final_hp = realized(final_scale)
    return {
        "channel": "special_bundle", "family": graph.family,
        "c86": 1.0, "curse_hp": hp_mult,
        "baseline_scale": baseline_scale, "final_scale": final_scale,
        "baseline_component_hp": (baseline_hp,),
        "final_component_hp": (final_hp,),
        "baseline_true_hp": baseline_hp, "true_hp": final_hp,
        "selected_levels": {source_code: graph.selected_level},
        "destinations": {
            source_code: (
                f"{SINGLE_BAR_SPECIAL_SPECS[graph.family]['logical']} key + "
                f"{BOSS_LEVEL}.c2"),
        },
        "baseline_leaf": baseline_leaf,
        "final_leaf": final_leaf,
    }


def sphere_hp_scale_plan(
        native: dict, boss_level: dict, *, target_hp: float,
        curse_hp: float) -> dict:
    """Solve victory HP only when every child-mediated phase stays closed."""

    components = list(native.get("components") or [])
    graph = native.get("graph")
    if (not native.get("verified") or not native.get("absolute_verified")
            or not isinstance(graph, SphereGraph) or not graph.ok
            or graph.parent_ref is None or graph.selected_level is None
            or graph.family not in SPHERE_SPECS or not components
            or components[-1].get("phase") != "main"):
        raise ValueError(
            f"Sphere 伸缩缺完整绝对证据:{native.get('reason') or 'unknown'}")
    if (not graph.behavior_verified or not graph.phase_budgets
            or graph.lifecycle is None
            or not graph.lifecycle.static_verified):
        raise ValueError(
            f"Sphere 阶段行为闭包未验证，严格模式必须重抽:{graph.family}")
    try:
        wanted = float(target_hp)
        hp_mult = float(curse_hp)
        native_parent = float(components[-1]["native_hp"])
        fixed_gate = math.fsum(
            float(component["native_hp"]) for component in components[:-1])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Sphere 伸缩输入含非数字") from exc
    baseline_parent_target = wanted - fixed_gate
    final_total_target = wanted * hp_mult
    final_parent_target = final_total_target - fixed_gate
    numeric = (wanted, hp_mult, native_parent,
               baseline_parent_target, final_parent_target)
    if not all(math.isfinite(value) and value > 0 for value in numeric):
        raise ValueError(
            "Sphere 目标必须大于不可改名的必杀水晶总 HP:"
            f"target={wanted},curse={hp_mult},gate={fixed_gate},"
            f"parent={native_parent}")
    source_code = graph.parent_ref.code
    source_leaf = boss_level.get(source_code)
    baseline_scale = baseline_parent_target / native_parent
    final_scale = final_parent_target / native_parent

    def realized(scale: float) -> tuple[str | bytes, float, int]:
        staged, column = clone_general_boss_level_hp(source_leaf, scale)
        source_row = cells(source_leaf)
        staged_row = cells(staged)
        old_value = float(source_row[column])
        factor = float(staged_row[column]) / old_value
        return staged, native_parent * factor, column

    baseline_leaf, baseline_parent_hp, baseline_column = realized(baseline_scale)
    final_leaf, final_parent_hp, final_column = realized(final_scale)
    if baseline_column != final_column:
        raise ValueError("Sphere baseline/final HP 通道漂移")
    fixed_components = tuple(float(component["native_hp"])
                             for component in components[:-1])
    baseline_components = fixed_components + (baseline_parent_hp,)
    final_components = fixed_components + (final_parent_hp,)
    baseline_targets = fixed_components + (baseline_parent_target,)
    final_targets = fixed_components + (final_parent_target,)
    destinations = {
        str(component["code"]): "native-fixed mandatory gate"
        for component in components[:-1]
    }
    for auxiliary in graph.auxiliaries:
        if auxiliary.role == "damage_conduit":
            source_logical = (
                SPHERE_AUX_LOGICALS[auxiliary.source_table]
                if auxiliary.source_table in SPHERE_AUX_LOGICALS
                else SPHERE_SPECS[graph.family]["logical"])
            destinations[auxiliary.level_code] = (
                f"{source_logical} child reference + "
                f"{BOSS_LEVEL} scaled with parent")
    destinations[source_code] = (
        f"{SPHERE_SPECS[graph.family]['logical']} key + "
        f"{BOSS_LEVEL}.c{final_column}")
    return {
        "channel": "special_bundle", "family": graph.family,
        "c86": 1.0, "curse_hp": hp_mult,
        "baseline_scale": baseline_scale, "final_scale": final_scale,
        "baseline_component_hp": baseline_components,
        "final_component_hp": final_components,
        "baseline_component_target_hp": baseline_targets,
        "final_component_target_hp": final_targets,
        "baseline_true_hp": math.fsum(baseline_components),
        "true_hp": math.fsum(final_components),
        "selected_levels": {
            str(component["code"]): graph.selected_level
            for component in components
        },
        "destinations": destinations,
        "baseline_leaf": baseline_leaf, "final_leaf": final_leaf,
        "parent_hp_column": final_column,
        "fixed_gate_hp": fixed_gate,
        "behavior_verified": True,
        "phase_budgets": [asdict(item) for item in graph.phase_budgets],
        "phase_lifecycle": (
            asdict(graph.lifecycle) if graph.lifecycle is not None else None),
    }


def _clone_result_failure(detail: str) -> OrochiCloneResult:
    return OrochiCloneResult(
        False, reason="SPECIAL_HP_CHANNEL_UNSUPPORTED", detail=detail)


def _orochi_ex_clone_failure(detail: str) -> OrochiExCloneResult:
    return OrochiExCloneResult(
        False, reason="SPECIAL_HP_CHANNEL_UNSUPPORTED", detail=detail)


def _single_bar_special_clone_failure(
        detail: str, family: str | None = None) -> SingleBarSpecialCloneResult:
    return SingleBarSpecialCloneResult(
        False, family=family, reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
        detail=detail)


def _sphere_clone_failure(
        detail: str, family: str | None = None) -> SphereCloneResult:
    return SphereCloneResult(
        False, family=family, reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
        detail=detail)


_SPHERE_AUX_CLONE_BASE = 1_900_000_000


def _sphere_aux_clone_id(
        family: str, round_no: int, group_ordinal: int,
        entity_ordinal: int) -> str:
    """Return a deterministic positive AS3-int ID for one round-local child."""

    spec = SPHERE_SPECS[family]
    if not (1 <= int(round_no) <= 999
            and 1 <= int(group_ordinal) <= 99
            and 1 <= int(entity_ordinal) <= 99):
        raise ValueError(
            "Sphere child clone coordinates exceed reserved namespace:"
            f"{round_no},{group_ordinal},{entity_ordinal}")
    value = (_SPHERE_AUX_CLONE_BASE + int(spec["kind"]) * 10_000_000
             + int(round_no) * 10_000 + int(group_ordinal) * 100
             + int(entity_ordinal))
    if value > 2_147_483_647:
        raise ValueError(f"Sphere child clone ID exceeds AS3 int:{value}")
    return str(value)


def _sphere_child_clone_code(
        family: str, round_no: int, group_ordinal: int,
        entity_ordinal: int) -> str:
    return (f"{PRIVATE_PREFIX}{family}{int(round_no)}_"
            f"g{int(group_ordinal)}c{int(entity_ordinal)}")


def clone_single_bar_special_bundle(
        bundle: rbb.NativeBossBundle, round_no: int, scale: float,
        tables: dict) -> SingleBarSpecialCloneResult:
    """Atomically clone one dedicated parent and its boss_level HP row."""

    family = special_bundle_family(bundle)
    if family not in SINGLE_BAR_SPECIAL_SPECS:
        return _single_bar_special_clone_failure(
            "bundle is not a proved single-bar special", family)
    try:
        round_value = int(round_no)
        factor = float(scale)
    except (TypeError, ValueError) as exc:
        return _single_bar_special_clone_failure(
            f"round/scale is not numeric:{exc}", family)
    if round_value <= 0 or not math.isfinite(factor) or factor <= 0:
        return _single_bar_special_clone_failure(
            f"round and scale must be finite positive:{round_no},{scale}",
            family)
    graph = inspect_single_bar_special_bundle(bundle, 100, tables)
    if (not graph.ok or graph.parent_ref is None
            or graph.selected_level is None):
        return _single_bar_special_clone_failure(
            graph.detail or graph.reason or "source graph failed", family)
    dedicated = tables.get(family)
    boss_level = tables.get("boss_level")
    if not isinstance(dedicated, dict) or not isinstance(boss_level, dict):
        return _single_bar_special_clone_failure(
            "dedicated/boss_level clone tables missing", family)
    target = f"{PRIVATE_PREFIX}{family}{round_value}"
    occupied = [name for name, table in (
        (family, dedicated), ("boss_level", boss_level)) if target in table]
    if occupied:
        return _single_bar_special_clone_failure(
            f"target key conflict:{target} in {','.join(occupied)}", family)

    overlay = dict(tables)
    overlay[family] = dict(dedicated)
    overlay["boss_level"] = dict(boss_level)
    try:
        overlay[family][target] = copy.deepcopy(dedicated[graph.parent_ref.code])
        overlay["boss_level"][target] = clone_hit_boss_level_c2(
            boss_level[graph.parent_ref.code], factor)
    except (KeyError, TypeError, ValueError) as exc:
        return _single_bar_special_clone_failure(
            f"dependency staging failed:{exc}", family)
    target_ref = rbb.BossRef(int(SINGLE_BAR_SPECIAL_SPECS[family]["kind"]), target)
    cloned_slots = []
    for slot in bundle.slots:
        single = target_ref if slot.single == graph.parent_ref else slot.single
        multi = target_ref if slot.multi == graph.parent_ref else slot.multi
        cloned_slots.append(replace(slot, single=single, multi=multi))
    cloned_bundle = replace(bundle, slots=tuple(cloned_slots))
    readback = single_bar_special_native_hp_evidence(
        cloned_bundle, graph.selected_level, overlay)
    source = single_bar_special_native_hp_evidence(
        bundle, graph.selected_level, tables)
    expected = (float(source["native_hp"]) * factor
                if source.get("verified") else None)
    if (not readback.get("verified") or readback.get("native_hp") is None
            or expected is None
            or not math.isclose(float(readback["native_hp"]), expected,
                                rel_tol=HP_TARGET_REL_TOLERANCE,
                                abs_tol=HP_TARGET_ABS_TOLERANCE)):
        return _single_bar_special_clone_failure(
            "overlay HP/identity readback failed:"
            f"{readback.get('detail') or readback.get('reason') or readback.get('native_hp')} "
            f"expected={expected}", family)

    dedicated[target] = overlay[family][target]
    boss_level[target] = overlay["boss_level"][target]
    return SingleBarSpecialCloneResult(
        True, family=family, parent_code=target,
        clone_map=((graph.parent_ref, target_ref),),
        bundle=cloned_bundle, evidence=readback,
        touched_tables=("boss_level", family))


