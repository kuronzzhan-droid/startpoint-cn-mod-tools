# Source section of rogue_build; loaded in its shared module namespace.
def clone_sphere_bundle(
        bundle: rbb.NativeBossBundle, round_no: int, parent_scale: float,
        tables: dict) -> SphereCloneResult:
    """Atomically clone a behavior-proved Sphere parent and damage conduits."""

    family = special_bundle_family(bundle)
    if family not in SPHERE_SPECS:
        return _sphere_clone_failure("bundle is not a proved Sphere", family)
    try:
        round_value = int(round_no)
        factor = float(parent_scale)
    except (TypeError, ValueError) as exc:
        return _sphere_clone_failure(f"round/scale is not numeric:{exc}", family)
    if round_value <= 0 or not math.isfinite(factor) or factor <= 0:
        return _sphere_clone_failure(
            f"round and scale must be finite positive:{round_no},{parent_scale}",
            family)
    graph = inspect_sphere_bundle(bundle, 100, tables)
    if (not graph.ok or graph.parent_ref is None
            or graph.selected_level is None):
        return _sphere_clone_failure(
            graph.detail or graph.reason or "source graph failed", family)
    if (not graph.behavior_verified or not graph.phase_budgets
            or graph.lifecycle is None
            or not graph.lifecycle.static_verified):
        return _sphere_clone_failure(
            f"Sphere phase behavior closure is not proved:{family}", family)
    spec = SPHERE_SPECS[family]
    scaled_aux_groups = tuple(
        (ordinal, group)
        for ordinal, group in enumerate(spec.get("aux_groups") or (), start=1)
        if group.get("scale_with_parent"))
    scaled_embedded_groups = tuple(
        (ordinal, group)
        for ordinal, group in enumerate(spec.get("embedded") or (), start=1)
        if group.get("scale_with_parent"))
    if not scaled_aux_groups and not scaled_embedded_groups:
        return _sphere_clone_failure(
            f"Sphere has no behavior-proved scalable conduits:{family}", family)
    dedicated = tables.get(family)
    boss_level = tables.get("boss_level")
    if not isinstance(dedicated, dict) or not isinstance(boss_level, dict):
        return _sphere_clone_failure(
            "Sphere dedicated/boss_level clone tables missing", family)
    target = f"{PRIVATE_PREFIX}{family}{round_value}"
    occupied = [name for name, table in (
        (family, dedicated), ("boss_level", boss_level)) if target in table]
    if occupied:
        return _sphere_clone_failure(
            f"target key conflict:{target} in {','.join(occupied)}", family)

    required_auxiliary_names = tuple(dict.fromkeys(
        str(group["table"]) for _ordinal, group in scaled_aux_groups
        if "level_column" in group))
    missing_auxiliaries = [
        name for name in required_auxiliary_names
        if not isinstance(tables.get(name), dict)]
    if missing_auxiliaries:
        return _sphere_clone_failure(
            "Sphere scalable auxiliary table missing:"
            + ",".join(missing_auxiliaries), family)

    overlay = dict(tables)
    overlay[family] = dict(dedicated)
    overlay["boss_level"] = dict(boss_level)
    for table_name in required_auxiliary_names:
        overlay[table_name] = dict(tables[table_name])
    staged_auxiliary_keys: dict[str, list[str]] = {
        name: [] for name in required_auxiliary_names}
    staged_level_codes: list[str] = []
    try:
        source_parent_node = dedicated[graph.parent_ref.code]
        target_parent_node = copy.deepcopy(source_parent_node)
        source_parent_leaf = source_parent_node[str(graph.selected_level)]
        target_parent_leaf = target_parent_node[str(graph.selected_level)]
        source_parent_row = cells(source_parent_leaf)
        target_parent_row = cells(target_parent_leaf)
        overlay["boss_level"][target], _column = clone_general_boss_level_hp(
            boss_level[graph.parent_ref.code], factor)

        # Embedded sources keep the boss_level code directly in the parent row.
        # Use g51..g99 so the already-published auxiliary g1.. namespace remains
        # stable for Thunder and for interrupted-write cleanup.
        for embedded_ordinal, group in scaled_embedded_groups:
            level_columns = tuple(map(int, group.get("level_columns") or ()))
            if not level_columns or len(set(level_columns)) != len(level_columns):
                raise ValueError(
                    f"embedded conduit lacks distinct level columns:{group}")
            clone_group_ordinal = 50 + embedded_ordinal
            for entity_ordinal, parent_column in enumerate(
                    level_columns, start=1):
                source_level_code = str(
                    source_parent_row[parent_column]).strip()
                target_level_code = _sphere_child_clone_code(
                    family, round_value, clone_group_ordinal, entity_ordinal)
                if target_level_code in overlay["boss_level"]:
                    raise ValueError(
                        f"boss_level child target conflict:{target_level_code}")
                overlay["boss_level"][target_level_code], _child_column = (
                    clone_general_boss_level_hp(
                        boss_level[source_level_code], factor))
                target_parent_row[parent_column] = target_level_code
                staged_level_codes.append(target_level_code)

        for group_ordinal, group in scaled_aux_groups:
            if "level_parent_column" in group:
                # Water/Holy child rows intentionally share a level code stored
                # in their parent values.  Clone that code once and keep all
                # official behavior-row IDs unchanged.
                parent_level_column = int(group["level_parent_column"])
                source_level_code = str(
                    source_parent_row[parent_level_column]).strip()
                target_level_code = _sphere_child_clone_code(
                    family, round_value, group_ordinal, 1)
                if target_level_code in overlay["boss_level"]:
                    raise ValueError(
                        f"boss_level child target conflict:{target_level_code}")
                overlay["boss_level"][target_level_code], _child_column = (
                    clone_general_boss_level_hp(
                        boss_level[source_level_code], factor))
                target_parent_row[parent_level_column] = target_level_code
                staged_level_codes.append(target_level_code)
                continue
            if "level_column" not in group:
                raise ValueError(
                    f"{group['table']} lacks an independently cloneable level code")
            table_name = str(group["table"])
            source_table = tables[table_name]
            target_table = overlay[table_name]
            level_column = int(group["level_column"])
            for entity_ordinal, parent_column in enumerate(
                    group["id_columns"], start=1):
                source_entity_id = str(
                    source_parent_row[int(parent_column)]).strip()
                target_entity_id = _sphere_aux_clone_id(
                    family, round_value, group_ordinal, entity_ordinal)
                target_level_code = _sphere_child_clone_code(
                    family, round_value, group_ordinal, entity_ordinal)
                conflicts = []
                if target_entity_id in target_table:
                    conflicts.append(f"{table_name}[{target_entity_id}]")
                if target_level_code in overlay["boss_level"]:
                    conflicts.append(f"boss_level[{target_level_code}]")
                if conflicts:
                    raise ValueError(
                        "Sphere child target conflict:" + ",".join(conflicts))
                source_child_leaf = source_table[source_entity_id]
                child_row = cells(source_child_leaf)
                source_level_code = str(child_row[level_column]).strip()
                child_row[level_column] = target_level_code
                target_table[target_entity_id] = join(
                    child_row, isinstance(source_child_leaf, bytes))
                overlay["boss_level"][target_level_code], _child_column = (
                    clone_general_boss_level_hp(
                        boss_level[source_level_code], factor))
                target_parent_row[int(parent_column)] = target_entity_id
                staged_auxiliary_keys[table_name].append(target_entity_id)
                staged_level_codes.append(target_level_code)
        target_parent_node[str(graph.selected_level)] = join(
            target_parent_row, isinstance(target_parent_leaf, bytes))
        overlay[family][target] = target_parent_node
    except (KeyError, TypeError, ValueError) as exc:
        return _sphere_clone_failure(f"dependency staging failed:{exc}", family)
    target_ref = rbb.BossRef(int(SPHERE_SPECS[family]["kind"]), target)
    cloned_slots = []
    for slot in bundle.slots:
        single = target_ref if slot.single == graph.parent_ref else slot.single
        multi = target_ref if slot.multi == graph.parent_ref else slot.multi
        cloned_slots.append(replace(slot, single=single, multi=multi))
    cloned_bundle = replace(bundle, slots=tuple(cloned_slots))
    readback = sphere_native_hp_evidence(
        cloned_bundle, graph.selected_level, overlay)
    source = sphere_native_hp_evidence(
        bundle, graph.selected_level, tables)
    source_components = list(source.get("components") or [])
    readback_components = list(readback.get("components") or [])
    if (not source.get("verified") or not readback.get("verified")
            or len(source_components) != len(readback_components)
            or not source_components):
        return _sphere_clone_failure(
            "Sphere overlay HP/identity readback failed:component drift", family)
    readback_graph = readback.get("graph")
    if (not isinstance(readback_graph, SphereGraph)
            or not readback_graph.behavior_verified
            or readback_graph.lifecycle is None
            or not readback_graph.lifecycle.static_verified
            or len(readback_graph.phase_budgets) != len(graph.phase_budgets)):
        return _sphere_clone_failure(
            "Sphere overlay phase behavior readback failed", family)
    source_lifecycle = graph.lifecycle
    target_lifecycle = readback_graph.lifecycle
    if (source_lifecycle.runtime_simulated
            or source_lifecycle.gameplay_verified
            or target_lifecycle.runtime_simulated
            or target_lifecycle.gameplay_verified
            or source_lifecycle.client_contract
            != target_lifecycle.client_contract
            or source_lifecycle.victory_component_count
            != target_lifecycle.victory_component_count
            or len(source_lifecycle.steps) != len(target_lifecycle.steps)):
        return _sphere_clone_failure(
            "Sphere overlay lifecycle proof metadata drift", family)
    for source_step, target_step in zip(
            source_lifecycle.steps, target_lifecycle.steps):
        source_shape = (
            source_step.sequence, source_step.source_phase,
            source_step.target_phase, source_step.trigger,
            source_step.member_phases, source_step.expected_entities,
            source_step.expected_completion_count, source_step.budget_phase,
            source_step.next_state_entry, source_step.verified)
        target_shape = (
            target_step.sequence, target_step.source_phase,
            target_step.target_phase, target_step.trigger,
            target_step.member_phases, target_step.expected_entities,
            target_step.expected_completion_count, target_step.budget_phase,
            target_step.next_state_entry, target_step.verified)
        ratios_match = (
            source_step.threshold_ratio is None
            and target_step.threshold_ratio is None)
        if (source_step.threshold_ratio is not None
                and target_step.threshold_ratio is not None):
            ratios_match = math.isclose(
                source_step.threshold_ratio, target_step.threshold_ratio,
                rel_tol=1e-12, abs_tol=1e-12)
        if (source_shape != target_shape or not ratios_match
                or len(source_step.entity_ids)
                != len(target_step.entity_ids)
                or len(set(target_step.entity_ids))
                != len(target_step.entity_ids)):
            return _sphere_clone_failure(
                "Sphere overlay lifecycle topology drift:"
                f"phase[{source_step.source_phase}] source={source_shape}/"
                f"ratio={source_step.threshold_ratio}/ids={len(source_step.entity_ids)} "
                f"target={target_shape}/ratio={target_step.threshold_ratio}/"
                f"ids={len(target_step.entity_ids)}", family)
    scalable_phases = {
        str(group["phase"])
        for _ordinal, group in (
            *scaled_embedded_groups, *scaled_aux_groups)}
    if len(readback_graph.auxiliaries) != len(graph.auxiliaries):
        return _sphere_clone_failure(
            "Sphere overlay auxiliary occurrence count drift", family)
    for source_aux, target_aux in zip(
            graph.auxiliaries, readback_graph.auxiliaries):
        expected_aux_hp = float(source_aux.native_hp) * (
            factor if source_aux.phase in scalable_phases else 1.0)
        if (target_aux.native_hp is None
                or not math.isclose(
                    float(target_aux.native_hp), expected_aux_hp,
                    rel_tol=HP_TARGET_REL_TOLERANCE,
                    abs_tol=HP_TARGET_ABS_TOLERANCE)):
            return _sphere_clone_failure(
                "Sphere overlay child HP readback failed:"
                f"{source_aux.phase}/{source_aux.entity_id}->"
                f"{target_aux.entity_id} actual={target_aux.native_hp} "
                f"expected={expected_aux_hp}", family)
    for source_budget, target_budget in zip(
            graph.phase_budgets, readback_graph.phase_budgets):
        if (source_budget.phase != target_budget.phase
                or source_budget.budget_model != target_budget.budget_model
                or source_budget.occurrences_per_entity
                != target_budget.occurrences_per_entity
                or source_budget.entity_occurrence_count
                != target_budget.entity_occurrence_count
                or source_budget.completion_count
                != target_budget.completion_count
                or not math.isclose(
                    source_budget.coverage_ratio,
                    target_budget.coverage_ratio,
                    rel_tol=HP_TARGET_REL_TOLERANCE,
                    abs_tol=HP_TARGET_REL_TOLERANCE)):
            return _sphere_clone_failure(
                "Sphere overlay phase budget ratio drift:"
                f"{source_budget.phase}", family)
    expected = (math.fsum(float(item["native_hp"])
                          for item in source_components[:-1])
                + float(source_components[-1]["native_hp"]) * factor)
    if not math.isclose(float(readback["native_hp"]), expected,
                        rel_tol=HP_TARGET_REL_TOLERANCE,
                        abs_tol=HP_TARGET_ABS_TOLERANCE):
        return _sphere_clone_failure(
            "Sphere overlay HP readback failed:"
            f"{readback.get('native_hp')} expected={expected}", family)

    dedicated[target] = overlay[family][target]
    boss_level[target] = overlay["boss_level"][target]
    for level_code in staged_level_codes:
        boss_level[level_code] = overlay["boss_level"][level_code]
    for table_name, entity_ids in staged_auxiliary_keys.items():
        for entity_id in entity_ids:
            tables[table_name][entity_id] = overlay[table_name][entity_id]
    return SphereCloneResult(
        True, family=family, parent_code=target,
        clone_map=((graph.parent_ref, target_ref),), bundle=cloned_bundle,
        evidence=readback, touched_tables=tuple(dict.fromkeys((
            "boss_level", *required_auxiliary_names, family))))


def clone_orochi_ex_parent_bundle(
        bundle: rbb.NativeBossBundle, round_no: int, scale: float,
        tables: dict, *, middle_scale: float | None = None) -> OrochiExCloneResult:
    """Atomically clone kind-4 parent, six heads and all three HP channels."""
    try:
        round_value = int(round_no)
        factor = float(scale)
        middle_factor = factor if middle_scale is None else float(middle_scale)
    except (TypeError, ValueError) as exc:
        return _orochi_ex_clone_failure(f"round/scale is not numeric:{exc}")
    if (round_value <= 0 or not math.isfinite(factor) or factor <= 0
            or not math.isfinite(middle_factor) or middle_factor <= 0):
        return _orochi_ex_clone_failure(
            "round and scales must be finite positive:"
            f"{round_no},{scale},{middle_scale}")
    source_graph = inspect_orochi_ex_bundle(bundle, 100, tables)
    if (not source_graph.ok or source_graph.parent_ref is None
            or source_graph.selected_level is None):
        return _orochi_ex_clone_failure(
            source_graph.detail or source_graph.reason or "source graph failed")
    required = ("orochi_ex", "orochi_ex_head", "boss_level")
    if not all(isinstance(tables.get(name), dict) for name in required):
        return _orochi_ex_clone_failure(
            "Orochi EX clone tables are missing or not mutable maps")
    dedicated = tables["orochi_ex"]
    heads = tables["orochi_ex_head"]
    boss_level = tables["boss_level"]
    target_parent = f"{PRIVATE_PREFIX}orochi_ex{round_value}"
    target_heads = tuple(
        f"{target_parent}_head{ordinal}" for ordinal in range(1, 7))
    for code in (target_parent,) + target_heads:
        occupied = [name for name, table in (
            ("orochi_ex", dedicated), ("orochi_ex_head", heads),
            ("boss_level", boss_level)) if code in table]
        if occupied:
            return _orochi_ex_clone_failure(
                f"target key conflict:{code} in {','.join(occupied)}")

    overlay = {
        "orochi_ex": dict(dedicated),
        "orochi_ex_head": dict(heads),
        "boss_level": dict(boss_level),
    }
    try:
        parent_node, parent_level, hp_report = wf_orochi_ex.build_scaled_hp_rows(
            dedicated, boss_level, source_graph.parent_ref.code, target_parent,
            fixed_phase_scale=factor, middle_scale=middle_factor)
        rewritten_parent: dict[str, object] = {}
        for tier, leaf in parent_node.items():
            row = cells(leaf)
            if len(row) != wf_orochi_ex.PARENT_COLUMNS:
                raise ValueError(
                    f"scaled parent tier {tier} has {len(row)} columns")
            current_children = tuple(row[index]
                                     for index in OROCHI_EX_CHILD_COLUMNS)
            if current_children != source_graph.child_codes:
                raise ValueError(
                    f"scaled parent child closure drift:{current_children}")
            for index, child_code in zip(
                    OROCHI_EX_CHILD_COLUMNS, target_heads):
                row[index] = child_code
            rewritten_parent[str(tier)] = join(
                row, isinstance(leaf, (bytes, bytearray)))
        overlay["orochi_ex"][target_parent] = rewritten_parent
        overlay["boss_level"][target_parent] = parent_level
        selected_parent_row = cells(
            rewritten_parent[str(source_graph.selected_level)])
        planned_head_levels, planned_capacity = (
            plan_orochi_ex_phase_damage_capacity(
                source_graph.child_codes, source_graph.selected_level,
                boss_level,
                phase1_required_hp=float(
                    selected_parent_row[wf_orochi_ex.PHASE1_HP_COLUMN]),
                phase3_required_hp=float(
                    selected_parent_row[wf_orochi_ex.PHASE3_HP_COLUMN]),
                minimum_scale=factor,
            )
        )
        for source_code, target_code in zip(
                source_graph.child_codes, target_heads):
            overlay["orochi_ex_head"][target_code] = copy.deepcopy(
                heads[source_code])
            overlay["boss_level"][target_code] = copy.deepcopy(
                planned_head_levels[source_code])

        source_node = dedicated[source_graph.parent_ref.code]
        if set(source_node) != set(rewritten_parent):
            raise ValueError(
                "scaled parent tier set drift:"
                f"source={sorted(source_node)},target={sorted(rewritten_parent)}")
        allowed_parent_columns = {
            wf_orochi_ex.PHASE1_HP_COLUMN,
            wf_orochi_ex.PHASE3_HP_COLUMN,
            *OROCHI_EX_CHILD_COLUMNS,
        }
        for tier in source_node:
            source_row = cells(source_node[tier])
            target_row = cells(rewritten_parent[str(tier)])
            drift = tuple(
                index for index, (before, after) in enumerate(
                    zip(source_row, target_row))
                if before != after and index not in allowed_parent_columns)
            if (len(source_row) != wf_orochi_ex.PARENT_COLUMNS
                    or len(target_row) != wf_orochi_ex.PARENT_COLUMNS
                    or drift):
                raise ValueError(
                    "Orochi EX parent non-HP/child topology drift:"
                    f"tier={tier},columns={drift}")
            if tuple(target_row[index]
                     for index in OROCHI_EX_CHILD_COLUMNS) != target_heads:
                raise ValueError(
                    f"Orochi EX target child closure drift:tier={tier}")
        source_parent_level = cells(boss_level[source_graph.parent_ref.code])
        target_parent_level = cells(parent_level)
        level_drift = tuple(
            index for index, (before, after) in enumerate(
                zip(source_parent_level, target_parent_level))
            if before != after and index != 2)
        if (len(source_parent_level) != wf_orochi_ex.BOSS_LEVEL_COLUMNS
                or len(target_parent_level) != wf_orochi_ex.BOSS_LEVEL_COLUMNS
                or level_drift):
            raise ValueError(
                "Orochi EX parent boss_level changed outside c2:"
                f"columns={level_drift}")
        for source_code, target_code in zip(
                source_graph.child_codes, target_heads):
            source_head_level = cells(boss_level[source_code])
            target_head_level = cells(
                overlay["boss_level"][target_code])
            head_level_drift = tuple(
                index for index, (before, after) in enumerate(
                    zip(source_head_level, target_head_level))
                if before != after and index != 2)
            if (overlay["orochi_ex_head"][target_code] != heads[source_code]
                    or len(source_head_level) != wf_orochi_ex.BOSS_LEVEL_COLUMNS
                    or len(target_head_level) != wf_orochi_ex.BOSS_LEVEL_COLUMNS
                    or target_head_level[0] != "0"
                    or head_level_drift
                    or overlay["boss_level"][target_code]
                    != planned_head_levels[source_code]):
                raise ValueError(
                    "Orochi EX child clone/c2 capacity drift:"
                    f"{source_code}->{target_code}:columns={head_level_drift}")
    except (KeyError, TypeError, ValueError,
            wf_orochi_ex.OrochiExHpError) as exc:
        return _orochi_ex_clone_failure(f"dependency staging failed:{exc}")

    cloned_slots = []
    for slot in bundle.slots:
        single = (rbb.BossRef(4, target_parent)
                  if slot.single == source_graph.parent_ref else slot.single)
        multi = (rbb.BossRef(4, target_parent)
                 if slot.multi == source_graph.parent_ref else slot.multi)
        cloned_slots.append(replace(slot, single=single, multi=multi))
    cloned_bundle = replace(bundle, slots=tuple(cloned_slots))
    readback_graph = inspect_orochi_ex_bundle(
        cloned_bundle, source_graph.selected_level, overlay)
    readback = orochi_ex_native_hp_evidence(
        cloned_bundle, source_graph.selected_level, overlay)
    source = orochi_ex_native_hp_evidence(
        bundle, source_graph.selected_level, tables)
    expected_total = None
    if source.get("verified") and len(source.get("components") or ()) == 3:
        source_components = list(source["components"])
        phase_after = hp_report.get("phase_hp_after", {}).get(
            str(source_graph.selected_level))
        if isinstance(phase_after, tuple) and len(phase_after) == 2:
            realized_middle_factor = (
                float(hp_report["middle_c2_after"])
                / float(hp_report["middle_c2_before"]))
            expected_total = math.fsum((
                float(phase_after[0]),
                float(source_components[1]["native_hp"])
                * realized_middle_factor,
                float(phase_after[1]),
            ))
    if (not readback_graph.ok or not readback.get("verified")
            or readback.get("native_hp") is None or expected_total is None
            or not math.isclose(float(readback["native_hp"]), expected_total,
                                rel_tol=HP_TARGET_REL_TOLERANCE,
                                abs_tol=HP_TARGET_ABS_TOLERANCE)):
        return _orochi_ex_clone_failure(
            "overlay HP/graph readback failed:"
            f"{readback_graph.detail or readback.get('reason') or readback.get('native_hp')} "
            f"expected={expected_total}")
    try:
        readback_components = list(readback.get("components") or ())
        if len(readback_components) != 3:
            raise ValueError("Orochi EX readback does not have three phases")
        phase_damage_capacity = orochi_ex_phase_damage_capacity_contract(
            target_heads, source_graph.selected_level,
            overlay["boss_level"],
            phase1_required_hp=float(readback_components[0]["native_hp"]),
            phase3_required_hp=float(readback_components[2]["native_hp"]),
        )
        for planned_phase, actual_phase in zip(
                planned_capacity["phases"],
                phase_damage_capacity["phases"]):
            planned_values = tuple(
                float(planned_phase["carrier_hp"][code])
                for code in planned_phase["head_codes"])
            actual_values = tuple(
                float(actual_phase["carrier_hp"][code])
                for code in actual_phase["head_codes"])
            if (int(planned_phase["phase"]) != int(actual_phase["phase"])
                    or not math.isclose(
                        float(planned_phase["required_hp"]),
                        float(actual_phase["required_hp"]),
                        rel_tol=1e-12, abs_tol=1e-5)
                    or any(not math.isclose(
                        expected, actual, rel_tol=1e-12, abs_tol=1e-5)
                           for expected, actual in zip(
                               planned_values, actual_values))):
                raise ValueError(
                    "Orochi EX planned/target phase carrier readback drift")
            actual_phase["minimum_scale"] = planned_phase["minimum_scale"]
            actual_phase["planned_scale"] = planned_phase["planned_scale"]
            actual_phase["source_head_codes"] = tuple(
                planned_phase["source_head_codes"])
            actual_phase["source_to_target"] = dict(zip(
                actual_phase["source_head_codes"],
                actual_phase["head_codes"]))
            actual_phase["source_carrier_hp"] = copy.deepcopy(
                planned_phase["source_carrier_hp"])
            actual_phase["source_total_carrier_hp"] = float(
                planned_phase["source_total_carrier_hp"])
            actual_phase["source_primary_carrier_hp"] = float(
                planned_phase["source_primary_carrier_hp"])
            actual_phase["source_boss_level_c2"] = copy.deepcopy(
                planned_phase["source_boss_level_c2"])
            actual_phase["planned_boss_level_c2"] = copy.deepcopy(
                planned_phase["planned_boss_level_c2"])
        phase_damage_capacity["minimum_scale"] = float(
            planned_capacity["minimum_scale"])
        phase_damage_capacity["format_margin"] = float(
            planned_capacity["format_margin"])
    except (KeyError, TypeError, ValueError,
            wf_orochi_ex.OrochiExHpError) as exc:
        return _orochi_ex_clone_failure(
            f"phase damage-carrier capacity readback failed:{exc}")
    threshold_contract = readback.get("phase_threshold_contract")
    if (not isinstance(threshold_contract, dict)
            or not threshold_contract.get("signed_int32_verified")
            or not threshold_contract.get("static_verified")
            or threshold_contract.get("runtime_simulated")
            or threshold_contract.get("gameplay_verified")):
        return _orochi_ex_clone_failure(
            "overlay PhaseThresholdIcon/signed-int32 contract failed")
    readback = dict(readback)
    readback["clone_semantics"] = {
        "parent_only_hp_and_child_columns_changed": True,
        "parent_boss_level_only_c2_changed": True,
        "six_head_nodes_equal_source": True,
        "six_head_boss_level_only_c2_planned": True,
        "phase1_and_phase3_carriers_cover_gate": True,
        "six_child_attack_target_references_closed": True,
        "phase_spawn_topology_preserved": True,
        "phase_threshold_contract": copy.deepcopy(threshold_contract),
        "phase_damage_capacity": copy.deepcopy(phase_damage_capacity),
        "static_verified": True,
        "runtime_simulated": False,
        "gameplay_verified": False,
    }

    # Commit additions only after the complete parent/head/HP overlay passes.
    dedicated[target_parent] = overlay["orochi_ex"][target_parent]
    boss_level[target_parent] = overlay["boss_level"][target_parent]
    for target_code in target_heads:
        heads[target_code] = overlay["orochi_ex_head"][target_code]
        boss_level[target_code] = overlay["boss_level"][target_code]
    clone_map = ((source_graph.parent_ref, rbb.BossRef(4, target_parent)),) + tuple(
        (rbb.BossRef(5, source_code), rbb.BossRef(5, target_code))
        for source_code, target_code in zip(
            source_graph.child_codes, target_heads))
    return OrochiExCloneResult(
        True, parent_code=target_parent, head_codes=target_heads,
        clone_map=clone_map, bundle=cloned_bundle, evidence=readback,
        touched_tables=("orochi_ex_head", "boss_level", "orochi_ex"))


def _orochi_clone_reference_error(
        expanded: HpExpansionResult, code_refs: dict,
        enemy_watch: dict | None) -> str | None:
    """Return why an expanded nine-entity graph cannot survive code renaming.

    ``hard`` references cannot be rewritten locally.  ``soft`` means the head
    owns a ``general_enemy_watch`` self subtree, which is cloneable only when
    the exact source row exists in the injected snapshot.  This helper is
    shared by catalog eligibility and realization so a bundle cannot enter the
    selector and then deterministically fail the same static precondition.
    """
    if code_refs.get("degraded"):
        return "external boss-code reference scan degraded"
    heads = tuple(member.code for member in expanded.members
                  if member.role == "head")
    hard = sorted(set(heads) & set(code_refs.get("hard", ())))
    if hard:
        return "head has uncloneable external code references:" + ",".join(hard)
    soft = sorted(set(heads) & set(code_refs.get("soft", ())))
    if soft:
        ew_self = enemy_watch.get("1") if isinstance(enemy_watch, dict) else None
        missing = [code for code in soft
                   if not isinstance(ew_self, dict) or code not in ew_self]
        if missing:
            return "required general_enemy_watch self row missing:" + ",".join(missing)
    return None


def clone_orochi_parent_bundle(bundle: rbb.NativeBossBundle, round_no: int,
                               scale: float, tables: dict) -> OrochiCloneResult:
    """Clone an Orochi parent and all eight heads through an off-table overlay.

    Expected validation failures return a structured result.  No caller-owned
    table is mutated until the overlay has been re-expanded successfully.
    """
    parent_ref = _orochi_parent_ref(bundle)
    if parent_ref is None:
        return _clone_result_failure("bundle is not one proved Orochi parent")
    try:
        round_value = int(round_no)
        factor = float(scale)
    except (TypeError, ValueError) as exc:
        return _clone_result_failure(f"round/scale is not numeric:{exc}")
    if round_value <= 0 or not math.isfinite(factor) or factor <= 0:
        return _clone_result_failure(
            f"round and scale must be finite positive:{round_no},{scale}")
    selected_values = {
        int(tier) for layer, slot, tier in bundle.selected_levels
        if any(item.layer == layer and item.slot == slot and item.single == parent_ref
               for item in bundle.slots)
    }
    if len(selected_values) != 1:
        return _clone_result_failure(
            f"bundle has no unique selected parent tier:{sorted(selected_values)}")
    selected_level = next(iter(selected_values))
    source = expand_bundle_hp_members(bundle, selected_level, tables)
    if not source.ok or source.total_hp is None:
        return _clone_result_failure(source.detail or "source HP expansion failed")

    required = ("orochi", "general_boss", "general_boss_variable", "boss_level")
    if not all(isinstance(tables.get(name), dict) for name in required):
        return _clone_result_failure("clone tables are missing or not mutable maps")
    oro = tables["orochi"]
    gb = tables["general_boss"]
    gv = tables["general_boss_variable"]
    bl = tables["boss_level"]
    ew = tables.get("general_enemy_watch")
    if ew is not None and not isinstance(ew, dict):
        return _clone_result_failure("general_enemy_watch is not a map")

    code_refs = tables.get("__code_references__")
    if not isinstance(code_refs, dict):
        code_refs = code_referenced_bosses(gb)
    ref_error = _orochi_clone_reference_error(source, code_refs, ew)
    if ref_error:
        return _clone_result_failure(ref_error)
    source_heads = tuple(member.code for member in source.members
                         if member.role == "head")

    parent_code = f"{PRIVATE_PREFIX}orochi{round_value}"
    head_codes = tuple(
        f"{parent_code}_head{ordinal}" for ordinal in range(1, 9))
    target_codes = (parent_code,) + head_codes
    ew_self = ew.get("1", {}) if isinstance(ew, dict) else {}
    for code in target_codes:
        occupied = [name for name, table in (
            ("orochi", oro), ("general_boss", gb),
            ("general_boss_variable", gv), ("boss_level", bl))
                    if code in table]
        if isinstance(ew_self, dict) and code in ew_self:
            occupied.append("general_enemy_watch")
        if occupied:
            return _clone_result_failure(
                f"target key conflict:{code} in {','.join(occupied)}")

    # Shallow-copy top-level maps and deep-copy only new dependency rows.  This
    # is an off-table overlay: no nested source node is edited in place.
    overlay = {
        "orochi": dict(oro),
        "general_boss": dict(gb),
        "general_boss_variable": dict(gv),
        "boss_level": dict(bl),
    }
    if isinstance(ew, dict):
        overlay_ew = dict(ew)
        overlay_ew["1"] = dict(ew_self) if isinstance(ew_self, dict) else {}
        overlay["general_enemy_watch"] = overlay_ew

    parent_node = oro[parent_ref.code]
    parent_leaf = parent_node[str(selected_level)]
    parent_row = cells(parent_leaf)
    parent_row[24] = ",".join(head_codes)
    overlay["orochi"][parent_code] = {
        str(selected_level): join(
            parent_row, isinstance(parent_leaf, (bytes, bytearray)))
    }
    try:
        overlay["boss_level"][parent_code] = clone_hit_boss_level_c2(
            bl[parent_ref.code], factor)
        for source_code, target_code in zip(source_heads, head_codes):
            overlay["general_boss"][target_code] = copy.deepcopy(gb[source_code])
            overlay["general_boss_variable"][target_code] = copy.deepcopy(
                gv[source_code])
            overlay["boss_level"][target_code] = clone_hit_boss_level_c2(
                bl[source_code], factor)
            if ("general_enemy_watch" in overlay
                    and isinstance(ew_self, dict) and source_code in ew_self):
                overlay["general_enemy_watch"]["1"][target_code] = copy.deepcopy(
                    ew_self[source_code])
    except (KeyError, TypeError, ValueError) as exc:
        return _clone_result_failure(f"dependency staging failed:{exc}")

    cloned_slots = []
    for slot in bundle.slots:
        single = (rbb.BossRef(3, parent_code)
                  if slot.single == parent_ref else slot.single)
        multi = (rbb.BossRef(3, parent_code)
                 if slot.multi == parent_ref else slot.multi)
        cloned_slots.append(replace(slot, single=single, multi=multi))
    cloned_selected = tuple(
        (layer, slot, tier) for layer, slot, tier in bundle.selected_levels)
    cloned_bundle = replace(
        bundle, slots=tuple(cloned_slots), selected_levels=cloned_selected)
    readback = expand_bundle_hp_members(cloned_bundle, selected_level, overlay)
    expected_total = source.total_hp * factor
    if (not readback.ok or readback.total_hp is None
            or not math.isclose(readback.total_hp, expected_total,
                                rel_tol=1e-9, abs_tol=1.0)):
        return _clone_result_failure(
            "overlay HP readback failed:"
            f"{readback.detail or readback.total_hp} expected={expected_total}")

    # Commit additions only after the complete nine-entity readback succeeds.
    oro[parent_code] = overlay["orochi"][parent_code]
    bl[parent_code] = overlay["boss_level"][parent_code]
    for target_code in head_codes:
        gb[target_code] = overlay["general_boss"][target_code]
        gv[target_code] = overlay["general_boss_variable"][target_code]
        bl[target_code] = overlay["boss_level"][target_code]
        if (isinstance(ew, dict)
                and target_code in overlay.get("general_enemy_watch", {}).get("1", {})):
            ew.setdefault("1", {})[target_code] = \
                overlay["general_enemy_watch"]["1"][target_code]

    clone_map = ((parent_ref, rbb.BossRef(3, parent_code)),) + tuple(
        (rbb.BossRef(1, source_code), rbb.BossRef(1, target_code))
        for source_code, target_code in zip(source_heads, head_codes))
    touched = ["orochi", "general_boss", "general_boss_variable", "boss_level"]
    if isinstance(ew, dict) and any(
            target_code in ew.get("1", {}) for target_code in head_codes):
        touched.append("general_enemy_watch")
    return OrochiCloneResult(
        True, parent_code=parent_code, head_codes=head_codes,
        clone_map=clone_map, bundle=cloned_bundle, expanded=readback,
        touched_tables=tuple(touched))


def purge_orochi_clones(tables: dict) -> tuple[str, ...]:
    """Purge only the dedicated ``mod_rogue_orochi*`` clone namespace."""
    touched: list[str] = []
    clone_pattern = re.compile(rf"{PRIVATE_PREFIX}orochi\d+(?:_head\d+)?$")
    for name in ("orochi", "general_boss", "general_boss_variable", "boss_level"):
        table = tables.get(name)
        if not isinstance(table, dict):
            continue
        keys = [key for key in table if clone_pattern.fullmatch(str(key))]
        for key in keys:
            table.pop(key, None)
        if keys:
            touched.append(name)
    ew = tables.get("general_enemy_watch")
    ew_self = ew.get("1") if isinstance(ew, dict) else None
    if isinstance(ew_self, dict):
        keys = [key for key in ew_self
                if clone_pattern.fullmatch(str(key))]
        for key in keys:
            ew_self.pop(key, None)
        if keys:
            touched.append("general_enemy_watch")
    return tuple(touched)


def purge_orochi_ex_clones(tables: dict) -> tuple[str, ...]:
    """Purge only round-local kind-4 parent/six-head clones."""
    touched: list[str] = []
    clone_pattern = re.compile(
        rf"{PRIVATE_PREFIX}orochi_ex\d+(?:_head[1-6])?$")
    for name in ("orochi_ex_head", "boss_level", "orochi_ex"):
        table = tables.get(name)
        if not isinstance(table, dict):
            continue
        keys = [key for key in table if clone_pattern.fullmatch(str(key))]
        for key in keys:
            table.pop(key, None)
        if keys:
            touched.append(name)
    return tuple(touched)


def purge_single_bar_special_clones(tables: dict) -> tuple[str, ...]:
    """Purge only the round-local proved single-bar clone namespaces."""

    touched: list[str] = []
    boss_level = tables.get("boss_level")
    for family in SINGLE_BAR_SPECIAL_SPECS:
        dedicated = tables.get(family)
        pattern = re.compile(rf"{PRIVATE_PREFIX}{re.escape(family)}\d+$")
        for name, table in ((family, dedicated), ("boss_level", boss_level)):
            if not isinstance(table, dict):
                continue
            keys = [key for key in table if pattern.fullmatch(str(key))]
            for key in keys:
                table.pop(key, None)
            if keys:
                touched.append(name)
    return tuple(dict.fromkeys(touched))


def purge_sphere_clones(tables: dict) -> tuple[str, ...]:
    """Purge exact round-local Sphere parents and their reserved child closure."""

    touched: list[str] = []
    boss_level = tables.get("boss_level")
    for family in SPHERE_SPECS:
        dedicated = tables.get(family)
        pattern = re.compile(rf"{PRIVATE_PREFIX}{re.escape(family)}(\d+)$")
        child_pattern = re.compile(
            rf"{PRIVATE_PREFIX}{re.escape(family)}(\d+)_g(\d+)c(\d+)$")
        parent_keys = ([
            key for key in dedicated if pattern.fullmatch(str(key))]
            if isinstance(dedicated, dict) else [])
        for parent_key in parent_keys:
            matched = pattern.fullmatch(str(parent_key))
            if matched is None:
                continue
            round_value = int(matched.group(1))
            parent_node = dedicated.get(parent_key)
            parent_rows = []
            if isinstance(parent_node, dict):
                for leaf in parent_node.values():
                    if isinstance(leaf, (str, bytes, bytearray)):
                        try:
                            parent_rows.append(cells(leaf))
                        except (TypeError, ValueError, UnicodeError):
                            continue
            for embedded_ordinal, group in enumerate(
                    SPHERE_SPECS[family].get("embedded") or (), start=1):
                if not group.get("scale_with_parent"):
                    continue
                clone_group_ordinal = 50 + embedded_ordinal
                for entity_ordinal, parent_column in enumerate(
                        group.get("level_columns") or (), start=1):
                    expected_level = _sphere_child_clone_code(
                        family, round_value, clone_group_ordinal,
                        entity_ordinal)
                    if not any(
                            int(parent_column) < len(row)
                            and str(row[int(parent_column)]).strip()
                            == expected_level
                            for row in parent_rows):
                        continue
                    if isinstance(boss_level, dict):
                        if boss_level.pop(expected_level, None) is not None:
                            touched.append("boss_level")
            for group_ordinal, group in enumerate(
                    SPHERE_SPECS[family].get("aux_groups") or (), start=1):
                if not group.get("scale_with_parent"):
                    continue
                if "level_parent_column" in group:
                    parent_column = int(group["level_parent_column"])
                    expected_level = _sphere_child_clone_code(
                        family, round_value, group_ordinal, 1)
                    if (any(
                            parent_column < len(row)
                            and str(row[parent_column]).strip() == expected_level
                            for row in parent_rows)
                            and isinstance(boss_level, dict)):
                        if boss_level.pop(expected_level, None) is not None:
                            touched.append("boss_level")
                    continue
                if "level_column" not in group:
                    continue
                table_name = str(group["table"])
                auxiliary_table = tables.get(table_name)
                if not isinstance(auxiliary_table, dict):
                    continue
                for entity_ordinal, parent_column in enumerate(
                        group["id_columns"], start=1):
                    expected_id = _sphere_aux_clone_id(
                        family, round_value, group_ordinal, entity_ordinal)
                    if not any(
                            int(parent_column) < len(row)
                            and str(row[int(parent_column)]).strip() == expected_id
                            for row in parent_rows):
                        continue
                    expected_level = _sphere_child_clone_code(
                        family, round_value, group_ordinal, entity_ordinal)
                    child_leaf = auxiliary_table.get(expected_id)
                    if not isinstance(child_leaf, (str, bytes, bytearray)):
                        continue
                    try:
                        child_row = cells(child_leaf)
                        actual_level = str(
                            child_row[int(group["level_column"])]).strip()
                    except (IndexError, KeyError, TypeError, ValueError,
                            UnicodeError):
                        continue
                    if actual_level != expected_level:
                        continue
                    auxiliary_table.pop(expected_id, None)
                    touched.append(table_name)
                    if isinstance(boss_level, dict):
                        if boss_level.pop(expected_level, None) is not None:
                            touched.append("boss_level")
            assert isinstance(dedicated, dict)
            dedicated.pop(parent_key, None)
            touched.append(family)
            if isinstance(boss_level, dict):
                if boss_level.pop(str(parent_key), None) is not None:
                    touched.append("boss_level")
        # Dependency-first persistence can be interrupted after boss_level or
        # auxiliary rows become durable but before the parent is saved.  Clean
        # only children whose string code and reserved numeric ID agree exactly.
        for group_ordinal, group in enumerate(
                SPHERE_SPECS[family].get("aux_groups") or (), start=1):
            if (not group.get("scale_with_parent")
                    or "level_column" not in group):
                continue
            table_name = str(group["table"])
            auxiliary_table = tables.get(table_name)
            if not isinstance(auxiliary_table, dict):
                continue
            orphan_ids: list[tuple[str, str]] = []
            for entity_id, child_leaf in auxiliary_table.items():
                if not isinstance(child_leaf, (str, bytes, bytearray)):
                    continue
                try:
                    child_row = cells(
                        bytes(child_leaf)
                        if isinstance(child_leaf, bytearray) else child_leaf)
                    level_code = str(
                        child_row[int(group["level_column"])]).strip()
                except (IndexError, KeyError, TypeError, ValueError,
                        UnicodeError):
                    continue
                match = child_pattern.fullmatch(level_code)
                if match is None:
                    continue
                round_value, encoded_group, entity_ordinal = map(
                    int, match.groups())
                if (encoded_group != group_ordinal
                        or not 1 <= entity_ordinal <= len(group["id_columns"])):
                    continue
                expected_id = _sphere_aux_clone_id(
                    family, round_value, group_ordinal, entity_ordinal)
                if str(entity_id) == expected_id:
                    orphan_ids.append((str(entity_id), level_code))
            for entity_id, level_code in orphan_ids:
                auxiliary_table.pop(entity_id, None)
                touched.append(table_name)
                if isinstance(boss_level, dict):
                    if boss_level.pop(level_code, None) is not None:
                        touched.append("boss_level")
        if isinstance(boss_level, dict):
            orphan_level_keys = [
                key for key in boss_level
                if pattern.fullmatch(str(key))
                or child_pattern.fullmatch(str(key))]
            for key in orphan_level_keys:
                boss_level.pop(key, None)
            if orphan_level_keys:
                touched.append("boss_level")
    return tuple(dict.fromkeys(touched))
