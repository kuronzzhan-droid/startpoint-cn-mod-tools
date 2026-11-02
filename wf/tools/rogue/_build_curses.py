# Source section of rogue_build; loaded in its shared module namespace.
def new_curse_diversity_state() -> dict:
    """Mutable per-build counters; callers serialize only the receipt copy."""

    return {
        "schema": CURSE_DIVERSITY_SCHEMA,
        "eligible": {}, "selected": {}, "last_names": [],
        "field_eligible": {}, "field_selected": {}, "last_fields": [],
        "rounds": [],
    }


def curse_diversity_receipt(state: dict) -> dict:
    """Return deterministic legal-opportunity/appearance counters."""

    if not isinstance(state, dict) or state.get("schema") != CURSE_DIVERSITY_SCHEMA:
        raise ValueError("诅咒多样性状态 schema 非法")
    return {
        "schema": CURSE_DIVERSITY_SCHEMA,
        "eligible": dict(sorted((state.get("eligible") or {}).items())),
        "selected": dict(sorted((state.get("selected") or {}).items())),
        "selection_gate_selected": dict(sorted(
            (state.get("selection_gate_selected")
             or state.get("selected") or {}).items())),
        "field_eligible": dict(sorted(
            (state.get("field_eligible") or {}).items())),
        "field_selected": dict(sorted(
            (state.get("field_selected") or {}).items())),
        "rounds": copy.deepcopy(state.get("rounds") or []),
        "frequency_caps": {
            "default": CURSE_RANDOM_FREQUENCY_CAP,
            "深渊重甲": DEEP_ARMOR_RANDOM_FREQUENCY_CAP,
            "field_program": FIELD_RANDOM_FREQUENCY_CAP,
        },
        "adjacent_cooldown": "strict_for_deep_armor_and_fields",
        "combo_uses_same_gate": True,
        "static_verified": True,
        "runtime_simulated": False,
        "gameplay_verified": False,
    }


def reconcile_curse_diversity_state(state: dict, floor_records) -> None:
    """Rebase diversity counters onto final post-band-gate curse picks.

    ``enforce_atk_band`` may lower or remove attack cards after every floor has
    already been selected.  The legal-opportunity counters stay valid, but the
    selected names/combo labels must come from those final picks or the audit
    can describe a pre-downgrade curse that is no longer present in the quest.
    """

    if not isinstance(state, dict) or state.get("schema") != CURSE_DIVERSITY_SCHEMA:
        raise ValueError("诅咒多样性状态 schema 非法")
    records = {int(record["r"]): record for record in floor_records or ()}
    state["selection_gate_selected"] = dict(state.get("selected") or {})
    selected: Counter = Counter()
    field_selected: Counter = Counter()
    rows = state.get("rounds")
    if not isinstance(rows, list):
        raise ValueError("诅咒多样性状态 rounds 非法")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("诅咒多样性状态含非对象 round")
        round_no = int(row.get("round") or 0)
        record = records.get(round_no)
        if record is None:
            raise ValueError(f"诅咒多样性状态缺最终楼层:{round_no}")
        curse = record.get("curse") or {}
        picks = list(curse.get("picks") or ())
        names = sorted({str(card["name"]) for card in picks
                        if card.get("name") and not card.get("caster")})
        fields = sorted({str(card["caster"][1]) for card in picks
                         if card.get("caster")})
        if len(fields) > 1:
            raise ValueError(f"第{round_no}战最终仍有多个领域程序")
        row["selected_names"] = names
        row["selected_field_programs"] = fields
        row["combo"] = curse.get("combo")
        selected.update(names)
        field_selected.update(fields)
    state["selected"] = dict(selected)
    state["field_selected"] = dict(field_selected)
    final_row = rows[-1] if rows else {}
    state["last_names"] = list(final_row.get("selected_names") or ())
    state["last_fields"] = list(final_row.get("selected_field_programs") or ())


def curse_pacing_blocks(r: int, n: int, history,
                        tier: str = "hell") -> dict[str, str]:
    """随机诅咒的节奏软闸；返回本层不得随机命中的名称→原因。

    工坊显式钉选不走这道软闸，但钉选结果仍会进入 history，影响后续随机层。
    最后 20% 以六层窗口最多两次高墙，且全塔不允许随机连续高墙。
    """
    if tier != "hell":
        return {}
    if n <= 0 or not 1 <= r <= n:
        raise ValueError(f"轮次越界:r={r},n={n}")
    history = [set(map(str, names or ())) for names in (history or ())]
    if len(history) > r - 1:
        raise ValueError(f"诅咒历史长于已完成楼层:{len(history)}>{r - 1}")
    reasons: list[str] = []
    if history and BLOOD_WALL_NAME in history[-1]:
        reasons.append("上一层已有血肉高墙，禁止连续")
    if is_deep_round(r, n):
        deep_start = math.floor(n * 0.8) + 1
        window_start = max(deep_start, r - BLOOD_WALL_DEEP_WINDOW + 1)
        history_start = r - len(history)
        recent = sum(
            BLOOD_WALL_NAME in names
            for round_no, names in enumerate(history, start=history_start)
            if window_start <= round_no < r
        )
        if recent >= BLOOD_WALL_DEEP_MAX:
            reasons.append(
                f"深层{BLOOD_WALL_DEEP_WINDOW}层窗口已有{recent}次，"
                f"上限{BLOOD_WALL_DEEP_MAX}次")
    return ({BLOOD_WALL_NAME: "；".join(reasons)} if reasons else {})


def _has_dragon_heart(picks: list[dict]) -> bool:
    return any(str(constructor) == "ACToleranceOfDebuff"
               for pick in picks
               for constructor, _strength, _layers in
               pick.get("stacked_resistance", []))


def _safe_non_boon_fields(picks: list[dict], menu) -> list[tuple]:
    used = {str(pick["caster"][1]) for pick in picks if pick.get("caster")}
    unique: dict[str, tuple] = {}
    for item in menu:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        category = item[3] if len(item) > 3 else "领域"
        program = str(item[1])
        if (category == "加成" or category not in FIELD_RANDOM_CATS
                or program in used):
            continue
        unique.setdefault(program, tuple(item))
    return list(unique.values())


def dragon_heart_companion_block(picks: list[dict], can_carry: bool,
                                 menu) -> str | None:
    """不屈龙心在 finalize 前的可实现性预检，供 redraw 路径记录原因。"""
    if not _has_dragon_heart(picks):
        return None
    if not can_carry:
        return "不屈龙心缺少 general_boss c109 载体"
    fields = [pick for pick in picks if pick.get("caster")]
    if any((pick["caster"][3] if len(pick["caster"]) > 3 else "领域") != "加成"
           for pick in fields):
        return None
    if not _safe_non_boon_fields(picks, menu):
        return "不屈龙心非加成可见领域候选耗尽"
    return None


def ensure_dragon_heart_companion(picks: list[dict], rng, can_carry: bool,
                                  menu) -> list[dict]:
    """为不屈龙心保底一个对普通队伍可见的非“加成”场机制。

    已有非加成 field 时复用；只有加成 field 时原位替换一个；无 field
    时追加恰好一个，不占普通诅咒名额。可行性问题必须在正常抽取时
    由 `dragon_heart_companion_block` 转成 log+redraw；直接调用则响亮失败。
    """
    picks = list(picks)
    why = dragon_heart_companion_block(picks, can_carry, menu)
    if why:
        raise RuntimeError(why)
    if not _has_dragon_heart(picks):
        return picks
    fields = [(i, pick) for i, pick in enumerate(picks) if pick.get("caster")]
    if any((pick["caster"][3] if len(pick["caster"]) > 3 else "领域") != "加成"
           for _i, pick in fields):
        return picks
    candidates = _safe_non_boon_fields(picks, menu)
    chosen = candidates[rng.randrange(len(candidates))]
    companion = {"name": "深渊法阵", "caster": chosen,
                 "text": f"{chosen[0]}·{chosen[2]}"}
    if fields:
        picks[fields[0][0]] = companion
    else:
        picks.append(companion)
    return picks


def abyss_curses(r: int, n: int, rng, tier: str, caps: dict | None = None,
                 forced: dict | None = None, no_base: bool = False, *,
                 baseline_c86: float | None = None,
                  c86_limits: tuple[float, float] | None = None,
                  baseline_dps: float | None = None,
                  base_duration_s: float | None = None,
                  hp_channel: str = "c86",
                  high_threat: bool = False,
                  forbid_hp_curses: bool = False,
                  capability_profile: dict | None = None,
                  random_forbidden: dict[str, str] | None = None,
                  diversity_state: dict | None = None) -> dict:
    """轮次诅咒包:{conds,hp,atk,tp,fever,time,gimmick,caster,desc,picks,combo}。

    caps = 地形能力 {"spawn": 有SPAWNn锚点, "panel": 官方板子配对地形}——
    祭坛/板子诅咒只在能生效的地形掉落(2026-07-20 真机实证:歼灭者类 boss 擂台
    只有 FUNNEL_SPAWN 锚点,zone-zako 出生静默失败)。
    no_base = 该层 boss 查不到基数(standard 表)→ 归一化不生效、真实伤害无上界
    保证,**禁掉攻击类诅咒**(2026-07-30 伤害审计:第15/18/26/29/30 战都是这种)。
    """
    out = {"conds": [], "damage_resistance": [], "element_resistance": [],
           "stacked_resistance": [],
           "hp": 1.0, "atk": 1.0, "tp": None, "fever": None,
           "time": None, "gimmick": False, "caster": None, "casters": [], "desc": "",
           "field_requested": 0, "field_applied": 0, "field_deficit": 0,
           "field_deficit_reason": None,
           "picks": [], "combo": None}
    caps = dict(caps or {})
    if capability_profile is None:
        # Public/test callers historically passed only caps. Keep that API,
        # but route it through the same declared general row as production.
        capability_profile = resolve_curse_capabilities(
            "boss_level", "general", caps, no_base=no_base)
    else:
        capability_profile = copy.deepcopy(capability_profile)
    if capability_profile.get("schema") != CURSE_CAPABILITY_SCHEMA:
        raise ValueError("诅咒能力矩阵 profile schema 非法")
    declared = capability_profile.get("declared")
    effective = capability_profile.get("effective")
    if (not isinstance(declared, dict) or not isinstance(effective, dict)
            or any(declared.get(axis) not in {True, False}
                   or effective.get(axis) not in {True, False}
                   for axis in CURSE_CAPABILITY_AXES)
            or any(effective[axis] and not declared[axis]
                   for axis in CURSE_CAPABILITY_AXES)):
        raise ValueError("诅咒能力矩阵 profile 能力轴非法")
    if forbid_hp_curses:
        # Compatibility only. Production resolves Sphere from the explicit
        # family row and never sets this legacy switch.
        effective["hp_multiplier"] = False
        restrictions = list(capability_profile.get("restrictions") or ())
        restrictions.append("legacy_forbid_hp_curses")
        capability_profile["restrictions"] = list(dict.fromkeys(restrictions))
    out["capability_profile"] = capability_profile
    out["used_capabilities"] = []
    has_forced = bool(forced and (forced.get("curses") or forced.get("field")))
    forced_names = list((forced or {}).get("curses") or [])
    has_element_mix = bool(forced is not None and "element_mix" in forced
                           and forced.get("element_mix") is not None)
    if has_element_mix and MIXED_ELEMENT_CURSE_NAME not in forced_names:
        raise ValueError("element_mix 只能与工坊钉选「混相禁域」同时提供")
    if tier == "off" and not has_forced:
        return out
    t = CURSE_TIERS.index(tier) if tier in CURSE_TIERS else 1
    d = r / n
    # 诅咒名额。**全塔烈狱**(2026-07-29 用户主推)时没有白板层:最浅也给 1 个,
    # 30% 起 2 个,60% 起 3 个(3 是条件槽能装下的上限,见 curse_conflict)。
    # 其余档位维持原节奏:≤15% 白板 / ≤45% 1 个 / 其余 2 个。
    if tier == "hell":
        count = hell_curse_slots(r, n)
    else:
        if d <= 0.15 and not has_forced:
            return out
        count = 1 if d <= 0.45 else 2
    field_requested = required_field_slots(r, n) if tier == "hell" else 0
    raw_pool = _curse_pool(
        t, rng, stack_layers=stacked_resistance_layers_for_depth(r, n),
        mixed_strengths=element_strengths_for_depth(r, n),
        forced_element_mix=((forced or {}).get("element_mix")
                            if has_element_mix else None))
    safe_pool = list(raw_pool)
    if BUILD_MODE == "legacy" and is_deep_round(r, n):
        # 深层血量锚已到多人决战量级；180/240 秒会把需求 DPS 再抬 3.75~5×。
        # 随机、组合、工坊强制三条路共用同一份过滤，后面 finalize 还有最终断言。
        safe_pool = [c for c in safe_pool if "time" not in c]
    blocked_cards = [
        (card, curse_capability_block(card, capability_profile))
        for card in safe_pool
    ]
    blocked_by_axis: dict[str, list[str]] = {}
    for card, block in blocked_cards:
        for axis in str(block or "").split(","):
            if axis:
                blocked_by_axis.setdefault(axis, []).append(str(card["name"]))
    for axis, names in blocked_by_axis.items():
        log(f"[curse] round={r} capability-block={axis} "
            f"family={capability_profile['family']} cards="
            f"{','.join(names)}; redraw")
    safe_pool = [card for card, block in blocked_cards if block is None]
    if effective["hard_element_resistance"]:
        # 软通道词条是专为没有属性硬通道的专场补池；普通 general Boss 继续使用
        # 更丰富的属性/动作硬通道，避免把补池反过来稀释其特色。
        safe_pool = [c for c in safe_pool if not c.get("soft_channel_fallback")]
    if high_threat:
        # 时限/高档属性墙是单条即可判定的硬禁项；HP 上限必须等组合后按净乘数判，
        # 不能在这里错杀 2.5×0.5=1.25 这类合法搭配。
        safe_pool = [c for c in safe_pool
                     if c.get("time") is None
                     and not any(float(value) >= ELEMENT_LOCK_THRESHOLD - 1e-12
                                 for value in _resistance_totals_by_target(
                                     [c], "element_resistance").values())]
    # 深度只是随机排程软约束。工坊钉选从 safe_pool 查名，仍必须通过载体/c36/
    # 可解性硬闸；随机、组合与 redraw 补位只从按层过滤后的 pool 取。
    allowed_elements = element_curse_names_for_depth(r, n, tier)
    pool = [c for c in safe_pool
            if c["name"] not in ELEMENT_CURSE_NAMES or c["name"] in allowed_elements]
    if not is_deep_round(r, n):
        # 一次性高 r 是硬墙；随机排程只在最后20%与可见叠层混用。
        # 工坊钉选仍从 safe_pool 取，保留显式越档能力（高威胁硬闸除外）。
        pool = [c for c in pool if c["name"] not in HIGH_ONE_SHOT_CURSE_NAMES]
    random_forbidden = {str(name): str(reason)
                        for name, reason in (random_forbidden or {}).items()}
    for name, reason in random_forbidden.items():
        if any(c.get("name") == name for c in pool):
            log(f"[curse] round={r} pace-block=「{name}」 reason={reason}; redraw")
    pool = [c for c in pool if c.get("name") not in random_forbidden]
    diversity_enabled = diversity_state is not None and not has_forced
    if diversity_state is not None and (
            not isinstance(diversity_state, dict)
            or diversity_state.get("schema") != CURSE_DIVERSITY_SCHEMA):
        raise ValueError("诅咒多样性状态 schema 非法")

    field_menu_candidates = list({str(item[1]): tuple(item)
                                  for item in field_menu_all()
                                  if (item[3] if len(item) > 3 else "领域")
                                  in FIELD_RANDOM_CATS}.values())
    diversity_blocks: dict[str, str] = {}
    if diversity_enabled:
        eligible = diversity_state.setdefault("eligible", {})
        selected = diversity_state.setdefault("selected", {})
        last_names = set(map(str, diversity_state.get("last_names") or ()))
        eligible_names = sorted({str(card["name"]) for card in pool
                                 if not card.get("caster")})
        for name in eligible_names:
            eligible[name] = int(eligible.get(name, 0)) + 1
            cap = (DEEP_ARMOR_RANDOM_FREQUENCY_CAP
                   if name == "深渊重甲" else CURSE_RANDOM_FREQUENCY_CAP)
            allowed = max(1, math.ceil(float(eligible[name]) * cap - 1e-12))
            if name == "深渊重甲" and name in last_names:
                diversity_blocks[name] = "上一层已有深渊重甲，进入严格相邻冷却"
            elif int(selected.get(name, 0)) >= allowed:
                diversity_blocks[name] = (
                    f"合法机会{eligible[name]}次/已出现{selected.get(name, 0)}次，"
                    f"达到频率上限{cap:g}")
        for name, reason in diversity_blocks.items():
            if any(str(card.get("name")) == name for card in pool):
                log(f"[curse] round={r} diversity-block=「{name}」 "
                    f"reason={reason}; redraw")
        pool = [card for card in pool
                if str(card.get("name")) not in diversity_blocks]

        field_eligible = diversity_state.setdefault("field_eligible", {})
        field_selected = diversity_state.setdefault("field_selected", {})
        last_fields = set(map(str, diversity_state.get("last_fields") or ()))
        allowed_fields = []
        for item in field_menu_candidates:
            program = str(item[1])
            field_eligible[program] = int(field_eligible.get(program, 0)) + 1
            allowed = max(1, math.ceil(
                float(field_eligible[program]) * FIELD_RANDOM_FREQUENCY_CAP
                - 1e-12))
            if program in last_fields or int(field_selected.get(program, 0)) >= allowed:
                continue
            allowed_fields.append(item)
        if allowed_fields:
            field_menu_candidates = allowed_fields
        pool = [card for card in pool if not card.get("caster")]
        pool.extend({
            "name": "深渊法阵", "caster": item,
            "text": f"{item[0]}·{item[2]}",
        } for item in field_menu_candidates)
    runtime_args = (baseline_c86, c86_limits, baseline_dps, base_duration_s)
    if any(v is not None for v in runtime_args) and not all(v is not None for v in runtime_args):
        raise ValueError(f"第{r}战诅咒数值门禁参数必须成套提供")

    def conflict(picks: list[dict]) -> str | None:
        why = curse_conflict(picks)
        if not why and high_threat:
            why = high_threat_curse_conflict(picks)
        if not why:
            why = dragon_heart_companion_block(
                picks, bool(effective["stacked_resistance"]
                            and effective["field_action"]),
                field_menu_candidates)
        if why or baseline_c86 is None:
            return why
        return curse_runtime_conflict(
            picks, baseline_c86=float(baseline_c86),
            c86_limits=c86_limits, baseline_dps=float(baseline_dps),
            base_duration_s=float(base_duration_s), hp_channel=hp_channel)

    def pick_key(c: dict):
        caster = c.get("caster")
        return ("field", str(caster[1])) if caster else ("curse", c.get("name"))

    def new_field_entries(current: list[dict], needed: int) -> list[dict]:
        """从多样性门禁后的安全菜单抽程序；当前静态闭包最多允许一个。"""
        used = {str(c["caster"][1]) for c in current if c.get("caster")}
        menu = [m for m in field_menu_candidates if str(m[1]) not in used]
        unique = {}
        for item in menu:
            unique.setdefault(str(item[1]), item)
        order = list(unique.values())
        if diversity_enabled:
            field_eligible = diversity_state.get("field_eligible") or {}
            field_selected = diversity_state.get("field_selected") or {}
            order.sort(key=lambda item: (
                float(field_selected.get(str(item[1]), 0))
                / max(1, int(field_eligible.get(str(item[1]), 0))),
                rng.random()))
        elif order:
            order = rng.sample(order, len(order))
        return [{"name": "深渊法阵", "caster": fm, "text": f"{fm[0]}·{fm[2]}"}
                for fm in order[:needed]]

    def refill_picks(current: list[dict], target_count: int,
                      prefer_caster: bool = False) -> list[dict]:
        """用完整冲突闸补满名额；耗尽时硬失败，绝不把 redraw 退化成少发。"""
        current = list(current)
        atk_used = any(c.get("atk", 1.0) > 1.0 for c in current)
        if effective["field_action"] and field_requested:
            present = len({str(c["caster"][1]) for c in current if c.get("caster")})
            add = min(max(0, target_count - len(current)), max(0, field_requested - present))
            for c in new_field_entries(current, add):
                if conflict(current + [c]) is None:
                    current.append(c)
            present = len({str(c["caster"][1]) for c in current if c.get("caster")})
            if present < min(field_requested, target_count):
                raise RuntimeError(
                    f"第{r}战领域候选耗尽:{present}/{min(field_requested, target_count)}")
        if diversity_enabled:
            eligible = diversity_state.get("eligible") or {}
            selected = diversity_state.get("selected") or {}
            field_eligible = diversity_state.get("field_eligible") or {}
            field_selected = diversity_state.get("field_selected") or {}
            order = sorted(pool, key=lambda card: (
                (str(card["name"]) in set(map(
                    str, diversity_state.get("last_names") or ())))
                if not card.get("caster") else False,
                (float(field_selected.get(str(card["caster"][1]), 0))
                 / max(1, int(field_eligible.get(str(card["caster"][1]), 0))))
                if card.get("caster") else
                (float(selected.get(str(card["name"]), 0))
                 / max(1, int(eligible.get(str(card["name"]), 0)))),
                rng.random(),
            ))
        else:
            order = rng.sample(pool, len(pool))
        # 深渊法阵(场程序)出场加权(2026-07-29 用户「场地效果可以再多一点」):
        # 平权时 1/12≈8%,这里 45% 概率把它提到队首 → 实际约四成楼层带场地效果。
        if (prefer_caster and effective["field_action"]
                and rng.random() < 0.45):
            caster = next((c for c in order if c.get("caster")), None)
            if caster is not None:
                order.remove(caster)
                order.insert(0, caster)
        for c in order:
            if len(current) >= target_count:
                break
            if c.get("gimmick") and not effective["panel_gimmick"]:
                continue
            if c.get("caster") and not effective["field_action"]:
                continue
            # 中后段保底已经填到目标数后，不再随机塞第 3 个领域；前段仍保留旧的
            # 45% 随机法阵手感。去重按 program ID，不按统一显示名“深渊法阵”。
            if c.get("caster") and field_requested and sum(
                    bool(p.get("caster")) for p in current) >= field_requested:
                continue
            if any(pick_key(c) == pick_key(p) for p in current):
                continue
            # 保留普通随机池原有的一张属性卡节奏；独立 ban 保底在完整抽取之后
            # 追加，不消耗普通名额。显式多卡由合并后的六属性封锁门禁裁定。
            if (c.get("name") in ELEMENT_CURSE_NAMES
                    and any(p.get("name") in ELEMENT_CURSE_NAMES for p in current)):
                continue
            is_atk = c.get("atk", 1.0) > 1.0
            if is_atk and atk_used:
                continue
            why = conflict(current + [c])
            if why:
                log(f"[curse] round={r} reject=「{c['name']}」"
                    f" with={','.join(p['name'] for p in current) or '(none)'}"
                    f" reason={why}; redraw")
                continue
            current.append(c)
            atk_used = atk_used or is_atk
        if len(current) < target_count:
            # “拒绝并重抽”不能退化成少发几条的静默截断；候选耗尽说明池/冲突规则坏了。
            raise RuntimeError(
                f"第{r}战诅咒重抽耗尽:{len(current)}/{target_count},拒绝落表")
        return current

    def finalize(picks: list[dict], combo_name: str | None = None) -> dict:
        picks = ensure_dragon_heart_companion(
            picks, rng, bool(effective["stacked_resistance"]
                             and effective["field_action"]),
            field_menu_candidates)
        why = conflict(picks)
        if why:
            raise RuntimeError(f"第{r}战诅咒最终组合未过门禁:{why}")
        result = apply_picks(out, picks, combo_name)
        applied = len(result.get("casters") or [])
        effective_field_requested = max(
            field_requested, 1 if _has_dragon_heart(picks) else 0)
        result["field_requested"] = effective_field_requested
        result["field_applied"] = applied
        result["field_deficit"] = max(0, effective_field_requested - applied)
        if result["field_deficit"]:
            result["field_deficit_reason"] = (caps.get("carrier_reason")
                                               or caps.get("element_reason")
                                               or "没有可用的 general_boss 领域载体")
        if BUILD_MODE == "legacy" and is_deep_round(r, n) and (result.get("time") is not None
                                    or any("time" in c for c in picks)):
            raise AssertionError(f"第{r}战深层仍残留时限诅咒")
        if high_threat:
            why = high_threat_curse_conflict(picks)
            if why:
                raise AssertionError(f"第{r}战高威胁最终组合越闸:{why}")
        if diversity_state is not None:
            selected_counts = diversity_state.setdefault("selected", {})
            field_selected = diversity_state.setdefault("field_selected", {})
            chosen_names = sorted({str(card["name"]) for card in picks
                                   if not card.get("caster")})
            chosen_fields = sorted({str(card["caster"][1]) for card in picks
                                    if card.get("caster")})
            for name in chosen_names:
                selected_counts[name] = int(selected_counts.get(name, 0)) + 1
            for program in chosen_fields:
                field_selected[program] = int(field_selected.get(program, 0)) + 1
            diversity_state["last_names"] = chosen_names
            diversity_state["last_fields"] = chosen_fields
            round_receipt = {
                "round": int(r),
                "eligible_names": sorted({
                    str(card["name"]) for card in pool if not card.get("caster")}),
                "selected_names": chosen_names,
                "eligible_field_programs": sorted(
                    str(item[1]) for item in field_menu_candidates),
                "selected_field_programs": chosen_fields,
                "combo": combo_name,
                "forced": bool(has_forced),
            }
            diversity_state.setdefault("rounds", []).append(round_receipt)
            result["diversity_receipt"] = copy.deepcopy(round_receipt)
        return result

    # 显式指定(工坊拖拽):有效钉选优先；被门禁拒绝的名额随机补齐到原指定数量。
    if forced and (forced.get("curses") or forced.get("field")):
        forced_curses = list(forced.get("curses") or [])
        # 深层的“第 4 个”是硬规格，不是工坊可绕过的下限。
        # 即使计划误填 5+ 个，也只保留前四个可解条目再重抽；
        # 领域另算 2 个硬通道，不占普通诅咒名额。
        curse_target = (count if is_deep_round(r, n)
                        else max(count, len(forced_curses)))
        if is_deep_round(r, n) and len(forced_curses) > curse_target:
            for nm in forced_curses[curse_target:]:
                log(f"[curse] round={r} reject=工坊额外「{nm}」 "
                    f"reason=深层普通诅咒固定 {curse_target} 个; redraw")
            forced_curses = forced_curses[:curse_target]
        field_target = (field_requested if effective["field_action"] else 0)
        if (not field_target and forced.get("field")
                and effective["field_action"]):
            field_target = 1
        # 领域不占“第4个诅咒”的名额；深层是 4 个普通诅咒 + 2 个领域。
        target_count = curse_target + field_target
        picks = [c for nm in forced_curses
                 for c in safe_pool if c["name"] == nm and not c.get("caster")]
        for nm in forced_curses:
            if is_deep_round(r, n) and nm == "时之枷锁":
                log(f"[curse] round={r} reject=「{nm}」 reason=深层禁时限; redraw")
            if no_base and nm in ATK_CURSE_TIERS:
                print(f"[WARN] 工坊钉选第{r}战:剔除「{nm}」(该层 boss 无基数,"
                      "归一化不生效,攻击类诅咒会失控)")
            if (nm in ELEMENT_CURSE_NAMES
                    and not effective["hard_element_resistance"]):
                why = (caps.get("element_reason")
                       or ",".join(capability_profile.get("restrictions") or ())
                       or "能力矩阵没有属性硬通道")
                log(f"[curse] round={r} reject=「{nm}」 reason={why}; redraw")
            if (nm in DAMAGE_HARD_CURSE_NAMES
                    and not effective["hard_damage_resistance"]):
                log(f"[curse] round={r} reject=「{nm}」 "
                    "reason=能力矩阵没有伤害硬通道; redraw")
            if (nm in STACKED_CURSE_NAMES
                    and not effective["stacked_resistance"]):
                log(f"[curse] round={r} reject=「{nm}」 "
                    "reason=能力矩阵没有叠层硬通道; redraw")
            if high_threat:
                original = next((c for c in raw_pool if c["name"] == nm), None)
                if original:
                    # HP 只能在完整组合上判；这里仅解释为何单条硬禁项没进 safe_pool。
                    threat_probe = dict(original)
                    threat_probe.pop("hp", None)
                    why = high_threat_curse_conflict([threat_probe])
                    if why:
                        log(f"[curse] round={r} reject=「{nm}」 reason={why}; redraw")
        if forced.get("field"):
            fm_forced = next((m for m in field_menu_all() if m[1] == forced["field"]), None)
            if fm_forced and effective["field_action"]:
                picks.append({"name": "深渊法阵", "caster": fm_forced,
                              "text": f"{fm_forced[0]}·{fm_forced[2]}"})
            else:
                log(f"[curse] round={r} reject=工坊法阵「{forced['field']}」"
                    " reason=本层没有可用的 general_boss 硬通道载体; redraw")
        # 钉选也要过冲突闸:手动钉出"四系全免疫"照样是无解层,发出去就卡死玩家
        if high_threat:
            # 净 HP 乘数与输入顺序无关，但逐条 kept 检查会看到中间态；先处理减血项，
            # 让 [高墙,玻璃] 与 [玻璃,高墙] 都按最终 1.25 倍作同一裁定。
            picks = [c for _i, c in sorted(
                enumerate(picks),
                key=lambda pair: (float(pair[1].get("hp", 1.0)) > 1.0, pair[0]))]
        kept: list[dict] = []
        for c in picks:
            why = conflict(kept + [c])
            if why:
                log(f"[curse] round={r} reject=「{c['name']}」 reason={why}; redraw")
                continue
            kept.append(c)
        if effective["field_action"] and field_requested:
            max_non_fields = curse_target
            non_fields = [c for c in kept if not c.get("caster")]
            if len(non_fields) > max_non_fields:
                rejected_ids = {id(c) for c in non_fields[max_non_fields:]}
                for c in kept:
                    if id(c) in rejected_ids:
                        log(f"[curse] round={r} reject=「{c['name']}」"
                            " reason=领域保底需预留名额; redraw")
                kept = [c for c in kept if id(c) not in rejected_ids]
        # 被 c36/载体/跨诅咒冲突拒掉的名额必须真正换成别的诅咒；补不满就拒绝落表。
        return finalize(refill_picks(kept, target_count))
    # 攻击类诅咒(嗜血/逆鳞/玻璃)每轮至多 1 个——双叠=一击秒杀墙,是恶心不是大胆
    picks = []
    combo_name = None
    # 用户口径“能出属性免疫的尽量出”：只有实际 general_boss 载体已通过
    # c109/c36/引用闭包门禁才进入这里。先从本层深度允许的属性卡里随机种一张，
    # 后续组合与补位仍走同一份冲突/可解性闸；高威胁过滤和六属性出口规则不放宽。
    if (effective["hard_element_resistance"] and count > 0
            and rng.random() < ELEMENT_CURSE_PREFERENCE_RATE):
        element_order = rng.sample(
            [c for c in pool if c["name"] in ELEMENT_CURSE_NAMES],
            sum(c["name"] in ELEMENT_CURSE_NAMES for c in pool))
        for candidate in element_order:
            if conflict([candidate]) is None:
                picks = [candidate]
                log(f"[curse] round={r} prefer=属性耐性 「{candidate['name']}」")
                break
    # ---- 先试组合(2026-07-29):名额 ≥2 时 55% 概率整套落地,剩余名额再独立随机补 ----
    if count - len(picks) >= 2 and rng.random() < COMBO_RATE:
        cands = [cb_ for cb_ in CURSE_COMBOS
                 if len(cb_["curses"]) <= count - len(picks)]
        if effective["hard_element_resistance"]:
            cands = [cb_ for cb_ in cands if not cb_.get("soft_fallback")]
        if is_deep_round(r, n):
            cands = [cb_ for cb_ in cands if "时之枷锁" not in cb_["curses"]]
        # 需要 boss 载体的组合(带深渊法阵)在 standard/专用表 boss 层落不上,先剔掉
        if not effective["field_action"]:
            cands = [cb_ for cb_ in cands if "深渊法阵" not in cb_["curses"]]
        while cands:
            cb_ = cands.pop(rng.randrange(len(cands)))
            got = []
            for nm in cb_["curses"]:
                if nm == "深渊法阵":
                    sub = [m for m in field_menu_candidates
                           if (m[3] if len(m) > 3 else "领域") == cb_.get("field_cat")]
                    sub = sub or list(field_menu_candidates)
                    fm2 = sub[rng.randrange(len(sub))]
                    got.append({"name": "深渊法阵", "caster": fm2,
                                "text": f"{fm2[0]}·{fm2[2]}"})
                else:
                    c = next((x for x in pool if x["name"] == nm), None)
                    if c:
                        got.append(c)
            complete = len(got) == len(cb_["curses"])
            why = conflict(picks + got) if complete else None
            if len(got) == len(cb_["curses"]) and not why:
                picks.extend(got)
                combo_name = cb_["name"]
                break
            if why:
                log(f"[curse] round={r} reject=【{cb_['name']}】"
                    f"({','.join(c['name'] for c in got)}) reason={why}; redraw")
    total_count = count + (field_requested if effective["field_action"] else 0)
    return finalize(refill_picks(picks, total_count, prefer_caster=True), combo_name)


def _leaf_rows(node):
    """任意深度嵌套表 → 逐个 leaf CSV 行。"""
    if isinstance(node, dict):
        for v in node.values():
            yield from _leaf_rows(v)
    else:
        s = node.decode("utf-8") if isinstance(node, bytes) else node
        for ln in s.split("\n"):
            if ln.strip():
                yield ln


# 直引 field 的源表 → battle_recommended_element 列位(0-based 元素枚举)
# 2026-07-29 补全:以前只登记 5 张表,而 src 池里的 world_story/story_event 以及
# 本次新增的 6 类都没登记 → c69 落到"随机元素",正是 C8016 的触发路径。
# 列位测绘法:先找该表的 field 列号,元素列 = field 列 − 固定偏移,偏移只有两族
# (长行 37 / 短行 29,ranking 是唯一的 24);逐表用"全行取值必须落在 0-6"验证,
# 并抽样对过语义(闪火试炼=火、haniwa_carnival_water=水、寄居蟹船长=水)。
# ⚠ score_attack/practice 三个偏移都能过 0-6 校验但语义互相矛盾,没有确证前
#   不登记(它们也不在 src 池里);登记错列比不登记更危险。
_ELEM_COL = {
    "master/quest/boss_battle_quest.orderedmap": 72,
    "master/quest/main_quest.orderedmap": 72,
    "master/quest/event/hard_multi_event_quest.orderedmap": 73,
    "master/quest/event/advent_event_quest.orderedmap": 78,
    "master/quest/event/raid_event_quest.orderedmap": 70,
    "master/quest/event/world_story_event_quest.orderedmap": 73,
    "master/quest/event/world_story_event_boss_battle_quest.orderedmap": 72,
    "master/quest/event/story_event_single_quest.orderedmap": 74,
    "master/quest/event/expert_single_event_quest.orderedmap": 75,
    "master/quest/event/solo_time_attack_event_quest.orderedmap": 72,
    "master/quest/event/ranking_event_single_quest.orderedmap": 68,
    "master/quest/event/carnival_event_quest.orderedmap": 69,
}


def field_official_elem_map() -> dict[str, int]:
    """field_data id → 官方源 quest 的 battle_recommended_element。

    塔层/挑战层经 floor 表间接(宿主表元素列 70/73,floor 键列 99/110);
    直引 field 的表按 _ELEM_COL 扫行、按 field_data 键匹配单元格。
    """
    fd_keys = set(_tbl("master/battle/field_data.orderedmap").keys())
    out: dict[str, int] = {}

    floor = q.load_table("master/battle/floor.orderedmap")
    fkey_fields: dict[str, list[str]] = {}
    for k, v in floor.items():
        if isinstance(v, dict):
            continue
        s = v.decode("utf-8") if isinstance(v, bytes) else v
        fkey_fields[k] = [cb._cols(ln)[0] for ln in s.split("\n")
                          if cb._cols(ln) and cb._cols(ln)[0] not in ("", "(None)")]
    for logical, elem_col, floor_col in [
        ("master/quest/event/tower_dungeon_event_quest.orderedmap", 70, 99),
        ("master/quest/event/challenge_dungeon_event_quest.orderedmap", 73, 110),
    ]:
        try:
            table = q.load_table(logical)
        except Exception:
            continue
        for ln in _leaf_rows(table):
            row = cb._cols(ln)
            if len(row) <= max(elem_col, floor_col):
                continue
            fkey, ev = row[floor_col], row[elem_col]
            if fkey in ("", "(None)") or ev not in ("0", "1", "2", "3", "4", "5", "6"):
                continue
            for field in fkey_fields.get(fkey, []):
                out.setdefault(field, int(ev))

    for logical, elem_col in _ELEM_COL.items():
        try:
            table = q.load_table(logical)
        except Exception:
            continue
        for ln in _leaf_rows(table):
            row = cb._cols(ln)
            if len(row) <= elem_col:
                continue
            ev = row[elem_col]
            if ev not in ("0", "1", "2", "3", "4", "5", "6"):
                continue
            field = next((x for x in row if x in fd_keys), "")
            if field:
                out.setdefault(field, int(ev))
    return out


# ---- 元素变体系列(2026-07-29 用户需求「XX系列收到一起」)----
# 这几族的六元素变体招式完全相同,只有属性/换色不同 —— 一座塔出两个就是重复内容
# (实测 1.4.237 同塔出了雷龟+暗凤两只精灵兽、1.4.236 出了苍机兵+闪机兵)。
# 归并成一个去重键后,全塔按 SERIES_CAPS 配额限次(不是只出一次,见 series_cap)。
#
# ⚠ 为什么用**显式名单**而不是"从模型名里剥元素词":
#   ① 要合并的这几族,元素在**目录名**里(battle/boss/spirit_beast_fire/…),
#      所以模型名天然带元素 → 现状各自成键;
#   ② 八岐大蛇正相反,模型名本来就是 `orochi`(元素/头在**文件名**里),各头靠
#      progs 签名区分 —— 剥元素词对它无效,但通用规则容易误伤,显式名单最可控;
#   ③ 机兵/女王/废龙的多数变体在 standard_boss(无模型路径、boss_names 也查不到名),
#      `_model_and_progs` 回落到"代号即模型",元素同样在代号里。
# ⚠ 机工神兵菲诺梅那(steampunk_another)排除在外:它是决战级独立 boss(塔腰常驻位),
#   跟六元素机兵不是一回事,并进去会让常驻位和机兵锚位互相顶掉。
BOSS_SERIES = (
    ("精灵兽", "spirit_beast", ()),
    ("女王", "variant_empress", ()),
    ("荒龙", "discarded_dragon", ()),
    ("机兵", "steampunk", ("steampunk_another",)),
)

# 每系列在**一座 30 层塔**里允许出现几次(2026-07-29 用户指定:女王2/机兵3/精灵兽2;
# 荒龙没点名,跟女王/精灵兽同档给 2)。别的 boss 一律 1 次。
# 「都可以根据层数动态调整」⇒ 实际配额按层数线性缩放,见 series_cap()。
SERIES_CAPS = {"精灵兽": 2, "女王": 2, "荒龙": 2, "机兵": 3}
SERIES_CAP_BASE_ROUNDS = 30


def series_cap(series: str, rounds: int) -> int:
    """系列在 rounds 层塔里的出场配额(以 30 层为基准线性缩放,至少 1)。

    30 层 = 用户给的原始数(女王2/机兵3/精灵兽2/荒龙2);
    15 层减半(机兵 2、其余 1),60 层翻倍(机兵 6、其余 4)。
    """
    base = SERIES_CAPS.get(series, 1)
    return max(1, round(base * rounds / SERIES_CAP_BASE_ROUNDS))


def boss_series_of(code: str, model: str = "") -> str | None:
    """boss 代号/模型 → 所属元素变体系列名;不属于任何系列返回 None。"""
    for name, prefix, excludes in BOSS_SERIES:
        if any(str(code).startswith(x) for x in excludes):
            continue
        if str(code).startswith(prefix) or str(model).startswith(prefix):
            return name
    return None


THUMBNAIL_EVIDENCE_SCHEMA = "wf-rogue-thumbnail-evidence/v1"


def quest_thumbnail_asset_logical(thumbnail: str) -> str:
    """Return the client logical PNG path for a rush quest c5 value."""
    value = str(thumbnail or "").strip()
    return value if value.endswith(".png") else value + ".png"


def boss_cover_visual_identity_map(
        general_boss: dict | None = None, standard_boss: dict | None = None,
        names: dict[str, str] | None = None) -> dict[str, str]:
    """Boss code → stable visual identity used only for quest-cover matching.

    Single/multi/tower/difficulty aliases often use different master IDs while
    sharing the same displayed Boss and model.  A cover describes that visual
    identity, not its balance/action variant.  Combining the official display
    name with the model root avoids merging theme variants which only share a
    base model, such as the two Hermit Crab families.
    """
    gb = _tbl(GENERAL_BOSS) if general_boss is None else general_boss
    sb = _tbl(STANDARD_BOSS) if standard_boss is None else standard_boss
    display_names = wb.boss_names() if names is None else names

    def leaves(node):
        if isinstance(node, dict):
            for child in node.values():
                yield from leaves(child)
        elif isinstance(node, (str, bytes, bytearray)):
            yield (node.decode("utf-8", "replace")
                   if isinstance(node, (bytes, bytearray)) else node)

    out: dict[str, str] = {}
    for code in sorted(set(gb) | set(sb)):
        node = gb.get(code) if code in gb else sb.get(code)
        models: set[str] = set()
        for leaf in leaves(node):
            for line in leaf.splitlines() or (leaf,):
                try:
                    values = cells(line)
                except (TypeError, ValueError, csv.Error, StopIteration):
                    continue
                for value in values:
                    if (value.startswith("battle/boss/")
                            and "general_16dots" not in value):
                        parts = value.split("/")
                        if len(parts) > 2:
                            models.add("/".join(parts[:3]))
                    elif value.startswith("battle/enemy/boss/"):
                        parts = value.split("/")
                        if len(parts) > 3:
                            models.add("/".join(parts[:4]).split("$")[0])
        display = str(display_names.get(code) or "").strip()
        model = "|".join(sorted(models))
        out[str(code)] = f"{display}\0{model}" if display or model else str(code)
    return out


def field_thumbnail_evidence_map(
        *, field_data: dict | None = None, floor: dict | None = None,
        zone: dict | None = None, quest_tables: dict[str, dict] | None = None,
        asset_exists=None, boss_identity_of=None) -> dict[str, dict]:
    """Build a fail-closed field → official quest-cover evidence map.

    There are two materially different thumbnail columns in the client data:
    ``floor.c2`` is a 31×31 in-battle floor icon, while quest rows carry the
    240×188 ``quest/thumbnail`` cover consumed by the rush floor list.  The old
    mapper only expanded tower/challenge host quests.  Dedicated bosses whose
    source field lives in boss-battle, practice, ranking, world-story, etc. then
    had no entry and silently kept the copied Combat Diver template cover.

    Exact field references in every known quest table are strongest.  When the
    selected Boss field has no direct quest row, reverse-index every direct
    official quest through field_data→zone→actual single-battle Boss tuple and
    reuse only a cover whose Boss identity tuple is exactly equal.  A
    tower/challenge host cover is retained as diagnostic metadata only; it is
    never sufficient proof for a Boss floor.  Every accepted image must exist
    in the effective client-visible asset chain.  Static provenance is
    recorded; it deliberately does not claim on-device UI verification.
    """
    fd = (_tbl("master/battle/field_data.orderedmap")
          if field_data is None else field_data)
    floor_table = (q.load_table("master/battle/floor.orderedmap")
                   if floor is None else floor)
    zone_table = (_tbl(ZONE_T) if zone is None else zone)
    official_fields = {
        str(field_id) for field_id in fd
        if str(field_id) not in ("", "(None)")
        and not str(field_id).startswith(f"{PRIVATE_PREFIX}")
    }
    exists = asset_exists or q.exists_current
    exists_cache: dict[str, bool] = {}
    visual_identities = (boss_cover_visual_identity_map()
                         if boss_identity_of is None else None)

    def visual_identity(code: str) -> str:
        if boss_identity_of is not None:
            return str(boss_identity_of(str(code)))
        return str(visual_identities.get(str(code), str(code)))

    field_bosses: dict[str, tuple[str, ...]] = {}
    field_visual_bosses: dict[str, tuple[str, ...]] = {}
    for field_id, leaf in fd.items():
        if str(field_id) not in official_fields or isinstance(leaf, dict):
            continue
        try:
            values = cells(leaf)
        except (TypeError, ValueError, csv.Error, StopIteration):
            continue
        if len(values) <= 2:
            continue
        bosses = tuple(sorted(zone_single_bosses(zone_table.get(values[2]))))
        if bosses:
            field_bosses[str(field_id)] = bosses
            field_visual_bosses[str(field_id)] = tuple(sorted(
                visual_identity(code) for code in bosses))

    def asset_is_present(thumbnail: str) -> tuple[str, bool]:
        logical = quest_thumbnail_asset_logical(thumbnail)
        if logical not in exists_cache:
            exists_cache[logical] = bool(logical and exists(logical))
        return logical, exists_cache[logical]

    candidates: dict[str, list[dict]] = {}

    def add_candidate(field_id: str, thumbnail: str, *, match: str,
                      category: str, logical: str, path=(), level: int = 0,
                      floor_key: str | None = None,
                      cover_field: str | None = None) -> None:
        if (field_id not in official_fields
                or thumbnail in (None, "", "(None)")):
            return
        asset_logical, present = asset_is_present(str(thumbnail))
        if not present:
            return
        candidates.setdefault(field_id, []).append({
            "schema": THUMBNAIL_EVIDENCE_SCHEMA,
            "field": field_id,
            "thumbnail": str(thumbnail),
            "asset_logical": asset_logical,
            "asset_exists": True,
            "source_match": match,
            "source_category": category,
            "source_logical": logical,
            "source_path": list(map(str, path)),
            "source_level": int(level),
            "floor_key": floor_key,
            "cover_field": str(cover_field or field_id),
            "bosses": list(field_bosses.get(field_id, ())),
            "boss_visual_identity": list(
                field_visual_bosses.get(field_id, ())),
            "static_verified": True,
            "runtime_simulated": False,
            "gameplay_verified": False,
        })

    table_cache: dict[str, dict] = {}
    category_order: dict[str, int] = {}
    for order, (category, _label, logical, _group, _icon) in enumerate(
            wb.QUEST_CATS):
        category_order[category] = order
        if quest_tables is not None:
            if logical not in quest_tables:
                continue
            table = quest_tables[logical]
        else:
            try:
                table = wb._load(logical)
            except (FileNotFoundError, KeyError, TypeError, ValueError,
                    zlib.error):
                continue
        table_cache[logical] = table
        for path, leaf in wb._leaves(table):
            # Never learn official cover metadata from this tool's previous
            # output.  Otherwise a stale 700099 c5 can become its own proof.
            if (category == "rush" and path
                    and str(path[0]) in GAUNTLET_HUB_EVENT_IDS):
                continue
            values = cells(leaf)
            thumbnail = next(
                (value for value in values if "/thumbnail/" in value), "")
            if not thumbnail:
                continue
            for index, field_id in enumerate(values):
                if field_id not in official_fields:
                    continue
                level_text = quest_level_of(values, index)
                add_candidate(
                    field_id, thumbnail, match="exact_field",
                    category=category, logical=logical, path=path,
                    level=int(level_text) if level_text else 0,
                    cover_field=field_id)

    # A field name is an implementation carrier, not the visual identity.  Use
    # direct official quest rows to build the real Boss-tuple→cover index, then
    # lend that cover to aliases containing the exact same runtime Boss tuple.
    # ``treant_single`` therefore resolves through ``main_1_7_2`` to the tree
    # Boss image instead of inheriting a challenge-floor host image of White Tiger.
    direct_by_bosses: dict[tuple[str, ...], list[dict]] = {}
    for field_id, options in candidates.items():
        signature = field_bosses.get(field_id)
        if not signature:
            continue
        for option in options:
            if option["source_match"] == "exact_field":
                direct_by_bosses.setdefault(signature, []).append(option)
    for field_id, signature in field_bosses.items():
        for source in direct_by_bosses.get(signature, ()):
            if source["field"] == field_id:
                continue
            add_candidate(
                field_id, source["thumbnail"], match="exact_boss_identity",
                category=source["source_category"],
                logical=source["source_logical"],
                path=source["source_path"], level=source["source_level"],
                cover_field=source["field"])

    # Some official masters give single/multi/tower variants different Boss
    # IDs even though the displayed Boss and model are identical.  Exact code
    # equality therefore cannot cover all valid aliases.  A second reverse
    # index uses the official display name plus model root; it is deliberately
    # weaker than exact code equality and stronger than any floor-host relation.
    direct_by_visual_bosses: dict[tuple[str, ...], list[dict]] = {}
    for field_id, options in candidates.items():
        signature = field_visual_bosses.get(field_id)
        if not signature:
            continue
        for option in options:
            if option["source_match"] == "exact_field":
                direct_by_visual_bosses.setdefault(signature, []).append(option)
    for field_id, signature in field_visual_bosses.items():
        if field_id in candidates and any(
                option["source_match"] in {
                    "exact_field", "exact_boss_identity"}
                for option in candidates[field_id]):
            continue
        for source in direct_by_visual_bosses.get(signature, ()):
            if source["field"] == field_id:
                continue
            add_candidate(
                field_id, source["thumbnail"],
                match="exact_boss_visual_identity",
                category=source["source_category"],
                logical=source["source_logical"],
                path=source["source_path"], level=source["source_level"],
                cover_field=source["field"])

    fkey_fields: dict[str, list[str]] = {}
    for floor_key, leaf in floor_table.items():
        if isinstance(leaf, dict):
            continue
        text = leaf.decode("utf-8") if isinstance(leaf, bytes) else str(leaf)
        fields: list[str] = []
        for line in text.splitlines():
            values = cb._cols(line)
            if values and values[0] in official_fields:
                fields.append(values[0])
        fkey_fields[str(floor_key)] = fields

    for category, logical, floor_col in (
            ("tower", "master/quest/event/tower_dungeon_event_quest.orderedmap", 99),
            ("challenge_dungeon",
             "master/quest/event/challenge_dungeon_event_quest.orderedmap", 110),
    ):
        table = table_cache.get(logical)
        if table is None:
            if quest_tables is not None:
                continue
            try:
                table = q.load_table(logical)
            except (FileNotFoundError, KeyError, TypeError, ValueError,
                    zlib.error):
                continue
        for path, leaf in wb._leaves(table):
            values = cells(leaf)
            if len(values) <= floor_col:
                continue
            floor_key = values[floor_col]
            thumbnail = values[3] if len(values) > 3 else ""
            level_text = quest_level_of(values, floor_col)
            for field_id in fkey_fields.get(floor_key, ()):
                add_candidate(
                    field_id, thumbnail, match="floor_host_quest",
                    category=category, logical=logical, path=path,
                    level=int(level_text) if level_text else 0,
                    floor_key=floor_key)

    out: dict[str, dict] = {}
    for field_id, options in candidates.items():
        # Exact field proof outranks exact Boss identity, and both outrank the
        # diagnostic-only floor-host relation.  Within a proof class choose the
        # highest official enemy level, then stable category/path ordering.
        match_rank = {
            "exact_field": 0,
            "exact_boss_identity": 1,
            "exact_boss_visual_identity": 2,
            "floor_host_quest": 3,
        }
        options.sort(key=lambda item: (
            match_rank.get(str(item["source_match"]), 99),
            -int(item["source_level"]),
            category_order.get(str(item["source_category"]), 999),
            str(item["source_logical"]),
            tuple(item["source_path"]),
            str(item["thumbnail"]),
        ))
        out[field_id] = options[0]
    return out


def field_thumbnail_map() -> dict[str, str]:
    """field_data id → verified 240×188 quest cover (never floor.c2)."""
    return {
        field_id: evidence["thumbnail"]
        for field_id, evidence in field_thumbnail_evidence_map().items()
    }


def resolve_quest_thumbnail(
        source_field: str, explicit_thumbnail: str | None,
        evidence_map: dict[str, dict], *, require: bool) -> tuple[str, dict | None]:
    """Resolve c5 from the actual boss donor field, never the terrain donor."""
    source_field = str(source_field)
    evidence = evidence_map.get(source_field)
    if (evidence is not None
            and (not require or evidence.get("source_match") in {
                "exact_field", "exact_boss_identity",
                "exact_boss_visual_identity"})):
        return str(evidence["thumbnail"]), copy.deepcopy(evidence)
    explicit = str(explicit_thumbnail or "")
    if require:
        if evidence is not None and evidence.get("source_match") == "floor_host_quest":
            raise ValueError(
                f"Boss 来源场地 {source_field} 只有 floor_host_quest 封面关系; "
                "无法证明图片中的 Boss 身份")
        raise ValueError(
            f"Boss 来源场地 {source_field} 没有可复核 quest 大图; "
            "拒绝沿用模板/地形封面")
    return explicit, None

START = "2000-01-01 12:00:00"
END = "2099-12-29 23:59:59"
RESULT_END = "2099-12-30 12:00:00"
EXCHANGE_END = "2099-12-31 11:59:59"


def cells(leaf) -> list[str]:
    line = leaf.decode("utf-8") if isinstance(leaf, bytes) else leaf
    return next(csv.reader(io.StringIO(line)))


def join(row: list[str], as_bytes: bool):
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(row)
    s = buf.getvalue()
    return s.encode("utf-8") if as_bytes else s


def enforce_gauntlet_quest_table_player_rank(quest_table: dict) -> dict:
    """Repair both gauntlet hubs, including rows inherited from an older roll."""
    for event_id in GAUNTLET_HUB_EVENT_IDS:
        event = quest_table.get(event_id)
        if event is None:
            continue
        if not isinstance(event, dict):
            raise ValueError(f"rush_event_quest[{event_id}] is not a nested map")
        for quest_key, leaf in event.items():
            if isinstance(leaf, dict):
                raise ValueError(
                    f"rush_event_quest[{event_id}][{quest_key}] is not a CSV leaf"
                )
            row = cells(leaf)
            if len(row) <= 48:
                raise ValueError(
                    f"rush_event_quest[{event_id}][{quest_key}] has only {len(row)} columns"
                )
            enforce_gauntlet_player_rank(row)
            event[quest_key] = join(row, isinstance(leaf, bytes))
    return quest_table


def build_deep_abyss_folder_leaf(template_leaf: bytes | str, fixed_rewards: list[dict]) -> bytes | str:
    """Preview the same fixed rewards that the server grants; never guess a default."""
    if not isinstance(fixed_rewards, list) or not 1 <= len(fixed_rewards) <= 10:
        raise ValueError("深渊固定奖励必须有 1 至 10 项，不能静默截断预览")
    row = list(cells(template_leaf))
    if len(row) != 37:
        raise ValueError(f"rush folder template has {len(row)} columns, expected 37")
    row[0] = "1"              # display_order
    row[1] = "1"              # quest_kind = rush folder
    row[2] = EVENT_NAME
    # Chance/random extras stay server-driven and are intentionally omitted
    # from this static preview.
    for base in range(7, 37, 3):
        row[base:base + 3] = ["(None)", "", "(None)"]
    for index, reward in enumerate(fixed_rewards):
        values = [reward.get(key) for key in ("type", "id", "count")]
        if any(type(value) is not int for value in values) or values[0] < 0 or min(values[1:]) <= 0:
            raise ValueError(f"深渊固定奖励格式无效: {reward!r}")
        base = 7 + 3 * index
        row[base:base + 3] = [str(value) for value in values]
    return join(row, isinstance(template_leaf, bytes))


def fmt(v: float) -> str:
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s or "0"


def select_surjective_level(node: dict, enemy_level: int) -> int | None:
    """客户端 getSurjectivity：返回第一个 ``>= enemy_level`` 的数字档。"""
    if not isinstance(node, dict):
        return None
    try:
        level = int(enemy_level)
    except (TypeError, ValueError):
        return None
    keys = sorted(int(k) for k in node if str(k).isdigit())
    return next((key for key in keys if key >= level), None)


def clone_hit_boss_level_c2(source_leaf, scale: float):
    """重建一条 Hit-HP boss_level 叶，只缩放 c2，绝不改原叶或 c3/c4。"""
    as_bytes = isinstance(source_leaf, (bytes, bytearray))
    source = bytes(source_leaf) if isinstance(source_leaf, bytearray) else source_leaf
    if not isinstance(source, (str, bytes)):
        raise ValueError(f"boss_level leaf 类型非法:{type(source_leaf).__name__}")
    row = cells(source)
    if len(row) < 13:
        raise ValueError(f"boss_level 行列数={len(row)}(<13)")
    if row[0] != "0":
        raise ValueError("仅 Hit HP(kind=0) 可通过 boss_level.c2 伸缩；Fix HP 必须拒绝")
    try:
        old_c2 = float(row[2])
        c3 = float(row[3])
        factor = float(scale)
    except (TypeError, ValueError) as exc:
        raise ValueError("boss_level c2/c3 或伸缩倍率不是数字") from exc
    if not all(math.isfinite(v) and v > 0 for v in (old_c2, c3, factor)):
        raise ValueError(f"boss_level c2/c3/倍率必须为有限正数:{old_c2},{c3},{factor}")
    new_c2 = old_c2 * factor
    if not math.isfinite(new_c2) or new_c2 <= 0:
        raise ValueError(f"boss_level.c2 伸缩结果非法:{new_c2}")
    row[2] = fmt(new_c2)
    return join(row, as_bytes)


def clone_fix_boss_level_hp(source_leaf, scale: float):
    """重建一条 Fix-HP boss_level 叶，只缩放 c5 并完整保留 c6。

    客户端 ``BossLevelValues`` 的 Fix 通道以 ``c5 * c6`` 为固定 HP 基数；
    等级曲线由 c1 决定。按比例缩放 c5 因而也适用于曲线倍率不为 1 的档，
    且不会把 Hit 通道使用的等级 K 重复乘入。
    """
    as_bytes = isinstance(source_leaf, (bytes, bytearray))
    source = bytes(source_leaf) if isinstance(source_leaf, bytearray) else source_leaf
    if not isinstance(source, (str, bytes)):
        raise ValueError(f"boss_level leaf 类型非法:{type(source_leaf).__name__}")
    row = cells(source)
    if len(row) < 13:
        raise ValueError(f"boss_level 行列数={len(row)}(<13)")
    if row[0] != "1":
        raise ValueError("仅 Fix HP(kind=1) 可通过 boss_level.c5 伸缩")
    try:
        old_c5 = float(row[5])
        c6 = float(row[6])
        factor = float(scale)
    except (TypeError, ValueError) as exc:
        raise ValueError("boss_level c5/c6 或伸缩倍率不是数字") from exc
    if not all(math.isfinite(v) and v > 0 for v in (old_c5, c6, factor)):
        raise ValueError(f"boss_level c5/c6/倍率必须为有限正数:{old_c5},{c6},{factor}")
    new_c5 = old_c5 * factor
    if not math.isfinite(new_c5) or new_c5 <= 0:
        raise ValueError(f"boss_level.c5 伸缩结果非法:{new_c5}")
    row[5] = fmt(new_c5)
    return join(row, as_bytes)


def clone_general_boss_level_hp(source_leaf, scale: float):
    """按 BossLevelValues 的 HP kind 分派到 Hit c2 或 Fix c5。"""
    row = cells(source_leaf)
    if len(row) < 13:
        raise ValueError(f"boss_level 行列数={len(row)}(<13)")
    if row[0] == "0":
        return clone_hit_boss_level_c2(source_leaf, scale), 2
    if row[0] == "1":
        return clone_fix_boss_level_hp(source_leaf, scale), 5
    raise ValueError(f"boss_level HP kind 不支持:{row[0]!r}")


def clone_target_hit_boss_level_hp(
        source_leaf, target_hp: float, enemy_level: int, *,
        curve_name: str = AUTHORITATIVE_HIT_HP_CURVE):
    """Rewrite one Hit row to an absolute round-local target and read it back.

    The source c4 correction curve may be client-bundled and therefore
    unavailable to the tool.  Scaling its c2 would still be proxy arithmetic.
    This adapter instead preserves the Hit kind and c3, replaces c4 with a
    curve whose table is locally audited, and solves c2 from the client formula
    ``c2 * c3 * correction[level] * GENERAL_HP_LEVEL_SCALE[level]``.

    It is intentionally limited to Hit rows.  Converting an unrelated Fix row
    or mixing HP kinds would expand the compatibility claim beyond the 51
    proxy-only General families and remains fail-closed.
    """
    as_bytes = isinstance(source_leaf, (bytes, bytearray))
    source = bytes(source_leaf) if isinstance(source_leaf, bytearray) else source_leaf
    if not isinstance(source, (str, bytes)):
        raise ValueError(f"boss_level leaf 类型非法:{type(source_leaf).__name__}")
    row = cells(source)
    if len(row) < 13:
        raise ValueError(f"boss_level 行列数={len(row)}(<13)")
    if row[0] != "0":
        raise ValueError("目标值权威适配仅接受 Hit HP(kind=0)")
    try:
        wanted = float(target_hp)
        c3 = float(row[3])
        level = int(enemy_level)
    except (TypeError, ValueError) as exc:
        raise ValueError("目标 HP、boss_level.c3 或敌等级不是数字") from exc
    correction = curve_value("hp", str(curve_name), level)
    level_scale = GENERAL_HP_LEVEL_SCALE.get(level)
    numeric = (wanted, c3, correction, level_scale)
    if (correction is None or level_scale is None
            or not all(math.isfinite(float(value)) and float(value) > 0
                       for value in numeric if value is not None)):
        raise ValueError(
            f"目标值权威 Hit 公式不可解:target={target_hp},c3={row[3]!r},"
            f"curve={curve_name}@{enemy_level}:{correction},K={level_scale}")
    solved_c2 = wanted / c3 / float(correction) / float(level_scale)
    if not math.isfinite(solved_c2) or solved_c2 <= 0:
        raise ValueError(f"目标值权威 boss_level.c2 解非法:{solved_c2}")
    row[2] = fmt(solved_c2)
    row[4] = str(curve_name)
    rebuilt = join(row, as_bytes)
    rebuilt_row = cells(rebuilt)
    readback = (float(rebuilt_row[2]) * float(rebuilt_row[3])
                * float(correction) * float(level_scale))
    if not math.isfinite(readback) or readback <= 0:
        raise ValueError(f"目标值权威 Hit 回读非法:{readback}")
    return rebuilt, readback


@dataclass(frozen=True)
class HpMember:
    """One reachable HP-bearing entity occurrence in a native bundle."""

    code: str
    kind: int
    role: str
    ordinal: int
    selected_level: int
    raw_hp: float


@dataclass(frozen=True)
class HpExpansionResult:
    ok: bool
    members: tuple[HpMember, ...] = ()
    total_hp: float | None = None
    selected_parent_level: int | None = None
    reason: str | None = None
    detail: str = ""


HP_TARGET_ABS_TOLERANCE = 1.0
HP_TARGET_REL_TOLERANCE = 1e-4


@dataclass(frozen=True)
class HpComponentAudit:
    """One occurrence/phase in a target plan and its client-formula readback."""

    occurrence: int
    boss_occurrence: int
    code: str
    readback_code: str
    phase: str
    kind: str
    source_evidence_kind: str
    evidence_kind: str
    source: str
    native_hp: float
    baseline_target_hp: float
    final_target_hp: float
    baseline_readback_hp: float
    final_readback_hp: float
    baseline_error_hp: float
    final_error_hp: float
    channel: str
    destination: str
    selected_level: int | None = None


@dataclass(frozen=True)
class HpAdaptationAudit:
    """Unified HP plan/readback receipt for one boss floor."""

    round_no: int
    family: str
    channel: str
    destination: str
    absolute_verified: bool
    baseline_target_hp: float
    final_target_hp: float
    baseline_readback_hp: float
    final_readback_hp: float
    baseline_error_hp: float
    final_error_hp: float
    baseline_c86: float
    final_c86: float
    abs_tolerance_hp: float
    rel_tolerance: float
    components: tuple[HpComponentAudit, ...]

    @property
    def baseline_tolerance_hp(self) -> float:
        return max(self.abs_tolerance_hp,
                   abs(self.baseline_target_hp) * self.rel_tolerance)

    @property
    def final_tolerance_hp(self) -> float:
        return max(self.abs_tolerance_hp,
                   abs(self.final_target_hp) * self.rel_tolerance)

    @property
    def within_tolerance(self) -> bool:
        return (abs(self.baseline_error_hp) <= self.baseline_tolerance_hp
                and abs(self.final_error_hp) <= self.final_tolerance_hp)


def _hp_evidence_source(component: dict) -> str:
    evidence = component.get("evidence")
    if isinstance(evidence, dict) and evidence.get("logical"):
        return str(evidence["logical"])
    if component.get("fixed_phase_evidence"):
        return wf_orochi_ex.OROCHI_EX_LOGICAL
    return f"{BOSS_LEVEL}:{component.get('code') or '?'}"


