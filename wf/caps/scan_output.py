"""Legacy human-readable matrix plus registered capability projections."""
import csv
import json
from pathlib import Path


def write_capability_matrix(records, capability_ids, target):
    """One stable registry-ID column per observed capability; 1 means evidence exists."""
    with target.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["id", "name", "title", "origin", *capability_ids, "layer_c"])
        for record in records:
            writer.writerow([record["id"], record["name"], record["title"], record["origin"],
                             *(int(c in record["capabilities"]) for c in capability_ids),
                             ";".join(record["layer_c"].get("mech", []))])

def pf_cell(r) -> str:
    if not r["pf_overrides"]:
        return "无"
    parts = []
    for o in r["pf_overrides"]:
        tag = "改" if r["origin"] == "modified" else "新"
        if o.get("official_key"):
            tag = "官方PF键"
        awake = "觉醒" if o["awake"] in ("1", "2") else ""
        parts.append(f"{tag}{'(' + awake + ')' if awake else ''}:{o['id']}[Lv{o['levels']}] FX={o['fx']}")
    return " / ".join(parts)


def awake_cell(r) -> str:
    if r["awake_event"] == "自制":
        extra = "+二板联动" if any("二板" in x for x in r["awake_server"]) else ""
        mission = "+自制觉醒任务" if any("任务" in x for x in r["awake_server"]) else ""
        return f"自制(觉醒事件{mission}{extra})"
    if r["awake_event"] == "官方":
        return "官方"
    if r["awake_rows"]:
        return f"仅数据行{len(r['awake_rows'])}条(无觉醒事件)"
    return "无"


def write_matrix(out, names, target: Path):
    with open(target, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "name", "title", "origin", "特殊强化弹射", "PF Lv4", "Fever扩展", "超限", "觉醒",
                    "APK能力依赖", "B层官方系统自制用法", "独有机制", "来源"])
        for r in out:
            n = names.get(r["id"], {})
            fever = []
            if any(v["string_id"].startswith("fever:items:") for v in r["unique_rows"].values()):
                fever.append("Fever箭头换道具(fever:items)")
            if any("724" in a for a in r["apk"]):
                fever.append("kind724 Fever比例")
            b = []
            if r["invoke"]:
                b.append(f"629 InvokeSkill×{len(r['invoke'])}")
            own = [u for u, v in r["unique_rows"].items() if not v["official"]]
            if own:
                b.append(f"自制固有状态×{len(own)}")
            if r["unison"]:
                b.append("合击位门(" + ",".join(sorted({x[-3:] for x in r['unison']})) + ")")
            if r["switch"] and not r["switch"].endswith("_voice_ready"):
                b.append("切换技能表:" + r["switch"])
            if r["pf_overrides"]:
                b.append("722/419 PF覆盖")
            if r["markers"]:
                b.append("DSL:" + "/".join(sorted(r["markers"])))
            w.writerow([r["id"], r["name"], r["title"], {"new": "new", "modified": "modified"}[r["origin"]],
                        pf_cell(r), "是" if any(o["lv4"] for o in r["pf_overrides"]) else "否",
                        ";".join(fever) or "无", "是(Lv120)" if r["overlimit"] else "否", awake_cell(r),
                        ";".join(r["apk"]) or "无", ";".join(b) or "无",
                        ";".join(n.get("mech", [])) or "(未命名)",
                        ";".join(r["provenance"] + n.get("docs", []))])
