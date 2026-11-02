# Source section of rogue_build; loaded in its shared module namespace.
def rogue_battle_write_plan(*, gimmick_dirty: bool, caster_dirty: bool,
                            orochi_dirty: bool,
                            enemy_watch_available: bool,
                            general_state_dirty: bool = False,
                            standard_dirty: bool = False,
                            orochi_ex_dirty: bool = False,
                            single_bar_special_dirty: tuple[str, ...] = (),
                            sphere_dirty: tuple[str, ...] = ()) \
        -> tuple[str, ...]:
    """Return dependency-first battle-table writes for a tower build."""
    out: list[str] = []
    if caster_dirty:
        out.extend((GENERAL_ZAKO, ZAKO_LEVEL))
    if general_state_dirty:
        # general_boss.c42 dereferences this routine id.  Persist the cloned
        # state routine before the general_boss row that makes it reachable.
        out.append(GENERAL_BOSS_STATE)
    if caster_dirty or orochi_dirty:
        out.extend((GENERAL_BOSS, BOSS_LEVEL, GENERAL_BOSS_VARIABLE))
        if enemy_watch_available:
            out.append(ENEMY_WATCH)
    if orochi_dirty:
        out.append(OROCHI)
    if orochi_ex_dirty:
        # Parent dereferences six child IDs and its own middle boss_level row.
        # Persist both dependencies before the kind-4 parent table.
        out.extend((BOSS_LEVEL, OROCHI_EX_HEAD, OROCHI_EX))
    for family in single_bar_special_dirty:
        spec = SINGLE_BAR_SPECIAL_SPECS.get(str(family))
        if spec is None:
            raise ValueError(f"未知专用单血条写入族:{family}")
        # Constructor dereferences boss_level by the same cloned key.
        out.extend((BOSS_LEVEL, str(spec["logical"])))
    for family in sphere_dirty:
        spec = SPHERE_SPECS.get(str(family))
        if spec is None:
            raise ValueError(f"未知 Sphere 写入族:{family}")
        # Child boss_level rows must become durable before their auxiliary rows;
        # those rows in turn must precede the parent that dereferences their IDs.
        out.append(BOSS_LEVEL)
        out.extend(
            SPHERE_AUX_LOGICALS[str(group["table"])]
            for group in spec.get("aux_groups") or ()
            if group.get("scale_with_parent") and "level_column" in group)
        out.append(str(spec["logical"]))
    if standard_dirty:
        # Standard Enemy DSL 资源已在表之前原子落盘；standard_boss 再引用它。
        out.append(STANDARD_BOSS)
    if gimmick_dirty:
        # field_data.c2 dereferences the zone key, so the dependency must be
        # durable first if the later per-file save fails.  This is still not a
        # cross-table transaction; it merely avoids the dangling direction.
        out.extend((ZONE_T, FIELD_DATA_T))
    return tuple(dict.fromkeys(out))


def _general_damage_check_hp_by_code(
        components: list[dict], baseline_component_hp,
        final_component_hp) -> dict[str, tuple[float, float, float]]:
    """Collapse occurrence-based HP triples only when same-code bars agree."""

    baseline_values = tuple(map(float, baseline_component_hp))
    final_values = tuple(map(float, final_component_hp))
    if (len(components) != len(baseline_values)
            or len(components) != len(final_values)):
        raise ValueError("General DamageCheck HP 组件数量漂移")
    grouped: dict[str, list[tuple[float, float, float]]] = {}
    for component, baseline_hp, final_hp in zip(
            components, baseline_values, final_values):
        try:
            source_hp = float(component["native_hp"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("General DamageCheck 源组件 HP 非法") from exc
        values = (source_hp, baseline_hp, final_hp)
        if not all(math.isfinite(value) and value > 0 for value in values):
            raise ValueError(
                f"General DamageCheck 组件 HP 必须为有限正数:{values}")
        grouped.setdefault(str(component.get("code") or ""), []).append(values)
    result: dict[str, tuple[float, float, float]] = {}
    for code, occurrences in grouped.items():
        if not code:
            raise ValueError("General DamageCheck 组件缺 boss code")
        first = occurrences[0]
        if any(any(not math.isclose(
                current[index], first[index], rel_tol=1e-12, abs_tol=1e-4)
                for index in range(3)) for current in occurrences[1:]):
            raise ValueError(
                f"General DamageCheck 同 code 实际出现的 HP 不一致:{code}")
        result[code] = first
    return result


def attach_general_damage_check_plans(
        plan: dict, *, components: list[dict], general_boss: dict,
        general_boss_state: dict | None, enemy_level: int,
        source_absolute_verified: bool) -> dict:
    """Attach per-code c42/c16 clone plans to one General HP plan.

    Proxy-origin Hit adapters replace an unknown official correction curve.
    Their final/source max-HP ratio is therefore unknowable.  If such a boss
    has a red DamageCheck, preserving its official absolute threshold cannot
    be proved and the candidate is rejected before any table mutation.
    """

    hp_by_code = _general_damage_check_hp_by_code(
        components, plan["baseline_component_hp"],
        plan["final_component_hp"])
    damage_plans: dict[str, dict] = {}
    contracts: dict[str, dict] = {}
    for code in plan["final_leaves"]:
        selected = int(plan["selected_levels"][code])
        node = general_boss.get(code)
        source_leaf = (node.get(str(selected))
                       if isinstance(node, dict) else None)
        if not isinstance(source_leaf, (str, bytes, bytearray)):
            raise ValueError(
                f"general_boss[{code}] 缺实际选中档 lv{selected}")
        row = cells(source_leaf)
        # Legacy unit fixtures use a one-cell marker.  Production passes the
        # real state table and must expose a complete c42-bearing row.
        if len(row) <= 42:
            if isinstance(general_boss_state, dict):
                raise ValueError(
                    f"general_boss[{code}]@{selected} 行过短，无法审计 c42")
            source_routine_id = "(None)"
        else:
            source_routine_id = str(row[42])
        source_hp, baseline_hp, final_hp = hp_by_code[code]
        if source_routine_id in {"", "(None)"}:
            source_tree: dict = {}
        else:
            if not isinstance(general_boss_state, dict):
                raise ValueError(
                    f"general_boss[{code}] 的 c42={source_routine_id} "
                    "缺 general_boss_state 静态门禁")
            source_tree = general_boss_state.get(source_routine_id)
            if not isinstance(source_tree, dict):
                raise ValueError(
                    f"general_boss_state[{source_routine_id}] 缺失或不是映射")
        source_records = general_damage_check_records(source_tree)
        if source_records and not source_absolute_verified:
            raise ValueError(
                "General DamageCheck 源 HP 曲线仍是代理，无法证明官方绝对红条门槛:"
                f"boss={code},routine={source_routine_id},"
                f"occurrences={len(source_records)}")
        baseline_tree = scale_general_damage_checks(
            source_tree, source_max_hp=source_hp,
            target_max_hp=baseline_hp)
        final_tree = scale_general_damage_checks(
            source_tree, source_max_hp=source_hp,
            target_max_hp=final_hp)
        contract = general_damage_check_contract(
            source_tree, baseline_tree, final_tree,
            source_max_hp=source_hp, baseline_max_hp=baseline_hp,
            final_max_hp=final_hp,
            source_routine_id=source_routine_id,
            final_routine_id=None, materialized=False)
        damage_plans[code] = {
            "selected_level": selected,
            "source_routine_id": source_routine_id,
            "source_routine_tree": source_tree,
            "baseline_routine_tree": baseline_tree,
            "final_routine_tree": final_tree,
            "source_max_hp": source_hp,
            "baseline_max_hp": baseline_hp,
            "final_max_hp": final_hp,
            "contract": contract,
        }
        contracts[code] = contract
        if source_records:
            plan["destinations"][code] += (
                ";general_boss.c42;general_boss_state.c16")
    plan["damage_check_plans"] = damage_plans
    plan["damage_check_contracts"] = contracts
    return plan


def materialize_general_damage_check_clone(
        cloned_general_node: dict, state_table: dict, damage_plan: dict, *,
        clone_code: str) -> tuple[dict, dict]:
    """Install one private routine and repoint only the selected clone row."""

    if not isinstance(cloned_general_node, dict):
        raise ValueError("General DamageCheck clone 的 general_boss 节点不是映射")
    if not isinstance(state_table, dict):
        raise ValueError("General DamageCheck clone 缺 general_boss_state 表")
    selected = int(damage_plan["selected_level"])
    source_routine_id = str(damage_plan["source_routine_id"])
    source_tree = damage_plan["source_routine_tree"]
    baseline_tree = damage_plan["baseline_routine_tree"]
    final_tree = damage_plan["final_routine_tree"]
    occurrence_count = len(general_damage_check_records(source_tree))
    rewritten = copy.deepcopy(cloned_general_node)
    final_routine_id = source_routine_id
    if occurrence_count:
        final_routine_id = f"{clone_code}_state"
        if final_routine_id in state_table:
            raise ValueError(
                f"General DamageCheck clone routine 已存在:{final_routine_id}")
        leaf = rewritten.get(str(selected))
        if not isinstance(leaf, (str, bytes, bytearray)):
            raise ValueError(
                f"General DamageCheck clone 缺选中档 lv{selected}")
        row = cells(leaf)
        if len(row) <= 42 or row[42] != source_routine_id:
            raise ValueError(
                "General DamageCheck clone 的 c42 源 routine 漂移:"
                f"expected={source_routine_id},actual="
                f"{row[42] if len(row) > 42 else '(short row)'}")
        row[42] = final_routine_id
        rewritten[str(selected)] = join(
            row, isinstance(leaf, (bytes, bytearray)))
        state_table[final_routine_id] = copy.deepcopy(final_tree)
    readback_tree = (state_table[final_routine_id]
                     if occurrence_count else final_tree)
    contract = general_damage_check_contract(
        source_tree, baseline_tree, readback_tree,
        source_max_hp=float(damage_plan["source_max_hp"]),
        baseline_max_hp=float(damage_plan["baseline_max_hp"]),
        final_max_hp=float(damage_plan["final_max_hp"]),
        source_routine_id=source_routine_id,
        final_routine_id=final_routine_id, materialized=True)
    return rewritten, contract


def clone_enemy_watch_routine_alias(
        self_node: dict, source_routine_id: str,
        final_routine_id: str) -> int:
    """Keep GeneralEnemyWatch lookup equivalent after c42 is privatized."""

    if not isinstance(self_node, dict):
        raise ValueError("general_enemy_watch self 节点不是映射")
    source = str(source_routine_id)
    target = str(final_routine_id)
    if source == target or source not in self_node:
        return 0
    if target in self_node:
        raise ValueError(f"general_enemy_watch routine alias 已存在:{target}")
    self_node[target] = copy.deepcopy(self_node[source])
    return 1


def general_hp_scale_plan(bosses: list[str], native: dict,
                          general_boss: dict, boss_level: dict,
                          enemy_level: int, *, target_hp: float,
                          curse_hp: float,
                          code_references: dict | None = None,
                          general_boss_state: dict | None = None,
                          component_budgets: dict[str, float] | None = None) -> dict:
    """为纯 general 层生成逐 code 的 baseline/final HP 叶与可复核证据。

    当前 ``boss_level`` 数据形态是 ``code -> CSV leaf``，没有等级内层；等级
    getSurjectivity 只发生在 ``general_boss``。这里把选中的 general 档记进计划，
    克隆后必须再次选档并逐项相等，防止代码与 boss_level 叶错配。绝对来源的
    Hit 行只改 c2、Fix 行只改 c5。若任一组件的 Hit 曲线只能代理，则不按代理
    原生值做比例缩放：所有实际出现次数等分整关目标，同时改写克隆 c2+c4 到
    已知曲线，再按客户端公式回读。
    """
    components = list(native.get("components") or [])
    if not native.get("verified") or not components:
        raise ValueError(f"general HP 伸缩缺原生 HP 证据:{native.get('reason') or 'unknown'}")
    if any(component.get("kind") != "general" for component in components):
        raise ValueError("general/standard 混合族不能用单一 c86/c2 通道，必须换 boss")
    ordered_codes = list(dict.fromkeys(map(str, bosses)))
    identity_block = identity_clone_locked_boss_reason(
        ordered_codes, code_references=code_references)
    if identity_block:
        # Defense in depth: candidate selection should have routed this layer
        # through same-id c86 already.  Keeping the check in the c2 plan means
        # a future caller cannot silently reintroduce a pure HP rename clone.
        raise ValueError(f"纯 HP clone 拒绝:{identity_block}")
    component_codes = [str(component.get("code")) for component in components]
    if not ordered_codes or set(component_codes) != set(ordered_codes):
        raise ValueError(
            f"general HP 实体与证据代号不一致:bosses={ordered_codes},components={component_codes}")
    try:
        wanted_hp = float(target_hp)
        hp_mult = float(curse_hp)
        native_hp = math.fsum(float(component["native_hp"]) for component in components)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("general HP 伸缩输入含非数字") from exc
    if not all(math.isfinite(v) and v > 0 for v in (wanted_hp, hp_mult, native_hp)):
        raise ValueError(
            f"general HP 伸缩输入必须为有限正数:target={target_hp},curse={curse_hp},native={native_hp}")
    baseline_scale = wanted_hp / native_hp
    final_scale = baseline_scale * hp_mult
    code_scales = {code: baseline_scale for code in ordered_codes}
    if component_budgets is not None:
        if (set(component_budgets) != set(ordered_codes)
                or any(not math.isfinite(v) or v <= 0 for v in component_budgets.values())
                or not math.isclose(math.fsum(component_budgets.values()), wanted_hp,
                                    rel_tol=1e-12, abs_tol=1e-4)):
            raise ValueError("逐 Boss 血量预算必须覆盖全部实体且总和等于关卡预算")
        for code in ordered_codes:
            code_scales[code] = component_budgets[code] / math.fsum(
                float(component["native_hp"]) for component in components
                if str(component["code"]) == code)
    selected_levels: dict[str, int] = {}
    baseline_leaves: dict[str, str | bytes] = {}
    final_leaves: dict[str, str | bytes] = {}
    baseline_factors: dict[str, float] = {}
    final_factors: dict[str, float] = {}
    hp_columns: dict[str, int] = {}
    destinations: dict[str, str] = {}
    # Production evidence names every component.  Some internal callers and
    # older tests predate that field, so absence alone must not turn a known
    # absolute Hit/Fix plan into the proxy-only adapter.  Explicit proxy
    # evidence (or an explicit top-level rejection) still fails closed.
    source_has_proxy = (
        native.get("absolute_verified") is False
        or any(component.get("evidence_kind") == "proxy"
               for component in components))
    if source_has_proxy:
        if component_budgets is not None:
            raise ValueError("逐 Boss 独立预算要求绝对原生 HP 证据")
        # One boss_level row is shared by every occurrence of the same code.
        # Equal per-occurrence allocation is deterministic even when a code
        # appears twice; proxy weights never enter the target calculation.
        baseline_each = wanted_hp / len(components)
        final_each = wanted_hp * hp_mult / len(components)
        baseline_readbacks: dict[str, float] = {}
        final_readbacks: dict[str, float] = {}
        for code in ordered_codes:
            selected = select_surjective_level(
                general_boss.get(code), int(enemy_level))
            if selected is None:
                raise ValueError(
                    f"general_boss[{code}] 无 >=lv{enemy_level} 的运行档")
            source_leaf = boss_level.get(code)
            if source_leaf is None:
                raise ValueError(f"boss_level[{code}] 缺失")
            component_modes = {
                str(component.get("hp_curve_kind"))
                for component in components
                if str(component.get("code")) == code
                and component.get("hp_curve_kind") is not None
            }
            if component_modes and component_modes != {"hit"}:
                raise ValueError(
                    f"boss_level[{code}] 代理目标值适配仅支持 Hit 组件:"
                    f"{sorted(component_modes)}")
            baseline_leaf, baseline_readback = clone_target_hit_boss_level_hp(
                source_leaf, baseline_each, int(enemy_level))
            final_leaf, final_readback = clone_target_hit_boss_level_hp(
                source_leaf, final_each, int(enemy_level))
            old_value = float(cells(source_leaf)[2])
            if not math.isfinite(old_value) or old_value <= 0:
                raise ValueError(f"boss_level[{code}].c2 原值非法:{old_value}")
            selected_levels[code] = selected
            baseline_leaves[code] = baseline_leaf
            final_leaves[code] = final_leaf
            baseline_factors[code] = float(cells(baseline_leaf)[2]) / old_value
            final_factors[code] = float(cells(final_leaf)[2]) / old_value
            hp_columns[code] = 2
            destinations[code] = "boss_level.c2+c4"
            baseline_readbacks[code] = baseline_readback
            final_readbacks[code] = final_readback
        baseline_component_hp = tuple(
            baseline_readbacks[str(component["code"])]
            for component in components)
        final_component_hp = tuple(
            final_readbacks[str(component["code"])]
            for component in components)
        plan = {
            "channel": "boss_level", "family": "general",
            "adapter_mode": "target_authoritative_hit",
            "authoritative_curve": AUTHORITATIVE_HIT_HP_CURVE,
            "absolute_after_adaptation": True,
            "source_absolute_verified": False,
            "c86": 1.0, "curse_hp": hp_mult,
            "selected_levels": selected_levels,
            "baseline_scale": baseline_scale, "final_scale": final_scale,
            "baseline_factors": baseline_factors,
            "final_factors": final_factors,
            "baseline_leaves": baseline_leaves, "final_leaves": final_leaves,
            "baseline_component_target_hp": tuple(
                baseline_each for _component in components),
            "final_component_target_hp": tuple(
                final_each for _component in components),
            "baseline_component_hp": baseline_component_hp,
            "final_component_hp": final_component_hp,
            "hp_columns": hp_columns, "destinations": destinations,
            "baseline_true_hp": math.fsum(baseline_component_hp),
            "true_hp": math.fsum(final_component_hp),
        }
        return attach_general_damage_check_plans(
            plan, components=components, general_boss=general_boss,
            general_boss_state=general_boss_state,
            enemy_level=int(enemy_level),
            source_absolute_verified=False)
    for code in ordered_codes:
        selected = select_surjective_level(general_boss.get(code), int(enemy_level))
        if selected is None:
            raise ValueError(f"general_boss[{code}] 无 >=lv{enemy_level} 的运行档")
        source_leaf = boss_level.get(code)
        if source_leaf is None:
            raise ValueError(f"boss_level[{code}] 缺失")
        baseline_leaf, hp_column = clone_general_boss_level_hp(
            source_leaf, code_scales[code])
        final_leaf, final_column = clone_general_boss_level_hp(
            source_leaf, code_scales[code] * hp_mult)
        if final_column != hp_column:
            raise ValueError(f"boss_level[{code}] baseline/final HP 通道漂移")
        component_modes = {
            str(component.get("hp_curve_kind"))
            for component in components
            if str(component.get("code")) == code
            and component.get("hp_curve_kind") is not None
        }
        expected_mode = "hit" if hp_column == 2 else "fix"
        if component_modes and component_modes != {expected_mode}:
            raise ValueError(
                f"boss_level[{code}] HP 证据类型与落表通道不一致:"
                f"evidence={sorted(component_modes)},channel={expected_mode}")
        old_value = float(cells(source_leaf)[hp_column])
        selected_levels[code] = selected
        baseline_leaves[code] = baseline_leaf
        final_leaves[code] = final_leaf
        baseline_factors[code] = float(cells(baseline_leaf)[hp_column]) / old_value
        final_factors[code] = float(cells(final_leaf)[hp_column]) / old_value
        hp_columns[code] = hp_column
        destinations[code] = f"boss_level.c{hp_column}"
    baseline_component_hp = tuple(
        float(component["native_hp"]) * baseline_factors[str(component["code"])]
        for component in components)
    final_component_hp = tuple(
        float(component["native_hp"]) * final_factors[str(component["code"])]
        for component in components)
    # BossLevelValues Fix 在每个实际实体处 floor；Hit 保留连续值。这里使用由
    # fmt 后落表值反算出的 factor，确保计划与最终克隆回读遵循同一取整边界。
    baseline_component_hp = tuple(
        float(math.floor(value))
        if hp_columns[str(component["code"])] == 5 else value
        for component, value in zip(components, baseline_component_hp))
    final_component_hp = tuple(
        float(math.floor(value))
        if hp_columns[str(component["code"])] == 5 else value
        for component, value in zip(components, final_component_hp))
    baseline_true_hp = math.fsum(baseline_component_hp)
    true_hp = math.fsum(final_component_hp)
    plan = {
        "channel": "boss_level", "family": "general",
        "adapter_mode": "relative_absolute_source",
        "absolute_after_adaptation": True,
        "source_absolute_verified": bool(native.get("absolute_verified")),
        "c86": 1.0, "curse_hp": hp_mult,
        "selected_levels": selected_levels,
        "baseline_scale": baseline_scale, "final_scale": final_scale,
        "baseline_factors": baseline_factors, "final_factors": final_factors,
        "baseline_leaves": baseline_leaves, "final_leaves": final_leaves,
        "baseline_component_hp": baseline_component_hp,
        "final_component_hp": final_component_hp,
        "hp_columns": hp_columns, "destinations": destinations,
        "baseline_true_hp": baseline_true_hp, "true_hp": true_hp,
    }
    if component_budgets is not None:
        plan["baseline_component_target_hp"] = tuple(
            float(component["native_hp"]) * code_scales[str(component["code"])]
            for component in components)
        plan["final_component_target_hp"] = tuple(
            value * hp_mult for value in plan["baseline_component_target_hp"])
    return attach_general_damage_check_plans(
        plan, components=components, general_boss=general_boss,
        general_boss_state=general_boss_state,
        enemy_level=int(enemy_level),
        source_absolute_verified=bool(native.get("absolute_verified", True)))


def _standard_native_from_evidence(
        native: dict, evidence_by_code: dict[str, dict],
        code_map: dict[str, str] | None = None) -> dict:
    """用重新解码的 forms 证据重建逐出现次数 Standard HP 结构。"""
    remap = code_map or {}
    components: list[dict] = []
    for source in native.get("components") or []:
        source_code = str(source.get("code") or "")
        evidence = evidence_by_code.get(source_code)
        if not isinstance(evidence, dict):
            raise ValueError(f"standard HP 回读缺 {source_code} 的 DSL 证据")
        form_index = source.get("form_index")
        if form_index is None:
            match = re.fullmatch(r"form\[(\d+)\]", str(source.get("phase") or ""))
            if match:
                form_index = int(match.group(1))
        try:
            form_index = int(form_index)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"standard HP 组件缺 form_index:{source}") from exc
        forms = {
            int(item["form_index"]): float(item["base_hp"])
            for item in evidence.get("health_forms") or ()
        }
        if form_index not in forms:
            raise ValueError(
                f"standard HP 回读 {source_code} 缺 form[{form_index}]")
        target_code = remap.get(source_code, source_code)
        try:
            # Older/unit-constructed evidence predates task-kind tagging and
            # retains the historical single-boss 0.55 semantics. Production
            # Rush evidence is always explicit 1.0 and never takes this fallback.
            runtime_scale = float(source.get(
                "standard_runtime_hp_scale", STANDARD_BOSS_BATTLE_HP_SCALE))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"standard HP 组件缺运行任务倍率:{source_code}") from exc
        if not math.isfinite(runtime_scale) or runtime_scale <= 0:
            raise ValueError(
                f"standard HP 运行任务倍率非法:{source_code}:{runtime_scale}")
        component = dict(source)
        component.update({
            "code": target_code,
            "native_hp": round(
                forms[form_index] * runtime_scale, 6),
            "evidence_kind": "absolute",
            "evidence": dict(
                evidence, code=target_code,
                standard_runtime_hp_scale=runtime_scale),
        })
        components.append(component)
    verified = bool(components) and bool(native.get("verified"))
    return {
        "native_hp": (math.fsum(float(item["native_hp"]) for item in components)
                      if verified else None),
        "components": components,
        "verified": verified,
        "absolute_verified": verified,
        "reason": None if verified else "standard HP 源证据不可验证",
    }


def clone_standard_boss_node(source_node: dict, selected_level: int,
                             resource_base: str) -> dict:
    """克隆 standard_boss 节点，只改本层实际选中档的 Enemy DSL 路径。"""
    if not isinstance(source_node, dict) or not source_node:
        raise ValueError("standard_boss clone 源节点不是非空等级表")
    key = str(int(selected_level))
    if key not in source_node:
        raise ValueError(f"standard_boss clone 缺选中档 lv{selected_level}")
    path = str(resource_base).strip()
    if not path or path.endswith(".esdl") or path.endswith(".esdl.amf3.deflate"):
        raise ValueError(f"standard_boss clone 资源基路径非法:{resource_base!r}")
    source_leaf = source_node[key]
    row = cells(source_leaf)
    if len(row) < 2 or not row[1].strip():
        raise ValueError(f"standard_boss clone lv{selected_level} 源资源路径缺失")
    row[1] = path
    cloned = copy.deepcopy(source_node)
    cloned[key] = join(row, isinstance(source_leaf, (bytes, bytearray)))
    if select_surjective_level(cloned, int(selected_level)) != int(selected_level):
        raise RuntimeError("standard_boss clone 后资源选档漂移")
    return cloned


def standard_hp_scale_plan(
        bosses: list[str], native: dict, standard_boss: dict,
        enemy_level: int, *, target_hp: float, curse_hp: float,
        code_references: dict | None = None,
        resources: dict[str, bytes] | None = None) -> dict:
    """生成 Standard DSL Health(T1) baseline/final 资源与客户端公式回读。"""
    components = list(native.get("components") or [])
    if not native.get("verified") or not native.get("absolute_verified") or not components:
        raise ValueError(
            f"standard HP 伸缩缺绝对证据:{native.get('reason') or 'unknown'}")
    if any(component.get("kind") != "standard" for component in components):
        raise ValueError("standard HP 计划不支持 general/standard 混合族")
    ordered_codes = list(dict.fromkeys(map(str, bosses)))
    component_codes = [str(component.get("code")) for component in components]
    if not ordered_codes or set(component_codes) != set(ordered_codes):
        raise ValueError(
            f"standard HP 实体与证据代号不一致:"
            f"bosses={ordered_codes},components={component_codes}")
    identity_block = identity_locked_boss_reason(
        ordered_codes, code_references=code_references)
    if identity_block:
        raise ValueError(f"standard DSL clone 拒绝:{identity_block}")
    try:
        wanted_hp = float(target_hp)
        hp_mult = float(curse_hp)
        native_hp = math.fsum(float(component["native_hp"])
                              for component in components)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("standard HP 伸缩输入含非数字") from exc
    if not all(math.isfinite(value) and value > 0
               for value in (wanted_hp, hp_mult, native_hp)):
        raise ValueError(
            f"standard HP 伸缩输入必须为有限正数:"
            f"target={target_hp},curse={curse_hp},native={native_hp}")
    baseline_scale = wanted_hp / native_hp
    final_scale = baseline_scale * hp_mult
    selected_levels: dict[str, int] = {}
    source_logicals: dict[str, str] = {}
    baseline_evidence: dict[str, dict] = {}
    final_evidence: dict[str, dict] = {}
    final_blobs: dict[str, bytes] = {}
    damage_check_contracts: dict[str, dict] = {}
    runtime_scales_by_code = {
        str(component["code"]): float(component.get(
            "standard_runtime_hp_scale", STANDARD_BOSS_BATTLE_HP_SCALE))
        for component in components
    }
    for code in ordered_codes:
        source = standard_boss_hp_evidence(
            code, int(enemy_level), standard_boss, resources)
        selected = int(source["selected_level"])
        logical = str(source["logical"])
        tree = _read_standard_enemy_dsl(logical, resources)
        baseline_blob = build_standard_enemy_dsl_blob(
            scale_standard_enemy_hp_tree(tree, baseline_scale))
        final_blob = build_standard_enemy_dsl_blob(
            scale_standard_enemy_hp_tree(tree, final_scale))
        baseline_tree = _read_standard_enemy_dsl(
            logical, {logical: baseline_blob})
        final_tree = _read_standard_enemy_dsl(logical, {logical: final_blob})
        baseline_evidence[code] = dict(
            standard_enemy_hp_base(baseline_tree), code=code,
            selected_level=selected, logical=logical)
        final_evidence[code] = dict(
            standard_enemy_hp_base(final_tree), code=code,
            selected_level=selected, logical=logical)
        damage_check_contracts[code] = standard_damage_check_contract(
            tree, final_tree,
            runtime_hp_scale=runtime_scales_by_code[code])
        selected_levels[code] = selected
        source_logicals[code] = logical
        final_blobs[code] = final_blob
    baseline_native = _standard_native_from_evidence(native, baseline_evidence)
    final_native = _standard_native_from_evidence(native, final_evidence)
    baseline_component_hp = _hp_component_readback_values(baseline_native, 1.0)
    final_component_hp = _hp_component_readback_values(final_native, 1.0)
    return {
        "channel": "standard_dsl", "family": "standard", "c86": 1.0,
        "curse_hp": hp_mult, "selected_levels": selected_levels,
        "source_logicals": source_logicals,
        "baseline_scale": baseline_scale, "final_scale": final_scale,
        "baseline_component_hp": baseline_component_hp,
        "final_component_hp": final_component_hp,
        "baseline_true_hp": math.fsum(baseline_component_hp),
        "true_hp": math.fsum(final_component_hp),
        "final_blobs": final_blobs,
        "damage_check_contracts": damage_check_contracts,
        "destinations": {
            code: "standard_boss.resource/forms.Health(T1)" for code in ordered_codes},
    }


def mixed_hp_scale_plan(
        bosses: list[str], native: dict, general_boss: dict, boss_level: dict,
        standard_boss: dict, enemy_level: int, *, target_hp: float,
        curse_hp: float, code_references: dict | None = None,
        resources: dict[str, bytes] | None = None,
        general_boss_state: dict | None = None) -> dict:
    """组合 General Hit/Fix 与 Standard DSL，保持整关组件原生占比。"""
    components = list(native.get("components") or [])
    if not native.get("verified") or not components:
        raise ValueError(f"mixed HP 伸缩缺原生证据:{native.get('reason') or 'unknown'}")
    families = {str(component.get("kind")) for component in components}
    if families != {"general", "standard"}:
        raise ValueError(f"mixed HP 计划只接受 general+standard:{sorted(families)}")
    identity_block = identity_clone_locked_boss_reason(
        list(map(str, bosses)), code_references=code_references)
    if identity_block:
        raise ValueError(f"mixed HP clone 拒绝:{identity_block}")
    total_native = math.fsum(float(component["native_hp"])
                             for component in components)
    wanted = float(target_hp)
    hp_mult = float(curse_hp)
    if not all(math.isfinite(value) and value > 0
               for value in (total_native, wanted, hp_mult)):
        raise ValueError(
            f"mixed HP 伸缩输入非法:target={target_hp},curse={curse_hp},"
            f"native={total_native}")

    def subset(kind: str) -> tuple[list[str], dict]:
        subset_components = [component for component in components
                             if str(component.get("kind")) == kind]
        codes = set(str(component.get("code")) for component in subset_components)
        ordered = [code for code in map(str, bosses) if code in codes]
        return ordered, {
            "native_hp": math.fsum(float(component["native_hp"])
                                   for component in subset_components),
            "components": subset_components,
            "verified": True,
            "absolute_verified": all(
                component.get("evidence_kind") == "absolute"
                for component in subset_components),
            "reason": None,
        }

    general_codes, general_native = subset("general")
    standard_codes, standard_native = subset("standard")
    general_target = wanted * float(general_native["native_hp"]) / total_native
    standard_target = wanted * float(standard_native["native_hp"]) / total_native
    general_plan = general_hp_scale_plan(
        general_codes, general_native, general_boss, boss_level,
        int(enemy_level), target_hp=general_target, curse_hp=hp_mult,
        code_references=code_references,
        general_boss_state=general_boss_state)
    standard_plan = standard_hp_scale_plan(
        standard_codes, standard_native, standard_boss, int(enemy_level),
        target_hp=standard_target, curse_hp=hp_mult,
        code_references=code_references, resources=resources)
    if not math.isclose(float(general_plan["baseline_scale"]),
                        float(standard_plan["baseline_scale"]),
                        rel_tol=1e-12, abs_tol=1e-12):
        raise RuntimeError("mixed HP 两个适配器的基线倍率不一致")
    general_baseline = iter(general_plan["baseline_component_hp"])
    standard_baseline = iter(standard_plan["baseline_component_hp"])
    general_final = iter(general_plan["final_component_hp"])
    standard_final = iter(standard_plan["final_component_hp"])
    baseline_component_hp: list[float] = []
    final_component_hp: list[float] = []
    for component in components:
        if component.get("kind") == "general":
            baseline_component_hp.append(float(next(general_baseline)))
            final_component_hp.append(float(next(general_final)))
        else:
            baseline_component_hp.append(float(next(standard_baseline)))
            final_component_hp.append(float(next(standard_final)))
    destinations = dict(general_plan["destinations"])
    destinations.update(standard_plan["destinations"])
    return {
        "channel": "mixed_hp", "family": "mixed", "c86": 1.0,
        "curse_hp": hp_mult,
        "baseline_scale": wanted / total_native,
        "final_scale": wanted / total_native * hp_mult,
        "baseline_component_hp": tuple(baseline_component_hp),
        "final_component_hp": tuple(final_component_hp),
        "baseline_true_hp": math.fsum(baseline_component_hp),
        "true_hp": math.fsum(final_component_hp),
        "selected_levels": {
            **general_plan["selected_levels"], **standard_plan["selected_levels"]},
        "destinations": destinations,
        "general_plan": general_plan, "standard_plan": standard_plan,
    }


def floor_hp_scaling_strategy(bosses: list[str], native: dict,
                              general_boss: dict, boss_level: dict,
                              enemy_level: int, *, required_c86: float,
                              deep: bool,
                              code_references: dict | None = None,
                              standard_boss: dict | None = None,
                              general_boss_state: dict | None = None) -> dict:
    """选择该层 HP 主通道；不可实现的族组合直接抛错供调用方重抽。"""
    components = list(native.get("components") or [])
    if not native.get("verified") or not components:
        raise ValueError(f"HP 主通道缺原生证据:{native.get('reason') or 'unknown'}")
    families = {str(component.get("kind")) for component in components}
    try:
        needed = float(required_c86)
        native_hp = float(native["native_hp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("HP 主通道 required_c86/native_hp 非数字") from exc
    if not all(math.isfinite(v) and v > 0 for v in (needed, native_hp)):
        raise ValueError(f"HP 主通道输入非法:c86={required_c86},native={native_hp}")
    if families == {"general"}:
        identity_block = identity_clone_locked_boss_reason(
            bosses, code_references=code_references)
        if identity_block:
            lo, hi = STANDARD_C86_LIMITS
            if not lo <= needed <= hi:
                raise ValueError(
                    f"{identity_block}; 保持原 id 仅可用 c86 微调窗口 "
                    f"{lo:g}~{hi:g}，需要 {needed:g}，拒绝候选并重抽")
            return {
                "channel": "c86", "family": "identity-locked",
                "baseline_c86": needed, "baseline_scale": 1.0,
                "selected_levels": {},
            }
        plan = general_hp_scale_plan(
            list(map(str, bosses)), native, general_boss, boss_level,
            int(enemy_level), target_hp=native_hp * needed, curse_hp=1.0,
            code_references=code_references,
            general_boss_state=general_boss_state)
        return {
            "channel": "boss_level", "family": "general",
            "baseline_c86": 1.0,
            "baseline_scale": plan["baseline_scale"],
            "selected_levels": plan["selected_levels"],
            "adapter_mode": plan.get("adapter_mode"),
            "absolute_after_adaptation": bool(
                plan.get("absolute_after_adaptation")),
        }
    if families == {"standard"}:
        identity_block = identity_locked_boss_reason(
            bosses, code_references=code_references)
        if identity_block:
            lo, hi = STANDARD_C86_LIMITS
            if not lo <= needed <= hi:
                raise ValueError(
                    f"{identity_block}; standard 保持原 id 仅可用 c86 微调窗口 "
                    f"{lo:g}~{hi:g}，需要 {needed:g}，拒绝候选并重抽")
            return {
                "channel": "c86", "family": "identity-locked-standard",
                "baseline_c86": needed, "baseline_scale": 1.0,
                "selected_levels": {},
            }
        standard_table = standard_boss or {}
        selected_levels = {}
        for code in dict.fromkeys(map(str, bosses)):
            selected = select_surjective_level(standard_table.get(code), enemy_level)
            if selected is None:
                raise ValueError(f"standard_boss[{code}] 无 >=lv{enemy_level} 的资源档")
            selected_levels[code] = selected
        return {"channel": "standard_dsl", "family": "standard",
                "baseline_c86": 1.0, "baseline_scale": needed,
                "selected_levels": selected_levels}
    if families == {"general", "standard"}:
        identity_block = identity_clone_locked_boss_reason(
            bosses, code_references=code_references)
        if identity_block:
            lo, hi = STANDARD_C86_LIMITS
            if not lo <= needed <= hi:
                raise ValueError(
                    f"{identity_block}; mixed 保持原 id 仅可用 c86 微调窗口 "
                    f"{lo:g}~{hi:g}，需要 {needed:g}，拒绝候选并重抽")
            return {
                "channel": "c86", "family": "identity-locked-mixed",
                "baseline_c86": needed, "baseline_scale": 1.0,
                "selected_levels": {},
            }
        standard_table = standard_boss or {}
        selected_levels = {}
        component_family = {
            str(component.get("code")): str(component.get("kind"))
            for component in components
        }
        for code in dict.fromkeys(map(str, bosses)):
            table = (standard_table if component_family.get(code) == "standard"
                     else general_boss)
            selected = select_surjective_level(table.get(code), enemy_level)
            if selected is None:
                raise ValueError(
                    f"mixed HP {component_family.get(code) or 'unknown'}[{code}] "
                    f"无 >=lv{enemy_level} 的运行档")
            selected_levels[code] = selected
        general_components = [
            component for component in components
            if str(component.get("kind")) == "general"]
        general_codes = [
            code for code in map(str, bosses)
            if component_family.get(code) == "general"]
        general_native_hp = math.fsum(
            float(component["native_hp"])
            for component in general_components)
        general_hp_scale_plan(
            general_codes, {
                "native_hp": general_native_hp,
                "components": general_components,
                "verified": True,
                "absolute_verified": all(
                    component.get("evidence_kind") == "absolute"
                    for component in general_components),
            }, general_boss, boss_level, int(enemy_level),
            target_hp=general_native_hp * needed, curse_hp=1.0,
            code_references=code_references,
            general_boss_state=general_boss_state)
        return {"channel": "mixed_hp", "family": "mixed",
                "baseline_c86": 1.0, "baseline_scale": needed,
                "selected_levels": selected_levels}
    raise ValueError(f"HP 主通道不支持混合/未知族:{sorted(families)}")


GB_RESIST_ELEMENT_RESISTANCE_COL = 36
_GB_BOOL_TRUE = {"true", "True", "TRUE"}
_GB_BOOL_FALSE = {"false", "False", "FALSE"}


def general_boss_element_immunity_block(general_boss: dict, code: str,
                                        enemy_level: int | None = None,
                                        general_boss_variable: dict | None = None) -> str | None:
    """实际 general_boss 代号能否承载正向属性耐性；返回阻断原因或 None。

    `resist_element_resistance` 已由 GeneralBossValues.as:725-754 钉死为 c36。
    必须先按本层 enemy level 选中最终/克隆后的实际档,再检查该档的全部 leaf。
    Lens v3 EnemyImpl.isConditionPrevented 对 strength>0 提前返回 false；c36
    仅限制部分非正向属性耐性，因此 true 不能用于拒绝本工具的正向耐性卡。
    客户端只接受六种大小写布尔字面量,缺行/短行/未知值一律 fail closed。
    """
    node = general_boss.get(code)
    if node is None:
        return f"actual boss {code} 不在 general_boss"
    # GeneralBossSource.as:88 直接对 GeneralBossTable[code] 调 getSurjectivity(level):
    # 取第一个 ≥敌等级的 general_boss 行。general_boss_variable 在 :96-99 另行解析,
    # **不参与 values/c36 选行**。只看 gv 会把 gb[79]=false / gb[100]=true 的
    # lv80/90 boss 错放；这里保留形参只为调用兼容,明确不使用。
    _ = general_boss_variable
    if isinstance(node, dict):
        gb_levels = sorted(int(k) for k in node if str(k).isdigit())
        if enemy_level is not None:
            selected_level = select_surjective_level(node, int(enemy_level))
        elif len(gb_levels) == 1:
            selected_level = gb_levels[0]
        else:
            selected_level = None
        if selected_level is None:
            return (f"actual boss {code} 无 ≥lv{enemy_level} 的克隆后实际"
                    " general_boss 行,fail closed")
        node = node[str(selected_level)]
        row_where = f"gb[{selected_level}]"
    else:
        row_where = "gb[leaf]"
    seen = 0
    for leaf in _leaf_rows(node):
        row = cells(leaf)
        if len(row) != 162:
            return (f"actual boss {code} {row_where} 行列数={len(row)}"
                    "(应为162),fail closed")
        raw = row[GB_RESIST_ELEMENT_RESISTANCE_COL]
        if raw not in _GB_BOOL_FALSE | _GB_BOOL_TRUE:
            return (f"actual boss {code} {row_where} c36={raw!r}"
                    " 非客户端合法布尔字面量,fail closed")
        seen += 1
    return None if seen else f"actual boss {code} {row_where} 没有可解析 leaf,fail closed"


def assert_element_immunity_runtime_safe(quest_logical: str, enemy_level: int) -> None:
    """防 autoHighLevel 将整族属性免疫静默吃掉。

    EnemySourceBase params[13]=autoHighLevel 且 level>=80 时会把
    resistElementResistance 强制置 true；isAutoHighLevelBoss() 仅在
    ScoreAttackEventBattleQuestLogic override 为 true,普通 event_quest 基类恒 false。
    当前 Rush 塔因此安全；未来若迁到 score_attack 且仍是 lv80/90/100,构建必须硬停。
    """
    path = str(quest_logical).replace("\\", "/").lower()
    if enemy_level >= 80 and "score_attack" in path:
        raise RuntimeError(
            f"属性免疫拒绝用于 score_attack lv{enemy_level}:autoHighLevel 会静默抵消效果")
    if "/quest/event/" not in path:
        raise RuntimeError(f"属性免疫 quest logic 未确证为 event_quest:{quest_logical}")


def patch_event_metadata(row: list[str]) -> list[str]:
    """只把深渊 Rush Event 的兑换代币改为深渊代币。"""
    row[10] = TOKEN_ID
    return row


def build_event_metadata_leaf(
    template_leaf: bytes | str,
    current_leaf: bytes | str,
) -> bytes | str:
    """Rebuild 700099 from the canonical template, preserving only banner art."""
    template = cells(template_leaf)
    current = cells(current_leaf)
    if len(template) < 18:
        raise ValueError(f"rush_event[{TEMPLATE_EVENT}] must have at least 18 columns")
    if len(current) < 5:
        raise ValueError(f"rush_event[{EVENT_ID}] must have at least 5 columns")

    row = list(template)
    row[0] = EVENT_STRING_ID
    row[1] = EVENT_NAME
    row[2] = f"{START},{END},{RESULT_END},{EXCHANGE_END}"
    row[3:5] = current[3:5]
    row[10] = TOKEN_ID
    row[15] = START
    row[16] = END
    row[17] = EXCHANGE_END
    return join(row, isinstance(current_leaf, bytes))


