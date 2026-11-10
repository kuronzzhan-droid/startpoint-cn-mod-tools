# Source section of rogue_build; loaded in its shared module namespace.
def build_native_bundle_catalog(
        enemy_level: int = 100, *,
        fd: dict | None = None,
        zone: dict | None = None,
        sb: dict | None = None,
        gb: dict | None = None,
        gv: dict | None = None,
        bl: dict | None = None,
        gz: dict | None = None,
        special_tables: dict | None = None,
        general_boss_state: dict | None = None,
        general_funnel: dict | None = None,
        standard_funnel: dict | None = None,
        kraken_tentacle: dict | None = None,
        kraken_funnel_level: dict | None = None,
        sphere_aux_tables: dict[str, dict] | None = None,
        general_enemy_watch: dict | None = None,
        funnel_ok=None,
        terrain_loader=None,
        action_loader=None,
        esdl_loader=None,
        code_references: dict | None = None,
        display_names: dict[str, str] | None = None,
        metadata_of=None,
        ) -> rbb.BundleCatalog:
    """Build the read-only post-gate catalog from every official active field.

    `cb.build_pool()` is deliberately absent: it may provide UI metadata later,
    but never decides boss identity or eligibility.  Live `mod_rogue_*` clones
    are provenance-filtered even when this API is called outside main's stale
    purge path, so a previous dry-run/write cannot add extra family tickets.
    """
    level = int(enemy_level)
    # A fully injected factory call is an isolated snapshot contract.  Optional
    # Task3 tables/resources that were not supplied must make portability
    # native-only; they must never fall through to the live store behind the
    # caller's back (the existing factory test pins this boundary).
    fully_injected = all(value is not None for value in (
        fd, zone, sb, gb, gv, bl, gz, special_tables))
    # The builder later purges stale ``mod_rogue_*`` rows in memory.  Keep this
    # factory uncached and accept those sanitized tables explicitly; otherwise
    # a same-process rebuild can silently reuse the pre-purge catalog.  The
    # no-argument path remains a read-only audit helper against the live store.
    fd = fd if fd is not None else q.load_table(FIELD_DATA_T)
    zone = zone if zone is not None else q.load_table(ZONE_T)
    sb = sb if sb is not None else q.load_table(STANDARD_BOSS)
    gb = gb if gb is not None else q.load_table(GENERAL_BOSS)
    gv = (gv if gv is not None else
          q.load_table("master/battle/boss/general_boss_variable.orderedmap"))
    bl = (bl if bl is not None else
          q.load_table("master/battle/boss/boss_level.orderedmap"))
    gz = gz if gz is not None else q.load_table(GENERAL_ZAKO)
    boss_states = (general_boss_state if general_boss_state is not None else
                   {} if fully_injected else
                   q.load_table("master/battle/boss/general_boss_state.orderedmap"))
    general_funnels = (general_funnel if general_funnel is not None else
                       {} if fully_injected else q.load_table(GENERAL_FUNNEL))
    standard_funnels = (standard_funnel if standard_funnel is not None else
                        {} if fully_injected else q.load_table(
                            "master/battle/boss/funnel/standard_funnel.orderedmap"))
    kraken_tentacles = (
        kraken_tentacle if kraken_tentacle is not None else
        {} if fully_injected else q.load_table(KRAKEN_TENTACLE))
    kraken_funnel_levels = (
        kraken_funnel_level if kraken_funnel_level is not None else
        {} if fully_injected else q.load_table(KRAKEN_FUNNEL_LEVEL))
    if sphere_aux_tables is not None:
        sphere_auxiliaries = dict(sphere_aux_tables)
    elif fully_injected:
        sphere_auxiliaries = {}
    else:
        sphere_auxiliaries = {
            name: q.load_table(logical)
            for name, logical in SPHERE_AUX_LOGICALS.items()
        }
    if general_enemy_watch is not None:
        enemy_watch = general_enemy_watch
    elif fully_injected:
        enemy_watch = None
    else:
        try:
            enemy_watch = q.load_table(ENEMY_WATCH)
        except Exception:
            # ``code_referenced_bosses`` will mark the matching scan degraded;
            # keep this snapshot missing so the special HP gate cannot pretend
            # that a required self-watch subtree is cloneable.
            enemy_watch = None
    validation = boss_ref_validation_tables(
        standard_boss=sb, general_boss=gb, general_boss_variable=gv,
        special_tables=special_tables, funnel_ok=funnel_ok)
    if special_tables is None:
        validation["orochi_ex_head"] = _tbl(OROCHI_EX_HEAD)
    else:
        validation.setdefault("orochi_ex_head", {})
    names = dict(display_names) if display_names is not None else wb.boss_names()

    def selected_leaf(ref: rbb.BossRef, selected: int | None):
        table_name = rbb.KIND_TABLES.get(ref.kind)
        table = validation.get(table_name, {}) if table_name else {}
        node = table.get(ref.code) if isinstance(table, dict) else None
        if isinstance(node, dict):
            if selected is not None and str(selected) in node:
                return node[str(selected)]
            for key in node:
                if str(key).isdigit():
                    return node[key]
            return None
        return node

    def identity_of(ref: rbb.BossRef, selected: int | None) -> dict:
        leaf = selected_leaf(ref, selected)
        text = (leaf.decode("utf-8", "replace") if isinstance(leaf, bytes)
                else leaf if isinstance(leaf, str) else "")
        model = ""
        roots: set[str] = set()
        for line in text.splitlines() or (text,):
            for value in cells(line) if line else ():
                if value.startswith("battle/boss/") and "general_16dots" not in value:
                    parts = value.split("/")
                    if len(parts) > 2 and not model:
                        model = parts[2]
                elif value.startswith("battle/enemy/boss/"):
                    parts = value.split("/")
                    if len(parts) > 3 and not model:
                        model = parts[3].split("$")[0]
                    roots.add(value)
                if value.startswith("battle/action"):
                    roots.add(value)
        return {
            "display": names.get(ref.code) or "",
            "model": model or ref.code,
            "actions": tuple(sorted(roots)),
        }

    def reference_gate(_field_id: str, slots: tuple[rbb.ActiveBossSlot, ...],
                       selected_levels: tuple[tuple[str, int, int], ...],
                       _level: int):
        # Task 2 proves the exact active single slot, its selected source leaf,
        # standard ESDL path / general boss_level row, and active zako refs.
        # External hard/soft code references and recursive action/spawn closure
        # are deliberately not claimed here; the portability gate below owns
        # that transitive proof without changing native eligibility.
        selected = {(layer, slot): tier for layer, slot, tier in selected_levels}
        for slot in slots:
            ref = slot.single
            if ref is None:
                continue
            result = rbb.validate_boss_ref(ref, _level, validation)
            if not result.ok:
                return rbb.GateResult(False, result.reason or "REFERENCE",
                                      detail=result.detail)
            if result.selected_level is not None:
                if selected.get((slot.layer, slot.slot)) != result.selected_level:
                    return rbb.GateResult(
                        False, "REFERENCE",
                        detail=f"slot {slot.layer}/{slot.slot} selected tier drift")
            if ref.kind == 0:
                leaf = selected_leaf(ref, result.selected_level)
                if not isinstance(leaf, (str, bytes, bytearray)):
                    return rbb.GateResult(False, "REFERENCE",
                                          detail=f"standard source leaf missing:{ref.code}")
                row = cells(leaf)
                if len(row) < 2 or not row[1]:
                    return rbb.GateResult(False, "REFERENCE",
                                          detail=f"standard ESDL path missing:{ref.code}")
                logical = (row[1] if row[1].endswith(".esdl.amf3.deflate")
                           else row[1] + ".esdl.amf3.deflate")
                if not q.exists_current(logical):
                    return rbb.GateResult(False, "REFERENCE",
                                          detail=f"standard ESDL file missing:{logical}")
            elif ref.code not in bl:
                return rbb.GateResult(False, "REFERENCE",
                                      detail=f"boss_level missing:{ref.code}")
        return rbb.GateResult(True)

    def hp_gate(slots: tuple[rbb.ActiveBossSlot, ...], _level: int):
        refs = [slot.single for slot in slots if slot.single is not None]
        if any(ref.kind not in (0, 1, 8) for ref in refs):
            return rbb.GateResult(False, "SPECIAL_HP_CHANNEL_UNSUPPORTED")
        # Preserve BossKind through HP dispatch.  ``floor_native_hp`` has a
        # legacy code-membership branch; forcing the exact source prevents a
        # future code that exists in both tables from turning kind 1 into a
        # standard ESDL read (or kind 0 into boss_level math).
        failures = []
        for ref in refs:
            if ref.kind == 0:
                evidence = floor_native_hp(
                    [ref.code], _level, standard_boss=sb, boss_level={},
                    standard_runtime_hp_scale=RUSH_EVENT_STANDARD_HP_SCALE)
            else:  # kinds 1/8 are both verified GeneralBoss source paths
                evidence = floor_native_hp(
                    [ref.code], _level, standard_boss={}, boss_level=bl)
            if not evidence.get("verified"):
                failures.append(
                    f"kind={ref.kind} code={ref.code}:"
                    f"{evidence.get('reason') or 'unknown HP'}")
        if failures:
            return rbb.GateResult(False, "HP_UNVERIFIED", detail="; ".join(failures))
        return rbb.GateResult(True)

    def bundle_hp_gate(bundle: rbb.NativeBossBundle, _level: int):
        family = special_bundle_family(bundle)
        if family in SINGLE_BAR_SPECIAL_SPECS:
            evidence_tables = {
                family: validation.get(family, {}),
                "boss_level": bl,
                "kraken_tentacle": kraken_tentacles,
                "kraken_funnel_level": kraken_funnel_levels,
                "__code_references__": code_refs,
                "__action_loader__": effective_action_loader,
                "__spawned_ref_gate__": spawned_ref_gate,
            }
            evidence = single_bar_special_native_hp_evidence(
                bundle, _level, evidence_tables)
            graph = evidence.get("graph")
            if (not evidence.get("verified")
                    or not evidence.get("absolute_verified")
                    or not isinstance(graph, SingleBarSpecialGraph)
                    or not graph.ok):
                return rbb.GateResult(
                    False, "SPECIAL_HP_CHANNEL_UNSUPPORTED",
                    detail=(evidence.get("detail")
                            or evidence.get("reason")
                            or "single victory-bar proof failed"))
            return rbb.GateResult(
                True, selected_level=graph.selected_level,
                source_table=family)
        if family in SPHERE_SPECS:
            evidence = sphere_native_hp_evidence(bundle, _level, {
                family: validation.get(family, {}),
                "boss_level": bl,
                **sphere_auxiliaries,
                "__code_references__": code_refs,
                "__action_loader__": effective_action_loader,
            })
            graph = evidence.get("graph")
            if (not evidence.get("verified")
                    or not evidence.get("absolute_verified")
                    or not isinstance(graph, SphereGraph) or not graph.ok):
                return rbb.GateResult(
                    False, "SPECIAL_HP_CHANNEL_UNSUPPORTED",
                    detail=(evidence.get("detail") or evidence.get("reason")
                            or "Sphere victory-component proof failed"))
            return rbb.GateResult(
                True, selected_level=graph.selected_level,
                source_table=family)
        if family == "orochi_ex":
            if code_refs.get("degraded"):
                return rbb.GateResult(
                    False, "SPECIAL_HP_CHANNEL_UNSUPPORTED",
                    detail="external boss-code reference scan degraded")
            evidence = orochi_ex_native_hp_evidence(bundle, _level, {
                "orochi_ex": validation.get("orochi_ex", {}),
                "orochi_ex_head": validation.get("orochi_ex_head", {}),
                "boss_level": bl,
            })
            graph = evidence.get("graph")
            if (not evidence.get("verified")
                    or not evidence.get("absolute_verified")
                    or not isinstance(graph, OrochiExGraph) or not graph.ok):
                return rbb.GateResult(
                    False, "SPECIAL_HP_CHANNEL_UNSUPPORTED",
                    detail=(evidence.get("detail")
                            or evidence.get("reason") or "three-bar proof failed"))
            return rbb.GateResult(
                True, selected_level=graph.selected_level,
                source_table="orochi_ex")
        if family != "orochi":
            refs = [slot.single for slot in bundle.slots
                    if slot.single is not None]
            return rbb.GateResult(
                False, "SPECIAL_HP_CHANNEL_UNSUPPORTED",
                detail=("VICTORY_COMPONENTS_UNAUDITED:"
                        + ";".join(f"kind={ref.kind}/{ref.code}" for ref in refs)))
        expanded = expand_bundle_hp_members(bundle, _level, {
            "orochi": validation.get("orochi", {}),
            "general_boss": gb,
            "general_boss_variable": gv,
            "boss_level": bl,
        })
        if not expanded.ok:
            return rbb.GateResult(
                False, expanded.reason or "SPECIAL_HP_CHANNEL_UNSUPPORTED",
                detail=expanded.detail)
        ref_error = _orochi_clone_reference_error(
            expanded, code_refs, enemy_watch)
        if ref_error:
            return rbb.GateResult(
                False, "SPECIAL_HP_CHANNEL_UNSUPPORTED", detail=ref_error)
        return rbb.GateResult(
            True, selected_level=expanded.selected_parent_level,
            source_table="orochi")

    if code_references is not None:
        code_refs = code_references
    elif fully_injected:
        code_refs = {"hard": frozenset(), "soft": frozenset(), "degraded": True}
    else:
        code_refs = code_referenced_bosses(gb)

    def missing_resource(kind: str):
        def load(logical: str):
            raise FileNotFoundError(
                f"{kind} loader not injected for isolated catalog:{logical}")
        return load

    effective_action_loader = (
        action_loader if action_loader is not None else
        missing_resource("action") if fully_injected else rbb.load_store_action)
    effective_esdl_loader = (
        esdl_loader if esdl_loader is not None else
        missing_resource("ESDL") if fully_injected else rbb.load_store_esdl)

    def spawned_ref_gate(source_kind: str, code: str, _level: int):
        return validate_spawned_ref(
            source_kind, code, _level,
            validation_tables=validation,
            general_zako=gz,
            general_funnel=general_funnels,
            standard_funnel=standard_funnels)

    requirement_cache: dict[tuple, rbb.RequirementResult] = {}

    def portability_gate(bundle: rbb.NativeBossBundle) -> rbb.RequirementResult:
        active_codes = tuple(sorted(
            slot.single.code for slot in bundle.slots if slot.single is not None))
        if code_refs.get("degraded"):
            return rbb.RequirementResult(
                False, reason="ACTION_CLOSURE_UNAUDITED",
                detail="external boss-code reference scan degraded")
        hard = sorted(set(active_codes) & set(code_refs.get("hard", ())))
        if hard:
            return rbb.RequirementResult(
                False, reason="ACTION_CLOSURE_UNAUDITED",
                detail="external hard boss-code references:" + ",".join(hard))
        key = (
            tuple((slot.layer, slot.slot,
                   None if slot.single is None else slot.single.kind,
                   None if slot.single is None else slot.single.code)
                  for slot in bundle.slots),
            bundle.selected_levels,
            bundle.active_layers,
        )
        if key not in requirement_cache:
            requirement_cache[key] = rbb.boss_terrain_requirements(
                bundle, level, {
                    "general_boss": gb,
                    "standard_boss": sb,
                    "general_boss_state": boss_states,
                    "action_loader": effective_action_loader,
                    "esdl_loader": effective_esdl_loader,
                    "spawned_ref_gate": spawned_ref_gate,
                })
        return requirement_cache[key]

    metadata_provider = metadata_of
    if metadata_provider is None:
        thumbnails = field_thumbnail_map()
        metadata_index: dict[str, set[tuple[str, str, str]]] = {}
        field_levels: dict[str, int] = {}
        field_ids = set(fd)

        # Official floor rows are the strongest field-local BGM source.  Their
        # third cell is only a 31×31 in-battle floor icon and must never flow
        # into rush quest c5; ``field_thumbnail_map`` resolves the independent
        # 240×188 quest cover chain.
        try:
            floor_table = q.load_table("master/battle/floor.orderedmap")
        except (FileNotFoundError, KeyError, TypeError, ValueError, zlib.error):
            floor_table = {}
        floor_bgm: dict[str, set[str]] = {}
        for node in floor_table.values():
            if isinstance(node, dict):
                continue
            text = (node.decode("utf-8", "replace")
                    if isinstance(node, (bytes, bytearray)) else str(node))
            for line in text.splitlines():
                values = cells(line)
                if not values or values[0] not in field_ids:
                    continue
                field_id = values[0]
                bgm = values[1] if len(values) > 1 else ""
                if bgm not in ("", "(None)"):
                    floor_bgm.setdefault(field_id, set()).add(bgm)
                metadata_index.setdefault(field_id, set()).add(
                    ("floor", "" if bgm == "(None)" else bgm,
                     thumbnails.get(field_id, "")))

        # Verified CN schemas where the BGM token is immediately after the
        # field cell.  challenge_dungeon uses field+1 as a frame limit and
        # skill_preview ends at the field, so neither is guessed here.
        direct_bgm_categories = {
            "boss_battle", "main", "ex", "practice", "advent", "raid",
            "rush", "hard_multi", "expert_single", "ranking",
            "score_attack", "solo_time_attack", "carnival", "story_event",
            "world_story", "world_story_boss",
        }
        for category, _label, logical, _group, _icon in wb.QUEST_CATS:
            try:
                quest_table = wb._load(logical)
            except (FileNotFoundError, KeyError, TypeError, ValueError, zlib.error):
                continue
            for _path, row in wb._leaves(quest_table):
                if not isinstance(row, str):
                    continue
                values = cells(row)
                referenced = [(index, value) for index, value in enumerate(values)
                              if value in field_ids]
                if not referenced:
                    continue
                for index, field_id in referenced:
                    source_level = quest_level_of(values, index)
                    if source_level:
                        field_levels[field_id] = max(
                            field_levels.get(field_id, 0), int(source_level))
                    direct_bgm = (values[index + 1]
                                  if category in direct_bgm_categories
                                  and index + 1 < len(values) else "")
                    if direct_bgm in ("", "(None)"):
                        direct_bgm = next(iter(sorted(floor_bgm.get(field_id, ()))), "")
                    thumbnail = thumbnails.get(field_id, "")
                    metadata_index.setdefault(field_id, set()).add(
                        (category, direct_bgm, thumbnail))

        def metadata_provider(field_id: str) -> dict:
            aliases = tuple(sorted(
                metadata_index.get(field_id, set()),
                key=lambda alias: (alias[0] == "floor", alias)))
            if aliases:
                category, bgm, thumbnail = aliases[0]
            else:
                category, bgm, thumbnail = "official", "", thumbnails.get(field_id, "")
            return {"category": category, "bgm": bgm, "thumbnail": thumbnail,
                    "aliases": aliases, "level": field_levels.get(field_id, 0)}

    return rbb.build_native_bundle_catalog(
        fd, zone, terrain_loader or rbb.load_store_terrain,
        enemy_level=level,
        validation_tables=validation,
        display_names=names,
        identity_of=identity_of,
        hp_gate=hp_gate,
        bundle_hp_gate=bundle_hp_gate,
        reference_gate=reference_gate,
        zako_codes=set(gz),
        portability_gate=portability_gate,
        official_field=lambda field_id: not field_id.startswith(("mod_rogue_", "mod_abyss_ex_")),
        metadata_of=metadata_provider,
        c8016_prefixes=C8016_BLOCKED_BOSS_PREFIXES,
    )


def choose_endless_native_bundle(rng, enemy_level: int = 100) \
        -> rbb.NativeBossBundle:
    """从正式构建器的 fresh post-gate catalog 选一个原生安全 bundle。"""
    level = int(enemy_level)
    if level <= 0:
        raise ValueError(f"无尽层敌等级非法:{enemy_level!r}")
    catalog = build_native_bundle_catalog(enemy_level=level)
    gated = []
    for bundles in catalog.bundles.values():
        for bundle in bundles:
            bosses = list(native_bundle_bosses(bundle))
            requirements = bundle.terrain_requirements
            if (bundle.portable and bundle.terrain_requirements is not None
                    and set(requirements.action_roots).issubset(
                        requirements.action_closure)
                    and not field_blocked(bundle.source_field)
                    and _pool_safe(bosses)):
                gated.append(bundle)
    safe_catalog = rbb.catalog_from_bundles(gated)
    if not safe_catalog.family_ids:
        raise RuntimeError(f"敌等级 {level} 没有通过完整门禁的原生 boss bundle")
    selected = rbb.choose_family_variant_bundle(
        safe_catalog, rng, policy=None).bundle
    if selected.source_field not in safe_catalog.eligible_source_fields:
        raise RuntimeError(
            f"无尽层 selector 返回了非 post-gate 场地:{selected.source_field}")
    return selected


def native_bundle_bosses(bundle: rbb.NativeBossBundle) -> tuple[str, ...]:
    """按 active slot 顺序返回单人侧实体代号，并保留真实重复实例。"""
    return tuple(slot.single.code for slot in bundle.slots
                 if slot.single is not None)


def native_bundle_field_index(catalog: rbb.BundleCatalog | None) \
        -> dict[str, rbb.NativeBossBundle]:
    """把 fresh catalog 的可用 bundle 按官方来源场地建成唯一索引。"""
    if catalog is None:
        return {}
    eligible = set(catalog.eligible_source_fields)
    out: dict[str, rbb.NativeBossBundle] = {}
    for bundles in catalog.discovered_bundles.values():
        for bundle in bundles:
            field = str(bundle.source_field)
            if field not in eligible:
                continue
            previous = out.get(field)
            if previous is not None and previous != bundle:
                raise RuntimeError(f"场地存在多个不一致的原生 bundle:{field}")
            out[field] = bundle
    return out


def checked_mix_terrain_compatibility(
        source_field: str, target_field: str,
        bundles_by_field: dict[str, rbb.NativeBossBundle], *,
        strict_transplant: bool,
        transplant_safe: set[str] | frozenset[str] | tuple[str, ...],
        ) -> rbb.CompatibilityResult:
    """正式 ``mix_pick`` 的 fail-closed 移植门禁。

    Boss 来源必须先完成 ActionDSL/ESDL 递归闭包分析，再把其中引用的
    ``p0/p1/p2``、Funnel 锚点及逐层 Boss 槽拓扑与目标地形逐项比较。
    仅有槽位数量相同或出现在旧 ``transplant_safe`` 名单中都不够。
    """
    source_field, target_field = str(source_field), str(target_field)
    source = bundles_by_field.get(source_field)
    target = bundles_by_field.get(target_field)
    if source is None or target is None:
        missing = []
        if source is None:
            missing.append(f"source={source_field}")
        if target is None:
            missing.append(f"target={target_field}")
        return rbb.CompatibilityResult(
            False, "BUNDLE_EVIDENCE_MISSING", ",".join(missing),
            source_field, target_field)
    if not source.portable or source.terrain_requirements is None:
        return rbb.CompatibilityResult(
            False, source.native_only_reason or "ACTION_CLOSURE_UNAUDITED",
            "Boss 来源缺可移植 ActionDSL/ESDL 闭包证明",
            source_field, target_field)
    return rbb.terrain_compatibility(
        source, target, source.terrain_requirements,
        strict_transplant=bool(strict_transplant),
        transplant_safe=transplant_safe)


def patch_quest_boss_fields(
        row: list[str], *, field: str, bosses, thumbnail: str | None,
        bgm: str | None, enemy_level: int, rng,
        play_field: str | None = None,
        field_elements: dict[str, int] | None = None,
        boss_elements: dict[str, int | None] | None = None,
        require_bgm: bool = False, require_thumbnail: bool = False,
        thumbnail_asset_exists=None) -> tuple[int, str]:
    """同步正式塔路径的 c5/c69/c95/c98/c99 boss 场地字段。"""
    if len(row) <= 99:
        raise ValueError(f"rush quest 行过短:{len(row)} < 100")
    source_field = str(field)
    target_field = str(play_field or source_field)
    if not source_field or not target_field:
        raise ValueError("无尽层 bundle 缺 field")
    level = int(enemy_level)
    if level <= 0:
        raise ValueError(f"无尽层敌等级非法:{enemy_level!r}")
    if require_bgm and bgm in (None, "", "(None)"):
        raise ValueError(f"无尽层 bundle 缺 BGM:{source_field}")
    if require_thumbnail and thumbnail in (None, "", "(None)"):
        raise ValueError(
            f"Boss 层缺已证明的 quest 大图:{source_field}; "
            "拒绝沿用模板旧封面")

    fields = field_official_elem_map() if field_elements is None else field_elements
    boss_map = boss_element_map() if boss_elements is None else boss_elements
    official = fields.get(source_field)
    fixed = next((boss_map[code] for code in bosses
                  if boss_map.get(code) is not None), None)
    if official is not None:
        element, tag = int(official), "(官方)"
    elif fixed is not None:
        element, tag = int(fixed), ""
    else:
        element, tag = int(rng.randrange(6)), "(随机)"
    if not 0 <= element < 6:
        raise ValueError(f"无尽层推荐元素非法:{element}")

    if thumbnail not in (None, "", "(None)"):
        thumbnail = str(thumbnail)
        asset_logical = quest_thumbnail_asset_logical(thumbnail)
        if (thumbnail_asset_exists is not None
                and not thumbnail_asset_exists(asset_logical)):
            raise ValueError(
                f"Boss 层封面资源不存在:{asset_logical} ({source_field})")
        row[5] = thumbnail
    row[69] = str(element)
    row[95] = str(level)
    row[98] = target_field
    if bgm not in (None, "", "(None)"):
        row[99] = str(bgm)
    return element, tag


def endless_bundle_publish_logicals(bundle: rbb.NativeBossBundle) -> tuple[str, ...]:
    """返回原生 bundle 与 quest 写回组成的 dependency-first 发布闭包。"""
    logicals: list[str] = []

    def add(logical: str | None) -> None:
        if logical and logical not in logicals:
            logicals.append(logical)

    add(bundle.terrain_logical)
    requirements = bundle.terrain_requirements
    if requirements is not None:
        for action in requirements.action_closure:
            add(action if action.endswith(".action.dsl.amf3.deflate")
                else action + ".action.dsl.amf3.deflate")

    kinds = {slot.single.kind for slot in bundle.slots
             if slot.single is not None}
    for kind in sorted(kinds):
        table_name = rbb.KIND_TABLES.get(kind)
        add(rbb.TABLE_LOGICALS.get(table_name))
    add(BOSS_LEVEL)
    add(GENERAL_ZAKO)
    add(ZAKO_LEVEL)

    spawned_kinds = {
        ref.source_kind
        for layer in (() if requirements is None else requirements.layers)
        for ref in layer.spawned_refs
    }
    has_funnels = bool(requirements and any(
        layer.funnels for layer in requirements.layers))
    if kinds & {1, 3, 8} or spawned_kinds & {"AlterEgo", "GeneralBoss"}:
        add(GENERAL_BOSS)
        add(GENERAL_BOSS_VARIABLE)
        add(GENERAL_BOSS_STATE)
        add(ENEMY_WATCH)
    if has_funnels or "Funnel" in spawned_kinds:
        add(GENERAL_FUNNEL)
    if "StandardFunnel" in spawned_kinds:
        add(STANDARD_FUNNEL)

    add(ZONE_T)
    add(FIELD_DATA_T)
    add(Q_QUEST)
    return tuple(logicals)


def _zone_pick(fdid: str) -> tuple[list[str], list[str]]:
    """field → 单人战实际 (boss codes, zako codes)，只读 terrain 激活层。

    boss 每实体槽是 `(single,multi)` 镜像对。塔是单人 event quest，客户端只读
    c24/c28/c32；即使 c26/c30/c34 写了不同代号也不能当成第二只实体。
    zone 中未被 terrain ``objectgroup.name`` 激活的 row 必须忽略；解析失败时
    fail closed 返回空，不回退到扫描整个 zone。数据列号使用 0-based。
    """
    fd = _tbl("master/battle/field_data.orderedmap")
    zone = _tbl("master/battle/zone.orderedmap")
    frow = fd.get(fdid)
    if not frow:
        return [], []
    try:
        caps = rbb.load_terrain_layer_caps(fdid, fd, zone, rbb.load_store_terrain)
        slots = rbb.active_boss_slots(fdid, fd, zone, rbb.load_store_terrain)
    except (FileNotFoundError, rbb.TerrainGateError):
        return [], []
    fc = cells(frow)
    zn = zone.get(fc[2])
    bosses = [slot.single.code for slot in slots if slot.single is not None]
    zakos: list[str] = []
    if isinstance(zn, dict):
        for cap in caps:
            wc = cells(zn[cap.layer])
            zakos.extend(wc[i] for i in range(2, min(22, len(wc)), 2)
                         if wc[i] not in ("(None)", ""))
    return bosses, zakos


# 难度分级:master/quest/quest_rank.orderedmap —— 难度由敌等级(c95)决定,
# quest 名里的 ::quest_rank:: 占位符由客户端按此表替换。
QUEST_RANKS = ((100, "地狱级"), (90, "超级+"), (80, "超级"),
               (70, "高级+"), (40, "高级"), (20, "中级"), (1, "初级"))

# 来源池难度下限(2026-07-29 用户需求「全部取最难的版本,超级最低」)。
# 80 = 超级;≥90 超级+;100 地狱级。只作用于副本来源池,塔池(崩坏域)的难度
# 由 --enemy-level / 轮次曲线另行决定,不受此门槛影响。
MIN_QUEST_LEVEL = 80
# 不吃难度门槛的来源池:主线 boss 是手挑名单,主线关卡的官方敌等级本来就低,
# 难度由 resolve_level 取 boss 最强档 + 轮次曲线决定,按官方档位刷会全军覆没。
NO_LEVEL_FLOOR = {"主线boss"}


def rank_of(level) -> str:
    """敌等级 → 难度名(客户端 ::quest_rank:: 的显示值)。"""
    try:
        value = int(level)
    except (TypeError, ValueError):
        return ""
    for floor, name in QUEST_RANKS:
        if value >= floor:
            return name
    return ""


# 敌等级列 = field 列 − 3。2026-07-29 全库实测:15 个有效 quest 类别 2903 行
# 100% 命中(boss_battle c109→c106、main c109→c106、advent c115→c112、
# hard_multi c110→c107、rush c98→c95、skill_preview c30→c27…)。
# 旧代码硬编码 cs[95],只对 rush schema 成立:领主战表 c95 是 HP 修正,
# 于是索拉斯场地被读成「lv1560 · 地狱级」。用相对列位替代按类别登记列表,
# 新 schema 也自动跟上。
def quest_level_of(cs: list[str], fidx: int) -> str:
    """quest 行 + field 所在列 → 敌等级字符串;越界/非 1-100 返回 ""。"""
    idx = fidx - 3
    if idx < 0 or idx >= len(cs):
        return ""
    val = str(cs[idx]).strip()
    return val if val.isdigit() and 1 <= int(val) <= 100 else ""


def quest_pool(cat: str, name_eq: str | None = None, require_boss: bool = True) -> list[dict]:
    """副本类别 → [{field,bosses,thumb,name,level,rank}](按 field 去重)。

    ⚠ 同一个 field 常有多行难度档,**取敌等级最高的那一行**(2026-07-29 用户需求
    「全部取最难的版本」)。分档有两种形态,这里都覆盖:
      ① 多 field 分档:`steampunk_fire_1..4`(中级/高级/高级+/超级)——尾号即档位;
      ② **单 field 多行分档**:`steampunk_another`(机工神兵菲诺梅那)一个场地
         挂 20/50/70/80/100 五行,难度只由行里的敌等级决定。
    旧代码按 field 首行去重,②型副本一律读成最低档 —— 菲诺梅那因此一直显示
    「lv20 中级」,实际有地狱级。
    """
    logical = next(x[2] for x in wb.QUEST_CATS if x[0] == cat)
    tree = wb._load(logical)
    fd_keys = set(_tbl("master/battle/field_data.orderedmap").keys())
    best: dict[str, tuple[int, dict]] = {}
    order: list[str] = []
    for _path, row in wb._leaves(tree):
        cs = row.split(",")
        name = next((x for x in cs[1:7] if x and wb._CJK.search(x)), "")
        name = name.replace("::quest_rank::", "").strip()
        if name_eq and name != name_eq:
            continue
        fidx = next((i for i, x in enumerate(cs) if x in fd_keys), None)
        if fidx is None:
            continue
        fdid = cs[fidx]
        bosses, zakos = _zone_pick(fdid)
        if require_boss and not bosses:
            continue
        thumb = next((x for x in cs if "/thumbnail/" in x), "")
        level = quest_level_of(cs, fidx)
        entry = {"field": fdid, "bosses": bosses, "zakos": zakos, "thumb": thumb,
                 "name": name.replace("::quest_rank::", rank_of(level)).strip(),
                 "level": level, "rank": rank_of(level), "cat": cat}
        lv = int(level) if level else 0
        if fdid not in best:
            order.append(fdid)
            best[fdid] = (lv, entry)
        elif lv > best[fdid][0]:
            best[fdid] = (lv, entry)
    entries = [best[f][1] for f in order]
    if BUILD_MODE in {"normal", "ex"}:
        entries = [entry for entry in entries if not abyss_modes.is_five_boss_source(
            entry["field"], entry.get("bosses", ()))]
    return entries


def zako_room_pool() -> list[dict]:
    """主线里的纯小怪房(zone 无 boss、有小怪)。"""
    out = []
    for entry in quest_pool("main", require_boss=False):
        if not entry["bosses"] and entry["zakos"]:
            out.append(entry)
    return out


# ---- 主线/EX 手挑名单(2026-07-29,从普查出的 47 个候选里选 22 个)----
# 取「真 boss」里★强烈建议+○建议;主动排除三类:
#   ① 16 个杂兵提拔族 —— 它们归第 2 战杂鱼层,进主池就是白给;
#   ② 5 个杂鱼感偏强的(红发老战士/五行·水善/人鱼老人/魔族男性/自动贩卖机);
#   ③ 诅咒弧魔艾基尔三形态 —— arch_evil 在 C8016 黑名单里,加了也会被门禁剔掉。
MAIN_STORY_BOSSES = (
    # 歼灭者全家的主线剧情版(advent 那 4 个另在降临池)
    "epuration_boss_single",             # 歼灭者
    "epuration_boss_another_single",     # 再战歼灭者
    "high_epuration_boss_single",        # 上位歼灭者个体
    "epuration_boss_variant_ver_single",  # 异形歼灭者(精灵/机械/龙)
    "epuration_boss_highest_main",       # 咒剑
    "epuration_boss_dragon_main",        # 吞噬星辰之物(⚠ 只有 80 档)
    # 龙
    "eye_dragon_boss", "eye_dragon_boss_ch12",   # 始龙之眼 / 祝星版
    # 其他真 boss
    "maou2",                    # 魔王
    "rec_android_boss_single",  # 雷克·雷吉斯塔
    "light_guardian_single",    # 精灵守护像
    "admin_human",              # 管理者(人型)
    "benzaiten",                # 形似弁天的魔物
    "guardian_totem_another",   # 诅咒图腾
    "devil_commander", "devil_commander_evil",   # 伊尔比斯 / 诅咒伊尔比斯
    "shiro",                    # 白虎兽人
    "wolf_assassin",            # 克劳斯
    # 联动「龙与言灵」
    "psychic_projection", "psychic_tomboygirl",
    "psychic_shouta", "psychic_shouta_sequel",
)


def boss_model(code: str) -> str:
    """boss 代号 → 模型族(资源路径里的族名);取不到返回 ""。

    两种路径形态都认:general_boss 的 `battle/boss/<族>/…`、
    standard_boss 的 `battle/enemy/boss/<族>…`。"""
    node = _tbl(GENERAL_BOSS).get(code) or _tbl(STANDARD_BOSS).get(code)
    leaves = list(node.values()) if isinstance(node, dict) else ([node] if node else [])
    for leaf in leaves:
        if isinstance(leaf, dict):
            continue
        text = leaf if isinstance(leaf, str) else leaf.decode("utf-8")
        for ln in text.split("\n"):
            for c in cells(ln):
                if "general_16dots" in c:
                    continue
                if c.startswith("battle/boss/"):
                    return c.split("/")[2]
                if c.startswith("battle/enemy/boss/"):
                    return c.split("/")[3]
        break
    return ""


# 「已有加强版」的来源池(2026-07-29 用户需求):追忆试炼/单人挑战、极时试炼
# 给的是同一个 boss 的 expert/EX 强化档,主线版留在池里只会白占一个位。
UPGRADED_SRC_CATS = ("expert_single", "solo_time_attack")


def main_story_boss_pool() -> list[dict]:
    """主线/EX 里手挑的 boss 层(名单见 MAIN_STORY_BOSSES)。

    同一个 field 在 `main_quest` 与 `ex_quest` 两张表都有,ex 是高难镜像
    (同场地敌等级更高)——两表合并后**按 field 取敌等级更高的一条**,
    自然落到 EX 版。⚠ 这个池不吃 MIN_QUEST_LEVEL 门槛:主线关卡的官方
    敌等级本来就低,难度由 resolve_level 取 boss 最强档 + 轮次曲线决定。

    **剔除在追忆试炼/极时试炼里已有加强版的 boss**:判据取「显示名 ∪ 模型族」——
    强化版换了攻击程序签名,`_family()` 那套去重认不出它俩是同一个角色
    (实测命中「管理者」:主线人型版 admin_human vs 追忆 administrator_light_expert)。
    """
    names = wb.boss_names()
    upgraded_names: set[str] = set()
    upgraded_models: set[str] = set()
    for cat in UPGRADED_SRC_CATS:
        for e in quest_pool(cat):
            for b in e["bosses"]:
                nm = str(names.get(b, "")).split("/")[0]
                if nm:
                    upgraded_names.add(nm)
                model = boss_model(b)
                if model:
                    upgraded_models.add(model)

    best: dict[str, dict] = {}
    for cat in ("main", "ex"):
        for e in quest_pool(cat):
            picked = [b for b in e["bosses"] if b in MAIN_STORY_BOSSES]
            if not picked:
                continue
            if any(str(names.get(b, "")).split("/")[0] in upgraded_names
                   or (boss_model(b) and boss_model(b) in upgraded_models)
                   for b in picked):
                continue
            lv = int(e["level"]) if str(e["level"]).isdigit() else 0
            cur = best.get(e["field"])
            cur_lv = int(cur["level"]) if cur and str(cur["level"]).isdigit() else -1
            if lv > cur_lv:
                best[e["field"]] = e
    return list(best.values())


def minion_boss_pool() -> list[dict]:
    """杂鱼 boss 层(2026-07-29 用户需求:第1战小怪房、**第2战打杂鱼 boss**)。

    = 主线里 zone boss **全部**命中杂兵提拔族判据的场地(is_minion_boss:真 boss
    从不出现在 general_zako,有同族前缀的即小怪提拔上来的)。比纯小怪房多一条
    boss 血条,又不至于第 2 战就上硬仗;这批 boss 也正是"最难版本"过滤会
    整体刷掉的那 16 个族,放在这里刚好各得其所。"""
    zk = set(q.load_table(GENERAL_ZAKO))
    out = []
    for entry in quest_pool("main"):
        bosses = entry["bosses"]
        if bosses and all(is_minion_boss(b, zk) for b in bosses):
            out.append(entry)
    return out


# ---- 深渊诅咒 v2(2026-07-19 用户需求:大胆增益减益,取代 v6 随机场地效果)----
# 可用旋钮(均有官方先例,零客户端改动):
#   battle_enemy_condition_1..5(c71-80):kind 0能力/1直击/2弹射/3技能=伤害耐性
#     (正=敌减伤,负=敌易伤,官方超3用过 -4),kind 4=敌方减益免疫;枚举仅此 5 种
#     (InitialEnemyCondition 反编译实锤,无隐藏项)。
#   c94 boss 韧性修正:官方 700007 无尽档用到 ×9。
#   c97 FEVER 槽上限:官方标准 400,无尽档 1000(越高 fever 越难攒)。
#   c100 战斗时限帧:官方恒 54000(15分),压低=倒计时压力。
# 诅咒 = 具名效果包,按 --curse 档位(standard/abyss/hell)取三档强度;
# 深度排程:≤15% 无 / ≤45% 1个 / ≤75% 2个 / >75% 2个(hell 3个)。
# 反编译实锤(InitialEnemyCondition.as):0=AbilityDamage 1=DirectAttackDamage
# 2=PowerFlipDamage(**强化弹射**,非普通球撞) 3=SkillDamage 4=Debuff。
# ⚠ 普通弹射(球接触伤害)没有对应免疫项,枚举里不存在 —— 标签必须写"强化弹射",
# 写成"弹射"会让人以为球撞也免疫(2026-07-28 用户实测反馈)。
COND_KIND_CN = {0: "能力", 1: "直击", 2: "强化弹射", 3: "技能"}
CURSE_TIERS = ("standard", "abyss", "hell")

# ---- 深渊法阵:官方场程序菜单(2026-07-19 全库扫描精选)----
# 施法载体=克隆 curse_eye 的"祭坛"zako,c30(enemy_action101)指向现成官方场程序,
# 塞进克隆 zone 的空 zako 槽。参数(数值/时长/目标)烤死在程序二进制里,只选不调。
# 预载安全实锤:resolver case 80(StartBuffField)/84(StartModifierField)/65(CreateFlood)
# 都有完整资产解析(buff_field 动画/field_text 动态字牌/boss_flood)。
FIELD_MENU = [
    ("圣蟹充能阵", "battle/action/enemy/action/boss_hermit_crab_another_light_ex/boss_hermit_crab_another_light_ex$skill_charge_field1", "充能加速领域", "加成"),
    ("连击法阵", "battle/action/enemy/action/boss_smr21_middle_boss/smr21_middle_boss$difficulity10_field_buf2", "连击加成领域", "加成"),
    ("封连领域", "battle/action/enemy/action/boss_haniwa_great_dark/boss_haniwa_great_dark$pf_field", "连击限制", "诅咒"),
    ("禁疗领域", "battle/action/enemy/action/boss_epuration_highest/boss_epuration_highest$field_debuff", "治疗禁止", "诅咒"),
    ("禁益领域", "battle/action/enemy/action/boss_chapter12_boss/boss_chapter12_boss$field_start1", "增益禁止", "诅咒"),
    ("血滑领域", "battle/action/enemy/action/boss_reine_rouge/boss_reine_rouge_form1$field_effect_expansion", "滑行损血", "诅咒"),
    ("深渊之水", "battle/action/enemy/action/boss_spirit_beast_water/boss_spirit_beast_water$drown_buf", "全场淹水", "场地"),
    ("元素统一场", "battle/action/enemy/action/boss_epuration_highest/boss_epuration_highest$element_field", "歼灭者元素场", "场地"),
    ("元素结界", "battle/action/enemy/action/boss_administrator_another_dark_ex/boss_administrator_another_dark_ex$field_pf", "元素耐性结界", "领域"),
    ("炎兽领域", "battle/action/enemy/action/boss_spirit_beast_fire/boss_spirit_beast_fire$spirit_beast_field_effect", "耐性+攻击领域", "领域"),
]

# 允许进**随机**法阵抽取的分类。
# 「环境」= CreateWindAttack / CreateGravitationalField 两个 2026-07-29 新放行的命令,
# 共 73 项。**真机实验已通过**(1.4.238 钉选第3战刮风/第4战重力,用户实测两层效果
# 都正常出现;第5战淹水=已验证对照组),据此放开随机池。
# 放行依据(三条都查过,不是只看那两个样本):
#   ① 73 项全是**单命令**(46 重力 + 27 刮风),零"复合"夹带;
#   ② **零资产路径参数** ⇒ 不存在"引用超出预载集合"的 C8016 路径;
#   ③ 重力的定位是**语义锚**(Top×76/Left×71/Center×36/Right×5)+ 相对偏移(±250/±420),
#      不是烤死的地形坐标 ⇒ 不踩 C14102 位移炸弹。
# ⚠ 真机只覆盖了 Center 锚(gravity_pf)与中段强度刮风(1,0.5,600);其余变体靠上面
#   三条结构判据外推。剩余风险是**观感**(重力井位置/刮风过强)而非崩溃。
# ⚠ CreateTornado 仍不放行:它带绝对坐标 + 外部特效路径,本次实验的结论**不迁移**
#   (刮风/重力没有资产引用,证明不了 resolver 会走 tornado 的字符串参数)。
FIELD_RANDOM_CATS = {"加成", "诅咒", "场地", "领域", "环境"}

_FIELD_MENU_ALL: list | None = None


def field_menu_all() -> list[tuple[str, str, str]]:
    """完整领域菜单 = 内置精选 + wf_field_catalog 全量净场目录(签名去重)。

    目录由 `python mod-tools/wf_field_catalog.py --write` 生成(131 程序/57 签名,
    AMF3 全解析);缺文件时回退内置 10 项。"""
    global _FIELD_MENU_ALL
    if _FIELD_MENU_ALL is None:
        menu = list(FIELD_MENU)
        try:
            cat = json.load(open(rogue_config_path("rogue_field_menu.json"),
                                 encoding="utf-8"))
            have = {m[1] for m in menu}
            for c in cat:
                if c.get("dup") or c["program"] in have:
                    continue
                menu.append((c["label"], c["program"], c["note"], c.get("cat", "领域")))
                have.add(c["program"])
        except Exception:
            pass
        _FIELD_MENU_ALL = menu
    return _FIELD_MENU_ALL


PLAN_TIERS = {"easy": ("off", 0.85), "normal": ("standard", 1.0),
              "elite": ("abyss", 1.0), "hell": ("hell", 1.15)}

# ---- 特殊 boss 原味保护名单(2026-07-26 用户需求)----
# rogue_special_bosses.json 的 authentic 名单:这些 boss 被随机抽中时**保持原场地
# 原机制**(mix 不拆解拼接),诅咒/等级修正照常叠加。general 系特殊 boss 的深渊法阵
# 仍可落(克隆自身追加程序=原样+机制);standard 系(菲诺梅那/终始之龙等)无 action
# 列可挂,法阵落不上(两条克隆路 2026-07-26 均已探明不通)。
SPECIAL_BOSSES_PATH = rogue_config_path("rogue_special_bosses.json")


def load_special_bosses() -> tuple[set[str], tuple[str, ...]]:
    """返回 (精确代号集, 前缀元组)。命中任一即原味保护。

    authentic_prefixes 用于整族保护(如 guardian_golem 全变体带突击位移,
    dark_matter 带变身位移——位移锚点烤在老家地形,异地拼接必 C14102)。"""
    try:
        data = json.load(open(SPECIAL_BOSSES_PATH, encoding="utf-8"))
        exact = set(map(str, data.get("authentic", [])))
        exact |= set(map(str, data.get("authentic_movement", [])))
        prefixes = tuple(map(str, data.get("authentic_prefixes", [])))
        # 插座族(嵌入场地的 boss:管理者/火力压制)双向危险:boss 出走=原味保护,
        # 老巢当拼接容器=地形侧排除(mix_pick 处理)
        prefixes += tuple(map(str, data.get("socket_families", [])))
        return exact, prefixes
    except Exception:
        return set(), ()


def load_high_threat_rules(
        path: str | os.PathLike[str] = SPECIAL_BOSSES_PATH
        ) -> tuple[tuple[str, ...], frozenset[str]]:
    """读取作者维护的高威胁前缀/精确代号；配置错误必须响亮失败。"""
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if "high_threat" not in data:
        raise ValueError(f"{path} 缺少 high_threat 键")
    raw = data["high_threat"]
    if not isinstance(raw, dict):
        raise TypeError("high_threat 必须是对象")
    for key in ("prefixes", "exact"):
        if key not in raw:
            raise ValueError(f"high_threat 缺少 {key} 键")
        if not isinstance(raw[key], list):
            raise TypeError(f"high_threat.{key} 必须是字符串数组")

    def clean(key: str) -> tuple[str, ...]:
        values: list[str] = []
        for index, value in enumerate(raw[key]):
            if not isinstance(value, str):
                raise TypeError(f"high_threat.{key}[{index}] 必须是字符串")
            value = value.strip()
            if not value:
                raise ValueError(f"high_threat.{key}[{index}] 不得为空字符串")
            if value not in values:
                values.append(value)
        return tuple(values)

    return clean("prefixes"), frozenset(clean("exact"))


def is_high_threat_bosses(bosses, prefixes: tuple[str, ...],
                          exact: frozenset[str]) -> bool:
    """HP 重排完成、mod clone 改名前，对实际 boss 代号匹配高威胁规则。"""
    return any(str(code) in exact
               or any(str(code).startswith(prefix) for prefix in prefixes)
               for code in bosses)


def prefer_non_threat_candidates(candidates: list, r: int | None, n: int,
                                 bosses_of, prefixes: tuple[str, ...],
                                 exact: frozenset[str]) -> list:
    """前 20% 楼层有普通合格项时回避高威胁；耗尽时保留原候选。"""
    if r is None or n <= 0 or r / n > 0.2:
        return candidates
    ordinary = [candidate for candidate in candidates
                if not is_high_threat_bosses(
                    bosses_of(candidate), prefixes, exact)]
    return ordinary or candidates


# ---- 精选 boss 加权(2026-07-29 用户需求:高价值 boss 出场率太低)----
# rogue_special_bosses.json 的 featured_bosses(前缀匹配,代号本身也是自己的前缀)
# + featured_weight(默认 4)。抽取时命中的候选按权重重复进候选表 = 权重 ×N,
# 不是硬钉:池子照常随机,只是天平往稀有 boss 倾斜。与全塔配额去重、
# prefer_fresh 历史降权叠加使用(先去重→再降权→最后加权)。
FEATURED_DEFAULT_WEIGHT = 4


def load_featured_bosses() -> tuple[tuple[str, ...], int]:
    """(精选前缀元组, 权重倍数);配置缺失返回空名单=不加权。"""
    try:
        data = json.load(open(SPECIAL_BOSSES_PATH, encoding="utf-8"))
        prefixes = tuple(map(str, data.get("featured_bosses", [])))
        weight = int(data.get("featured_weight", FEATURED_DEFAULT_WEIGHT))
        return prefixes, max(1, weight)
    except Exception:
        return (), FEATURED_DEFAULT_WEIGHT


def is_featured(bosses, prefixes: tuple[str, ...]) -> bool:
    return any(str(b).startswith(p) for p in prefixes for b in bosses)


def load_socket_families() -> tuple[str, ...]:
    try:
        data = json.load(open(SPECIAL_BOSSES_PATH, encoding="utf-8"))
        return tuple(map(str, data.get("socket_families", [])))
    except Exception:
        return ()


def load_transplant_policy() -> tuple[bool, set[str]]:
    """白名单制(2026-07-28 三崩后默认):True 时仅 transplant_safe 可被移植,其余原味。"""
    try:
        data = json.load(open(SPECIAL_BOSSES_PATH, encoding="utf-8"))
        return (bool(data.get("strict_transplant", True)),
                set(map(str, data.get("transplant_safe", []))))
    except Exception:
        return True, set()


def is_special_boss(code: str, special: tuple[set[str], tuple[str, ...]]) -> bool:
    exact, prefixes = special
    return code in exact or any(str(code).startswith(p) for p in prefixes)


# ---- boss 出场历史(2026-07-26 用户需求:出现过的 boss 降低再出现概率)----
# work/rogue_boss_history.json = 最近 3 座塔的 boss 名单;抽取时 80% 概率
# 优先从"最近两座塔没出过"的候选里挑,新面孔优先但不绝对禁止(池子小不至于枯竭)。
BOSS_HISTORY_PATH = configured_path("rogue_boss_history") or Path(MOD_DIR) / "work" / "rogue_boss_history.json"


def load_boss_history() -> list[list[str]]:
    try:
        data = json.load(open(BOSS_HISTORY_PATH, encoding="utf-8"))
        return [list(map(str, tower)) for tower in data.get("recent", [])][:3]
    except Exception:
        return []


def save_boss_history(bosses: list[str]) -> None:
    recent = [sorted(set(bosses))] + load_boss_history()
    os.makedirs(os.path.dirname(BOSS_HISTORY_PATH), exist_ok=True)
    with open(BOSS_HISTORY_PATH, "w", encoding="utf-8") as fh:
        json.dump({"recent": recent[:3]}, fh, ensure_ascii=False, indent=1)


# ---- 全塔难度预设(2026-07-26 用户需求:任意层数 + 三种难度类型)----
# 成长曲线改端点式:起点/终点倍率固定,growth = (end/start)^(1/(n-1)) 按层数自适应,
# 8 层和 33 层都是同样的起终点难度,不会指数爆炸。tier=None(gradient)= 按深度
# off→standard→abyss→hell 四段递进。
# 2026-07-29 起点上调(用户真机反馈:玛格诺斯/泽古拉/元素球「都太弱」):
# 端点式曲线的**起点**决定前中段体感,原 gradient 起点 0.4 让第 9 战只有 hp×1.44。
# 只抬起点+略抬终点,曲线形状不变(层数自适应仍成立)。
# 对照(30 层 gradient):第9战 hp 1.44→2.62、第15战 2.9→5.2、末战 25→30。
# ⚠ **atk 端点已按官方参照带压回**(2026-07-29,用户「不要太高或者太低」)。
# 反编译列位实锤(`弹国服/scripts/pinball/master/generated/*QuestValues.as`:
# field 列 f 起算 f-10=hp_boss、f-7=atk_boss、f-3=enemy_level,20 张表一致)后统计
# **官方 3393 行**:
#   · lv100 的 atk_boss —— 中位 **1.0**、p90 1.215、**max 6.63**(全库唯一离群点,第二名 1.8)
#   · **全库没有任何一行 atk 修正 > 10**
#   · 官方**不靠 quest HP 修正抬难度**；rush 110 个 c86 样本全是 1.0，
#     真血量来自 boss_level / standard 战斗资源，而不是 quest c86
# 旧值 atk 终点 18.0 配上玻璃深渊 ×3.0 与 PLAN_TIERS ×1.15,末层写进 c89-91 的倍率
# 达 **62.1**,实测线上塔 atk 中位 8.92 / 最高 80.09,**比官方天花板高一个数量级**。
# 新端点把典型攻击值拉回官方带内；旧 HP 端点现只保留难度同比缩放/热身代理，
# general boss 的最终真血量由绝对 DPS 目标反解进 clone boss_level.c2。
# ⚠ **hp 端点同样压回**(用户指定参照:无幻之宴 / 机工神兵菲诺梅那)。
# 查官方原值 —— 这两个在 lv100 的修正是 **全 1.0**(菲诺梅那在降临讨伐甚至 0.7),
# 难度完全来自 enemy_level=100 + 它们自带的数值。而我们这座塔给**同一场战斗**写的是
# 菲诺梅那 hp 22.28/atk 4.64、无幻之宴 hp 40.02/atk 16.29 —— 把官方战斗做成了 40 倍血。
# 这两个都是 standard 系(无 boss_level 基数、**不参与归一**),拿到的就是裸曲线值,
# 所以曲线端点本身必须压。
# 新口径:**×1.0 ≈ 无幻之宴/菲诺梅那 那一档**,曲线只负责深度推进(首层 0.6× → 末层 3×);
# boss 之间的强弱差由归一化补偿承担,不再靠曲线堆。
# ⚠ **2026-07-30 二次压回:刀→血**(玩家「连战 boss 伤害过高」审计)。
# 上一轮把 atk 终点从 18.0 压到 2.5 之后,实测中后段 col 中位仍有 4.03 —— 因为
# 终点只管曲线,真正落表的是 曲线×来源补偿×归一化×**攻击诅咒**。烈狱档 16/30 层
# 带攻击诅咒且顶格,叠在塔尾自身已达 2.4-3.3 的曲线上。
# 端点扫描(3 seed × 5 档,scratchpad/sweep_endpoint.py):atk 终点 2.5 时分位闸要
# 出手 20 次、把中后段攻击诅咒**全部摘光**才进带;终点 1.7 时只出手 6 次(多为降档
# 而非摘除),中后段仍有 6/20 层保留攻击诅咒 —— 闸门回到"兜底"而不是"主力"。
# atk **起点不动**(0.8):玩家反馈「前10关都不算强」,前段本就不该再削。
# 2026-08-05 真机裁定覆盖旧“放大 c86”方案：官方 rush c86 无 >1 先例，
# general 血量主伸缩必须改写克隆 boss_level.c2，quest c86 固定 1.0。
DIFF_PRESETS = {
    #            hp起  hp终   atk起 atk终  诅咒档
    "easy":     (0.3,  1.2,   0.3,  0.9,  "off"),
    "normal":   (0.5,  2.2,   0.5,  1.3,  "abyss"),
    "hell":     (0.9,  4.0,   1.1,  1.1,  "hell"),
    "gradient": (0.5,  2.6,   0.6,  1.5,  None),
}

# ---- atk 落表值的**显式构建期硬闸**(2026-08-05 定档)----
# solve_atk 只报告真实乘积；enforce_atk_band 先降攻击诅咒，再降低该层 ba，
# 每次变更后完整重算并写日志。以下兼容常量统一表达最终 c89/c91 硬上限。
ATK_MULT_CEILING = 1.5
ATK_COMBO_CAP = 1.5
NOBASE_ATK_CAP = 1.5
# 真伤指数 = boss 原生 atk(该层等级)× 落表 col ÷ 同曲线组中位锚。
# col 合规 ≠ 真伤合规:第6战青之女王 col 只有 1.90,但原生 atk ≈ 中位 3 倍,
# 0.55 幂压缩没压平 → 真伤指数 5.62 = 全塔第一(隐形尖峰)。这条直接封每跳伤害。
TRUE_DMG_CAP = 4.0
# 带 funnel 的层:炮台弹幕同吃 boss 列倍率(第18战巫妖 4.68/第29战深渊之云 4.81),
# 玩家会把它算进"boss 伤害"。c90 相对 c91 降档。
FUNNEL_ATK_SCALE = 0.6
# 报告仍保留前/中后段切片；实际分位硬闸与 max=1.5 覆盖全塔。
BAND_FROM = 1 / 3
BAND_TARGET = {"median": 1.1, "p90": 1.35, "max": 1.5}
# 敌等级爬坡三段(--enemy-level ramp,默认)。官方 enemy_level 分布:lv80 是主流
# 难档(662 行 21.9%),lv100 只有 127 行(4.2%);atk_correction_curve 实解
# lv79=1.898 / lv89=1.992 / lv99=2.505 / lv100=3.267 —— lv100 是曲线悬崖顶,
# 全塔平坦 lv100 等于把 96% 官方内容不敢站的位置站满 30 层。
LEVEL_RAMP = (80, 90, 100)

# 2026-08-25 用户定档：默认 Hell 的 29 个 Boss 关按“诅咒前整关总 HP”线性
# 递增，第 2 战 30 亿、第 30 战 150 亿。多阶段适配器再按实际胜利血条的原生
# 占比分配；血量诅咒只乘最终目标，不能混回这条基础曲线。
#
# target_dps 仍是内部选择/时限门禁的统一坐标，按默认 900 秒从 HP 换算；实际
# 落表始终使用 target_dps × 该层模板原始时限，因此审计同时保留基础总 HP 与
# 诅咒后最终总 HP。旧 60 万→2500 万几何 DPS 线只由显式 --ramp 恢复。
TARGET_BASE_DURATION_S = 900.0
HELL_BOSS_HP_FIRST = 3_000_000_000.0
HELL_BOSS_HP_LAST = 15_000_000_000.0
TARGET_DPS_FIRST = HELL_BOSS_HP_FIRST / TARGET_BASE_DURATION_S
TARGET_DPS_LAST = HELL_BOSS_HP_LAST / TARGET_BASE_DURATION_S
_TARGET_DPS_BAND_RATIOS = (
    21_940_625.0 / 25_000_000.0,
    30_716_875.0 / 25_000_000.0,
)
TARGET_DPS_LAST_BAND = tuple(
    TARGET_DPS_LAST * ratio for ratio in _TARGET_DPS_BAND_RATIOS)
RAMP_TARGET_DPS_FIRST = 600_000.0
RAMP_TARGET_DPS_LAST = 25_000_000.0
RAMP_TARGET_DPS_LAST_BAND = (21_940_625.0, 30_716_875.0)
WARMUP_TARGET_DPS = 600_000.0
MAX_DPS_DOWN_JITTER = 0.15
STANDARD_C86_LIMITS = (0.9, 1.1)

# 30 层塔 r26~30 的深层硬锚。r25 回到常规候选池。
# 计分鲨鱼没有传伤链，禁止作为击杀目标；保留 eye 与妄羊1~4。
# 领域与 HP 通道仍由主流程逐层复核，候选不足时不可绕过安全门禁。
DEEP_HP_ANCHOR_FIELDS_30 = (
    "eye_dragon_multibattle",
    "raid_alter_sheep_materia1",
    "raid_alter_sheep_materia2",
    "raid_alter_sheep_materia3",
    "raid_alter_sheep_materia4",
)

# r16~24 的领域/血量联合锚。九层均经正式来源表、单人 zone、等级 ramp、
# general/standard 原生 HP 解析链和 caster_carrier_block 逐项复核；所需 c86
# 为 12.43~18.55，落在用户裁定的中段官方窗口 0.1~30。它们的实际 general_boss
# c36=true，因此普通领域可挂、属性免疫会由现有 c36 门禁拒绝并重抽。
MID_HP_ANCHOR_FIELDS_30 = (
    "multi_normal_1_10_4",
    "multi_normal_1_3_3",
    "raid_yokai_emaki_middle_boss",
    "multi_normal_1_6_4",
    "yokai_emaki_01_big_boss_multi",
    "big_boss_anv1_multi",
    "advent_z_collabo",
    "desert_bonds_big_boss_multi_ex",
    "summer_2020_boss_multi",
)

# 早段动态重排的保底候选。它们不是固定排程：正常随机结果只要原生 HP 能让
# 基线 c86 命中窗口就原样保留；只有异构池抽到过薄/过厚 boss 时，才与正式来源池
# 一起参与候补。此清单保证 r2~15 至少存在一组已复算可行解，避免算法因某次池变动
# 无候选而靠放宽窗口蒙混过关。
EARLY_HP_FALLBACK_FIELDS_30 = (
    "solo_time_attack_green1",
    "halfanv3",
    "anv3",
    "haniwa_carnival_dark_direct",
    "multi_normal_1_19_4",
    "haniwa_carnival_dark",
    "anv3_hell",
    "advent_spirit_beast_thunder_4",
    "mechanic_dragon_eater_multi_80",
    "advent_r_collabo",
    "advent_xm22",
    "haniwa_carnival_dark_pf",
    "advent_s_collabo1",
    "steampunk_another",
)
