"""Schema + semantic validation. Findings are ``block`` (B-xxx, publish refused) or ``warning`` (W-xxx).

Codes follow the design doc (rogue-content-editor-design.md §3), adapted to the real trial server:
B-008 is a full port of the server's load-time config validation, B-004 replays its relic/event
normalizers (the server silently drops what it cannot normalize), B-014 lists editor-only policy
fields that the current server would ignore.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from . import catalog, effects as fx, encounters as enc, jsonio, servercheck
from .workspace import SCHEMA_PATH, event_keys, option_key, relic_keys

ELEMENTS = fx.ELEMENTS


@lru_cache(maxsize=1)
def _validator():
    from jsonschema import Draft202012Validator
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


class Findings:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, code, pointer, message, *, entity_type=None, entity_id=None, related=(), fix=None):
        severity = "block" if code.startswith("B") else "warning"
        self.items.append({"code": code, "severity": severity, "pointer": pointer, "entity_type": entity_type,
                           "entity_id": entity_id, "message": message, "related_ids": list(related),
                           "suggested_fix": fix})


def schema_errors(workspace: dict) -> list[dict]:
    out = []
    for err in sorted(_validator().iter_errors(workspace), key=lambda e: [str(p) for p in e.absolute_path])[:200]:
        pointer = "/" + "/".join(str(p) for p in err.absolute_path)
        message = err.message
        if err.validator == "oneOf" and len(message) > 240:
            message = "不符合任何允许的形状（效果类型未登记、参数越界，或 effect/effects 同时存在）"
        out.append({"pointer": pointer, "message": message[:400]})
    return out


def _master_checks(f: Findings, ws, master):
    for problem in master.error:
        f.add("B-001", "/source", problem, entity_type="master",
              fix="确认 profiles/local.json rogue_corridor.data_dir 指向完整生成物；截断样本不能当完整表")
    src = ws["source"]
    if master.tier_sha and src.get("tier_table_sha256") != master.tier_sha:
        f.add("B-013", "/source/tier_table_sha256", "完整 tier_table 已变化（与工作区锁定的哈希不同）", entity_type="master",
              fix="在总览页确认变化后执行「重新锁定主数据」")
    if master.soul_sha and src.get("soul_catalog_sha256") != master.soul_sha:
        f.add("B-013", "/source/soul_catalog_sha256", "魂珠目录 rules_v3_metadata.json 已变化", entity_type="master",
              fix="在总览页确认后执行「重新锁定主数据」")
    if src.get("soul_catalog_sha256") is None:
        f.add("B-013", "/source/soul_catalog_sha256", "魂珠目录未锁定，不能宣称通过完整发布校验", entity_type="master")
    rules = ws["data"]["rules"]
    if (rules.get("host") or {}).get("event_id") != src.get("runtime_host_event_id"):
        f.add("B-013", "/data/rules/host/event_id", "宿主活动 ID 与导入时不同", entity_type="rules")
    meta = (master.tier_table or {}).get("meta") or {}
    if meta.get("runtime_tested") is False:
        f.add("W-007", "/source", "tier_table 只经过静态检查（runtime_tested=false）；全量候选仍需试验服/真机验证",
              entity_type="master")


def _id_checks(f: Findings, ws):
    data, life, pol = ws["data"], ws["lifecycle"], ws["policy"]
    tomb = {(t["kind"], t["id"]) for t in life["tombstones"]}
    seen = set()
    for i, r in enumerate(data["relics"]):
        rid = r.get("relic_id")
        if rid in seen:
            f.add("B-002", f"/data/relics/{i}/relic_id", f"遗物 ID {rid} 重复", entity_type="relic", entity_id=rid)
        seen.add(rid)
        if ("relic", rid) in tomb:
            f.add("B-002", f"/data/relics/{i}/relic_id", f"遗物 ID {rid} 已删除（墓碑），不能复用", entity_type="relic", entity_id=rid)
    seen = set()
    all_options = {}
    for i, ev in enumerate(data["events"]):
        eid = ev.get("event_id")
        if eid in seen:
            f.add("B-002", f"/data/events/{i}/event_id", f"事件 ID {eid} 重复", entity_type="event", entity_id=eid)
        seen.add(eid)
        if ("event", eid) in tomb:
            f.add("B-002", f"/data/events/{i}/event_id", f"事件 ID {eid} 已删除（墓碑），不能复用", entity_type="event", entity_id=eid)
        ids = pol["event_option_ids"].get(eid)
        if ids is None or len(ids) != len(ev.get("options") or []):
            f.add("B-002", f"/policy/event_option_ids/{eid}", f"事件 {eid} 的稳定选项 ID 数量与选项数不一致",
                  entity_type="event", entity_id=eid)
        for oid in ids or []:
            if oid in all_options:
                f.add("B-002", f"/policy/event_option_ids/{eid}", f"选项 ID {oid} 同时属于 {all_options[oid]} 与 {eid}",
                      entity_type="event", entity_id=eid)
            all_options[oid] = eid
            if ("event_option", oid) in tomb:
                f.add("B-002", f"/policy/event_option_ids/{eid}", f"选项 ID {oid} 已删除（墓碑），不能复用",
                      entity_type="event", entity_id=eid)
    for eid in pol["event_option_ids"]:
        if eid not in seen:
            f.add("B-012", f"/policy/event_option_ids/{eid}", f"选项 ID 映射指向不存在的事件 {eid}", entity_type="event", entity_id=eid)


def _locale_checks(f: Findings, ws):
    data = ws["data"]
    loc = data["locales"]
    zh, en = loc.get("zh") or {}, loc.get("en") or {}
    used = set()

    def need(key, pointer, entity_type, entity_id, raw_zh=None):
        used.add(key)
        for lang, table in (("zh", zh), ("en", en)):
            if key not in table:
                f.add("B-005", pointer, f"{lang} 缺少文本键 {key}", entity_type=entity_type, entity_id=entity_id,
                      fix="在文本页或详情里补齐中英文本")
            elif not str(table[key]).strip():
                f.add("B-005", pointer, f"{lang} 文本为空：{key}" + ("（英文待补）" if lang == "en" else ""),
                      entity_type=entity_type, entity_id=entity_id)
        if raw_zh is not None and key in zh and zh[key] != raw_zh:
            f.add("W-003", pointer, f"旧字段中文与 locales.zh[{key}] 不一致（双真值）", entity_type=entity_type,
                  entity_id=entity_id, fix="在详情页保存一次即可同步")

    for i, r in enumerate(data["relics"]):
        rid = r.get("relic_id")
        name_key, desc_key = relic_keys(rid)
        if r.get("name_key") != name_key or r.get("desc_key") != desc_key:
            f.add("B-005", f"/data/relics/{i}", f"遗物 {rid} 的文本键应为 {name_key}/{desc_key}", entity_type="relic", entity_id=rid)
        need(r.get("name_key"), f"/data/relics/{i}/name_key", "relic", rid, r.get("name"))
        need(r.get("desc_key"), f"/data/relics/{i}/desc_key", "relic", rid, r.get("desc"))
    for i, ev in enumerate(data["events"]):
        eid = ev.get("event_id")
        title_key, text_key = event_keys(eid)
        if ev.get("title_key") != title_key or ev.get("text_key") != text_key:
            f.add("B-005", f"/data/events/{i}", f"事件 {eid} 的文本键应为 {title_key}/{text_key}", entity_type="event", entity_id=eid)
        need(ev.get("title_key"), f"/data/events/{i}/title_key", "event", eid, ev.get("title"))
        need(ev.get("text_key"), f"/data/events/{i}/text_key", "event", eid, ev.get("text"))
        for j, opt in enumerate(ev.get("options") or []):
            if opt.get("label_key") != option_key(eid, j):
                f.add("B-005", f"/data/events/{i}/options/{j}/label_key",
                      f"事件 {eid} 选项 {j} 的文本键应为 {option_key(eid, j)}（选项重排后必须重建）", entity_type="event", entity_id=eid)
            need(opt.get("label_key"), f"/data/events/{i}/options/{j}/label_key", "event", eid, opt.get("label"))
    orphans = sorted((set(zh) | set(en)) - used)
    if orphans:
        f.add("W-008", "/data/locales", f"{len(orphans)} 个文本键没有被遗物/事件引用：" + "、".join(orphans[:8]),
              entity_type="locale", related=orphans[:50])
    if set(zh) != set(en):
        diff = sorted(set(zh) ^ set(en))
        f.add("B-005", "/data/locales", f"中英键集合不一致（{len(diff)} 个）：" + "、".join(diff[:8]), entity_type="locale",
              related=diff[:50])


LEVEL_TEXT = re.compile(r"(\d+)\s*(?:→|->|至|到)\s*(\d+)\s*级")


def _content_checks(f: Findings, ws, base_ws):
    data = ws["data"]
    rules = data["rules"]
    aliases_r, aliases_e = fx.relic_aliases(rules), fx.event_aliases(rules)
    base_relics = {r.get("relic_id"): r for r in ((base_ws or {}).get("data", {}).get("relics") or [])}
    roster = rules.get("roster") or {}
    for i, r in enumerate(data["relics"]):
        rid = r.get("relic_id")
        settled = fx.server_relic(r, aliases_r)
        if not settled["ok"]:
            f.add("B-004", f"/data/relics/{i}", f"服务端会丢弃遗物 {rid}：{settled['reason']}", entity_type="relic", entity_id=rid,
                  fix="只用效果清单里的类型与参数范围")
            continue
        combat = [e for e in settled["effects"] if e.get("runtime") == "client_pending"]
        if combat:
            fresh = rid not in base_relics or jsonio.canonical(base_relics[rid]) != jsonio.canonical(r)
            f.add("W-002", f"/data/relics/{i}", ("新增/改动的" if fresh else "") +
                  f"战斗类效果（{'、'.join(e['type'] for e in combat)}）服务端只透传，是否生效取决于客户端",
                  entity_type="relic", entity_id=rid)
        raws = fx.relic_raw_effects(r)
        legacy = [e.get("type") for e in raws if isinstance(e, dict) and str(e.get("type")).lower() in fx.BUILTIN_RELIC_ALIASES
                  and "|" in fx.BUILTIN_RELIC_ALIASES[str(e.get("type")).lower()]]
        if legacy:
            f.add("W-004", f"/data/relics/{i}", f"旧口径 {'、'.join(legacy)}：服务端按 " +
                  "，".join(fx.describe_settled(e) for e in settled["effects"]) + " 结算（乘数/百分数换算）",
                  entity_type="relic", entity_id=rid)
        for text in (r.get("desc") or "", (data["locales"].get("zh") or {}).get(r.get("desc_key") or "", "")):
            m = LEVEL_TEXT.search(text)
            if m and (int(m.group(1)), int(m.group(2))) != (roster.get("start_level"), roster.get("max_level")):
                f.add("W-003", f"/data/relics/{i}/desc", f"文案写 {m.group(0)}，规则是 {roster.get('start_level')}→{roster.get('max_level')} 级",
                      entity_type="relic", entity_id=rid, fix="选定真实玩法口径后改文案或规则")
                break
    for i, ev in enumerate(data["events"]):
        eid = ev.get("event_id")
        settled = fx.server_event(ev, aliases_e)
        if not settled["ok"]:
            f.add("B-004", f"/data/events/{i}", f"服务端会丢弃事件 {eid}：{settled['reason']}", entity_type="event", entity_id=eid)
    if not data["relics"]:
        f.add("B-004", "/data/relics", "没有遗物时服务端会回退到内置占位遗物", entity_type="relic")
    if not data["events"]:
        f.add("B-004", "/data/events", "没有事件时服务端会回退到内置占位事件", entity_type="event")
    rarities = {r.get("rarity") for r in data["relics"]}
    for src, weights in ((rules.get("rewards") or {}).get("relic_rarity_weights") or {}).items():
        if not isinstance(weights, dict):
            continue
        empty = [k for k, w in weights.items() if isinstance(w, (int, float)) and w > 0 and k not in rarities]
        if empty:
            f.add("W-009", f"/data/rules/rewards/relic_rarity_weights/{src}",
                  f"{src} 来源给 {'、'.join(empty)} 有权重但没有这种稀有度的遗物（服务端会改抽其他稀有度）", entity_type="rules")
        if sum(w for w in weights.values() if isinstance(w, (int, float))) <= 0:
            f.add("W-009", f"/data/rules/rewards/relic_rarity_weights/{src}", f"{src} 来源遗物权重全为 0（改为任意稀有度）",
                  entity_type="rules")


def _rules_checks(f: Findings, ws, base_ws):
    data = ws["data"]
    rules = data["rules"]
    host_rounds = sorted({e["round"] for e in enc.host_encounters(data["encounter_pool"]) if e["round"] is not None})
    for problem in servercheck.check_rules(rules, host_rounds):
        f.add("B-008", problem["pointer"] if "pointer" in problem else problem["path"],
              "服务端会拒绝加载配置（回廊整体不可用）：" + problem["message"], entity_type="rules")
    bsw = (rules.get("rewards") or {}).get("battle_step_weights") or {}
    if isinstance(bsw, dict) and sum(v for v in bsw.values() if isinstance(v, (int, float))) <= 0:
        f.add("B-006", "/data/rules/rewards/battle_step_weights", "普通战奖励的角色/武器权重总和为 0", entity_type="rules")
    bands = (rules.get("rewards") or {}).get("tier_weights_by_floor") or []
    good = [b for b in bands if isinstance(b, dict) and isinstance(b.get("floors"), list) and len(b["floors"]) == 2]
    for a in range(len(good)):
        for b in range(a + 1, len(good)):
            (a0, a1), (b0, b1) = good[a]["floors"], good[b]["floors"]
            if isinstance(a0, int) and isinstance(b0, int) and a0 <= b1 and b0 <= a1:
                f.add("W-013", "/data/rules/rewards/tier_weights_by_floor", f"分层区间 {good[a]['floors']} 与 {good[b]['floors']} 重叠（先匹配的生效）",
                      entity_type="rules")
    for i, band in enumerate(good):
        w = band.get("weights")
        if isinstance(w, list) and len(w) == 4 and all(isinstance(x, (int, float)) for x in w) and abs(sum(w) - 100) > 1e-6:
            f.add("W-001", f"/data/rules/rewards/tier_weights_by_floor/{i}/weights", f"第 {i + 1} 段四档权重合计 {sum(w):g}（按比例归一，不要求 100）",
                  entity_type="rules")
    d = rules.get("difficulty") or {}
    if d.get("active_profile") == "test":
        test = (d.get("profiles") or {}).get("test") or {}
        f.add("W-010", "/data/rules/difficulty/active_profile", f"生效难度是试验档（hp×{test.get('hp')}、atk×{test.get('atk')}），只适合隔离试验服",
              entity_type="rules")
    # W-005: notable economy swings against the import base.
    if base_ws:
        old_rules = base_ws["data"]["rules"]
        old_bands = (old_rules.get("rewards") or {}).get("tier_weights_by_floor") or []
        for i, (ob, nb) in enumerate(zip(old_bands, good)):
            try:
                o4, n4 = ob["weights"][3] / sum(ob["weights"]), nb["weights"][3] / sum(nb["weights"])
            except (KeyError, TypeError, ZeroDivisionError, IndexError):
                continue
            if n4 > max(2 * o4, 0.01):
                f.add("W-005", f"/data/rules/rewards/tier_weights_by_floor/{i}/weights",
                      f"第 {i + 1} 段 T4 概率 {o4:.1%} → {n4:.1%}（超过 2 倍）", entity_type="rules")
        for key in ("character_prices", "weapon_prices"):
            for t, old in ((old_rules.get("shop") or {}).get(key) or {}).items():
                new = ((rules.get("shop") or {}).get(key) or {}).get(t)
                if isinstance(old, int) and isinstance(new, int) and old > 0 and new < old / 2:
                    f.add("W-005", f"/data/rules/shop/{key}/{t}", f"{key} T{t} 价格 {old} → {new}（降幅过半）", entity_type="rules")


def _encounter_checks(f: Findings, ws):
    data = ws["data"]
    view = enc.acts_view(data["rules"], data["encounter_pool"])
    for p in view["problems"]:
        code = "B-009" if "首领" in p["message"] else "B-010"
        f.add(code, f"/data/rules/map/acts/{p['act'] - 1}/encounter_ranks", p["message"], entity_type="act",
              entity_id=str(p["act"]))
    for e in view["host"]:
        for issue in e["damage_issues"]:
            f.add("W-011", "/data/encounter_pool", f"遭遇 {e['quest_id']} 诅咒属性文本未识别：{issue}", entity_type="encounter",
                  entity_id=e["quest_id"])
    return view


def _pool_checks(f: Findings, ws, master):
    data, pol = ws["data"], ws["policy"]
    rules = data["rules"]
    overlay = data["pool_overlay"]
    if master.tier_table is None:
        return None, None
    chars = catalog.character_pool(master, rules, overlay, pol)
    by_id = {c["id"]: c for c in chars}
    admitted = {str(c.get("id")) for c in master.characters()}
    boss_ids = {str(c.get("id")) for c in (overlay.get("boss_playable") or {}).get("characters") or []}
    for cid, ov in ((overlay.get("tier_overrides") or {}).get("characters") or {}).items():
        if cid not in admitted and not (ov.get("tier") is None and cid in boss_ids):
            f.add("B-003", f"/data/pool_overlay/tier_overrides/characters/{cid}",
                  f"角色 {cid} 不在 tier_table 入池名单，服务端会忽略这条覆盖", entity_type="character", entity_id=cid)
    for c in chars:
        if c["boss_playable"] and c.get("boss_playable_stale"):
            f.add("B-003", "/data/pool_overlay/boss_playable", f"boss 转可玩 {c['id']} 的排除原因已变化（{'；'.join(c['boss_playable_stale'])}），服务端会把它挡在池外",
                  entity_type="character", entity_id=c["id"], fix="重新生成 v3f 叠加层或确认后禁用")
    for cid, p in pol.get("characters", {}).items():
        c = by_id.get(cid)
        if c is None:
            f.add("B-003", f"/policy/characters/{cid}", f"策略里的角色 {cid} 不在主数据里", entity_type="character", entity_id=cid)
            continue
        if p.get("enabled") is True and not c["in_pool"]:
            f.add("B-014", f"/policy/characters/{cid}/enabled",
                  f"{c['name']}（{cid}）被主数据排除（{c.get('excluded_reason')}），当前服务端不能从编辑台放入回廊池（候选标记）",
                  entity_type="character", entity_id=cid, fix="需要重建 tier_table 或服务端支持 rogue_pool_policy.json")
        if "starter_eligible" in p and p["starter_eligible"] != c["starter_derived"]:
            f.add("B-014", f"/policy/characters/{cid}/starter_eligible",
                  f"{c['name']}（{cid}）单独设置「可进开局包」需要服务端能力（现规则：档位≤传说且非 boss 转可玩自动可进）",
                  entity_type="character", entity_id=cid)
        if "min_act" in p and p["min_act"] != c["min_act_derived"]:
            f.add("B-014", f"/policy/characters/{cid}/min_act",
                  f"{c['name']}（{cid}）单独设置最早出现幕需要服务端能力（现只有 boss 转可玩整组的 min_act）",
                  entity_type="character", entity_id=cid)
    weapons = catalog.weapon_pool(master, rules, pol)
    w_by_id = {w["id"]: w for w in weapons}
    for wid, p in pol.get("weapons", {}).items():
        w = w_by_id.get(wid)
        if w is None:
            f.add("B-003", f"/policy/weapons/{wid}", f"策略里的武器 {wid} 不在主数据里", entity_type="weapon", entity_id=wid)
            continue
        effective = [k for k, v in p.items() if k != "notes" and not (
            (k == "enabled" and v == w["in_pool"]) or (k == "tier_override" and v == w["source_tier"]) or
            (k == "starter_eligible" and v == w["starter_derived"]) or (k == "min_act" and v == 1) or
            (k == "soul_extractable" and v == bool(w["soul_id"] and not w["soul_excluded_reason"])))]
        if effective:
            f.add("B-014", f"/policy/weapons/{wid}", f"武器 {w['name']}（{wid}）的 {'/'.join(effective)} 需要服务端能力（服务端不读武器覆盖）",
                  entity_type="weapon", entity_id=wid)
        if p.get("enabled") is True and w["group"] == "pending_element":
            f.add("B-003", f"/policy/weapons/{wid}/enabled", f"{wid} 属性政策未定（weapons_pending_element_policy），不能当六属性武器入池",
                  entity_type="weapon", entity_id=wid)
    for table, label in (("souls", "魂珠"), ("relics", "遗物"), ("events", "事件"), ("encounters", "遭遇")):
        for item, p in pol.get(table, {}).items():
            effective = [k for k in p if k != "notes"]
            if effective:
                f.add("B-014", f"/policy/{table}/{item}", f"{label} {item} 的 {'/'.join(effective)} 需要服务端能力（当前服务端不读这些策略）",
                      entity_type=table[:-1], entity_id=item)
    for act, p in pol.get("acts", {}).items():
        if any(p.get(k) for k in ("exclude_quest_ids", "exclude_rounds", "boss_quest_ids")):
            f.add("B-014", f"/policy/acts/{act}", f"第{act}幕的幕级遭遇/首领白名单需要服务端能力（现只支持全局 exclude_rounds 与排名段）",
                  entity_type="act", entity_id=act)
    shop = pol.get("shop") or {}
    for kind, table in (shop.get("item_overrides") or {}).items():
        for item, p in table.items():
            if [k for k in p if k != "notes"]:
                f.add("B-014", f"/policy/shop/item_overrides/{kind}/{item}", "单品价格/上架覆盖需要服务端 priceResolver", entity_type="shop",
                      entity_id=f"{kind}:{item}")
    for svc, p in (shop.get("service_overrides") or {}).items():
        if [k for k in p if k != "notes"]:
            f.add("B-014", f"/policy/shop/service_overrides/{svc}", f"服务 {svc} 的单独价格/开关需要服务端能力", entity_type="shop", entity_id=svc)
    # B-011: the server's start-pack generator (rogue-start-packs-v2.js) per element.
    for el in ELEMENTS:
        cs = [c for c in chars if c["in_pool"] and c["element"] == el and c["effective_tier"] <= 3 and not c["boss_playable"]]
        low = [c for c in cs if c["effective_tier"] <= 2]
        ws_ = [w for w in weapons if w["in_pool"] and w["element"] == el and (w["source_tier"] or 9) <= 2]
        if len(cs) < 6 or len(low) < 5 or len(ws_) < 3:
            f.add("B-011", "/data/pool_overlay/tier_overrides", f"开局选{fx.ELEMENT_NAMES[el]}属性时服务端拿不到开局包"
                  f"（可用角色 {len(cs)}/6、其中普通/稀有 {len(low)}/5、普通/稀有武器 {len(ws_)}/3）", entity_type="element",
                  entity_id=str(el))
    return chars, weapons


def validate(workspace: dict, master, base_ws: dict | None = None) -> dict:
    f = Findings()
    for err in schema_errors(workspace):
        f.add("B-001", err["pointer"], "结构校验失败：" + err["message"])
    _master_checks(f, workspace, master)
    _id_checks(f, workspace)
    try:
        _locale_checks(f, workspace)
        _content_checks(f, workspace, base_ws)
        _rules_checks(f, workspace, base_ws)
        _encounter_checks(f, workspace)
        _pool_checks(f, workspace, master)
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        f.add("B-001", "/", f"工作区结构损坏，语义校验中断：{type(exc).__name__}: {exc}")
    blockers = sum(1 for x in f.items if x["severity"] == "block")
    return {"revision": workspace.get("revision"), "input_digest": jsonio.digest(workspace),
            "blockers": blockers, "warnings": len(f.items) - blockers, "findings": f.items}
