# Source section of rogue_build; loaded in its shared module namespace.
def boss_target_hp(r: int, n: int) -> float:
    """返回默认 Hell 第 ``r`` 个 Boss 关的诅咒前整关总 HP。

    第 1 战是无 Boss 热身，不属于这条曲线。只有一个 Boss 关（``n == 2``）
    时优先守住终关 150 亿锚；常规 30 层则严格命中第 2 战 30 亿与第 30 战
    150 亿，中间 27 个点线性插值。
    """
    if BUILD_MODE in {"normal", "ex"}:
        if n != 30:
            raise ValueError("普通深渊拆分版固定为 30 关")
        return float(abyss_modes.base_hp(BUILD_MODE, r))
    if n < 2 or not 2 <= r <= n:
        raise ValueError(f"Boss HP 曲线轮次越界:r={r},n={n}")
    if n == 2:
        return HELL_BOSS_HP_LAST
    progress = (r - 2) / (n - 2)
    return HELL_BOSS_HP_FIRST + (
        HELL_BOSS_HP_LAST - HELL_BOSS_HP_FIRST) * progress


def target_dps(r: int, n: int, *, ramp: bool = False) -> float:
    """第 r 关内部目标 DPS；默认由线性 Boss HP 曲线按 900 秒换算。"""
    if n < 2 or not 1 <= r <= n:
        raise ValueError(f"DPS 曲线轮次越界:r={r},n={n}")
    if ramp:
        progress = (r - 1) / (n - 1)
        return RAMP_TARGET_DPS_FIRST * (
            (RAMP_TARGET_DPS_LAST / RAMP_TARGET_DPS_FIRST) ** progress)
    if r < first_boss_round():
        return WARMUP_TARGET_DPS
    return boss_target_hp(r, n) / TARGET_BASE_DURATION_S


def configured_target_dps(r: int, n: int, hp_base: float, hp_growth: float,
                          stage_multiplier: float = 1.0, *,
                          ramp: bool = False) -> float:
    """把旧 HP 难度端点映射到选定的 linear-HP/legacy-ramp profile。

    选中的 profile 是 hell 默认锚；`--difficulty` / `--hp-base` /
    `--hp-growth` 仍通过“当前旧曲线 ÷ hell 旧曲线”等比缩放它。
    默认线性 HP profile 不再吃工坊阶段乘区：阶段 tier 只决定诅咒菜单，
    否则当前全 Hell 布局里的旧 ×1.15 会把 30亿→150亿整体改成
    34.5亿→172.5亿。该兼容乘区只保留给显式 ``--ramp``；血量/时限诅咒
    仍在随后的 realized 层生效，不能被这个函数抵消。

    来源 `bh` 与旧 HP normalize 不再二次乘入：它们原本是在原生
    HP 不可见时的代理，现在已由 general/standard 真 HP 反解取代。
    """
    if n < 2 or not 1 <= r <= n:
        raise ValueError(f"DPS 曲线轮次越界:r={r},n={n}")
    vals = (float(hp_base), float(hp_growth), float(stage_multiplier))
    if not all(math.isfinite(v) and v > 0 for v in vals):
        raise ValueError(
            f"HP 目标缩放必须为有限正数:base={hp_base},"
            f"growth={hp_growth},stage={stage_multiplier}")
    hell_base, hell_end = DIFF_PRESETS["hell"][:2]
    hell_growth = (hell_end / hell_base) ** (1 / (n - 1))
    configured = vals[0] * (vals[1] ** (r - 1))
    canonical = hell_base * (hell_growth ** (r - 1))
    stage_scale = vals[2] if ramp else 1.0
    return target_dps(r, n, ramp=ramp) * configured / canonical * stage_scale


def deep_hp_anchor_field(r: int, n: int) -> str | None:
    """返回 30 层塔 r26~30 的安全硬锚；r25 回到常规可击杀候选池。"""
    if n != 30 or BUILD_MODE == "ex":
        return None
    first = 26
    return DEEP_HP_ANCHOR_FIELDS_30[r - first] if first <= r <= 30 else None


def mid_hp_anchor_field(r: int, n: int) -> str | None:
    """返回 30 层成品塔 r16~24 的绝对 HP / 单领域载体锚。"""
    if n != 30 or BUILD_MODE == "ex":
        return None
    first = 16
    return MID_HP_ANCHOR_FIELDS_30[r - first] if first <= r <= 24 else None


def hp_correction_limits(r: int, n: int) -> tuple[float, float]:
    """最终 quest c86 窗口；中段放宽，深层重新收紧。"""
    if not 1 <= r <= n:
        raise ValueError(f"HP 修正窗口轮次越界:r={r},n={n}")
    if n == 30 and 16 <= r <= 24:
        return (0.1, 30.0)
    return (0.1, 10.0)


def solve_hp_correction(dps: float, duration_s: float, native_hp: float) -> float:
    """由目标 DPS、实战时长和 c86 前原生 HP 反解 quest HP 修正。"""
    vals = (float(dps), float(duration_s), float(native_hp))
    if not all(math.isfinite(v) and v > 0 for v in vals):
        raise ValueError(f"HP 修正输入必须为有限正数:dps={dps},time={duration_s},hp={native_hp}")
    value = vals[0] * vals[1] / vals[2]
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"HP 修正解非法:{value}")
    return value


def hp_curve_errors(records: list[dict], n: int,
                    last_band: tuple[float, float] | None = None, *,
                    ramp: bool = False) -> list[str]:
    """linear-HP/legacy-ramp 两套互斥 profile 门禁；返回空列表即通过。

    `verified` 只影响报告覆盖率，不允许把不可验层静默当成 0；门禁仍读取它的
    显式估算 DPS。`target_exempt` 表示血量可读、但按保留原 Boss 的策略无法归一，
    因此不冒充命中 linear-HP/legacy-ramp 目标带，也不阻断整座塔的非破坏性构建。
    """
    errors: list[str] = []
    if last_band is None:
        last_band = (RAMP_TARGET_DPS_LAST_BAND
                     if ramp else TARGET_DPS_LAST_BAND)
    all_by_round = {
        int(rec["r"]): rec for rec in records
        if rec.get("baseline_dps") is not None
    }
    rows = sorted((rec for rec in records
                   if rec.get("baseline_dps") is not None
                   and not rec.get("target_exempt")),
                  key=lambda rec: int(rec["r"]))
    if not rows:
        return ["没有可审计的 DPS 记录"]
    if not ramp:
        by_round = {int(rec["r"]): rec for rec in rows}
        warmup = by_round.get(1) if BUILD_MODE != "ex" else None
        if warmup is not None and not warmup.get("warmup"):
            errors.append("第1关未标记为唯一小怪热身豁免层")
        missing = [r for r in range(first_boss_round(), n + 1) if r not in all_by_round]
        if missing:
            errors.append("缺少 boss 层 DPS 记录:" + ",".join(map(str, missing)))
        last_record = all_by_round.get(n) or {}
        try:
            last_target = float(last_record["target_dps"])
        except (KeyError, TypeError, ValueError):
            last_target = target_dps(n, n)
        if not math.isfinite(last_target) or last_target <= 0:
            errors.append(f"第{n}关目标 DPS 非法:{last_target!r}")
            return errors
        lo_ratio = float(last_band[0]) / last_target
        hi_ratio = float(last_band[1]) / last_target
        for r in range(first_boss_round(), n + 1):
            rec = by_round.get(r)
            if rec is None:
                continue
            dps = float(rec["baseline_dps"])
            try:
                expected = float(rec["target_dps"])
            except (KeyError, TypeError, ValueError):
                errors.append(f"第{r}关缺目标 DPS，无法验收基础 HP 梯度")
                continue
            lo, hi = expected * lo_ratio, expected * hi_ratio
            if not lo <= dps <= hi:
                errors.append(
                    f"第{r}关基线 DPS {dps:.0f} 未进本层梯度目标带 "
                    f"{lo:.0f}~{hi:.0f}(target={expected:.0f})")
        return errors
    for prev, cur in zip(rows, rows[1:]):
        if (float(cur["baseline_dps"]) + 1e-9
                < float(prev["baseline_dps"]) * (1 - MAX_DPS_DOWN_JITTER)):
            errors.append(
                f"第{cur['r']}关基线 DPS 下跌超过15%:"
                f"{prev['baseline_dps']:.0f}→{cur['baseline_dps']:.0f}")
    first = all_by_round.get(1)
    last = all_by_round.get(n)
    if first is None or last is None:
        errors.append(f"首尾记录不完整:round1={first is not None},round{n}={last is not None}")
        return errors
    if last.get("target_exempt"):
        return errors
    last_dps = float(last["baseline_dps"])
    if not float(last_band[0]) <= last_dps <= float(last_band[1]):
        errors.append(f"第{n}关 DPS {last_dps:.0f} 未进末层目标带")
    ratio = last_dps / float(first["baseline_dps"])
    if not 35.0 <= ratio <= 50.0:
        errors.append(f"首尾 DPS 比 {ratio:.2f}× 不在 35~50×")
    return errors


def hp_short_time_errors(records: list[dict]) -> list[str]:
    """任意层若短于 300 秒且实战需求超过 2000 万/s，直接拒绝。"""
    errors: list[str] = []
    for rec in records:
        try:
            duration = float(rec["duration_s"])
            dps = float(rec["realized_dps"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"第{rec.get('r', '?')}战短时限审计字段不完整")
            continue
        if duration < 300.0 and dps > 20_000_000.0:
            errors.append(
                f"第{rec['r']}战短时限与高血量同时命中:"
                f"{duration:.0f}s/{dps:.0f} DPS")
    return errors


def hp_correction_errors(records: list[dict], n: int) -> list[str]:
    """最终活动实体类 HP 修正按主通道验收；只报错，不做静默 clamp。"""
    errors: list[str] = []
    for rec in records:
        try:
            r = int(rec["r"])
            c86 = float(rec["c86"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"第{rec.get('r', '?')}战 c86 审计字段不完整")
            continue
        family = str(rec.get("family") or "")
        if rec.get("target_exempt") or family == "unscaled":
            continue
        if family == "no-boss" and rec.get("warmup"):
            continue
        if family in {"general", "mixed", "orochi", "orochi_ex",
                      *SINGLE_BAR_SPECIAL_SPECS, *SPHERE_SPECS}:
            if not math.isclose(c86, 1.0, rel_tol=0.0, abs_tol=1e-12):
                errors.append(f"第{r}战 {family} 最终 c86={c86:g}（必须恒为 1）")
            continue
        if family == "standard" or family.startswith("identity-locked"):
            lo, hi = STANDARD_C86_LIMITS
            if not lo <= c86 <= hi:
                errors.append(
                    f"第{r}战 {family} 最终 c86={c86:g} "
                    f"超出微调窗口 {lo:g}~{hi:g}")
            continue
        if family == "unknown":
            # 非破坏性血量带:该层的血量按不动(读不出 HP 通道),走 86e27250 之前
            # 的老路——原生血量 × 曲线 c86,不参与 c86 主通道审计。
            # 这些层已经在 [WARN] 里逐条列名,并计入 [真HP门禁] 的「无boss估算」。
            continue
        errors.append(f"第{r}战 HP 族/通道不可审计:{family or '(missing)'}")
    return errors


def quest_hp_multiplier_plan(*, baseline: float, final: float,
                              has_boss: bool) -> dict:
    """Build independent c86/c87/c88 HP multipliers for one floor."""

    try:
        baseline_value = float(baseline)
        final_value = float(final)
    except (TypeError, ValueError) as exc:
        raise ValueError("任务级 HP 三分类计划含非数字") from exc
    if not all(math.isfinite(value) and value > 0
               for value in (baseline_value, final_value)):
        raise ValueError(
            f"任务级 HP 三分类计划必须为有限正数:{baseline},{final}")
    boss_floor = bool(has_boss)
    return {
        "columns": {"enemy": "c86", "device_or_summon": "c87", "boss": "c88"},
        "has_boss": boss_floor,
        "baseline": {
            "enemy": 1.0 if boss_floor else baseline_value,
            "device_or_summon": 1.0,
            "boss": baseline_value if boss_floor else 1.0,
        },
        "final": {
            "enemy": 1.0 if boss_floor else final_value,
            "device_or_summon": 1.0,
            "boss": final_value if boss_floor else 1.0,
        },
        "active_target_class": "boss" if boss_floor else "enemy",
        "independent_verified": True,
        "mechanism_budget_separate": True,
    }


def quest_hp_multiplier_errors(records: list[dict]) -> list[str]:
    """Reject coupled or mislabeled quest-level c86/c87/c88 plans."""

    errors: list[str] = []
    for rec in records:
        label = f"第{rec.get('r', '?')}战"
        plan = rec.get("quest_hp_multipliers")
        if not isinstance(plan, dict):
            errors.append(f"{label} 缺 c86/c87/c88 独立 HP 计划")
            continue
        try:
            has_boss = bool(plan["has_boss"])
            active = "boss" if has_boss else "enemy"
            inactive = "enemy" if has_boss else "boss"
            baseline = {key: float(value)
                        for key, value in plan["baseline"].items()}
            final = {key: float(value)
                     for key, value in plan["final"].items()}
            expected_baseline = float(rec["baseline_c86"])
            expected_final = float(rec["c86"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{label} c86/c87/c88 独立 HP 计划字段非法")
            continue
        if set(baseline) != {"enemy", "device_or_summon", "boss"} \
                or set(final) != {"enemy", "device_or_summon", "boss"}:
            errors.append(f"{label} c86/c87/c88 独立 HP 计划分类不完整")
            continue
        if (not math.isclose(baseline[active], expected_baseline,
                             rel_tol=0.0, abs_tol=1e-12)
                or not math.isclose(final[active], expected_final,
                                    rel_tol=0.0, abs_tol=1e-12)):
            errors.append(f"{label} 活动实体类 HP 倍率未命中审计值")
        for stage, values in (("baseline", baseline), ("final", final)):
            if (not math.isclose(values[inactive], 1.0, rel_tol=0.0, abs_tol=1e-12)
                    or not math.isclose(values["device_or_summon"], 1.0,
                                        rel_tol=0.0, abs_tol=1e-12)):
                errors.append(f"{label} {stage} HP 倍率错误捆绑三类实体")
        if (plan.get("independent_verified") is not True
                or plan.get("mechanism_budget_separate") is not True):
            errors.append(f"{label} c86/c87/c88 独立/机制预算证据未通过")
    return errors


def native_hp_coverage_errors(floor_records: list[dict]) -> list[str]:
    """A 路径覆盖门禁：有 boss 的层不得退成无证据代理。

    纯小怪热身没有 boss 血条，不在用户给定的 29 层 boss 公式内；它是唯一允许
    `verified=false` 的结构性例外。新 boss 类型一旦读不到，必须显式扩解析器或拒绝。
    """
    errors = []
    for rec in floor_records:
        bosses = list((rec.get("pick") or {}).get("bosses") or [])
        native = rec.get("native_hp") or {}
        if bosses and not native.get("verified"):
            errors.append(
                f"第{rec.get('r')}战 boss HP 无绝对证据:"
                f"{','.join(map(str, bosses))} ({native.get('reason') or 'unknown'})")
    return errors


def difficulty_curve(diff: str, n: int) -> tuple[float, float, float, float]:
    """难度预设 → (hp_base, hp_growth, atk_base, atk_growth),端点式按层数求增长率。"""
    hp0, hp1, atk0, atk1, _tier = DIFF_PRESETS[diff]
    steps = max(1, n - 1)
    return (hp0, (hp1 / hp0) ** (1 / steps), atk0, (atk1 / atk0) ** (1 / steps))


def tier_for_round(diff: str, r: int, n: int) -> str:
    """难度预设 → 该层诅咒档位。gradient = 按深度四段递进(从简单到难)。"""
    tier = DIFF_PRESETS[diff][4]
    if tier is not None:
        return tier
    d = r / n
    if d <= 0.25:
        return "off"
    if d <= 0.5:
        return "standard"
    if d <= 0.75:
        return "abyss"
    return "hell"


def is_minion_boss(code: str, zako_keys: set[str]) -> bool:
    """杂兵提拔族判定(2026-07-28 用户强度调查):真 boss 从不出现在 general_zako,
    小怪表里有同族前缀的"boss"=杂兵提拔(地鼠/镰鼬/警备机/枪兵…),观感弱。
    规则:过 1/3 进度后只出真 boss。"""
    parts = str(code).split('_')
    for n in range(len(parts), 0, -1):
        if '_'.join(parts[:n]) in zako_keys:
            return True
    return False


def floor_tier(field: str) -> int:
    """楼层强度档 1(最浅)~5(最深),按塔区编号;非塔场地(幽玄域单人本等)=2
    (2026-07-27 用户反馈:默认 3 会让简单 boss 漏进后半程)。

    伪随机排布用:深关只从高档抽,杜绝"后期撞见简单小 boss"。"""
    m = re.match(r"tower_dungeon_+(low_)?area_(\d+)_", field)
    if not m:
        return 2
    if m.group(1):                      # low_area = 入门塔
        return 1
    area = int(m.group(2))
    if area <= 3:
        return 1
    if area <= 6:
        return 2
    if area <= 8:
        return 3
    return 4 if area == 9 else 5


def collapse_grades(entries: list[dict], name_of) -> list[dict]:
    """难度分级去重:同 boss(按显示名集合)只保留最高难度版本。

    分级副本(高级/超级/超级+)在池里是同前缀不同尾号的多个 field
    (multi_normal_1_16_1..4 / empress_wind_1..5),boss 相同强度不同——
    只留最难的一个。

    2026-07-29 起**先比敌等级、再比尾号**:等级列在 quest_level_of 修好之前
    不可信,只能拿尾号当代理;现在等级是权威档位,尾号退为同级时的兜底
    (empress_wind_1..5 这类同为 80 级的靠尾号分先后)。"""
    best: dict[frozenset, tuple[tuple[int, int], dict]] = {}
    order: list[frozenset] = []
    for e in entries:
        key = frozenset(name_of(e["bosses"]))
        m = re.match(r"^(.*?)_(\d+)$", e["field"])
        rank = (int(e["level"]) if str(e.get("level", "")).isdigit() else 0,
                int(m.group(2)) if m else 0)
        cur = best.get(key)
        if cur is None:
            order.append(key)
            best[key] = (rank, e)
        elif rank > cur[0]:
            best[key] = (rank, e)
    return [best[k][1] for k in order]


def boss_family_cooldown_group(bosses) -> str | None:
    """Collapse high-risk related families for adjacent-floor cooldown."""

    codes = tuple(str(code).lower() for code in bosses or ())
    if any("sphere" in code for code in codes):
        return "sphere"
    if any("orochi" in code for code in codes):
        return "orochi"
    return None


def select_special_showcase_families(
        available_families, rng, *, limit: int = 5) -> tuple[str, ...]:
    """Choose diverse dedicated families without forcing every variant."""

    available = set(map(str, available_families or ()))
    grouped = {
        "orochi": [name for name in ("orochi", "orochi_ex")
                    if name in available],
        "sphere": [name for name in SPHERE_SPECS if name in available],
        "conductor": ["conductor"] if "conductor" in available else [],
        "touyakiren_ceo": (["touyakiren_ceo"]
                            if "touyakiren_ceo" in available else []),
        "kraken": ["kraken"] if "kraken" in available else [],
    }
    chosen = [members[rng.randrange(len(members))]
              for members in grouped.values() if members]
    rng.shuffle(chosen)
    return tuple(chosen[:max(0, int(limit))])


FULL_SPECIAL_SHOWCASE_SLOTS = (
    ("orochi", 0.82),
    ("orochi_ex", 0.74),
    ("conductor", 0.66),
    ("touyakiren_ceo", 0.58),
    ("kraken", 0.50),
    ("water_sphere", 0.46),
    ("holy_sphere", 0.42),
    ("wind_sphere", 0.38),
    ("thunder_sphere", 0.34),
    ("fire_sphere", 0.30),
)
DIVERSE_SPECIAL_SHOWCASE_FRACTIONS = (0.30, 0.43, 0.57, 0.70, 0.83)


def special_showcase_slots(
        available_families, rng, *, rounds: int) -> tuple[tuple[str, float], ...]:
    """Plan native-special showcase slots without crowding a 30-floor roll.

    Normal 30-floor towers choose one Orochi variant and one Sphere variant,
    plus the three independent single-bar families.  A 60-floor static canary
    has room for every currently supported family and deliberately restores
    full adapter coverage instead of inheriting the gameplay roster limit.
    """

    available = set(map(str, available_families or ()))
    if int(rounds) >= 60:
        return tuple((family, fraction)
                     for family, fraction in FULL_SPECIAL_SHOWCASE_SLOTS
                     if family in available)
    selected = select_special_showcase_families(available, rng, limit=5)
    return tuple(zip(selected, DIVERSE_SPECIAL_SHOWCASE_FRACTIONS))


def build_schedule(n: int, rng) -> dict[int, str]:
    """楼层计划 v8(任意层数自适应,2~98 层):
    第 1 战恒=小怪房热身(n≥3;n=2 时首战直接进塔层,给奖励测试用);
    第 2 战 20% 概率再来一间小怪房;末战=安全高难终局候选池;
    末战-1=无幻之宴守门(n≥5);比例锚 领主战20%/机兵40%/降临讨伐55%/女帝歼灭者70%
    (撞位向后找空、再向前,塞不下放弃);其余全部=塔池(--mix 时为拼接层)。

    v9(2026-07-29):**领主战多位**。领主战池有 143 个场地(索拉斯双阶段八套、
    八岐大蛇各档都在里面),却只给 1 个位 → 单座塔抽中某个特定 boss ≈5.6%,
    用户「打了这么久没见过」。改成大塔多开位:<15 层 1 个、15-24 层 2 个、
    ≥25 层 3 个(全塔配额去重保证不会重样)。"""
    # Keep the legacy schedule label for layout-plan compatibility; its picker
    # now resolves the safe high-difficulty finale pool instead of pinning dragon.
    sched = {n: "终始之龙"}
    if n >= 3:
        sched[1] = "小怪房"
    if n >= 4:
        # v11(2026-07-29 用户需求):第2战固定"杂鱼 boss"(杂兵提拔族),
        # 替掉原来 20% 概率再来一间小怪房——热身两层的节奏改成 小怪→杂鱼boss。
        sched[2] = "杂鱼boss"
    if n >= 5:
        sched[n - 1] = "无幻之宴"
    if n >= 7:
        # 机工神兵菲诺梅那(steampunk_another 地狱级,双 boss 本体+foom2)
        # 常驻塔腰固定位，不参与随机。
        # 位置=**塔腰**(2026-07-29 用户指定:15层→7、30层→15、50层→25),
        # 不放末尾——末尾已经是 无幻之宴+终局候选 的双守门。
        sched[max(3, n // 2)] = "机工神兵"
    anchors = [("领主战", 0.2), ("世界剧情", 0.3), ("机兵", 0.4),
               ("剧情活动", 0.48), ("降临讨伐", 0.55), ("女帝歼灭者", 0.7)]
    if n >= 17:
        anchors.append(("领主战", 0.62))
    if n >= 24:
        anchors.append(("领主战", 0.85))
    # v10(2026-07-29 全类别普查):6 类高价值来源以前整类抽不到,按塔高逐个开位。
    # 门槛按**容量**排——每个新来源多占一层,开太早会把塔池层挤光
    # (实测 10 层塔在门槛 0.34 时锚位吃满 1..10,一层崩坏域都不剩)。
    # 土俑嘉年华开 **3 个位**(2026-07-29 用户:一座塔最多来 3 个不同的土俑)——
    # 全塔配额去重保证三次抽到的是不同伤害体系的变体,不会重样。
    for label, frac, need in (("战阵之宴", 0.34, 16), ("单人挑战", 0.44, 18),
                              ("主线boss", 0.5, 19), ("极时试炼", 0.58, 20),
                              ("剧情boss", 0.66, 22), ("元素试炼", 0.76, 25),
                              ("土俑嘉年华", 0.28, 26), ("土俑嘉年华", 0.62, 28),
                              ("土俑嘉年华", 0.88, 30)):
        if n >= need:
            anchors.append((label, frac))
    # 锚位预算:塔池(崩坏域)是这个玩法的底色,**至少留 1/5 楼层**给塔层/拼接层。
    # 预算 = 总层数 − 固定位 − 保留位;超出的锚位按 anchors 先后顺序放弃。
    reserve = max(1, round(n * 0.2))
    budget = max(0, n - len(sched) - reserve)
    for label, frac in anchors[:budget]:
        t = max(2, min(n - 2, round(n * frac)))
        slot = next((s for s in list(range(t, n - 1)) + list(range(t - 1, 1, -1))
                     if s not in sched), None)
        if slot is not None:
            sched[slot] = label
    return sched


def reserve_schedule_slot(schedule: dict[int, str], rounds: int, label: str,
                          *, fraction: float = 0.8) -> int | None:
    """Reserve the nearest unused non-terminal round without moving anchors.

    Dedicated native-only boss bundles must keep their official field.  They
    therefore need one explicit schedule slot instead of entering the ordinary
    transplant/donor registry.  Existing fixed/curated slots remain stronger;
    this helper only fills a genuinely unused round and returns ``None`` when
    the tower is too short or full.
    """
    n = int(rounds)
    if n < 4:
        return None
    target = max(2, min(n - 2, round(n * float(fraction))))
    candidates = list(range(target, n - 1)) + list(range(target - 1, 1, -1))
    slot = next((round_no for round_no in candidates
                 if round_no not in schedule), None)
    if slot is not None:
        schedule[slot] = str(label)
    return slot


def layout_plan() -> dict:
    """连战工坊布局计划(GUI 写 work/rogue-config/rogue_layout_plan.json):
    {"stages": [{"from":1,"to":2,"tier":"easy|normal|elite|hell"}],
     "floors": {"5": {"curses": ["深渊重甲"], "field": "battle/…program"}}}
    stages 决定该层诅咒档位+难度乘区(PLAN_TIERS);floors 显式指定优先于随机。"""
    try:
        with open(
            rogue_config_path("rogue_layout_plan.json"), encoding="utf-8"
        ) as fh:
            return json.load(fh)
    except Exception:
        return {}


def plan_tier_for(plan: dict, r: int, default_tier: str) -> tuple[str, float]:
    for st in plan.get("stages") or []:
        try:
            if int(st["from"]) <= r <= int(st["to"]):
                return PLAN_TIERS.get(str(st.get("tier")), (default_tier, 1.0))
        except (KeyError, ValueError, TypeError):
            continue
    return (default_tier, 1.0)


def field_tuning() -> dict:
    """领域数值调整配置(GUI 写 mod-tools/rogue_field_tuning.json):
    {"global": {"加成": 1.0, "诅咒": 1.0, "场地": 1.0, "领域": 1.0},
     "per": {program: 倍率}}。倍率≠1 时构建期锻造缩放变体(wf_field_catalog.forge)。"""
    try:
        return json.load(open(rogue_config_path("rogue_field_tuning.json"),
                              encoding="utf-8"))
    except Exception:
        return {}


def pick_field_program(menu: list, rng):
    """法阵程序抽取:**全目录均匀**,每个条目一票。

    ⚠ 2026-07-29 曾按 √条目数 在分类间加权,理由是"刮风/重力的 73 项只是数值变体、
    观感上就两种效果"——**用户当场纠正:观感不一样**。实测参数跨度也支持这点:
    刮风强度 0.05→1.0(20 倍)、时长 280→3000 帧(4.7 秒→50 秒,10 倍);
    重力四种锚点(Top/Left/Center/Right)+ 94 种数值组合。那是 73 种不同体验。
    所以回到均匀,不替玩家做"这些看起来都一样"的判断。
    真正的问题是**标签分不出变体**,已在 wf_field_catalog.label_of 把强度/时长/
    锚点编进 note(「狂风领域·强风10秒·方向1」),而不是靠压低出场率来回避。
    """
    return menu[rng.randrange(len(menu))]


def log(message: str) -> None:
    """构建期审计日志。独立成函数,测试可截获“拒绝并重抽”而不吞输出。"""
    print(message)


# CreateCondition 的 AdditionalConditionKind 构造名。这里故意不用数字索引:
# 未知构造名在 validates=false 时会静默下落成索引 0,不崩不报、效果却像不存在。
DAMAGE_RESISTANCE_AC = {
    0: "ACAbilityDamageResistance",
    1: "ACDirectAttackDamageResistance",
    2: "ACPowerFlipDamageResistance",
    3: "ACSkillDamageResistance",
}
ELEMENT_DATA_CN = {1: "火", 2: "水", 3: "雷", 4: "风", 5: "光", 6: "暗"}
ELEMENT_CURSE_SPECS = {
    # 按随机排程强度排序；元素正抗性走 damage/(1+r)，不是伤害类型的 damage*(1-r)。
    "元素滞钝": (1, 1.0),
    "三相封界": (3, 9.0),
    "元素禁壁": (1, 99.0),
    "五相绝域": (5, 999.0),
}
MIXED_ELEMENT_CURSE_NAME = "混相禁域"
ELEMENT_CURSE_NAMES = (*tuple(ELEMENT_CURSE_SPECS), MIXED_ELEMENT_CURSE_NAME)
ELEMENT_RESISTANCE_STRENGTHS = (1.0, 9.0, 99.0, 999.0)
ELEMENT_LOCK_THRESHOLD = 99.0
STACKED_DAMAGE_STRENGTH = 0.01
STACKED_DEBUFF_STRENGTH = 1.0
STACKED_MAX_ACCUMULATION = 99
STACKED_DURATION_FRAMES = 9_999_999
STACKED_CURSE_NAMES = ("层叠龙鳞", "不屈龙心")
STACKED_DAMAGE_AC_KIND = {name: kind for kind, name in DAMAGE_RESISTANCE_AC.items()}


def element_immunity_requested(forced: dict | None) -> bool:
    """工坊是否明确要求本层保留属性免疫载体。"""
    names = list((forced or {}).get("curses") or [])
    return any(name in ELEMENT_CURSE_NAMES for name in names)


def hard_condition_carrier_requested(forced: dict | None) -> bool:
    """工坊是否钉了必须通过 general_boss c109 才能落地的词条。"""
    names = set(map(str, (forced or {}).get("curses") or []))
    return bool(names & (set(ELEMENT_CURSE_NAMES)
                         | set(DAMAGE_HARD_CURSE_NAMES)
                         | set(STACKED_CURSE_NAMES)))


def prefer_element_immunity_hp_candidates(ranked: list[tuple]) -> tuple[list[tuple], bool]:
    """HP 重排先用可挂属性免疫的候选；耗尽时显式回退原候选。

    每项最后一个元素是 metrics dict，其中 ``element_immunity_block=None``
    表示实际 general_boss 档、c36 与载体引用门禁均通过。返回值第二项为
    是否发生了“无合格载体，只能降级”的事实，调用方必须记录日志。
    """
    eligible = [item for item in ranked
                if item and isinstance(item[-1], dict)
                and item[-1].get("element_immunity_block") is None]
    return (eligible, False) if eligible else (ranked, bool(ranked))


DAMAGE_HARD_CURSE_NAMES = ("深渊壁垒", "绝对壁垒", "三重壁垒")
PRE_ACTION_CURSE_NAMES = DAMAGE_HARD_CURSE_NAMES + STACKED_CURSE_NAMES
HIGH_ONE_SHOT_CURSE_NAMES = (
    "绝对壁垒", "三重壁垒",
    *(name for name, (_count, strength) in ELEMENT_CURSE_SPECS.items()
      if strength >= ELEMENT_LOCK_THRESHOLD),
)
IMMUNITY_DURATION_FRAMES = 999_999


def stacked_resistance_layers_for_depth(r: int, n: int) -> int:
    """官方式累计层排程：前20% 20层，中段50层，最后20% 90层。"""
    if n <= 0 or not 1 <= r <= n:
        raise ValueError(f"轮次越界:r={r},n={n}")
    if r / n <= 0.2:
        return 20
    return 90 if r / n > 0.8 else 50


def stacked_resistance_entry(name: str, constructor: str,
                             strength: float, layers: int) -> dict:
    """构造一条叠层词条；文案只由真实单层强度与层数推导。"""
    strength = float(strength)
    layers = int(layers)
    if constructor not in (*STACKED_DAMAGE_AC_KIND, "ACToleranceOfDebuff"):
        raise ValueError(f"叠层抗性不支持构造 {constructor}")
    if not math.isfinite(strength) or strength <= 0:
        raise ValueError(f"叠层抗性单层强度非法:{strength}")
    if not 1 <= layers <= STACKED_MAX_ACCUMULATION:
        raise ValueError(f"叠层抗性层数必须为1~{STACKED_MAX_ACCUMULATION}:{layers}")
    if constructor == "ACToleranceOfDebuff":
        # ConditionChangeCalculator: 普通减益命中率 = hitRate - debuffResistance；
        # 随机数包含 0，所以 r=1 / hitRate=1 仍约十万分之一漏过；forceApply 始终绕过。
        text = (f"减益耐性×{layers}层（普通减益几乎无法命中；"
                "强制赋予除外）")
    else:
        kind = STACKED_DAMAGE_AC_KIND[constructor]
        reduction = strength * layers
        if reduction >= 1.0:
            label = "完全免疫"
        else:
            label = f"减{reduction * 100:.6g}%"
        text = f"{COND_KIND_CN[kind]}抗性×{layers}层（{label}）"
    return {"name": str(name),
            "stacked_resistance": [(constructor, strength, layers)],
            "text": text}


def _merged_stacked_resistance(picks: list[dict]) -> list[tuple[str, float, int]]:
    """合并同构造/强度的层数；超过官方 99 层上限即拒绝。"""
    layers_by_card: dict[tuple[str, float], int] = {}
    order: list[tuple[str, float]] = []
    for pick in picks:
        for constructor, strength, layers in pick.get("stacked_resistance", []):
            constructor = str(constructor)
            strength = float(strength)
            layers = int(layers)
            # 复用公开构造器做完整参数校验；这里只取其规范化结果。
            stacked_resistance_entry("_validate", constructor, strength, layers)
            key = (constructor, strength)
            if key not in layers_by_card:
                order.append(key)
            layers_by_card[key] = layers_by_card.get(key, 0) + layers
            if layers_by_card[key] > STACKED_MAX_ACCUMULATION:
                raise ValueError(
                    f"{constructor} 同参数累计 {layers_by_card[key]} 层>"
                    f"{STACKED_MAX_ACCUMULATION}，客户端会静默封顶")
    return [(constructor, strength, layers_by_card[(constructor, strength)])
            for constructor, strength in order]


def _stacked_resistance_totals(picks: list[dict]) -> dict[str, float]:
    """按客户端 strength×magnification 汇总叠层条件，不改变可见层 DSL。"""
    totals: dict[str, float] = {}
    for constructor, strength, layers in _merged_stacked_resistance(picks):
        totals[constructor] = totals.get(constructor, 0.0) + strength * layers
    return totals


def _normalize_resistance_atom(atom, key: str) -> tuple[int, float, bool]:
    """把旧二元耐性与新三元耐性统一为(target,value,cancelable)。

    `CreateCondition.params[4]` 是整条命令共用的可驱散标记。属性
    耐性属于深渊诅咒的常驻规则，所有强度都强制不可驱散；伤害类型
    r>=1 是硬墙，即使调用者请求 true 也强制改为 false。旧二元调用
    始终按 false 兼容。
    """
    if key not in {"damage_resistance", "element_resistance"}:
        raise ValueError(f"未知耐性通道:{key}")
    if not isinstance(atom, (list, tuple)) or len(atom) not in (2, 3):
        raise ValueError(f"{key} 耐性原子必须是二元/三元组:{atom!r}")
    raw_target, raw_value = atom[:2]
    if isinstance(raw_target, bool):
        raise ValueError(f"{key} 目标不能是 bool:{raw_target!r}")
    target, value = int(raw_target), float(raw_value)
    if key == "damage_resistance" and target not in DAMAGE_RESISTANCE_AC:
        raise ValueError(f"未知伤害类型 {target};只接受 0..3")
    if key == "element_resistance" and target not in ELEMENT_DATA_CN:
        raise ValueError(f"属性数据码 {target} 非法;只接受 1..6")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{key} 耐性强度必须是有限正数,收到 {value}")
    cancelable = False
    if len(atom) == 3:
        cancelable = atom[2]
        if not isinstance(cancelable, bool):
            raise ValueError(f"{key} cancelable 必须是 bool:{cancelable!r}")
    if key == "element_resistance":
        cancelable = False
    threshold = (ELEMENT_LOCK_THRESHOLD if key == "element_resistance" else 1.0)
    if value >= threshold - 1e-12:
        cancelable = False
    return target, value, cancelable


def _merged_resistance(picks: list[dict], key: str) -> list[tuple[int, float, bool]]:
    """跨诅咒按(target,cancelable)合并，保留命令级可驱散语义。

    属性轴与客户端一样累加 strength；伤害类型在同组内沿用取最强
    策略以防同组自行叠出负伤害。不同可驱散组必须分开落树；客户端最终
    依然会跨组累加，所以可解性由 `_resistance_totals_by_target` 再求和。
    """
    values: dict[tuple[int, bool], float] = {}
    order: list[tuple[int, bool]] = []
    for pick in picks:
        for raw in pick.get(key, []):
            target, value, cancelable = _normalize_resistance_atom(raw, key)
            group = (target, cancelable)
            if group not in values:
                order.append(group)
                values[group] = value
            elif key == "element_resistance":
                values[group] += value
            elif abs(value) > abs(values[group]):
                values[group] = value

    # 多张软卡在同 true 组合并后也可能跨过硬墙阈值。最终程序不允许
    # “高墙整体可驱散”，因此把该组迁入 false 后再合并。
    threshold = ELEMENT_LOCK_THRESHOLD if key == "element_resistance" else 1.0
    for group in list(order):
        target, cancelable = group
        if not cancelable or values[group] < threshold - 1e-12:
            continue
        hard_group = (target, False)
        value = values.pop(group)
        order.remove(group)
        if hard_group not in values:
            order.append(hard_group)
            values[hard_group] = value
        elif key == "element_resistance":
            values[hard_group] += value
        elif abs(value) > abs(values[hard_group]):
            values[hard_group] = value
    return [(target, values[(target, cancelable)], cancelable)
            for target, cancelable in order]


def _resistance_totals_by_target(picks: list[dict], key: str) -> dict[int, float]:
    """按客户端消费语义跨 cancelable false/true 两组求和。"""
    totals: dict[int, float] = {}
    for target, value, _cancelable in _merged_resistance(picks, key):
        totals[target] = totals.get(target, 0.0) + float(value)
    return totals


def damage_resistance_totals(picks: list[dict]) -> dict[int, float]:
    """按实际落表结果合计关卡、一次性和叠层三种伤害抗性。

    同一来源先沿用其编译合并规则；不同来源在客户端 ConditionSlot 中
    相加。不能只分别判断各来源是否达到 100%，否则会漏放 90%+40%。
    """
    totals = _resistance_totals_by_target(picks, "damage_resistance")
    for constructor, value in _stacked_resistance_totals(picks).items():
        kind = STACKED_DAMAGE_AC_KIND.get(constructor)
        if kind is not None:
            totals[kind] = totals.get(kind, 0.0) + value
    for kind, value in merge_conds(picks):
        if kind in {"0", "1", "2", "3"}:
            target = int(kind)
            totals[target] = totals.get(target, 0.0) + float(value)
    return totals


def immunity_axes(picks: list[dict]) -> tuple[set[str], set[int]]:
    """返回跨诅咒合并后的(完全免疫伤害类型,高阻断属性)。

    旧 c71 条目也纳入伤害轴,让迁移期/工坊旧计划同样过硬闸；新硬通道分别来自
    damage_resistance / element_resistance。伤害类型 r=1 走 ``*(1-r)``，确为免疫；
    元素 r>0 走 ``/(1+r)``，只把 r>=99（伤害至多 1%）视作封锁一条普通属性路。

    FixedAttackCalculator / RatioAttackCalculator 的 elementResistanceRate 与
    specificDamageResistance 均固定为 0，能绕过两轴；这些集合服务于 NormalAttack
    常规输出路的设计门禁，不宣称战斗在机制上绝对无解。
    """
    damage = {str(kind) for kind, value in damage_resistance_totals(picks).items()
              if value >= 1.0 - 1e-12}
    elements = {int(element) for element, value in
                _resistance_totals_by_target(picks, "element_resistance").items()
                if 1 <= int(element) <= 6
                and float(value) >= ELEMENT_LOCK_THRESHOLD - 1e-12}
    return damage, elements


ELEMENT_BAN_GUARANTEE_NAME = "属性封锁保底"
ELEMENT_BAN_GUARANTEE_STRENGTH = 999.0


def guarantee_element_bans(picks: list[dict], rng, minimum: int = 2, *,
                           excluded_elements=()) -> tuple[list[dict], dict]:
    """Plan additive elemental bans without replacing cards or spending slots.

    This is a policy operation, not proof that a Boss can execute the conditions.
    A runtime carrier must be checked separately before compiling a floor. Use
    a per-floor RNG independent of the tower RNG so this supplement cannot move
    the subsequent Boss/curse rolls. Existing >=99 totals count as bans; weaker
    resistance stays intact, including on the one remaining open element.
    """
    if isinstance(minimum, bool) or not isinstance(minimum, int) or not 0 <= minimum <= 5:
        raise ValueError("属性封锁保底数量只接受 0..5 的整数")
    excluded = set(excluded_elements)
    if any(type(e) is not int or e not in ELEMENT_DATA_CN for e in excluded):
        raise ValueError("属性封锁排除项必须是 1..6 的属性整数")
    if minimum > len(set(ELEMENT_DATA_CN) - excluded):
        raise ValueError("属性封锁保底超过可选属性数量")
    why = curse_conflict(picks)
    if why:
        raise ValueError(f"属性封锁保底前的原始组合非法，须重抽:{why}")
    totals = _resistance_totals_by_target(picks, "element_resistance")
    if any(totals.get(e, 0.0) > 0 for e in excluded):
        raise ValueError("排除属性仍有原始抗性，须先明确处理原有诅咒")
    blocked = immunity_axes(picks)[1]
    missing = max(0, minimum - len(blocked))
    selected = sorted(rng.sample(sorted(set(ELEMENT_DATA_CN) - blocked - excluded), missing)) if missing else []
    result = copy.deepcopy(picks)
    if selected:
        # Supplement only the missing strength. A weak original curse on a
        # selected element survives unchanged; the resulting total is r=999.
        atoms = [(element, ELEMENT_BAN_GUARANTEE_STRENGTH - totals.get(element, 0.0), False)
                 for element in selected]
        result.append({"name": ELEMENT_BAN_GUARANTEE_NAME,
                       "element_ban_guarantee": True,
                       "element_resistance": atoms,
                       "text": "·".join(ELEMENT_DATA_CN[e] for e in selected) + "伤害降至0.1%"})
    final = immunity_axes(result)[1]
    if not minimum <= len(final) <= 5 or not blocked <= final:
        raise ValueError("属性封锁保底合并后越界或丢失原有封锁")
    why = curse_conflict(result)
    if why:
        raise ValueError(f"属性封锁保底后的组合非法:{why}")
    receipt = {"minimum": minimum, "maximum": 5, "threshold": ELEMENT_LOCK_THRESHOLD,
                    "original_banned": sorted(blocked), "added_banned": selected,
                    "final_banned": sorted(final), "open_elements": sorted(set(ELEMENT_DATA_CN) - final),
                    "ordinary_slots_consumed": 0, "runtime_verified": False}
    if excluded:
        receipt["excluded_elements"] = sorted(excluded)
    return result, receipt


def element_ban_rng(seed: int, round_no: int):
    """Domain-separated reproducible RNG; independent of other floor draws."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("属性保底种子必须是整数")
    if isinstance(round_no, bool) or not isinstance(round_no, int) or round_no < 1:
        raise ValueError("属性保底层号必须为正整数")
    digest = hashlib.sha256(f"abyss-element-ban-v1:{seed}:{round_no}".encode("ascii")).digest()
    return random.Random(int.from_bytes(digest, "big"))


def _slv(value: int | float) -> list[dict]:
    return [{"min": value, "max": value}]


def resistance_label(value: float) -> str:
    """按元素公式 ``damage/(1+r)`` 生成不夸大的玩家文案。"""
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"属性耐性强度必须是有限正数,收到 {value}")
    denominator = 1.0 + value
    if math.isclose(denominator, 2.0, rel_tol=0.0, abs_tol=1e-12):
        return "伤害减半"
    nearest = round(denominator)
    if (denominator <= 10.0
            and math.isclose(denominator, nearest, rel_tol=0.0, abs_tol=1e-12)):
        return f"伤害降至1/{nearest}"
    percent = 100.0 / denominator
    return f"伤害降至{percent:.6g}%"


def element_strengths_for_depth(r: int, n: int) -> tuple[float, ...]:
    """混相禁域的逐属性强度池：20%/50%/80% 三个深度分界。"""
    if n <= 0 or not 1 <= r <= n:
        raise ValueError(f"轮次越界:r={r},n={n}")
    d = r / n
    count = 1 if d <= 0.2 else (2 if d <= 0.5 else (3 if d <= 0.8 else 4))
    return ELEMENT_RESISTANCE_STRENGTHS[:count]


def _card_resistance_atoms(rng, key: str, pairs) -> list[tuple[int, float, bool]]:
    """一张逻辑软卡只抽一次可驱散性；元素通道始终落为不可驱散。

    元素软卡仍消费原抽签，避免同 seed 后续诅咒/Boss 随机序列漂移。
    """
    base = [_normalize_resistance_atom((target, value, False), key)
            for target, value in pairs]
    threshold = ELEMENT_LOCK_THRESHOLD if key == "element_resistance" else 1.0
    has_soft = any(value < threshold - 1e-12 for _target, value, _ in base)
    soft_cancelable = bool(has_soft and rng.randrange(4) == 0)
    if key == "element_resistance":
        soft_cancelable = False
    return [(target, value,
             soft_cancelable if value < threshold - 1e-12 else False)
            for target, value, _old in base]


def mixed_element_entry(rng, strengths, forced=None,
                        name: str = MIXED_ELEMENT_CURSE_NAME) -> dict:
    """生成每个属性独立强度的混相卡。

    forced 在任何 RNG 调用前完整校验，工坊钉选因此不消耗这张
    卡自身的属性数/属性/强度/可驱散抽签。作者钉选样例明确落成
    不可驱散；随机软卡才按 3:1 混入可驱散版。
    """
    try:
        allowed = tuple(float(value) for value in strengths)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"混相强度池非法:{strengths!r}") from exc
    if (not allowed or any(value not in ELEMENT_RESISTANCE_STRENGTHS
                           for value in allowed)
            or len(set(allowed)) != len(allowed)):
        raise ValueError(f"混相强度池必须是 1/9/99/999 的非空唯一子集:{allowed}")

    if forced is not None:
        if not isinstance(forced, list) or not 1 <= len(forced) <= 5:
            raise ValueError("工坊 element_mix 必须是 1~5 项列表")
        parsed: list[tuple[int, float, bool]] = []
        seen: set[int] = set()
        for item in forced:
            if not isinstance(item, dict) or set(item) != {"element", "strength"}:
                raise ValueError(f"element_mix 每项必须只含 element/strength:{item!r}")
            element, strength = item["element"], item["strength"]
            if (isinstance(element, bool) or not isinstance(element, int)
                    or element not in ELEMENT_DATA_CN):
                raise ValueError(f"element_mix 属性必须是数据层 1..6:{element!r}")
            if (isinstance(strength, bool)
                    or not isinstance(strength, (int, float))
                    or float(strength) not in ELEMENT_RESISTANCE_STRENGTHS):
                raise ValueError(f"element_mix 强度只允许 1/9/99/999:{strength!r}")
            if element in seen:
                raise ValueError(f"element_mix 属性重复:{element}")
            seen.add(element)
            parsed.append((element, float(strength), False))
        atoms = sorted(parsed)
    else:
        count = rng.randrange(5) + 1
        elements = sorted(rng.sample(range(1, 7), count))
        raw = [(element, allowed[rng.randrange(len(allowed))])
               for element in elements]
        atoms = _card_resistance_atoms(rng, "element_resistance", raw)
    text = "·".join(ELEMENT_DATA_CN[element] + resistance_label(value)
                    for element, value, _cancelable in atoms)
    return {"name": str(name), "element_resistance": atoms, "text": text}


def build_immunity_dsl_tree(
        damage_resistance: list[tuple],
        element_resistance: list[tuple],
        stacked_resistance: list[tuple[str, float, int]] | None = None) -> list:
    """耐性 action DSL 树(CreateCondition → 自身 conditionSlot)。

    ⚠ 元素码必须写数据层 ToleranceOfElementTarget 的 1-based 编码:
      1火/2水/3雷/4风/5光/6暗；客户端内部虽 remap 为 0=全属性、1..6=六属性,
      这里绝不能写内部编码 0,也不接受 254=ALL / 255=OWNER。
    """
    damage = _merged_resistance(
        [{"damage_resistance": damage_resistance}], "damage_resistance")
    elements = _merged_resistance(
        [{"element_resistance": element_resistance}], "element_resistance")
    grouped: dict[bool, list] = {False: [], True: []}
    for kind, value, cancelable in damage:
        name = DAMAGE_RESISTANCE_AC[kind]
        if name not in wf_dsl_sig.ENUMS["AdditionalConditionKind"]:
            raise RuntimeError(f"DSL 签名表缺少构造 {name},拒绝静默下落")
        grouped[cancelable].append(
            [name, _slv(IMMUNITY_DURATION_FRAMES), _slv(value), _slv(1)])
    for element, value, cancelable in elements:
        name = "ACToleranceOfElement"
        if name not in wf_dsl_sig.ENUMS["AdditionalConditionKind"]:
            raise RuntimeError(f"DSL 签名表缺少构造 {name},拒绝静默下落")
        grouped[cancelable].append(
            [name, _slv(IMMUNITY_DURATION_FRAMES), element, _slv(value), _slv(1)])
    if "CreateCondition" not in wf_dsl_sig.COMMANDS:
        raise RuntimeError("DSL 签名表缺少 CreateCondition,拒绝静默下落")
    if "GenericConditionHitEffect" not in wf_dsl_sig.ENUMS["ConditionHitEffect"]:
        raise RuntimeError("DSL 签名表缺少 GenericConditionHitEffect")
    commands: list[list] = []
    # params[4] 是整条 CreateCondition 共用布尔；必须先 false 后 true
    # 分成至多两条命令，不能把原子级语义塞进不存在的参数位。
    for cancelable in (False, True):
        acs = grouped[cancelable]
        if not acs:
            continue
        commands.append(["Command", [
            "CreateCondition", -17, acs, _slv(1), ["GenericConditionHitEffect"],
            cancelable,
            False, "", None, False,
            3,                     # 目标种类必填 3
            _slv(1), False,
        ]])

    stacked = [(str(constructor), float(strength), int(layers))
               for constructor, strength, layers in (stacked_resistance or [])]
    # 同参数卡超过 maxAccumulation 时客户端会静默封顶；产出前必须拒绝。
    _stacked_resistance_totals([{"stacked_resistance": stacked}])
    for constructor, strength, layers in stacked:
        if constructor not in wf_dsl_sig.ENUMS["AdditionalConditionKind"]:
            raise ValueError(f"DSL 签名表缺少叠层构造 {constructor},拒绝静默下落")
        if constructor == "ACToleranceOfDebuff":
            ac = [constructor, _slv(STACKED_DURATION_FRAMES),
                  _slv(strength), _slv(STACKED_MAX_ACCUMULATION)]
        else:
            if constructor not in STACKED_DAMAGE_AC_KIND:
                raise ValueError(f"叠层抗性不支持构造 {constructor}")
            ac = [constructor, _slv(STACKED_DURATION_FRAMES),
                  _slv(strength), _slv(STACKED_MAX_ACCUMULATION)]
        # 终始之龙的层数不是写进 maxAccumulation，而是重复同 GID 条件：每次
        # outer magnification=1，同 ID 重放后逐层累计，99 只是上限。
        for _ in range(layers):
            commands.append(["Command", [
                "CreateCondition", -17, [copy.deepcopy(ac)], _slv(1), ["None"],
                False,             # 官方素材同样不可驱散
                True,              # 跳过同帧 hash 去重；否则重复命令只落第一层
                "", None, False,
                3, _slv(1), False,
            ]])
    if not commands:
        raise ValueError("空免疫 DSL 没有可执行词条")
    # general_boss c109/c111-160 引用的 3382 个可解析 enemy action 全部是 ActionDsl v1。
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False,
            False, 0, ["Block", commands]]


def build_immunity_dsl_blob(tree: list) -> bytes:
    """AMF3 + raw-deflate 往返自校验；构造名/参数树有任何漂移就拒绝产出。"""
    from wf.tools.rogue._dsl_validation import _validate_official_dsl
    _validate_official_dsl(tree, "abyss-immunity-before-serialization")
    raw = wf_dsl.encode_amf3(tree)
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    blob = co.compress(raw) + co.flush()
    parsed = wf_dsl.parse_dsl(zlib.decompress(blob, -15))["tree"]
    if parsed != tree:
        raise RuntimeError("属性免疫 DSL build→parse 往返不等价")
    _validate_official_dsl(parsed, "abyss-immunity-after-serialization")
    return blob


def immunity_program(
        damage_resistance: list[tuple],
        element_resistance: list[tuple],
        stacked_resistance: list[tuple[str, float, int]] | None = None) -> tuple[str, list]:
    """同一耐性参数签名复用同一 action 文件,避免每层重复锻造。"""
    damage = sorted(_merged_resistance(
        [{"damage_resistance": damage_resistance}], "damage_resistance"))
    elements = sorted(_merged_resistance(
        [{"element_resistance": element_resistance}], "element_resistance"))
    stacked = sorted((str(k), float(v), int(n))
                     for k, v, n in (stacked_resistance or []))
    tree = build_immunity_dsl_tree(damage, elements, stacked)
    signature = json.dumps([damage, elements, stacked],
                           ensure_ascii=True, separators=(",", ":"))
    tag = hashlib.sha1(signature.encode("ascii")).hexdigest()[:12]
    return f"battle/action/enemy/action/mod_rogue/immunity_{tag}", tree


def rewrite_boss_carrier_node(node, action_program: str | None = None,
                              pre_action_program: str | None = None,
                              action_programs=()):
    """克隆 general_boss 节点并追加普通 action / c109 pre_action。

    c109 不能覆盖官方已有 pre_action；c110=true 保证续战重跑。字段用 csv.reader/writer
    处理,包含逗号的程序数组仍保持一格。多个领域共用**同一个** boss 克隆和 action
    槽；按程序 ID 去重，避免双领域把同一程序重复执行。
    """
    programs = ([action_program] if action_program else []) + list(action_programs or ())
    programs = list(dict.fromkeys(str(p) for p in programs if str(p)))
    if not programs and not pre_action_program:
        raise ValueError("载体克隆至少需要一个 action 程序")

    def append(cell: str, program: str) -> str:
        existing = [] if cell in ("", "(None)") else cell.split(",")
        return ",".join(existing if program in existing else existing + [program])

    def rewrite(value):
        if isinstance(value, dict):
            return {k: rewrite(v) for k, v in value.items()}
        row = cells(value)
        while len(row) < 162:
            row.append("")
        if pre_action_program:
            row[109] = append(row[109], pre_action_program)
            row[110] = "true"
        if programs:
            for i in range(111, 161):
                if row[i] not in ("", "(None)"):
                    for program in programs:
                        row[i] = append(row[i], program)
                    break
            else:
                row[111] = ",".join(programs)
        return join(row, isinstance(value, (bytes, bytearray)))

    return rewrite(node)


def curse_conflict(picks: list[dict]) -> str | None:
    """这组诅咒能不能同层?返回冲突原因;None = 可以。

    2026-07-29「三重壁垒」上线后实测:深层烈狱 20000 次采样里
      · 绝对壁垒 + 三重壁垒 同层 5.9%
      · **四系伤害全免疫 = 无解层 1.26%**(绝对壁垒免疫的那系,正好是三重壁垒放行的那系)
      · 条件槽被填满 30.3%(超出的被 `conds[:5]` **静默截断**,配的效果白配)
    全塔烈狱会把这两个概率放大,所以按硬规则拦在抽取环节。
    """
    # ① 同一 kind 同时有正值(抗性/免疫)和负值(易伤)= 自相矛盾。
    #    ⚠ 判据必须看**符号**,不能只看"是不是 1.0"——2026-07-29 第一版只拦
    #    「完全免疫 1.0 + 易伤」,漏掉了 0.3/0.4/0.5 三档抗性配易伤;全库两两普查:
    #      深渊壁垒+深渊逆鳞 **16/16 恒冲突**(壁垒盖全四系,逆鳞必然踩上)
    #      亡者不屈+深渊逆鳞 4/16、深渊逆鳞+绝对壁垒 4/16、深渊重甲+深渊逆鳞 4/16
    field_programs = [str(pick["caster"][1]) for pick in picks
                      if pick.get("caster")]
    if len(field_programs) > 1:
        return ("领域同时执行闭包未证明，同层当前最多落一个程序:"
                + "+".join(field_programs))
    try:
        _stacked_resistance_totals(picks)
    except (TypeError, ValueError) as exc:
        return f"叠层抗性参数非法:{exc}"
    signs: dict[str, set] = {}
    for p in picks:
        for k, v in p.get("cond", []):
            if k == "4":
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            signs.setdefault(k, set()).add("+" if fv > 0 else "-")
        for atom in p.get("damage_resistance", []):
            try:
                k, fv, _cancelable = _normalize_resistance_atom(
                    atom, "damage_resistance")
            except (TypeError, ValueError):
                continue
            signs.setdefault(str(k), set()).add("+" if fv > 0 else "-")
        for constructor, strength, _layers in p.get("stacked_resistance", []):
            kind = STACKED_DAMAGE_AC_KIND.get(str(constructor))
            if kind is not None:
                signs.setdefault(str(kind), set()).add(
                    "+" if float(strength) > 0 else "-")
    bad = sorted(k for k, s in signs.items() if len(s) > 1)
    if bad:
        return f"kind {bad} 同时有抗性/免疫和易伤(自相矛盾)"
    # ② 槽位与无解层判定都按**合并后**的条件算(同 kind 同号会被 merge_conds 收成一条)
    merged = merge_conds(picks)
    if len(merged) > 5:
        return "条件槽超 5(超出的会被静默截断)"
    damage_immune, element_immune = immunity_axes(picks)
    if damage_immune >= {"0", "1", "2", "3"}:
        return "四种伤害类型全免疫(无解层)"
    # 2026-09-09: keep all rolled cards and allow a separate minimum-ban
    # supplement. The open element may retain weak resistance; only six
    # combined high-blocking totals are forbidden.
    if element_immune >= {1, 2, 3, 4, 5, 6}:
        return (f"六属性均达高阻断阈值(r≥{fmt(ELEMENT_LOCK_THRESHOLD)};"
                "普通属性伤害出口封死，定值/比例伤害仍可绕过)")
    return None


def curse_runtime_conflict(picks: list[dict], *, baseline_c86: float,
                           c86_limits: tuple[float, float],
                           baseline_dps: float,
                           base_duration_s: float,
                           hp_channel: str = "c86") -> str | None:
    """组合落表前的数值硬闸；违规组合必须拒绝并重抽，不能截断。

    no-boss/identity-locked 的血量乘数走 c86；general 与 standard_dsl 的
    血量诅咒折进克隆资源，c86 恒为 1。短时限始终按最终实战 DPS 合并后判。
    """
    base_c86 = float(baseline_c86)
    base_dps = float(baseline_dps)
    base_time = float(base_duration_s)
    lo, hi = map(float, c86_limits)
    if not all(math.isfinite(v) and v > 0
               for v in (base_c86, base_dps, base_time, lo, hi)) or hi < lo:
        raise ValueError(
            f"诅咒数值门禁输入非法:c86={baseline_c86},limits={c86_limits},"
            f"dps={baseline_dps},time={base_duration_s}")
    hp_mult = math.prod(float(c.get("hp", 1.0)) for c in picks)
    clone_channels = {"boss_level", "standard_dsl", "mixed_hp", "special_bundle"}
    if hp_channel not in {"c86", *clone_channels}:
        raise ValueError(f"未知 HP 通道:{hp_channel}")
    final_c86 = (base_c86 if hp_channel in clone_channels
                 else float(fmt(base_c86 * hp_mult)))
    if not lo <= final_c86 <= hi:
        return (f"最终 c86={final_c86:g} 超出本层窗口 {lo:g}~{hi:g}"
                f"(基线 {base_c86:g}×诅咒血量 {hp_mult:g})")
    frames = [float(c["time"]) for c in picks if c.get("time") is not None]
    duration = min(frames) / 60.0 if frames else base_time
    realized_dps = base_dps * hp_mult * base_time / duration
    if duration < 300.0 and realized_dps > 20_000_000.0:
        return (f"短时限高血量无解:{duration:.0f}s/"
                f"{realized_dps:.0f} DPS>20000000")
    return None


def high_threat_curse_conflict(picks: list[dict]) -> str | None:
    """高威胁 boss 的统一降难门禁；独立于是否有 HP 基线参数。"""
    if any(c.get("time") is not None for c in picks):
        return "高威胁 boss 禁止时限诅咒"
    high_elements = [(element, value) for element, value in
                     _resistance_totals_by_target(
                         picks, "element_resistance").items()
                     if float(value) >= ELEMENT_LOCK_THRESHOLD - 1e-12]
    if high_elements:
        return ("高威胁 boss 禁止高档属性墙(r≥"
                f"{fmt(ELEMENT_LOCK_THRESHOLD)}):{high_elements}")
    hp_mult = math.prod(float(c.get("hp", 1.0)) for c in picks)
    if not math.isfinite(hp_mult) or hp_mult > 1.5 + 1e-12:
        return f"高威胁 boss 诅咒血量×{hp_mult:g} 超过基准 1.5 倍"
    return None


def merge_conds(picks: list[dict]) -> list[tuple[str, str]]:
    """多个诅咒的条件槽合并:同 kind 的**同号**值取绝对值最大的一条。

    同 kind 重复会白占 5 个槽里的名额(弱的被强的盖住,语义上没意义),合并后
    能多塞一个诅咒。全库普查里这种"冗余重复"有 6 对,例如
    深渊壁垒(四系0.3) + 亡者不屈(能力0.5) → 能力只留 0.5。
    kind4(减益免疫)没有强度,去重保留一条即可。
    ⚠ 同 kind **异号**不在这里合并 —— 那是硬冲突,由 curse_conflict 拒掉,
      不能悄悄合成一个值糊弄过去。
    """
    best: dict[str, float] = {}
    order: list[str] = []
    has_debuff = False
    for p in picks:
        for k, v in p.get("cond", []):
            if k == "4":
                has_debuff = True
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if k not in best:
                order.append(k)
                best[k] = fv
            elif abs(fv) > abs(best[k]):
                best[k] = fv
    out: list[tuple[str, str]] = [("4", "")] if has_debuff else []
    out += [(k, fmt(best[k])) for k in order]
    return out


# ---- 诅咒组合(2026-07-29 用户需求「设计组合一下随机效果」)----
# 纯独立随机在 3 诅咒档位下经常出"三个不相干的数值"——有强度没主题。
# 组合 = 手工搭的成套方案,每套有明确玩法身份;抽中组合时整套落地,
# 剩余名额再用独立随机补。`field_cat` 指定该组合里「深渊法阵」从哪一类场效果抽。
CURSE_COMBOS = (
    {"name": "单通道", "curses": ("三重壁垒", "深渊逆鳞"),
     "note": "只剩一系能打,而那一系还易伤——逼构筑但留了出口"},
    {"name": "铁壁", "curses": ("深渊壁垒", "血肉高墙", "深渊重甲"),
     "note": "全系抗性+血厚+韧性,纯耐久战"},
    {"name": "速攻", "curses": ("玻璃深渊", "时之枷锁"),
     "note": "敌攻爆表血减半+限时,抢杀或被杀"},
    {"name": "枯竭", "curses": ("魔力枯竭", "亡者不屈", "深渊法阵"), "field_cat": "诅咒",
     "note": "攒不了 FEVER、上不了减益、场地还在削你"},
    {"name": "绞肉机", "curses": ("血肉高墙", "嗜血狂潮", "深渊重甲"),
     "note": "血厚攻高韧性高,长期拉锯"},
    {"name": "孤注", "curses": ("绝对壁垒", "深渊法阵"), "field_cat": "加成",
     "note": "一系完全免疫,但场地反过来给你增益"},
    {"name": "风暴", "curses": ("深渊法阵", "深渊逆鳞"), "field_cat": "环境",
     "note": "刮风/重力搅局,配一系易伤当补偿"},
    {"name": "凋零", "curses": ("时之枷锁", "深渊法阵", "血肉高墙"), "field_cat": "诅咒",
     "note": "限时+血厚+场地持续削,DPS 检定"},
    {"name": "偏转阵列", "curses": ("直击偏转", "术式扰流", "深渊重甲"),
     "soft_fallback": True,
     "note": "无硬载体专场的软通道组合:直击/技能减伤+韧性,不改 Boss 动作"},
    {"name": "迟滞战线", "curses": ("直击偏转", "魔力枯竭", "亡者不屈"),
     "soft_fallback": True,
     "note": "无硬载体专场的消耗组合:直击减伤+FEVER 压力+减益防护"},
)
COMBO_RATE = 0.55        # 名额 ≥2 时走组合的概率,其余走独立随机
# 已通过 general_boss c109/c36/阶段引用门禁的楼层，优先尝试一条属性耐性。
# 不是 100% 强制：保留少量纯组合/数值层，也避免把“可承载”误写成“必须承载”。
ELEMENT_CURSE_PREFERENCE_RATE = 0.85

SOFT_CHANNEL_CURSE_NAMES = ("能力抑制", "直击偏转", "术式扰流")

# Boss HP 适配与诅咒落表是两条不同的能力轴。过去这里靠
# ``forbid_hp_curses``、``caps.boss``、``caps.element`` 三处临时判断拼接，
# 新专用族如果漏接一处就会被默认放行。矩阵把每一种已知
# (HP channel, family) 的静态能力列全；未声明组合直接失败，不继承“通用安全”。
CURSE_CAPABILITY_SCHEMA = "wf-rogue-curse-capability/v1"
CURSE_CAPABILITY_AXES = (
    "hp_multiplier", "attack_multiplier", "time_limit",
    "soft_quest_condition", "hard_damage_resistance",
    "hard_element_resistance", "stacked_resistance",
    "field_action", "panel_gimmick",
)


def _curse_capability_row(*, hp_multiplier: bool = True,
                          hard_carrier: bool = False,
                          panel_gimmick: bool = True) -> dict[str, bool]:
    return {
        "hp_multiplier": bool(hp_multiplier),
        "attack_multiplier": True,
        "time_limit": True,
        "soft_quest_condition": True,
        "hard_damage_resistance": bool(hard_carrier),
        "hard_element_resistance": bool(hard_carrier),
        "stacked_resistance": bool(hard_carrier),
        "field_action": bool(hard_carrier),
        "panel_gimmick": bool(panel_gimmick),
    }


CURSE_CAPABILITY_MATRIX: dict[tuple[str, str], dict[str, bool]] = {
    ("boss_level", "general"): _curse_capability_row(hard_carrier=True),
    ("standard_dsl", "standard"): _curse_capability_row(),
    ("mixed_hp", "mixed"): _curse_capability_row(hard_carrier=True),
    ("c86", "identity-locked"): _curse_capability_row(hard_carrier=True),
    ("c86", "identity-locked-standard"): _curse_capability_row(),
    ("c86", "identity-locked-mixed"): _curse_capability_row(
        hard_carrier=True),
    ("c86", "no-boss"): _curse_capability_row(panel_gimmick=False),
    # 非严格旧路径仍会显式落到 unknown；它不是新 Boss 家族的默认项。
    ("unscaled", "unknown"): _curse_capability_row(hard_carrier=True),
    ("special_bundle", "orochi"): _curse_capability_row(),
    ("special_bundle", "orochi_ex"): _curse_capability_row(),
    ("special_bundle", "kraken"): _curse_capability_row(),
    ("special_bundle", "conductor"): _curse_capability_row(),
    ("special_bundle", "touyakiren_ceo"): _curse_capability_row(),
    **{
        ("special_bundle", family): _curse_capability_row(
            hp_multiplier=False)
        for family in SPHERE_SPECS
    },
}


def curse_capability_matrix_receipt() -> list[dict]:
    """Return a stable, JSON-safe copy of every declared static matrix row."""

    return [
        {"channel": channel, "family": family,
         "capabilities": dict(CURSE_CAPABILITY_MATRIX[(channel, family)])}
        for channel, family in sorted(CURSE_CAPABILITY_MATRIX)
    ]


def resolve_curse_capabilities(
        channel: str, family: str, caps: dict | None = None, *,
        no_base: bool = False) -> dict:
    """Resolve one declared matrix row against this floor's proven carriers."""

    key = (str(channel), str(family))
    declared = CURSE_CAPABILITY_MATRIX.get(key)
    if declared is None:
        raise ValueError(
            "UNDECLARED_CURSE_CAPABILITY:"
            f"channel={key[0]},family={key[1]};"
            "新增 Boss/适配通道必须先声明诅咒能力矩阵")
    caps = dict(caps or {})
    effective = dict(declared)
    restrictions: list[str] = []
    carrier_axes = (
        "hard_damage_resistance", "stacked_resistance", "field_action")
    if not caps.get("boss"):
        for axis in carrier_axes:
            if effective[axis]:
                effective[axis] = False
        restrictions.append(str(
            caps.get("carrier_reason") or "no_proved_general_boss_carrier"))
    if not caps.get("element"):
        if effective["hard_element_resistance"]:
            effective["hard_element_resistance"] = False
        restrictions.append(str(
            caps.get("element_reason") or "no_proved_element_carrier"))
    if not caps.get("panel"):
        effective["panel_gimmick"] = False
        restrictions.append("field_has_no_proved_panel_pair")
    if no_base:
        effective["attack_multiplier"] = False
        effective["time_limit"] = False
        restrictions.append("no_auditable_hp_base")
    if key[1] in SPHERE_HP_CURSE_FORBIDDEN_FAMILIES:
        restrictions.append("sphere_phase_budget_forbids_hp_multiplier")
    return {
        "schema": CURSE_CAPABILITY_SCHEMA,
        "channel": key[0], "family": key[1],
        "declared": dict(declared), "effective": effective,
        "restrictions": list(dict.fromkeys(restrictions)),
    }


def curse_card_capability_requirements(card: dict) -> set[str]:
    """Classify one realized card by the actual columns/resources it needs."""

    requirements: set[str] = set()
    if not math.isclose(float(card.get("hp", 1.0)), 1.0,
                        rel_tol=0.0, abs_tol=1e-12):
        requirements.add("hp_multiplier")
    if not math.isclose(float(card.get("atk", 1.0)), 1.0,
                        rel_tol=0.0, abs_tol=1e-12):
        requirements.add("attack_multiplier")
    if card.get("time") is not None:
        requirements.add("time_limit")
    if card.get("cond"):
        requirements.add("soft_quest_condition")
    if card.get("damage_resistance"):
        requirements.add("hard_damage_resistance")
    if card.get("element_resistance"):
        requirements.add("hard_element_resistance")
    if card.get("stacked_resistance"):
        requirements.add("stacked_resistance")
    if card.get("caster"):
        requirements.add("field_action")
    if card.get("gimmick"):
        requirements.add("panel_gimmick")
    return requirements


def curse_capability_block(card: dict, profile: dict) -> str | None:
    """Return the first unavailable capability required by ``card``."""

    effective = profile.get("effective") if isinstance(profile, dict) else None
    if not isinstance(effective, dict):
        return "missing_capability_profile"
    missing = sorted(
        axis for axis in curse_card_capability_requirements(card)
        if effective.get(axis) is not True)
    return ",".join(missing) if missing else None

# ---- 攻击类诅咒分档表(2026-07-30 降档)----
# 旧值 (1.4,1.7,2.0)/(1.5,1.8,2.2)/(2.2,2.6,3.0),烈狱档顶格叠在塔尾自身已达
# 2.4-3.3 的基础曲线上 → col>4 的层全是这三个。新烈狱端点 1.7/1.8/2.6
# (2026-07-30 用户指定),低档按同比例下调保持单调阶梯——阶梯本身也是**降档闸**
# 的台阶(超标层 tier 2→1→0→摘除,逐级重算,desc 跟着改,落表值与文案永不脱节)。
ATK_CURSE_TIERS = {
    "嗜血狂潮": (1.05, 1.10, 1.15),
    "深渊逆鳞": (1.10, 1.20, 1.30),
    "玻璃深渊": (1.20, 1.30, 1.40),
}


def atk_curse_entry(name: str, t: int, weak: int = 0) -> dict:
    """攻击类诅咒在档位 t 的完整条目。降档闸复用同一入口 → 数值与 text 恒一致。"""
    mult = ATK_CURSE_TIERS[name][t]
    if name == "嗜血狂潮":
        return {"name": name, "atk": mult, "hp": 0.85, "atk_tier": t,
                "text": f"敌攻×{mult}·血-15%"}
    if name == "玻璃深渊":
        return {"name": name, "atk": mult, "hp": 0.5, "atk_tier": t,
                "text": f"敌攻×{mult}·血-50%"}
    w = (0.3, 0.4, 0.5)[t]                       # 深渊逆鳞:易伤系绑三重壁垒放行系
    return {"name": name, "atk": mult, "atk_tier": t, "weak": weak,
            "cond": [(str(weak), fmt(-w))],
            "text": f"敌攻×{mult}·{COND_KIND_CN[weak]}易伤{int(w * 100)}%"}


def _curse_pool(t: int, rng, *, stack_layers: int = 50,
                mixed_strengths=ELEMENT_RESISTANCE_STRENGTHS,
                forced_element_mix=None) -> list[dict]:
    """t = 档位索引 0/1/2。硬通道耐性键单列,不再占 quest c71-80。"""
    wall = rng.randrange(4)   # 绝对壁垒的免疫系随机
    wall_open = rng.randrange(4)                             # 三重壁垒放行的那一系
    wall3 = [k for k in range(4) if k != wall_open]           # 其余三系全免
    # 属性诅咒族:1/3/1/5 属性四档；最强一档仍明确留下 1 个属性出口。
    # 文案统一从 damage/(1+r) 反推，绝不能再把 r=1 写成“完全免疫”。
    # 每条独立抽样,跨条目叠加后的出口由 curse_conflict 再做全组合硬闸。
    element_sets = {name: sorted(rng.sample(range(1, 7), count))
                    for name, (count, _strength) in ELEMENT_CURSE_SPECS.items()}
    _stacked_constructors = tuple(DAMAGE_RESISTANCE_AC.values())
    stacked_damage_constructor = _stacked_constructors[
        rng.randrange(len(_stacked_constructors))]
    stacked_damage = stacked_resistance_entry(
        "层叠龙鳞", stacked_damage_constructor,
        STACKED_DAMAGE_STRENGTH, stack_layers)
    stacked_debuff = stacked_resistance_entry(
        "不屈龙心", "ACToleranceOfDebuff",
        STACKED_DEBUFF_STRENGTH, stack_layers)
    mixed_element = mixed_element_entry(
        rng, mixed_strengths, forced=forced_element_mix)

    def element_entry(name: str) -> dict:
        blocked = element_sets[name]
        _count, strength = ELEMENT_CURSE_SPECS[name]
        open_elements = [e for e in range(1, 7) if e not in blocked]
        text = ("·".join(ELEMENT_DATA_CN[e] for e in blocked)
                + "属性" + resistance_label(strength))
        if len(open_elements) <= 3:
            text += "(只留" + "·".join(ELEMENT_DATA_CN[e] for e in open_elements) + ")"
        return {"name": name,
                "element_resistance": _card_resistance_atoms(
                    rng, "element_resistance", [(e, strength) for e in blocked]),
                "text": text}
    # ⚠ 逆鳞的易伤系**绑定到三重壁垒放行的那一系**,不再独立随机:
    # 【单通道】= 三重壁垒 + 深渊逆鳞,承诺"只剩一系能打、而那一系还易伤"。
    # 独立随机时易伤经常落在已经免疫的系上(实测 1.4.241 第15战:三系免疫 + 能力易伤,
    # 而能力正是被免疫的那个)——组合的承诺落空,同一 kind 还同时挂免疫和易伤。
    # 绑定后单通道恒自洽;逆鳞单独出现时 wall_open 本身就是随机的,不影响随机性。
    weak = wall_open
    # 随机法阵只从"已验证安全"的分类里抽;「环境」类要工坊钉选(见 FIELD_RANDOM_CATS)
    _menu = [m for m in field_menu_all() if (m[3] if len(m) > 3 else "领域") in FIELD_RANDOM_CATS]
    _menu = _menu or field_menu_all()
    fm = pick_field_program(_menu, rng)     # 分类间 √ 加权,分类内均匀
    return [
        {"name": "深渊重甲", "tp": (3, 6, 9)[t], "cond": [("2", fmt((0.2, 0.3, 0.4)[t]))],
         "text": f"韧性×{(3, 6, 9)[t]}·弹耐{int((0.2, 0.3, 0.4)[t] * 100)}%"},
        {"name": "魔力枯竭", "fever": (600, 800, 1200)[t],
         "text": f"FEVER需求×{(1.5, 2, 3)[t]}"},
        {"name": "时之枷锁", "time": (21600, 14400, 10800)[t],
         "text": f"限时{(6, 4, 3)[t]}分"},
        atk_curse_entry("嗜血狂潮", t),
        {"name": "深渊壁垒",
         "damage_resistance": _card_resistance_atoms(
             rng, "damage_resistance",
             [(k, (0.2, 0.25, 0.3)[t]) for k in range(4)]),
         "text": f"全系耐性{int((0.2, 0.25, 0.3)[t] * 100)}%"},
        {"name": "亡者不屈", "cond": [("4", ""), ("0", fmt((0.3, 0.4, 0.5)[t]))],
         "text": f"减益免疫·能耐{int((0.3, 0.4, 0.5)[t] * 100)}%"},
        # 无属性/动作硬通道的专用 Boss 不能安全克隆 c109，也不能挂元素耐性 DSL。
        # 这三条只复用已真机工作的 quest c71-80 InitialEnemyCondition，强度始终
        # 低于完全免疫；既增加专场随机性，也不引入代号引用或资源闭包。
        {"name": "能力抑制", "cond": [("0", fmt((0.2, 0.3, 0.4)[t]))],
         "soft_channel_fallback": True,
         "text": f"能力耐性{int((0.2, 0.3, 0.4)[t] * 100)}%"},
        {"name": "直击偏转", "cond": [("1", fmt((0.2, 0.3, 0.4)[t]))],
         "soft_channel_fallback": True,
         "text": f"直击耐性{int((0.2, 0.3, 0.4)[t] * 100)}%"},
        {"name": "术式扰流", "cond": [("3", fmt((0.2, 0.3, 0.4)[t]))],
         "soft_channel_fallback": True,
         "text": f"技能耐性{int((0.2, 0.3, 0.4)[t] * 100)}%"},
        {"name": "血肉高墙", "hp": (1.6, 2.0, 2.5)[t],
         "text": f"敌血×{(1.6, 2.0, 2.5)[t]}"},
        atk_curse_entry("深渊逆鳞", t, weak),
        # 绝对壁垒:随机一系伤害极高耐性,炼狱=完全免疫(强度1.0=伤害×0),逼构筑切换
        {"name": "绝对壁垒", "damage_resistance": _card_resistance_atoms(
             rng, "damage_resistance", [(wall, (0.7, 0.85, 1.0)[t])]),
         "text": f"{COND_KIND_CN[wall]}{'完全免疫' if t == 2 else '耐性' + str(int((0.7, 0.85, 1.0)[t] * 100)) + '%'}"},
        # 三重壁垒(2026-07-29 用户需求「免疫可以不止一种,比如三种」):
        # 四系里随机去掉一系,剩下三系同时高耐性/炼狱档完全免疫 —— 只留一条输出路,
        # 逼队伍必须带对那一系。条件槽有 5 个,三条 cond 塞得下。
        {"name": "三重壁垒",
         "damage_resistance": _card_resistance_atoms(
             rng, "damage_resistance", [(k, (0.5, 0.7, 1.0)[t]) for k in wall3]),
         "text": ("·".join(COND_KIND_CN[k] for k in wall3)
                   + ('三重免疫' if t == 2 else f"三重耐性{int((0.5, 0.7, 1.0)[t] * 100)}%")
                   + f"(只剩{COND_KIND_CN[wall_open]}能打)")},
        element_entry("元素滞钝"),
        element_entry("三相封界"),
        element_entry("元素禁壁"),
        element_entry("五相绝域"),
        mixed_element,
        stacked_damage,
        stacked_debuff,
        # 玻璃深渊:攻击爆表但血量减半,速杀或被杀
        atk_curse_entry("玻璃深渊", t),
        # 深渊法阵:克隆 boss 追加官方场程序(领域/淹水/结界,详见 FIELD_MENU)。
        # 2026-07-20 真机验证通过(白虎战「连击加成领域效果发动」)。
        # ⚠「乱流机关」已除名:c36/37 只是预载清单不控板子渲染皮肤(真机 falsified),
        # 无板子地形又缺锚点——两个卖点全死,勿复活。
        {"name": "深渊法阵", "caster": fm, "text": f"{fm[0]}·{fm[2]}"},
    ]


def apply_picks(out: dict, picks: list[dict], combo: str | None = None) -> dict:
    """把一组诅咒条目合成效果包。**降档闸改了 picks 之后重算走同一条路**,
    保证 hp/atk/conds/desc 永远与 picks 一致(不会出现"文案写×2.6、落表 1.4")。"""
    why = curse_conflict(picks)
    if why:
        raise ValueError(f"诅咒效果包未过组合门禁:{why}")
    profile = out.get("capability_profile")
    if isinstance(profile, dict):
        blocked = [
            (str(card.get("name") or "(unnamed)"), curse_capability_block(
                card, profile))
            for card in picks
            if curse_capability_block(card, profile) is not None
        ]
        if blocked:
            raise ValueError(
                "诅咒条目越过能力矩阵:"
                + ";".join(f"{name}->{reason}" for name, reason in blocked))
    out.update({"conds": [], "damage_resistance": [], "element_resistance": [],
                "stacked_resistance": [],
                "hp": 1.0, "atk": 1.0, "tp": None, "fever": None,
                "time": None, "gimmick": False, "caster": None, "casters": [],
                "picks": picks, "combo": combo})
    names = []
    caster_ids: set[str] = set()
    for c in picks:
        out["hp"] *= c.get("hp", 1.0)
        out["atk"] *= c.get("atk", 1.0)
        out["gimmick"] = out["gimmick"] or c.get("gimmick", False)
        caster = c.get("caster")
        if caster:
            program = str(caster[1])
            if program not in caster_ids:
                caster_ids.add(program)
                out["casters"].append(caster)
        if "tp" in c:
            out["tp"] = max(out["tp"] or 0, c["tp"])
        if "fever" in c:
            out["fever"] = max(out["fever"] or 0, c["fever"])
        if "time" in c:
            out["time"] = min(out["time"] or 10 ** 9, c["time"])
        names.append(f"「{c['name']}」{c['text']}")
    out["conds"] = merge_conds(picks)[:5]
    out["damage_resistance"] = _merged_resistance(picks, "damage_resistance")
    out["element_resistance"] = _merged_resistance(picks, "element_resistance")
    out["stacked_resistance"] = _merged_stacked_resistance(picks)
    out["used_capabilities"] = sorted(set().union(*(
        curse_card_capability_requirements(card) for card in picks
    ))) if picks else []
    out["caster"] = out["casters"][0] if out["casters"] else None  # 旧调用方兼容视图
    out["desc"] = (f"【{combo}】" if combo else "") + " ".join(names)
    return out


def downgrade_atk_curse(curse: dict) -> str | None:
    """把该层的攻击类诅咒降一档；最低档只摘攻击组件,HP 组件原样保留。

    分位硬闸的**唯一收敛手段**:每调用一次 atk 严格下降,最多 4 步(2→1→0→摘)
    就回到无攻击诅咒的裸曲线,故循环必然终止。"""
    picks = list(curse.get("picks") or [])
    i = next((i for i, c in enumerate(picks)
              if c.get("name") in ATK_CURSE_TIERS and "atk_tier" in c), None)
    if i is None:
        return None
    c = picks[i]
    t = int(c.get("atk_tier", 0))
    if t > 0:
        picks[i] = atk_curse_entry(c["name"], t - 1, int(c.get("weak", 0)))
        note = f"「{c['name']}」×{c['atk']}→×{picks[i]['atk']}"
        combo = curse.get("combo")
    else:
        hp_mult = float(c.get("hp", 1.0))
        if abs(hp_mult - 1.0) > 1e-12:
            # 攻击与血量是同一条诅咒的两个组件。分位闸只获准摘攻击；留下显式、
            # 可重算的 HP 残响条目,避免 apply_picks 把 0.5/0.85 重置成 1.0。
            pct = int(round(abs(1.0 - hp_mult) * 100))
            direction = "-" if hp_mult < 1.0 else "+"
            picks[i] = {"name": f"{c['name']}·残响", "hp": hp_mult,
                        "text": f"敌血{direction}{pct}%（攻击增幅已摘）"}
        else:
            picks.pop(i)
        note = f"摘除「{c['name']}」攻击组件"
        # 组合的承诺(【速攻】=敌攻爆表+限时)已经不成立,标签一并摘掉,别骗玩家
        combo = None
    hp_before = float(curse.get("hp", 1.0))
    apply_picks(curse, picks, combo)
    if not math.isclose(float(curse["hp"]), hp_before, rel_tol=0.0, abs_tol=1e-12):
        raise AssertionError(f"降档误改血量乘数:{hp_before}→{curse['hp']}")
    if t == 0:
        # dry-run 的分位闸日志直接留下同 seed 的前后不变量证据，不只靠测试内断言。
        note += f"（血量×{fmt(hp_before)}保持）"
    return note


def is_deep_round(r: int, n: int) -> bool:
    """最后 20%（30 层塔即第 25~30 战）。"""
    if n <= 0 or not 1 <= r <= n:
        raise ValueError(f"轮次越界:r={r},n={n}")
    return r / n > 0.8


def element_curse_names_for_depth(r: int, n: int,
                                  tier: str = "hell") -> set[str]:
    """属性耐性族随机候选：浅层低阻、深层高阻；显式钉选不走这道软筛选。

    30 层 hell 对应 1~6 滞钝、7~15 滞钝/三相、16~24 三相/禁壁、
    25~30 禁壁/五相。standard 最高滞钝，abyss 最高三相。
    """
    if n <= 0 or not 1 <= r <= n:
        raise ValueError(f"轮次越界:r={r},n={n}")
    d = r / n
    stage = 0 if d <= 0.2 else (1 if d <= 0.5 else (2 if d <= 0.8 else 3))
    cap = {"standard": 0, "abyss": 1, "hell": 3}.get(tier, 0)
    stage = min(stage, cap)
    return (
        {"元素滞钝"},
        {"元素滞钝", "三相封界"},
        {"三相封界", "元素禁壁"},
        {"元素禁壁", "五相绝域"},
    )[stage] | {MIXED_ELEMENT_CURSE_NAME}


def hell_curse_slots(r: int, n: int) -> int:
    """烈狱诅咒名额：≤20% 1、≤50% 2、其余 3，最后 20% 4。"""
    if is_deep_round(r, n):
        return 4
    d = r / n
    return 1 if d <= 0.2 else (2 if d <= 0.5 else 3)


def required_field_slots(r: int, n: int) -> int:
    """领域保底：过半程 1 个；未证明调度闭包前同一时刻只挂一个。"""
    return 1 if r / n > 0.5 else 0


BLOOD_WALL_NAME = "血肉高墙"
BLOOD_WALL_DEEP_WINDOW = 6
BLOOD_WALL_DEEP_MAX = 2
CURSE_DIVERSITY_SCHEMA = "wf-rogue-curse-diversity/v1"
CURSE_RANDOM_FREQUENCY_CAP = 0.35
DEEP_ARMOR_RANDOM_FREQUENCY_CAP = 0.15
FIELD_RANDOM_FREQUENCY_CAP = 0.35


