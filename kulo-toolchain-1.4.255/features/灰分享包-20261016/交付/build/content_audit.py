#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""离线审计我方 1.4.131–219 中的测试数据与新增副本，仅写本工作区 audit。"""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import zipfile

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
if ROOT.name == "交付":
    ROOT = ROOT.parent
AUDIT = ROOT / "audit"
TOOLKIT = Path("D:/WF/out/kulo-patch-toolkit")
STORE = TOOLKIT / "store131"
OURS_MANIFEST = Path("D:/WF/out/角色超限-120/localsrv219/assets/asset-patch/manifest.json")
ZIP_ROOTS = [Path("D:/WF/out/碧-1.4.216/localsrv-216/assets/asset-patch/active"),
             Path("D:/WF/out/角色超限-120/patch")]
sys.path.insert(0, "D:/WF/startpoint-cn-kulo/tools/fantasy-gauntlet-mod-tools")
import wf_quest_lib as q


def member(logical):
    h = hashlib.sha1((logical + q.SALT).encode()).hexdigest()
    return "production/upload/" + h[:2] + "/" + h[2:]


def csvrow(text):
    return next(csv.reader(io.StringIO(text)))


def parse(raw):
    if raw is None:
        return None
    try:
        value = q.parse_node(raw)
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def get_logicals():
    result = {}
    pathlist = Path("D:/WF/startpoint-cn-kulo/tools/fantasy-gauntlet-mod-tools/WF_PATHLIST_recovered.txt")
    for line in pathlist.read_text("utf-8-sig").splitlines():
        lp = line.strip()
        if lp and not lp.startswith("#"):
            result[member(lp)] = lp
    for base in [TOOLKIT / "cursed_abyss/patch", TOOLKIT / "pilot"]:
        for f in base.rglob("*.integrity.json"):
            data = json.loads(f.read_text("utf-8-sig"))
            for m, lp in data.get("logical_paths", {}).items():
                result[m] = lp
    return result


def load_chain():
    manifest = json.loads(OURS_MANIFEST.read_text("utf-8-sig"))
    zips = []
    for entry in manifest["patches"]:
        try:
            version = int(entry["version"].split(".")[-1])
        except ValueError:
            continue
        if not 131 <= version <= 219 or not entry.get("enabled", True):
            continue
        for name in entry.get("chain") or [entry["archive"]]:
            found = [d / name for d in ZIP_ROOTS if (d / name).exists()]
            if not found:
                raise FileNotFoundError(name)
            zips.append((version, found[0]))
    return zips


def base_raw(m):
    p = STORE / m
    return p.read_bytes() if p.exists() else None


def read_index(index, m):
    if m not in index:
        return base_raw(m)
    with zipfile.ZipFile(index[m]) as z:
        return z.read(m)


def leaves(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaves(child, path + (str(key),))
    else:
        yield path, value


def build_exclusions(chain, logicals):
    # 157 虽名为 record-fix，实际是公共魂珠图集修复，不能按边删除。
    bad_versions = {153: "GM 武器", 155: "训练假人", 156: "训练假人", 177: "训练假人",
                    178: "训练假人", 180: "训练假人", 181: "训练假人", 193: "GM 武器"}
    index, rules, full_members = {}, {}, {}
    evidence = []
    for version, archive in chain:
        # 193 的第二包是杰拉尔德语音，保留。
        bad = version in bad_versions and (version != 193 or "gm-weapon6" in archive.name)
        with zipfile.ZipFile(archive) as z:
            for m in z.namelist():
                if m.endswith("/"):
                    continue
                if bad:
                    old, new = parse(read_index(index, m)), parse(z.read(m))
                    if new is not None:
                        old = old or {}
                        changed = [k for k in set(old) | set(new) if old.get(k) != new.get(k)]
                        for key in changed:
                            item = {"member": m, "logical_path": logicals.get(m, "未核实"), "key_path": [str(key)],
                                    "action": "restore_baseline", "reason": bad_versions[version],
                                    "source_archives": [archive.name], "introduced": key not in old}
                            ident = (m, str(key))
                            if ident in rules:
                                rules[ident]["source_archives"].append(archive.name)
                            else:
                                rules[ident] = item
                    else:
                        full_members[m] = {"member": m, "logical_path": logicals.get(m, "未核实"),
                                           "action": "restore_baseline", "reason": bad_versions[version],
                                           "source_archive": archive.name}
                index[m] = archive
    ids = [str(v) for v in range(5990001, 5990007)]
    pattern = re.compile(r"(?<!\d)(?:" + "|".join(ids) + r")(?!\d)")
    references = []
    dummy_markers = {r["key_path"][0] for r in rules.values()
                     if r["reason"] == "训练假人" and not r["key_path"][0].isdigit()}
    dummy_markers.update({"boss_typed_waraboss", "boss_super_waraboss", "wf_dummy_energy", "wf_dummy_skill_charge_half"})
    test_references = []
    for m in sorted(index):
        value = parse(read_index(index, m))
        if value is None:
            continue
        for path, v in leaves(value):
            haystack = "/".join(path) + " " + str(v)
            markers = sorted(x for x in dummy_markers if x in haystack)
            if markers:
                test_references.append({"member": m, "logical_path": logicals.get(m, "未核实"),
                                        "key_path": list(path), "markers": markers,
                                        "source_archive": index[m].name})
                ident = (m, path[0])
                if ident not in rules:
                    rules[ident] = {"member": m, "logical_path": logicals.get(m, "未核实"), "key_path": [path[0]],
                                    "action": "restore_baseline", "reason": "训练假人后续引用",
                                    "source_archives": [index[m].name], "introduced": path[0] not in (parse(base_raw(m)) or {})}
            matches = sorted(set(pattern.findall("/".join(path) + " " + str(v))))
            if not matches:
                continue
            references.append({"member": m, "logical_path": logicals.get(m, "未核实"),
                               "key_path": list(path), "ids": matches, "value": v,
                               "source_archive": index[m].name})
            # Nested tables are kept at top-level gameplay object to avoid malformed internal rows.
            ident = (m, path[0])
            if ident not in rules:
                rules[ident] = {"member": m, "logical_path": logicals.get(m, "未核实"), "key_path": [path[0]],
                                "action": "restore_baseline", "reason": "GM 武器后续引用",
                                "source_archives": [index[m].name], "introduced": path[0] not in (parse(base_raw(m)) or {})}
    rows = sorted(rules.values(), key=lambda r: (r["logical_path"], r["key_path"]))
    report = {"policy": "恢复共同祖先对应键或成员；共同祖先不存在时删除。灰已有键如有碰撞须保留并另记冲突。",
              "gm_weapon_ids": ids, "test_quest_ids": [str(v) for v in range(1103, 1124)],
              "excluded_rows": rows, "excluded_members": sorted(full_members.values(), key=lambda r: r["member"]),
              "gm_references": references, "test_references": test_references,
              "retained_shared_fix": {"edge": "1.4.156→1.4.157",
              "reason": "文件名 typed-dummies-record-fix，实际修复公共 item/sprite_sheet 魂珠图集；保留。"}}
    return report, index


def make_schedule(index):
    sys.path.insert(0, str(ROOT / "交付/build"))
    import common as c
    hui = c.View("hui")
    quests, anchors = [], []
    hme = "master/quest/event/hard_multi_event.orderedmap"
    events = parse(read_index(index, member(hme))) or {}
    for lp, kind in [("master/quest/boss_battle_quest.orderedmap", "主线 Boss 领主战"),
                     ("master/quest/event/hard_multi_event_quest.orderedmap", "共同决战")]:
        m = member(lp)
        before, after = parse(base_raw(m)) or {}, parse(read_index(index, m)) or {}
        base_leaves = dict(leaves(before))
        hui_ids = {csvrow(v)[0] for _, v in leaves(hui.load(lp) or {})}
        for path, value in leaves(after):
            r = csvrow(value)
            if path in base_leaves or r[0] in hui_ids:
                continue
            if r[0] == "1098001":
                anchors.append({"quest_id": r[0], "reason": "魂珠兑换商店隐藏锚点，非可玩副本，不计入重新排期清单。"})
                continue
            quest = {"quest_id": r[0], "name": r[2].replace(" ::quest_rank::", ""), "stored_name": r[2],
                     "kind": kind, "table": lp, "key_path": list(path), "rank": path[-1],
                     "start": r[5], "end": r[6], "condition_cells_c7_c31": r[7:32],
                     "condition_note": "未核实", "status": "需重新排期，开放时间由灰定"}
            if kind == "主线 Boss 领主战":
                if r[7] == "0":
                    quest["condition_note"] = f"主线 {r[8]}-{r[9]}-{r[10]} 通关（quest id {r[11]}）"
                elif r[7] == "2":
                    quest["condition_note"] = f"前置领主战 quest id {r[11]} 通关（章/节点/档 {r[8]}/{r[9]}/{r[10]}）"
                quest["condition_note"] += f"；推荐属性代码 {r[72]}；c73={r[73]}（条件语义未核实）"
            else:
                event = csvrow(events[path[0]])
                quest["event_id"] = path[0]
                quest["event_name"] = event[2]
                quest["event_start"] = event[23]
                quest["event_end"] = event[24]
                quest["event_condition_cells_c10_c22"] = event[10:23]
                quest["condition_note"] = ("关卡 c7–c31 无显式前置（均为空或 (None)）；"
                                           f"活动 c10={event[10]}、c14={event[14]}、c18={event[18]}、c19={event[19]}；"
                                           "活动字段运行时含义未核实")
            quests.append(quest)
    return {"basis": "我方 1.4.219 相对共同祖先新增，排除灰 1.4.136 已有 quest id；保持源时间不修改。",
            "count": len(quests), "playable_quests": sorted(quests, key=lambda x: int(x["quest_id"])),
            "nonplayable_anchors": anchors,
            "coverage": {"added_quest_tables": ["boss_battle_quest: 46=45可玩+1098001商店隐藏锚点",
                                               "hard_multi_event_quest: 27可玩", "practice_quest: 21训练关卡，全部剔除"],
                         "cursed_paradox_edges_149_152": "逐包成员核实，无 quest 表；仅武器、强化、魂珠、商店、独有状态、DSL和图标，不新增副本。"},
            "time_semantics": "(None) 为源表未填结束时间；时间时区未核实。未调用客户端或服务器。"}


def dump(name, value):
    AUDIT.mkdir(parents=True, exist_ok=True)
    (AUDIT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")


def make_notes(exclusions, schedule, index):
    rows = exclusions["excluded_rows"]
    lines = ["# 分享包内容审计", "", "本审计只读取固定本地输入，没有联网或调用服务器、模拟器。",
             "", "## 排除策略", "", f"GM 武器 5990001–5990006 共 6 把；训练关卡 1103–1123 共 21 个。",
             f"客户端逐键排除 {len(rows)} 个表键、逐成员排除 {len(exclusions['excluded_members'])} 个独立资源。",
             "这些键和资源恢复共同祖先值；共同祖先不存在时删除。灰已有内容优先，任何灰侧碰撞由主合并记录。",
             "GM 表数据涉及 ability_soul、equipment、equipment_status、item、custom_ability_string，另有专用 direct_hits DSL。",
             "训练数据包括 practice 入口、folder 101、boss/field/zone/level/funnel/state/variable、专用即时道具、地形和 DSL。",
             "", "## 逐项排除的训练副本", "", "| quest id | 名称 |", "|---|---|"]
    practice = parse(read_index(index, member("master/quest/practice/practice_quest.orderedmap")))
    for qid in exclusions["test_quest_ids"]:
        lines.append(f"| {qid} | {csvrow(practice[qid])[2]} |")
    lines += ["", "## 逐键排除清单", "", "| 表逻辑路径 | 键 | 原因 |", "|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['logical_path']} | {'/'.join(r['key_path'])} | {r['reason']} |")
    lines += ["", "## 整成员排除清单", "", "| 逻辑路径 | CDN 成员 | 原因 |", "|---|---|---|"]
    for r in exclusions["excluded_members"]:
        lines.append(f"| {r['logical_path']} | {r['member']} | {r['reason']} |")
    lines += ["", "## 后续引用审查", "", "对我方链最终改动成员中可解码表的键和叶值扫描精确 GM id 5990001–5990006，",
              f"找到 {len(exclusions['gm_references'])} 个叶值命中；这些命中均已纳入排除策略。"]
    later = [r for r in rows if r["reason"].endswith("后续引用")]
    if later:
        lines += ["", "后续边追加的引用："]
        for r in later:
            lines.append(f"- {r['logical_path']} / {'/'.join(r['key_path'])}：{r['reason']}，源 {', '.join(r['source_archives'])}。")
    else:
        lines.append("未发现原始引入边以外的 GM/训练引用。")
    lines += ["", "1.4.156→1.4.157 虽名 typed-dummies-record-fix，实际只有公共 item/sprite_sheet 图集；",
              "其功能为魂珠图集修复，保留。1.4.192→193 的第二分包为杰拉尔德语音，同样保留。",
              "1.4.153→154 modchar-stack-cap 是角色平衡：无上限成长改最多3次、单次数值×1.3并封顶；不是调试，保留。",
              "1.4.196→197 / 197→198 平衡源脚本显式排除 five-boss-atlas-slim 测试边；本链不含该边。",
              "1.4.198→199 / 201→202 为真实高难 Boss/Funnel 等级及伴生变量补行，保留；1.4.200→201 的训练道具等级键另行剔除。",
              "", "## 需重新排期的决战副本", "",
              f"共 {schedule['count']} 个可玩 quest id，其中主线 Boss 领主战 "
              f"{sum(q['kind']=='主线 Boss 领主战' for q in schedule['playable_quests'])} 个、共同决战 "
              f"{sum(q['kind']=='共同决战' for q in schedule['playable_quests'])} 个。",
              "以下每一项均为 **需重新排期，开放时间由灰定**；本包保留源表时间，不做排期决定。",
              "源表没有给出时区，时间时区未核实；(None) 表示未填结束时间。关卡原名里的 ::quest_rank:: 为客户端替换标记。",
              "", "| quest id | 副本 | 当前开放时间 | 当前条件 |", "|---|---|---|---|"]
    for r in schedule["playable_quests"]:
        time = f"{r['start']} → {r['end']}"
        if "event_start" in r:
            time += f"；活动 {r['event_id']}：{r['event_start']} → {r['event_end']}"
        name = f"{r['name']}（{r['kind']}，档位 {r['rank']}）"
        lines.append(f"| {r['quest_id']} | {name} | {time} | {r['condition_note']} |")
    lines += ["", "1098001 是魂珠兑换商店隐藏过期锚点，用来满足客户端节点构造；不作为可玩副本排期。",
              "已扫描我方终态所有改过的 master/quest/*quest.orderedmap：新增 boss_battle_quest 46叶（45可玩+1隐藏锚点）、hard_multi_event_quest 27叶、practice_quest 21叶（全部训练剔除）。",
              "149→150、150→151、151→152 的诅咒r4/深渊二期/PARADOX包逐成员核实没有 quest 表，因此不增加副本排期项。",
              "完整源条件列已保存在 schedule.json，包括关卡 c7–c31 和共同决战活动 c10–c22，无法确认的运行时含义明确写为未核实。", ""]
    (AUDIT / "content-notes.md").write_text("\n".join(lines), "utf-8")


def export_annex():
    out = ROOT / "交付/附录"
    out.mkdir(parents=True, exist_ok=True)
    text = (AUDIT / "content-notes.md").read_text("utf-8")
    exclusions, schedule = text.split("## 需重新排期的决战副本", 1)
    (out / "排除明细.md").write_text(exclusions.replace("# 分享包内容审计", "# 排除明细") + "\n", "utf-8")
    (out / "副本排期.md").write_text("# 需重新排期的决战副本\n" + schedule, "utf-8")
    for name in ["exclusions.json", "schedule.json"]:
        (out / name).write_bytes((AUDIT / name).read_bytes())


def main():
    chain, logicals = load_chain(), get_logicals()
    exclusions, index = build_exclusions(chain, logicals)
    dump("exclusions.json", exclusions)
    schedule = make_schedule(index)
    dump("schedule.json", schedule)
    make_notes(exclusions, schedule, index)
    export_annex()
    tables = {}
    for lp in ["master/quest/boss_battle_quest.orderedmap", "master/quest/boss_battle_stage_node.orderedmap",
               "master/quest/event/hard_multi_event.orderedmap", "master/quest/event/hard_multi_event_quest.orderedmap",
               "master/quest/event/event_folder_events.orderedmap", "master/quest/practice/practice_quest.orderedmap"]:
        m = member(lp)
        before, after = parse(base_raw(m)) or {}, parse(read_index(index, m)) or {}
        tables[lp] = {"member": m, "added": {k: v for k, v in after.items() if k not in before},
                      "modified": {k: v for k, v in after.items() if k in before and before[k] != v}}
    dump("quest-table-delta.json", tables)
    print(json.dumps({"excluded_rows": len(exclusions["excluded_rows"]), "excluded_members": len(exclusions["excluded_members"]),
                      "gm_references": len(exclusions["gm_references"]),
                      "schedule_count": schedule["count"],
                      "quest_added": {k: len(v["added"]) for k, v in tables.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit("历史来源分析工具，不再直接输出旧剔除规则；第三轮请运行build_all.py或build_inclusion_r3.py。")
