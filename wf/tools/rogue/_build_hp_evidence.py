# Source section of rogue_build; loaded in its shared module namespace.
def standard_enemy_hp_base(tree: dict) -> dict:
    """从已解析的 standard enemy DSL 返回可审计 HP 基数证据。

    未知 union tag、缺字段、非有限值均 fail closed；T2=Defeat 是合法的非血量
    termination condition，按客户端 switch case 1 忽略。
    """
    forms = tree.get("au") if isinstance(tree, dict) else None
    if not isinstance(forms, list) or not forms:
        raise ValueError("standard enemy DSL 缺少非空 forms(短键 au)")
    terms: list[float] = []
    health_forms: list[dict] = []
    for index, form in enumerate(forms):
        term = form.get("d") if isinstance(form, dict) else None
        if not isinstance(term, list) or not term or not isinstance(term[0], str):
            raise ValueError(f"standard enemy form[{index}] terminationCondition(d) 非法")
        tag = term[0]
        if tag == "T2":                         # Defeat(index 1)，不贡献 HP
            continue
        if tag != "T1" or len(term) < 2:         # 未知构造必须响亮失败
            raise ValueError(f"standard enemy form[{index}] 未知 termination tag:{tag!r}")
        try:
            value = float(term[1])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"standard enemy form[{index}] Health 参数不是数值") from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"standard enemy form[{index}] Health 参数非法:{value!r}")
        terms.append(value)
        health_forms.append({"form_index": index, "base_hp": value})
    if not terms:
        raise ValueError("standard enemy DSL 没有 Health(T1) termination form")
    return {"form_count": len(forms), "health_terms": tuple(terms),
            "health_forms": tuple(health_forms),
            "base_hp": math.fsum(terms)}


STANDARD_DAMAGE_CHECK_SCHEMA = "wf-standard-damage-check/v1"
# TypePackerResource2: state.e is animation, state.m is Trial, and Trial.T2
# is DamageCheck. A script-based DamageCheck is still a damage trial; it
# cannot be silently skipped or rescaled as a literal percentage.


def _dsl_scalar(value):
    """Unwrap nested one-value union payloads used by state timers."""

    current = value
    for _ in range(8):
        if (isinstance(current, list) and len(current) == 2
                and isinstance(current[0], str)
                and current[0].startswith("T")):
            current = current[1]
            continue
        break
    return current


def standard_damage_check_records(tree: dict) -> tuple[dict, ...]:
    """Read every Standard DSL DamageCheck occurrence without code dedupe."""

    forms = tree.get("au") if isinstance(tree, dict) else None
    if not isinstance(forms, list):
        raise ValueError("standard enemy DSL 缺 forms，无法审计 DamageCheck")
    health_by_form = {
        int(item["form_index"]): float(item["base_hp"])
        for item in standard_enemy_hp_base(tree)["health_forms"]
    }
    records: list[dict] = []

    def walk(value, path: tuple, form_index: int | None) -> None:
        if isinstance(value, dict):
            union = value.get("m")
            if (len(path) == 4 and path[0] == "au" and path[2] == "g"
                    and isinstance(union, list) and len(union) == 2
                    and union[0] == "T2"):
                payload = union[1]
                if isinstance(payload, dict) and payload.get("h") is not None:
                    raise ValueError(
                        f"DamageCheck script 门槛缺独立 HP 依赖证明:path={path}")
                if not isinstance(payload, dict) or "a" not in payload:
                    raise ValueError(f"DamageCheck payload 非法:path={path}")
                if form_index is None or form_index not in health_by_form:
                    raise ValueError(
                        f"DamageCheck 不在带 Health(T1) 的 form 内:path={path}")
                try:
                    percentage = float(payload["a"])
                    duration_frames = float(_dsl_scalar(value.get("d")))
                    state_id = int(value.get("a"))
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"DamageCheck 百分比/窗口/state id 非法:path={path}") from exc
                if (not math.isfinite(percentage) or percentage <= 0
                        or not math.isfinite(duration_frames)
                        or duration_frames <= 0):
                    raise ValueError(
                        f"DamageCheck 百分比/窗口必须为有限正数:path={path}")
                records.append({
                    "path": tuple(path),
                    "form_index": int(form_index),
                    "state_id": state_id,
                    "percentage": percentage,
                    "form_base_hp": health_by_form[int(form_index)],
                    "duration_frames": duration_frames,
                    "success_branch": copy.deepcopy(value.get("b")),
                    "timeout_branch": copy.deepcopy(value.get("c")),
                    "state_without_percentage": copy.deepcopy(value),
                })
                records[-1]["state_without_percentage"]["m"][1].pop("a")
            for key, child in value.items():
                walk(child, path + (key,), form_index)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                next_form = (index if path == ("au",) else form_index)
                walk(child, path + (index,), next_form)

    walk(tree, (), None)
    return tuple(records)


def _set_tree_path(root, path: tuple, value) -> None:
    node = root
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value


def scale_standard_damage_checks(tree: dict, hp_scale: float) -> dict:
    """Reverse-scale percentages so official absolute red-bar damage stays fixed."""

    try:
        factor = float(hp_scale)
    except (TypeError, ValueError) as exc:
        raise ValueError("DamageCheck HP 倍率不是数值") from exc
    if not math.isfinite(factor) or factor <= 0:
        raise ValueError(f"DamageCheck HP 倍率必须为有限正数:{hp_scale!r}")
    cloned = copy.deepcopy(tree)
    for record in standard_damage_check_records(tree):
        percentage = float(record["percentage"]) / factor
        if (not math.isfinite(percentage) or percentage <= 0
                or percentage > 100.0 + 1e-9):
            raise ValueError(
                "DamageCheck 保持官方绝对门槛后百分比越界:"
                f"state={record['state_id']},percentage={percentage:g}%")
        _set_tree_path(
            cloned, tuple(record["path"]) + ("m", 1, "a"), percentage)
    return cloned


def standard_damage_check_contract(
        source_tree: dict, final_tree: dict, *,
        runtime_hp_scale: float) -> dict:
    """Prove state topology and absolute DamageCheck thresholds after HP scaling."""

    try:
        runtime_scale = float(runtime_hp_scale)
    except (TypeError, ValueError) as exc:
        raise ValueError("DamageCheck 运行 HP 倍率不是数值") from exc
    if not math.isfinite(runtime_scale) or runtime_scale <= 0:
        raise ValueError("DamageCheck 运行 HP 倍率必须为有限正数")
    source = standard_damage_check_records(source_tree)
    final = standard_damage_check_records(final_tree)
    if len(source) != len(final):
        raise ValueError("DamageCheck 出现次数在 HP 伸缩后漂移")
    receipts: list[dict] = []
    for occurrence, (before, after) in enumerate(zip(source, final), start=1):
        identity_keys = ("path", "form_index", "state_id", "duration_frames",
                         "success_branch", "timeout_branch",
                         "state_without_percentage")
        if any(before[key] != after[key] for key in identity_keys):
            raise ValueError(
                f"DamageCheck[{occurrence}] 状态/窗口/成功失败分支漂移")
        source_max_hp = float(before["form_base_hp"]) * runtime_scale
        final_max_hp = float(after["form_base_hp"]) * runtime_scale
        source_threshold = source_max_hp * float(before["percentage"]) / 100.0
        final_threshold = final_max_hp * float(after["percentage"]) / 100.0
        error_hp = final_threshold - source_threshold
        tolerance = max(1e-4, abs(source_threshold) * 1e-12)
        if abs(error_hp) > tolerance:
            raise ValueError(
                f"DamageCheck[{occurrence}] 绝对伤害门槛漂移:{error_hp:g} HP")
        receipts.append({
            "occurrence": occurrence,
            "path": list(before["path"]),
            "form_index": int(before["form_index"]),
            "state_id": int(before["state_id"]),
            "source_percentage": float(before["percentage"]),
            "final_percentage": float(after["percentage"]),
            "source_max_hp": source_max_hp,
            "final_max_hp": final_max_hp,
            "source_absolute_threshold_hp": source_threshold,
            "final_absolute_threshold_hp": final_threshold,
            "absolute_error_hp": error_hp,
            "duration_frames": float(before["duration_frames"]),
            "success_branch": copy.deepcopy(before["success_branch"]),
            "timeout_branch": copy.deepcopy(before["timeout_branch"]),
        })
    return {
        "schema": STANDARD_DAMAGE_CHECK_SCHEMA,
        "occurrence_count": len(receipts),
        "runtime_hp_scale": runtime_scale,
        "checks": receipts,
        "topology_preserved": True,
        "absolute_thresholds_preserved": True,
        "static_verified": True,
        "runtime_simulated": False,
        "gameplay_verified": False,
    }


GENERAL_DAMAGE_CHECK_SCHEMA = "wf-general-boss-damage-check/v1"
GENERAL_DAMAGE_CHECK_PERCENT_COLUMN = 16
GENERAL_DAMAGE_CHECK_ROW_WIDTH = 53


def general_damage_check_records(routine_tree: dict) -> tuple[dict, ...]:
    """Read every General Boss red DamageCheck state occurrence.

    ``general_boss_state.c16`` is an optional percentage.  It is unrelated to
    ``next_state`` test kind 9 (c29/c31/c32), which is another DamageCheck
    condition and must never be rewritten as the visible red trial bar.
    Occurrences are deliberately path based: duplicate state ids remain
    duplicate runtime states and are not collapsed by code or name.
    """

    if not isinstance(routine_tree, dict):
        raise ValueError("general_boss_state routine 不是映射")
    records: list[dict] = []

    def walk(node, path: tuple[str, ...]) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                walk(child, path + (str(key),))
            return
        if not isinstance(node, (str, bytes, bytearray)):
            raise ValueError(
                f"general_boss_state 叶类型非法:path={path},"
                f"type={type(node).__name__}")
        row = cells(node)
        if len(row) != GENERAL_DAMAGE_CHECK_ROW_WIDTH:
            raise ValueError(
                f"general_boss_state 行列数={len(row)}"
                f"(!={GENERAL_DAMAGE_CHECK_ROW_WIDTH}):path={path}")
        raw_percentage = row[GENERAL_DAMAGE_CHECK_PERCENT_COLUMN]
        if raw_percentage == "(None)":
            return
        try:
            percentage = float(raw_percentage)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"General DamageCheck c16 百分比非法:path={path}:"
                f"{raw_percentage!r}") from exc
        if (not math.isfinite(percentage) or percentage <= 0
                or percentage > 100.0 + 1e-9):
            raise ValueError(
                f"General DamageCheck c16 百分比越界:path={path}:"
                f"{percentage:g}%")
        identity_row = list(row)
        identity_row[GENERAL_DAMAGE_CHECK_PERCENT_COLUMN] = None
        records.append({
            "path": tuple(path),
            "state_id": str(row[0]),
            "percentage": percentage,
            "options_c17_c21": tuple(row[17:22]),
            # Protect all other 52 columns, including state transitions and
            # the optional failure-state switch.  c16 is the only legal diff.
            "row_without_percentage": tuple(identity_row),
        })

    walk(routine_tree, ())
    return tuple(records)


def _format_damage_check_percentage(value: float) -> str:
    """Preserve sub-HP precision when a multi-billion HP bar is rescaled."""

    rendered = format(float(value), ".15g")
    if rendered in {"", "-0", "0"}:
        raise ValueError(f"DamageCheck 百分比格式化为零:{value!r}")
    return rendered


def scale_general_damage_checks(
        routine_tree: dict, *, source_max_hp: float,
        target_max_hp: float) -> dict:
    """Reverse-scale only c16 so the official absolute trial damage is kept."""

    try:
        source_hp = float(source_max_hp)
        target_hp = float(target_max_hp)
    except (TypeError, ValueError) as exc:
        raise ValueError("General DamageCheck HP 不是数值") from exc
    if not all(math.isfinite(value) and value > 0
               for value in (source_hp, target_hp)):
        raise ValueError(
            "General DamageCheck HP 必须为有限正数:"
            f"source={source_max_hp!r},target={target_max_hp!r}")
    hp_scale = target_hp / source_hp
    cloned = copy.deepcopy(routine_tree)
    for record in general_damage_check_records(routine_tree):
        percentage = float(record["percentage"]) / hp_scale
        if (not math.isfinite(percentage) or percentage <= 0
                or percentage > 100.0 + 1e-9):
            raise ValueError(
                "General DamageCheck 保持官方绝对门槛后百分比越界:"
                f"state={record['state_id']},percentage={percentage:g}%")
        path = tuple(record["path"])
        leaf = cloned
        for key in path:
            leaf = leaf[key]
        row = cells(leaf)
        row[GENERAL_DAMAGE_CHECK_PERCENT_COLUMN] = (
            _format_damage_check_percentage(percentage))
        _set_tree_path(
            cloned, path,
            join(row, isinstance(leaf, (bytes, bytearray))))
    return cloned


def general_damage_check_contract(
        source_tree: dict, baseline_tree: dict, final_tree: dict, *,
        source_max_hp: float, baseline_max_hp: float, final_max_hp: float,
        source_routine_id: str, final_routine_id: str | None,
        materialized: bool = False) -> dict:
    """Prove base/final trial thresholds and the 52-column state closure."""

    try:
        source_hp = float(source_max_hp)
        baseline_hp = float(baseline_max_hp)
        final_hp = float(final_max_hp)
    except (TypeError, ValueError) as exc:
        raise ValueError("General DamageCheck 回执 HP 不是数值") from exc
    if not all(math.isfinite(value) and value > 0
               for value in (source_hp, baseline_hp, final_hp)):
        raise ValueError("General DamageCheck 回执 HP 必须为有限正数")
    source = general_damage_check_records(source_tree)
    baseline = general_damage_check_records(baseline_tree)
    final = general_damage_check_records(final_tree)
    if len(source) != len(baseline) or len(source) != len(final):
        raise ValueError("General DamageCheck 出现次数在 HP 伸缩后漂移")
    checks: list[dict] = []
    identity_keys = (
        "path", "state_id", "options_c17_c21", "row_without_percentage")
    for occurrence, (before, base, after) in enumerate(
            zip(source, baseline, final), start=1):
        if (any(before[key] != base[key] for key in identity_keys)
                or any(before[key] != after[key] for key in identity_keys)):
            raise ValueError(
                f"General DamageCheck[{occurrence}] 非 c16 状态字段/拓扑漂移")
        source_threshold = source_hp * float(before["percentage"]) / 100.0
        baseline_threshold = baseline_hp * float(base["percentage"]) / 100.0
        final_threshold = final_hp * float(after["percentage"]) / 100.0
        baseline_error = baseline_threshold - source_threshold
        final_error = final_threshold - source_threshold
        tolerance = max(1e-4, abs(source_threshold) * 1e-12)
        if abs(baseline_error) > tolerance or abs(final_error) > tolerance:
            raise ValueError(
                f"General DamageCheck[{occurrence}] 绝对伤害门槛漂移:"
                f"baseline={baseline_error:g},final={final_error:g} HP")
        checks.append({
            "occurrence": occurrence,
            "path": list(before["path"]),
            "state_id": str(before["state_id"]),
            "source_percentage": float(before["percentage"]),
            "baseline_percentage": float(base["percentage"]),
            "final_percentage": float(after["percentage"]),
            "source_max_hp": source_hp,
            "baseline_max_hp": baseline_hp,
            "final_max_hp": final_hp,
            "source_absolute_threshold_hp": source_threshold,
            "baseline_absolute_threshold_hp": baseline_threshold,
            "final_absolute_threshold_hp": final_threshold,
            "baseline_absolute_error_hp": baseline_error,
            "final_absolute_error_hp": final_error,
            "options_c17_c21": list(before["options_c17_c21"]),
        })
    return {
        "schema": GENERAL_DAMAGE_CHECK_SCHEMA,
        "source_routine_id": str(source_routine_id),
        "final_routine_id": (
            None if final_routine_id is None else str(final_routine_id)),
        "occurrence_count": len(checks),
        "source_max_hp": source_hp,
        "baseline_max_hp": baseline_hp,
        "final_max_hp": final_hp,
        "baseline_hp_scale": baseline_hp / source_hp,
        "final_hp_scale": final_hp / source_hp,
        "hp_curse_multiplier": final_hp / baseline_hp,
        "checks": checks,
        "routine_cloned": bool(checks),
        "materialized": bool(materialized),
        "enemy_watch_lookup_preserved": not bool(checks),
        "enemy_watch_routine_alias_count": 0,
        "topology_preserved": True,
        "non_percentage_columns_preserved": True,
        "absolute_thresholds_preserved": True,
        "static_verified": True,
        "runtime_simulated": False,
        "gameplay_verified": False,
    }


def scale_standard_enemy_hp_tree(tree: dict, scale: float) -> dict:
    """克隆 Standard Enemy DSL，并只缩放各 form 的 Health(T1) 参数。"""
    try:
        factor = float(scale)
    except (TypeError, ValueError) as exc:
        raise ValueError("standard DSL HP 伸缩倍率不是数字") from exc
    if not math.isfinite(factor) or factor <= 0:
        raise ValueError(f"standard DSL HP 伸缩倍率必须为有限正数:{scale!r}")
    source = standard_enemy_hp_base(tree)
    cloned = copy.deepcopy(tree)
    forms = cloned["au"]
    for record in source["health_forms"]:
        index = int(record["form_index"])
        term = forms[index]["d"]
        value = float(term[1]) * factor
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"standard enemy form[{index}] HP 伸缩结果非法:{value}")
        term[1] = value
    cloned = scale_standard_damage_checks(cloned, factor)
    readback = standard_enemy_hp_base(cloned)
    if (readback["form_count"] != source["form_count"]
            or tuple(item["form_index"] for item in readback["health_forms"])
            != tuple(item["form_index"] for item in source["health_forms"])):
        raise RuntimeError("standard DSL HP 伸缩改变了 form/termination 结构")
    return cloned


def build_standard_enemy_dsl_blob(tree: dict) -> bytes:
    """把 Standard Enemy DSL 编码成 raw-deflate，并做语义与 HP 证据回读。"""
    expected = standard_enemy_hp_base(tree)
    raw = wf_dsl.encode_amf3(tree)
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    blob = co.compress(raw) + co.flush()
    try:
        parsed = wf_dsl.parse_dsl(zlib.decompress(blob, -15))["tree"]
    except (KeyError, TypeError, ValueError, zlib.error) as exc:
        raise RuntimeError("standard DSL build 后无法重新解码") from exc
    actual = standard_enemy_hp_base(parsed)
    if actual != expected or parsed != tree:
        raise RuntimeError("standard DSL build→parse 往返不等价")
    return blob


def _read_standard_enemy_dsl(
        logical: str, resources: dict[str, bytes] | None = None) -> dict:
    """从内存资源覆盖或只读 store 解析一份 Standard Enemy DSL。"""
    raw = resources.get(logical) if isinstance(resources, dict) else None
    if raw is None:
        raw = q.read_raw(logical)
    try:
        unpacked = zlib.decompress(raw, -15)
    except zlib.error as exc:
        raise ValueError(f"{logical} 不是 raw-deflate enemy DSL") from exc
    parsed = wf_dsl.parse_dsl(unpacked).get("tree")
    if not isinstance(parsed, dict):
        raise ValueError(f"{logical} enemy DSL 根节点不是对象")
    return parsed


def standard_boss_hp_evidence(code: str, level: int,
                              standard_boss: dict | None = None,
                              resources: dict[str, bytes] | None = None) -> dict:
    """解析一只 standard boss 在运行等级所选资源的 HP 基数。

    等级选择照 GeneralEnemySourceHelper.getSurjectivity：首个 ``>= level`` 的档。
    返回资源逻辑名、所选档和 forms 证据，供 dry-run 报告逐只回代。
    """
    table = standard_boss if standard_boss is not None else q.load_table(STANDARD_BOSS)
    node = table.get(code)
    if not isinstance(node, dict):
        raise ValueError(f"{code} 不在 standard_boss 或节点不是等级表")
    levels = sorted(int(k) for k in node if str(k).isdigit() and int(k) >= int(level))
    if not levels:
        raise ValueError(f"{code} standard_boss 无 >=lv{level} 的资源档")
    selected = levels[0]
    row = cells(node[str(selected)])
    if len(row) < 2 or not row[1].strip():
        raise ValueError(f"{code}@{selected} standard_boss 缺资源路径")
    base_path = row[1].strip()
    logical = (base_path if base_path.endswith(".esdl.amf3.deflate")
               else base_path + ".esdl.amf3.deflate")
    overlay = isinstance(resources, dict) and logical in resources
    cached = None if overlay else _STANDARD_HP_CACHE.get(logical)
    if cached is None:
        parsed = _read_standard_enemy_dsl(logical, resources)
        cached = standard_enemy_hp_base(parsed)
        if not overlay:
            _STANDARD_HP_CACHE[logical] = cached
    return dict(cached, code=code, selected_level=selected, logical=logical)


# 用户给定的 event_quest 真血量换算档；只接受已逆向确认的六个运行等级。
# 真血量(general/special 且走 boss_level) = true_stat(...)[0] × K[level] × c86。
GENERAL_HP_LEVEL_SCALE = {
    79: 2250.0, 80: 2250.0,
    89: 2362.5, 90: 2362.5,
    99: 2475.0, 100: 2475.0,
}

_OROCHI_EX_HP_TABLE: dict | None = None


def orochi_ex_hp_table() -> dict:
    """Return the dedicated Orochi EX parent table used by the HP adapter."""
    global _OROCHI_EX_HP_TABLE
    if _OROCHI_EX_HP_TABLE is None:
        try:
            value = q.load_table(wf_orochi_ex.OROCHI_EX_LOGICAL)
        except (FileNotFoundError, TypeError, ValueError, zlib.error):
            value = {}
        _OROCHI_EX_HP_TABLE = value if isinstance(value, dict) else {}
    return _OROCHI_EX_HP_TABLE


def floor_native_hp(bosses, level: int, standard_boss: dict | None = None,
                    boss_level: dict | None = None,
                    orochi_ex: dict | None = None,
                    standard_resources: dict[str, bytes] | None = None,
                    *, standard_runtime_hp_scale: float =
                    STANDARD_BOSS_BATTLE_HP_SCALE) -> dict:
    """返回该层所有实际 boss 实例在 c86 前的 HP 及证据。

    调用方必须传单人战实际槽(c24/28/32)；镜像消歧在 `_zone_pick` 完成。
    此处不按 code 去重：跨 wave / 不同实体槽允许同代号真实出场两次，须逐只相加。
    任一实例不可解析就把整层标成 unverifiable，绝不拿部分和冒充总血量。

    ``orochi_ex`` 家族拆成三项证据：第一/第三阶段来自专用表且不吃
    quest HP 修正，中段仍走 boss_level/成长曲线。这样报告和回代不会再把
    普通倍率错误地乘到整只 Boss 上。
    """
    try:
        standard_scale = float(standard_runtime_hp_scale)
    except (TypeError, ValueError) as exc:
        raise ValueError("Standard Enemy 运行 HP 倍率不是数值") from exc
    if not math.isfinite(standard_scale) or standard_scale <= 0:
        raise ValueError(
            f"Standard Enemy 运行 HP 倍率必须为有限正数:{standard_scale!r}")
    table = standard_boss if standard_boss is not None else q.load_table(STANDARD_BOSS)
    orochi_table = orochi_ex_hp_table() if orochi_ex is None else orochi_ex
    components: list[dict] = []
    reasons: list[str] = []
    for boss_occurrence, code in enumerate(map(str, bosses), start=1):
        if code in table:
            try:
                evidence = standard_boss_hp_evidence(
                    str(code), int(level), table, standard_resources)
                health_forms = evidence.get("health_forms") or tuple(
                    {"form_index": index, "base_hp": value}
                    for index, value in enumerate(evidence["health_terms"])
                )
                for phase_ordinal, form in enumerate(health_forms, start=1):
                    components.append({
                        "code": str(code), "kind": "standard",
                        "phase": f"form[{int(form['form_index'])}]",
                        "form_index": int(form["form_index"]),
                        "phase_ordinal": phase_ordinal,
                        "boss_occurrence": boss_occurrence,
                        "evidence_kind": "absolute",
                        "standard_runtime_hp_scale": standard_scale,
                        "native_hp": round(
                            float(form["base_hp"])
                            * standard_scale, 6),
                        "evidence": dict(
                            evidence,
                            standard_runtime_hp_scale=standard_scale),
                    })
            except (FileNotFoundError, KeyError, TypeError, ValueError, zlib.error) as exc:
                components.append({"code": str(code), "kind": "standard",
                                   "boss_occurrence": boss_occurrence,
                                   "native_hp": None, "error": str(exc)})
                reasons.append(f"{code}:{exc}")
            continue
        if isinstance(orochi_table, dict) and code in orochi_table:
            try:
                profile = wf_orochi_ex.read_fixed_phase_hp(
                    orochi_table, code, int(level))
                stat = true_stat(code, "hp", int(level), boss_level)
                scale = GENERAL_HP_LEVEL_SCALE.get(int(level))
                if stat is None or scale is None:
                    why = ("boss_level/曲线不可解析" if stat is None
                           else f"lv{level} 的 K 未经确认")
                    raise wf_orochi_ex.OrochiExHpError(why)
                stat_source = boss_base_stats(boss_level).get(code, {})
                evidence_kind = "absolute"
                if curve_value(
                    "hp", str(stat_source.get("hpc") or ""), int(level)
                ) is None:
                    evidence_kind = "proxy"
                middle_hp = round(float(stat[0]) * scale, 6)
                phase_components = list(wf_orochi_ex.hp_components(
                    profile, middle_hp,
                    middle_evidence_kind=evidence_kind,
                ))
                phase_components[1].update({
                    "hp_curve_kind": str(stat_source.get("hp_mode") or "hit"),
                    "true_stat": float(stat[0]),
                    "k": scale,
                })
                for component in phase_components:
                    component["boss_occurrence"] = boss_occurrence
                    component["fixed_phase_evidence"] = profile.evidence()
                components.extend(phase_components)
            except (KeyError, TypeError, ValueError,
                    wf_orochi_ex.OrochiExHpError) as exc:
                components.append({
                    "code": code, "kind": "orochi_ex",
                    "boss_occurrence": boss_occurrence,
                    "native_hp": None, "error": str(exc),
                })
                reasons.append(f"{code}:{exc}")
            continue
        stat = true_stat(str(code), "hp", int(level), boss_level)
        scale = GENERAL_HP_LEVEL_SCALE.get(int(level))
        if stat is None or scale is None:
            why = ("boss_level/曲线不可解析" if stat is None
                   else f"lv{level} 的 K 未经确认")
            components.append({"code": str(code), "kind": "unknown",
                               "boss_occurrence": boss_occurrence,
                               "native_hp": None, "error": why})
            reasons.append(f"{code}:{why}")
            continue
        stat_source = boss_base_stats(boss_level).get(str(code), {})
        hp_curve_kind = str(stat_source.get("hp_mode") or "hit")
        # Hit 的 correction 曲线查不到时，true_stat 会按既有 PROXY_CURVE 代理；
        # 这只能用于同组相对排序，绝不能在报告里冒充绝对血量证据。
        evidence_kind = "absolute"
        if (hp_curve_kind == "hit"
                and curve_value("hp", str(stat_source.get("hpc") or ""),
                                int(level)) is None):
            evidence_kind = "proxy"
        components.append({"code": str(code), "kind": "general",
                           "boss_occurrence": boss_occurrence,
                           "hp_curve_kind": hp_curve_kind,
                           "evidence_kind": evidence_kind,
                           # 数据层是十进制；消掉二进制浮点乘 K 后的
                           # 58_939_649.99999999 之类伪差，便于审计逐项对账。
                           "native_hp": round(float(stat[0]) * scale, 6),
                           "true_stat": float(stat[0]), "k": scale})
    verified = bool(components) and not reasons
    total = (math.fsum(float(c["native_hp"]) for c in components)
             if verified else None)
    return {"native_hp": total, "components": components, "verified": verified,
            "absolute_verified": (verified and all(
                c.get("evidence_kind") == "absolute" for c in components)),
            "reason": "; ".join(reasons) if reasons else None}


def _hp_component_readback_values(native: dict, c86: float) -> tuple[float, ...]:
    """按客户端取整边界回读每个 HP 组件，且保持逐出现次数可加总。

    StandardEnemySource 会先把同一实体所有 Health forms 相加，再统一乘该任务
    类型的运行 HP 倍率、quest c86 并 floor；拆成逐 form 证据后不能误改成逐
    form floor。这里把一次
    实体级 floor 的结果按未取整贡献比例分配回各 form，既保留精确总量，也让
    逐阶段审计仍可相加。Fix general 则仍按每只实体自己的 HP 组件 floor。
    """
    components = list(native.get("components") or [])
    factor = float(c86)
    if not math.isfinite(factor) or factor <= 0:
        raise ValueError(f"quest HP correction 必须为有限正数:{c86!r}")
    out: list[float | None] = [None] * len(components)
    standard_groups: dict[tuple[int, str], list[tuple[int, float]]] = {}
    for index, component in enumerate(components):
        hp = float(component["native_hp"])
        if component.get("apply_quest_hp_correction", True):
            hp *= factor
        if component.get("kind") == "standard":
            group = (int(component.get("boss_occurrence") or index + 1),
                     str(component.get("code") or ""))
            standard_groups.setdefault(group, []).append((index, hp))
        else:
            out[index] = (float(math.floor(hp))
                          if component.get("hp_curve_kind") == "fix" else hp)
    for members in standard_groups.values():
        unrounded = math.fsum(hp for _index, hp in members)
        rounded = float(math.floor(unrounded))
        allocated = 0.0
        for position, (index, hp) in enumerate(members):
            value = (rounded - allocated if position == len(members) - 1
                     else rounded * hp / unrounded)
            out[index] = value
            allocated += value
    return tuple(float(value) for value in out)


def _true_hp_at_c86(native: dict, c86: float) -> float:
    """用客户端各族的取整位置回代真 HP。"""
    return math.fsum(_hp_component_readback_values(native, c86))


def solve_floor_hp_record(r: int, n: int, native: dict, *,
                          base_duration_s: float, duration_s: float,
                          curse_hp: float, raw_c86: float,
                          family: str, target: float | None = None) -> dict:
    """分别审计无诅咒基线与最终实战 HP，血量/时限诅咒绝不被反解抵消。

    baseline_c86 只由几何目标和 quest 原始时限反解；落表 c86 再乘
    curse_hp。最终时限只用于 realized_dps，不能回头缩放 c86。
    """
    if not native.get("verified") or native.get("native_hp") is None:
        raise ValueError(f"第{r}战原生 HP 未验证:{native.get('reason') or 'unknown'}")
    base_duration = float(base_duration_s)
    duration = float(duration_s)
    hp_mult = float(curse_hp)
    if not all(math.isfinite(v) and v > 0
               for v in (base_duration, duration, hp_mult)):
        raise ValueError(
            f"第{r}战 HP 审计输入非法:base={base_duration_s},"
            f"time={duration_s},curse_hp={curse_hp}")
    target = target_dps(r, n) if target is None else float(target)
    if not math.isfinite(target) or target <= 0:
        raise ValueError(f"第{r}战目标 DPS 非法:{target!r}")
    baseline_c86 = float(fmt(solve_hp_correction(
        target, base_duration, float(native["native_hp"]))))
    # 任务 A 的乘法陷阱在这里封口：攻击组件降档后只要 curse_hp 不变，
    # 最终 c86 / 真 HP / 实战 DPS 就逐项不变。
    c86 = float(fmt(baseline_c86 * hp_mult))
    baseline_true_hp = _true_hp_at_c86(native, baseline_c86)
    true_hp = _true_hp_at_c86(native, c86)
    raw = float(raw_c86)
    if not math.isfinite(raw) or raw <= 0:
        raise ValueError(f"第{r}战原始 c86 非法:{raw_c86}")
    return {"r": r, "family": family, "verified": True,
            "absolute_verified": bool(native.get("absolute_verified")), "native": native,
            "base_duration_s": base_duration, "duration_s": duration,
            "target_dps": target, "curse_hp": hp_mult,
            "baseline_c86": baseline_c86, "c86": c86,
            "baseline_true_hp": baseline_true_hp, "true_hp": true_hp,
            "baseline_dps": baseline_true_hp / base_duration,
            "realized_dps": true_hp / duration,
            "raw_c86": raw, "family_scale": baseline_c86 / raw}


def unscaled_floor_hp_record(r: int, native: dict, *,
                             base_duration_s: float, duration_s: float,
                             curse_hp: float, raw_c86: float,
                             target: float, scaling_error: str) -> dict:
    """Keep exact HP evidence when policy cannot move a boss into the target band.

    Readability and scalability are separate facts.  A standard/special boss
    can have fully decoded absolute HP while the selected scaling policy refuses
    the c86/boss_level change needed to normalize it.  Older reporting erased
    the valid evidence in that case and mislabeled the floor as ``无boss估算``.
    """
    if not native.get("verified") or native.get("native_hp") is None:
        raise ValueError(f"第{r}战原生 HP 未验证:{native.get('reason') or 'unknown'}")
    base_duration = float(base_duration_s)
    duration = float(duration_s)
    hp_mult = float(curse_hp)
    baseline_c86 = float(raw_c86)
    wanted = float(target)
    if not all(math.isfinite(value) and value > 0 for value in (
            base_duration, duration, hp_mult, baseline_c86, wanted)):
        raise ValueError(f"第{r}战未归一 HP 审计输入非法")
    c86 = float(fmt(baseline_c86 * hp_mult))
    baseline_true_hp = _true_hp_at_c86(native, baseline_c86)
    true_hp = _true_hp_at_c86(native, c86)
    return {
        "r": r, "family": "unscaled", "verified": True,
        "absolute_verified": bool(native.get("absolute_verified")),
        "native": native,
        "base_duration_s": base_duration, "duration_s": duration,
        "target_dps": wanted, "curse_hp": hp_mult,
        "baseline_c86": baseline_c86, "c86": c86,
        "baseline_true_hp": baseline_true_hp, "true_hp": true_hp,
        "baseline_dps": baseline_true_hp / base_duration,
        "realized_dps": true_hp / duration,
        "raw_c86": baseline_c86, "family_scale": 1.0,
        "target_exempt": True, "scaling_error": str(scaling_error),
    }


# 未知曲线的代理:hp 用 boss 档(230 个 boss 在用,与 normal 同为 boss 侧修正),
# atk 用 single 档。假设,可调。
PROXY_CURVE = {"hp": "hit_hp_boss", "atk": "atk_single"}
# Unknown client-bundled Hit correction curves may use ``hit_hp_boss`` only for
# relative diagnostics.  A round-local clone is different: once both c2 and c4
# are rewritten, this downloaded/bundled curve becomes the authoritative HP
# channel and can be read back with the exact client formula.
AUTHORITATIVE_HIT_HP_CURVE = "hit_hp_boss"


def curve_medians(codes, level: int = 100) -> tuple[dict, dict]:
    """给一批 boss 代号 → 每个归一化分组的中位数(目标锚)。

    曲线已知的全部归入 "*" 组(真实数值可比);未知的按曲线名各自成组。
    """
    hp_g: dict[str, list] = {}
    atk_g: dict[str, list] = {}
    for c in codes:
        for kind, g in (("hp", hp_g), ("atk", atk_g)):
            t = true_stat(c, kind, level)
            if t:
                g.setdefault(t[1], []).append(t[0])
    med = lambda xs: sorted(xs)[len(xs) // 2]        # noqa: E731
    return ({k: med(v) for k, v in hp_g.items()},
            {k: med(v) for k, v in atk_g.items()})


COMPRESS_DEFAULT = {"hp": 1.0, "atk": 0.55}


def stat_normalize(bosses, hp_med: dict, atk_med: dict,
                   lo: float, hi: float, level: int = 100,
                   compress: dict | None = None,
                   hi_by_kind: dict | None = None) -> tuple[float, float]:
    """一层的 (hp 补偿, atk 补偿)。同曲线组中位数 ÷ 本层基数,夹在 [lo, hi]。

    一层多个 boss 时取**基数最大的那个**当代表(血最厚的决定这层的手感)。
    查不到基数(standard 系/专用表)返回 (1.0, 1.0) —— 无数据不瞎补。
    """
    compress = compress or COMPRESS_DEFAULT
    hi_by_kind = hi_by_kind or {}
    fh = fa = 1.0
    for kind, med in (("hp", hp_med), ("atk", atk_med)):
        vals = [t for t in (true_stat(c, kind, level) for c in bosses) if t]
        if not vals:
            continue
        val, grp = max(vals, key=lambda t: t[0])     # 一层多 boss:按最厚的算
        anchor = med.get(grp)
        if not anchor:
            continue
        # **压缩而不是抹平**:指数 1.0 = 完全拉平,0 = 完全不动。
        # 血量可以拉平(极差 2846× 纯属噪声),但**伤害要留高低差**——
        # 全池 atk 极差 86×,一刀切归一会把 134 个削、118 个抬,只剩 15 个没动,
        # boss 之间的"这个打得疼"手感就没了(2026-07-29 用户:不要太高或太低,可以高低有别)。
        # 残余跨度 ≈ 原极差^(1-指数):atk 86^0.4 ≈ 6× 的区间,有别但不致命。
        k = compress[kind]
        f = (anchor / val) ** k if k else 1.0
        f = min(float(hi_by_kind.get(kind, hi)), max(lo, f))
        if kind == "hp":
            fh = f
        else:
            fa = f
    return fh, fa


def stat_anchor(bosses, med: dict, kind: str, level: int) -> tuple[float, float] | None:
    """该层的 (原生数值, 同曲线组中位锚);查不到基数返回 None。

    None = standard 表 boss(无 boss_level 条目)——归一化对它们**无效**,拿到的
    是裸曲线值,原生数值不在审计视野内。返回值有两个用途:
      · None → 走 NOBASE_ATK_CAP + 禁攻击类诅咒
      · 非 None → 真伤指数闸(原生 atk 高的 boss,col 合规也可能每跳爆表)
    与 stat_normalize 同口径:一层多 boss 取基数最大的那个。"""
    best = None
    for c in bosses:
        t = true_stat(c, kind, level)
        if t and med.get(t[1]) and (best is None or t[0] > best[0]):
            best = (t[0], med[t[1]])
    return best


def solve_atk(rec: dict, atk_base: float, atk_growth: float,
              scale: float = 1.0) -> float:
    """只计算曲线×攻击来源×攻击诅咒的真实乘积，不静默夹值。

    ``st_mult`` 只保留给旧 ``--ramp`` HP/档位；默认线性 Boss HP 不吃该乘区。
    攻击超标由 ``enforce_atk_band`` 显式降档。
    """
    factors = {
        "atk_base": atk_base,
        "atk_growth": atk_growth,
        "scale": scale,
        "ba": rec.get("ba"),
        "curse.atk": (rec.get("curse") or {}).get("atk"),
    }
    for name, raw in factors.items():
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"第{rec.get('r')}战攻击因子 {name} 非数值:{raw!r}") from exc
        if not math.isfinite(value) or value <= 0:
            raise RuntimeError(f"第{rec.get('r')}战攻击因子 {name} 必须为有限正数:{raw!r}")
    try:
        value = (float(atk_base) * (float(atk_growth) ** (int(rec["r"]) - 1))
                 * float(rec["ba"]) * float(scale)
                 * float(rec["curse"]["atk"]))
    except (OverflowError, TypeError, ValueError) as exc:
        raise RuntimeError(f"第{rec.get('r')}战攻击乘积不可计算") from exc
    if not math.isfinite(value) or value <= 0:
        raise RuntimeError(f"第{rec.get('r')}战攻击乘积必须为有限正数:{value!r}")
    return value


def band_stats(cols: list[float]) -> dict:
    """col 分布的三个受检分位(P90 = 最近秩)。闸门与体检读数**共用**这一个口径,
    否则会出现"闸门说过了、体检说超了"的自相矛盾。"""
    s = sorted(cols)
    return {"median": statistics.median(s), "max": s[-1],
            "p90": s[min(len(s) - 1, math.ceil(0.9 * len(s)) - 1)]}


def band_violation(cols: list[float]) -> tuple[str, float] | None:
    """全塔 col 分布是否落进目标带 → (超标项, 实测值) 或 None。"""
    if not cols:
        return None
    got = band_stats(cols)
    for key in ("max", "p90", "median"):
        if got[key] > BAND_TARGET[key] + 1e-9:
            return key, got[key]
    return None


def enforce_atk_band(recs: list[dict], atk_base: float, atk_growth: float,
                     n: int) -> tuple[float, list[str]]:
    """全塔攻击硬闸：先降攻击诅咒，再显式降低该层攻击来源 ``ba``。"""
    if n <= 0:
        raise RuntimeError(f"塔层数必须为正数:{n}")
    scale, log = 1.0, []

    def recalc() -> None:
        for rec in recs:
            rec["atk"] = solve_atk(rec, atk_base, atk_growth, scale)

    def explicit_limit(rec: dict) -> float:
        limit = BAND_TARGET["max"]
        if rec.get("anchor"):
            native, med = map(float, rec["anchor"])
            if (not math.isfinite(native) or not math.isfinite(med)
                    or native <= 0 or med <= 0):
                raise RuntimeError(
                    f"第{rec.get('r')}战真伤锚必须为有限正数:{rec.get('anchor')!r}")
            limit = min(limit, TRUE_DMG_CAP * med / native)
        if not math.isfinite(limit) or limit <= 0:
            raise RuntimeError(f"第{rec.get('r')}战攻击上限非法:{limit!r}")
        return limit

    def downgrade(rec: dict, limit: float, reason: str) -> None:
        if rec["atk"] <= limit + 1e-9:
            return
        note = downgrade_atk_curse(rec["curse"])
        if note is None:
            old_ba = float(rec["ba"])
            rec["ba"] = old_ba * limit / rec["atk"]
            if (not math.isfinite(float(rec["ba"])) or float(rec["ba"]) <= 0
                    or not float(rec["ba"]) < old_ba):
                raise RuntimeError(
                    f"第{rec.get('r')}战攻击来源降档无进展:{old_ba!r}→{rec['ba']!r}")
            note = (f"攻击来源×{old_ba:g}→×{rec['ba']:g}"
                    f"（{reason}目标×{limit:g}）")
        log.append(f"[分位闸] 第{rec['r']}战 {note}")
        recalc()

    recalc()
    for _ in range(600):
        hard = [rec for rec in recs
                if rec["atk"] > explicit_limit(rec) + 1e-9]
        if hard:
            top = max(hard,
                      key=lambda rec: (rec["atk"] / explicit_limit(rec), rec["r"]))
            limit = explicit_limit(top)
            reason = ("原生攻击尖峰" if limit < BAND_TARGET["max"] - 1e-12
                      else "全塔硬上限")
            downgrade(top, limit, reason)
            continue
        bad = band_violation([rec["atk"] for rec in recs])
        if bad:
            key, got = bad
            limit = BAND_TARGET[key]
            hot = max((rec for rec in recs if rec["atk"] > limit + 1e-9),
                      key=lambda rec: (rec["atk"], rec["r"]), default=None)
            if hot is None:
                raise RuntimeError(f"攻击分位 {key}={got:g} 超标但找不到可降档楼层")
            downgrade(hot, limit, f"{key}={got:g}")
            continue
        break
    else:
        raise RuntimeError("攻击分位闸未在 600 步内收敛")
    for rec in recs:
        limit = explicit_limit(rec)
        if rec["atk"] > limit + 1e-9:
            raise RuntimeError(
                f"第{rec['r']}战攻击×{rec['atk']:g}仍超过硬上限×{limit:g}")
    bad = band_violation([rec["atk"] for rec in recs])
    if bad:
        raise RuntimeError(f"攻击分位闸后置复核失败:{bad[0]}={bad[1]:g}")
    return scale, log


def resolve_level(bosses, want: int, lv_ceil: dict | None,
                  lv_floor: dict | None, lv_gb: dict | None,
                  prefer_max: bool = False) -> int | None:
    """给一组 boss 找可行敌等级;都不行返回 None。

    候选 = 三张等级表里出现过的键(20/49/50/70/79/80/100…)+ want。
    prefer_max=False:取离 want 最近(同距优先高),终始之龙在 90 级塔自动落 80。
    prefer_max=True(「最强」模式,2026-07-28 用户需求):取全 boss 都可行的
    **最高档**,即每个 boss 都以自己数据里的最强形态出场
    (白虎/水机兵Hard→100、终始之龙/风机兵→80)。"""
    if not bosses:
        return want
    table_keys: set[int] = set()
    for code in bosses:
        for table in (lv_ceil, lv_floor, lv_gb, special_boss_levels()):
            entry = (table or {}).get(code)
            if isinstance(entry, dict):
                table_keys |= {int(k) for k in entry if str(k).isdigit()}
    if prefer_max:
        # 只在数据里真实存在的档位中选;无等级表的 boss 用 want 兜底
        order = sorted(table_keys, reverse=True) or [int(want)]
    else:
        order = sorted(table_keys | {int(want)}, key=lambda x: (abs(x - want), -x))
    for level in order:
        if all(boss_level_ok(code, level, lv_ceil, lv_floor, lv_gb) for code in bosses):
            return level
    return None


def validate_built_rows(rows: dict[str, list[str]], fd: dict, zone: dict,
                        enemies: set[str], zakos: set[str],
                        lv_ceil: dict | None = None,
                        lv_floor: dict | None = None,
                        lv_gb: dict | None = None,
                        validation_tables: dict | None = None) -> list[dict]:
    """构建产物(round → quest 行)逐关链检查;写入前调用,悬空即拒绝产出。

    lv_ceil=standard_boss / lv_floor=gv / lv_gb=general_boss,按每行 c95 查等级覆盖。"""
    reports = []
    for rk, row in rows.items():
        if len(row) > 98:
            level = int(row[95]) if len(row) > 95 and str(row[95]).isdigit() else None
            rep = check_field_chain(row[98], fd, zone, enemies, zakos, level=level,
                                    lv_ceil=lv_ceil, lv_floor=lv_floor, lv_gb=lv_gb,
                                    validation_tables=validation_tables)
        else:
            rep = {"ok": False, "field": None, "zone": None, "bosses": [],
                   "zakos": [], "errors": ["quest 行不足 99 列(缺 c98 field)"]}
        rep["round"] = rk
        rep["quest_id"] = row[0] if row else ""
        reports.append(rep)
    return reports


def validate_event_chain(event_id: str, *, qt: dict | None = None,
                         fd: dict | None = None, zone: dict | None = None,
                         enemies: set[str] | None = None,
                         zakos: set[str] | None = None,
                         lv_ceil: dict | None = None,
                         lv_floor: dict | None = None,
                         lv_gb: dict | None = None,
                         validation_tables: dict | None = None,
                         quest_path: "Path | None" = None) -> list[dict]:
    """事件全部关卡的解析链报告(输入 event_id,输出每关状态)。

    表参数缺省时读 store 现状;quest_path 可指定 quest 表备份文件回溯历史
    (复现 .bak-wfmod-rush99field 里关 13 的 water_sphere 悬空)。
    """
    if qt is None:
        qt = q.load_table(Q_QUEST, path=quest_path)
    if fd is None:
        fd = q.load_table(FIELD_DATA_T)
    if zone is None:
        zone = q.load_table(ZONE_T)
    if zakos is None:
        zakos = set(q.load_table(GENERAL_ZAKO))
    if enemies is None:
        sb = q.load_table(STANDARD_BOSS)
        gb = q.load_table(GENERAL_BOSS)
        enemies = set(gb) | set(sb) | zakos
        if lv_ceil is None:
            lv_ceil = sb
        if lv_floor is None:
            lv_floor = q.load_table("master/battle/boss/general_boss_variable.orderedmap")
        if lv_gb is None:
            lv_gb = gb
    ev = qt.get(str(event_id))
    if not isinstance(ev, dict):
        return [{"ok": False, "round": None, "quest_id": None, "field": None,
                 "zone": None, "bosses": [], "zakos": [],
                 "errors": [f"rush_event_quest[{event_id}] 缺失或不是嵌套 map"]}]
    rows: dict[str, list[str]] = {}
    for rk, leaf in ev.items():
        if isinstance(leaf, dict):
            rows[rk] = []
        else:
            rows[rk] = cells(leaf)
    return validate_built_rows(rows, fd, zone, enemies, zakos,
                               lv_ceil=lv_ceil, lv_floor=lv_floor, lv_gb=lv_gb,
                               validation_tables=validation_tables)


def print_chain_reports(reports: list[dict]) -> int:
    """打印每关状态,返回悬空关数。"""
    bad = 0
    for rep in reports:
        boss_disp = ",".join(rep["bosses"]) or "-"
        if rep["ok"]:
            print(f"  关{rep['round']}: field={rep['field']} boss={boss_disp} OK")
        else:
            bad += 1
            print(f"  关{rep['round']}: field={rep['field']} boss={boss_disp} ✗")
            for e in rep["errors"]:
                print(f"      {e}")
    return bad


# zone 的 boss 槽 = 三对列,每对 (单人战代号, 多人战代号)。客户端
# ZoneSourceValues.get_bossN() 按 isSingleBattle 二选一读其中**一列**
# (single→c24/28/32,multi→c26/30/34),所以两列必须始终指向同一只 boss;
# 只改半边 = 换 boss 在一种战斗模式下静默失效(2026-07-30 法阵克隆实锤,见
# gimmick_field)。
ZONE_BOSS_SLOTS = ((24, 26), (28, 30), (32, 34))


def _legacy_active_boss_slots(zn) -> tuple[rbb.ActiveBossSlot, ...]:
    """Adapt a bare zone node through the new active-slot parser.

    Older callers do not carry a field/terrain identity.  For that legacy-only
    boundary, each well-formed zone row is represented by a synthetic terrain
    layer, then parsed by :func:`rbb.active_boss_slots`; production field reads
    must use the real terrain path via ``_zone_pick``.  Missing BossKind is never
    inferred from the mirror side: malformed legacy rows fail closed too.
    """
    if not isinstance(zn, dict):
        return ()
    normalized: dict[str, str] = {}
    layers: list[dict] = []
    for layer, leaf in zn.items():
        if isinstance(leaf, dict) or not str(layer).isdigit():
            continue
        try:
            row = cells(leaf)
        except (TypeError, ValueError, csv.Error, StopIteration):
            continue
        if len(row) <= 34:
            continue
        normalized[str(layer)] = join(row, isinstance(leaf, (bytes, bytearray)))
        layers.append({"type": "objectgroup", "name": str(layer), "objects": []})
    if not normalized:
        return ()
    try:
        return rbb.active_boss_slots(
            "__legacy__",
            {"__legacy__": "__legacy__,terrain/__legacy__,__legacy_zone__"},
            {"__legacy_zone__": normalized},
            terrain_loader=lambda _logical: {"layers": layers},
        )
    except rbb.TerrainGateError:
        return ()


