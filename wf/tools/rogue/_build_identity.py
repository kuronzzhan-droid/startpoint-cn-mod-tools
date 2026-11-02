# Source section of rogue_build; loaded in its shared module namespace.
def zone_boss_slots(zn) -> list[set[str]]:
    """zone 嵌套 dict → 每个**已占用** boss 槽的代号集合(单人/多人列合并)。

    返回长度 = 该 zone 实际会出场的 boss 实体数(跨波次累加)。
    """
    out: list[set[str]] = []
    for slot in _legacy_active_boss_slots(zn):
        codes = {ref.code for ref in (slot.single, slot.multi) if ref is not None}
        if codes:
            out.append(codes)
    return out


def zone_single_bosses(zn) -> list[str]:
    """从已解析/内存克隆 zone 读单人战实际 boss 实体列表。

    这是 `_zone_pick` 的内存态版；Task C `--mix` 会在还没落盘时克隆
    field/zone，继续读 store 旧表会把 donor 的未出场部分也算进 HP。
    """
    return [slot.single.code for slot in _legacy_active_boss_slots(zn)
            if slot.single is not None]


def _sync_boss_kind(wc: list[str], code_index: int, code: str, kind_of) -> None:
    """把 code_index 这一列的 BossKind 列(恒为左邻列)校正到与 code 相符。

    rbb.SLOT_COLUMNS 每槽 4 列 = (单人kind, 单人code, 多人kind, 多人code),
    所以 kind 列 = code 列 − 1。kind_of 返回 None 表示现值已自洽。"""
    if kind_of is None:
        return
    k = code_index - 1
    if k < 0 or k >= len(wc):
        return
    want = kind_of(code, wc[k])
    if want is not None and str(want) != str(wc[k]):
        wc[k] = str(want)


def apply_boss_swap(wc: list[str], old: str, new: str, kind_of=None) -> list[str]:
    """把 zone wave 行里的 boss 代号 old 换成 new——**单人 + 多人两列都换**。

    客户端 ZoneSourceValues.get_bossN() 按 isSingleBattle 二选一读
    (single→c24/28/32,multi→c26/30/34),只换半边的话另一种战斗模式仍指向
    原 boss:法阵载体克隆静默失效,成对 boss 变成「克隆 + 原体」各打各的。
    2026-07-30 修(swap_zone_bosses 六列全换,gimmick_field 这条路漏了三列)。
    2026-08-07 增 kind_of:代号列换了,BossKind 列必须跟着换,见
    zone_boss_kind_fixer。
    """
    for a, b in ZONE_BOSS_SLOTS:
        for i in (a, b):
            if len(wc) > i and wc[i] == old:
                wc[i] = new
                _sync_boss_kind(wc, i, new, kind_of)
    return wc


def swap_zone_bosses(zn: dict, bosses: list[str], kind_of=None) -> dict:
    """zone 嵌套 dict 的 boss 槽(单人 c24/28/32 + 多人 c26/30/34)按序循环换成 bosses。

    zako 槽(c2-20)与其余列原样保留——zako 出生锚点属于地形,跨地形移植会静默失败,
    boss 槽则全 boss 场地形通用(gimmick_field boss_swap 同机制,已真机验证)。

    kind_of(见 zone_boss_kind_fixer)负责同步 BossKind 列:`--mix` 把 donor
    的 boss 换进地形老家的 zone,而地形老家可能是 kraken/orochi/*_sphere 的
    场子,kind 列不跟着改就会让客户端拿 general 代号去专表里查。
    """
    out = {}
    bi = 0
    for wk, wrow in zn.items():
        wc = cells(wrow)
        for single_i, multi_i in ZONE_BOSS_SLOTS:
            occupied = [i for i in (single_i, multi_i)
                        if len(wc) > i and wc[i] not in ("", "(None)")]
            if not occupied:
                continue
            code = bosses[bi % len(bosses)]
            for i in occupied:
                wc[i] = code
                _sync_boss_kind(wc, i, code, kind_of)
            bi += 1
        out[wk] = join(wc, isinstance(wrow, (bytes, bytearray)))
    return out


_PHASE_LINKED: frozenset[str] | None = None


def phase_linked_bosses(zone_t: dict | None = None,
                        fd_t: dict | None = None,
                        bbq_t: dict | None = None) -> frozenset[str]:
    """**数据驱动**的「成对 / 分阶段」boss 名单(不硬编码任何名字)。

    两路信号并集:
      A. 官方成对出场——boss 在**官方任一 zone 的同一波次**里与别的 boss 实体
         共存(青之女王 form1/form2、深渊之兽云 cloud/p3、机工神兵 multi/foom2、
         风神/雷神…)。
      B. 官方阶段链——boss 出现在 `boss_battle_quest`(三层嵌套 章→战斗→阶段,
         c109=field)同一场**战斗**的多个阶段里,且各阶段 boss 组互不相同
         (维·索拉斯 不死王→猫头鹰 是典型:zone 各自单实体,只有 A 抓不到)。

    这类 boss 的击杀/转场联动按**代号**串联,法阵载体克隆只换得动其中一只
    (make_caster_boss 只克隆首只 general boss),联动一断就表现为「打不死」
    (2026-07-30 玩家实测)。进程内缓存。
    """
    global _PHASE_LINKED
    if _PHASE_LINKED is not None and zone_t is None and fd_t is None and bbq_t is None:
        return _PHASE_LINKED
    zone = zone_t if zone_t is not None else _tbl(ZONE_T)
    fd = fd_t if fd_t is not None else _tbl(FIELD_DATA_T)
    try:
        bbq = bbq_t if bbq_t is not None else _tbl("master/quest/boss_battle_quest.orderedmap")
    except Exception:
        bbq = {}
    flagged: set[str] = set()
    # ---- A:同 wave 多实体 ----
    for zk, zv in zone.items():
        if str(zk).startswith("mod_rogue"):
            continue                    # 自家克隆层不当判据(否则越滚越大)
        slots = zone_boss_slots(zv)
        if len(slots) > 1:
            for s in slots:
                flagged |= s
    # ---- B:boss_battle_quest 阶段链 ----
    def _field_bosses(fid: str) -> set[str]:
        frow = fd.get(fid)
        if frow is None or isinstance(frow, dict):
            return set()
        fc = cells(frow)
        if len(fc) < 3:
            return set()
        out: set[str] = set()
        for s in zone_boss_slots(zone.get(fc[2])):
            out |= s
        return out

    for chv in bbq.values():
        if not isinstance(chv, dict):
            continue
        for btv in chv.values():
            if not isinstance(btv, dict):
                continue
            per_phase = []
            for row in btv.values():
                if isinstance(row, dict):
                    continue
                c = cells(row)
                fid = c[109] if len(c) > 109 else ""
                if fid and fid != "(None)":
                    bs = _field_bosses(fid)
                    if bs:
                        per_phase.append(frozenset(bs))
            if len({s for s in per_phase}) > 1:      # 同一场战斗出现 ≥2 组不同 boss
                for s in per_phase:
                    flagged |= set(s)
    result = frozenset(flagged)
    if zone_t is None and fd_t is None and bbq_t is None:
        _PHASE_LINKED = result
    return result


# general_boss 的 subroutine_change2/3/4 = c45-51 / c52-58 / c59-65,
# 每段的 kind 列 = c48 / c55 / c62(客户端 GeneralBossValues:866-916 实锤):
#   "0"=Normal、"1"=Withstand(状态ID)、"2"=WithstandState —— 1/2 都是**转阶段无敌**。
# ⚠ 只作诊断用,**不要拿它当门禁判据**(2026-08-03 已证伪):无敌的解除是
# GeneralBossOrFunnel.exitUniqueState:496-513 —— boss 离开 invincible_end_state
# 指名的那个 unique state 时清标志位,而该态的 termination_condition 是纯帧计数
# (shark phase2_change=Time(120)、haniwa phase2_move1=Move(15)/phase3_neutral1=Time(10)),
# 与伤害/韧性/眩晕完全解耦;官方 182 条 Withstand 相位条目里终止条件为无限的**零命中**。
# 眩晕更不可能是解除前提:stunIfPossible 自带 `!isInvincible()` 前置(EnemyImpl:1070),
# 那样会构成死锁。
WITHSTAND_KIND_COLS = (48, 55, 62)


def withstand_phase_boss(code: str, gb_t: dict | None = None) -> bool:
    """该 boss 是否带「转阶段无敌」(Withstand / WithstandState)。**仅诊断用**,见上方注释。"""
    gb = gb_t if gb_t is not None else _tbl(GENERAL_BOSS)
    node = gb.get(code)
    if node is None:
        return False
    leaf = node
    while isinstance(leaf, dict):
        leaf = leaf[next(iter(leaf))]
    if not isinstance(leaf, str):
        leaf = leaf.decode("utf-8", "replace")
    c = cells(leaf)
    return any(len(c) > i and c[i] in ("1", "2") for i in WITHSTAND_KIND_COLS)


# ---- 「按 boss 代号的外部引用」集合(2026-08-03 玩家实锤的真凶)----
# 法阵载体克隆改的是 **zone 里的 boss 代号**(shark → mod_rogue_boss10)。客户端里
# boss 代号除了自己那三张表(general_boss/boss_level/general_boss_variable,都已随克隆复制),
# 还被**别的实体反向按字符串引用**,这些引用克隆覆盖不到,改名即静默断链(不崩不报):
#
#   ① damage_share —— general_funnel 的 c32 = damage_share_target_boss_id
#      (GeneralFunnelValues:808)。绑定判据是「随从的该列 == boss 的 generalEnemyWatchSelfId
#      (就是 boss 代号)」(GeneralEnemy:1977-1990),绑上后打随从会**额外给 boss 压一条同额伤害**
#      (ImpactCalculator:536/563)。绑不上只是把 damageShareTarget 留成 null(GeneralEnemy:3434)。
#      → shark_blue/red/brown 的 c32 = 'shark';turretA~D 的 c32 = 'haniwa_great_wind'。
#        shark 本体的 subroutine 1 只有一个 neutral 挂血态,战斗内容全在三条鳍上,
#        断链后**打鳍完全白打**;旋风巨土俑四个炮台合计是本体血的 2.9 倍,官方杀法就是
#        砸炮台带穿本体,断链后只能硬啃本体 ⇒ 玩家报的「血量下不去」。
#   ② general_enemy_watch —— 表形状 [自身实体种类][selfCode][selfRoutine][对方实体种类][partnerCode]…,
#      ⚠ 第一层是**实体种类**(1=general boss / 2=funnel / 3=breakable block),
#      **不是** GeneralEnemyWatchKind 那个 9 值枚举(StateMatched/HpRatio/Winced/… 在叶子行的列里)。
#      实测顶层只有 "1"/"2";"2" 的 84 个 self 键与 general_boss 交集为 0(全是 funnel_*),
#      所以只取 "1" 两侧是完整的,不是拍脑袋。
#      self 侧和 partner 侧**都按代号索引**(GeneralEnemyWatchTable:24-30、
#      GeneralEnemyWatchTableTools.getSelfData/getPartnerValues,全 Maybe 容错、查不到静默返回 null)。
#      partner 侧(别人 watch 我)可在原 watcher 的 partner map 下**追加克隆 id
#      别名**，保留官方键不变；self 侧(我 watch 别人)则把整棵自身子树挂到新代号。
#      两边都由 make_caster_boss 闭合并随 general_enemy_watch 一起进入发布计划。
#   ③ next_state 的 test kind 15 = GeneralBossAlive(bossId)(GeneralBossStateValues:677-717)。
#      全库只有 raijin/hujin 互引,已被「多 boss 槽/成对族」两条覆盖,这里一并纳入判据兜底。
#
# 判别力(本轮 7 个法阵载体实测):shark、haniwa_great_wind **2/2 命中**;
# lich_wind_single、dark_matter_single、guardian_golem_another_light_single、
# treant_single、security_armour_single **5/5 放过**(它们在全库只出现在被克隆的三张表里)。
# 对比之下「带 Withstand 就禁」误杀 14 只无人引用的 boss —— 第4关的 dark_matter_single
# 正是被克隆的 Withstand 载体且玩家零反馈,现成反证。
GENERAL_FUNNEL = "master/battle/boss/funnel/general_funnel.orderedmap"
ENEMY_WATCH = "master/battle/boss/general_enemy_watch.orderedmap"
FUNNEL_DMGSHARE_COL = 32            # GeneralFunnelValues.as:808-809
BOSS_ALIVE_TEST, BOSS_ALIVE_ID_COL = "15", 30   # GeneralBossStateValues.as:677-717
_CODE_REFS: dict[str, frozenset[str]] | None = None


def code_referenced_bosses(gb_t: dict | None = None) -> dict:
    """按「能不能靠克隆补救」把代号引用分成两档,外加一个 degraded 失败标志。

      hard —— 所有外部反向引用的兼容并集，供“异地搬运”门禁使用；包含
              damage_share、enemy_watch partner、GeneralBossAlive。
      damage_share / boss_alive —— **当前补不了**，原场地改名也会断链。
      enemy_watch_partner —— 原场地改名可通过新增 partner 别名子树补齐，
              但异地搬运仍不安全（watcher/funnel 没被一起搬走）。
      soft —— **能补**:enemy_watch 的 self 侧(我自己的观察表),整棵子树挂到新代号下即可
              (make_caster_boss 已实现)。补齐后这类可以正常当法阵载体。
      degraded —— 任一来源没扫成。**必须 fail-closed**:名单只会偏小 = 漏拦,
              而漏拦的后果是线上 boss 打不死(实测 shark 与 haniwa_great_wind
              只靠 ① damage_share 这一路才认得出来,①塌了它们立刻回到候选池)。
              所以 degraded 时一律不发法阵,宁可这轮少几个落点。
    """
    global _CODE_REFS
    if _CODE_REFS is not None and gb_t is None:
        return _CODE_REFS
    hard: set[str] = set()
    damage_share: set[str] = set()
    enemy_watch_partner: set[str] = set()
    boss_alive: set[str] = set()
    soft: set[str] = set()
    degraded = False

    def _leaf(n):
        while isinstance(n, dict):
            n = n[next(iter(n))]
        return n if isinstance(n, str) else n.decode("utf-8", "replace")

    try:
        gb = gb_t if gb_t is not None else _tbl(GENERAL_BOSS)
    except Exception as e:      # 没有 store 的环境(CI / 上游 fork / 别人的克隆)
        print(f"[WARN] general_boss 读不到({e});本轮不发深渊法阵")
        return {"hard": frozenset(), "soft": frozenset(), "degraded": True}
    # ① damage_share:general_funnel c32
    try:
        for v in _tbl(GENERAL_FUNNEL).values():
            c = cells(_leaf(v))
            if len(c) > FUNNEL_DMGSHARE_COL and c[FUNNEL_DMGSHARE_COL] not in ("", "(None)"):
                damage_share.add(c[FUNNEL_DMGSHARE_COL])
    except Exception as e:
        print(f"[WARN] damage_share 扫描失败({e});本轮不发深渊法阵")
        degraded = True
    # ② general_enemy_watch:partner(实体种类=1)键 → hard;self 键 → soft
    try:
        ew = _tbl(ENEMY_WATCH)
        soft |= set(ew.get("1", {}))

        def _partner(node, depth=0):
            if not isinstance(node, dict):
                return
            for k, v in node.items():
                if depth == 3:
                    if str(k) == "1" and isinstance(v, dict):
                        enemy_watch_partner.update(v.keys())
                else:
                    _partner(v, depth + 1)
        _partner(ew)
    except Exception as e:
        print(f"[WARN] enemy_watch 扫描失败({e});本轮不发深渊法阵")
        degraded = True
    # ③ 状态机 next_state test kind 15 = GeneralBossAlive(bossId)
    try:
        def _scan_states(node):
            if isinstance(node, dict):
                for v in node.values():
                    _scan_states(v)
                return
            c = cells(_leaf(node))
            if len(c) > BOSS_ALIVE_ID_COL and c[29] == BOSS_ALIVE_TEST:
                if c[BOSS_ALIVE_ID_COL] not in ("", "(None)"):
                    boss_alive.add(c[BOSS_ALIVE_ID_COL])
        _scan_states(_tbl("master/battle/boss/general_boss_state.orderedmap"))
    except Exception as e:
        print(f"[WARN] BossAlive 扫描失败({e});本轮不发深渊法阵")
        degraded = True
    # Standard Funnel reverse links live inside ESDL, not general_funnel CSV.
    # Omitting them let the floor-12 HP clone silently sever both cores.
    standard_links = set()
    try:
        from wf_standard_enemy_links import funnel_boss_references
        standard_links = funnel_boss_references(
            _tbl(STANDARD_FUNNEL), cells, _read_standard_enemy_dsl)
        damage_share.update(code for kind, code in standard_links if kind == "damage_share")
        enemy_watch_partner.update(code for kind, code in standard_links if kind == "enemy_watch_partner")
    except Exception as exc:
        print(f"[WARN] Standard Funnel 反向引用扫描失败({exc});拒绝未经证明的克隆")
        degraded = True
    hard = damage_share | enemy_watch_partner | boss_alive
    codes = set(gb)
    result = {"hard": frozenset(hard & codes),
              "soft": frozenset((soft - hard) & codes),
              # 保留来源分类，供“原场地改名克隆”做更细的闭包判据。
              # enemy_watch partner 可以通过新增别名子树补齐；damage_share 与
              # BossAlive 仍需要克隆 funnel/action/state 所有者，继续 fail closed。
              "damage_share": frozenset(damage_share & codes),
              "enemy_watch_partner": frozenset(enemy_watch_partner & codes),
              "boss_alive": frozenset(boss_alive & codes),
              # Dedicated constructors do not live in general_boss, but a
              # parent-key clone must still prove that no generic runtime
              # object names that id.  Preserve the unfiltered sets for the
              # special-bundle identity gate; legacy general callers continue
              # using the filtered fields above.
              "all_damage_share": frozenset(damage_share),
              "all_enemy_watch_partner": frozenset(enemy_watch_partner),
              "all_enemy_watch_self": frozenset(soft),
              "all_boss_alive": frozenset(boss_alive),
              "standard_identity_references": frozenset(code for _, code in standard_links),
              "degraded": degraded}
    if gb_t is None:
        _CODE_REFS = result
    return result


def identity_locked_boss_reason(
        bosses, *, code_references: dict | None = None) -> str | None:
    """Return why an identity-changing operation must not touch ``bosses``.

    The authoritative identity-lock set combines General ``hard`` and
    ``standard_identity_references``: these ids are referenced by another
    runtime object and renaming them silently breaks damage sharing, partner
    watches, or phase-alive checks.  A degraded scan is fail-closed because its
    hard set is known to be incomplete.
    """
    codes = sorted({str(code) for code in bosses if str(code)})
    if not codes:
        return None
    if "shark_score_event" in codes:
        return "shark_score_event 是不可击杀的计分活动族，不能用于击杀通关塔"
    refs = (code_referenced_bosses() if code_references is None
            else code_references)
    if refs.get("degraded"):
        return (f"identity-locked 判据扫描降级，拒绝改名/异地搬运:"
                f"{','.join(codes)}")
    hard = (frozenset(map(str, refs.get("hard") or ()))
            | frozenset(map(str, refs.get("standard_identity_references") or ())))
    hits = sorted(set(codes) & hard)
    if not hits:
        return None
    return (f"identity-locked boss {','.join(hits)} 被外部实体按代号引用"
            "(damage_share/enemy_watch partner/BossAlive)，master id 必须保持不变")


def identity_clone_locked_boss_reason(
        bosses, *, code_references: dict | None = None) -> str | None:
    """Return why an in-place boss rename cannot be closed safely.

    ``general_enemy_watch`` partner lookups are additive: every watcher can
    keep its official partner branch and receive an equivalent branch keyed by
    the clone id.  ``clone_enemy_watch_partner_aliases`` realizes that closure.
    Funnel ``damage_share`` and state ``GeneralBossAlive`` are not additive at
    the boss row boundary, so those sources remain locked.  Older/synthetic
    callers that provide only the legacy combined ``hard`` set fail closed.
    """
    codes = sorted({str(code) for code in bosses if str(code)})
    if not codes:
        return None
    if "shark_score_event" in codes:
        return "shark_score_event 是不可击杀的计分活动族，不能用于击杀通关塔"
    refs = (code_referenced_bosses() if code_references is None
            else code_references)
    if refs.get("degraded"):
        return (f"identity-locked 判据扫描降级，拒绝改名克隆:"
                f"{','.join(codes)}")
    if not all(key in refs for key in (
            "damage_share", "enemy_watch_partner", "boss_alive")):
        # A legacy injected snapshot cannot prove which hard source is the
        # aliasable watch-partner case.  Treat the whole set as uncloneable.
        return identity_locked_boss_reason(
            codes, code_references=refs)
    locked = (set(map(str, refs.get("damage_share") or ()))
              | set(map(str, refs.get("boss_alive") or ()))
              | set(map(str, refs.get("standard_identity_references") or ())))
    hits = sorted(set(codes) & locked)
    if not hits:
        return None
    kinds = []
    if set(hits) & set(map(str, refs.get("damage_share") or ())):
        kinds.append("damage_share")
    if set(hits) & set(map(str, refs.get("boss_alive") or ())):
        kinds.append("BossAlive")
    if set(hits) & set(map(str, refs.get("standard_identity_references") or ())):
        kinds.append("Standard ESDL")
    return (f"identity-locked boss {','.join(hits)} 存在不可局部闭合的 "
            f"{'/'.join(kinds)} 代号引用，拒绝改名克隆")


def clone_enemy_watch_partner_aliases(
        enemy_watch: dict, source_code: str, clone_code: str) -> int:
    """Add clone-id aliases for every GeneralBoss partner branch.

    Shape: ``[selfKind][selfCode][selfRoutine][partnerKind=1]`` then a map
    keyed by partner boss id.  The nested partner routine stays unchanged
    because a cloned GeneralBoss deliberately retains its official routine id.
    All conflicts are checked before mutation, so a failure cannot leave a
    partially aliased table.
    """
    if not isinstance(enemy_watch, dict):
        raise ValueError("general_enemy_watch is not a map")
    source = str(source_code)
    target = str(clone_code)
    if not source or not target or source == target:
        raise ValueError(f"enemy_watch partner alias ids invalid:{source!r}->{target!r}")
    parents: list[dict] = []
    for self_kind in enemy_watch.values():
        if not isinstance(self_kind, dict):
            continue
        for self_node in self_kind.values():
            if not isinstance(self_node, dict):
                continue
            for routine_node in self_node.values():
                if not isinstance(routine_node, dict):
                    continue
                partner_map = routine_node.get("1")
                if not isinstance(partner_map, dict) or source not in partner_map:
                    continue
                if target in partner_map:
                    raise ValueError(
                        f"general_enemy_watch partner alias conflict:{target}")
                parents.append(partner_map)
    for partner_map in parents:
        partner_map[target] = copy.deepcopy(partner_map[source])
    return len(parents)


def enemy_watch_partner_reference_count(
        enemy_watch: dict, boss_code: str) -> int:
    """Count exact partner-key occurrences for one GeneralBoss id."""
    if not isinstance(enemy_watch, dict):
        return 0
    target = str(boss_code)
    count = 0
    for self_kind in enemy_watch.values():
        if not isinstance(self_kind, dict):
            continue
        for self_node in self_kind.values():
            if not isinstance(self_node, dict):
                continue
            for routine_node in self_node.values():
                partner_map = (routine_node.get("1")
                               if isinstance(routine_node, dict) else None)
                if isinstance(partner_map, dict) and target in partner_map:
                    count += 1
    return count


def enemy_watch_partner_alias_error(
        enemy_watch: dict, source_code: str, clone_code: str) -> str | None:
    """Verify every source partner branch has one byte-equivalent clone key."""
    if not isinstance(enemy_watch, dict):
        return "general_enemy_watch is not a map"
    source = str(source_code)
    target = str(clone_code)
    found = 0
    for self_kind in enemy_watch.values():
        if not isinstance(self_kind, dict):
            continue
        for self_node in self_kind.values():
            if not isinstance(self_node, dict):
                continue
            for routine_node in self_node.values():
                partner_map = (routine_node.get("1")
                               if isinstance(routine_node, dict) else None)
                if not isinstance(partner_map, dict) or source not in partner_map:
                    continue
                found += 1
                if target not in partner_map:
                    return f"partner alias missing:{source}->{target}"
                if partner_map[target] != partner_map[source]:
                    return f"partner alias subtree drift:{source}->{target}"
    if found == 0:
        return f"partner source missing:{source}"
    return None


def purge_enemy_watch_partner_aliases(
        enemy_watch: dict | None, prefix: str = f"{PRIVATE_PREFIX}boss") -> int:
    """Remove stale generated partner keys nested below official watchers."""
    if not isinstance(enemy_watch, dict):
        return 0
    removed = 0
    for self_kind in enemy_watch.values():
        if not isinstance(self_kind, dict):
            continue
        for self_node in self_kind.values():
            if not isinstance(self_node, dict):
                continue
            for routine_node in self_node.values():
                partner_map = (routine_node.get("1")
                               if isinstance(routine_node, dict) else None)
                if not isinstance(partner_map, dict):
                    continue
                stale = [key for key in partner_map
                         if str(key).startswith(str(prefix))]
                for key in stale:
                    partner_map.pop(key, None)
                removed += len(stale)
    return removed


def identity_locked_mix_reason(
        bosses, source_field: str, target_field: str, *,
        code_references: dict | None = None) -> str | None:
    """Reject relocating an identity-locked boss away from its native field."""
    if str(source_field) == str(target_field):
        return None
    why = identity_locked_boss_reason(
        bosses, code_references=code_references)
    if why is None:
        return None
    return (f"{why}; 原生 field={source_field}，异地 terrain={target_field}"
            " 不允许拼接")


def caster_carrier_block(field_id: str, bosses: list[str],
                         fd_t: dict, zone_t: dict,
                         phase_set: frozenset[str] | None = None,
                         gb_t: dict | None = None,
                         refs: dict | None = None) -> str | None:
    """「深渊法阵」载体门禁:返回拒绝理由(None = 可以当载体)。

    法阵的施法载体 = 克隆该轮首只 general boss 并给它追加官方场程序
    (make_caster_boss)。三种情况必须拒发:
      ① 该层 zone 有 **多个 boss 实体** —— 只换得动一只,余下的仍指向原代号,
         成对 boss 从此各打各的;
      ② 该层 boss 属于官方**成对/分阶段族**(phase_linked_bosses)—— 即便这层
         只摆了一只,它的阶段转场仍按代号找同伴,克隆即断链;
      ③ 该层 boss **被外部实体按代号引用且补不回来**(damage_share /
         GeneralBossAlive)—— ①②只认 zone 里
         摆得出来的联动,这类"随从按字符串认爹"的引用整个漏在缝里。2026-08-03 玩家实锤:
         shark(背鳍三兄弟)与 haniwa_great_wind(旋风巨土俑)"血量下不去",
         正是它们的随从(三条鳍 / 四个炮台)靠 damage_share 把伤害转给本体,
         克隆改名后转账链断掉、静默降级 ⇒ 打随从等于白打。
    三条都是数据判据,不认名字(索拉斯/女王/机工神兵一视同仁)。

    refs = code_referenced_bosses(...) 的结果。调用方应当**只算一次**再逐层传进来
    (它要遍历 general_boss_state 4.4MB,每层重算会白烧十几秒)。省略则内部自己算。
    refs["degraded"] 为真时一律拒发 —— 引用名单不完整,放行就是赌命。
    """
    sequential_ex = False
    frow = fd_t.get(field_id)
    if isinstance(frow, (str, bytes, bytearray)):
        fc = cells(frow)
        if len(fc) > 2:
            slots = zone_boss_slots(zone_t.get(fc[2]))
            sequential_ex = (BUILD_MODE == "ex" and field_id.startswith("mod_abyss_ex_final")
                             and len(slots) == 2 and len(set(bosses)) == 2
                             and isinstance(zone_t.get(fc[2]), dict)
                             and set(zone_t[fc[2]]) == {"0"}
                             and cells(zone_t[fc[2]]["0"])[22] == "1")
            if len(slots) > 1 and not sequential_ex:
                return f"zone 有 {len(slots)} 个 boss 实体(法阵只换得动一只)"
    linked = phase_set if phase_set is not None else phase_linked_bosses()
    hit = {b for b in bosses if b in linked}     # bosses 可能含单人/多人同码重复
    if sequential_ex and all(str(b).startswith("mod_fb_") for b in bosses):
        # These private actors are flagged by the five-boss donor itself. Both
        # actors are cloned here; the independent code-reference gate remains.
        hit = set()
    if hit:
        return f"{','.join(sorted(hit))} 属官方成对/分阶段族"
    if refs is None:
        refs = code_referenced_bosses(gb_t)
    if refs.get("degraded"):
        return "代号引用名单扫描降级(见上方 WARN),本轮一律不发法阵"
    clone_block = identity_clone_locked_boss_reason(
        bosses, code_references=refs)
    if clone_block:
        return clone_block
    return None


def live_forged_dsl_logicals(gb: dict | None = None,
                             sb: dict | None = None) -> list[str]:
    """现网 general/standard 克隆引用的全部锻造 DSL 逻辑路径。

    锻造变体(wf_field_catalog.forge)只存在于 store,不发布客户端就会
    「因为有不足的数据 返回标题画面进行下载」死循环(2026-07-26 关15 实锤)。
    发布 rush 内容时必须把这些文件一并上链。
    """
    if gb is None:
        gb = q.load_table(GENERAL_BOSS)
    if sb is None:
        sb = q.load_table(STANDARD_BOSS)
    out = set()
    for code, node in gb.items():
        if not str(code).startswith("mod_rogue"):
            continue
        leaf = node[next(iter(node))] if isinstance(node, dict) else node
        s = leaf if isinstance(leaf, str) else leaf.decode("utf-8")
        for m in re.finditer(r"battle/action/enemy/action/mod_rogue/[^,\"\n]+", s):
            out.add(m.group(0) + ".action.dsl.amf3.deflate")
    for code, node in sb.items():
        if not str(code).startswith(f"{PRIVATE_PREFIX}standard") or not isinstance(node, dict):
            continue
        for leaf in node.values():
            if isinstance(leaf, dict):
                continue
            row = cells(leaf)
            if len(row) < 2 or not row[1].strip():
                continue
            base = row[1].strip()
            if not base.startswith("battle/enemy/boss/mod_rogue/"):
                continue
            out.add(base if base.endswith(".esdl.amf3.deflate")
                    else base + ".esdl.amf3.deflate")
    return sorted(out)


def store_chain_ctx(fresh: bool = False):
    """store 现状的链检查上下文 (fd, zone, enemies, zakos, lv_ceil, lv_floor)。

    fresh=False 用 _tbl 进程内缓存(GUI 候选池等只读场景);fresh=True 每次重读
    (写入流程/长驻进程里 store 可能已被其它步骤改过)。lv_ceil=standard_boss、
    lv_floor=general_boss_variable、lv_gb=general_boss,配合
    check_field_chain(level=) 查等级覆盖(v4 两步规则)。"""
    load = q.load_table if fresh else _tbl
    fd = load(FIELD_DATA_T)
    zone = load(ZONE_T)
    gz = load(GENERAL_ZAKO)
    sb = load(STANDARD_BOSS)
    gb = load(GENERAL_BOSS)
    gv = load("master/battle/boss/general_boss_variable.orderedmap")
    enemies = set(gb) | set(sb) | set(gz)
    return fd, zone, enemies, set(gz), sb, gv, gb


def verify_cdn_chain(logicals: list[str],
                     cdn_diff: "Path | None" = None) -> list[tuple[str, str]]:
    """发布完整性自检:每个逻辑路径的 store 现字节须等于 CDN diff 链最新版包内字节。

    C8601「key=mod_rogue_f9 不存在」事故根因:表写进了 store 却没进发布清单,
    quest 引用链在客户端侧断裂。发布成功后调用;返回 [(逻辑路径, 问题)] 清单
    (空 = 通过)。同一版本边可能拆多包(序号 N),同版本任一包字节一致即通过。
    """
    if cdn_diff is None:
        import wf_publish as pub
        # The isolated Mode15 project publishes custom resources through
        # assets/asset-patch/active + manifest.json.  Verify that live chain
        # instead of the read-only official .cdn baseline.
        active_patch = getattr(pub, "ACTIVE_PATCH", None)
        cdn_diff = active_patch if active_patch is not None else pub.CDN_DIFF
    cdn_diff = Path(cdn_diff)
    ver_re = re.compile(r"pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-\d+-")
    wanted = {f"production/upload/{q.hashed_rel(logical)}": logical
              for logical in logicals}
    best: dict[str, tuple[tuple[int, ...], list[Path]]] = {}
    for zp in sorted(cdn_diff.glob("*.zip")):
        m = ver_re.match(zp.name)
        if not m:
            continue
        ver = tuple(int(x) for x in m.group(2).split("."))
        try:
            with zipfile.ZipFile(zp) as zf:
                names = set(zf.namelist())
        except Exception:
            continue        # 坏包按不含处理:只会把问题报出来,不会漏报
        for member in wanted:
            if member not in names:
                continue
            cur = best.get(member)
            if cur is None or ver > cur[0]:
                best[member] = (ver, [zp])
            elif ver == cur[0]:
                cur[1].append(zp)
    problems: list[tuple[str, str]] = []
    for member, logical in wanted.items():
        sp = q.store_path(logical)
        if not sp.is_file():
            problems.append((logical, f"store 文件缺失({sp})"))
            continue
        want_hash = hashlib.sha256(sp.read_bytes()).hexdigest()
        hit = best.get(member)
        if hit is None:
            problems.append((logical, "不在 CDN diff 链任何包里(未发布)"))
            continue
        ver, zips = hit
        ok = False
        for zp in zips:
            try:
                with zipfile.ZipFile(zp) as zf:
                    if hashlib.sha256(zf.read(member)).hexdigest() == want_hash:
                        ok = True
                        break
            except Exception:
                continue
        if not ok:
            problems.append((
                logical,
                f"CDN 链最新版 {'.'.join(map(str, ver))}"
                f"({zips[0].name}) 字节与 store 不一致(链上是旧内容)"))
    return problems


# ⚠ 两张表的元素枚举**不一样**(2026-07-29 测绘实锤,以前一直按同一套换算):
#   general_boss c0(boss 固定元素 kind):0=Inherit 1火 2水 3雷 4风 5光 6暗
#   quest c69(battle_recommended_element):**0风 1火 2水 3雷 4暗 5光**
# 后者由 advent 六属性精灵兽/六属性废龙两族交叉验证(火1/水2/雷3/风0/光5/暗4),
# 并与 ranking 五元素试炼、carnival 六色土俑、solo_time_attack 六色试炼、
# expert_single(不死王=风0/废墟魔像=火1/寄居蟹=水2)四张表全部自洽。
# c69 写的是 quest 枚举,所以固定元素 boss 必须按下表换算,不能沿用 kind-1。
GB_KIND_TO_QUEST_ELEM = {1: 1, 2: 2, 3: 3, 4: 0, 5: 5, 6: 4}
# quest 枚举 → 中文(下标即 c69 取值)
QUEST_ELEM_CN = ["风", "火", "水", "雷", "暗", "光"]


def boss_element_map() -> dict[str, int | None]:
    """boss code → 固定元素(**quest c69 枚举**)或 None(=Inherit,元素随 c69)。

    只读 general_boss(c0=元素kind);standard_boss 表无元素列 = 恒继承 quest 元素。
    返回值直接可写 c69 —— 换算表见 GB_KIND_TO_QUEST_ELEM。
    """
    out: dict[str, int | None] = {}
    table = q.load_table(GENERAL_BOSS)
    for code, node in table.items():
        leaf = node
        if isinstance(node, dict):
            leaf = node[next(iter(node))]
        s = leaf.decode("utf-8") if isinstance(leaf, bytes) else leaf
        kind = cb._cols(s.split("\n")[0])[0]
        out[code] = GB_KIND_TO_QUEST_ELEM.get(int(kind)) if kind.isdigit() else None
    return out


# ---- 跨副本楼层来源(v7,2026-07-19 用户设计:随 rounds 自适应)----
# 固定锚:第1轮(rounds≥8 时含第2轮)=小怪房热身;**末轮恒=主线终 boss 终始之龙**,
# 末轮-1=无幻之宴守门(rounds≥5)。比例锚(按 rounds 百分比落位,撞位向后找空,
# 塞不下放弃):领主战20% / 机兵40% / 降临讨伐55% / 女帝歼灭者70%。其余轮=连战塔池。
# 简单来源叠难度补偿(小怪房/领主战/浅层塔),见 SRC_BOOST / tower_area_boost。
import wf_boss as wb              # noqa: E402


_TBL_CACHE: dict[str, dict] = {}


def _tbl(logical: str) -> dict:
    if logical not in _TBL_CACHE:
        _TBL_CACHE[logical] = q.load_table(logical)
    return _TBL_CACHE[logical]


def boss_ref_validation_tables(*, standard_boss: dict | None = None,
                               general_boss: dict | None = None,
                               general_boss_variable: dict | None = None,
                               special_tables: dict | None = None,
                               funnel_ok=None) -> dict:
    """Build the sole BossKind validation bundle consumed by ``wf_rogue_bundle``.

    The model module must not import this builder.  We therefore inject the
    already-proven level/funnel semantics as callbacks and return the *selected
    numeric tier*, not a boolean.  Kinds 0/1/8 fail closed without this bundle.
    Explicit empty dicts are honored for isolated tests; ``None`` loads the
    configured store read-only.
    """
    sb = standard_boss if standard_boss is not None else _tbl(STANDARD_BOSS)
    gb = general_boss if general_boss is not None else _tbl(GENERAL_BOSS)
    gv_logical = "master/battle/boss/general_boss_variable.orderedmap"
    gv = (general_boss_variable if general_boss_variable is not None
          else _tbl(gv_logical))
    tables: dict = {"standard_boss": sb, "general_boss": gb}
    if special_tables is None:
        for logical in SPECIAL_BOSS_TABLES:
            name = Path(logical).name.removesuffix(".orderedmap")
            tables[name] = _tbl(logical)
    else:
        for name, table in special_tables.items():
            short = Path(str(name)).name.removesuffix(".orderedmap")
            tables[short] = table

    effective_funnel_ok = funnel_ok if funnel_ok is not None else boss_funnel_ok

    def selected_level(ref: rbb.BossRef, enemy_level: int, _tables: dict):
        if ref.kind == 0:
            return select_surjective_level(sb.get(ref.code), enemy_level)
        if ref.kind in (1, 8):
            if not boss_level_ok(
                    ref.code, enemy_level, {}, gv, gb,
                    funnel_ok_fn=effective_funnel_ok,
                    special_levels={}):
                return None
            # GeneralEnemy selects the greatest variable tier <= c95 first,
            # then GeneralBossValues.getSurjectivity selects the first row
            # >= that variable tier.  Querying general_boss directly with c95
            # rejects proven gv[80]/gb[80] content at lv90/100 and made the
            # legacy gate disagree with the final exact-kind gate.
            variable = gv.get(ref.code)
            variable_levels = (sorted(
                int(key) for key in variable if str(key).isdigit())
                if isinstance(variable, dict) else [])
            usable = [tier for tier in variable_levels
                      if tier <= int(enemy_level)]
            lookup_level = max(usable) if usable else int(enemy_level)
            return select_surjective_level(gb.get(ref.code), lookup_level)
        return None

    tables["__level_validator__"] = selected_level
    tables["__funnel_ok__"] = effective_funnel_ok
    return tables


def validate_spawned_ref(
        source_kind: str, code: str, enemy_level: int, *,
        validation_tables: dict,
        general_zako: dict,
        general_funnel: dict,
        standard_funnel: dict,
        ) -> rbb.GateResult:
    """Validate an action/state dependency against its exact client source.

    The three minion tables and GeneralBoss use getSurjectivity, so a numeric
    tier at or above the battle level must exist. SpawnAlterEgo constructs a
    GeneralBossAlterEgoSource and GeneralBossAlive names a GeneralBoss; a
    same-code StandardBoss or Zako row must never satisfy either dependency.
    Same-layer membership for GeneralBossAlive is checked by the closure walker,
    which owns the necessary layer context.
    """

    try:
        level = int(enemy_level)
    except (TypeError, ValueError):
        return rbb.GateResult(False, "LEVEL",
                              detail=f"invalid spawned-ref level:{enemy_level!r}")

    table_by_kind = {
        "Funnel": (general_funnel, "general_funnel"),
        "StandardFunnel": (standard_funnel, "standard_funnel"),
        "Zako": (general_zako, "general_zako"),
    }
    if source_kind in table_by_kind:
        table, label = table_by_kind[source_kind]
        node = table.get(code) if isinstance(table, dict) else None
        selected = select_surjective_level(node, level)
        if selected is None:
            reason = "FUNNEL_LEVEL" if source_kind != "Zako" else "LEVEL"
            return rbb.GateResult(
                False, reason, source_table=label,
                detail=f"{label} has no tier >= {level}:{code}")
        return rbb.GateResult(
            True, selected_level=selected, source_table=label)

    if source_kind in ("AlterEgo", "GeneralBoss"):
        return rbb.validate_boss_ref(
            rbb.BossRef(1, code), level, validation_tables)
    return rbb.GateResult(
        False, "REFERENCE",
        detail=f"unknown spawned reference kind:{source_kind}")
