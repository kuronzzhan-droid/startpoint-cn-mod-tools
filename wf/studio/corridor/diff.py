"""Diff a workspace against a baseline: JSON pointers, readable entity lines, file list, impact."""
from __future__ import annotations

from . import catalog, effects as fx, encounters as enc, jsonio, rulesfields
from .layout import RUNTIME_FILES

ID_KEYS = {"/data/relics": "relic_id", "/data/events": "event_id", "/data/encounter_pool/encounters": "quest_id",
           "/data/pool_overlay/boss_playable/characters": "id"}


def _esc(part) -> str:
    return str(part).replace("~", "~0").replace("/", "~1")


def pointer_diff(before, after, path: str = "", out=None, limit: int = 2000) -> list[dict]:
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(before, dict) and isinstance(after, dict):
        for k in list(before) + [k for k in after if k not in before]:
            p = f"{path}/{_esc(k)}"
            if k not in after:
                out.append({"path": p, "op": "remove", "before": before[k]})
            elif k not in before:
                out.append({"path": p, "op": "add", "after": after[k]})
            else:
                pointer_diff(before[k], after[k], p, out, limit)
        return out
    if isinstance(before, list) and isinstance(after, list):
        key = ID_KEYS.get(path)
        if key and all(isinstance(x, dict) for x in before + after):
            old = {str(x.get(key)): x for x in before}
            new = {str(x.get(key)): x for x in after}
            for ident, item in old.items():
                p = f"{path}[{key}={ident}]"
                if ident not in new:
                    out.append({"path": p, "op": "remove", "before": item})
                else:
                    pointer_diff(item, new[ident], p, out, limit)
            for ident, item in new.items():
                if ident not in old:
                    out.append({"path": f"{path}[{key}={ident}]", "op": "add", "after": item})
            old_order = [i for i in old if i in new]
            new_order = [i for i in new if i in old]
            if old_order != new_order:
                out.append({"path": path, "op": "reorder", "before": old_order, "after": new_order})
            return out
        for i in range(max(len(before), len(after))):
            p = f"{path}/{i}"
            if i >= len(after):
                out.append({"path": p, "op": "remove", "before": before[i]})
            elif i >= len(before):
                out.append({"path": p, "op": "add", "after": after[i]})
            else:
                pointer_diff(before[i], after[i], p, out, limit)
        return out
    if jsonio.canonical(before) != jsonio.canonical(after):
        out.append({"path": path, "op": "replace", "before": before, "after": after})
    return out


def _fmt(v) -> str:
    if v is None:
        return "（无）"
    text = jsonio.canonical(v)
    return text if len(text) <= 80 else text[:77] + "…"


def readable(base: dict, ws: dict, master=None) -> list[dict]:
    """Entity-level lines: {area, entity, text}."""
    lines = []
    b, a = base["data"], ws["data"]
    # rules fields (labelled)
    for change in pointer_diff(b["rules"], a["rules"], ""):
        field = rulesfields.BY_PATH.get(change["path"])
        label = field["label"] if field else change["path"]
        lines.append({"area": "规则", "entity": change["path"],
                      "text": f"{label}：{_fmt(change.get('before'))} → {_fmt(change.get('after'))}"})
    # relics
    old = {r.get("relic_id"): r for r in b["relics"]}
    new = {r.get("relic_id"): r for r in a["relics"]}
    aliases = fx.relic_aliases(a["rules"])
    for rid in new.keys() - old.keys():
        settled = fx.server_relic(new[rid], aliases)
        what = "，".join(fx.describe_settled(e) for e in settled.get("effects", [])) if settled["ok"] else settled["reason"]
        lines.append({"area": "遗物", "entity": rid, "text": f"新增 {rid}「{new[rid].get('name')}」（{fx.RARITY_NAMES.get(new[rid].get('rarity'))}）：{what}"})
    for rid in old.keys() - new.keys():
        lines.append({"area": "遗物", "entity": rid, "text": f"删除 {rid}「{old[rid].get('name')}」（ID 退休，不再复用）"})
    for rid in sorted(old.keys() & new.keys()):
        for change in pointer_diff(old[rid], new[rid], ""):
            lines.append({"area": "遗物", "entity": rid,
                          "text": f"{rid}「{new[rid].get('name')}」{change['path']}：{_fmt(change.get('before'))} → {_fmt(change.get('after'))}"})
    # events
    old = {e.get("event_id"): e for e in b["events"]}
    new = {e.get("event_id"): e for e in a["events"]}
    for eid in new.keys() - old.keys():
        lines.append({"area": "事件", "entity": eid, "text": f"新增 {eid}「{new[eid].get('title')}」，{len(new[eid].get('options') or [])} 个选项"})
    for eid in old.keys() - new.keys():
        lines.append({"area": "事件", "entity": eid, "text": f"删除 {eid}「{old[eid].get('title')}」（ID 退休）"})
    old_ids, new_ids = base["policy"]["event_option_ids"], ws["policy"]["event_option_ids"]
    for eid in sorted(old.keys() & new.keys()):
        before_ids, after_ids = old_ids.get(eid) or [], new_ids.get(eid) or []
        if before_ids != after_ids and sorted(before_ids) == sorted(after_ids):
            lines.append({"area": "事件", "entity": eid, "text": f"{eid} 选项重排：" + "、".join(
                f"{before_ids.index(o)}→{i}" for i, o in enumerate(after_ids) if before_ids.index(o) != i) + "（文本键已同步重建）"})
        for oid in set(after_ids) - set(before_ids):
            lines.append({"area": "事件", "entity": eid, "text": f"{eid} 新增选项 {after_ids.index(oid)}「{new[eid]['options'][after_ids.index(oid)].get('label')}」"})
        for oid in set(before_ids) - set(after_ids):
            lines.append({"area": "事件", "entity": eid, "text": f"{eid} 删除选项「{old[eid]['options'][before_ids.index(oid)].get('label')}」"})
        for oid in set(before_ids) & set(after_ids):
            o_old = old[eid]["options"][before_ids.index(oid)]
            o_new = new[eid]["options"][after_ids.index(oid)]
            for change in pointer_diff({k: v for k, v in o_old.items() if k != "label_key"},
                                       {k: v for k, v in o_new.items() if k != "label_key"}, ""):
                lines.append({"area": "事件", "entity": eid, "text": f"{eid} 选项「{o_new.get('label')}」{change['path']}：{_fmt(change.get('before'))} → {_fmt(change.get('after'))}"})
        for k in ("title", "text"):
            if old[eid].get(k) != new[eid].get(k):
                lines.append({"area": "事件", "entity": eid, "text": f"{eid} {k}：{_fmt(old[eid].get(k))} → {_fmt(new[eid].get(k))}"})
    # pool overlay
    o_ov = ((b["pool_overlay"].get("tier_overrides") or {}).get("characters") or {})
    n_ov = ((a["pool_overlay"].get("tier_overrides") or {}).get("characters") or {})
    for cid in sorted(set(o_ov) | set(n_ov), key=lambda x: int(x) if x.isdigit() else 0):
        before, after = o_ov.get(cid), n_ov.get(cid)
        if jsonio.canonical(before) == jsonio.canonical(after):
            continue
        name = (after or before or {}).get("name") or cid

        def state(v):
            if v is None:
                return "主数据档位"
            return "移出回廊池" if v.get("tier") is None else f"T{v.get('tier')}"
        lines.append({"area": "角色池", "entity": cid, "text": f"角色 {cid} {name}：{state(before)} → {state(after)}"})
    # policy
    for change in pointer_diff(base["policy"], ws["policy"], ""):
        if change["path"].startswith("/event_option_ids"):
            continue
        lines.append({"area": "策略（编辑层）", "entity": change["path"],
                      "text": f"{change['path']}：{_fmt(change.get('before'))} → {_fmt(change.get('after'))}"})
    # locales (keys only that are not covered by relic/event raw text sync)
    for lang in ("zh", "en"):
        bo, ao = b["locales"].get(lang) or {}, a["locales"].get(lang) or {}
        changed = [k for k in set(bo) | set(ao) if bo.get(k) != ao.get(k)]
        if changed:
            lines.append({"area": "文本", "entity": lang, "text": f"{lang} 文本 {len(changed)} 处变化：" + "、".join(sorted(changed)[:6])
                          + ("…" if len(changed) > 6 else "")})
    if jsonio.canonical(b["tier_overrides"]) != jsonio.canonical(a["tier_overrides"]):
        lines.append({"area": "旧覆盖表", "entity": "tier_overrides.json", "text": "tier_overrides.json 有改动（数据线生成器读取，服务端不读）"})
    return lines


def impact(base: dict, ws: dict, master) -> dict:
    """Game-level consequences: act bosses, pool sizes per tier, starter availability."""
    def summary(doc):
        data = doc["data"]
        acts = enc.acts_view(data["rules"], data["encounter_pool"])
        out = {"acts": [{"act": a["act"], "size": a["size"], "boss": a["boss"], "boss_by_element": a["boss_by_element"]}
                        for a in acts["acts"]],
               "relics_by_rarity": {r: sum(1 for x in data["relics"] if x.get("rarity") == r) for r in fx.RARITIES},
               "events": len(data["events"])}
        if master is not None and master.tier_table is not None:
            chars = catalog.character_pool(master, data["rules"], data["pool_overlay"], doc["policy"])
            out["characters_by_tier"] = {str(t): sum(1 for c in chars if c["in_pool"] and c["effective_tier"] == t) for t in range(1, 5)}
            out["starter_by_element"] = {str(el): sum(1 for c in chars if c["in_pool"] and c["element"] == el and c["starter_derived"])
                                         for el in fx.ELEMENTS}
        return out
    return {"before": summary(base), "after": summary(ws)}


def file_changes(before_files: dict[str, bytes], after_files: dict[str, bytes]) -> list[dict]:
    names = sorted(set(before_files) | set(after_files))
    out = []
    for name in names:
        b, a = before_files.get(name), after_files.get(name)
        if b == a:
            continue
        out.append({"name": name, "before": jsonio.sha256(b) if b is not None else None,
                    "after": jsonio.sha256(a) if a is not None else None,
                    "server_reads": next((s.server_reads for s in RUNTIME_FILES if s.release == name), name.startswith("data/"))})
    return out
