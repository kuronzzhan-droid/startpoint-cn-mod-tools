# Source section of rogue_build; loaded in its shared module namespace.
def inspect_sphere_bundle(
        bundle: rbb.NativeBossBundle, enemy_level: int,
        tables: dict) -> SphereGraph:
    """Validate a Sphere parent, all child sources and native-field identity."""

    family = special_bundle_family(bundle)
    if family not in SPHERE_SPECS:
        return SphereGraph(
            False, reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail="bundle is not a proved Sphere constructor")
    ref = _sphere_parent_ref(bundle, family)
    if ref is None:
        return SphereGraph(
            False, family=family, reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail="Sphere bundle does not have one exact parent")
    spec = SPHERE_SPECS[family]
    dedicated = tables.get(family)
    boss_level = tables.get("boss_level")
    if not isinstance(dedicated, dict) or not isinstance(boss_level, dict):
        return SphereGraph(
            False, family=family, parent_ref=ref,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail=f"{family} dedicated/boss_level table missing")
    node = dedicated.get(ref.code)
    if not isinstance(node, dict):
        return SphereGraph(
            False, family=family, parent_ref=ref,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail=f"{family}[{ref.code}] is not a level map")
    selected_values = {
        int(tier) for layer, slot, tier in bundle.selected_levels
        if any(item.layer == layer and item.slot == slot and item.single == ref
               for item in bundle.slots)
    }
    if len(selected_values) != 1:
        return SphereGraph(
            False, family=family, parent_ref=ref,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail=f"Sphere selected parent tier is not unique:{selected_values}")
    selected = next(iter(selected_values))
    if selected > int(enemy_level) or str(selected) not in node:
        return SphereGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail=f"Sphere selected tier drift:{selected}@enemy{enemy_level}")
    try:
        parent_row = cells(node[str(selected)])
        level_row = cells(boss_level[ref.code])
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        return SphereGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail=f"Sphere parent rows malformed:{exc}")
    if len(parent_row) != int(spec["columns"]):
        return SphereGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail=(f"{family} row has {len(parent_row)} columns;"
                    f"expected {spec['columns']}"))
    if len(level_row) != 13 or level_row[0] not in {"0", "1"}:
        return SphereGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail="Sphere parent boss_level is not a 13-column Hit/Fix row")
    parent_evidence = floor_native_hp(
        [ref.code], selected, standard_boss={}, boss_level=boss_level,
        orochi_ex={})
    parent_components = list(parent_evidence.get("components") or [])
    if (not parent_evidence.get("verified")
            or not parent_evidence.get("absolute_verified")
            or len(parent_components) != 1):
        return SphereGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail=("Sphere parent has no absolute HP proof:"
                    f"{parent_evidence.get('reason') or ref.code}"))

    rows_for_identity = [parent_row]
    auxiliaries: list[SphereAuxiliaryRef] = []
    try:
        for embedded in spec.get("embedded") or ():
            for ordinal, column in enumerate(embedded["level_columns"], start=1):
                level_code = str(parent_row[int(column)]).strip()
                auxiliaries.append(SphereAuxiliaryRef(
                    entity_id=f"embedded:{embedded['phase']}:{ordinal}",
                    level_code=level_code, selected_level=selected,
                    phase=str(embedded["phase"]), role=str(embedded["role"]),
                    source_table=family,
                    victory_component=bool(embedded.get("victory"))))
        for group in spec.get("aux_groups") or ():
            table_name = str(group["table"])
            table = tables.get(table_name)
            if not isinstance(table, dict):
                raise ValueError(f"Sphere auxiliary table missing:{table_name}")
            ids = tuple(str(parent_row[int(column)]).strip()
                        for column in group["id_columns"])
            if (len(set(ids)) != len(ids)
                    or any(not value or value == "(None)" for value in ids)):
                raise ValueError(
                    f"Sphere auxiliary IDs are not exact/distinct:{table_name}:{ids}")
            for entity_id in ids:
                child_row = cells(table[entity_id])
                if len(child_row) != int(group["columns"]):
                    raise ValueError(
                        f"{table_name}[{entity_id}] has {len(child_row)} columns;"
                        f"expected {group['columns']}")
                if "level_parent_column" in group:
                    level_code = str(
                        parent_row[int(group["level_parent_column"])]).strip()
                else:
                    level_code = str(child_row[int(group["level_column"])]).strip()
                rows_for_identity.append(child_row)
                auxiliaries.append(SphereAuxiliaryRef(
                    entity_id=entity_id, level_code=level_code,
                    selected_level=selected, phase=str(group["phase"]),
                    role=str(group["role"]), source_table=table_name,
                    victory_component=bool(group.get("victory"))))
    except (IndexError, KeyError, TypeError, ValueError, UnicodeError) as exc:
        return SphereGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            parent_hp_kind=("hit" if level_row[0] == "0" else "fix"),
            auxiliaries=tuple(auxiliaries),
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED", detail=str(exc))

    validated_auxiliaries: list[SphereAuxiliaryRef] = []
    for auxiliary in auxiliaries:
        child_evidence = floor_native_hp(
            [auxiliary.level_code], selected, standard_boss={},
            boss_level=boss_level, orochi_ex={})
        if (not auxiliary.level_code
                or not child_evidence.get("verified")
                or not child_evidence.get("absolute_verified")
                or len(child_evidence.get("components") or []) != 1):
            return SphereGraph(
                False, family=family, parent_ref=ref, selected_level=selected,
                parent_hp_kind=("hit" if level_row[0] == "0" else "fix"),
                auxiliaries=tuple(auxiliaries),
                reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
                detail=(f"Sphere child has no absolute HP/level proof:"
                        f"{auxiliary.source_table}/{auxiliary.entity_id}"
                        f"->{auxiliary.level_code}:"
                        f"{child_evidence.get('reason') or 'unknown'}"))
        validated_auxiliaries.append(replace(
            auxiliary,
            native_hp=float(child_evidence["components"][0]["native_hp"])))
    auxiliaries = validated_auxiliaries
    parent_hp = float(parent_components[0]["native_hp"])
    phase_budgets, behavior_error = _sphere_phase_budgets(
        family, parent_row, parent_hp, tuple(auxiliaries))
    if behavior_error is not None:
        return SphereGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            parent_hp_kind=("hit" if level_row[0] == "0" else "fix"),
            auxiliaries=tuple(auxiliaries), phase_budgets=phase_budgets,
            behavior_verified=False,
            reason="SPECIAL_PHASE_BEHAVIOR_UNSAFE", detail=behavior_error)
    lifecycle, lifecycle_error = _sphere_lifecycle_proof(
        family, parent_row, tuple(auxiliaries), phase_budgets)
    behavior_verified = (
        bool(phase_budgets) and lifecycle is not None
        and lifecycle.static_verified and lifecycle_error is None)
    if lifecycle_error is not None or lifecycle is None:
        return SphereGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            parent_hp_kind=("hit" if level_row[0] == "0" else "fix"),
            auxiliaries=tuple(auxiliaries), phase_budgets=phase_budgets,
            lifecycle=lifecycle, behavior_verified=False,
            reason="SPECIAL_PHASE_BEHAVIOR_UNSAFE",
            detail=lifecycle_error or "Sphere lifecycle proof missing")
    if any(value == ref.code for row in rows_for_identity for value in row):
        return SphereGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            parent_hp_kind=("hit" if level_row[0] == "0" else "fix"),
            auxiliaries=tuple(auxiliaries), phase_budgets=phase_budgets,
            lifecycle=lifecycle, behavior_verified=behavior_verified,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail="Sphere parent/child row embeds its parent master id")

    refs = tables.get("__code_references__")
    required_ref_sets = (
        "all_damage_share", "all_enemy_watch_partner",
        "all_enemy_watch_self", "all_boss_alive")
    if (not isinstance(refs, dict) or refs.get("degraded")
            or not all(key in refs for key in required_ref_sets)):
        return SphereGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            parent_hp_kind=("hit" if level_row[0] == "0" else "fix"),
            auxiliaries=tuple(auxiliaries), phase_budgets=phase_budgets,
            lifecycle=lifecycle, behavior_verified=behavior_verified,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail="Sphere external boss-code reference scan unavailable/degraded")
    ref_hits = [key for key in required_ref_sets
                if ref.code in set(map(str, refs.get(key) or ()))]
    if ref_hits:
        return SphereGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            parent_hp_kind=("hit" if level_row[0] == "0" else "fix"),
            auxiliaries=tuple(auxiliaries), phase_budgets=phase_budgets,
            lifecycle=lifecycle, behavior_verified=behavior_verified,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail="Sphere parent id has external references:" + ",".join(ref_hits))

    roots = tuple(dict.fromkeys(
        value.removesuffix(".action.dsl.amf3.deflate")
        for row in rows_for_identity for value in row
        if value.startswith("battle/action/")))
    identity = audit_native_action_identity(
        roots, ref.code, tables.get("__action_loader__"))
    if not identity.ok:
        return SphereGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            parent_hp_kind=("hit" if level_row[0] == "0" else "fix"),
            auxiliaries=tuple(auxiliaries), phase_budgets=phase_budgets,
            lifecycle=lifecycle, behavior_verified=behavior_verified,
            action_roots=roots,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED", detail=identity.detail)
    return SphereGraph(
        True, family=family, parent_ref=ref, selected_level=selected,
        parent_hp_kind=("hit" if level_row[0] == "0" else "fix"),
        auxiliaries=tuple(auxiliaries), phase_budgets=phase_budgets,
        lifecycle=lifecycle, behavior_verified=behavior_verified,
        action_roots=roots)


def sphere_native_hp_evidence(
        bundle: rbb.NativeBossBundle, enemy_level: int, tables: dict) -> dict:
    """Return exact victory HP: mandatory gates followed by the parent bar."""

    graph = inspect_sphere_bundle(bundle, enemy_level, tables)
    if (not graph.ok or graph.parent_ref is None
            or graph.selected_level is None or graph.family is None):
        return {
            "native_hp": None, "components": [], "verified": False,
            "absolute_verified": False,
            "reason": graph.reason or graph.detail, "detail": graph.detail,
            "graph": graph,
        }
    components: list[dict] = []
    phase_counts: dict[str, int] = {}
    for auxiliary in graph.auxiliaries:
        if not auxiliary.victory_component:
            continue
        evidence = floor_native_hp(
            [auxiliary.level_code], graph.selected_level,
            standard_boss={}, boss_level=tables["boss_level"], orochi_ex={})
        component = dict(evidence["components"][0])
        phase_counts[auxiliary.phase] = phase_counts.get(auxiliary.phase, 0) + 1
        ordinal = phase_counts[auxiliary.phase]
        component.update({
            "kind": "special", "special_family": graph.family,
            "phase": f"{auxiliary.phase}[{ordinal}]",
            "phase_ordinal": len(components) + 1,
            "selected_level": graph.selected_level,
            "evidence": {
                "logical": BOSS_LEVEL, "selected_level": graph.selected_level,
                "role": "mandatory_victory_gate",
                "entity_id": auxiliary.entity_id,
                "source_table": auxiliary.source_table,
            },
        })
        components.append(component)
    parent_evidence = floor_native_hp(
        [graph.parent_ref.code], graph.selected_level,
        standard_boss={}, boss_level=tables["boss_level"], orochi_ex={})
    parent_component = dict(parent_evidence["components"][0])
    parent_component.update({
        "kind": "special", "special_family": graph.family, "phase": "main",
        "phase_ordinal": len(components) + 1,
        "selected_level": graph.selected_level,
        "evidence": {
            "logical": BOSS_LEVEL, "selected_level": graph.selected_level,
            "role": "final_parent_victory_bar",
                "auxiliary_entities": [asdict(item) for item in graph.auxiliaries],
                "behavior_verified": graph.behavior_verified,
                "phase_budgets": [asdict(item) for item in graph.phase_budgets],
                "phase_lifecycle": (
                    asdict(graph.lifecycle) if graph.lifecycle is not None
                    else None),
                "auxiliary_role": (
                "mandatory_gate entries add to victory HP; damage_conduit "
                "entries transfer their damage to the parent and are not added twice"),
        },
    })
    components.append(parent_component)
    verified = bool(components) and all(
        component.get("evidence_kind") == "absolute" for component in components)
    return {
        "native_hp": (math.fsum(float(item["native_hp"]) for item in components)
                      if verified else None),
        "components": components, "verified": verified,
        "absolute_verified": verified,
        "reason": None if verified else "Sphere victory HP evidence drift",
        "graph": graph, "behavior_verified": graph.behavior_verified,
        "phase_budgets": [asdict(item) for item in graph.phase_budgets],
        "phase_lifecycle": (
            asdict(graph.lifecycle) if graph.lifecycle is not None else None),
    }


def inspect_orochi_ex_bundle(bundle: rbb.NativeBossBundle, enemy_level: int,
                             tables: dict) -> OrochiExGraph:
    """Validate the known parent→six-head graph without mutating any table.

    The official graph has one immutable schema.  Generated clones must retain
    the same six ordered child occurrences under a round-local namespace.  A
    future table drift therefore fails closed instead of guessing new columns.
    """
    parent_ref = _orochi_ex_parent_ref(bundle)
    if parent_ref is None:
        return OrochiExGraph(
            False, reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail="bundle is not one proved kind=4 Orochi EX parent")
    dedicated = tables.get("orochi_ex")
    heads = tables.get("orochi_ex_head")
    boss_level = tables.get("boss_level")
    if not all(isinstance(table, dict)
               for table in (dedicated, heads, boss_level)):
        return OrochiExGraph(
            False, parent_ref=parent_ref,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail="Orochi EX graph is missing parent/head/boss_level tables")
    try:
        selected, parent_row = wf_orochi_ex.select_parent_row(
            dedicated, parent_ref.code, int(enemy_level))
    except (KeyError, TypeError, ValueError,
            wf_orochi_ex.OrochiExHpError) as exc:
        return OrochiExGraph(
            False, parent_ref=parent_ref,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED", detail=str(exc))
    selected_values = {
        int(tier) for layer, slot, tier in bundle.selected_levels
        if any(item.layer == layer and item.slot == slot
               and item.single == parent_ref for item in bundle.slots)
    }
    if selected_values != {selected}:
        return OrochiExGraph(
            False, parent_ref=parent_ref, selected_level=selected,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail=("Orochi EX selected tier drift:bundle="
                    f"{sorted(selected_values)},parent={selected}"))
    if len(parent_row) != wf_orochi_ex.PARENT_COLUMNS:
        return OrochiExGraph(
            False, parent_ref=parent_ref, selected_level=selected,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail=f"Orochi EX parent row has {len(parent_row)} columns")
    child_codes = tuple(parent_row[index].strip()
                        for index in OROCHI_EX_CHILD_COLUMNS)
    expected_children = (
        OROCHI_EX_CANONICAL_HEADS if parent_ref.code == "orochi_ex" else
        tuple(f"{parent_ref.code}_head{ordinal}" for ordinal in range(1, 7))
    )
    if child_codes != expected_children or len(set(child_codes)) != 6:
        return OrochiExGraph(
            False, parent_ref=parent_ref, selected_level=selected,
            child_codes=child_codes,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail=("Orochi EX six-child closure drift:actual="
                    f"{child_codes},expected={expected_children}"))
    parent_level = boss_level.get(parent_ref.code)
    try:
        parent_level_row = cells(parent_level)
    except (TypeError, ValueError, UnicodeError) as exc:
        return OrochiExGraph(
            False, parent_ref=parent_ref, selected_level=selected,
            child_codes=child_codes,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail=f"Orochi EX parent boss_level malformed:{exc}")
    if len(parent_level_row) != wf_orochi_ex.BOSS_LEVEL_COLUMNS \
            or parent_level_row[0] != "0":
        return OrochiExGraph(
            False, parent_ref=parent_ref, selected_level=selected,
            child_codes=child_codes,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail="Orochi EX parent boss_level is not a 13-column Hit row")
    for code in child_codes:
        node = heads.get(code)
        if (not isinstance(node, dict)
                or select_surjective_level(node, selected) != selected):
            return OrochiExGraph(
                False, parent_ref=parent_ref, selected_level=selected,
                child_codes=child_codes,
                reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
                detail=f"Orochi EX child does not cover tier {selected}:{code}")
        leaf = node.get(str(selected))
        try:
            head_row = cells(leaf)
            level_row = cells(boss_level.get(code))
        except (TypeError, ValueError, UnicodeError) as exc:
            return OrochiExGraph(
                False, parent_ref=parent_ref, selected_level=selected,
                child_codes=child_codes,
                reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
                detail=f"Orochi EX child row malformed:{code}:{exc}")
        if len(head_row) != 179:
            return OrochiExGraph(
                False, parent_ref=parent_ref, selected_level=selected,
                child_codes=child_codes,
                reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
                detail=f"Orochi EX child row has {len(head_row)} columns:{code}")
        if len(level_row) != wf_orochi_ex.BOSS_LEVEL_COLUMNS or level_row[0] != "0":
            return OrochiExGraph(
                False, parent_ref=parent_ref, selected_level=selected,
                child_codes=child_codes,
                reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
                detail=f"Orochi EX child boss_level is not a Hit row:{code}")
        try:
            numeric = (float(level_row[2]), float(level_row[3]))
        except (TypeError, ValueError):
            numeric = (float("nan"), float("nan"))
        if not all(math.isfinite(value) and value > 0 for value in numeric):
            return OrochiExGraph(
                False, parent_ref=parent_ref, selected_level=selected,
                child_codes=child_codes,
                reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
                detail=f"Orochi EX child HP basis is invalid:{code}")
    return OrochiExGraph(
        True, parent_ref=parent_ref, selected_level=selected,
        child_codes=child_codes)


def _orochi_ex_head_native_hp(
        code: str, selected_level: int, boss_level: dict) -> float:
    """Read one Orochi EX head's absolute c86=1 HP from its Hit channel."""

    evidence = floor_native_hp(
        [str(code)], int(selected_level), standard_boss={},
        boss_level=boss_level, orochi_ex={})
    components = list(evidence.get("components") or ())
    if (not evidence.get("verified") or not evidence.get("absolute_verified")
            or len(components) != 1
            or components[0].get("evidence_kind") != "absolute"):
        raise wf_orochi_ex.OrochiExHpError(
            "Orochi EX head HP is not absolute:"
            f"{code}:{evidence.get('reason') or 'unknown'}")
    try:
        value = float(evidence["native_hp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise wf_orochi_ex.OrochiExHpError(
            f"Orochi EX head HP is not numeric:{code}") from exc
    if not math.isfinite(value) or value <= 0:
        raise wf_orochi_ex.OrochiExHpError(
            f"Orochi EX head HP is not finite positive:{code}:{value}")
    return value


def orochi_ex_phase_damage_capacity_contract(
        child_codes: tuple[str, ...], selected_level: int, boss_level: dict,
        *, phase1_required_hp: float, phase3_required_hp: float,
        required_coverage_ratio: float =
        OROCHI_EX_PHASE_CARRIER_COVERAGE_RATIO) -> dict:
    """Prove both fixed-phase gates against the six current head HP rows."""

    codes = tuple(map(str, child_codes))
    if len(codes) != 6 or len(set(codes)) != 6:
        raise wf_orochi_ex.OrochiExHpError(
            f"Orochi EX phase capacity needs six unique heads:{codes}")
    if not isinstance(boss_level, dict):
        raise wf_orochi_ex.OrochiExHpError(
            "Orochi EX phase capacity is missing boss_level")
    phases: list[dict] = []
    for phase, phase_codes, primary, required_hp in (
            (1, codes[:3], codes[1], phase1_required_hp),
            (3, codes[3:], codes[4], phase3_required_hp)):
        carrier_hp: dict[str, float] = {}
        carrier_c2: dict[str, float] = {}
        for code in phase_codes:
            try:
                row = cells(boss_level[code])
            except (KeyError, TypeError, ValueError, UnicodeError) as exc:
                raise wf_orochi_ex.OrochiExHpError(
                    f"Orochi EX phase{phase} head row malformed:{code}:{exc}"
                ) from exc
            if len(row) != wf_orochi_ex.BOSS_LEVEL_COLUMNS or row[0] != "0":
                raise wf_orochi_ex.OrochiExHpError(
                    f"Orochi EX phase{phase} head is not a Hit row:{code}")
            try:
                c2 = float(row[2])
            except (TypeError, ValueError) as exc:
                raise wf_orochi_ex.OrochiExHpError(
                    f"Orochi EX phase{phase} head c2 is not numeric:{code}"
                ) from exc
            if not math.isfinite(c2) or c2 <= 0:
                raise wf_orochi_ex.OrochiExHpError(
                    f"Orochi EX phase{phase} head c2 is invalid:{code}:{c2}")
            carrier_c2[code] = c2
            carrier_hp[code] = _orochi_ex_head_native_hp(
                code, int(selected_level), boss_level)
        phase_contract = wf_orochi_ex.validate_phase_damage_capacity(
            required_hp, carrier_hp,
            label=f"orochi_ex.phase{phase}",
            primary_carrier=primary,
            required_coverage_ratio=required_coverage_ratio)
        phase_contract.update({
            "phase": phase,
            "head_codes": phase_codes,
            "boss_level_c2": carrier_c2,
            "selected_level": int(selected_level),
            "absolute_verified": True,
            "static_verified": True,
        })
        phases.append(phase_contract)
    return {
        "schema": OROCHI_EX_PHASE_CAPACITY_SCHEMA,
        "selected_level": int(selected_level),
        "required_coverage_ratio": float(required_coverage_ratio),
        "phases": phases,
        "absolute_verified": True,
        "static_verified": True,
        "runtime_simulated": False,
        "gameplay_verified": False,
    }


def plan_orochi_ex_phase_damage_capacity(
        child_codes: tuple[str, ...], selected_level: int, boss_level: dict,
        *, phase1_required_hp: float, phase3_required_hp: float,
        minimum_scale: float,
        required_coverage_ratio: float =
        OROCHI_EX_PHASE_CARRIER_COVERAGE_RATIO,
        ) -> tuple[dict[str, str | bytes], dict]:
    """Plan c2-only head rows, then independently read back both phase gates."""

    codes = tuple(map(str, child_codes))
    if len(codes) != 6 or len(set(codes)) != 6:
        raise wf_orochi_ex.OrochiExHpError(
            f"Orochi EX phase capacity needs six unique heads:{codes}")
    try:
        floor_scale = float(minimum_scale)
        coverage = float(required_coverage_ratio)
    except (TypeError, ValueError) as exc:
        raise wf_orochi_ex.OrochiExHpError(
            "Orochi EX phase capacity scale/coverage is not numeric") from exc
    if (not math.isfinite(floor_scale) or floor_scale <= 0
            or not math.isfinite(coverage) or coverage < 1.0):
        raise wf_orochi_ex.OrochiExHpError(
            "Orochi EX phase capacity scale/coverage is invalid:"
            f"{minimum_scale},{required_coverage_ratio}")

    staged_level = dict(boss_level)
    planned_leaves: dict[str, str | bytes] = {}
    planning: list[dict] = []
    for phase, phase_codes, primary, required_hp in (
            (1, codes[:3], codes[1], phase1_required_hp),
            (3, codes[3:], codes[4], phase3_required_hp)):
        source_hp = {
            code: _orochi_ex_head_native_hp(
                code, int(selected_level), boss_level)
            for code in phase_codes
        }
        required_capacity = (
            float(required_hp) * coverage
            * (1.0 + OROCHI_EX_PHASE_CARRIER_FORMAT_MARGIN)
        )
        total_hp = math.fsum(source_hp.values())
        primary_hp = float(source_hp[primary])
        phase_scale = max(
            floor_scale,
            required_capacity / total_hp,
            required_capacity / primary_hp,
        )
        if not math.isfinite(phase_scale) or phase_scale <= 0:
            raise wf_orochi_ex.OrochiExHpError(
                f"Orochi EX phase{phase} carrier scale is invalid:{phase_scale}")
        source_c2: dict[str, float] = {}
        planned_c2: dict[str, float] = {}
        for code in phase_codes:
            source_row = cells(boss_level[code])
            source_c2[code] = float(source_row[2])
            planned = clone_hit_boss_level_c2(boss_level[code], phase_scale)
            planned_leaves[code] = planned
            staged_level[code] = planned
            planned_c2[code] = float(cells(planned)[2])
        planning.append({
            "phase": phase,
            "head_codes": phase_codes,
            "primary_carrier": primary,
            "source_head_codes": phase_codes,
            "source_to_target": {code: code for code in phase_codes},
            "minimum_scale": floor_scale,
            "planned_scale": phase_scale,
            "source_carrier_hp": source_hp,
            "source_total_carrier_hp": total_hp,
            "source_primary_carrier_hp": primary_hp,
            "source_boss_level_c2": source_c2,
            "planned_boss_level_c2": planned_c2,
        })

    contract = orochi_ex_phase_damage_capacity_contract(
        codes, int(selected_level), staged_level,
        phase1_required_hp=phase1_required_hp,
        phase3_required_hp=phase3_required_hp,
        required_coverage_ratio=coverage)
    for phase_contract, phase_plan in zip(contract["phases"], planning):
        if phase_contract["phase"] != phase_plan["phase"]:
            raise wf_orochi_ex.OrochiExHpError(
                "Orochi EX phase capacity plan/readback order drift")
        phase_contract.update(phase_plan)
    contract["minimum_scale"] = floor_scale
    contract["format_margin"] = OROCHI_EX_PHASE_CARRIER_FORMAT_MARGIN
    return planned_leaves, contract


def orochi_ex_native_hp_evidence(bundle: rbb.NativeBossBundle,
                                 enemy_level: int, tables: dict) -> dict:
    """Return the three victory HP bars after proving the six-child graph."""
    graph = inspect_orochi_ex_bundle(bundle, enemy_level, tables)
    if not graph.ok or graph.parent_ref is None or graph.selected_level is None:
        return {
            "native_hp": None, "components": [], "verified": False,
            "absolute_verified": False,
            "reason": graph.reason or graph.detail, "detail": graph.detail,
            "graph": graph,
        }
    evidence = floor_native_hp(
        [graph.parent_ref.code], graph.selected_level,
        standard_boss={}, boss_level=tables["boss_level"],
        orochi_ex=tables["orochi_ex"])
    components = list(evidence.get("components") or [])
    if (not evidence.get("verified") or not evidence.get("absolute_verified")
            or len(components) != 3):
        return dict(
            evidence, verified=False, absolute_verified=False,
            reason=evidence.get("reason") or "Orochi EX three-bar evidence drift",
            graph=graph)
    for ordinal, component in enumerate(components, start=1):
        component["special_family"] = "orochi_ex"
        component["phase"] = f"phase[{ordinal}]"
        component["phase_ordinal"] = ordinal
        component["selected_level"] = graph.selected_level
        component["evidence"] = {
            "logical": (
                f"{OROCHI_EX}.c{wf_orochi_ex.PHASE1_HP_COLUMN}"
                if ordinal == 1 else
                BOSS_LEVEL if ordinal == 2 else
                f"{OROCHI_EX}.c{wf_orochi_ex.PHASE3_HP_COLUMN}"
            ),
            "selected_level": graph.selected_level,
            "role": f"phase{ordinal}",
            "apply_quest_hp_correction": bool(
                component.get("apply_quest_hp_correction", True)),
        }
    try:
        threshold_contract = wf_orochi_ex.phase_threshold_icon_contract(
            float(components[0]["native_hp"]),
            float(components[1]["native_hp"]),
            float(components[2]["native_hp"]),
        )
    except (KeyError, TypeError, ValueError,
            wf_orochi_ex.OrochiExHpError) as exc:
        return dict(
            evidence, components=components, verified=False,
            absolute_verified=False,
            reason="Orochi EX phase threshold/icon contract failed",
            detail=str(exc), graph=graph,
            phase_threshold_contract=None)
    evidence["components"] = components
    evidence["graph"] = graph
    evidence["phase_threshold_contract"] = threshold_contract
    return evidence


def expand_bundle_hp_members(bundle: rbb.NativeBossBundle, enemy_level: int,
                             tables: dict) -> HpExpansionResult:
    """Expand an Orochi parent into one parent plus eight ordered head instances.

    ``total_hp`` is the raw :func:`true_stat` sum before the event-level K/c86
    multipliers.  The parent c24 list is occurrence-based: duplicate head codes
    remain duplicate members and are never collapsed into a set.
    """
    parent_ref = _orochi_parent_ref(bundle)
    if parent_ref is None:
        return _special_hp_failure("bundle is not one proved kind=3 Orochi parent")
    oro = tables.get("orochi")
    gb = tables.get("general_boss")
    gv = tables.get("general_boss_variable")
    bl = tables.get("boss_level")
    if not all(isinstance(table, dict) for table in (oro, gb, gv, bl)):
        return _special_hp_failure("Orochi HP expansion is missing one of oro/gb/gv/bl")
    parent_node = oro.get(parent_ref.code)
    selected = select_surjective_level(parent_node, enemy_level)
    if selected is None:
        return _special_hp_failure(
            f"{parent_ref.code} has no first tier >= lv{enemy_level}")
    parent_leaf = parent_node.get(str(selected)) if isinstance(parent_node, dict) else None
    if not isinstance(parent_leaf, (str, bytes, bytearray)):
        return _special_hp_failure(
            f"{parent_ref.code}@{selected} parent row is missing", selected)
    try:
        parent_row = cells(parent_leaf)
    except (TypeError, ValueError, UnicodeError) as exc:
        return _special_hp_failure(
            f"{parent_ref.code}@{selected} parent row cannot be parsed:{exc}", selected)
    if len(parent_row) < 25:
        return _special_hp_failure(
            f"{parent_ref.code}@{selected} parent row has {len(parent_row)} columns", selected)
    heads = tuple(code.strip() for code in parent_row[24].split(",")
                  if code.strip() and code.strip() != "(None)")
    if len(heads) != 8:
        return _special_hp_failure(
            f"{parent_ref.code}@{selected} c24 has {len(heads)} heads instead of 8",
            selected)

    specs = ((parent_ref.code, 3, "parent", 0),) + tuple(
        (code, 1, "head", ordinal)
        for ordinal, code in enumerate(heads, start=1))
    members: list[HpMember] = []
    for code, kind, role, ordinal in specs:
        leaf = bl.get(code)
        if not isinstance(leaf, (str, bytes, bytearray)):
            return _special_hp_failure(f"boss_level leaf missing:{code}", selected)
        try:
            hp_row = cells(leaf)
        except (TypeError, ValueError, UnicodeError) as exc:
            return _special_hp_failure(f"boss_level malformed:{code}:{exc}", selected)
        if len(hp_row) < 13 or hp_row[0] != "0":
            return _special_hp_failure(
                f"boss_level is not finite positive Hit HP:{code}", selected)
        try:
            c2 = float(hp_row[2])
            c3 = float(hp_row[3])
        except (TypeError, ValueError) as exc:
            return _special_hp_failure(f"boss_level malformed:{code}:{exc}", selected)
        if not all(math.isfinite(value) and value > 0 for value in (c2, c3)):
            return _special_hp_failure(
                f"boss_level is not finite positive Hit HP:{code}", selected)
        # ``true_stat`` intentionally proxies unknown curves for relative pool
        # ranking.  Orochi cloning needs an absolute nine-member readback, so
        # that fallback is forbidden here: an unknown/non-positive curve would
        # turn a guessed value into the c2 scaling baseline.
        curve_name = hp_row[4]
        curve = curve_value("hp", curve_name, selected)
        if curve is None or not math.isfinite(curve) or curve <= 0:
            return _special_hp_failure(
                f"unknown or invalid Hit HP curve:{code}:{curve_name}@{selected}",
                selected)
        if role == "head":
            gb_node = gb.get(code)
            gv_node = gv.get(code)
            if not isinstance(gb_node, dict) or not isinstance(gv_node, dict):
                return _special_hp_failure(f"head gb/gv dependency missing:{code}", selected)
            # Heads are dependencies of the selected parent row.  Prove that
            # exact tier directly; do not apply the ordinary standalone-general
            # "gv must have a low tier" rule (multi_plus intentionally has [100]).
            if (select_surjective_level(gb_node, selected) != selected
                    or select_surjective_level(gv_node, selected) != selected):
                return _special_hp_failure(
                    f"head does not cover parent-selected tier {selected}:{code}", selected)
        stat = true_stat(code, "hp", selected, bl)
        raw_hp = float(stat[0]) if stat is not None else float("nan")
        if not math.isfinite(raw_hp) or raw_hp <= 0:
            return _special_hp_failure(f"raw HP cannot be proved:{code}", selected)
        members.append(HpMember(
            code=code, kind=kind, role=role, ordinal=ordinal,
            selected_level=selected, raw_hp=raw_hp))
    return HpExpansionResult(
        True, members=tuple(members), total_hp=math.fsum(
            member.raw_hp for member in members),
        selected_parent_level=selected)


def orochi_native_hp_evidence(bundle: rbb.NativeBossBundle, enemy_level: int,
                              tables: dict) -> dict:
    """Split Orochi's victory HP bar from its eight mechanism heads.

    ``expand_bundle_hp_members`` intentionally reports the BossLevel ``true_stat``
    before the event battle-level K.  The ordinary floor adapter reports HP at
    quest c86=1, so this bridge applies the one confirmed K exactly once and
    preserves every actual occurrence in parent/c24 order.

    Only the central parent is the victory-condition HP bar shown to the player.
    The eight heads are mortal mechanism actors and remain an independently
    scaled/audited ``mechanism_budget``; counting them toward the strict floor
    target cuts the visible parent bar roughly in half and is therefore forbidden.
    """
    expanded = expand_bundle_hp_members(bundle, int(enemy_level), tables)
    selected = expanded.selected_parent_level
    scale = GENERAL_HP_LEVEL_SCALE.get(int(selected)) if selected is not None else None
    if not expanded.ok or expanded.total_hp is None or scale is None:
        detail = expanded.detail or (
            f"lv{selected} 的 Orochi K 未经确认" if selected is not None
            else "Orochi parent selected level is missing")
        return {
            "native_hp": None, "components": [], "verified": False,
            "absolute_verified": False,
            "reason": expanded.reason or detail, "detail": detail,
            "expanded": expanded,
        }
    components: list[dict] = []
    mechanism_components: list[dict] = []
    for occurrence, member in enumerate(expanded.members, start=1):
        phase = ("parent" if member.role == "parent"
                 else f"head[{member.ordinal}]")
        component = {
            "code": member.code,
            "kind": "special",
            "special_family": "orochi",
            "phase": phase,
            "phase_ordinal": member.ordinal,
            "boss_occurrence": occurrence,
            "evidence_kind": "absolute",
            "native_hp": round(float(member.raw_hp) * float(scale), 6),
            "true_stat": float(member.raw_hp),
            "k": float(scale),
            "hp_curve_kind": "hit",
            "selected_level": int(member.selected_level),
            "counts_toward_boss_target": member.role == "parent",
            "budget_kind": ("victory_hp" if member.role == "parent"
                            else "mechanism_budget"),
            "evidence": {
                "logical": (f"{OROCHI}.c24 -> {BOSS_LEVEL}"
                            if member.role == "parent" else BOSS_LEVEL),
                "selected_level": int(member.selected_level),
                "role": member.role,
                "ordinal": int(member.ordinal),
            },
        }
        if member.role == "parent":
            components.append(component)
        else:
            mechanism_components.append(component)
    if len(components) != 1 or len(mechanism_components) != 8:
        return {
            "native_hp": None, "components": components,
            "mechanism_components": mechanism_components,
            "verified": False, "absolute_verified": False,
            "reason": ("Orochi 胜利/机制组件数量非法:"
                       f"parent={len(components)},heads={len(mechanism_components)}"),
            "expanded": expanded,
        }
    mechanism_hp = math.fsum(
        float(item["native_hp"]) for item in mechanism_components)
    return {
        "native_hp": math.fsum(float(item["native_hp"])
                               for item in components),
        "components": components,
        "mechanism_hp": mechanism_hp,
        "mechanism_components": mechanism_components,
        "mechanism_budget": {
            "kind": "orochi_heads",
            "counts_toward_boss_target": False,
            "victory_condition": "central_parent_only",
            "native_hp": mechanism_hp,
            "occurrences": len(mechanism_components),
        },
        "verified": True,
        "absolute_verified": True,
        "reason": None,
        "expanded": expanded,
    }
