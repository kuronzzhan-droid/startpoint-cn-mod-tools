"""Read gameplay evidence for each new or modified character, using immutable inputs."""
from __future__ import annotations
import json
from wf.paths import REPOSITORY
import wf_mod_tool as core
from .scan_facts import (SYSTEM_KINDS, PF_OVERRIDE, INVOKE_SKILL, CHARGE_CAP_UNIQUE,
                        KYLE_UNIQUES, SUNBURN_UNIQUE, DSL_MARKERS, PER_CHAR_APK,
                        UNISON_PRE, UNISON_TRIG, Layout, cell, dsl_facts, dsl_logical)
from .scan_source import provenance


def scan_characters(src, server_assets):
    enum_map = json.loads((REPOSITORY / "ability_enum_map.json").read_text("utf-8"))
    lay = {"ability": Layout(enum_map, "ability"), "leader": Layout(enum_map, "leader_ability")}
    baseline = src.baseline

    T = {n: src.table(n) for n in ("character", "ability", "leader", "skill", "switched", "condition",
                                    "power_flip", "strings")}
    O = {n: src.table(n, True) for n in ("character", "ability", "leader", "skill", "condition", "power_flip")}
    AWAKE = "master/mission/character_awake_event.orderedmap"
    awake, awake0 = src.table(AWAKE), src.table(AWAKE, True)
    overlimit = src.server_table(server_assets / "character_overlimit.json")
    ol_chars = {str(c) for c in overlimit.get("characters", [])}
    strings = T["strings"]
    mod_codes = set()

    chars = src.characters()
    for c in chars:
        mod_codes.add(T["character"][c["id"]][0][0])

    tree_cache: dict[str, dict | None] = {}

    current: dict = {}

    def facts(path: str):
        lg = dsl_logical(path)
        result = _facts(lg)
        if result is None:
            src.missing_dsl.add(lg)
        if result and "cmds" in result and current.get("rec") is not None:
            current["rec"]["markers"] |= {DSL_MARKERS[c] for c in result["cmds"] if c in DSL_MARKERS}
        return result

    def _facts(lg: str):
        if lg not in tree_cache:
            try:
                t = src.tree(lg)
                tree_cache[lg] = dsl_facts(t) if t is not None else None
            except (OSError, ValueError, TypeError) as exc:
                raise ValueError(f"cannot scan DSL {lg}: {exc}") from exc
        return tree_cache[lg]

    official_cache: dict[str, str] = {}

    def effect_origin(effect: str, code: str) -> str:
        if effect in official_cache:
            return official_cache[effect]
        result = None
        for suf in (".parts.amf3.deflate", ".timeline.amf3.deflate"):
            digest = core.sha1_path(effect + suf)
            rel = digest[:2] + "/" + digest[2:]
            for root in ("common", "medium", "android"):
                if baseline.get(root, rel) is not None:
                    result = "官方CDN"
        if result is None:
            if any(m and m in effect for m in mod_codes) or "cnmod" in effect:
                result = "自制(code_name目录)"
            else:
                layer = src.locate(effect + ".parts.amf3.deflate") or src.locate(effect + ".timeline.amf3.deflate")
                if layer is None:
                    result = "APK内置(推断官方)"
                elif layer == "store131":
                    # store131 = 1.4.131 共用链快照,混有官方 APK 件与早期 MOD:官方标准目录名判官方
                    folder = effect.rsplit("/", 2)[-2]
                    result = ("官方(APK件,store131)" if folder.startswith("effect_") else "自制(≤1.4.131)")
                else:
                    result = "自制(补丁边" + layer[:40] + ")"
        official_cache[effect] = result
        return result

    prov = provenance(src, core, [c["id"] for c in chars], T)
    def load_json(name):
        f = server_assets / name
        return src.server_table(f)
    awake_ext = load_json("character_awake_extension.json")
    awake_missions = {str(v[0][1]) for v in load_json("mission_char_awake_cnmod.json").values() if v and len(v[0]) > 1}

    out = []
    for c in chars:
        cid = c["id"]
        row = T["character"][cid][0]
        code = row[0]
        rec = {"id": cid, "code": code, "name": c["name"], "title": c["title"], "origin": c["origin"],
               "pf_overrides": [], "system": set(), "invoke": [], "uniques": set(), "unison": set(),
               "awake_rows": [], "desc_override": [], "changed": [], "dsl": [], "notes": [], "markers": set()}
        current["rec"] = rec
        groups = [("ability", f"能力{i + 1}", k) for i, k in enumerate(row[19:25])] + [("leader", "队长", cell(row, 17))]
        for table, slot, key in groups:
            if not key or key == "(None)":
                continue
            rows = T[table].get(key, [])
            if c["origin"] == "modified" and rows != O[table].get(key):
                rec["changed"].append(slot)
            L = lay[table]
            for n, r in enumerate(rows):
                trig = cell(r, L.trigger)
                block = {"0": "instant", "1": "during"}.get(trig)
                ak = cell(r, L.awake_kind)
                if ak in ("1", "2"):
                    rec["awake_rows"].append(f"{slot}#{n}:{'替换' if ak == '1' else '追加'}")
                for p in ("precondition1", "precondition2", "precondition3"):
                    pk = cell(r, L.col(p, "kind"))
                    if pk in UNISON_PRE:
                        rec["unison"].add(f"{slot}合击前置{pk}")
                tk = cell(r, L.col("instant_trigger", "kind")) if block == "instant" else cell(r, L.col("during_trigger", "kind"))
                if block == "instant" and tk in UNISON_TRIG:
                    rec["unison"].add(f"{slot}合击触发{tk}")
                for uc in L.unique_cols():
                    v = cell(r, uc)
                    if v and v not in ("(None)", "0") and v.isdigit():
                        rec["uniques"].add(v)
                sid = cell(r, 0)
                if sid and ("desc_override_" + sid) in strings:
                    rec["desc_override"].append(sid)
                if block is None:
                    continue
                kind = cell(r, L.col(f"{block}_content", "kind"))
                if (block, kind) in SYSTEM_KINDS:
                    rec["system"].add(SYSTEM_KINDS[(block, kind)])
                if (block, kind) in PF_OVERRIDE:
                    pid = cell(r, L.col(f"{block}_content", "powerflip_override.id"))
                    lv = cell(r, L.col(f"{block}_content", "powerflip_override.levels"))
                    rec["pf_overrides"].append({"slot": slot, "row": n, "kind": kind, "id": pid, "levels": lv,
                                                "awake": ak, "main_only": table == "leader" or kind in ("722", "419")})
                if (block, kind) == INVOKE_SKILL:
                    sk = cell(r, L.col("instant_content", "string_id"))
                    path = cell(r, L.col("instant_content", "action_path"))
                    rec["invoke"].append({"slot": slot, "skill": sk, "path": path})
                    if path:
                        f = facts(path)
                        if f and "uniques" in f:
                            rec["uniques"] |= f["uniques"]
                            if f["bta"]:
                                rec["dsl"].append(f"629:{sk} buffTargetAs{sorted(f['bta'])}")
        # 技能 DSL
        sk_rows = T["skill"].get(cell(row, 8), {})
        if c["origin"] == "modified" and sk_rows != O["skill"].get(cell(row, 8)):
            rec["changed"].append("技能")
        for lvl, rows in sk_rows.items():
            if rows and len(rows[0]) > 7 and rows[0][7] not in ("", "(None)"):
                f = facts(rows[0][7])
                if f and "uniques" in f:
                    rec["uniques"] |= f["uniques"]
                    if f["bta"]:
                        rec["dsl"].append(f"技能Lv{lvl} buffTargetAs{sorted(f['bta'])}")
        sw = cell(row, 14)
        rec["switch"] = sw
        # PF 覆盖 DSL 与特效来源
        for o in rec["pf_overrides"]:
            paths = T["power_flip"].get(o["id"], [[]])[0] if o["id"] in T["power_flip"] else []
            o["official_key"] = o["id"] in O["power_flip"]
            o["lv4"] = "4" in [x.strip() for x in o["levels"].replace('"', "").split(",")]
            eff = {}
            bta = set()
            for p in paths:
                if not p or p.endswith("/empty"):
                    continue
                f = facts(p)
                if f and "effects" in f:
                    for e in f["effects"]:
                        eff[e] = effect_origin(e, code)
                    rec["uniques"] |= f["uniques"]
                    bta |= f["bta"]
                    if "attack_to_hostile_hit" in json.dumps(sorted(f["cmds"])):
                        o["marker"] = True
            o["effects"] = eff
            o["bta"] = sorted(bta)
            kinds = {v.startswith("自制") for v in eff.values()}
            o["fx"] = ("无直接特效路径" if not kinds else "全自制" if kinds == {True}
                       else "官方复用" if kinds == {False} else "自制+官方混用")
        # 固有状态串
        ustr = {}
        for u in sorted(rec["uniques"]):
            r = T["condition"].get(u)
            if r:
                ustr[u] = {"string_id": r[0][0], "name": cell(r[0], 1), "max": cell(r[0], 4),
                           "official": u in O["condition"]}
        rec["unique_rows"] = ustr
        apk = set(rec["system"])
        for u, info in ustr.items():
            s = info["string_id"]
            if s.startswith("fever:items:"):
                apk.add("Fever箭头换道具(APK#90-93)")
            if s.startswith("hidden_"):
                apk.add("hidden_固有隐藏(APK#58)")
            if s.startswith("wfx:"):
                apk.add("WFX框架(未上)")
        if CHARGE_CAP_UNIQUE in rec["uniques"]:
            apk.add("充能上限固有13999010(APK#53)")
        if rec["uniques"] & KYLE_UNIQUES:
            apk.add("凯尔直击参数(APK#54/#56)")
        if SUNBURN_UNIQUE in rec["uniques"]:
            apk.add("白晒伤减抗(APK#05)")
        if any(o["lv4"] for o in rec["pf_overrides"]):
            apk.add("PF Lv4(APK#87-89)")
        if any(o.get("bta") for o in rec["pf_overrides"]) or rec["dsl"]:
            apk.add("伤害类型转换buffTargetAs(APK#20)")
        if any(o.get("marker") for o in rec["pf_overrides"]):
            apk.add("PF追加命中静默(APK#55)")
        if "ModDualForm" in cell(row, 5).split(","):
            apk.add("ModDualForm双形态(APK#21)")
        if cid in ol_chars:
            apk.add("超限Lv120(APK#78-86,101,108-111+服务端)")
        if rec["desc_override"]:
            apk.add("文案覆盖desc_override(APK#02)")
        if sw.endswith("_voice_ready"):
            apk.add("通用准备语音轮换(APK#94-96)")
        for x in PER_CHAR_APK.get(cid, []):
            apk.add(x)
        rec["apk"] = sorted(apk)
        rec["overlimit"] = cid in ol_chars
        rec["provenance"] = prov.get(cid, [])
        rec["awake_server"] = [x for x, ok in (("二板联动(character_awake_extension)", cid in awake_ext),
                                               ("自制觉醒任务(mission_char_awake_cnmod)", cid in awake_missions)) if ok]
        rec["awake_event"] = ("自制" if cid in awake and awake.get(cid) != awake0.get(cid)
                              else "官方" if cid in awake else "无")
        rec["mod_dual"] = "ModDualForm" in cell(row, 5)
        out.append(rec)

    return out
