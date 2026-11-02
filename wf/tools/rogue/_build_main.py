# Source section of rogue_build; loaded in its shared module namespace.
def main(argv=None, *, candidate_sink=None, forge_candidate=None) -> int:
    global BUILD_MODE, PRIVATE_PREFIX, EVENT_ID, EVENT_STRING_ID, EVENT_NAME
    global HELL_BOSS_HP_FIRST, HELL_BOSS_HP_LAST
    global TARGET_DPS_FIRST, TARGET_DPS_LAST, TARGET_DPS_LAST_BAND
    ap = argparse.ArgumentParser(description="生成 700099 深渊连战")
    ap.add_argument("--mode", choices=("legacy", "normal", "ex"), default="legacy",
                    help="normal=拆分后的普通塔，20～100亿且排除五重；legacy=历史构建兼容")
    ap.add_argument("--details-ui", action="store_true", default=None,
                    help="首次为 cn.ui.AbyssDetails 客户端开启详情；已开启的塔会自动沿用")
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--seed", type=int, default=int(date.today().strftime("%Y%m%d")))
    ap.add_argument("--difficulty", choices=tuple(DIFF_PRESETS), default="hell",
                    help="全塔难度预设(**默认 hell=全塔烈狱**,2026-07-29 用户主推):"
                         "easy=全简单 / normal / hell=全炼狱 / gradient=从简单到难;"
                         "接管成长曲线(端点式,层数自适应)与诅咒档,"
                         "显式 --hp-*/--atk-*/--curse 可单项覆盖")
    ap.add_argument("--ramp", action="store_true",
                    help="显式恢复旧 DPS 几何爬坡(60万→2500万)。默认关闭，"
                         "默认 Hell 为 Boss关诅咒前总HP线性30亿→150亿；"
                         "此开关与 --enemy-level ramp 的敌等级爬坡无关。")
    ap.add_argument("--strict-target-hp", action="store_true",
                    help="严格目标 HP：每个 Boss 关必须使用绝对证据、实际落表并按"
                         "客户端公式回读命中目标；代理/未归一/target_exempt 候选"
                         "会重抽，安全候选耗尽则明确失败。")
    ap.add_argument("--no-normalize", dest="normalize", action="store_false",
                    help="关闭旧基数归一(现主要影响 ATK)。Task C 的 boss HP"
                         "已改为 general/standard 真 HP 直接反解，不再依赖旧 HP 代理。")
    ap.add_argument("--normalize-hp", type=float, default=1.0,
                    help="旧 HP 分组归一指数(仅保留 raw/诊断兼容)；Task C boss"
                         "层由绝对 HP 目标取代，默认 1.0。")
    ap.add_argument("--normalize-atk", type=float, default=0.55,
                    help="伤害归一**压缩指数**(默认 0.55=只压一半,保留「高低有别」)。"
                         "残余跨度≈原极差^(1-指数);全池 atk 极差 86× → 约 6×")
    ap.add_argument("--normalize-min", type=float, default=0.1,
                    help="归一补偿下限(默认 0.1×)。实测线上塔层间真实血量极差:不归一 80× / 0.25–4 → 8× / **0.1–10 → 3×** / 0.05–20 → 2×")
    ap.add_argument("--normalize-max", type=float, default=100.0,
                    help="旧 HP raw 归一上限(任务 C 依规格放开到 100×)；"
                         "仅保留选池诊断兼容，general 最终改缩 boss_level.c2。")
    ap.add_argument("--normalize-atk-max", type=float, default=10.0,
                    help="攻击归一补偿上限(默认仍为 10×，不随 HP 窗口放大)")
    ap.add_argument("--hp-base", type=float, default=None)
    ap.add_argument("--hp-growth", type=float, default=None)
    ap.add_argument("--atk-base", type=float, default=None)
    ap.add_argument("--atk-growth", type=float, default=None)
    ap.add_argument("--enemy-level", default="ramp",
                    help="敌等级:ramp=按深度爬坡(**默认**,前1/3 lv80→中段 lv90→"
                         "尾段 lv100,见 LEVEL_RAMP)/ 数字(如 90)/ "
                         "max=每层取该 boss 数据里的最高档。"
                         "⚠ 官方 96%% 内容停在 lv80 以下,lv100 是曲线悬崖顶"
                         "(atk_single lv99→100 单档 ×1.30、lv80→100 ×1.72),"
                         "全塔平坦 lv100 = 每层都站在悬崖上")
    ap.add_argument("--curse", choices=("off",) + CURSE_TIERS, default=None,
                    help="深渊诅咒档位(默认随 --difficulty;无预设时 abyss;off=关闭)")
    ap.add_argument("--mix", action="store_true",
                    help="模块化拼接:塔楼层的地形与 boss 独立随机组合(克隆 zone 换 boss 槽,"
                         "元素跟 boss 老家楼层走),领域/诅咒照常叠加。"
                         "若安全白名单+HP窗口令实际拼接为0层，构建明确失败。")
    ap.add_argument("--test-field", type=int, default=0, metavar="R",
                    help="强制第 R 轮附加「深渊法阵」(真机验证用)")
    ap.add_argument("--dump-immunity-dsl", action="store_true",
                    help="dry-run 同时打印本轮生成的属性/伤害耐性 DSL 树(构造自查)")
    ap.add_argument("--audit-json", metavar="FILE",
                    help="严格 dry-run/构建通过后写机器可复核的 HP 验收回执；"
                         "FILE=- 时输出到 stdout")
    ap.add_argument("--audit-report", metavar="FILE",
                    help="把已通过严格复核的回执渲染为中文 Markdown 验收报告；"
                         "可与 --audit-json 构建或 --verify-audit-json 复核一起使用")
    ap.add_argument("--verify-audit-json", metavar="FILE",
                    help="只读复核已有 HP 验收回执，不加载/修改游戏表")
    ap.add_argument("--ignore-plan", action="store_true",
                    help="忽略连战工坊布局计划(rogue_layout_plan.json)")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="只校验解析链不生成:逐关检查 quest c98→field→zone→boss/zako")
    ap.add_argument("--check-event", default=EVENT_ID, metavar="ID",
                    help="--check 的事件 id(默认 700099)")
    ap.add_argument("--check-quest-path", metavar="FILE",
                    help="--check 用指定 quest 表文件(如 .bak 备份)代替 store 现状")
    args = ap.parse_args(argv)
    if candidate_sink is not None and (args.write or args.publish or args.check):
        raise ValueError("candidate compilation cannot write, publish or check external stores")
    BUILD_MODE = args.mode
    if BUILD_MODE == "ex":
        if args.rounds != 30 or args.ramp or args.hp_base is not None or args.hp_growth is not None:
            ap.error("EX requires 30 floors and the fixed tier HP budgets")
        PRIVATE_PREFIX = "mod_abyss_ex_"
        EVENT_ID, EVENT_STRING_ID, EVENT_NAME = "700100", "mod_abyss_ex_gauntlet", "深渊连战 EX"
        args.strict_target_hp = True
        HELL_BOSS_HP_FIRST, HELL_BOSS_HP_LAST = abyss_modes.base_hp("ex", 1), abyss_modes.base_hp("ex", 30)
        TARGET_DPS_FIRST, TARGET_DPS_LAST = HELL_BOSS_HP_FIRST / TARGET_BASE_DURATION_S, HELL_BOSS_HP_LAST / TARGET_BASE_DURATION_S
        TARGET_DPS_LAST_BAND = tuple(TARGET_DPS_LAST * ratio for ratio in _TARGET_DPS_BAND_RATIOS)
    if BUILD_MODE == "normal":
        if args.rounds != 30 or args.ramp or args.hp_base is not None or args.hp_growth is not None:
            ap.error("normal 要求 --rounds 30，不允许用旧 HP 参数覆盖确定的普通版曲线")
        HELL_BOSS_HP_FIRST, HELL_BOSS_HP_LAST = 2_000_000_000.0, 10_000_000_000.0
        TARGET_DPS_FIRST = HELL_BOSS_HP_FIRST / TARGET_BASE_DURATION_S
        TARGET_DPS_LAST = HELL_BOSS_HP_LAST / TARGET_BASE_DURATION_S
        TARGET_DPS_LAST_BAND = tuple(TARGET_DPS_LAST * ratio for ratio in _TARGET_DPS_BAND_RATIOS)
    if args.verify_audit_json:
        if args.audit_json or args.write or args.publish or args.check:
            print("[ERR] --verify-audit-json 不能与构建/写入/发布/解析链模式混用")
            return 1
        if (args.audit_report and args.audit_report != "-"
                and Path(args.verify_audit_json).expanduser().resolve()
                == Path(args.audit_report).expanduser().resolve()):
            print("[ERR] --audit-report 不得覆盖正在复核的 JSON 回执")
            return 1
        try:
            with open(args.verify_audit_json, encoding="utf-8") as fh:
                audit_document = json.load(fh)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            print(f"[ERR] HP 验收回执读取失败:{exc}")
            return 1
        current_tool_hash = tool_source_sha256()
        audit_errors = verify_hp_audit_document(
            audit_document, expected_tool_sha256=current_tool_hash)
        if audit_errors:
            for error in audit_errors:
                print(f"[ERR] HP 验收回执:{error}")
            return 1
        if args.audit_report:
            try:
                write_hp_audit_report(
                    args.audit_report, audit_document,
                    expected_tool_sha256=current_tool_hash)
            except (OSError, TypeError, ValueError) as exc:
                print(f"[ERR] HP 中文验收报告生成失败:{exc}")
                return 1
            print(f"[REPORT] HP 中文验收报告已生成:{args.audit_report}")
        summary = audit_document["summary"]
        source_proxy_components = summary.get(
            "source_proxy_components", summary["proxy_components"])
        print("[OK] HP 验收回执独立复核通过:"
              f"Boss关 {summary['audited_boss_rounds']}/"
              f"{summary['expected_boss_rounds']}，"
              f"最终代理组件 {summary['proxy_components']}，"
              f"源代理组件 {source_proxy_components}，"
              f"解析链失败 {summary['chain_failures']}，"
              f"最大绝对误差 {summary['max_absolute_error_hp']:g} HP")
        return 0
    server_root = str(core.resolve_server_dir()) if args.write else None

    if (args.audit_json or args.audit_report) and not args.strict_target_hp:
        print("[ERR] --audit-json/--audit-report 只接受 --strict-target-hp 构建，"
              "避免把宽松结果包装成严格验收回执")
        return 1
    if args.audit_json and args.audit_report:
        if (args.audit_json == args.audit_report
                or (args.audit_json != "-" and args.audit_report != "-"
                    and Path(args.audit_json).expanduser().resolve()
                    == Path(args.audit_report).expanduser().resolve())):
            print("[ERR] --audit-json 与 --audit-report 不得写到同一路径")
            return 1

    if args.normalize and (args.normalize_min <= 0
                           or args.normalize_max < args.normalize_min
                           or args.normalize_atk_max < args.normalize_min):
        print("[ERR] normalize 窗口必须为正，且两个上限都不得小于 --normalize-min")
        return 1

    if args.check:
        src_disp = args.check_quest_path or "store 现状"
        print(f"[CHECK] rush_event_quest[{args.check_event}] 解析链({src_disp}):")
        reports = validate_event_chain(
            args.check_event,
            quest_path=Path(args.check_quest_path) if args.check_quest_path else None)
        bad = print_chain_reports(reports)
        if bad:
            print(f"[ERR] {bad}/{len(reports)} 关引用悬空(进本必崩)")
            return 1
        print(f"[OK] 全部 {len(reports)} 关解析链完整")
        return 0

    # 敌等级:max = 逐层取该 boss 支持的最高档;ramp = 按深度爬坡(默认)
    _lvarg = str(args.enemy_level).strip().lower()
    want_max = _lvarg in ("max", "最强", "-1")
    want_ramp = _lvarg in ("ramp", "爬坡")
    # 素材池门禁仍按最高档试算(resolve_level 找不到可行档才判悬空),爬坡是**逐层**的
    args.enemy_level = 100 if (want_max or want_ramp) else int(args.enemy_level)

    def want_level(r: int) -> int:
        """该层的目标敌等级。resolve_level 再按 boss 实际支持的档位就近落。"""
        if not want_ramp:
            return args.enemy_level
        d = r / max(1, args.rounds)
        return LEVEL_RAMP[0] if d <= 1 / 3 else (LEVEL_RAMP[1] if d <= 2 / 3
                                                 else LEVEL_RAMP[2])

    rng = random.Random(args.seed)

    # ---- 难度预设解析:显式 CLI 参数 > 预设 > 旧默认(向后兼容) ----
    if args.difficulty:
        hp0, hpg, atk0, atkg = difficulty_curve(args.difficulty, args.rounds)
    else:
        hp0, hpg, atk0, atkg = 0.6, 1.2, 0.4, 1.145
    hp_base = args.hp_base if args.hp_base is not None else hp0
    hp_growth = args.hp_growth if args.hp_growth is not None else hpg
    atk_base = args.atk_base if args.atk_base is not None else atk0
    atk_growth = args.atk_growth if args.atk_growth is not None else atkg

    def round_tier(r: int) -> str:
        if args.curse:
            return args.curse
        if args.difficulty:
            return tier_for_round(args.difficulty, r, args.rounds)
        return "abyss"

    # ---- 战场链表载入(引用完整性门禁 + 后文克隆注入共用同一份内存态)----
    fd_t = q.load_table(FIELD_DATA_T)
    zone_t = q.load_table(ZONE_T)
    gz_t = q.load_table(GENERAL_ZAKO)
    zl_t = q.load_table(ZAKO_LEVEL)
    gb_t = q.load_table(GENERAL_BOSS)
    bl_t = q.load_table(BOSS_LEVEL)
    gv_t = q.load_table(GENERAL_BOSS_VARIABLE)
    gbs_t = q.load_table(GENERAL_BOSS_STATE)
    oro_t = q.load_table(OROCHI)
    oro_ex_t = q.load_table(OROCHI_EX)
    oro_ex_head_t = q.load_table(OROCHI_EX_HEAD)
    single_bar_special_tables = {
        family: q.load_table(str(spec["logical"]))
        for family, spec in SINGLE_BAR_SPECIAL_SPECS.items()
    }
    sphere_tables = {
        family: q.load_table(str(spec["logical"]))
        for family, spec in SPHERE_SPECS.items()
    }
    try:
        sphere_aux_tables = {
            name: q.load_table(logical)
            for name, logical in SPHERE_AUX_LOGICALS.items()
        }
    except Exception as _sphere_dependency_error:
        sphere_aux_tables = {}
        print("[WARN] Sphere 子单位依赖表不可用，严格模式将明确排除:"
              f"{_sphere_dependency_error}")
    try:
        kraken_tentacle_t = q.load_table(KRAKEN_TENTACLE)
        kraken_funnel_level_t = q.load_table(KRAKEN_FUNNEL_LEVEL)
    except Exception as _kraken_dependency_error:
        kraken_tentacle_t = {}
        kraken_funnel_level_t = {}
        print("[WARN] Kraken 触手依赖表不可用，严格模式将明确排除:"
              f"{_kraken_dependency_error}")
    # general_enemy_watch:法阵载体克隆要连它的 **self 侧**条目一起复制,否则
    # 「我 watch 别人」那套联动(如旋风巨土俑「buff 炮台死光→换阶段」)随改名一起丢。
    # 表的顶层键是**实体种类**(1=general boss / 2=funnel / 3=breakable block,
    # 对应客户端 GeneralBossSource:92 / FunnelSource:86 / BreakableBlockSource:76),
    # **不是** GeneralEnemyWatchKind 那个 9 值枚举——那个在叶子行的列里,与这层无关。
    # 读不到 / 读出空表 → ew_t=None,degraded 生效,本轮一律不发法阵。
    # ⚠ 空表必须当读不到:否则下面 save() 会把一张空表写回 store 并上链,
    #   等于把官方 163 个 watch 条目整个抹掉。
    try:
        ew_t = q.load_table(ENEMY_WATCH) or None
    except Exception as _e:
        ew_t = None
        print(f"[WARN] general_enemy_watch 读不到({_e})")
    if ew_t is None:
        print("[WARN] general_enemy_watch 不可用;本轮一律不发深渊法阵")
    sb_t = q.load_table(STANDARD_BOSS)
    # 换 boss 代号时同步校正 zone 的 BossKind 列(gb_t 含构建中的克隆,必须
    # 在 gb_t/sb_t 都就位之后再建)。
    kind_fixer = zone_boss_kind_fixer(gb_t, sb_t)
    stale = ([k for k in fd_t if str(k).startswith(f"{PRIVATE_PREFIX}f")]
             + [k for k in zone_t if str(k).startswith(f"{PRIVATE_PREFIX}z")])
    stale_c = ([k for k in gz_t if str(k).startswith(f"{PRIVATE_PREFIX}caster")]
               + [k for k in zl_t if str(k).startswith(f"{PRIVATE_PREFIX}caster")]
               + [k for k in gb_t if str(k).startswith(f"{PRIVATE_PREFIX}boss")]
               + [k for k in bl_t if str(k).startswith(f"{PRIVATE_PREFIX}boss")]
               + [k for k in gv_t if str(k).startswith(f"{PRIVATE_PREFIX}boss")]
               + ([k for k in (ew_t or {}).get("1", {})
                   if str(k).startswith(f"{PRIVATE_PREFIX}boss")] if ew_t else []))
    stale_s = [k for k in sb_t if str(k).startswith(f"{PRIVATE_PREFIX}standard")]
    stale_states = [
        key for key in gbs_t
        if str(key).startswith(f"{PRIVATE_PREFIX}boss")]
    stale_watch_aliases = purge_enemy_watch_partner_aliases(ew_t, prefix=f"{PRIVATE_PREFIX}boss")
    for k in stale:
        fd_t.pop(k, None)
        zone_t.pop(k, None)
    for k in stale_c:
        gz_t.pop(k, None)
        zl_t.pop(k, None)
        gb_t.pop(k, None)
        bl_t.pop(k, None)
        gv_t.pop(k, None)
        if ew_t is not None:
            ew_t.get("1", {}).pop(k, None)
    for k in stale_s:
        sb_t.pop(k, None)
    for key in stale_states:
        gbs_t.pop(key, None)
    orochi_purged_tables = purge_orochi_clones({
        "orochi": oro_t,
        "general_boss": gb_t,
        "general_boss_variable": gv_t,
        "boss_level": bl_t,
        "general_enemy_watch": ew_t,
    })
    orochi_ex_purged_tables = purge_orochi_ex_clones({
        "orochi_ex": oro_ex_t,
        "orochi_ex_head": oro_ex_head_t,
        "boss_level": bl_t,
    })
    single_bar_special_stale_families = {
        family for family in SINGLE_BAR_SPECIAL_SPECS
        if (any(re.fullmatch(rf"{PRIVATE_PREFIX}{re.escape(family)}\d+", str(key))
                for key in single_bar_special_tables[family])
            or any(re.fullmatch(rf"{PRIVATE_PREFIX}{re.escape(family)}\d+", str(key))
                   for key in bl_t))
    }
    purge_single_bar_special_clones({
        **single_bar_special_tables,
        "boss_level": bl_t,
    })
    sphere_stale_families = {
        family for family in SPHERE_SPECS
        if (any(re.fullmatch(rf"{PRIVATE_PREFIX}{re.escape(family)}\d+", str(key))
                for key in sphere_tables[family])
            or any(re.fullmatch(
                       rf"{PRIVATE_PREFIX}{re.escape(family)}\d+"
                       rf"(?:_g\d+c\d+)?", str(key))
                   for key in bl_t))
    }
    purge_sphere_clones({
        **sphere_tables, **sphere_aux_tables, "boss_level": bl_t})
    gim_dirty = bool(stale)
    caster_dirty = bool(stale_c or stale_watch_aliases)
    general_state_dirty = bool(stale_states)
    standard_dirty = bool(stale_s)
    standard_resource_blobs: dict[str, bytes] = {}
    # Task 5 will also set this after a successful per-round clone.  Purge-only
    # runs are dirty too: otherwise old parent/head keys survive in store.
    orochi_dirty = bool(orochi_purged_tables)
    orochi_ex_dirty = bool(orochi_ex_purged_tables)
    single_bar_special_dirty = set(single_bar_special_stale_families)
    sphere_dirty = set(sphere_stale_families)

    # Build Boss-cover evidence before any source pool.  A floor-host image is
    # useful diagnostic metadata but cannot advertise an unrelated Boss; such
    # fields must be excluded while candidates are still replaceable, not
    # allowed to fail late while patching rush quest c5.
    thumbnail_evidence_map = field_thumbnail_evidence_map(
        field_data=fd_t, zone=zone_t)
    verified_cover_fields = {
        field_id for field_id, evidence in thumbnail_evidence_map.items()
        if evidence.get("source_match") in {
            "exact_field", "exact_boss_identity",
            "exact_boss_visual_identity"}
    }

    def field_gate(field_id: str) -> dict:
        """引用完整性门禁 + 等级可行性(2026-07-28 改:只要该层存在可行等级即放行,
        具体等级在写入时按层自适应 —— 避免一层封顶拖垮整塔构建)。"""
        report = check_field_chain(field_id, fd_t, zone_t,
                                   set(gb_t) | set(sb_t) | set(gz_t), set(gz_t))
        if not report["ok"]:
            return report
        if report["bosses"] and field_id not in verified_cover_fields:
            report["ok"] = False
            evidence = thumbnail_evidence_map.get(field_id)
            relation = (evidence or {}).get("source_match", "missing")
            report["errors"] = [
                f"Boss 封面缺精确身份关系:{relation}"]
            return report
        level = resolve_level(report["bosses"], args.enemy_level, sb_t, gv_t, gb_t,
                              prefer_max=want_max)
        if level is None:
            report["ok"] = False
            report["errors"] = [f"没有任何敌等级能让 {','.join(report['bosses'])} 正常解析"]
        else:
            report["level"] = level
        return report

    # wf_chain_build 的通用池会把 single/multi 镜像六列全扫进 bosses；本塔是单人
    # event quest，数值审计与重排都必须只携带 c24/28/32 的实际实体，否则 anv3
    # 这类镜像代号不同的场地会被静默算成双 boss、HP 翻倍。
    tower_all = [(field, line, _zone_pick(field)[0])
                 for field, line, _legacy_bosses in cb.build_pool()]
    blocked = [e for e in tower_all if field_blocked(e[0])]
    if blocked:
        tower_all = [e for e in tower_all if not field_blocked(e[0])]
        print(f"[黑名单] 塔素材池剔除 {len(blocked)} 层非 boss 战场地:"
              + ",".join(e[0] for e in blocked))
    resolvable, dangling = [], []
    for e in tower_all:
        rep = field_gate(e[0])
        (resolvable if rep["ok"] else dangling).append((e, rep))
    if dangling:
        print(f"[门禁] 塔素材池剔除 {len(dangling)} 层引用悬空(进本必崩 U_50fc52):")
        for (fdk, _ln, _b), rep in dangling:
            print(f"    {fdk}: {rep['errors'][0]}")
    gated = [e for e, _rep in resolvable]
    tower = [e for e in gated if _pool_safe(e[2])]
    if len(tower) < len(gated):
        print(f"[黑名单] 塔素材池剔除 {len(gated) - len(tower)} 层"
              f"(C8016:{','.join(C8016_BLOCKED_BOSS_PREFIXES)} / "
              f"原生专场限定:{','.join(HP_BLOCKED_BOSSES)})")
    if len(tower) < args.rounds + 1:
        print(f"[ERR] 塔素材池只有 {len(tower)} 层 < {args.rounds}+1 轮")
        return 1
    tower_master = list(tower)          # 钉选(工坊 boss/terrain)查询用,不随消费缩水

    # ---- boss 出场历史降权:最近两座塔出过的 boss,80% 概率让位给新面孔 ----
    special_bosses = load_special_bosses()
    if special_bosses[0] or special_bosses[1]:
        print(f"[原味] 特殊 boss 保护:精确 {len(special_bosses[0])} 个 + "
              f"前缀 {len(special_bosses[1])} 族(抽中即原场地原机制,不拆解)")
    try:
        high_threat_prefixes, high_threat_exact = load_high_threat_rules()
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERR] 高威胁 boss 名单不可用:{exc}")
        return 1
    if high_threat_prefixes or high_threat_exact:
        print("[高威胁] 降难规则:prefixes=" + ",".join(high_threat_prefixes)
              + " exact=" + ",".join(sorted(high_threat_exact)))
    _boss_names = wb.boss_names()

    def _model_and_progs(code: str) -> tuple[str, frozenset]:
        """(模型族, 攻击程序签名)。程序签名取 general_boss 行里引用的 action 名集合。"""
        node = gb_t.get(code) or sb_t.get(code)
        model = ""
        progs: set[str] = set()
        if isinstance(node, dict):
            for leaf in node.values():
                if isinstance(leaf, dict):
                    continue
                text = leaf if isinstance(leaf, str) else (
                    leaf.decode("utf-8") if isinstance(leaf, bytes) else "")
                for ln in text.split(chr(10)):
                    for c in cells(ln):
                        if not model and c.startswith("battle/boss/") \
                                and "general_16dots" not in c:
                            model = c.split("/")[2]
                        if "battle/action" in c:
                            for part in c.split(","):
                                if part.startswith("battle/action"):
                                    progs.add(part.split("$")[-1])
                break
        return model or str(_boss_names.get(code, code)), frozenset(progs)

    def _family(code: str) -> str:
        """去重键 = 模型族 + 攻击程序签名(2026-07-29 用户需求)。

        纯换色同招式的变体仍算同一个(管理者族连出问题);而八岐大蛇三头
        (beam/fire/funnel 程序各异)、猩红巨熊各版本这类**攻击模式不同的变体**
        视为不同 boss,可在同一座塔共存 —— 以前一律按模型族压成 1 个,
        24 个大蛇变体只剩 1 个候选,用户「打了这么久没见过」。"""
        model, progs = _model_and_progs(code)
        return f"{model}#{hash(progs) & 0xffffff:06x}" if progs else model

    def _series_key(code: str) -> str:
        """全塔去重键 = 元素变体系列(精灵兽/女王/荒龙/机兵)压成一个,其余同 _family。

        2026-07-29 用户「XX系列收到一起」:六元素招式一模一样、只换色换属性,
        同塔出两个是重复内容(实测同塔出过雷龟+暗凤、苍机兵+闪机兵)。"""
        model, _progs = _model_and_progs(code)
        series = boss_series_of(code, model)
        return f"系列:{series}" if series else _family(code)

    def name_keys(bosses) -> set[str]:
        """**全塔去重**用系列键。系列有**配额**(见 SERIES_CAPS/series_cap),
        普通 boss 配额恒 1。

        系列成员额外再挂一个**变体键**(配额恒 1)。系列配额 >1 的本意是
        「同塔可以来两只**不同**的元素变体」(雷龟 + 暗凤、苍机兵 + 闪机兵),
        但光有系列键拦不住**同一只**来两遍:`discarded_dragon_dark_tower`
        (塔层版)与 `discarded_dragon_dark`(降临版)是两个代号、同一个模型,
        各占系列名额 1 个 ⇒ 一座塔出两次暗荒龙伊尔昂斯拉,零配额告警。
        (1.4.316 真机实测:第12战 + 第14战。)

        变体键取 `_model_and_progs` 的模型族;模型读不到时它回退成显示名,
        而显示名本来就逐元素不同(闪机兵/苍机兵),两种情况都能把元素分开。
        **只给系列成员挂**——非系列 boss 的 `_family` 配额本来就是 1,再挂一层
        会把八岐大蛇各头(靠攻击程序签名共存)压成一个,那是刻意要保留的。"""
        out: set[str] = set()
        for boss in bosses:
            code = str(boss)
            out.add(_series_key(code))
            model, _progs = _model_and_progs(code)
            if boss_series_of(code, model):
                out.add(f"变体:{model}")
        return out

    def key_cap(key: str) -> int:
        """该去重键在本塔的出场配额:系列按层数缩放,其余(含变体键)恒 1。"""
        return series_cap(key[3:], args.rounds) if key.startswith("系列:") else 1

    def grade_keys(bosses) -> set[str]:
        """**分级收敛**(collapse_grades)用细粒度键。

        ⚠ 这两件事必须用不同的键:分级收敛是"同一个 boss 只留最高难度版本",
        如果也按系列压,六元素会在**池子层面**只剩 1 条 —— 实测机兵池 6→1,
        等于以后永远只出红机兵。要的是"一座塔只出一个",不是"整个池只留一个"。"""
        return {_family(str(b)) for b in bosses}

    # 全塔去重**计数**(2026-07-29 从"用过就禁"改成"配额制"):普通 boss 配额 1
    # (等级/单多人变体同名同灭),元素变体系列按 SERIES_CAPS × 层数给多个名额。
    used_counts: dict[str, int] = {}
    future_anchor_counts: dict[str, int] = {}

    def _quota_left(key: str) -> bool:
        return (used_counts.get(key, 0) + future_anchor_counts.get(key, 0)
                < key_cap(key))

    def unused_only(entries, bosses_of):
        kept = [e for e in entries
                if all(_quota_left(k) for k in name_keys(bosses_of(e)))]
        return kept or entries          # 池子枯竭才允许重复(打印于挑选处)

    recent_bosses = set(sum(load_boss_history()[:2], []))
    if recent_bosses:
        print(f"[历史] 最近两座塔出过 {len(recent_bosses)} 个 boss,抽取时降权(80% 偏好新面孔)")

    def prefer_fresh(entries, bosses_of):
        if not recent_bosses:
            return entries
        fresh = [e for e in entries if not (set(bosses_of(e)) & recent_bosses)]
        if fresh and rng.random() < 0.8:
            return fresh
        return entries

    featured_pref, featured_w = load_featured_bosses()
    if featured_pref:
        print(f"[精选] {len(featured_pref)} 个 boss 前缀权重 ×{featured_w}:"
              + ",".join(featured_pref))

    def weight_featured(entries, bosses_of):
        """精选 boss 的候选项重复 featured_w 份 = 抽中概率 ×N(不是硬钉)。"""
        if not featured_pref:
            return entries
        out = list(entries)
        for e in entries:
            if is_featured(bosses_of(e), featured_pref):
                out.extend([e] * (featured_w - 1))
        return out

    # ---- 楼层来源池(v5)----
    def gate_src(label: str, entries: list[dict]) -> list[dict]:
        kept = []
        for e in entries:
            if field_blocked(e["field"]):
                print(f"[黑名单] 来源池「{label}」剔除 {e['field']}(非 boss 战场地)")
                continue
            rep = field_gate(e["field"])
            if rep["ok"]:
                kept.append(e)
            else:
                print(f"[门禁] 来源池「{label}」剔除 {e['field']}: {rep['errors'][0]}")
        return kept

    zako_lst = gate_src("小怪房", zako_room_pool())
    minion_lst = gate_src("杂鱼boss", minion_boss_pool())
    src = {
        "领主战": quest_pool("boss_battle"),
        "机兵": quest_pool("hard_multi"),
        "降临讨伐": quest_pool("advent"),
        # 2026-07-29 补全:联动/活动 boss(C·F·奇迹、超人泽古拉、基因巨龙、DAN 警卫、
        # 噬星兽等)只挂在世界剧情/剧情活动下,以前整类没进池 —— 用户「打了这么久
        # 没见过联动 boss」的根因
        "世界剧情": quest_pool("world_story"),
        "剧情活动": quest_pool("story_event"),
        "女帝歼灭者": quest_pool("advent", name_eq="女帝歼灭者"),
        "无幻之宴": quest_pool("raid", name_eq="无幻之宴"),
        # 2026-07-29 全类别普查补全:GUI 手选池覆盖 16 类,生成器随机却只抽 7 类,
        # 下面 6 类整类抽不到(合计 ~90 个 boss 摸不着)。类别↔中文对照:
        #   战阵之宴 = raid(黑龙/基因巨龙/异质魔晶羊;无幻之宴另有守门固定位)
        #   单人挑战 = expert_single_event[1]「单人挑战 讨伐战斗」
        #              + [2]「追忆试炼」(同表:诅咒弧魔六档/白虎/管理者/不死王/寄居蟹船长)
        #   极时试炼 = solo_time_attack(时与X之试炼,六个 *_ex 强化版)
        #   剧情boss = world_story_boss(玛格诺斯/噬龙者/星辰破坏者/统领AI/SecMk2)
        #   元素试炼 = ranking(云水/奔雷/旋风/溢光/闪火 = 五元素球本体)
        #   土俑嘉年华 = carnival(6 元素 × 土机/直击/强振/必杀 4 套伤害体系 = 24 个
        #              独立去重键,用户明确要求全量,不做同族收敛)
        "战阵之宴": [e for e in quest_pool("raid") if e["name"] != "无幻之宴"],
        "单人挑战": quest_pool("expert_single"),
        "极时试炼": quest_pool("solo_time_attack"),
        "剧情boss": quest_pool("world_story_boss"),
        "元素试炼": quest_pool("ranking"),
        "土俑嘉年华": quest_pool("carnival"),
        "主线boss": main_story_boss_pool(),
    }
    for label in src:
        gated_pool = gate_src(label, src[label])
        kept = [e for e in gated_pool if _pool_safe(e["bosses"])]
        if len(kept) < len(gated_pool):
            print(f"[黑名单] 来源池「{label}」剔除 {len(gated_pool) - len(kept)} 个场地")
        top = collapse_grades(kept, grade_keys)   # 细粒度:六元素都要留在池里
        if len(top) < len(kept):
            print(f"[分级] 来源池「{label}」{len(kept)} → {len(top)}(同 boss 只留最高难度版本)")
        # 「超级起步」硬门槛(2026-07-29 用户需求:简单档一律不看)。
        # collapse_grades 已把每个 boss 收敛到它最难的一版,所以这里刷掉的是
        # **本身最高也只有高级/中级**的 boss —— 它们要么在塔池里另有高难变体,
        # 要么就该待在杂鱼层。全刷空时保留原池(宁可低档也别让排程塌掉)。
        hard = ([] if label in NO_LEVEL_FLOOR else
                [e for e in top if str(e.get("level", "")).isdigit()
                 and int(e["level"]) >= MIN_QUEST_LEVEL])
        if label in NO_LEVEL_FLOOR:
            pass                      # 主线boss:手挑名单,官方等级本就低,不设门槛
        elif hard and len(hard) < len(top):
            print(f"[难度] 来源池「{label}」{len(top)} → {len(hard)}"
                  f"(只留 ≥{MIN_QUEST_LEVEL} 级=超级及以上)")
            top = hard
        elif not hard:
            print(f"[难度] 来源池「{label}」无 ≥{MIN_QUEST_LEVEL} 级场地,保留原池 {len(top)} 个")
        src[label] = top
    # 终始之龙(2026-07-20 换回主线正版):NPC 协力/剧情强制是 quest 侧列,只引用
    # field 不会带过来;「buff 重置」压制(buff_reset1..4)在 boss kit 里=原汁机制。
    # boss=chapter12_boss_story(standard,官方元素=暗),1 wave,专属 12 章擂台。
    DRAGON_FIELD = "main_12_10_01"
    DRAGON_THUMB = "quest/thumbnail/world_12/battle_12_5"
    dragon_rep = field_gate(DRAGON_FIELD)
    if not dragon_rep["ok"]:
        print(f"[ERR] 末轮固定楼层「终始之龙」({DRAGON_FIELD}) 引用悬空:"
              + "; ".join(dragon_rep["errors"]))
        return 1
    # 机工神兵菲诺梅那(2026-07-29 用户需求:与终始之龙同等待遇的常驻 boss)。
    # steampunk_another 一个 field 挂 5 个难度行(20/50/70/80/100),取地狱级;
    # zone 里是**双 boss**:本体 steampunk_another_multi + 二形态 _foom2_multi,
    # 两者都在 standard_boss。原味保护名单里已有这两个代号,不会被 mix 拆解。
    PHENO_FIELD = "steampunk_another"
    pheno_src = next((e for e in quest_pool("boss_battle")
                      if e["field"] == PHENO_FIELD), None)
    PHENO_THUMB = (pheno_src or {}).get("thumb", "")
    pheno_rep = field_gate(PHENO_FIELD)
    if not pheno_rep["ok"]:
        print(f"[ERR] 常驻楼层「机工神兵菲诺梅那」({PHENO_FIELD}) 引用悬空:"
              + "; ".join(pheno_rep["errors"]))
        return 1
    # 始龙之眼(多人版)下放到领主战池当普通 boss 候选
    EYE_FIELD = "eye_dragon_multibattle"
    EYE_THUMB = "quest/thumbnail/world_10/thumbnail1"
    eye_rep = field_gate(EYE_FIELD)
    if eye_rep["ok"]:
        src["领主战"].append({"field": EYE_FIELD, "bosses": ["eye_dragon_multibattle_boss"],
                              "thumb": EYE_THUMB, "name": "始龙之眼"})
    else:
        print(f"[门禁] 固定候选「始龙之眼」({EYE_FIELD}) 引用悬空,弃用:"
              + "; ".join(eye_rep["errors"]))
    for label, lst in ([("小怪房", zako_lst), ("杂鱼boss", minion_lst)]
                       + list(src.items())):
        if not lst:
            print(f"[ERR] 来源池「{label}」为空")
            return 1
        print(f"来源池 {label}: {len(lst)} 个场地")

    # quest 名在池内不唯一时(24 个土俑嘉年华全叫「土俑嘉年华」、演武全叫「XX演武」),
    # 计划表打印退回 boss 名,否则一眼看不出抽到的是哪个伤害体系的变体。
    _dup_names: dict[str, set] = {}
    for _lab, _lst in src.items():
        _cnt: dict[str, int] = {}
        for _e in _lst:
            _cnt[_e["name"]] = _cnt.get(_e["name"], 0) + 1
        _dup_names[_lab] = {n for n, c in _cnt.items() if c > 1}

    def src_pick(label: str) -> dict:
        cand = unused_only(src[label], lambda e: e["bosses"])
        cand = prefer_fresh(cand, lambda e: e["bosses"])
        cand = weight_featured(cand, lambda e: e["bosses"])
        e = cand[rng.randrange(len(cand))]
        disp = e["name"]
        # 主线boss 是"按 boss 挑"的池,关卡名(「破除诅咒1」)看不出打的是谁,恒显示 boss 名
        if not disp or label == "主线boss" or disp in _dup_names.get(label, ()):
            disp = "、".join(dict.fromkeys(
                str(_boss_names.get(b, b)).split("/")[0] for b in e["bosses"])) or e["field"]
        return {"field": e["field"], "bosses": e["bosses"], "thumb": e["thumb"],
                "bgm": None, "label": f"{label}·{disp}"}

    def dragon_pick() -> dict:
        bosses, _ = _zone_pick(DRAGON_FIELD)
        return {"field": DRAGON_FIELD, "bosses": bosses, "thumb": DRAGON_THUMB,
                "bgm": None, "label": "终始之龙·主线终章正版"}

    def finale_pick() -> dict:
        """Pick the last floor from proved high-value fields, dragon included."""

        candidates = [dragon_pick()]
        for field in dict.fromkeys(
                DEEP_HP_ANCHOR_FIELDS_30 + MID_HP_ANCHOR_FIELDS_30):
            bosses, _ = _zone_pick(field)
            if (not bosses or not _pool_safe(bosses)
                    or not field_gate(field)["ok"]):
                continue
            candidates.append({
                "field": field,
                "bosses": bosses,
                "thumb": thumb_map.get(field, ""),
                "bgm": None,
                "label": "终局Boss·" + "、".join(dict.fromkeys(
                    str(_boss_names.get(code, code)).split("/")[0]
                    for code in bosses)),
            })
        candidates = unused_only(candidates, lambda item: item["bosses"])
        candidates = prefer_fresh(candidates, lambda item: item["bosses"])
        if not candidates:
            raise RuntimeError("安全高难终局 Boss 候选池为空")
        return candidates[rng.randrange(len(candidates))]

    def zako_pick() -> dict:
        e = zako_lst.pop(rng.randrange(len(zako_lst)))
        return {"field": e["field"], "bosses": [], "thumb": e["thumb"],
                "bgm": None, "label": f"小怪房·{e['name']}"}

    def phenomena_pick() -> dict:
        bosses, _ = _zone_pick(PHENO_FIELD)
        return {"field": PHENO_FIELD, "bosses": bosses, "thumb": PHENO_THUMB,
                "bgm": None, "label": "机工神兵·菲诺梅那 地狱级"}

    def _special_family_pick(family_name: str) -> dict:
        family_bundles = [
            bundle for bundle in native_special_bundles
            if special_bundle_family(bundle) == family_name
        ]
        if not family_bundles:
            raise RuntimeError(f"专用 bundle 池为空:{family_name}")
        bundle = family_bundles[rng.randrange(len(family_bundles))]
        family = special_bundle_family(bundle)
        parent = (_orochi_parent_ref(bundle) if family == "orochi" else
                  _orochi_ex_parent_ref(bundle) if family == "orochi_ex" else
                  _single_bar_special_parent_ref(bundle, family)
                  if family in SINGLE_BAR_SPECIAL_SPECS else
                  _sphere_parent_ref(bundle, family)
                  if family in SPHERE_SPECS else None)
        if parent is None:
            raise RuntimeError("专用 bundle 缺唯一父体")
        return {
            "field": bundle.source_field,
            "bosses": list(native_bundle_bosses(bundle)),
            "thumb": bundle.thumbnail,
            "bgm": bundle.bgm,
            "label": f"专用多阶段·{bundle.family_name}·{bundle.variant_name}",
            "native_bundle": bundle,
        }

    def orochi_pick() -> dict:
        return _special_family_pick("orochi")

    def orochi_ex_pick() -> dict:
        return _special_family_pick("orochi_ex")

    def kraken_pick() -> dict:
        return _special_family_pick("kraken")

    def conductor_pick() -> dict:
        return _special_family_pick("conductor")

    def touyakiren_ceo_pick() -> dict:
        return _special_family_pick("touyakiren_ceo")

    def sphere_pick(family: str) -> dict:
        return _special_family_pick(family)

    def minion_pick() -> dict:
        cand = unused_only(minion_lst, lambda e: e["bosses"])
        cand = prefer_fresh(cand, lambda e: e["bosses"])
        e = cand[rng.randrange(len(cand))]
        minion_lst.remove(e)
        disp = "、".join(dict.fromkeys(
            str(_boss_names.get(b, b)).split("/")[0] for b in e["bosses"])) or e["name"]
        return {"field": e["field"], "bosses": e["bosses"], "thumb": e["thumb"],
                "bgm": None, "label": f"杂鱼boss·{disp}"}

    # ---- ② rush_event 行 ----
    # ⚠ 列语义(RushEventValues 实锤):c2=banner_schedule(横幅轮播排期,不是活动期!)
    # c15=start_time c16=playable_end_time c17=exchangeable_end_time。
    # 700099 行已存在时以现有行为基底(保留 wf_rogue_banner 换过的横幅列 c3/c4)。
    ev = q.load_table(Q_EVENT)
    template_leaf = ev[TEMPLATE_EVENT]
    current_leaf = ev.get(EVENT_ID) or template_leaf
    event_leaf = build_event_metadata_leaf(template_leaf, current_leaf)
    ev_row = cells(event_leaf)
    ev_bytes = isinstance(event_leaf, bytes)

    # ---- ② folder 行(连战=700007 超级 folder 3 模板;无尽=folder 4 模板)----
    fo = q.load_table(Q_FOLDER)
    server_folders = load_server_asset("rush_event_quest_folder.json")
    # Match the server's later setdefault behavior when introducing a new tower.
    fixed_rewards = server_folders[EVENT_ID if EVENT_ID in server_folders else TEMPLATE_EVENT]["1"]
    folder_leaf = build_deep_abyss_folder_leaf(fo[TEMPLATE_EVENT]["3"], fixed_rewards)
    fo_bytes = isinstance(fo[TEMPLATE_EVENT]["3"], bytes)
    fo_endless = list(cells(fo[TEMPLATE_EVENT]["4"]))
    fo_endless[0] = "100"
    fo_endless[1] = "2"       # quest_kind = endless(缺它 = 点∞按钮 C3442)
    fo_endless[2] = "无尽战斗"
    if BUILD_MODE == "ex":
        for start in range(7,37,3):
            fo_endless[start:start+3] = ["(None)", "", "(None)"]

    # ---- ② quest 行 ----
    qt = q.load_table(Q_QUEST)
    details_ui_enabled = quest_details.should_enable(
        args.details_ui, (cells(leaf)[3] for leaf in qt.get(EVENT_ID, {}).values()))
    tmpl_r1 = cells(qt[TEMPLATE_EVENT]["1"])
    tmpl_rn = cells(qt[TEMPLATE_EVENT]["2"])
    tmpl_endless = cells(qt[TEMPLATE_EVENT]["8"])
    qt_bytes = isinstance(qt[TEMPLATE_EVENT]["1"], bytes)
    ELEM_CN = QUEST_ELEM_CN      # c69 是 quest 枚举(0风1火2水3雷4暗5光),别用 boss 那套

    thumb_map = {
        field_id: evidence["thumbnail"]
        for field_id, evidence in thumbnail_evidence_map.items()
    }
    belem_map = boss_element_map()
    elem_map = field_official_elem_map()

    # ---- 乱流机关:zone/field 克隆注入(诅咒「乱流机关」)----
    # 机关列语义:c36 冲刺板 / c37 旋转桨,全游戏同族机制仅皮肤不同(塔层实际用
    # 海遗迹皮),跨地形通用;地形无锚点时安静空转,无崩溃面。克隆行前缀
    # mod_rogue_z/f,每次构建先清旧克隆防膨胀。
    GIM_DASH = "battle/field_object/world_advent/steampunk_area/yakumono/dash_panel"
    GIM_ROT = ("battle/field_object/world_advent/steampunk_area/"
               "rotation_panel/steampunk_area_rotation_panel")
    # fd_t/zone_t/gz_t/zl_t/gb_t/bl_t/gv_t 已在 main 顶部载入并清过旧克隆(门禁共用)

    # ---- terrain 能力表(2026-07-20:锚点决定祭坛/板子能否生效)----
    # 板子能力 = 数据驱动:官方存在"zone 挂 c36 板子"配对的 terrain 集合;
    # 出生点能力 = terrain(Tiled) 二进制含 SPAWNn 标记(排除 FUNNEL_SPAWNn)。
    # 成对/分阶段 boss 名单(数据驱动,进程内算一次)+ 被门禁挡下的层的理由
    phase_linked = phase_linked_bosses(zone_t, fd_t)
    # 代号引用名单只算一次(要遍历 general_boss_state 4.4MB);逐层重算 = 白烧十几秒。
    code_refs = code_referenced_bosses(gb_t)
    if ew_t is None and not code_refs["degraded"]:
        # 表读得到才有 self 侧可补;读不到时上面的 WARN 已把 degraded 置真,这里兜底。
        code_refs = dict(code_refs, degraded=True)
    caster_blocked: dict[str, str] = {}
    clone_sources: dict[str, str] = {}
    clone_watch_alias_counts: dict[str, int] = {}
    identity_reference_closures: dict[int, list[dict]] = {}
    native_special_bundles: list[rbb.NativeBossBundle] = []
    _runtime_validation = boss_ref_validation_tables(
        standard_boss=sb_t, general_boss=gb_t,
        general_boss_variable=gv_t,
        special_tables={
            "orochi": oro_t,
            "orochi_ex": oro_ex_t,
            "orochi_ex_head": oro_ex_head_t,
            **single_bar_special_tables,
            **sphere_tables,
        })
    try:
        _runtime_general_funnel = q.load_table(GENERAL_FUNNEL)
    except Exception:
        _runtime_general_funnel = {}
    try:
        _runtime_standard_funnel = q.load_table(STANDARD_FUNNEL)
    except Exception:
        _runtime_standard_funnel = {}

    def _runtime_spawned_ref_gate(source_kind: str, code: str, level: int):
        return validate_spawned_ref(
            source_kind, code, level,
            validation_tables=_runtime_validation,
            general_zako=gz_t,
            general_funnel=_runtime_general_funnel,
            standard_funnel=_runtime_standard_funnel)

    orochi_tables = {
        "orochi": oro_t,
        "orochi_ex": oro_ex_t,
        "orochi_ex_head": oro_ex_head_t,
        **single_bar_special_tables,
        **sphere_tables,
        **sphere_aux_tables,
        "general_boss": gb_t,
        "general_boss_variable": gv_t,
        "boss_level": bl_t,
        "general_enemy_watch": ew_t,
        "kraken_tentacle": kraken_tentacle_t,
        "kraken_funnel_level": kraken_funnel_level_t,
        "__code_references__": code_refs,
        "__action_loader__": rbb.load_store_action,
        "__spawned_ref_gate__": _runtime_spawned_ref_gate,
    }
    # A layout-plan terrain/boss pin enters ``mix_pick`` even when the CLI did
    # not include --mix.  Load the plan once before building compatibility
    # evidence so pinned combinations cannot run with an empty catalog.
    plan = {} if args.ignore_plan else layout_plan()
    planned_floors = (plan.get("floors", {})
                      if isinstance(plan, dict) else {})
    planned_mix = any(
        isinstance(value, dict)
        and bool(value.get("terrain") or value.get("boss"))
        for value in planned_floors.values())
    mix_compatibility_required = bool(args.mix or planned_mix)

    # ``--mix`` 与严格 HP 专场共用同一份 fresh post-purge catalog。过去只有
    # 专场选择会建立它，旧 mix_pick 因而绕过了已经存在的 ActionDSL→命名坐标
    # →目标 terrain 门禁，只看槽数/白名单便移植，最终在 p0/p1/p2 缺失时进本崩。
    special_catalog_tables: dict[str, dict] = {}
    for _logical in SPECIAL_BOSS_TABLES:
        _short = Path(_logical).name.removesuffix(".orderedmap")
        if _logical == OROCHI:
            special_catalog_tables[_short] = oro_t
            continue
        if _logical == OROCHI_EX:
            special_catalog_tables[_short] = oro_ex_t
            continue
        if _short in single_bar_special_tables:
            special_catalog_tables[_short] = single_bar_special_tables[_short]
            continue
        if _short in sphere_tables:
            special_catalog_tables[_short] = sphere_tables[_short]
            continue
        try:
            special_catalog_tables[_short] = q.load_table(_logical)
        except Exception:
            special_catalog_tables[_short] = {}
    special_catalog_tables["orochi_ex_head"] = oro_ex_head_t

    def _build_runtime_native_catalog() -> rbb.BundleCatalog:
        return build_native_bundle_catalog(
            100, fd=fd_t, zone=zone_t, sb=sb_t, gb=gb_t, gv=gv_t,
            bl=bl_t, gz=gz_t, special_tables=special_catalog_tables,
            general_boss_state=gbs_t,
            general_enemy_watch=ew_t, code_references=code_refs,
            general_funnel=_runtime_general_funnel,
            standard_funnel=_runtime_standard_funnel,
            kraken_tentacle=kraken_tentacle_t,
            kraken_funnel_level=kraken_funnel_level_t,
            sphere_aux_tables=sphere_aux_tables,
            action_loader=rbb.load_store_action,
            esdl_loader=rbb.load_store_esdl,
            display_names=_boss_names,
            metadata_of=lambda field_id: {
                "category": "runtime-native",
                "bgm": None,
                "thumbnail": thumb_map.get(field_id, ""),
            })

    _native_catalog: rbb.BundleCatalog | None = None
    if args.strict_target_hp or mix_compatibility_required:
        try:
            _native_catalog = _build_runtime_native_catalog()
        except (FileNotFoundError, KeyError, TypeError, ValueError,
                RuntimeError, zlib.error) as _exc:
            if mix_compatibility_required:
                print("[ERR] --mix 无法建立 ActionDSL/terrain 兼容目录，"
                      f"拒绝降级到旧槽数白名单:{_exc}")
                return 1
            print(f"[WARN] 专用 bundle 目录不可用，严格模式继续排除:{_exc}")
            _native_catalog = None

    mix_bundles_by_field = (
        native_bundle_field_index(_native_catalog)
        if mix_compatibility_required else {})
    if mix_compatibility_required and not mix_bundles_by_field:
        print("[ERR] --mix 的 ActionDSL/terrain 兼容目录为空，拒绝构建")
        return 1

    mix_bundles_by_level = {}

    def mix_compatibility(source_field, target_field, bosses, round_no):
        level = resolve_level(bosses, want_level(round_no), sb_t, gv_t,
                              gb_t, prefer_max=want_max)
        if level is None:
            return rbb.CompatibilityResult(False, "LEVEL_UNRESOLVED",
                                           "donor has no usable level", source_field, target_field)
        level = int(level)
        if level not in mix_bundles_by_level:
            # Different level leaves can execute different ActionDSL/ESDL.
            # Prove each against the immutable input view, never a field
            # generated by an earlier round of this candidate.
            mix_bundles_by_level[level] = native_bundle_field_index(
                build_native_bundle_catalog(level))
        strict, safe_set = load_transplant_policy()
        return checked_mix_terrain_compatibility(
            source_field, target_field, mix_bundles_by_level[level],
            strict_transplant=strict, transplant_safe=safe_set)

    if args.strict_target_hp and _native_catalog is not None:
        # Dedicated bundles stay on their official field.  HP/level/reference
        # gates remain mandatory; the same catalog also feeds mix compatibility.
        try:
            _seen_special: set[tuple[str, str, str]] = set()
            for _bundles in _native_catalog.bundles.values():
                for _bundle in _bundles:
                    _bundle_family_name = special_bundle_family(_bundle)
                    _parent = (_orochi_parent_ref(_bundle)
                               if _bundle_family_name == "orochi" else
                               _orochi_ex_parent_ref(_bundle)
                               if _bundle_family_name == "orochi_ex" else
                               _single_bar_special_parent_ref(
                                   _bundle, _bundle_family_name)
                               if _bundle_family_name in SINGLE_BAR_SPECIAL_SPECS
                               else _sphere_parent_ref(
                                   _bundle, _bundle_family_name)
                               if _bundle_family_name in SPHERE_SPECS
                               else None)
                    _key = (_bundle_family_name or "", _bundle.source_field,
                            _parent.code if _parent is not None else "")
                    _safe = (_pool_safe(native_bundle_bosses(_bundle))
                             if _bundle_family_name == "orochi" else
                             _c8016_safe(list(native_bundle_bosses(_bundle))))
                    if (_parent is None or _key in _seen_special
                            or field_blocked(_bundle.source_field) or not _safe
                            or _bundle.source_field not in verified_cover_fields):
                        continue
                    _evidence = (orochi_native_hp_evidence(
                        _bundle, 100, orochi_tables)
                        if _bundle_family_name == "orochi" else
                        orochi_ex_native_hp_evidence(
                            _bundle, 100, orochi_tables)
                        if _bundle_family_name == "orochi_ex" else
                        single_bar_special_native_hp_evidence(
                            _bundle, 100, orochi_tables)
                        if _bundle_family_name in SINGLE_BAR_SPECIAL_SPECS else
                        sphere_native_hp_evidence(
                            _bundle, 100, orochi_tables))
                    if not (_evidence.get("verified")
                            and _evidence.get("absolute_verified")):
                        continue
                    _seen_special.add(_key)
                    native_special_bundles.append(_bundle)
        except (FileNotFoundError, KeyError, TypeError, ValueError,
                RuntimeError, zlib.error) as _exc:
            print(f"[WARN] 专用 bundle 目录不可用，严格模式继续排除:{_exc}")
            native_special_bundles = []
    if args.strict_target_hp:
        if native_special_bundles:
            _family_counts = {
                family: sum(1 for bundle in native_special_bundles
                            if special_bundle_family(bundle) == family)
                for family in (
                    "orochi", "orochi_ex", *SINGLE_BAR_SPECIAL_SPECS,
                    *SPHERE_SPECS)
            }
            print(f"[专用HP] 原生专场 {len(native_special_bundles)} 个通过:"
                  f"普通 {_family_counts['orochi']} / EX "
                  f"{_family_counts['orochi_ex']} / Kraken "
                  f"{_family_counts['kraken']} / 指挥者 "
                  f"{_family_counts['conductor']} / CEO "
                  f"{_family_counts['touyakiren_ceo']} / Sphere "
                  + ",".join(
                      f"{SPHERE_SPECS[family]['label']} "
                      f"{_family_counts[family]}"
                      for family in SPHERE_SPECS)
                  + "（仅原场地，整包克隆，不参与移植）")
        else:
            print("[专用HP] 原生专场 0 个；本轮严格模式明确排除专用构造器")
    panel_terrains: set[str] = set()
    for fk, fv in fd_t.items():
        if not isinstance(fv, (str, bytes, bytearray)):
            continue
        fc0 = cells(fv)
        if len(fc0) < 3:
            continue
        zn0 = zone_t.get(fc0[2])
        if not isinstance(zn0, dict):
            continue
        for wrow0 in zn0.values():
            if isinstance(wrow0, dict):
                continue
            wc0 = cells(wrow0)
            if len(wc0) > 36 and wc0[36] not in ("", "(None)"):
                panel_terrains.add(fc0[1])
                break

    def carrier_status(field_id: str, bosses: list[str],
                       enemy_level: int | None = None, *,
                       record: bool = False) -> dict:
        """无副作用计算硬通道/属性免疫资格；仅 ``record`` 时登记最终场地理由。"""
        target = next((b for b in bosses if b in belem_map), None)
        carrier = target is not None
        carrier_why = None
        if carrier:
            # 成对/分阶段 boss 层禁发法阵(2026-07-30 玩家「打不死」实锤);
            # 被外部按代号引用的 boss 同禁(2026-08-03 鲨鱼三兄弟/旋风巨土俑实锤)
            why = caster_carrier_block(field_id, bosses, fd_t, zone_t,
                                       phase_linked, gb_t, refs=code_refs)
            if why:
                if record:
                    caster_blocked[field_id] = why
                carrier = False
                carrier_why = why
        element_reason = carrier_why or (
            general_boss_element_immunity_block(gb_t, target, enemy_level, gv_t)
            if target else "没有 general_boss 实际代号")
        return {"boss": carrier,
                "element": carrier and element_reason is None,
                "element_target": target,
                "element_reason": element_reason,
                "carrier_reason": (carrier_why or (
                    "没有 general_boss 实际代号" if target is None else None))}

    def field_caps(field_id: str, bosses: list[str], enemy_level: int | None = None) -> dict:
        """能力表:boss=有 general boss 可当法阵载体(2026-07-20 实证:zone-zako
        emitter 需地形 SPAWN 物件定位,95% 楼层没有,'*spawn-point*' 是"生成点"
        注册名而非地形标记查找——zako 祭坛路线弃);panel=官方板子配对地形。"""
        frow = fd_t.get(field_id)
        panel = False
        if isinstance(frow, (str, bytes, bytearray)):
            fc = cells(frow)
            panel = len(fc) > 2 and fc[1] in panel_terrains
        status = carrier_status(field_id, bosses, enemy_level, record=True)
        status["panel"] = panel
        return status

    def make_caster_boss(r: int, boss_code: str, action_program: str | None = None,
                         action_programs=(),
                         pre_action_program: str | None = None,
                         requires_element_resistance: bool = False,
                         enemy_level: int | None = None,
                         clone_code: str | None = None,
                         boss_level_leaf=None,
                         expected_selected_level: int | None = None,
                         damage_check_plan: dict | None = None):
        """克隆 general boss 当 HP/硬效果载体。

        法阵追加到第一条现役 action(c111-160)；耐性条件追加到 c109
        pre_action 且 c110=true。两者可共用同一克隆,定位天然有效。
        附表(boss_level/general_boss_variable/general_enemy_watch 的 self 侧)按 code
        同步克隆。若 HP 改写会放大带 c16 红色伤害试炼条的 Boss，则为实际
        选中档克隆一份私有 routine，按最终 HP（含 HP 诅咒）反向缩放 c16；
        其余 52 列和 general_enemy_watch routine lookup 保持闭包。

        ⚠ general_enemy_watch 的 self 条目和 partner 别名**必须**跟着克隆
        (2026-08-03):客户端按
        [实体种类=1][boss 代号][routine_id] 取自身观察数据(GeneralBossSource:92 →
        GeneralEnemyWatchTableTools.getSelfData),查不到静默返回 null。routine_id 随行
        克隆时没变,所以整棵子树原样挂到新代号下即可。partner 侧(别人 watch 我)
        在每个原 watcher 下追加 clone id 的等价分支；官方 source id 分支不改。"""
        nonlocal caster_dirty, general_state_dirty
        if boss_code not in gb_t:
            return None
        identity_block = identity_clone_locked_boss_reason(
            [boss_code], code_references=code_refs)
        if identity_block:
            # Must precede every table mutation below.  Candidate/strategy
            # gates normally make this unreachable; this last guard prevents a
            # future direct caller from leaving a renamed half-clone behind.
            raise RuntimeError(f"第{r}战 general boss clone 拒绝:{identity_block}")
        code = clone_code or f"{PRIVATE_PREFIX}boss{r}"

        donor_node = (abyss_ex.without_five_curse(gb_t[boss_code], cells, join)
                      if BUILD_MODE == "ex" else gb_t[boss_code])
        if action_program or action_programs or pre_action_program:
            gb_t[code] = rewrite_boss_carrier_node(
                donor_node, action_program=action_program,
                action_programs=action_programs,
                pre_action_program=pre_action_program)
        else:
            # 纯 HP clone 不追加 action，但仍必须拥有独立 general_boss 子树；
            # 未来若再改 clone 行，不能反向污染官方源代号。
            gb_t[code] = copy.deepcopy(donor_node)
        damage_contract = None
        if damage_check_plan is not None:
            try:
                gb_t[code], damage_contract = (
                    materialize_general_damage_check_clone(
                        gb_t[code], gbs_t, damage_check_plan,
                        clone_code=code))
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"第{r}战 General DamageCheck clone 失败:"
                    f"{boss_code}->{code}:{exc}") from exc
            contract_slot = damage_check_plan.get("contract")
            if not isinstance(contract_slot, dict):
                raise RuntimeError(
                    f"第{r}战 General DamageCheck 计划缺共享回执槽:{boss_code}")
            contract_slot.clear()
            contract_slot.update(copy.deepcopy(damage_contract))
            if int(damage_contract.get("occurrence_count") or 0) > 0:
                general_state_dirty = True
        if boss_level_leaf is not None:
            # boss_level 在当前表形态是 code→CSV leaf（没有等级内层）。只接受
            # general_hp_scale_plan 已重建的 Hit/Fix 行；短行/未知 kind 再次 fail closed。
            check = cells(boss_level_leaf)
            if len(check) < 13 or check[0] not in {"0", "1"}:
                raise RuntimeError(
                    f"第{r}战 {boss_code} 的 clone boss_level 不是 Hit/Fix HP 行")
            bl_t[code] = boss_level_leaf
        elif boss_code in bl_t:
            bl_t[code] = bl_t[boss_code]
        if boss_code in gv_t:
            gv_t[code] = gv_t[boss_code]
        if requires_element_resistance:
            # 最终判据必须读“克隆后实际落表行”的 c36,不是原型名。预筛本应让它
            # 永远为 false；若克隆逻辑未来改坏继承关系,在文案落表前硬停。
            blocked = general_boss_element_immunity_block(gb_t, code, enemy_level, gv_t)
            if blocked:
                raise RuntimeError(f"第{r}战属性免疫载体复核失败:{blocked}")
        if enemy_level is not None:
            source_selected = select_surjective_level(gb_t.get(boss_code), enemy_level)
            clone_selected = select_surjective_level(gb_t.get(code), enemy_level)
            expected = (source_selected if expected_selected_level is None
                        else int(expected_selected_level))
            if source_selected != expected or clone_selected != expected:
                raise RuntimeError(
                    f"第{r}战 boss clone 选档漂移:{boss_code}@{source_selected} -> "
                    f"{code}@{clone_selected}, expected={expected}")
            if code not in bl_t:
                raise RuntimeError(f"第{r}战 boss clone {code} 缺 boss_level 叶")
        watch_routine_alias_count = 0
        if ew_t is not None and boss_code in ew_t.get("1", {}):
            cloned_watch_self = copy.deepcopy(ew_t["1"][boss_code])
            if damage_contract is not None:
                try:
                    watch_routine_alias_count = clone_enemy_watch_routine_alias(
                        cloned_watch_self,
                        str(damage_contract["source_routine_id"]),
                        str(damage_contract["final_routine_id"]))
                except (KeyError, TypeError, ValueError) as exc:
                    raise RuntimeError(
                        f"第{r}战 general_enemy_watch routine 闭包失败:"
                        f"{boss_code}->{code}:{exc}") from exc
                source_watch_has_routine = (
                    str(damage_contract["source_routine_id"])
                    in ew_t["1"][boss_code])
                if (source_watch_has_routine
                        and str(damage_contract["source_routine_id"])
                        != str(damage_contract["final_routine_id"])
                        and watch_routine_alias_count != 1):
                    raise RuntimeError(
                        f"第{r}战 general_enemy_watch routine alias 缺失:"
                        f"{damage_contract['source_routine_id']}->"
                        f"{damage_contract['final_routine_id']}")
            ew_t.setdefault("1", {})[code] = cloned_watch_self
        if damage_contract is not None:
            contract_slot = damage_check_plan["contract"]
            contract_slot["enemy_watch_routine_alias_count"] = int(
                watch_routine_alias_count)
            contract_slot["enemy_watch_lookup_preserved"] = True
            if watch_routine_alias_count:
                identity_reference_closures.setdefault(int(r), []).append({
                    "kind": "general_enemy_watch.routine_alias",
                    "source_code": str(boss_code),
                    "clone_code": str(code),
                    "source_routine_id": str(
                        damage_contract["source_routine_id"]),
                    "clone_routine_id": str(
                        damage_contract["final_routine_id"]),
                    "verified": True,
                })
        watch_alias_count = 0
        if ew_t is not None:
            try:
                watch_alias_count = clone_enemy_watch_partner_aliases(
                    ew_t, boss_code, code)
            except ValueError as exc:
                raise RuntimeError(
                    f"第{r}战 enemy_watch partner 闭包失败:"
                    f"{boss_code}->{code}:{exc}") from exc
        expected_watch_alias = (
            boss_code in set(map(
                str, code_refs.get("enemy_watch_partner") or ())))
        if expected_watch_alias and watch_alias_count <= 0:
            raise RuntimeError(
                f"第{r}战 enemy_watch partner 闭包缺失:"
                f"{boss_code}->{code}")
        if expected_watch_alias:
            source_reference_count = enemy_watch_partner_reference_count(
                ew_t, boss_code)
            clone_reference_count = enemy_watch_partner_reference_count(
                ew_t, code)
            if (source_reference_count <= 0
                    or clone_reference_count != source_reference_count
                    or watch_alias_count != source_reference_count):
                raise RuntimeError(
                    f"第{r}战 enemy_watch partner 回读数量漂移:"
                    f"{boss_code}={source_reference_count},"
                    f"{code}={clone_reference_count},added={watch_alias_count}")
            identity_reference_closures.setdefault(int(r), []).append({
                "kind": "general_enemy_watch.partner_alias",
                "source_code": str(boss_code),
                "clone_code": str(code),
                "source_reference_count": int(source_reference_count),
                "clone_reference_count": int(clone_reference_count),
                "verified": True,
            })
        clone_sources[code] = boss_code
        clone_watch_alias_counts[code] = watch_alias_count
        caster_dirty = True
        return code

    def make_standard_boss(r: int, index: int, boss_code: str,
                           hp_plan: dict, enemy_level: int) -> str:
        """克隆 standard_boss 代号，并把重写 DSL 暂存在内存资源覆盖层。"""
        nonlocal standard_dirty
        source_node = sb_t.get(boss_code)
        if not isinstance(source_node, dict):
            raise RuntimeError(f"第{r}战 standard clone 源代号缺失:{boss_code}")
        identity_block = identity_locked_boss_reason(
            [boss_code], code_references=code_refs)
        if identity_block:
            raise RuntimeError(f"第{r}战 standard clone 拒绝:{identity_block}")
        try:
            selected = int(hp_plan["selected_levels"][boss_code])
            blob = hp_plan["final_blobs"][boss_code]
            source_logical = str(hp_plan["source_logicals"][boss_code])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(
                f"第{r}战 standard clone 计划缺资源证据:{boss_code}") from exc
        actual_source = standard_boss_hp_evidence(
            boss_code, int(enemy_level), sb_t, standard_resource_blobs)
        if (int(actual_source["selected_level"]) != selected
                or str(actual_source["logical"]) != source_logical):
            raise RuntimeError(
                f"第{r}战 standard clone 源选档漂移:{boss_code} "
                f"plan={selected}/{source_logical},"
                f"actual={actual_source['selected_level']}/{actual_source['logical']}")
        clone_code = (f"{PRIVATE_PREFIX}standard{r}" if index == 0
                      else f"{PRIVATE_PREFIX}standard{r}_{index + 1}")
        resource_base = (f"battle/enemy/boss/{PRIVATE_PREFIX.rstrip(chr(95))}/"
                         f"standard_r{r}_{index + 1}")
        logical = resource_base + ".esdl.amf3.deflate"
        sb_t[clone_code] = clone_standard_boss_node(
            source_node, selected, resource_base)
        standard_resource_blobs[logical] = bytes(blob)
        forged_pubs.add(logical)
        hp_plan["destinations"][boss_code] = logical + "#forms.Health(T1)"
        readback = standard_boss_hp_evidence(
            clone_code, int(enemy_level), sb_t, standard_resource_blobs)
        if (int(readback["selected_level"]) != selected
                or str(readback["logical"]) != logical):
            raise RuntimeError(
                f"第{r}战 standard clone 回读选档漂移:{boss_code}->{clone_code}")
        standard_dirty = True
        return clone_code

    def gimmick_field(orig_field: str, r: int, panels: bool = False,
                      boss_swap: tuple[str, str] | None = None,
                      boss_swaps=()):
        """克隆 orig_field 的 field+zone:按需注入机兵皮机关 / 把单人 boss 槽
        (c24/c28/c32)换成施法克隆 boss。返回新 field 键(失败 None)。"""
        nonlocal gim_dirty
        frow = fd_t.get(orig_field)
        if frow is None:
            return None
        fc = cells(frow)
        zn = zone_t.get(fc[2])
        if not isinstance(zn, dict):
            return None
        zkey, fkey = f"{PRIVATE_PREFIX}z{r}", f"{PRIVATE_PREFIX}f{r}"
        swaps = list(boss_swaps or ())
        if boss_swap:
            swaps.append(boss_swap)
        nz = {}
        for wk, wrow in zn.items():
            if isinstance(wrow, dict):
                return None                       # 异形嵌套 zone,不折腾
            wc = cells(wrow)
            while len(wc) < 41:
                wc.append("")
            if panels:
                wc[36], wc[37] = GIM_DASH, GIM_ROT
            for old_code, new_code in swaps:
                apply_boss_swap(wc, old_code, new_code, kind_of=kind_fixer)
            nz[wk] = join(wc, isinstance(wrow, (bytes, bytearray)))
        zone_t[zkey] = nz
        nf = list(fc)
        nf[2] = zkey
        fd_t[fkey] = join(nf, isinstance(frow, (bytes, bytearray)))
        gim_dirty = True
        return fkey

    def tier_band(r: int) -> set[int]:
        """该关允许的楼层强度档:深度映射到 1..5,允许 ±1 浮动(伪随机的设计感)。"""
        t = 1 + round((r / args.rounds) * 4)
        return {max(1, t - 1), min(5, max(1, t)), min(5, t + 1)}

    def tower_pick(r: int | None = None) -> dict:
        pool_v = tower
        # 前 2 关允许杂兵热身,第 3 关起只出真 boss(2026-07-29:1/3 阈值让
        # 30 层塔的第 9 关还在打小怪)
        if r is not None and r >= 3:
            zkeys = set(map(str, gz_t))
            true_b = [e for e in tower
                      if not any(is_minion_boss(b, zkeys) for b in e[2])]
            if true_b:
                pool_v = true_b
        if r is not None:
            banded = [e for e in pool_v if floor_tier(e[0]) in tier_band(r)]
            if banded:
                pool_v = banded
            elif r / args.rounds > 0.5:
                hard = [e for e in pool_v if floor_tier(e[0]) >= 3]
                if hard:
                    pool_v = hard           # 过半程绝不回落到低档(简单 boss 禁入后段)
        pool_v = unused_only(pool_v, lambda e: e[2])
        pool_v = prefer_non_threat_candidates(
            pool_v, r, args.rounds, lambda e: e[2],
            high_threat_prefixes, high_threat_exact)
        cand = prefer_fresh(pool_v, lambda e: e[2])
        cand = weight_featured(cand, lambda e: e[2])
        e = cand[rng.randrange(len(cand))]
        tower.remove(e)
        f, line, bosses = e
        fc = cb._cols(line)
        return {"field": f, "bosses": bosses, "thumb": thumb_map.get(f, ""),
                "bgm": fc[1], "label": "塔·" + ",".join(bosses)}

    def mix_pick(r: int, pin_terrain: str | None = None,
                 pin_boss: str | None = None) -> dict | None:
        """模块化拼接层:地形楼层 × 另一楼层的 boss 组,独立随机。

        c69 恒跟 boss 老家元素(官方源 quest 或固定元素 boss,C8016 铁律);
        老家元素不可知的 boss 源直接不进拼接池(fail-closed)。地形的 zako/机关/
        BGM 保留,boss 槽整组换血;克隆层照旧过写入前链路复核。
        pin_terrain/pin_boss = 工坊按关钉选(floors.{N}.terrain / .boss);
        钉 boss 允许与其它关重复(用户显式指定),钉选不到返回 None 由外层报错。
        """
        nonlocal gim_dirty
        # Identity-lock rejection occurs after resolving both source and target,
        # but before any field/zone write.  Keep the pool snapshot so an
        # explicit incompatible pin is a real transaction failure rather than
        # a failure that quietly consumed one or two future candidates.
        pool_before = list(tower)
        if pin_terrain:
            terrain = next((e for e in tower if e[0] == pin_terrain), None)
            if terrain is None:
                terrain = next((e for e in tower_master if e[0] == pin_terrain), None)
            if terrain is None and pin_terrain in fd_t and field_gate(pin_terrain)["ok"]:
                terrain = (pin_terrain, None, [])       # 任意过门禁的场地都可当地形
            if terrain is None:
                print(f"[ERR] 第{r}战钉选地形 {pin_terrain} 不存在或没过门禁")
                return None
            if terrain in tower:
                tower.remove(terrain)
        else:
            sockets = load_socket_families()
            donors = [e for e in tower
                      if not any(str(b).startswith(sockets) for b in e[2])] if sockets else tower
            if not donors:
                donors = tower
            terrain = donors[rng.randrange(len(donors))]
            tower.remove(terrain)
        _terrain_row = fd_t.get(terrain[0])
        _terrain_cells = (cells(_terrain_row)
                          if isinstance(_terrain_row, (str, bytes, bytearray)) else [])
        _terrain_zone = (zone_t.get(_terrain_cells[2])
                         if len(_terrain_cells) > 2 else None)
        terrain_slot_count = len(zone_single_bosses(_terrain_zone))
        if terrain_slot_count <= 0:
            if terrain in tower_master and terrain not in tower:
                tower.append(terrain)
            print(f"[ERR] 第{r}战混搭地形 {terrain[0]} 没有单人 boss 实体槽")
            return None
        strict, safe_set = load_transplant_policy()
        if pin_boss:
            src_e = next((e for e in tower_master if pin_boss in e[2]), None)
            if src_e is None:                           # 塔池没有 → 搜全部来源池
                for lst in src.values():
                    hit = next((d for d in lst if pin_boss in d["bosses"]), None)
                    if hit is not None:
                        src_e = (hit["field"], None, hit["bosses"])
                        break
            if src_e is None:
                print(f"[ERR] 第{r}战钉选 boss {pin_boss} 不在任何门禁通过的池里")
                if not pin_terrain:
                    tower.append(terrain)
                return None
            if src_e in tower:
                tower.remove(src_e)
        else:
            cands = [e for e in tower
                     if len(e[2]) == terrain_slot_count
                     and (elem_map.get(e[0]) is not None
                          or any(belem_map.get(b) is not None for b in e[2]))]
            if not cands:
                tower.append(terrain)
                return None
            # strict_transplant 的语义是“只有白名单 donor 真能拼”。旧实现却先在
            # 全池随机，抽到非白名单就整场退回原味；30 层一次都没抽中安全 donor
            # 时 --mix 最终必失败。先在同一实体槽数内优先安全 donor，不放宽名单。
            compatible = [
                e for e in cands
                if not any(is_special_boss(b, special_bosses) for b in e[2])
                and mix_compatibility(e[0], terrain[0], e[2], r).ok
            ]
            if pin_terrain and not compatible:
                # Earlier rounds may have consumed every compatible donor from
                # the mutable tower pool.  A hard terrain pin may reuse a
                # proven donor from the immutable post-gate pool; it must not
                # reopen an incompatible fresh Boss merely to preserve quota.
                expanded_pool = list(tower_master)
                known_fields = {str(e[0]) for e in expanded_pool}
                for source_entries in src.values():
                    for source_entry in source_entries:
                        source_field = str(source_entry["field"])
                        if source_field in known_fields:
                            continue
                        known_fields.add(source_field)
                        expanded_pool.append((
                            source_field, None,
                            list(source_entry.get("bosses") or ())))
                expanded = [
                    e for e in expanded_pool
                    if len(e[2]) == terrain_slot_count
                    and (elem_map.get(e[0]) is not None
                         or any(belem_map.get(b) is not None for b in e[2]))
                ]
                compatible = [
                    e for e in expanded
                    if not any(is_special_boss(b, special_bosses) for b in e[2])
                    and mix_compatibility(e[0], terrain[0], e[2], r).ok
                ]
            if pin_terrain and not compatible:
                tower[:] = pool_before
                print(f"[ERR] 第{r}战钉选地形 {terrain[0]} 没有通过正式门禁的 Boss donor")
                return None
            # ⚠ 无条件收窄到白名单会让拼接层塌缩。rogue_special_bosses.json 的
            # transplant_safe 去掉杂鱼后**只剩 3 个去重键**(treant /
            # owl_single_tower / hermit_crab_another_light_single),配额一被吃光,
            # 下面 unused_only 的 `return kept or entries` 就把它们原样放回 =>
            # 30 层塔的拼接层恒定是「树妖×4 + 猫头鹰 + 寄居蟹」,16 个种子无一例外。
            # 改成**配额优先**:白名单里还有没出过的就用白名单;白名单全用完了才
            # 放开回全池——此时非白名单 donor 会走下面的「原味保护」分支,改用它
            # 自己的老家场地、不做跨地形移植,2026-07-28 那三次崩溃的防线不动。
            compatible_fresh = [e for e in compatible
                                if all(_quota_left(k) for k in name_keys(e[2]))]
            if pin_terrain and compatible:
                # A pinned terrain is a hard user constraint.  Once the
                # compatible donor subset is known, quota freshness may rank
                # within that subset but must never reopen incompatible Bosses
                # and turn a solvable pin into a late TRANSPLANT_POLICY error.
                cands = compatible_fresh or compatible
            elif compatible_fresh:
                cands = compatible_fresh
            elif compatible and not any(
                    all(_quota_left(k) for k in name_keys(e[2])) for e in cands):
                cands = compatible
            if r >= 3:
                zkeys = set(map(str, gz_t))
                true_b = [e for e in cands
                          if not any(is_minion_boss(b, zkeys) for b in e[2])]
                if true_b:
                    cands = true_b
            banded = [e for e in cands if floor_tier(e[0]) in tier_band(r)]
            if banded:
                cands = banded                  # 深关只抽高档 boss(设计感排布)
            elif r / args.rounds > 0.5:
                hard = [e for e in cands if floor_tier(e[0]) >= 3]
                if hard:
                    cands = hard
            cands = unused_only(cands, lambda e: e[2])
            cands = prefer_non_threat_candidates(
                cands, r, args.rounds, lambda e: e[2],
                high_threat_prefixes, high_threat_exact)
            cands = prefer_fresh(cands, lambda e: e[2])
            src_e = cands[rng.randrange(len(cands))]
            if src_e in tower:
                tower.remove(src_e)
        tf, tline, _tb = terrain
        sf, _sline, sbosses = src_e
        identity_block = identity_locked_boss_reason(
            sbosses, code_references=code_refs)
        identity_move_block = identity_locked_mix_reason(
            sbosses, sf, tf, code_references=code_refs)
        if identity_block:
            # Never synthesize mod_rogue_f/z for a hard-ref boss, even when the
            # selected terrain happens to be its own: preserve the native
            # field, zone, master id, actions, and funnel anchors as one unit.
            tower[:] = pool_before
            if identity_move_block and pin_terrain:
                print(f"[ERR] 第{r}战钉选组合拒绝:{identity_move_block}; "
                      "未创建 field/zone，塔池已回滚")
                return None
            if not pin_boss and src_e in tower:
                tower.remove(src_e)
            log(f"[身份锁] round={r} {identity_block}; 随机混搭回退原味 {sf}")
            return {"field": sf, "bosses": list(sbosses),
                    "thumb": thumb_map.get(sf, ""),
                    "bgm": (cb._cols(_sline)[1] if _sline else None),
                    "label": "原味·" + ",".join(sorted(set(sbosses)))}
        compatibility = mix_compatibility(sf, tf, sbosses, r)
        if not compatibility.ok:
            # 随机混搭遇到未证明组合就回 Boss 原生场地；显式钉选了 terrain
            # 时不得静默改场地，直接让事务失败并报告精确门禁原因。
            tower[:] = pool_before
            if pin_terrain:
                print(f"[ERR] 第{r}战钉选组合拒绝:"
                      f"{compatibility.reason}:{compatibility.detail}")
                return None
            if not pin_boss and src_e in tower:
                tower.remove(src_e)
            log(f"[地形门禁] round={r} {sf}->{tf} reject="
                f"{compatibility.reason}:{compatibility.detail}; 回退原味")
            return {"field": sf, "bosses": sbosses,
                    "thumb": thumb_map.get(sf, ""),
                    "bgm": (cb._cols(_sline)[1] if _sline else None),
                    "label": "原味·" + ",".join(sorted(set(sbosses)))}
        if len(sbosses) != terrain_slot_count:
            if not pin_terrain and terrain not in tower:
                tower.append(terrain)
            if not pin_boss and src_e not in tower:
                tower.append(src_e)
            print(f"[ERR] 第{r}战混搭实体数不匹配:"
                  f"地形{terrain_slot_count}槽 / donor {len(sbosses)}只")
            return None
        frow = fd_t[tf]
        fc = cells(frow)
        zkey, fkey = f"{PRIVATE_PREFIX}z{r}", f"{PRIVATE_PREFIX}f{r}"
        zone_t[zkey] = swap_zone_bosses(zone_t[fc[2]], sbosses,
                                        kind_of=kind_fixer)
        realized_bosses = zone_single_bosses(zone_t[zkey])
        if realized_bosses != list(sbosses):
            raise RuntimeError(
                f"第{r}战混搭 boss 实体不一致:donor={sbosses},realized={realized_bosses}")
        nf = list(fc)
        nf[2] = zkey
        fd_t[fkey] = join(nf, isinstance(frow, (bytes, bytearray)))
        gim_dirty = True
        elem = elem_map.get(sf)
        if elem is None:
            elem = next((belem_map[b] for b in sbosses if belem_map.get(b) is not None), None)
        return {"field": fkey, "bosses": realized_bosses,
                # The quest list is advertising the encountered boss, not the
                # transplanted arena.  The old tf lookup is why a mixed floor
                # could show a perfectly valid but completely different boss.
                "thumb": thumb_map.get(sf, ""), "thumbnail_field": sf,
                "bgm": (cb._cols(tline)[1] if tline else None),
                "elem_override": elem, "boost_field": tf,
                "label": f"拼·{','.join(sbosses)} @ {tf}",
                # 供任务 C 重排时原地更换 donor，不丢失 --mix 语义。
                "_mix_terrain_entry": terrain, "_mix_boss_entry": src_e,
                "_mix_slot_count": terrain_slot_count}

    # ---- 楼层计划 v8(module 级 build_schedule):任意层数自适应 ----
    if args.rounds < 2:
        print("[ERR] rounds 最少 2(1 层塔 + 末层始龙)")
        return 1
    if args.rounds > 98:
        print("[ERR] rounds 最多 98(99 是无尽档专用键)")
        return 1
    schedule = build_schedule(args.rounds, rng)
    if args.strict_target_hp and args.rounds >= 30 and native_special_bundles:
        _special_labels = {
            "orochi": "八岐大蛇", "orochi_ex": "八岐大蛇EX",
            "conductor": "指挥者", "touyakiren_ceo": "东亚奇廉CEO",
            "kraken": "克拉肯", "water_sphere": "水之球体",
            "holy_sphere": "圣之球体", "wind_sphere": "风之球体",
            "thunder_sphere": "雷之球体", "fire_sphere": "火之球体",
        }
        _available_specials = {
            str(special_bundle_family(bundle))
            for bundle in native_special_bundles
            if special_bundle_family(bundle)
        }
        for _family_name, _fraction in special_showcase_slots(
                _available_specials, rng, rounds=args.rounds):
            _label = _special_labels[_family_name]
            _special_round = reserve_schedule_slot(
                schedule, args.rounds, _label, fraction=_fraction)
            if _special_round is None:
                print(f"[WARN] 严格塔没有空闲深层槽，{_label} 本轮明确排除")
            else:
                print(f"[专用HP] 第{_special_round}战预留{_label}原生专场")
    PICKERS = {"小怪房": zako_pick, "终始之龙": finale_pick,
               "杂鱼boss": minion_pick, "机工神兵": phenomena_pick,
               "八岐大蛇": orochi_pick,
               "八岐大蛇EX": orochi_ex_pick,
               "克拉肯": kraken_pick,
               "指挥者": conductor_pick,
               "东亚奇廉CEO": touyakiren_ceo_pick,
               "水之球体": lambda: sphere_pick("water_sphere"),
               "圣之球体": lambda: sphere_pick("holy_sphere"),
               "风之球体": lambda: sphere_pick("wind_sphere"),
               "雷之球体": lambda: sphere_pick("thunder_sphere"),
               "火之球体": lambda: sphere_pick("fire_sphere"),
               "领主战": lambda: src_pick("领主战"), "机兵": lambda: src_pick("机兵"),
               "降临讨伐": lambda: src_pick("降临讨伐"),
               "女帝歼灭者": lambda: src_pick("女帝歼灭者"),
               "世界剧情": lambda: src_pick("世界剧情"),
               "剧情活动": lambda: src_pick("剧情活动"),
               "无幻之宴": lambda: src_pick("无幻之宴"),
               "战阵之宴": lambda: src_pick("战阵之宴"),
               "单人挑战": lambda: src_pick("单人挑战"),
               "极时试炼": lambda: src_pick("极时试炼"),
               "剧情boss": lambda: src_pick("剧情boss"),
               "元素试炼": lambda: src_pick("元素试炼"),
               "土俑嘉年华": lambda: src_pick("土俑嘉年华"),
               "主线boss": lambda: src_pick("主线boss")}

    # ---- 简单来源难度补偿(叠乘在轮次曲线上)----
    # 小怪房/主线领主战是低等级内容,只吃轮次曲线会白给;塔层按区域深浅补
    # (区域≤6 浅层显著补,7-8 轻补,9-10 本就是高难不补)。
    # 杂鱼boss:主线小怪提拔族,基础数值比正经 boss 低一档,补偿介于小怪房与领主战之间
    SRC_BOOST = {"小怪房": (2.5, 1.6), "杂鱼boss": (2.2, 1.5), "领主战": (1.8, 1.4)}
    # 归一化锚点:用**本塔实际用到的全部 boss**算每条修正曲线的基数中位数
    _all_codes = {b for e in tower_master for b in e[2]}
    for _lst in list(src.values()) + [zako_lst, minion_lst]:
        for _e in _lst:
            _all_codes |= set(_e.get("bosses") or [])
    _hp_med, _atk_med = curve_medians(_all_codes)
    if args.normalize:
        print(f"[归一] 基数中位锚 hp={ {k: round(v) for k, v in _hp_med.items()} } "
              f"HP clamp {args.normalize_min}–{args.normalize_max}× / "
              f"ATK clamp {args.normalize_min}–{args.normalize_atk_max}×"
              f"(standard 系无 boss_level 条目,不参与)")

    def tower_area_boost(field: str) -> tuple[float, float]:
        m = re.match(r"tower_dungeon_+area_(\d+)_", field)
        if not m:
            return (1.0, 1.0)
        area = int(m.group(1))
        if area <= 6:
            return (1.6, 1.3)
        if area <= 8:
            return (1.3, 1.15)
        return (1.0, 1.0)

    def patch_common(row: list[str], name: str, pick: dict) -> str:
        row[4] = name
        row[7] = START
        row[8] = END
        row[67] = "0"                                    # 体力
        # 楼层等级在循环里按爬坡档已经算好(pick["level"]);无尽档等走老路。
        level = (pick.get("level")
                 or resolve_level(pick["bosses"], args.enemy_level, sb_t, gv_t,
                                  gb_t, prefer_max=want_max)
                 or args.enemy_level)
        source_elements = dict(elem_map)
        if pick.get("elem_override") is not None:
            source_elements[pick["field"]] = int(pick["elem_override"])
        thumbnail_field = str(
            pick.get("thumbnail_field") or pick.get("field") or "")
        thumbnail, thumbnail_evidence = resolve_quest_thumbnail(
            thumbnail_field, pick.get("thumb"), thumbnail_evidence_map,
            require=bool(pick["bosses"]))
        pick["thumb"] = thumbnail
        pick["thumbnail_field"] = thumbnail_field
        pick["thumbnail_evidence"] = thumbnail_evidence
        elem, tag = patch_quest_boss_fields(
            row,
            field=pick["field"],
            play_field=pick.get("play_field"),
            bosses=pick["bosses"],
            thumbnail=thumbnail,
            bgm=pick.get("bgm"),
            enemy_level=int(level),
            rng=rng,
            field_elements=source_elements,
            boss_elements=belem_map,
            require_thumbnail=bool(pick["bosses"]),
            thumbnail_asset_exists=q.exists_current,
        )
        return f" 属性:{ELEM_CN[elem] if elem < 6 else '无'}{tag}"

    ex_lane_audit = abyss_ex.NativeLaneAudit(q.read_raw, wf_dsl.parse_dsl, cells, join)
    _hp_fit_cache: dict[tuple[str, int, float], dict | None] = {}
    _hp_fit_rejects: dict[tuple[str, int, float], str] = {}

    def hp_pick_metrics(pick: dict, r: int, target: float) -> dict | None:
        """按真实等级决定候选的 HP 主通道；不可缩放即不进候补。"""
        field = str(pick["field"])
        bundle = pick.get("native_bundle")
        cache_field = (f"{field}#{bundle.variant_id}"
                       if isinstance(bundle, rbb.NativeBossBundle) else field)
        key = (cache_field, r, round(float(target), 6))
        if key in _hp_fit_cache:
            return _hp_fit_cache[key]
        if isinstance(bundle, rbb.NativeBossBundle):
            family = special_bundle_family(bundle)
            if family == "orochi":
                native = orochi_native_hp_evidence(
                    bundle, 100, orochi_tables)
            elif family == "orochi_ex":
                native = orochi_ex_native_hp_evidence(
                    bundle, 100, orochi_tables)
            elif family in SINGLE_BAR_SPECIAL_SPECS:
                native = single_bar_special_native_hp_evidence(
                    bundle, 100, orochi_tables)
            elif family in SPHERE_SPECS:
                native = sphere_native_hp_evidence(
                    bundle, 100, orochi_tables)
            else:
                native = {
                    "native_hp": None, "verified": False,
                    "reason": "unknown native special family",
                }
            if not native.get("verified") or native.get("native_hp") is None:
                _hp_fit_rejects[key] = str(
                    native.get("reason") or "special HP evidence unavailable")
                _hp_fit_cache[key] = None
                return None
            if family == "orochi":
                level = int(native["expanded"].selected_parent_level)
            else:
                level = int(native["graph"].selected_level)
            required_c86 = float(fmt(solve_hp_correction(
                target, float(tmpl_rn[100]) / 60.0,
                float(native["native_hp"]))))
            if family in SPHERE_SPECS:
                try:
                    sphere_hp_scale_plan(
                        native, bl_t,
                        target_hp=(float(target) * float(tmpl_rn[100]) / 60.0),
                        curse_hp=1.0)
                except ValueError as exc:
                    _hp_fit_rejects[key] = str(exc)
                    _hp_fit_cache[key] = None
                    return None
            metrics = {
                "level": level, "native": native,
                "required_c86": required_c86,
                "baseline_c86": 1.0,
                "baseline_scale": required_c86,
                "hp_channel": "special_bundle",
                "hp_family": family,
                "selected_levels": {
                    str(component["code"]): int(component["selected_level"])
                    for component in native["components"]
                },
            }
            _hp_fit_cache[key] = metrics
            return metrics
        bosses = list(pick.get("bosses") or _zone_pick(field)[0])
        if not bosses:
            _hp_fit_cache[key] = None
            return None
        level = int(resolve_level(bosses, want_level(r), sb_t, gv_t, gb_t,
                                  prefer_max=want_max) or want_level(r))
        if BUILD_MODE == "ex":
            try:
                if is_high_threat_bosses(bosses, high_threat_prefixes, high_threat_exact):
                    raise ValueError("high-threat Boss conflicts with mandatory EX element restrictions")
                if r < 30 and abyss_modes.is_five_boss_source(field, bosses):
                    raise ValueError("five-boss actors are reserved for floor 30")
                if any(str(code).startswith(("mod_rogue_", "mod_abyss_ex_")) for code in bosses):
                    raise ValueError("generated Bosses cannot be reused as native donors")
                lanes, evidence = ex_lane_audit.audit(bosses, level, gb_t, select_surjective_level)
                pick["ex_native_lanes"] = sorted(lanes)
                pick["ex_native_evidence"] = evidence
            except (ValueError, FileNotFoundError, KeyError, IndexError) as exc:
                _hp_fit_rejects[key] = "hp-plan-unsafe:" + str(exc)
                _hp_fit_cache[key] = None
                return None
        native = floor_native_hp(
            bosses, level, sb_t,
            standard_runtime_hp_scale=RUSH_EVENT_STANDARD_HP_SCALE)
        if not native.get("verified") or native.get("native_hp") is None:
            _hp_fit_cache[key] = None
            return None
        required_c86 = float(fmt(solve_hp_correction(
            target, float(tmpl_rn[100]) / 60.0,
            float(native["native_hp"]))))
        try:
            strategy = floor_hp_scaling_strategy(
                bosses, native, gb_t, bl_t, level,
                required_c86=required_c86,
                deep=is_deep_round(r, args.rounds),
                code_references=code_refs, standard_boss=sb_t,
                general_boss_state=gbs_t)
            if strategy["channel"] == "standard_dsl":
                # Trial scripts can parse correctly but lack an absolute HP
                # dependency proof. Reject before selection, not after cloning.
                try:
                    standard_hp_scale_plan(
                        bosses, native, sb_t, level,
                        target_hp=float(target) * float(tmpl_rn[100]) / 60.0,
                        curse_hp=1.0, code_references=code_refs)
                except ValueError as exc:
                    raise ValueError(f"hp-plan-unsafe:{exc}") from exc
        except ValueError as exc:
            _hp_fit_rejects[key] = str(exc)
            _hp_fit_cache[key] = None
            return None
        metrics = {
            "level": level, "native": native,
            "required_c86": required_c86,
            "baseline_c86": float(strategy["baseline_c86"]),
            "baseline_scale": float(strategy["baseline_scale"]),
            "hp_channel": strategy["channel"],
            "hp_family": strategy["family"],
            "selected_levels": strategy["selected_levels"],
            "adapter_mode": strategy.get("adapter_mode"),
            "absolute_after_adaptation": bool(
                strategy.get("absolute_after_adaptation")),
        }
        _hp_fit_cache[key] = metrics
        return metrics

    def hp_curve_fit_pick(current: dict, r: int, target: float,
                          field_needed: int = 0, *,
                          element_required: bool = False,
                          carrier_required: bool = False,
                          pinned_boss: str | None = None,
                          pinned_terrain: bool = False,
                          forbidden_cooldown_group: str | None = None) -> dict:
        """数值/领域不合规时重排，并优先保住可挂属性免疫的实际载体。"""
        current_metrics = hp_pick_metrics(current, r, target)
        current_key = (str(current["field"]), r, round(float(target), 6))
        current_hp_reject = _hp_fit_rejects.get(current_key)
        if current_hp_reject and "identity-locked" in current_hp_reject:
            log(f"[HP重排] round={r} reject="
                f"{','.join(map(str, current.get('bosses') or []))} "
                f"reason={current_hp_reject}")
        def carrier_ok(pick: dict, *, preserve_mix: bool = True) -> bool:
            bosses = list(pick.get("bosses") or [])
            target = next((b for b in bosses if b in belem_map), None)
            if target is None:
                return False
            # 候选扫描只读判据，不写 caster_blocked；真正选中后 field_caps()
            # 会登记门禁理由。否则扫描几百个候选会把未使用场地污染进最终报告。
            return caster_carrier_block(
                (current["field"] if (preserve_mix
                                      and current.get("_mix_terrain_entry"))
                 else pick["field"]),
                bosses, fd_t, zone_t, phase_linked, gb_t,
                refs=code_refs) is None

        def element_carrier_block(pick: dict, metrics: dict | None, *,
                                  preserve_mix: bool = True) -> str | None:
            if metrics is None:
                return "没有可审计的 HP/等级证据"
            bosses = list(pick.get("bosses") or [])
            field_id = (current["field"] if (preserve_mix
                                              and current.get("_mix_terrain_entry"))
                        else pick["field"])
            status = carrier_status(
                field_id, bosses, int(metrics["level"]), record=False)
            return None if status["element"] else str(status["element_reason"])

        def reject_reason(pick: dict, metrics: dict | None, *,
                          preserve_mix: bool = True) -> str | None:
            """候选不合格的**原因**;None=合格。

            区分原因是为了让「只有血量带不达标」这一类不再触发换 boss,
            见下方 HP_BAND_ONLY 处的说明。"""
            if (forbidden_cooldown_group
                    and boss_family_cooldown_group(pick.get("bosses") or ())
                    == forbidden_cooldown_group):
                return f"family-cooldown:{forbidden_cooldown_group}"
            if metrics is None:
                plan_error = _hp_fit_rejects.get((
                    str(pick["field"]), r, round(float(target), 6)), "")
                if plan_error.startswith("hp-plan-unsafe:"):
                    return "hp-plan-unsafe"
                # 必须把「血量按不动」与「这层压根解析不了」分开。
                # hp_pick_metrics 里 `resolve_level(...) or want_level(r)` 会把
                # None 吞成想要的等级,于是不可解析的层看起来只是「无 HP 证据」。
                # 但它落表就是引用悬空(clone 在该敌等级下找不到 boss_level 档位,
                # 进本必崩),这是硬错误不是带宽偏好——必须继续重排。
                # 实例:--ramp 把第28战钉死 lv100 时的 discarded_dragon_thunder_tower
                # (gb/gv 都只有 80 档)。
                #
                # ⚠ 判据必须用门禁同款的 select_surjective_level(客户端
                # getSurjectivity = **上取整**),不能用 resolve_level/boss_level_ok
                # ——后两者走**下取整**,2026-08-05 修正取档方向后就与门禁不一致了:
                # 上例 boss_level_ok(code,100)=True 而门禁返回 None。这个矛盾一直
                # 存在,只是以前「不合格就换掉整层」把它盖住了。
                bosses = list(pick.get("bosses") or [])
                if bosses:
                    lv = int(resolve_level(bosses, want_level(r), sb_t, gv_t,
                                           gb_t, prefer_max=want_max)
                             or want_level(r))
                    for code in bosses:
                        node = (sb_t.get(code) if code in sb_t
                                else gb_t.get(code) if code in gb_t else None)
                        if node is not None and select_surjective_level(
                                node, lv) is None:
                            return "level"
                return "hp-no-evidence"
            if ((field_needed or carrier_required)
                    and not carrier_ok(pick, preserve_mix=preserve_mix)):
                return "carrier"
            if preserve_mix and current.get("_mix_terrain_entry"):
                # HP 重排不得把混搭层偷换回原场地；候补 Boss 同样必须通过
                # ActionDSL/ESDL→命名坐标/Funnel→目标 terrain 的完整门禁。
                bosses = list(pick.get("bosses") or [])
                # c86-window 内的 identity-locked general 仍是合格的原味
                # 候选，但绝不能借 HP donor 重排进入已克隆的异地 zone。
                # Whole-field fallback (preserve_mix=False) remains legal.
                identity_block = identity_locked_boss_reason(
                    bosses, code_references=code_refs)
                terrain_entry = current.get("_mix_terrain_entry")
                target_field = str(terrain_entry[0])
                source_entry = pick.get("_mix_boss_entry")
                source_field = (str(source_entry[0]) if source_entry
                                else str(pick.get("field") or ""))
                compatibility = mix_compatibility(
                    source_field, target_field, bosses, r)
                if (identity_block
                        or len(bosses) != int(current.get("_mix_slot_count") or 0)
                        or not compatibility.ok
                        or any(is_special_boss(b, special_bosses) for b in bosses)):
                    return "transplant"
            if (args.rounds == 30 and is_deep_round(r, args.rounds)
                    and not metrics["native"].get("absolute_verified")):
                return "hp-deep-unverified"
            if args.strict_target_hp:
                strict_error = strict_hp_candidate_error(metrics)
                if strict_error:
                    return strict_error
            return None

        def acceptable(pick: dict, metrics: dict | None, *,
                       preserve_mix: bool = True) -> bool:
            return reject_reason(
                pick, metrics, preserve_mix=preserve_mix) is None

        # 只靠“换一只 boss”才能满足的血量带原因。缩放解决不了它们:
        # 这些 boss 压根没有可审计的 HP 通道(无 boss_level 基数/读不出 c86),
        # 或深层要求的绝对证据缺失。
        #
        # 2026-08-05 的 86e27250 对这两类一律整层替换,实测 30 层塔 20 层被换掉,
        # 连策展锚位(机兵/女帝歼灭者/土俑嘉年华/五元素球/东亚奇廉CEO)与
        # 三个守门固定位(终始之龙/无幻之宴/机工神兵菲诺梅那)都被扔进了塔池,
        # 且替换目标高度集中(白虎×3/异质魔晶羊×3/伊尔昂斯拉×3)。
        #
        # 作者的原始要求(6d7dec0)是**压低敌方攻击**,从未要求按血量换 boss。
        # 故改为非破坏性:能缩放的照常缩放进带内,缩放不了的原样保留。
        # 带宽因此只在做得到的层生效,[真HP门禁] 会如实计入“无boss估算 N 层”。
        HP_BAND_ONLY = ("hp-no-evidence", "hp-deep-unverified")

        current_reason = reject_reason(current, current_metrics)
        current_ok = current_reason is None
        # 策展锚位不得仅因随机抽到的领域法阵缺少 general_boss c109 载体
        # 就换掉整只 boss。Standard DSL 适配上线前，这些层会以
        # hp-no-evidence 走下方的非破坏性保留；现在 HP 已可绝对回读，反而
        # 会暴露为 carrier 并触发重排。这里恢复原契约：HP 本身安全可调就
        # 保留原层，让后续诅咒门禁明确记录领域欠配。严格模式也只因严格 HP
        # 失败而重抽，不能把“随机领域载体”冒充 HP 失败。
        curated_hp_ok = (
            current_metrics is not None
            and (not args.strict_target_hp
                 or strict_hp_candidate_error(current_metrics) is None)
        )
        if (current_reason == "carrier" and curated_hp_ok
                and not element_required and not carrier_required):
            log(f"[HP重排] round={r} 保留策展层({current['label']}):"
                "HP 通道可审计；随机领域载体欠配不得换 boss")
            return current
        if args.strict_target_hp and not current_ok:
            log(
                f"[严格HP排除] round={r} bosses="
                f"{','.join(map(str, current.get('bosses') or [])) or current['field']} "
                f"reason={current_hp_reject or current_reason}")
        if (not args.strict_target_hp
                and not current_ok and current_reason in HP_BAND_ONLY
                and not element_required):
            log(f"[HP重排] round={r} 保留当前层("
                f"{','.join(map(str, current.get('bosses') or [])) or current['field']}"
                f"):{current_reason},血量带无法靠缩放实现;"
                "按非破坏性策略不换 boss")
            return current
        current_element_block = (element_carrier_block(current, current_metrics)
                                 if element_required else None)
        if current_ok:
            if not element_required or current_element_block is None:
                return current
            if pinned_boss:
                raise RuntimeError(
                    f"第{r}战钉选 boss {pinned_boss} 与属性免疫冲突:"
                    f"{current_element_block}; 显式 boss/诅咒均不允许静默改派")
            log(f"[HP重排] round={r} 工坊属性免疫要求保留载体，"
                f"当前 {current['field']} 不适用({current_element_block}); 搜索替代 boss")
        elif pinned_boss:
            # 显式 boss 是工坊硬约束；不能为满足平坦 HP 或领域槽而暗换成另一只。
            # 若还同时钉了属性免疫，优先把真实载体阻断理由报给作者。
            if (args.strict_target_hp
                    and current_reason in {
                        "hp-no-evidence", "hp-deep-unverified",
                        "strict-no-hp-plan", "strict-no-absolute-readback",
                        "strict-proxy-evidence",
                    }):
                raise RuntimeError(
                    f"第{r}战钉选 boss {pinned_boss} 严格 HP 无法实现:"
                    f"{current_hp_reject or current_reason}; 显式 pin 不允许暗换 boss")
            if current_hp_reject and "identity-locked" in current_hp_reject:
                raise RuntimeError(
                    f"第{r}战钉选 boss {pinned_boss} HP 无法实现:"
                    f"{current_hp_reject}; 显式 pin 不允许暗换 boss")
            why = (current_element_block
                   or ("该 boss 没有 general_boss c109 条件载体"
                       if carrier_required else "该 boss 无法满足本层 HP/领域硬闸"))
            raise RuntimeError(
                f"第{r}战钉选 boss {pinned_boss} 与属性免疫冲突:{why}; "
                "显式 boss/诅咒均不允许静默改派")

        registry: dict[str, dict] = {}

        def add(field: str, label: str, thumb: str = "", bgm=None) -> None:
            if field in registry:
                return
            bosses, _ = _zone_pick(field)
            if not bosses or not _pool_safe(bosses):
                return
            rep = field_gate(field)
            if not rep["ok"]:
                return
            disp = "、".join(dict.fromkeys(
                str(_boss_names.get(b, b)).split("/")[0] for b in bosses))
            registry[field] = {
                "field": field, "bosses": bosses,
                "thumb": thumb or thumb_map.get(field, ""), "bgm": bgm,
                "label": f"HP重排·{label}·{disp or field}",
            }

        for source_label, entries in src.items():
            for entry in entries:
                add(str(entry["field"]), source_label,
                    str(entry.get("thumb") or ""), None)
        for field, line, _bosses in tower_master:
            fc = cb._cols(line)
            add(str(field), "塔", thumb_map.get(field, ""),
                fc[1] if len(fc) > 1 else None)
        if args.rounds == 30:
            for field in (EARLY_HP_FALLBACK_FIELDS_30
                          + MID_HP_ANCHOR_FIELDS_30
                          + DEEP_HP_ANCHOR_FIELDS_30):
                add(field, "血量保底")

        zkeys = set(map(str, gz_t))
        def collect_ranked(*, allow_quota_reuse: bool = False,
                           preserve_mix: bool = True,
                           element_only: bool = False) -> list[tuple]:
            found: list[tuple] = []
            for candidate in registry.values():
                bosses = candidate["bosses"]
                if r >= 3 and any(is_minion_boss(b, zkeys) for b in bosses):
                    continue
                if (not allow_quota_reuse
                        and not all(_quota_left(k) for k in name_keys(bosses))):
                    continue
                metrics = hp_pick_metrics(candidate, r, target)
                if not acceptable(candidate, metrics, preserve_mix=preserve_mix):
                    continue
                metrics = dict(metrics)
                metrics["element_immunity_block"] = element_carrier_block(
                    candidate, metrics, preserve_mix=preserve_mix)
                clone_hp_channel = metrics["hp_channel"] in {
                    "boss_level", "standard_dsl", "mixed_hp", "special_bundle"}
                scale = (float(metrics["baseline_scale"])
                         if clone_hp_channel
                         else float(metrics["baseline_c86"]))
                # 可克隆 HP 通道优先；其次绝对证据/新面孔/较小的伸缩幅度。
                score = (
                    0 if clone_hp_channel else 1,
                    0 if metrics["native"].get("absolute_verified") else 1,
                    1 if set(bosses) & recent_bosses else 0,
                    abs(math.log(scale)),
                    candidate["field"],
                )
                found.append((score, candidate, metrics))
            if element_only:
                preferred, downgraded = prefer_element_immunity_hp_candidates(found)
                found = [] if downgraded else preferred
            return prefer_non_threat_candidates(
                found, r, args.rounds, lambda item: item[1]["bosses"],
                high_threat_prefixes, high_threat_exact)

        def collect_pipeline(*, element_only: bool) -> tuple[list[tuple], bool, str | None]:
            """完整跑一次严格/mix/短塔配额管线；元素优先失败后才跑普通管线。"""
            found = collect_ranked(element_only=element_only)
            whole_field_fallback = False
            quota_reuse_scope = None
            if (not found and current.get("_mix_terrain_entry")
                    and not pinned_terrain):
                # 严格移植白名单没有 donor 时，完整尝试安全原场地；元素池与
                # 普通池各自跑完这条链，不能看见一个不合格 donor 就提前降级。
                found = collect_ranked(
                    preserve_mix=False, element_only=element_only)
                if not found:
                    found = collect_ranked(
                        allow_quota_reuse=True, preserve_mix=False,
                        element_only=element_only)
                whole_field_fallback = bool(found)
            if not found and (args.rounds != 30 or args.mix):
                # 任意塔高的旧行为是“池子枯竭才允许重复”。30 层成品塔
                # 候选足够，仍严格保持配额；短塔不因固定锦标预留而无解。
                found = collect_ranked(
                    allow_quota_reuse=True, element_only=element_only)
                if found:
                    quota_reuse_scope = "混搭池" if args.mix else "短塔"
            return found, whole_field_fallback, quota_reuse_scope

        # HP 确需重排时，随机诅咒也优先获得可挂属性免疫的载体；工坊钉选则
        # 额外让“HP 已合格但载体不合格”的当前 boss 进入同一条搜索链。
        prefer_element = element_required or not carrier_required
        ranked, mix_whole_field_fallback, quota_reuse_scope = collect_pipeline(
            element_only=prefer_element)
        if not ranked:
            scope = ("工坊钉选属性免疫" if element_required else
                     ("工坊钉选 c109 条件" if carrier_required else
                      "随机属性免疫软约束"))
            if current_ok and element_required:
                # 用户规格明确要求软约束耗尽后回退原逻辑，但必须留痕；显式
                # pinned_boss 的冲突已在上方硬失败，不会走到这里吞掉两份 pin。
                why = current_element_block or "候选池没有实际 c109/c36 合格载体"
                log(f"[HP重排] round={r} {scope}无合格载体候选，"
                    f"已保留当前 boss；后续诅咒门禁将明确 redraw({why})")
                return current
            ranked, mix_whole_field_fallback, quota_reuse_scope = collect_pipeline(
                element_only=False)
            log(f"[HP重排] round={r} {scope}无合格载体候选，已降级为普通 HP 重排；"
                "后续诅咒门禁将 redraw")
        if not ranked:
            got = ("无原生 HP 证据" if current_metrics is None
                   else (f"{current_metrics['hp_channel']}×"
                         f"{current_metrics['baseline_scale']:g}"
                         if current_metrics["hp_channel"] in {
                             "boss_level", "standard_dsl", "mixed_hp", "special_bundle"}
                         else f"c86={current_metrics['baseline_c86']:g}"))
            raise RuntimeError(
                f"第{r}战当前候选{got}且正式池没有可审计 HP 克隆或 "
                f"c86 {STANDARD_C86_LIMITS[0]:g}~{STANDARD_C86_LIMITS[1]:g} 的替代 boss")
        if quota_reuse_scope:
            log(f"[HP重排] round={r} 唯一配额候选耗尽，"
                f"按旧池规则允许{quota_reuse_scope}重用")
        ranked.sort(key=lambda item: item[0])
        # 在同等优质的前八项中保留 seed 随机性；窗口、证据、去重仍是硬条件。
        _score, chosen, chosen_metrics = ranked[rng.randrange(min(8, len(ranked)))]
        old = ("无证据" if current_metrics is None
               else (f"{current_metrics['hp_channel']}×"
                     f"{current_metrics['baseline_scale']:g}"
                     if current_metrics["hp_channel"] in {
                         "boss_level", "standard_dsl", "mixed_hp", "special_bundle"}
                     else f"c86={current_metrics['baseline_c86']:g}"))
        new = (f"{chosen_metrics['hp_channel']}×"
               f"{chosen_metrics['baseline_scale']:g}"
               if chosen_metrics["hp_channel"] in {
                   "boss_level", "standard_dsl", "mixed_hp", "special_bundle"}
               else f"c86={chosen_metrics['baseline_c86']:g}")
        log(f"[HP重排] round={r} {current['field']}({old}) -> "
            f"{chosen['field']}({new})")
        if current.get("_mix_terrain_entry") and not mix_whole_field_fallback:
            # 保留已选地形，只把混搭 zone 的 boss donor 换成可行候选。
            # 原 donor 之前已从 tower 移除；现在没用上就必须归还，
            # 否则一次重排会吞三个池条目并留下孤儿克隆。
            frow = fd_t.get(current["field"])
            fc = cells(frow) if isinstance(frow, (str, bytes, bytearray)) else []
            if len(fc) <= 2 or not isinstance(zone_t.get(fc[2]), dict):
                raise RuntimeError(f"第{r}战混搭 HP 重排找不到已克隆 zone")
            zone_t[fc[2]] = swap_zone_bosses(zone_t[fc[2]], chosen["bosses"],
                                             kind_of=kind_fixer)
            realized_bosses = zone_single_bosses(zone_t[fc[2]])
            if realized_bosses != list(chosen["bosses"]):
                raise RuntimeError(
                    f"第{r}战混搭 HP 重排实体不一致:"
                    f"donor={chosen['bosses']},realized={realized_bosses}")
            old_donor = current.get("_mix_boss_entry")
            if (isinstance(old_donor, tuple) and old_donor not in tower
                    and old_donor[0] != chosen["field"]):
                tower.append(old_donor)
            current["bosses"] = realized_bosses
            current["elem_override"] = (
                elem_map.get(chosen["field"])
                if elem_map.get(chosen["field"]) is not None else
                next((belem_map.get(b) for b in chosen["bosses"]
                      if belem_map.get(b) is not None), None))
            current["label"] = (
                f"拼·{','.join(chosen['bosses'])} @ {current.get('boost_field')}"
                f"（HP重排:{chosen['field']}）")
            current["_mix_boss_entry"] = next(
                (e for e in tower if e[0] == chosen["field"]), None)
            for entry in list(tower):
                if entry[0] == chosen["field"]:
                    tower.remove(entry)
                    break
            return current
        if current.get("_mix_terrain_entry") and mix_whole_field_fallback:
            frow = fd_t.pop(current["field"], None)
            fc = cells(frow) if isinstance(frow, (str, bytes, bytearray)) else []
            if len(fc) > 2:
                zone_t.pop(fc[2], None)
            for released in (current.get("_mix_terrain_entry"),
                             current.get("_mix_boss_entry")):
                if isinstance(released, tuple) and released not in tower:
                    tower.append(released)
            log(f"[HP重排] round={r} --mix 无兼容的安全 HP donor，"
                f"撤销克隆并退回原场地 {chosen['field']}")
        for entry in list(tower):
            if entry[0] == chosen["field"]:
                tower.remove(entry)
                break
        return chosen

    quest_rows: dict[str, list[str]] = {}
    forged_pubs: set[str] = set()
    immunity_programs: dict[str, list] = {}
    if plan.get("stages") or plan.get("floors"):
        print(f"[工坊] 布局计划生效:阶段 {len(plan.get('stages') or [])} 段,"
              f"显式指定 {len(plan.get('floors') or {})} 层")
    plan_lines = []
    if args.mix and len(tower) < args.rounds * 2 + 1:
        print(f"[ERR] --mix 每层耗两个塔楼层,塔池 {len(tower)} < {args.rounds}×2+1")
        return 1
    # ---- 固定位 boss 预登记配额(2026-07-29 交叉核查抓到的真 bug)----
    # 楼层按 r 升序生成、`used_counts` 在**选完之后**才写,所以塔腰固定位(菲诺梅那)
    # 之前的锚位取候选时它还没占配额 —— 而 `steampunk_another` 本身**仍是领主战(44)
    # 和降临讨伐(36)两个池的成员**(lv100,四道筛子全刷不掉它),于是 30 层塔的
    # 第 6 战领主战锚位可以把它抽走,和第 15 战固定位撞成同一个 boss 出两次
    # (1.4.238 实际发生过;seed 20260812+4 可复现)。
    # 修法:固定位的 boss 在循环**开始前**就登记配额,让随机锚位天然避开。
    for _fixed_field, _lab in ((PHENO_FIELD, "机工神兵"),):
        _live_fixed = [rr for rr, lab in schedule.items()
                       if lab == _lab]
        if _live_fixed:
            _fb, _ = _zone_pick(_fixed_field)
            for _k in name_keys(_fb):
                used_counts[_k] = used_counts.get(_k, 0) + 1
    # 中段/深层锚进入独立“未来预留”，防止浅层提前抽走；到映射轮次先释放，
    # 只有实际选中才进入 used_counts。不能直接预加 used_counts，否则未采用/被 pin
    # 绕开的锚会形成幽灵占用，实际锚还会被重复计数。
    for _rr in range(1, args.rounds + 1):
        _af = (mid_hp_anchor_field(_rr, args.rounds)
               or deep_hp_anchor_field(_rr, args.rounds))
        if _af:
            _ab, _ = _zone_pick(_af)
            for _k in name_keys(_ab):
                future_anchor_counts[_k] = future_anchor_counts.get(_k, 0) + 1

    ex_final_pick = None
    if BUILD_MODE == "ex":
        donors = [key for key in fd_t if key.startswith("mod_five_boss_var_s1_")]
        rng.shuffle(donors)
        for donor in donors:
            donor_cells = cells(fd_t[donor])
            donor_zone = zone_t.get(donor_cells[2], {})
            if set(donor_zone) != {"0"}:
                continue
            actors = [cells(donor_zone["0"])[i] for i in (24,28,32)]
            pairs = [(a,b) for a in actors for b in actors if a != b]
            rng.shuffle(pairs)
            for pair in pairs:
                field_id = "mod_abyss_ex_final_pair"
                try:
                    if not all(boss_level_ok(code, 100, sb_t, gv_t, gb_t) for code in pair):
                        continue
                    pair_zone = abyss_ex.sequential_pair(donor, fd_t, zone_t, pair, cells, join)
                    ex_lane_audit.audit(pair, 100, gb_t, select_surjective_level)
                    block = identity_clone_locked_boss_reason(pair, code_references=code_refs)
                    if block:
                        continue
                    zone_t[field_id] = pair_zone
                    fd_t[field_id] = join([donor_cells[0], donor_cells[1], field_id], isinstance(fd_t[donor], bytes))
                    candidate = {"field": field_id, "bosses": list(pair), "thumb": thumb_map.get(donor, ""),
                                 "bgm": None, "label": "EX双Boss决战", "thumbnail_field": donor,
                                 "ex_final_donor": donor}
                    metrics = hp_pick_metrics(candidate, 30, abyss_modes.base_hp("ex",30)/TARGET_BASE_DURATION_S)
                    if metrics is None or strict_hp_candidate_error(metrics):
                        continue
                    ex_final_pick = candidate
                    gim_dirty = True
                    break
                except (ValueError, KeyError, IndexError, FileNotFoundError):
                    continue
            if ex_final_pick:
                break
        if not ex_final_pick:
            raise RuntimeError("no verified five-boss sequential pair satisfies EX final gates")

    tower_bosses: list[str] = []
    floor_recs: list[dict] = []
    curse_name_history: list[set[str]] = []
    curse_diversity_state = new_curse_diversity_state()
    mix_applied_rounds: list[int] = []
    previous_boss_cooldown_group: str | None = None
    for r in range(1, args.rounds + 1):
        label = None if BUILD_MODE == "ex" else schedule.get(r)
        forced = (((plan.get("floors") or {}).get(str(r))) or {}) if not args.ignore_plan else {}
        pin_t, pin_b = forced.get("terrain"), forced.get("boss")
        mapped_anchor = (mid_hp_anchor_field(r, args.rounds)
                         or deep_hp_anchor_field(r, args.rounds))
        if mapped_anchor:
            _mapped_bosses, _ = _zone_pick(mapped_anchor)
            for _k in name_keys(_mapped_bosses):
                left = future_anchor_counts.get(_k, 0) - 1
                if left > 0:
                    future_anchor_counts[_k] = left
                else:
                    future_anchor_counts.pop(_k, None)
        st_tier, st_mult = plan_tier_for(plan, r, round_tier(r))
        _target_dps = configured_target_dps(
            r, args.rounds, hp_base, hp_growth, st_mult, ramp=args.ramp)
        if r >= first_boss_round() and not args.ramp:
            try:
                _template_duration_s = float(tmpl_rn[100]) / 60.0
            except (IndexError, TypeError, ValueError):
                print(f"[ERR] 第{r}战模板 c100 时限不可解析:{tmpl_rn[100]!r}")
                return 1
            if (not math.isfinite(_template_duration_s)
                    or _template_duration_s <= 0):
                print(f"[ERR] 第{r}战模板时限非法:{_template_duration_s}s")
                return 1
            # configured_target_dps 的默认坐标是 900 秒；先还原为整关基础 HP，
            # 再除以真实模板时限。这样模板时限即使以后调整，30亿→150亿的
            # 基础总 HP 仍保持不变，不会悄悄变成“固定 DPS × 新时限”。
            _target_dps *= TARGET_BASE_DURATION_S / _template_duration_s
        if r < first_boss_round() and not args.ramp:
            _target_dps = WARMUP_TARGET_DPS
        field_needed = required_field_slots(r, args.rounds) if st_tier == "hell" else 0
        if BUILD_MODE == "ex" and r == 30:
            pick = copy.deepcopy(ex_final_pick)
        elif label and not (pin_t or pin_b):
            pick = PICKERS[label]()
        elif args.mix or pin_t or pin_b:
            pick = mix_pick(r, pin_t, pin_b)
            if pick is None and (pin_t or pin_b):
                print(f"[ERR] 第{r}战钉选失败(terrain={pin_t} boss={pin_b}),拒绝产出")
                return 1
            pick = pick or tower_pick(r)
        else:
            pick = tower_pick(r)
        _element_required = BUILD_MODE == "ex" or element_immunity_requested(forced)
        _carrier_required = BUILD_MODE == "ex" or hard_condition_carrier_requested(forced)
        # 钉地形只锁地形，不锁 donor：仍走 HP/属性载体重排，并在混搭 zone 内
        # 原地换 boss。钉 boss 则保持硬约束；与钉选属性免疫冲突时明确失败，
        # 绝不能成功产出后把「元素禁壁」随机替换掉。
        if r >= first_boss_round() and not (BUILD_MODE == "ex" and r == 30) and (not pin_b or _element_required or _carrier_required):
            try:
                pick = hp_curve_fit_pick(
                    pick, r, _target_dps, field_needed,
                    element_required=_element_required,
                    carrier_required=_carrier_required,
                    pinned_boss=(str(pin_b) if pin_b else None),
                    pinned_terrain=bool(pin_t),
                    forbidden_cooldown_group=(
                        None if pin_b else previous_boss_cooldown_group))
            except RuntimeError as exc:
                print(f"[ERR] {exc}")
                return 1
        if args.test_field == r and label is None:
            tries = 0
            while not field_caps(pick["field"], pick["bosses"])["boss"] and tower and tries < 30:
                pick = tower_pick(r)
                tries += 1
        _high_threat = is_high_threat_bosses(
            pick.get("bosses") or [], high_threat_prefixes, high_threat_exact)
        if BUILD_MODE == "normal" and abyss_modes.is_five_boss_source(
                pick["field"], pick.get("bosses") or (),
                [str(pick.get(key) or "") for key in ("play_field", "boost_field", "thumbnail_field")]):
            raise ValueError(f"普通深渊第{r}关包含五重来源，拒绝生成: {pick['field']}")
        pick["high_threat"] = _high_threat
        previous_boss_cooldown_group = boss_family_cooldown_group(
            pick.get("bosses") or ())
        if _high_threat:
            log(f"[高威胁] round={r} bosses={','.join(pick.get('bosses') or [])} "
                "禁时限/禁高档属性墙/诅咒HP≤1.5")
        tower_bosses += pick["bosses"]
        for _k in name_keys(pick["bosses"]):
            used_counts[_k] = used_counts.get(_k, 0) + 1
        row = list(tmpl_r1 if r < first_boss_round() else tmpl_rn)
        row[0] = str(int(EVENT_ID) * 1000 + r)
        row[1] = "1"
        row[2] = str(r)
        enforce_gauntlet_player_rank(row)
        abyss_modes.set_finite_quest_prerequisite(row, int(EVENT_ID), r)
        bh, ba = (SRC_BOOST.get(label, (1.0, 1.0)) if label
                  else tower_area_boost(pick.get("boost_field") or pick["field"]))
        _native_bundle = pick.get("native_bundle")
        if isinstance(_native_bundle, rbb.NativeBossBundle):
            _bundle_family = special_bundle_family(_native_bundle)
            _bundle_source_hp = (
                orochi_native_hp_evidence(_native_bundle, 100, orochi_tables)
                if _bundle_family == "orochi" else
                orochi_ex_native_hp_evidence(
                    _native_bundle, 100, orochi_tables)
                if _bundle_family == "orochi_ex" else
                single_bar_special_native_hp_evidence(
                    _native_bundle, 100, orochi_tables)
                if _bundle_family in SINGLE_BAR_SPECIAL_SPECS else
                sphere_native_hp_evidence(
                    _native_bundle, 100, orochi_tables)
                if _bundle_family in SPHERE_SPECS else
                {"verified": False, "absolute_verified": False,
                 "reason": "unknown native special family"}
            )
            if not _bundle_source_hp.get("verified"):
                print(f"[ERR] 第{r}战专用 bundle HP 证据失效:"
                      f"{_bundle_source_hp.get('reason') or 'unknown'}")
                return 1
            if _bundle_family == "orochi":
                _lv = int(_bundle_source_hp["expanded"].selected_parent_level)
            else:
                _lv = int(_bundle_source_hp["graph"].selected_level)
        else:
            _bundle_family = None
            _bundle_source_hp = None
            _lv = int(resolve_level(pick["bosses"], want_level(r), sb_t, gv_t,
                                    gb_t, prefer_max=want_max) or want_level(r))
        pick["level"] = _lv
        # 该层有没有可归一的基数?standard 表 boss 查不到 → 归一化不生效,
        # 拿到的是裸曲线值,真实伤害无上界保证(2026-07-30 审计盲区实锤)
        _anchor = stat_anchor(pick["bosses"], _atk_med, "atk", _lv)
        _hp_anchor = stat_anchor(pick["bosses"], _hp_med, "hp", _lv)
        # HP 按族分治：general Hit/Fix 分别落 clone boss_level.c2/c5；standard
        # 落克隆 Enemy DSL 的 T1 Health；混合层由两个适配器共享同一整关倍率。
        _native_hp = (_bundle_source_hp if _bundle_source_hp is not None else
                      floor_native_hp(
                          pick["bosses"], _lv, sb_t,
                          standard_runtime_hp_scale=
                          RUSH_EVENT_STANDARD_HP_SCALE))
        try:
            _base_duration_s = float(row[100]) / 60.0
        except (TypeError, ValueError):
            print(f"[ERR] 第{r}战模板 c100 时限不可解析:{row[100]}")
            return 1
        if not math.isfinite(_base_duration_s) or _base_duration_s <= 0:
            print(f"[ERR] 第{r}战模板时限非法:{_base_duration_s}s")
            return 1
        # 基础数值归一:按 boss 基数相对同曲线组中位数反向补偿(2026-07-29 用户需求)
        if args.normalize:
            nh, na = stat_normalize(pick["bosses"], _hp_med, _atk_med,
                                    args.normalize_min, args.normalize_max, _lv,
                                    {"hp": args.normalize_hp, "atk": args.normalize_atk},
                                    {"atk": args.normalize_atk_max})
            bh, ba = bh * nh, ba * na
            pick["norm"] = (nh, na)
        caps = field_caps(pick["field"], pick["bosses"], _lv)
        _runtime_kwargs = {}
        _hp_strategy = None
        _hp_scaling_error = None
        if (_native_hp.get("verified")
                and isinstance(_native_bundle, rbb.NativeBossBundle)):
            _required_c86 = float(fmt(solve_hp_correction(
                _target_dps, _base_duration_s,
                float(_native_hp["native_hp"]))))
            _hp_strategy = {
                "channel": "special_bundle", "family": str(_bundle_family),
                "baseline_c86": 1.0, "baseline_scale": _required_c86,
                "selected_levels": {
                    str(component["code"]): int(component["selected_level"])
                    for component in _native_hp["components"]
                },
            }
            _runtime_kwargs = {
                "baseline_c86": 1.0,
                "c86_limits": (1.0, 1.0),
                "baseline_dps": _target_dps,
                "base_duration_s": _base_duration_s,
                "hp_channel": "special_bundle",
            }
        elif _native_hp.get("verified"):
            _required_c86 = float(fmt(solve_hp_correction(
                _target_dps, _base_duration_s,
                float(_native_hp["native_hp"]))))
            try:
                _hp_strategy = floor_hp_scaling_strategy(
                    pick["bosses"], _native_hp, gb_t, bl_t, _lv,
                    required_c86=_required_c86,
                    deep=is_deep_round(r, args.rounds),
                    code_references=code_refs, standard_boss=sb_t,
                    general_boss_state=gbs_t)
            except ValueError as exc:
                # 非破坏性血量带的第二半:hp_curve_fit_pick 已经决定「缩放不了
                # 就保留这一层」,这里就不能再因为算不出缩放而整座塔拒绝产出。
                # 退回该 boss 的原生血量(= 官方值,86e27250 之前一直如此),
                # 该层不进带内,[真HP门禁] 会如实计入「无boss估算」。
                # 典型触发者正是被策展进来的锚位:土俑嘉年华的 haniwa_great_*_pf
                # 是 identity-locked(被 damage_share/enemy_watch 按代号引用),
                # master id 不能动、c86 只有 0.9~1.1 的微调窗口。
                print(f"[WARN] 第{r}战 HP 主通道不可实现,退回原生血量:{exc}")
                _hp_strategy = None
                _runtime_kwargs = {}
                _hp_scaling_error = str(exc)
            if _hp_strategy is not None:
                _baseline_c86 = float(_hp_strategy["baseline_c86"])
                _baseline_true_hp = (
                    _target_dps * _base_duration_s
                    if _hp_strategy["channel"] in {
                        "boss_level", "standard_dsl", "mixed_hp",
                        "special_bundle"}
                    else _true_hp_at_c86(_native_hp, _baseline_c86))
                _runtime_kwargs = {
                    "baseline_c86": _baseline_c86,
                    "c86_limits": ((1.0, 1.0)
                                   if _hp_strategy["channel"] in {
                                       "boss_level", "standard_dsl", "mixed_hp",
                                       "special_bundle"}
                                   else STANDARD_C86_LIMITS),
                    "baseline_dps": _baseline_true_hp / _base_duration_s,
                    "base_duration_s": _base_duration_s,
                    "hp_channel": _hp_strategy["channel"],
                }
        elif not pick["bosses"]:
            # 第 1 战是唯一无 boss 血条的结构性例外，无法用相邻 boss 的反解比例
            # 事后放大 c86；否则抽到高墙时可能在诅咒已定案后才越窗，失去重抽机会。
            # 直接用它自己的旧曲线 c86 作透明代理，并在抽取阶段照常过最终窗口/时限闸。
            _proxy_baseline_c86 = float(fmt(
                hp_base * (hp_growth ** (r - 1)) * bh * st_mult))
            _runtime_kwargs = {
                "baseline_c86": _proxy_baseline_c86,
                "c86_limits": hp_correction_limits(r, args.rounds),
                "baseline_dps": _target_dps,
                "base_duration_s": _base_duration_s,
            }
            _hp_strategy = {
                "channel": "c86", "family": "no-boss",
                "baseline_c86": _proxy_baseline_c86, "baseline_scale": 1.0,
                "selected_levels": {},
            }
        _hp_family = (_hp_strategy["family"] if _hp_strategy else "unknown")
        _hp_channel = (_hp_strategy["channel"]
                       if _hp_strategy else "unscaled")
        _pacing_blocks = curse_pacing_blocks(
            r, args.rounds, curse_name_history, tier=st_tier)
        try:
            _curse_capabilities = resolve_curse_capabilities(
                _hp_channel, _hp_family, caps,
                no_base=(_anchor is None or _hp_strategy is None))
            if BUILD_MODE == "ex":
                _ex_lanes, _ex_evidence = ex_lane_audit.audit(pick["bosses"], _lv, gb_t, select_surjective_level)
                curse = abyss_ex.roll_curses(sys.modules[__name__], r, rng, _ex_lanes,
                                             _curse_capabilities, _runtime_kwargs,
                                             native_evidence=_ex_evidence,
                                             history=curse_name_history)
                curse["ex_native_evidence"] = _ex_evidence
            else:
                curse = abyss_curses(
                r, args.rounds, rng, st_tier, caps, forced,
                # _hp_strategy is None = 这层的血量按不动(读不出通道,或
                # identity-locked 只剩 0.9~1.1 微调窗口),等价于「无基数层」:
                # 攻击诅咒与时限诅咒都必须禁掉,否则真实伤害/需求 DPS 无上界。
                no_base=(_anchor is None or _hp_strategy is None),
                high_threat=_high_threat,
                capability_profile=_curse_capabilities,
                random_forbidden=_pacing_blocks,
                diversity_state=curse_diversity_state,
                **_runtime_kwargs)
        except (RuntimeError, ValueError) as exc:
            print(f"[ERR] 第{r}战诅咒组合无法满足硬闸:{exc}")
            return 1
        if _high_threat:
            _threat_why = high_threat_curse_conflict(curse.get("picks") or [])
            if _threat_why:
                print(f"[ERR] 第{r}战高威胁诅咒后置复核失败:{_threat_why}")
                return 1
        curse_name_history.append({
            str(pick.get("name")) for pick in (curse.get("picks") or [])
            if pick.get("name")
        })
        hard_damage = curse.get("damage_resistance") or []
        hard_elements = curse.get("element_resistance") or []
        hard_stacked = curse.get("stacked_resistance") or []
        quest_elements = BUILD_MODE in ("normal", "ex") and bool(hard_elements)
        if quest_elements and any(cancelable for _, _, cancelable in hard_elements):
            raise ValueError("quest element carrier cannot preserve cancelable resistance")
        hard_program = None
        if hard_elements:
            assert_element_immunity_runtime_safe(Q_QUEST, _lv)
        if hard_damage or (hard_elements and not quest_elements) or hard_stacked:
            hard_program, hard_tree = immunity_program(
                hard_damage, [] if quest_elements else hard_elements, hard_stacked)
            build_immunity_dsl_blob(hard_tree)       # dry-run 也做 AMF3/raw-deflate 往返门禁
            immunity_programs.setdefault(hard_program, hard_tree)
            forged_pubs.add(hard_program + ".action.dsl.amf3.deflate")
            if args.dump_immunity_dsl:
                print(f"[DSL] 第{r}战 {hard_program}")
                print(json.dumps(hard_tree, ensure_ascii=False, separators=(",", ":")))
        if args.test_field == r and not curse["casters"]:
            if caps["boss"]:
                _menu = field_menu_all()
                fm = _menu[rng.randrange(len(_menu))]
                apply_picks(curse, (curse.get("picks") or [])
                            + [{"name": "深渊法阵", "caster": fm,
                                "text": f"{fm[0]}·{fm[2]}"}], curse.get("combo"))
            else:
                why = caster_blocked.get(pick["field"])
                print(f"[WARN] 第{r}战无 general boss 载体,--test-field 落不了法阵"
                      + (f"(门禁:{why})" if why else ""))
        # test-field 会在 abyss_curses.finalize 之后补条目，重新给领域覆盖率记账。
        if curse.get("field_requested"):
            curse["field_applied"] = len(curse.get("casters") or [])
            curse["field_deficit"] = max(
                0, int(curse["field_requested"]) - int(curse["field_applied"]))
        if curse.get("field_deficit"):
            why = curse.get("field_deficit_reason") or caps.get("carrier_reason") \
                or "没有可用的 general_boss 领域载体"
            curse["field_deficit_reason"] = why
            log(f"[curse] round={r} field-underfill="
                f"{curse['field_applied']}/{curse['field_requested']} reason={why}")
            # 非破坏性策略下这不再是致命错误。法阵载体必须是 general 系 boss
            # (见「深渊连战-随机方案-当前.md」第九节:抽到 standard/专用表 boss
            # 时法阵**静默落不上,不是崩溃**)。既然我们不再为了凑载体把策展
            # 锚位换掉,就得允许这些层欠配——[领域/时限] 行会如实报「欠配 N 层」。
            print(f"[WARN] 第{r}战领域保底欠配:"
                  f"{curse['field_applied']}/{curse['field_requested']} ({why})")
        _hp_plan = None
        if _hp_strategy and _hp_strategy["channel"] == "boss_level":
            try:
                _hp_plan = general_hp_scale_plan(
                    pick["bosses"], _native_hp, gb_t, bl_t, _lv,
                    target_hp=_target_dps * _base_duration_s,
                    curse_hp=float(curse["hp"]),
                    code_references=code_refs,
                    general_boss_state=gbs_t,
                    component_budgets=({code: abyss_modes.base_hp("ex", 30) / 2 for code in pick["bosses"]}
                                       if BUILD_MODE == "ex" and r == 30 else None))
            except ValueError as exc:
                print(f"[ERR] 第{r}战 boss_level HP 伸缩计划失败:{exc}")
                return 1
        elif _hp_strategy and _hp_strategy["channel"] == "standard_dsl":
            try:
                _hp_plan = standard_hp_scale_plan(
                    pick["bosses"], _native_hp, sb_t, _lv,
                    target_hp=_target_dps * _base_duration_s,
                    curse_hp=float(curse["hp"]),
                    code_references=code_refs,
                    resources=standard_resource_blobs)
            except (RuntimeError, ValueError) as exc:
                print(f"[ERR] 第{r}战 Standard DSL HP 伸缩计划失败:{exc}")
                return 1
        elif _hp_strategy and _hp_strategy["channel"] == "mixed_hp":
            try:
                _hp_plan = mixed_hp_scale_plan(
                    pick["bosses"], _native_hp, gb_t, bl_t, sb_t, _lv,
                    target_hp=_target_dps * _base_duration_s,
                    curse_hp=float(curse["hp"]),
                    code_references=code_refs,
                    resources=standard_resource_blobs,
                    general_boss_state=gbs_t)
            except (RuntimeError, ValueError) as exc:
                print(f"[ERR] 第{r}战 Mixed HP 伸缩计划失败:{exc}")
                return 1
        elif _hp_strategy and _hp_strategy["channel"] == "special_bundle":
            try:
                if _hp_strategy["family"] == "orochi":
                    _hp_plan = orochi_hp_scale_plan(
                        _native_hp, bl_t,
                        target_hp=_target_dps * _base_duration_s,
                        curse_hp=float(curse["hp"]))
                elif _hp_strategy["family"] == "orochi_ex":
                    _hp_plan = orochi_ex_hp_scale_plan(
                        _native_hp, oro_ex_t, bl_t,
                        target_hp=_target_dps * _base_duration_s,
                        curse_hp=float(curse["hp"]))
                elif _hp_strategy["family"] in SINGLE_BAR_SPECIAL_SPECS:
                    _hp_plan = single_bar_special_hp_scale_plan(
                        _native_hp, bl_t,
                        target_hp=_target_dps * _base_duration_s,
                        curse_hp=float(curse["hp"]))
                elif _hp_strategy["family"] in SPHERE_SPECS:
                    _hp_plan = sphere_hp_scale_plan(
                        _native_hp, bl_t,
                        target_hp=_target_dps * _base_duration_s,
                        curse_hp=float(curse["hp"]))
                else:
                    raise ValueError(
                        f"未知专用 HP 族:{_hp_strategy['family']}")
            except (RuntimeError, ValueError) as exc:
                print(f"[ERR] 第{r}战专用多阶段 HP 伸缩计划失败:{exc}")
                return 1
        _final_native_hp = _native_hp
        if curse["gimmick"] or curse["casters"] or hard_program or _hp_plan:
            swaps: list[tuple[str, str]] = []
            action_programs: list[str] = []
            field_program_receipts: list[dict] = []
            fields_tuned = False
            for fm_ in list(curse.get("casters") or []):
                source_action_program = str(fm_[1])
                action_program = source_action_program
                fcat = fm_[3] if len(fm_) > 3 else "领域"
                tun = field_tuning()
                factor = float(tun.get("per", {}).get(action_program)
                               or tun.get("global", {}).get(fcat, 1) or 1)
                if abs(factor - 1.0) > 1e-9:
                    # 缩放标注挂在法阵条目自己的 text 上,降档闸重渲 desc 时不会丢
                    for _c in curse.get("picks") or []:
                        if (_c.get("caster")
                                and str(_c["caster"][1]) == str(fm_[1])):
                            _c["text"] += f"×{factor:g}"
                    fields_tuned = True
                    if forge_candidate is not None:
                        action_program = forge_candidate(action_program, factor)
                    elif args.write:
                        import wf_field_catalog as wfc
                        action_program = wfc.forge(action_program, scale=factor)
                if action_program.startswith("battle/action/enemy/action/mod_rogue/"):
                    forged_pubs.add(action_program + ".action.dsl.amf3.deflate")
                if action_program not in action_programs:
                    action_programs.append(action_program)
                field_program_receipts.append({
                    "name": str(fm_[0]),
                    "description": str(fm_[2]),
                    "category": str(fcat),
                    "declared_program": source_action_program,
                    "applied_program": action_program,
                    "readback_match": True,
                })
            if len(action_programs) > 1:
                print(f"[ERR] 第{r}战领域同时执行闭包未证明，拒绝落多个程序:"
                      + ",".join(action_programs))
                return 1
            curse["field_program_receipts"] = field_program_receipts
            if fields_tuned:
                apply_picks(curse, curse.get("picks") or [], curse.get("combo"))
            target = caps.get("element_target") if (action_programs or hard_program or hard_elements) else None
            carrier_clone = None
            if _hp_plan and _hp_plan["channel"] == "boss_level":
                source_codes = list(_hp_plan["final_leaves"])
                if target in source_codes:
                    source_codes.remove(target)
                    source_codes.insert(0, target)
                for index, source_code in enumerate(source_codes):
                    clone_code = (f"{PRIVATE_PREFIX}boss{r}" if index == 0
                                  else f"{PRIVATE_PREFIX}boss{r}_{index + 1}")
                    is_carrier = source_code == target
                    clone = make_caster_boss(
                        r, source_code,
                        action_programs=(action_programs if is_carrier else ()),
                        pre_action_program=(hard_program if is_carrier or BUILD_MODE == "ex" else None),
                        requires_element_resistance=(bool(hard_elements) and (is_carrier or BUILD_MODE == "ex")),
                        enemy_level=_lv, clone_code=clone_code,
                        boss_level_leaf=_hp_plan["final_leaves"][source_code],
                        expected_selected_level=_hp_plan["selected_levels"][source_code],
                        damage_check_plan=(
                            _hp_plan["damage_check_plans"][source_code]))
                    if not clone:
                        print(f"[ERR] 第{r}战 general HP clone 失败:{source_code}")
                        return 1
                    swaps.append((source_code, clone))
                    if is_carrier:
                        carrier_clone = clone
            elif _hp_plan and _hp_plan["channel"] == "standard_dsl":
                source_codes = list(_hp_plan["final_blobs"])
                for index, source_code in enumerate(source_codes):
                    try:
                        clone = make_standard_boss(
                            r, index, source_code, _hp_plan, _lv)
                    except (RuntimeError, ValueError) as exc:
                        print(f"[ERR] 第{r}战 standard HP clone 失败:"
                              f"{source_code}:{exc}")
                        return 1
                    swaps.append((source_code, clone))
            elif _hp_plan and _hp_plan["channel"] == "mixed_hp":
                general_plan = _hp_plan["general_plan"]
                standard_plan = _hp_plan["standard_plan"]
                general_codes = list(general_plan["final_leaves"])
                if target in general_codes:
                    general_codes.remove(target)
                    general_codes.insert(0, target)
                for index, source_code in enumerate(general_codes):
                    clone_code = (f"{PRIVATE_PREFIX}boss{r}" if index == 0
                                  else f"{PRIVATE_PREFIX}boss{r}_{index + 1}")
                    is_carrier = source_code == target
                    clone = make_caster_boss(
                        r, source_code,
                        action_programs=(action_programs if is_carrier else ()),
                        pre_action_program=(hard_program if is_carrier or BUILD_MODE == "ex" else None),
                        requires_element_resistance=(bool(hard_elements) and (is_carrier or BUILD_MODE == "ex")),
                        enemy_level=_lv, clone_code=clone_code,
                        boss_level_leaf=general_plan["final_leaves"][source_code],
                        expected_selected_level=general_plan[
                            "selected_levels"][source_code],
                        damage_check_plan=(
                            general_plan["damage_check_plans"][source_code]))
                    if not clone:
                        print(f"[ERR] 第{r}战 mixed general HP clone 失败:{source_code}")
                        return 1
                    swaps.append((source_code, clone))
                    if is_carrier:
                        carrier_clone = clone
                for index, source_code in enumerate(standard_plan["final_blobs"]):
                    try:
                        clone = make_standard_boss(
                            r, index, source_code, standard_plan, _lv)
                    except (RuntimeError, ValueError) as exc:
                        print(f"[ERR] 第{r}战 mixed standard HP clone 失败:"
                              f"{source_code}:{exc}")
                        return 1
                    swaps.append((source_code, clone))
                _hp_plan["destinations"].update(standard_plan["destinations"])
            elif _hp_plan and _hp_plan["channel"] == "special_bundle":
                if not isinstance(_native_bundle, rbb.NativeBossBundle):
                    print(f"[ERR] 第{r}战 special_bundle 计划缺原生 bundle")
                    return 1
                if _hp_plan["family"] == "orochi":
                    _orochi_clone = clone_orochi_parent_bundle(
                        _native_bundle, r, float(_hp_plan["final_scale"]),
                        orochi_tables)
                    if (not _orochi_clone.ok or _orochi_clone.bundle is None
                            or _orochi_clone.expanded is None
                            or _orochi_clone.parent_code is None):
                        print(f"[ERR] 第{r}战八岐父体整包克隆失败:"
                              f"{_orochi_clone.detail or _orochi_clone.reason or 'unknown'}")
                        return 1
                    _source_parent = _orochi_parent_ref(_native_bundle)
                    _final_native_hp = orochi_native_hp_evidence(
                        _orochi_clone.bundle, _lv, orochi_tables)
                    orochi_dirty = True
                    _special_clone = _orochi_clone
                elif _hp_plan["family"] == "orochi_ex":
                    _orochi_ex_clone = clone_orochi_ex_parent_bundle(
                        _native_bundle, r,
                        float(_hp_plan["final_fixed_phase_scale"]),
                        orochi_tables,
                        middle_scale=float(_hp_plan["final_middle_scale"]))
                    if (not _orochi_ex_clone.ok
                            or _orochi_ex_clone.bundle is None
                            or _orochi_ex_clone.parent_code is None):
                        print(f"[ERR] 第{r}战八岐 EX 父体/六子体整包克隆失败:"
                              f"{_orochi_ex_clone.detail or _orochi_ex_clone.reason or 'unknown'}")
                        return 1
                    _source_parent = _orochi_ex_parent_ref(_native_bundle)
                    _final_native_hp = orochi_ex_native_hp_evidence(
                        _orochi_ex_clone.bundle, _lv, orochi_tables)
                    orochi_ex_dirty = True
                    _special_clone = _orochi_ex_clone
                elif _hp_plan["family"] in SINGLE_BAR_SPECIAL_SPECS:
                    _single_special_clone = clone_single_bar_special_bundle(
                        _native_bundle, r, float(_hp_plan["final_scale"]),
                        orochi_tables)
                    if (not _single_special_clone.ok
                            or _single_special_clone.bundle is None
                            or _single_special_clone.parent_code is None):
                        print(f"[ERR] 第{r}战专用单血条整包克隆失败:"
                              f"{_single_special_clone.detail or _single_special_clone.reason or 'unknown'}")
                        return 1
                    _source_parent = _single_bar_special_parent_ref(
                        _native_bundle, _hp_plan["family"])
                    _final_native_hp = single_bar_special_native_hp_evidence(
                        _single_special_clone.bundle, _lv, orochi_tables)
                    single_bar_special_dirty.add(str(_hp_plan["family"]))
                    _special_clone = _single_special_clone
                elif _hp_plan["family"] in SPHERE_SPECS:
                    _sphere_clone = clone_sphere_bundle(
                        _native_bundle, r, float(_hp_plan["final_scale"]),
                        orochi_tables)
                    if (not _sphere_clone.ok or _sphere_clone.bundle is None
                            or _sphere_clone.parent_code is None):
                        print(f"[ERR] 第{r}战 Sphere 整包克隆失败:"
                              f"{_sphere_clone.detail or _sphere_clone.reason or 'unknown'}")
                        return 1
                    _source_parent = _sphere_parent_ref(
                        _native_bundle, _hp_plan["family"])
                    _final_native_hp = sphere_native_hp_evidence(
                        _sphere_clone.bundle, _lv, orochi_tables)
                    sphere_dirty.add(str(_hp_plan["family"]))
                    _special_clone = _sphere_clone
                else:
                    print(f"[ERR] 第{r}战未知专用 HP 族:{_hp_plan['family']}")
                    return 1
                if _source_parent is None:
                    print(f"[ERR] 第{r}战专用 bundle 源父体漂移")
                    return 1
                swaps.append((_source_parent.code, _special_clone.parent_code))
                if not _final_native_hp.get("verified"):
                    print(f"[ERR] 第{r}战专用多阶段克隆回读失败:"
                          f"{_final_native_hp.get('reason') or 'unknown'}")
                    return 1
                _hp_plan["clone_map"] = tuple(
                    (source.code, target_ref.code)
                    for source, target_ref in _special_clone.clone_map)
                _hp_plan["touched_tables"] = _special_clone.touched_tables
                if (_hp_plan["family"] == "orochi_ex"
                        and isinstance(_special_clone.evidence, dict)):
                    _hp_plan["phase_clone_semantics"] = copy.deepcopy(
                        _special_clone.evidence.get("clone_semantics"))
            elif action_programs or hard_program:
                carrier_clone = (make_caster_boss(
                    r, target, action_programs=action_programs,
                    pre_action_program=hard_program,
                    requires_element_resistance=bool(hard_elements),
                    enemy_level=_lv) if target else None)
                if carrier_clone:
                    swaps.append((target, carrier_clone))
            play_field = gimmick_field(pick["field"], r,
                                       panels=curse["gimmick"], boss_swaps=swaps)
            if ((action_programs or hard_program) and not carrier_clone) or not play_field:
                print(f"[ERR] 第{r}战硬通道载体/field 克隆失败,拒绝保留虚假诅咒文案")
                return 1
            pick["play_field"] = play_field
            _play_row = fd_t.get(play_field)
            _play_cells = (cells(_play_row)
                           if isinstance(_play_row, (str, bytes, bytearray)) else [])
            _play_zone = zone_t.get(_play_cells[2]) if len(_play_cells) > 2 else None
            runtime_bosses = zone_single_bosses(_play_zone)
            swap_map = dict(swaps)
            expected_bosses = [swap_map.get(code, code) for code in pick["bosses"]]
            if runtime_bosses != expected_bosses:
                print(f"[ERR] 第{r}战最终 boss swap 不一致:"
                      f"expected={expected_bosses},actual={runtime_bosses}")
                return 1
            pick["runtime_bosses"] = runtime_bosses
            if hard_elements:
                # 最终实际 code = field 成功换入的 clone；再读一次克隆后 c36。
                actual_code = carrier_clone if play_field else target
                blocked = general_boss_element_immunity_block(gb_t, actual_code, _lv, gv_t)
                if blocked:
                    print(f"[ERR] 第{r}战属性免疫最终载体复核失败:{blocked}")
                    return 1
            if _hp_plan:
                if _hp_plan["channel"] != "special_bundle":
                    _final_native_hp = floor_native_hp(
                        runtime_bosses, _lv, sb_t, bl_t,
                        standard_resources=standard_resource_blobs,
                        standard_runtime_hp_scale=
                        RUSH_EVENT_STANDARD_HP_SCALE)
                if not _final_native_hp.get("verified"):
                    print(f"[ERR] 第{r}战最终 clone HP 不可审计:"
                          f"{_final_native_hp.get('reason') or 'unknown'}")
                    return 1
                actual_hp = _true_hp_at_c86(_final_native_hp, 1.0)
                if not math.isclose(actual_hp, float(_hp_plan["true_hp"]),
                                    rel_tol=1e-9, abs_tol=1.0):
                    print(f"[ERR] 第{r}战 clone HP 回读不一致:"
                          f"plan={_hp_plan['true_hp']},actual={actual_hp}")
                    return 1
        note = patch_common(row, f"{EVENT_NAME} 第{r}战", pick)
        quest_rows[str(r)] = row
        # ⚠ 数值列**不在这里落**:分位硬闸要看到全塔分布才能决定哪层降档,
        # 降档又会改回 hp/诅咒词条/副标题。所以先攒 record,闸门跑完再统一写。
        floor_recs.append({
            "r": r, "row": row, "pick": pick, "note": note, "bh": bh, "ba": ba,
            "curse": curse, "st_mult": st_mult, "no_base": _anchor is None,
            "anchor": _anchor, "hp_anchor": _hp_anchor,
            "hp_family": _hp_family, "native_hp": _native_hp,
            "final_native_hp": _final_native_hp,
            "hp_strategy": _hp_strategy, "hp_plan": _hp_plan,
            "hp_scaling_error": _hp_scaling_error,
            "target_dps": _target_dps,
            "base_duration_s": _base_duration_s,
            "funnel": any(fc.startswith(b) for b in pick["bosses"]
                          for fc in funnel_levels()),
        })
        if args.mix and pick.get("_mix_terrain_entry"):
            mix_applied_rounds.append(r)

    if args.mix:
        if not mix_applied_rounds:
            print("[ERR] --mix 实际拼接 0 层：严格 transplant_safe 白名单"
                  "与当前 HP/c86 窗口无交集，拒绝以全部原场地冒充混搭成功")
            return 1
        print(f"[MIX] 实际拼接 {len(mix_applied_rounds)} 层:"
              + ",".join(map(str, mix_applied_rounds)))

    # ---- 分位硬闸 + 数值列落表(2026-07-30)----
    curve_scale, band_log = enforce_atk_band(floor_recs, atk_base, atk_growth,
                                             args.rounds)
    try:
        reconcile_curse_diversity_state(curse_diversity_state, floor_recs)
    except (KeyError, TypeError, ValueError) as exc:
        print(f"[ERR] 诅咒/领域多样性终态回执重建失败:{exc}")
        return 1

    # 非破坏性血量带:有 boss 却读不出绝对 HP 证据的层不再拒绝产出——那等于
    # 强制把这些 boss 从塔里赶走。命中这条的恰恰是策展锚位本身
    # (菲诺梅那 steampunk_another / 土俑 haniwa_great_*_pf / 精灵兽 spirit_beast_* /
    # 女王 variant_empress_* / hero_big_boss_80_multi ...)。
    # 这些层用官方原生血量,不进需求带;下面 [真HP门禁] 的「无boss估算 N 层」
    # 就是它们的账。解析器读不到新 boss 类型的**质量信号仍然保留**,只是降级成告警。
    native_errors = native_hp_coverage_errors(floor_recs)
    if native_errors:
        for error in native_errors:
            print(f"[WARN] {error}")
        print(f"[WARN] 共 {len(native_errors)} 层用原生血量(不进需求带);"
              "如需把某只 boss 纳入带内,给它补 HP 解析器而不是把它换掉")

    # ---- 任务 D：普通 general 真 HP 折进 clone boss_level.c2；quest c86 恒 1 ----
    # identity-locked general 与 standard 都只允许同 id 的 c86 0.9~1.1 微调；
    # 第1战无 boss 是唯一代理。
    hp_audits: list[dict] = []
    unresolved_hp: list[tuple[dict, float, float]] = []
    for frec in floor_recs:
        raw_c86 = float(fmt(hp_base * (hp_growth ** (frec["r"] - 1))
                            * frec["bh"] * frec["st_mult"]))
        frames = frec["curse"].get("time") or frec["row"][100]
        try:
            duration_s = float(frames) / 60.0
        except (TypeError, ValueError):
            print(f"[ERR] 第{frec['r']}战 c100 时限不可解析:{frames}")
            return 1
        if not math.isfinite(duration_s) or duration_s <= 0:
            print(f"[ERR] 第{frec['r']}战时限非法:{duration_s}s")
            return 1
        if frec.get("hp_plan"):
            plan = frec["hp_plan"]
            final_native = frec["final_native_hp"]
            baseline_true_hp = float(plan["baseline_true_hp"])
            true_hp = _true_hp_at_c86(final_native, 1.0)
            hp_evidence = {}
            if plan["channel"] == "boss_level":
                for code in plan["final_leaves"]:
                    hp_column = int(plan["hp_columns"][code])
                    hp_evidence[code] = {
                        "column": f"c{hp_column}",
                        "source": float(cells(bl_t[code])[hp_column]),
                        "baseline": float(
                            cells(plan["baseline_leaves"][code])[hp_column]),
                        "final": float(
                            cells(plan["final_leaves"][code])[hp_column]),
                        "selected_general_level": plan["selected_levels"][code],
                        "adapter_mode": plan.get("adapter_mode"),
                        "source_curve": cells(bl_t[code])[4],
                        "final_curve": cells(plan["final_leaves"][code])[4],
                        "damage_check": copy.deepcopy(
                            plan["damage_check_contracts"][code]),
                    }
            elif plan["channel"] == "standard_dsl":
                for code in plan["final_blobs"]:
                    hp_evidence[code] = {
                        "source": plan["source_logicals"][code],
                        "destination": plan["destinations"][code],
                        "selected_standard_level": plan["selected_levels"][code],
                        "health_forms": sum(
                            1 for component in frec["native_hp"]["components"]
                            if str(component.get("code")) == code),
                        "damage_check": copy.deepcopy(
                            plan["damage_check_contracts"][code]),
                    }
            elif plan["channel"] == "mixed_hp":
                component_kinds = {
                    str(component.get("code")): str(component.get("kind"))
                    for component in frec["native_hp"]["components"]
                }
                for code, destination in plan["destinations"].items():
                    hp_evidence[code] = {
                        "kind": component_kinds.get(code, "unknown"),
                        "destination": destination,
                        "selected_level": plan["selected_levels"][code],
                    }
            elif plan["channel"] == "special_bundle":
                hp_evidence = {
                    "family": str(plan["family"]),
                    "components": len(frec["native_hp"].get("components") or []),
                    "clone_map": list(plan.get("clone_map") or ()),
                    "destinations": dict(plan["destinations"]),
                    "selected_levels": dict(plan["selected_levels"]),
                    "touched_tables": list(plan.get("touched_tables") or ()),
                }
                if plan["family"] == "orochi":
                    hp_evidence["mechanism_budget"] = copy.deepcopy(
                        plan["mechanism_budget"])
            audit = {
                "r": frec["r"], "family": str(plan["family"]), "verified": True,
                "absolute_verified": bool(
                    final_native.get("absolute_verified")),
                "native": frec["native_hp"], "final_native": final_native,
                "base_duration_s": float(frec["base_duration_s"]),
                "duration_s": duration_s,
                "target_dps": float(frec["target_dps"]),
                "curse_hp": float(frec["curse"]["hp"]),
                "baseline_c86": 1.0, "c86": 1.0,
                "baseline_true_hp": baseline_true_hp, "true_hp": true_hp,
                "baseline_dps": baseline_true_hp / float(frec["base_duration_s"]),
                "realized_dps": true_hp / duration_s,
                "raw_c86": raw_c86,
                "family_scale": float(plan["baseline_scale"]),
                ({"boss_level": "boss_level_hp",
                  "standard_dsl": "standard_dsl_hp",
                  "mixed_hp": "mixed_hp",
                  "special_bundle": "special_bundle_hp"}[plan["channel"]]): hp_evidence,
            }
            if (plan["channel"] == "special_bundle"
                    and plan["family"] == "orochi_ex"):
                audit["orochi_ex_phase_safety"] = {
                    "baseline": copy.deepcopy(
                        plan["baseline_phase_threshold_contract"]),
                    "final": copy.deepcopy(
                        plan["final_phase_threshold_contract"]),
                    "baseline_fixed_phase_scale": float(
                        plan["baseline_fixed_phase_scale"]),
                    "baseline_middle_scale": float(
                        plan["baseline_middle_scale"]),
                    "final_fixed_phase_scale": float(
                        plan["final_fixed_phase_scale"]),
                    "final_middle_scale": float(
                        plan["final_middle_scale"]),
                    "max_safe_fixed_phase_scale": float(
                        plan["max_safe_fixed_phase_scale"]),
                    "baseline_fixed_phase_int32_capped": bool(
                        plan["baseline_fixed_phase_int32_capped"]),
                    "final_fixed_phase_int32_capped": bool(
                        plan["final_fixed_phase_int32_capped"]),
                    "phase_damage_capacity": {
                        "baseline": copy.deepcopy(
                            plan["baseline_phase_damage_capacity"]),
                        "final": copy.deepcopy(
                            plan["final_phase_damage_capacity"]),
                        "clone_readback": copy.deepcopy(
                            (plan.get("phase_clone_semantics") or {}).get(
                                "phase_damage_capacity")),
                    },
                    "clone_semantics": copy.deepcopy(
                        plan.get("phase_clone_semantics")),
                    "static_verified": True,
                    "runtime_simulated": False,
                    "gameplay_verified": False,
                }
            elif (plan["channel"] == "special_bundle"
                  and plan["family"] == "orochi"):
                audit["mechanism_budget"] = copy.deepcopy(
                    plan["mechanism_budget"])
            if plan["channel"] == "boss_level":
                audit["damage_checks"] = copy.deepcopy(
                    plan["damage_check_contracts"])
            elif plan["channel"] == "standard_dsl":
                audit["damage_checks"] = copy.deepcopy(
                    plan["damage_check_contracts"])
            elif plan["channel"] == "mixed_hp":
                general_checks = plan["general_plan"][
                    "damage_check_contracts"]
                standard_checks = plan["standard_plan"][
                    "damage_check_contracts"]
                overlap = set(general_checks) & set(standard_checks)
                if overlap:
                    print("[ERR] Mixed DamageCheck 回执 code 冲突:"
                          + ",".join(sorted(overlap)))
                    return 1
                audit["damage_checks"] = copy.deepcopy({
                    **general_checks, **standard_checks})
            frec["hp_audit"] = audit
            hp_audits.append(audit)
        elif frec["native_hp"].get("verified") and frec.get("hp_scaling_error"):
            audit = unscaled_floor_hp_record(
                frec["r"], frec["native_hp"],
                base_duration_s=frec["base_duration_s"],
                duration_s=duration_s, curse_hp=frec["curse"]["hp"],
                raw_c86=raw_c86, target=frec["target_dps"],
                scaling_error=frec["hp_scaling_error"])
            frec["hp_audit"] = audit
            hp_audits.append(audit)
        elif frec["native_hp"].get("verified"):
            audit = solve_floor_hp_record(
                frec["r"], args.rounds, frec["native_hp"],
                base_duration_s=frec["base_duration_s"],
                duration_s=duration_s, curse_hp=frec["curse"]["hp"],
                raw_c86=raw_c86,
                family=frec["hp_family"], target=frec["target_dps"])
            frec["hp_audit"] = audit
            hp_audits.append(audit)
        else:
            unresolved_hp.append((frec, raw_c86, duration_s))

    # 第 1 战固定为纯小怪房，没有 boss 血条；用户给定公式只覆盖 29 个 boss 层。
    # 对这类层保留可见的旧曲线代理，并在抽诅咒时就用同一个值过窗口门禁；
    # DPS 只记为目标估算、verified=false，报告不得冒充绝对血量验收。
    for frec, raw_c86, duration_s in unresolved_hp:
        baseline_c86 = raw_c86
        curse_hp = float(frec["curse"]["hp"])
        c86 = float(fmt(baseline_c86 * curse_hp))
        target = float(frec["target_dps"])
        baseline_true_hp = target * float(frec["base_duration_s"])
        true_hp = baseline_true_hp * curse_hp
        audit = {
            "r": frec["r"], "family": frec["hp_family"], "verified": False,
            "absolute_verified": False,
            "native": frec["native_hp"],
            "base_duration_s": float(frec["base_duration_s"]),
            "duration_s": duration_s, "target_dps": target,
            "curse_hp": curse_hp,
            "baseline_c86": baseline_c86, "c86": c86,
            "baseline_true_hp": baseline_true_hp, "true_hp": true_hp,
            "baseline_dps": target, "realized_dps": true_hp / duration_s,
            "raw_c86": raw_c86, "family_scale": 1.0,
            "proxy_round": None, "warmup": frec["r"] < first_boss_round(),
        }
        frec["hp_audit"] = audit
        hp_audits.append(audit)

    # 统一 adapter 回执：所有可读 Boss 层都记录逐出现次数/逐阶段的目标、落表
    # 通道与客户端公式回读。严格模式在下方把这份结构当发布前硬门禁；普通模式
    # 也保留回执，让未归一层的误差不再只藏在自然语言告警里。
    for frec in floor_recs:
        audit = frec["hp_audit"]
        if not audit.get("verified"):
            continue
        baseline_target_hp = (float(audit["target_dps"])
                              * float(audit["base_duration_s"]))
        final_target_hp = baseline_target_hp * float(audit["curse_hp"])
        plan = frec.get("hp_plan")
        if plan:
            baseline_parts = tuple(plan["baseline_component_hp"])
            channel = str(plan["channel"])
            destination = dict(plan["destinations"])
            readback_native = frec["final_native_hp"]
            baseline_c86 = final_c86 = 1.0
        elif audit.get("target_exempt"):
            baseline_parts = None
            channel = "unscaled"
            destination = "none"
            readback_native = frec["native_hp"]
            baseline_c86 = float(audit["baseline_c86"])
            final_c86 = float(audit["c86"])
        else:
            baseline_parts = None
            channel = "c86"
            destination = ("rush_event_quest.c88"
                           if frec["pick"].get("bosses")
                           else "rush_event_quest.c86")
            readback_native = frec["native_hp"]
            baseline_c86 = float(audit["baseline_c86"])
            final_c86 = float(audit["c86"])
        try:
            audit["adapter_audit"] = build_hp_adaptation_audit(
                frec["r"], frec["native_hp"], family=str(audit["family"]),
                channel=channel, destination=destination,
                baseline_target_hp=baseline_target_hp,
                final_target_hp=final_target_hp,
                baseline_c86=baseline_c86, final_c86=final_c86,
                readback_native=readback_native,
                baseline_component_hp=baseline_parts,
                baseline_component_target_hp=(
                    plan.get("baseline_component_target_hp") if plan else None),
                final_component_target_hp=(
                    plan.get("final_component_target_hp") if plan else None),
            )
            if (isinstance(readback_native, dict)
                    and "behavior_verified" in readback_native):
                audit["phase_behavior"] = {
                    "verified": bool(readback_native.get("behavior_verified")),
                    "static_verified": bool(
                        (readback_native.get("phase_lifecycle") or {}).get(
                            "static_verified")),
                    "runtime_simulated": False,
                    "gameplay_verified": False,
                    "source": copy.deepcopy(
                        frec["native_hp"].get("phase_budgets") or []),
                    "final_readback": copy.deepcopy(
                        readback_native.get("phase_budgets") or []),
                    "source_lifecycle": copy.deepcopy(
                        frec["native_hp"].get("phase_lifecycle")),
                    "final_lifecycle": copy.deepcopy(
                        readback_native.get("phase_lifecycle")),
                }
        except ValueError as exc:
            print(f"[ERR] 第{frec['r']}战统一 HP adapter 回读失败:{exc}")
            return 1

    for frec in floor_recs:
        audit = frec["hp_audit"]
        try:
            audit["quest_hp_multipliers"] = quest_hp_multiplier_plan(
                baseline=float(audit["baseline_c86"]),
                final=float(audit["c86"]),
                has_boss=bool(frec["pick"].get("bosses")))
        except (KeyError, TypeError, ValueError) as exc:
            print(f"[ERR] 第{frec['r']}战 c86/c87/c88 独立 HP 计划失败:{exc}")
            return 1

    # 作者末层带是 hell 默认的验收锚；显式改 --hp-* /
    # 其它难度时按同比缩放该带，不让“参数已生效”反被 hell 闸拒绝。
    _canonical_hp = (args.difficulty == "hell"
                     and args.hp_base is None and args.hp_growth is None)
    _last_target = next(a["target_dps"] for a in hp_audits
                        if a["r"] == args.rounds)
    _target_anchor = (RAMP_TARGET_DPS_LAST if args.ramp else TARGET_DPS_LAST)
    _canonical_band = (RAMP_TARGET_DPS_LAST_BAND
                       if args.ramp else TARGET_DPS_LAST_BAND)
    _last_target_scale = float(_last_target) / _target_anchor
    _hp_last_band = (_canonical_band if _canonical_hp else
                     tuple(v * _last_target_scale for v in _canonical_band))
    hp_errors = hp_curve_errors(
        hp_audits, args.rounds, _hp_last_band, ramp=args.ramp)
    hp_errors += hp_short_time_errors(hp_audits)
    hp_errors += hp_correction_errors(hp_audits, args.rounds)
    hp_errors += quest_hp_multiplier_errors(hp_audits)
    if args.strict_target_hp:
        hp_errors += strict_target_hp_errors(hp_audits)
    if hp_errors:
        for error in hp_errors:
            print(f"[ERR] HP 曲线门禁:{error}")
        return 1

    for frec in floor_recs:
        r, row, curse = frec["r"], frec["row"], frec["curse"]
        audit = frec["hp_audit"]
        ex_atk_factor = abyss_modes.attack_factor("ex", frec["r"]) if BUILD_MODE == "ex" else 1.0
        atk = fmt(frec["atk"] * ex_atk_factor)
        # 三类 HP 修正独立落表：Boss 层的任务级兜底只允许进入 c88；严格资源
        # clone 层三列自然均为 1。第1战纯小怪房只写 c86，炮台/召唤物 c87
        # 保持 1，绝不再让一个非 1 倍率同时放大三类实体。
        hp_plan = audit["quest_hp_multipliers"]["final"]
        enemy_hp = fmt(hp_plan["enemy"])
        device_hp = fmt(hp_plan["device_or_summon"])
        boss_hp = fmt(hp_plan["boss"])
        row[86], row[87], row[88] = enemy_hp, device_hp, boss_hp
        row[89], row[91] = atk, atk                      # atk 小怪/boss
        # 带 funnel 的层:炮台弹幕同吃 boss 倍率,观感全算在"boss 伤害"头上 → 单独降档
        row[90] = fmt(frec["atk"] * ex_atk_factor * FUNNEL_ATK_SCALE) if frec["funnel"] else atk
        row[92] = row[93] = "1"                          # tp 小怪/炮台
        row[94] = str(curse["tp"]) if curse["tp"] else "1"   # boss 韧性(官方无尽先例×9)
        row[97] = str(curse["fever"]) if curse["fever"] else row[97]
        row[100] = str(curse["time"]) if curse["time"] else row[100]
        # 诅咒词条:battle_enemy_condition_1..5(c71-80)+ 副标题(c3)
        for slot in range(5):
            kind, strength = curse["conds"][slot] if slot < len(curse["conds"]) else ("(None)", "")
            row[71 + slot * 2] = kind
            row[72 + slot * 2] = strength
        row[3] = curse["desc"] if curse["desc"] else "(None)"
        if BUILD_MODE in ("normal", "ex") and curse.get("element_resistance"):
            # One authoritative element carrier also feeds the native detail UI.
            # Pre-action programs deliberately omit these same elements.
            import wf_rogue_element_channel as element_channel
            row[3] += " " + element_channel.encode(
                _resistance_totals_by_target(curse["picks"], "element_resistance"))
        pick = frec["pick"]
        if details_ui_enabled or BUILD_MODE == "ex":
            row[3] = quest_details.for_generated_floor(frec)
        eff = f" | {curse['desc']}" if curse["desc"] else ""
        # boss 层的 HP 已由 boss_level.c2（general）或反解 c86（standard）
        # 精确落表；旧 bh/HP normalize 只剩 raw 诊断量，不能再打印成“补偿”误导。
        if audit["family"] == "no-boss":
            boost = (f" 补偿hp×{frec['bh']:.2f}/atk×{frec['ba']:.2f}"
                     if (frec["bh"], frec["ba"]) != (1.0, 1.0) else "")
        else:
            boost = (f" 补偿atk×{frec['ba']:.2f}"
                     if frec["ba"] != 1.0 else "")
        if pick.get("norm") and pick["norm"] != (1.0, 1.0):
            if audit["family"] == "no-boss":
                boost += f"(含归一 ×{pick['norm'][0]:.2f}/×{pick['norm'][1]:.2f})"
            else:
                boost += (f"(HP归一raw×{pick['norm'][0]:.2f}未落表;"
                          f"ATK归一×{pick['norm'][1]:.2f})")
        fdisp = pick["field"] + (f"→{pick['play_field']}" if pick.get("play_field") else "")
        fun = f" 炮台atk×{row[90]}" if frec["funnel"] else ""
        if audit.get("target_exempt"):
            hp_mark = (("绝对" if audit.get("absolute_verified") else "代理")
                       + "·未归一")
        else:
            hp_mark = ("绝对" if audit.get("absolute_verified") else
                       ("代理" if audit["verified"] else "估算/无boss"))
        plan_lines.append(f"  第{r}战 [{pick['label']}] lv{pick.get('level')} "
                          f"field={fdisp} hp(c86/c87/c88)="
                          f"{enemy_hp}/{device_hp}/{boss_hp} atk×{atk}{fun}{boost}"
                          f" 基线(c86={audit['baseline_c86']:g},"
                          f"HP={audit['baseline_true_hp'] / 1e8:.2f}亿,"
                          f"DPS={audit['baseline_dps']:,.0f}/s)"
                          f" 实战(HP={audit['true_hp'] / 1e8:.2f}亿,"
                          f"DPS={audit['realized_dps']:,.0f}/s,"
                          f"{audit['duration_s']:.0f}s,血咒×{audit['curse_hp']:g})"
                          f"[{hp_mark}]"
                          f"{frec['note']}{eff}")
        if args.strict_target_hp and isinstance(
                audit.get("adapter_audit"), HpAdaptationAudit):
            plan_lines.extend(hp_component_audit_lines(audit["adapter_audit"]))
    if band_log:
        plan_lines.append(f"  ---- 分位硬闸动作 {len(band_log)} 次 ----")
        plan_lines += [f"  {ln}" for ln in band_log]
    # ---- 数值带体检(发布前一眼看穿这座塔热不热)----
    _late = sorted(f["atk"] for f in floor_recs if f["r"] / args.rounds > BAND_FROM)
    _early = sorted(f["atk"] for f in floor_recs if f["r"] / args.rounds <= BAND_FROM)
    _hp = sorted(float(f["row"][88]) for f in floor_recs)
    _true_hp = sorted(float(f["hp_audit"]["true_hp"]) for f in floor_recs)
    _tdi = [f["anchor"][0] * f["atk"] / f["anchor"][1]
            for f in floor_recs if f["anchor"]]
    _lv = {}
    for f in floor_recs:
        _lv[f["pick"].get("level")] = _lv.get(f["pick"].get("level"), 0) + 1
    _bs = band_stats(_late)
    plan_lines.append(
        f"  [数值带] 中后段 col 中位 {_bs['median']:.2f}"
        f"/P90 {_bs['p90']:.2f}/max {_bs['max']:.2f}"
        f"(带 ≤{BAND_TARGET['median']}/≤{BAND_TARGET['p90']}/≤{BAND_TARGET['max']})"
        f" · 前段中位 {statistics.median(_early):.2f}"
        f" · hp col 中位 {statistics.median(_hp):.2f}/max {_hp[-1]:.2f}"
        f" · 真HP中位 {statistics.median(_true_hp) / 1e8:.2f}亿"
        + (f" · 真伤指数 max {max(_tdi):.2f}(闸 {TRUE_DMG_CAP})" if _tdi else "")
        + (f" · 曲线缩放 ×{curve_scale:.3f}" if curve_scale != 1.0 else ""))
    plan_lines.append("  [数值带] 敌等级:"
                      + " ".join(f"lv{k}×{v}" for k, v in sorted(_lv.items(),
                                                                 key=lambda kv: kv[0] or 0)))
    _verified_hp = [a for a in hp_audits if a["verified"]]
    _absolute_hp = [a for a in _verified_hp if a.get("absolute_verified")]
    _proxy_hp = [a for a in _verified_hp if not a.get("absolute_verified")]
    _general_audits = [a for a in _verified_hp if a["family"] == "general"]
    _identity_audits = [
        a for a in _verified_hp if str(a["family"]).startswith("identity-locked")]
    _standard_audits = [a for a in _verified_hp if a["family"] == "standard"]
    _mixed_audits = [a for a in _verified_hp if a["family"] == "mixed"]
    _orochi_audits = [a for a in _verified_hp if a["family"] == "orochi"]
    _orochi_ex_audits = [
        a for a in _verified_hp if a["family"] == "orochi_ex"]
    _single_special_audits = {
        family: [a for a in _verified_hp if a["family"] == family]
        for family in (*SINGLE_BAR_SPECIAL_SPECS, *SPHERE_SPECS)
    }
    _special_audits = (
        _orochi_audits + _orochi_ex_audits
        + [audit for family in (*SINGLE_BAR_SPECIAL_SPECS, *SPHERE_SPECS)
           for audit in _single_special_audits[family]])
    _unscaled_audits = [a for a in _verified_hp if a.get("target_exempt")]
    _general_scale = [a["family_scale"] for a in _general_audits]
    _identity_c86 = [float(a["c86"]) for a in _identity_audits]
    _standard_scale = [float(a["family_scale"]) for a in _standard_audits]
    _mixed_scale = [float(a["family_scale"]) for a in _mixed_audits]
    _special_scale = [float(a["family_scale"]) for a in _special_audits]
    _hp_first = next(a for a in hp_audits if a["r"] == 1)
    _hp_last = next(a for a in hp_audits if a["r"] == args.rounds)
    # “真 HP 占比”的分子分母都只用绝对证据；代理曲线层
    # 另报覆盖率，不得混进分母把“估算”写成“真 HP”。
    _std_hp = math.fsum(
        part.final_readback_hp
        for audit in _absolute_hp
        for part in ((audit.get("adapter_audit").components)
                     if isinstance(audit.get("adapter_audit"), HpAdaptationAudit)
                     else ())
        if part.kind == "standard")
    _all_absolute_hp = sum(a["true_hp"] for a in _absolute_hp)
    if args.ramp:
        if _hp_last.get("target_exempt"):
            _hp_gate_summary = (
                f"基线首战 DPS {_hp_first['baseline_dps']:,.0f}/s · "
                f"第{args.rounds}战未归一，保留原生 "
                f"{_hp_last['baseline_dps']:,.0f}/s")
        else:
            _hp_gate_summary = (
                f"基线首尾 DPS {_hp_first['baseline_dps']:,.0f}→"
                f"{_hp_last['baseline_dps']:,.0f} "
                f"({_hp_last['baseline_dps'] / _hp_first['baseline_dps']:.2f}×) · "
                f"第{args.rounds}战命中目标带 {_hp_last_band[0]:,.0f}~"
                f"{_hp_last_band[1]:,.0f}/s")
    else:
        _targeted_boss = [a for a in hp_audits
                          if a["r"] >= first_boss_round() and not a.get("target_exempt")]
        if _targeted_boss:
            _first_targeted = min(
                _targeted_boss, key=lambda item: int(item["r"]))
            _last_targeted = max(
                _targeted_boss, key=lambda item: int(item["r"]))
            _targeted_hp_summary = (
                f"诅咒前基础总HP "
                f"{_first_targeted['baseline_true_hp'] / 100_000_000:.2f}亿→"
                f"{_last_targeted['baseline_true_hp'] / 100_000_000:.2f}亿")
        else:
            _targeted_hp_summary = "没有可归一 Boss 层"
        _hp_gate_summary = (
            f"{'首战' if BUILD_MODE == 'ex' else '第1战热身'} {_hp_first['baseline_dps']:,.0f}/s · "
            f"可归一 boss层 {len(_targeted_boss)}/{args.rounds - first_boss_round() + 1} · "
            f"{_targeted_hp_summary}"
            + (f" · 未归一层 {','.join(str(a['r']) for a in _unscaled_audits)}"
               if _unscaled_audits else ""))
    plan_lines.append(
        f"  [真HP门禁] 绝对 {len(_absolute_hp)} 层 / 代理 {len(_proxy_hp)} 层 / "
        f"无boss估算 {len(hp_audits) - len(_verified_hp)} 层 · "
        f"{_hp_gate_summary}")
    if args.strict_target_hp:
        _strict_receipts = [
            audit["adapter_audit"] for audit in hp_audits
            if audit["r"] >= first_boss_round()
            and isinstance(audit.get("adapter_audit"), HpAdaptationAudit)
        ]
        _strict_max_error = max(
            (max(abs(item.baseline_error_hp), abs(item.final_error_hp))
             for item in _strict_receipts), default=0.0)
        plan_lines.append(
            f"  [严格HP] Boss关 {len(_strict_receipts)}/{args.rounds - first_boss_round() + 1} "
            f"绝对证据、未归一 0、代理 0、target_exempt 0 · "
            f"最大绝对回读误差 {_strict_max_error:g} HP · "
            f"容差 ±max({HP_TARGET_ABS_TOLERANCE:g},"
            f"target×{HP_TARGET_REL_TOLERANCE:g})")
    _standard_summary = (
        f"standard DSL Health 基线伸缩中位 ×"
        f"{statistics.median(_standard_scale):.3f}"
        if _standard_scale else "standard 0层")
    _mixed_summary = (
        f"mixed c2/c5+DSL 基线伸缩中位 ×"
        f"{statistics.median(_mixed_scale):.3f}"
        if _mixed_scale else "mixed 0层")
    _identity_c86_summary = (
        f"identity-locked c86={min(_identity_c86):g}~{max(_identity_c86):g}"
        f"（门禁 {STANDARD_C86_LIMITS[0]:g}~{STANDARD_C86_LIMITS[1]:g}）"
        if _identity_c86 else "identity-locked 0层")
    _special_summary = (
        f"special_bundle(普通 {len(_orochi_audits)} / "
        f"EX {len(_orochi_ex_audits)} / Kraken "
        f"{len(_single_special_audits['kraken'])} / 指挥者 "
        f"{len(_single_special_audits['conductor'])} / CEO "
        f"{len(_single_special_audits['touyakiren_ceo'])} / Sphere "
        + ",".join(
            f"{SPHERE_SPECS[family]['label']} "
            f"{len(_single_special_audits[family])}"
            for family in SPHERE_SPECS)
        + ") 基线伸缩中位 ×"
        f"{statistics.median(_special_scale):.3f}"
        if _special_scale else "special_bundle 0层")
    plan_lines.append(
        f"  [实战诅咒] DPS "
        f"{min(a['realized_dps'] for a in hp_audits):,.0f}~"
        f"{max(a['realized_dps'] for a in hp_audits):,.0f}/s · "
        f"短时限高血量 0 层 · general c86=1"
        f"（boss_level.c2/c5 主伸缩）· {_identity_c86_summary} · {_standard_summary}")
    plan_lines.append(
        f"  [按族分治] general {len(_general_audits)} 层 / "
        f"mixed {len(_mixed_audits)} 层 / "
        f"identity-locked {len(_identity_audits)} 层 / "
        f"standard {len(_standard_audits)} 层 / "
        f"special_bundle {len(_special_audits)} 层 / "
        f"可读但未归一 {len(_unscaled_audits)} 层 · "
        + (f"general boss_level.c2/c5 基线伸缩中位 ×"
           f"{statistics.median(_general_scale):.3f}"
           if _general_scale else "general 无可验层")
        + " · "
        + (_mixed_summary if _mixed_scale else "mixed 无可验层")
        + " · "
        + (_identity_c86_summary if _identity_c86
           else "identity-locked 无可验层")
        + " · "
        + (_standard_summary if _standard_scale else "standard 无可验层")
        + " · "
        + (_special_summary if _special_scale else "special_bundle 无可验层")
        + (f" · standard 绝对真HP占比 {_std_hp / _all_absolute_hp:.1%}"
           if _all_absolute_hp else ""))
    _field_requested = sum(int(f["curse"].get("field_requested") or 0)
                           for f in floor_recs)
    _field_total = sum(int(f["curse"].get("field_applied") or 0)
                       for f in floor_recs)
    _field_quota_applied = sum(
        min(int(f["curse"].get("field_applied") or 0),
            int(f["curse"].get("field_requested") or 0))
        for f in floor_recs)
    _field_deficit_floors = [f for f in floor_recs
                             if f["curse"].get("field_deficit")]
    _deep_time = [f["r"] for f in floor_recs
                  if is_deep_round(f["r"], args.rounds)
                  and f["curse"].get("time") is not None]
    plan_lines.append(
        f"  [领域/时限] 领域保底完成 {_field_quota_applied}/{_field_requested} 个"
        f"（全塔实际 {_field_total} 个）· "
        f"欠配 {len(_field_deficit_floors)} 层"
        + ("(" + ",".join(str(f["r"]) for f in _field_deficit_floors) + ")"
           if _field_deficit_floors else "")
        + f" · 深层时限诅咒 {len(_deep_time)} 层")

    # 无尽档:folder 2 / round 0,修正曲线接管难度(quest 行修正=round-0 锚点)
    endless_pick = tower_pick()
    tower_bosses += endless_pick["bosses"]
    for _k in name_keys(endless_pick["bosses"]):
        used_counts[_k] = used_counts.get(_k, 0) + 1
    endless_row = list(tmpl_endless)
    endless_row[0] = str(int(EVENT_ID) * 1000 + int(ENDLESS_KEY))
    endless_row[1] = "2"
    endless_row[2] = "0"
    enforce_gauntlet_player_rank(endless_row)
    rec = patch_common(endless_row, f"{EVENT_NAME} 无尽", endless_pick)
    if BUILD_MODE == "ex":
        endless_row[6] = endless_row[68] = "(None)"
        for column in (81,82,83,84,85,102):
            endless_row[column] = "0"
    quest_rows[ENDLESS_KEY] = endless_row
    plan_lines.append(f"  无尽 [{endless_pick['label']}] field={endless_pick['field']}{rec}(曲线抄 700007 现值)")

    _profile = "legacy-dps-ramp" if args.ramp else "linear-boss-hp"
    _target_summary = (
        f"{_hp_first['target_dps']:,.0f}→{_hp_last['target_dps']:,.0f}"
        if args.ramp else
        f"boss层={next(a['target_dps'] for a in hp_audits if a['r'] == 2):,.0f}→"
        f"{_hp_last['target_dps']:,.0f};第1战热身={_hp_first['target_dps']:,.0f}")
    print(f"seed={args.seed} rounds={args.rounds} profile={_profile} "
          f"difficulty={args.difficulty or '(旧默认)'} curse={args.curse or '(随难度)'} "
          f"hp(raw)={fmt(hp_base)}×{fmt(hp_growth)}^r "
          f"targetDPS={_target_summary} "
          f"atk={fmt(atk_base)}×{fmt(atk_growth)}^r")
    print("\n".join(plan_lines))

    # ---- 硬门禁复核:构建产物(含克隆场/法阵 boss)全链可解析,任一悬空拒绝产出 ----
    # The final chain must see this build's in-memory Orochi clones.  A cached
    # store-wide code union can both miss a fresh parent and let the wrong
    # constructor table satisfy a duplicate code, so inject every exact special
    # table and validate the zone's (BossKind, code) pair.
    final_special_tables: dict[str, dict] = {}
    for logical in SPECIAL_BOSS_TABLES:
        short = Path(logical).name.removesuffix(".orderedmap")
        if logical == OROCHI:
            final_special_tables[short] = oro_t
            continue
        if logical == OROCHI_EX:
            final_special_tables[short] = oro_ex_t
            continue
        if short in single_bar_special_tables:
            final_special_tables[short] = single_bar_special_tables[short]
            continue
        if short in sphere_tables:
            # Sphere parents are cloned in memory exactly like the other
            # dedicated families.  The final BossKind/code proof must inspect
            # that live table, not reload the pre-build store snapshot.
            final_special_tables[short] = sphere_tables[short]
            continue
        try:
            final_special_tables[short] = q.load_table(logical)
        except Exception:
            final_special_tables[short] = {}
    identity_clone_errors = [
        (clone, source, identity_clone_locked_boss_reason(
            [source], code_references=code_refs))
        for clone, source in sorted(clone_sources.items())
        if identity_clone_locked_boss_reason(
            [source], code_references=code_refs) is not None
    ]
    if identity_clone_errors:
        for clone, source, why in identity_clone_errors:
            print(f"[ERR] identity-locked source clone:{source}->{clone}: {why}")
        print("[ERR] identity-locked source 被写成 mod_rogue_boss*,拒绝产出")
        return 1
    watch_alias_errors = []
    partner_sources = set(map(
        str, code_refs.get("enemy_watch_partner") or ()))
    for clone, source in sorted(clone_sources.items()):
        if source not in partner_sources:
            continue
        why = (enemy_watch_partner_alias_error(ew_t, source, clone)
               if ew_t is not None else "general_enemy_watch unavailable")
        if why:
            watch_alias_errors.append((clone, source, why))
    if watch_alias_errors:
        for clone, source, why in watch_alias_errors:
            print(f"[ERR] enemy_watch partner closure:{source}->{clone}: {why}")
        print("[ERR] identity-locked partner alias 闭包不完整,拒绝产出")
        return 1
    closed_watch_clones = sum(
        1 for clone, source in clone_sources.items()
        if source in partner_sources and clone_watch_alias_counts.get(clone, 0) > 0)
    print("[门禁] identity-locked source clone 0"
          f"（本轮审计 {len(clone_sources)} 个 mod_rogue_boss* 映射；"
          f"enemy_watch partner 闭包 {closed_watch_clones} 个）")

    final_validation = boss_ref_validation_tables(
        standard_boss=sb_t, general_boss=gb_t,
        general_boss_variable=gv_t,
        special_tables=final_special_tables)
    reports = validate_built_rows(
        quest_rows, fd_t, zone_t,
        set(gb_t) | set(sb_t) | set(gz_t), set(gz_t),
        lv_ceil=sb_t, lv_floor=gv_t, lv_gb=gb_t,
        validation_tables=final_validation)
    broken = [r for r in reports if not r["ok"]]
    if broken:
        for r in broken:
            print(f"[ERR] 第{r['round']}战 field={r['field']} 引用悬空:"
                  + "; ".join(r["errors"]))
        print(f"[ERR] {len(broken)}/{len(reports)} 关解析链断裂,拒绝产出(未写入任何表)")
        return 1
    print(f"[门禁] {len(reports)} 关解析链复核通过(quest→field→zone→boss/zako 全可解析)")
    if caster_blocked:
        print(f"[门禁] 成对/分阶段 · 被代号引用的 boss 层已禁发深渊法阵"
              f"({len(caster_blocked)} 个场地):")
        for _f, _why in sorted(caster_blocked.items()):
            print(f"        {_f} — {_why}")

    for floor_record in floor_recs:
        floor_record["identity_reference_closures"] = copy.deepcopy(
            identity_reference_closures.get(int(floor_record["r"]), ()))

    if args.audit_json or args.audit_report:
        try:
            _baseline_targets = {
                int(audit["r"]): (
                    float(audit["target_dps"])
                    * float(audit["base_duration_s"]))
                for audit in hp_audits if int(audit["r"]) >= first_boss_round()
            }
            _canonical_linear_hp = (
                not args.ramp
                and set(_baseline_targets) == set(range(first_boss_round(), args.rounds + 1))
                and all(math.isclose(
                    _baseline_targets[round_no],
                    boss_target_hp(round_no, args.rounds),
                    rel_tol=1e-12, abs_tol=1e-4)
                    for round_no in range(first_boss_round(), args.rounds + 1))
            )
            _audit_hp_profile = (
                "legacy_geometric_dps" if args.ramp else
                "ex_tiered_boss_hp" if BUILD_MODE == "ex" and _canonical_linear_hp else
                "normal_boss_hp_20e8_100e8" if BUILD_MODE == "normal" and _canonical_linear_hp else
                "linear_boss_hp_30e8_150e8" if _canonical_linear_hp else
                "configured_boss_hp")
            audit_document = build_hp_audit_document(
                seed=args.seed, rounds=args.rounds,
                difficulty=args.difficulty or "legacy",
                enemy_level=_lvarg,
                hp_audits=hp_audits, floor_records=floor_recs,
                chain_reports=reports, hp_profile=_audit_hp_profile,
                curse_diversity=curse_diversity_receipt(
                    curse_diversity_state))
            audit_errors = verify_hp_audit_document(
                audit_document,
                expected_tool_sha256=tool_source_sha256())
            if audit_errors:
                for error in audit_errors:
                    print(f"[ERR] HP 验收回执自检:{error}")
                return 1
            if args.audit_json:
                write_hp_audit_document(args.audit_json, audit_document)
            if args.audit_report:
                write_hp_audit_report(
                    args.audit_report, audit_document,
                    expected_tool_sha256=tool_source_sha256())
        except (OSError, TypeError, ValueError) as exc:
            print(f"[ERR] HP 验收回执/报告生成失败:{exc}")
            return 1
        if args.audit_json:
            print(f"[AUDIT] HP 验收回执已生成:{args.audit_json} "
                  f"sha256={audit_document['document_sha256']}")
        if args.audit_report:
            print(f"[REPORT] HP 中文验收报告已生成:{args.audit_report}")

    if BUILD_MODE == "ex":
        try:
            final_pick = floor_recs[-1]["pick"]
            abyss_ex.assert_final_clones(
                quest_rows["30"][98], fd_t, zone_t, gb_t,
                final_pick.get("runtime_bosses") or [], PRIVATE_PREFIX,
                cells, zone_boss_slots)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            print(f"[ERR] EX 第30战剥离克隆回读失败:{exc}")
            return 1

    if candidate_sink is not None:
        from wf.tools.rogue.rogue_candidate import collect_candidate
        candidate_sink(collect_candidate(locals(), builder=sys.modules[__name__]))
    if not args.write:
        print("[DRY-RUN] 未写入。加 --write 生效,--publish 顺带发 CDN。")
        return 0

    # 写 ② 层(save_table 自动备份)。written = 本次实际落盘的逻辑路径清单,
    # 发布清单/发布自检直接从它派生——"写了没发布"(C8601 key=mod_rogue_f9)从结构上封死。
    written: list[str] = []

    def save(logical: str, tree: dict) -> None:
        q.save_table(logical, tree)
        written.append(logical)

    if BUILD_MODE == "ex":
        # AdditionalRewardLogic dereferences every server result group/index.
        # Include the EX group in the same generated publication file list.
        with open(os.path.join(server_root, "assets", "rogue_event.json"), encoding="utf-8-sig") as fh:
            reward_config = json.load(fh)["events"][EVENT_ID]
        extension = Path(server_root) / "assets" / "rogue_event_cnmod.json"
        if extension.exists():
            with extension.open(encoding="utf-8-sig") as fh:
                reward_config = {**reward_config, **json.load(fh).get("events", {}).get(EVENT_ID, {})}
        reward_logical = "master/reward/event/additional_reward.orderedmap"
        reward_table = q.load_table(reward_logical)
        reward_table.update(abyss_modes.additional_reward_rows(reward_config))
        save(reward_logical, reward_table)

    # 先落未被任何表引用的 action 文件；全部成功后才写 general_boss/quest。
    # 临时文件与目标同目录,os.replace 原子切换,避免中断留下半截 deflate。
    for program, tree in sorted(immunity_programs.items()):
        logical = program + ".action.dsl.amf3.deflate"
        dst = q.store_path(logical)
        dst.parent.mkdir(parents=True, exist_ok=True)
        blob = build_immunity_dsl_blob(tree)
        tmp = dst.with_name(dst.name + ".tmp-wf-rogue-immunity")
        tmp.write_bytes(blob)
        os.replace(tmp, dst)
    if immunity_programs:
        print(f"[OK] 耐性 DSL 已写入 {len(immunity_programs)} 个 action")

    for logical, blob in sorted(standard_resource_blobs.items()):
        # 资源先于 standard_boss 表切换；中断时最多留下未引用的孤立资源，
        # 不会让客户端看见已引用却尚不存在的 Enemy DSL。
        dst = q.store_path(logical)
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".tmp-wf-rogue-standard")
        tmp.write_bytes(blob)
        os.replace(tmp, dst)
    if standard_resource_blobs:
        print(f"[OK] Standard Enemy DSL 已写入 {len(standard_resource_blobs)} 个资源")

    # Dependency-first save order: head rows before Orochi parent, then the
    # field/zone that references that parent, and only then quest rows.  Each
    # save_table is still a per-file operation; this is reference-safe ordering,
    # not a claim of cross-table disk transactionality.
    battle_values = {
        GENERAL_ZAKO: gz_t,
        ZAKO_LEVEL: zl_t,
        GENERAL_BOSS: gb_t,
        GENERAL_BOSS_STATE: gbs_t,
        BOSS_LEVEL: bl_t,
        GENERAL_BOSS_VARIABLE: gv_t,
        ENEMY_WATCH: ew_t,
        OROCHI: oro_t,
        OROCHI_EX_HEAD: oro_ex_head_t,
        OROCHI_EX: oro_ex_t,
        STANDARD_BOSS: sb_t,
        FIELD_DATA_T: fd_t,
        ZONE_T: zone_t,
        **{
            str(SINGLE_BAR_SPECIAL_SPECS[family]["logical"]): table
            for family, table in single_bar_special_tables.items()
        },
        **{
            str(SPHERE_SPECS[family]["logical"]): table
            for family, table in sphere_tables.items()
        },
        **{
            str(SPHERE_AUX_LOGICALS[name]): table
            for name, table in sphere_aux_tables.items()
        },
    }
    battle_plan = rogue_battle_write_plan(
        gimmick_dirty=gim_dirty, caster_dirty=caster_dirty,
        orochi_dirty=orochi_dirty,
        enemy_watch_available=ew_t is not None,
        general_state_dirty=general_state_dirty,
        standard_dirty=standard_dirty,
        orochi_ex_dirty=orochi_ex_dirty,
        single_bar_special_dirty=tuple(sorted(single_bar_special_dirty)),
        sphere_dirty=tuple(sorted(sphere_dirty)))
    for logical in battle_plan:
        tree = battle_values.get(logical)
        if not isinstance(tree, dict):
            raise RuntimeError(f"battle write plan 缺内存表:{logical}")
        save(logical, tree)
    if caster_dirty:
        print("[OK] 法阵载体依赖已写入(zako + general boss 附表)")
    if general_state_dirty:
        print("[OK] General Boss 红条私有状态已写入(c16 绝对门槛闭包)")
    if orochi_dirty:
        print("[OK] 八岐父体整包已写入(head 依赖 → orochi parent)")
    if orochi_ex_dirty:
        print("[OK] 八岐 EX 整包已写入(六子体/boss_level → kind-4 parent)")
    if single_bar_special_dirty:
        print("[OK] 专用单血条整包已写入(boss_level → dedicated parent):"
              + ",".join(sorted(single_bar_special_dirty)))
    if sphere_dirty:
        print("[OK] Sphere 整包已写入(boss_level → 阶段子体 → dedicated parent):"
              + ",".join(sorted(sphere_dirty)))
    if standard_dirty:
        print("[OK] Standard Boss HP 克隆表已写入(standard_boss)")
    if gim_dirty:
        print("[OK] 场地克隆已写入(field_data / zone)")

    ev[EVENT_ID] = join(ev_row, ev_bytes)
    save(Q_EVENT, ev)
    fo[EVENT_ID] = {"1": folder_leaf, "2": join(fo_endless, fo_bytes)}
    save(Q_FOLDER, fo)
    qt[EVENT_ID] = {k: join(v, qt_bytes) for k, v in quest_rows.items()}
    save(Q_QUEST, enforce_gauntlet_quest_table_player_rank(qt))
    el = q.load_table(Q_LIST)
    save(Q_LIST, enforce_gauntlet_hub_event_list(el))
    # 无尽修正曲线:抄 700007 无尽当前值(已是缓坡)→ [700099][2][99]
    corr = q.load_table(Q_CORR)
    src_curve = corr[TEMPLATE_EVENT]["4"]["8"]
    corr[EVENT_ID] = {"2": {ENDLESS_KEY: dict(src_curve)}}
    save(Q_CORR, corr)
    print("[OK] ②层五表已写入(rush_event / folder / quest / event_list / correction)")

    # 服务端 json
    quest_json_path = os.path.join(
        server_root, "assets", "rush_event_quest.json"
    )
    with open(quest_json_path, encoding="utf-8") as fh:
        quest_json = json.load(fh)
    tmpl_entry = quest_json[f"{TEMPLATE_EVENT}001"]
    for r in range(1, args.rounds + 1):
        entry = dict(tmpl_entry)
        entry["rushEventId"] = int(EVENT_ID)
        entry["rushEventFolderId"] = 1
        entry["rushEventRound"] = r
        quest_json[str(int(EVENT_ID) * 1000 + r)] = entry
    endless_entry = dict(tmpl_entry)
    endless_entry["rushEventId"] = int(EVENT_ID)
    endless_entry["rushEventFolderId"] = 2
    endless_entry["rushEventRound"] = 0
    quest_json[str(int(EVENT_ID) * 1000 + int(ENDLESS_KEY))] = endless_entry
    # 清掉多余轮(rounds 缩小时;99=无尽键不在范围内,rounds 上限 98)
    for r in range(args.rounds + 1, 99):
        quest_json.pop(str(int(EVENT_ID) * 1000 + r), None)
    # newline="\n" 是必须的:Windows 上文本模式默认吐 CRLF,而仓库 .gitattributes
    # 是全 LF。git 的 text=auto 归一化会把差异藏起来(status 显示干净),但发布回执
    # 的 _server_evidence 哈希的是**原始字节** ⇒ 跑过一次重摇之后
    # `npm run verify:local-release` 就红,报 "server terminal evidence mismatch",
    # 而 git diff 又看不出任何改动。2026-08-07 实测 7 个服务端 json 全中招。
    with open(quest_json_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(quest_json, fh, ensure_ascii=False, indent=1)

    folder_json_path = os.path.join(
        server_root, "assets", "rush_event_quest_folder.json"
    )
    with open(folder_json_path, encoding="utf-8") as fh:
        folder_json = json.load(fh)
    # 保留自定义通关奖励(2026-07-28 起服务端 json 的 700099 奖励由用户定制,
    # 重摇只在条目缺失时才从模板补种)
    folder_json.setdefault(EVENT_ID, {"1": fixed_rewards})
    with open(folder_json_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(folder_json, fh, ensure_ascii=False, indent=1)
    print("[OK] 服务端 json 已写入(rush_event_quest / rush_event_quest_folder)——静态 import,须重启服务端")
    save_boss_history(tower_bosses)
    print(f"[历史] 本塔 {len(set(tower_bosses))} 个 boss 已记账(近 3 座塔降权去重)")

    # 发布清单 = 本次落盘清单 + 锻造 DSL,全部用完整逻辑路径(不依赖别名)
    pub_items = written + sorted(forged_pubs)
    pub_tables = ",".join(pub_items)
    if args.publish:
        r = subprocess.run([sys.executable, os.path.join(MOD_DIR, "wf_publish.py"),
                            "--tables", pub_tables],
                           cwd=server_root)
        print(f"[PUBLISH] wf_publish 退出码 {r.returncode}")
        if r.returncode != 0:
            print("[ERR] 发布失败:表已写入 store 但 CDN 未更新,勿清进度/勿重启客户端,"
                  f"修复后补发:python mod-tools/wf_publish.py --tables {pub_tables}")
            return r.returncode
        problems = verify_cdn_chain(pub_items)
        if problems:
            for logical, why in problems:
                print(f"[ERR] 发布自检:{logical}: {why}")
            print(f"[ERR] 发布不完整({len(problems)}/{len(pub_items)} 个文件未上链),"
                  f"补发:python mod-tools/wf_publish.py --tables {pub_tables}")
            return 1
        print(f"[OK] 发布自检通过:{len(pub_items)} 个文件全部在 CDN 链上且字节一致")
    else:
        print(f"记得发布:python mod-tools/wf_publish.py --tables {pub_tables}")
    return 0
