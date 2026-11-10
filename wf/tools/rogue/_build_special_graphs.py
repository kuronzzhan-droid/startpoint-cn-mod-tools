# Source section of rogue_build; loaded in its shared module namespace.
def _sphere_phase_budgets(
        family: str, parent_row: list[str], parent_hp: float,
        auxiliaries: tuple[SphereAuxiliaryRef, ...]) \
        -> tuple[tuple[SpherePhaseBudget, ...], str | None]:
    """Recompute native/runtime phase closure from client-proved contracts."""

    contracts = tuple(SPHERE_SPECS[family].get("phase_contracts") or ())
    if not contracts:
        return (), None
    budgets: list[SpherePhaseBudget] = []
    for contract in contracts:
        phase = str(contract["phase"])
        member_phases = tuple(map(
            str, contract.get("member_phases") or (phase,)))
        matching = tuple(
            item for item in auxiliaries if item.phase in member_phases)
        try:
            entry = float(parent_row[int(contract["entry_column"])])
            exit_ratio = (float(parent_row[int(contract["exit_column"])])
                          if "exit_column" in contract
                          else float(contract["exit_ratio"]))
            expected_entities = int(contract["expected_entities"])
            expected_completion_raw = contract.get("expected_completion_count")
            expected_completion = (
                None if expected_completion_raw is None
                else int(expected_completion_raw))
            occurrences_per_entity = int(
                contract.get("occurrences_per_entity", 1))
            native_child_hp = tuple(float(item.native_hp) for item in matching)
            child_hp = native_child_hp * occurrences_per_entity
            overdamage = bool(contract["overdamage"])
            budget_model = str(
                contract.get("budget_model") or "capped_child_hp")
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            return tuple(budgets), f"{phase} contract is malformed:{exc}"
        if (not math.isfinite(parent_hp) or parent_hp <= 0
                or not (0 <= exit_ratio < entry <= 1)):
            return tuple(budgets), (
                f"{phase} threshold/parent HP is invalid:"
                f"entry={entry},exit={exit_ratio},parent={parent_hp}")
        if (len(matching) != expected_entities
                or occurrences_per_entity <= 0
                or any(item.role != "damage_conduit" for item in matching)
                or any(not math.isfinite(value) or value <= 0
                       for value in native_child_hp)):
            return tuple(budgets), (
                f"{phase} conduit set drift:count={len(matching)}/"
                f"{expected_entities},roles={[item.role for item in matching]},"
                f"hp={native_child_hp},occurrences={occurrences_per_entity}")
        if budget_model not in {"capped_child_hp", "raw_hit_overdamage"}:
            return tuple(budgets), (
                f"{phase} unknown phase budget model:{budget_model}")
        if budget_model == "raw_hit_overdamage" and not overdamage:
            return tuple(budgets), (
                f"{phase} raw-hit budget requires client overdamage")
        if budget_model == "capped_child_hp" and expected_completion is None:
            return tuple(budgets), (
                f"{phase} capped budget lacks expected completion count")
        required = parent_hp * (entry - exit_ratio)
        available = math.fsum(child_hp)
        tolerance = max(
            HP_TARGET_ABS_TOLERANCE,
            abs(required) * HP_TARGET_REL_TOLERANCE)
        completion: int | None = None
        if budget_model == "capped_child_hp":
            cumulative = 0.0
            for count, value in enumerate(
                    sorted(child_hp, reverse=True), start=1):
                cumulative += value
                if cumulative + tolerance >= required:
                    completion = count
                    break
            verified = (
                available + tolerance >= required
                and completion == expected_completion)
        else:
            # SphereMicronucleus.applyAttack forwards param1.damage rather than
            # its capped local HP loss.  Child HP therefore is only a durability
            # lower bound; exact closure is the preserved occurrence/scale model.
            verified = expected_completion is None
        budget = SpherePhaseBudget(
            phase=phase, entry_ratio=entry, exit_ratio=exit_ratio,
            parent_hp=parent_hp, required_damage_hp=required,
            available_damage_hp=available,
            coverage_ratio=(available / required if required > 0 else math.inf),
            completion_count=completion,
            expected_completion_count=expected_completion,
            entity_ids=tuple(item.entity_id for item in matching),
            level_codes=tuple(item.level_code for item in matching),
            occurrences_per_entity=occurrences_per_entity,
            entity_occurrence_count=len(matching) * occurrences_per_entity,
            overdamage=overdamage, budget_model=budget_model,
            verified=verified)
        budgets.append(budget)
        if not verified:
            return tuple(budgets), (
                f"{phase} damage budget is not closed:required={required:g},"
                f"available={available:g},coverage={budget.coverage_ratio:g},"
                f"completion={completion},expected={expected_completion},"
                f"model={budget_model}")
    return tuple(budgets), None


def _sphere_lifecycle_proof(
        family: str, parent_row: list[str],
        auxiliaries: tuple[SphereAuxiliaryRef, ...],
        phase_budgets: tuple[SpherePhaseBudget, ...]) \
        -> tuple[SphereLifecycleProof | None, str | None]:
    """Close every static phase edge without claiming runtime simulation.

    The four-edge topology comes from the client 1.8.1 Sphere state machine:
    ``Sphere.changePhase`` enters ``getInitialStateByNextPhase`` for phases
    2..4, while a depleted phase-4 parent enters ``Sphere.enterDeadState``.
    Family contracts bind those edges to the exact constructor children and
    the independently recomputed damage budgets above.
    """

    contracts = tuple(SPHERE_SPECS[family].get("lifecycle_contracts") or ())
    expected_targets = (2, 3, 4, None)
    if len(contracts) != 4:
        return None, f"lifecycle edge count drift:{len(contracts)}/4"
    budgets_by_phase = {budget.phase: budget for budget in phase_budgets}
    budget_members = {
        str(contract["phase"]): tuple(map(
            str, contract.get("member_phases") or (contract["phase"],)))
        for contract in (SPHERE_SPECS[family].get("phase_contracts") or ())
    }
    if len(budgets_by_phase) != len(phase_budgets):
        return None, "phase damage budgets contain duplicate phase keys"
    used_budgets: set[str] = set()
    used_gate_ids: set[str] = set()
    steps: list[SphereLifecycleStep] = []
    allowed_triggers = {
        "mandatory_gate_clear", "parent_hp_threshold",
        "child_damage_threshold", "parent_hp_depleted",
    }
    for sequence, (contract, target_expected) in enumerate(
            zip(contracts, expected_targets), start=1):
        try:
            source_phase = int(contract["source_phase"])
            target_raw = contract.get("target_phase")
            target_phase = None if target_raw is None else int(target_raw)
            trigger = str(contract["trigger"])
        except (KeyError, TypeError, ValueError) as exc:
            return None, f"lifecycle edge {sequence} malformed:{exc}"
        if (source_phase != sequence or target_phase != target_expected
                or trigger not in allowed_triggers):
            return None, (
                f"lifecycle edge {sequence} topology drift:"
                f"phase={source_phase}->{target_phase},trigger={trigger}")

        threshold_ratio: float | None = None
        member_phases: tuple[str, ...] = ()
        expected_entities = 0
        expected_completion: int | None = None
        entity_ids: tuple[str, ...] = ()
        budget_phase: str | None = None
        verified = False
        if trigger == "mandatory_gate_clear":
            member_phases = tuple(map(
                str, contract.get("member_phases") or ()))
            matching = tuple(
                item for item in auxiliaries
                if item.phase in member_phases and item.victory_component)
            try:
                expected_entities = int(contract["expected_entities"])
                expected_completion = int(
                    contract["expected_completion_count"])
            except (KeyError, TypeError, ValueError) as exc:
                return None, f"lifecycle gate {sequence} malformed:{exc}"
            entity_ids = tuple(item.entity_id for item in matching)
            verified = (
                source_phase == 1 and bool(member_phases)
                and len(matching) == expected_entities
                and expected_completion == expected_entities
                and len(set(entity_ids)) == len(entity_ids))
            used_gate_ids.update(entity_ids)
        elif trigger == "parent_hp_threshold":
            try:
                threshold_ratio = float(
                    parent_row[int(contract["threshold_column"])])
            except (IndexError, KeyError, TypeError, ValueError) as exc:
                return None, f"lifecycle threshold {sequence} malformed:{exc}"
            verified = (
                target_phase is not None and math.isfinite(threshold_ratio)
                and 0 < threshold_ratio < 1)
        elif trigger == "child_damage_threshold":
            budget_phase = str(contract.get("budget_phase") or "")
            budget = budgets_by_phase.get(budget_phase)
            if budget is None:
                return None, (
                    f"lifecycle edge {sequence} lacks phase budget:"
                    f"{budget_phase or '(missing)'}")
            used_budgets.add(budget_phase)
            threshold_ratio = budget.exit_ratio
            member_phases = budget_members.get(budget_phase, ())
            expected_entities = len(budget.entity_ids)
            expected_completion = budget.expected_completion_count
            entity_ids = budget.entity_ids
            verified = (
                budget.verified and expected_entities > 0
                and len(set(entity_ids)) == expected_entities
                and math.isfinite(threshold_ratio)
                and 0 <= threshold_ratio < 1)
        else:
            threshold_ratio = 0.0
            verified = source_phase == 4 and target_phase is None

        next_state_entry = (
            f"getInitialStateByNextPhase({target_phase})"
            if target_phase is not None else "Sphere.enterDeadState")
        step = SphereLifecycleStep(
            sequence=sequence, source_phase=source_phase,
            target_phase=target_phase, trigger=trigger,
            threshold_ratio=threshold_ratio, member_phases=member_phases,
            expected_entities=expected_entities,
            expected_completion_count=expected_completion,
            entity_ids=entity_ids, budget_phase=budget_phase,
            next_state_entry=next_state_entry, verified=verified)
        steps.append(step)
        if not verified:
            return None, (
                f"lifecycle edge {sequence} is not closed:"
                f"{source_phase}->{target_phase}/{trigger},"
                f"entities={len(entity_ids)}/{expected_entities},"
                f"completion={expected_completion}")

    required_gate_ids = {
        item.entity_id for item in auxiliaries if item.victory_component}
    if used_gate_ids != required_gate_ids:
        return None, (
            "lifecycle mandatory victory gates drift:"
            f"used={sorted(used_gate_ids)},required={sorted(required_gate_ids)}")
    if used_budgets != set(budgets_by_phase):
        return None, (
            "lifecycle phase budget coverage drift:"
            f"used={sorted(used_budgets)},"
            f"required={sorted(budgets_by_phase)}")
    proof = SphereLifecycleProof(
        family=family, steps=tuple(steps),
        victory_component_count=1 + len(required_gate_ids),
        client_contract=(
            "client-1.8.1:Sphere.changePhase/getInitialStateByNextPhase/"
            "enterDeadState"),
        static_verified=True)
    return proof, None


def _special_hp_failure(detail: str,
                        selected_level: int | None = None) -> HpExpansionResult:
    return HpExpansionResult(
        False, selected_parent_level=selected_level,
        reason="SPECIAL_HP_CHANNEL_UNSUPPORTED", detail=detail)


def _orochi_parent_ref(bundle: rbb.NativeBossBundle) -> rbb.BossRef | None:
    refs = [slot.single for slot in bundle.slots if slot.single is not None]
    if len(refs) != 1:
        return None
    ref = refs[0]
    if (ref.kind != 3
            or (ref.code not in rbb.OROCHI_PARENT_VARIANTS
                and re.fullmatch(rf"{PRIVATE_PREFIX}orochi\d+", ref.code) is None)):
        return None
    return ref


def _orochi_ex_parent_ref(bundle: rbb.NativeBossBundle) -> rbb.BossRef | None:
    refs = [slot.single for slot in bundle.slots if slot.single is not None]
    if len(refs) != 1:
        return None
    ref = refs[0]
    if (ref.kind != 4
            or (ref.code != "orochi_ex"
                and re.fullmatch(rf"{PRIVATE_PREFIX}orochi_ex\d+", ref.code) is None)):
        return None
    return ref


def _single_bar_special_parent_ref(
        bundle: rbb.NativeBossBundle,
        family: str | None = None) -> rbb.BossRef | None:
    refs = [slot.single for slot in bundle.slots if slot.single is not None]
    if len(refs) != 1:
        return None
    ref = refs[0]
    candidates = (
        (family,) if family in SINGLE_BAR_SPECIAL_SPECS
        else tuple(SINGLE_BAR_SPECIAL_SPECS))
    for name in candidates:
        spec = SINGLE_BAR_SPECIAL_SPECS[name]
        if ref.kind != int(spec["kind"]):
            continue
        if (not ref.code.startswith(f"{PRIVATE_PREFIX}")
                or re.fullmatch(rf"{PRIVATE_PREFIX}{re.escape(name)}\d+", ref.code)):
            return ref
    return None


def _sphere_parent_ref(
        bundle: rbb.NativeBossBundle,
        family: str | None = None) -> rbb.BossRef | None:
    refs = [slot.single for slot in bundle.slots if slot.single is not None]
    if len(refs) != 1:
        return None
    ref = refs[0]
    candidates = ((family,) if family in SPHERE_SPECS else tuple(SPHERE_SPECS))
    for name in candidates:
        spec = SPHERE_SPECS[name]
        if ref.kind != int(spec["kind"]):
            continue
        if (ref.code == str(spec["canonical"])
                or re.fullmatch(rf"{PRIVATE_PREFIX}{re.escape(name)}\d+", ref.code)):
            return ref
    return None


def special_bundle_family(bundle: rbb.NativeBossBundle) -> str | None:
    """Return the exact proved constructor family for a native special bundle."""
    if _orochi_parent_ref(bundle) is not None:
        return "orochi"
    if _orochi_ex_parent_ref(bundle) is not None:
        return "orochi_ex"
    for family in SINGLE_BAR_SPECIAL_SPECS:
        if _single_bar_special_parent_ref(bundle, family) is not None:
            return family
    for family in SPHERE_SPECS:
        if _sphere_parent_ref(bundle, family) is not None:
            return family
    return None


def audit_native_action_identity(
        action_roots: tuple[str, ...] | list[str], identifier: str,
        loader, *, max_actions: int = 2048) -> rbb.GateResult:
    """Prove parent-id absence without reclassifying official callbacks.

    Sphere callbacks such as CreateReferencePoint may execute their block once
    per runtime subject.  Cardinality is irrelevant here because Sphere stays
    on its official field and no child/action reference is rewritten.  This
    bounded recursive walk therefore proves only the rename property: every
    statically named action must load and none may contain the parent master id.
    Terrain/spawn portability remains outside this native-only proof.
    """

    if not callable(loader):
        return rbb.GateResult(False, "ACTION_CLOSURE_UNAUDITED",
                              detail="native action loader missing")
    target = str(identifier)
    queue = [str(root).removesuffix(".action.dsl.amf3.deflate")
             for root in action_roots]
    seen: set[str] = set()
    try:
        while queue:
            logical = queue.pop(0)
            if logical in seen:
                continue
            if (not logical.startswith("battle/action/")
                    or len(seen) >= int(max_actions)):
                raise ValueError(
                    f"invalid/unbounded native action closure:{logical}")
            seen.add(logical)
            value = loader(logical)
            stack = [value]
            while stack:
                item = stack.pop()
                if isinstance(item, dict):
                    stack.extend(item.values())
                elif isinstance(item, (list, tuple)):
                    stack.extend(item)
                elif isinstance(item, str):
                    if item == target:
                        raise ValueError(
                            f"action {logical} contains parent master id:{target}")
                    if item.startswith("battle/action/"):
                        child = item.removesuffix(".action.dsl.amf3.deflate")
                        if child not in seen:
                            queue.append(child)
    except (FileNotFoundError, KeyError, TypeError, ValueError, zlib.error) as exc:
        return rbb.GateResult(False, "ACTION_CLOSURE_UNAUDITED", detail=str(exc))
    return rbb.GateResult(
        True, source_table="native_action_identity",
        detail=f"{len(seen)} recursively named actions are parent-id independent")


def inspect_single_bar_special_bundle(
        bundle: rbb.NativeBossBundle, enemy_level: int,
        tables: dict) -> SingleBarSpecialGraph:
    """Validate one proved single-bar parent and its rename-safe closure."""

    family = special_bundle_family(bundle)
    if family not in SINGLE_BAR_SPECIAL_SPECS:
        return SingleBarSpecialGraph(
            False, reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail="bundle is not a proved single-bar special constructor")
    ref = _single_bar_special_parent_ref(bundle, family)
    if ref is None:
        return SingleBarSpecialGraph(
            False, family=family, reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail="single-bar special bundle does not have one parent")
    spec = SINGLE_BAR_SPECIAL_SPECS[family]
    dedicated = tables.get(family)
    boss_level = tables.get("boss_level")
    if not isinstance(dedicated, dict) or not isinstance(boss_level, dict):
        return SingleBarSpecialGraph(
            False, family=family, parent_ref=ref,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail=f"{family} dedicated/boss_level table missing")
    node = dedicated.get(ref.code)
    if not isinstance(node, dict):
        return SingleBarSpecialGraph(
            False, family=family, parent_ref=ref,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail=f"{family}[{ref.code}] is not a level map")
    selected_values = {
        int(tier) for layer, slot, tier in bundle.selected_levels
        if any(item.layer == layer and item.slot == slot and item.single == ref
               for item in bundle.slots)
    }
    if len(selected_values) != 1:
        return SingleBarSpecialGraph(
            False, family=family, parent_ref=ref,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail=f"selected parent tier is not unique:{sorted(selected_values)}")
    selected = next(iter(selected_values))
    if selected > int(enemy_level) or str(selected) not in node:
        return SingleBarSpecialGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail=f"selected tier drift:{selected}@enemy{enemy_level}")
    try:
        dedicated_row = cells(node[str(selected)])
        level_row = cells(boss_level[ref.code])
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        return SingleBarSpecialGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail=f"dedicated/boss_level row malformed:{exc}")
    if len(dedicated_row) != int(spec["columns"]):
        return SingleBarSpecialGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail=(f"{family} row has {len(dedicated_row)} columns;"
                    f"expected {spec['columns']}"))
    if any(value == ref.code for value in dedicated_row):
        return SingleBarSpecialGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail="dedicated row embeds its parent master id")
    if len(level_row) != 13 or level_row[0] != "0":
        return SingleBarSpecialGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail="single-bar parent boss_level is not a 13-column Hit row")
    try:
        numeric = (float(level_row[2]), float(level_row[3]))
    except (TypeError, ValueError):
        numeric = (float("nan"), float("nan"))
    curve = curve_value("hp", level_row[4], selected)
    if (not all(math.isfinite(value) and value > 0 for value in numeric)
            or curve is None or not math.isfinite(curve) or curve <= 0
            or selected not in GENERAL_HP_LEVEL_SCALE):
        return SingleBarSpecialGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail=f"single-bar parent has no absolute Hit HP proof@{selected}")

    auxiliary_refs: tuple[str, ...] = ()
    funnel_columns = tuple(spec.get("funnel_ref_columns") or ())
    if funnel_columns:
        tentacle = tables.get("kraken_tentacle")
        funnel_level = tables.get("kraken_funnel_level")
        if not isinstance(tentacle, dict) or not isinstance(funnel_level, dict):
            return SingleBarSpecialGraph(
                False, family=family, parent_ref=ref, selected_level=selected,
                reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
                detail="Kraken tentacle/funnel_level dependency tables missing")
        try:
            auxiliary_refs = tuple(dedicated_row[index].strip()
                                   for index in funnel_columns)
        except (IndexError, AttributeError) as exc:
            return SingleBarSpecialGraph(
                False, family=family, parent_ref=ref, selected_level=selected,
                reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
                detail=f"Kraken tentacle reference columns malformed:{exc}")
        if (len(auxiliary_refs) != 2 or len(set(auxiliary_refs)) != 2
                or any(not code or code == "(None)" for code in auxiliary_refs)):
            return SingleBarSpecialGraph(
                False, family=family, parent_ref=ref, selected_level=selected,
                auxiliary_refs=auxiliary_refs,
                reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
                detail=f"Kraken must name two distinct tentacles:{auxiliary_refs}")
        for code in auxiliary_refs:
            node = tentacle.get(code)
            child_level = select_surjective_level(node, selected)
            try:
                child_row = cells(node[str(child_level)])
                child_level_row = cells(funnel_level[code])
            except (KeyError, TypeError, ValueError, UnicodeError) as exc:
                return SingleBarSpecialGraph(
                    False, family=family, parent_ref=ref,
                    selected_level=selected, auxiliary_refs=auxiliary_refs,
                    reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
                    detail=f"Kraken tentacle dependency malformed:{code}:{exc}")
            if child_level is None or len(child_row) != 13 \
                    or len(child_level_row) != 13:
                return SingleBarSpecialGraph(
                    False, family=family, parent_ref=ref,
                    selected_level=selected, auxiliary_refs=auxiliary_refs,
                    reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
                    detail=(f"Kraken tentacle does not cover tier {selected} "
                            f"with 13-column rows:{code}"))

    refs = tables.get("__code_references__")
    if not isinstance(refs, dict) or refs.get("degraded"):
        return SingleBarSpecialGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail="external boss-code reference scan unavailable/degraded")
    required_ref_sets = (
        "all_damage_share", "all_enemy_watch_partner",
        "all_enemy_watch_self", "all_boss_alive")
    if not all(key in refs for key in required_ref_sets):
        return SingleBarSpecialGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail="external reference snapshot lacks dedicated-id coverage")
    ref_hits = [key for key in required_ref_sets
                if ref.code in set(map(str, refs.get(key) or ()))]
    if ref_hits:
        return SingleBarSpecialGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED",
            detail="parent id has external references:" + ",".join(ref_hits))

    roots = tuple(dict.fromkeys(
        value.removesuffix(".action.dsl.amf3.deflate")
        for value in dedicated_row if value.startswith("battle/action/")))
    closure = rbb.audit_action_identity_closure(
        roots, ref.code, tables.get("__action_loader__"),
        enemy_level=selected,
        spawned_ref_gate=tables.get("__spawned_ref_gate__"))
    if not closure.ok:
        return SingleBarSpecialGraph(
            False, family=family, parent_ref=ref, selected_level=selected,
            action_roots=roots, auxiliary_refs=auxiliary_refs,
            reason="SPECIAL_HP_CHANNEL_UNSUPPORTED", detail=closure.detail)
    return SingleBarSpecialGraph(
        True, family=family, parent_ref=ref, selected_level=selected,
        action_roots=roots, auxiliary_refs=auxiliary_refs)


def single_bar_special_native_hp_evidence(
        bundle: rbb.NativeBossBundle, enemy_level: int, tables: dict) -> dict:
    """Return the one client victory bar for a proved dedicated parent."""

    graph = inspect_single_bar_special_bundle(bundle, enemy_level, tables)
    if (not graph.ok or graph.parent_ref is None
            or graph.selected_level is None or graph.family is None):
        return {
            "native_hp": None, "components": [], "verified": False,
            "absolute_verified": False,
            "reason": graph.reason or graph.detail, "detail": graph.detail,
            "graph": graph,
        }
    evidence = floor_native_hp(
        [graph.parent_ref.code], graph.selected_level,
        standard_boss={}, boss_level=tables["boss_level"], orochi_ex={})
    components = list(evidence.get("components") or [])
    if (not evidence.get("verified") or not evidence.get("absolute_verified")
            or len(components) != 1):
        return dict(
            evidence, verified=False, absolute_verified=False,
            reason=evidence.get("reason") or "single victory-bar evidence drift",
            graph=graph)
    component = components[0]
    component.update({
        "kind": "special",
        "special_family": graph.family,
        "phase": "main",
        "phase_ordinal": 1,
        "selected_level": graph.selected_level,
        "evidence": {
            "logical": BOSS_LEVEL,
            "selected_level": graph.selected_level,
            "role": "victory_bar",
            "auxiliary_entities": list(graph.auxiliary_refs),
            "auxiliary_role": str(
                SINGLE_BAR_SPECIAL_SPECS[graph.family]["auxiliary"]),
        },
    })
    evidence["components"] = components
    evidence["graph"] = graph
    return evidence
