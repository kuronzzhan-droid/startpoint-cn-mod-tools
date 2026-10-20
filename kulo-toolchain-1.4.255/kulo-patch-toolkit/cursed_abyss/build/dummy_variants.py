# -*- coding: utf-8 -*-
"""全伤害木人（1111 单体 / 1112 多体）各加两个变体：能量瓶（场地道具每 5 秒刷新，拾取全队技能槽 +50%）、
伤害圈（以木人为中心，每秒对范围内造成最大 HP 1% 的比例伤害，每 15 秒扩大一档）。叠加在 1.4.179 上。"""
import copy, hashlib, json, os, shutil, zipfile, zlib
os.environ.setdefault("WF_TIP", "180")
from live149 import *  # noqa
import wf_cursed_weapons_r4 as W
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import detect_style, dump_like
from typed_dummies import csv_text, DSL_DIR
import typed_dummies_v2 as V2

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.179-1.4.180-1-dummy-variants-local.zip"
LP = dict(V2.LP, dii="master/battle/yakumono/direct_instant_item.orderedmap",
          eii="master/battle/item/executable_instant_item.orderedmap",
          eii_level="master/battle/item/executable_instant_item_level.orderedmap")
ITEM_TEMPLATE = "skill_charge_middle"  # 新道具的 eii 行与 eii_level 行都从该模板复制
TERRAIN_SRC = "battle/terrain/practice_quest/practice_waraboss_tough"
TERRAIN_NEW = "battle/terrain/practice_quest/wf_dummy_energy"
ITEM = "wf_dummy_skill_charge_half"
ITEM_ACTION = "battle/action/item/action/" + ITEM
REPOP = 300
ITEM_SPOTS = [(68, 395), (130, 412), (192, 395)]
RADII = [150, 300, 450, 600, 900]
STAGE = 900
VARIANTS = [
    ("1113", "1111", "practice_all_damage_dummy", "practice_energy_dummy", "能量瓶木人·无", "energy"),
    ("1114", "1111", "practice_all_damage_dummy", "practice_zone_dummy", "伤害圈木人·无", "zone"),
    ("1115", "1112", "practice_all_damage_dummies", "practice_energy_dummies", "能量瓶木人们·无", "energy"),
    ("1116", "1112", "practice_all_damage_dummies", "practice_zone_dummies", "伤害圈木人们·无", "zone"),
]
NL = chr(10)


def S(v):
    return [{"min": v, "max": v}]


def hit(r):
    return ["Command", ["CreateHitArea", "*", -17, ["AB"], 0, 0, 0, True, True, ["Circle", S(r)], ["Center"], ["Center"],
                        ["Single"], ["SpecifyHitAreaLifetimeDirectly", 10], ["CalculatedUsingMaxNumOfHits", 1], ["Some", S(1)],
                        False, True, ["None"], 0, ["Block", []], 1, 2,
                        ["Block", [["Command", ["CreateRatioAttack", 2, 2, S(0.01)]]]], 0, 0, ["None"]]]


def zone_events():
    ev = []
    for k, r in enumerate(RADII):
        last = k == len(RADII) - 1
        rep = ["Event", ["Repeat", 60, 9999999 if last else STAGE // 60, "*", ["Block", [hit(r)]]]]
        ev.append(rep if k == 0 else ["Event", ["Wait", k * STAGE, "*", ["Block", [rep]]]])
    return ev


def assert_item_levels(T):
    """每个 executable_instant_item 键、每个 direct_instant_item 引用的道具（c1 非空）都必须有 executable_instant_item_level 行。"""
    lv = set(T["eii_level"])
    miss_eii = sorted(set(T["eii"]) - lv)
    miss_dii = sorted({row(v)[1] for v in T["dii"].values()} - {""} - lv)
    assert not miss_eii and not miss_dii, ("executable_instant_item_level 缺行", miss_eii, miss_dii)


def main():
    T = {k: load(v) for k, v in LP.items()}
    BASE = copy.deepcopy(T)
    files, report = {}, []
    assert ITEM not in T["eii"] and ITEM not in T["dii"]
    src_eii = T["eii"][ITEM_TEMPLATE]
    fo = src_eii.split(",")[0]
    T["eii"][ITEM] = fo + "," + ITEM_ACTION + (NL if src_eii.endswith(NL) else "")
    assert row(T["dii"]["skill_charge_large_wait_short"]) == ["0", "skill_charge_large", "", "300"]
    T["dii"][ITEM] = csv_text([["0", ITEM, "", str(REPOP)]], T["dii"]["skill_charge_large_wait_short"])
    # 1.4.201 根修：新增的即时道具必须同时有 executable_instant_item_level 行（缺行 = 拾取时 C8601）。
    for new_item in sorted((set(T["eii"]) - set(BASE["eii"])) | {row(v)[1] for k, v in T["dii"].items() if k not in BASE["dii"]} - {""}):
        assert new_item not in T["eii_level"], new_item
        T["eii_level"][new_item] = T["eii_level"][ITEM_TEMPLATE]
    assert_item_levels(T)
    item_tree = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0, ["Block", [
        ["Command", ["FindAllSubjects", 0, 33, [], [], [], [], [], ["DoNothing"],
                     ["Block", [["Command", ["AddSkillPoint", 0, S(0.5)]]]]]]]]]
    ref = wf_dsl.parse_dsl(zlib.decompress(read_raw("battle/action/item/action/skill_charge_large.action.dsl.amf3.deflate")[0], -15))["tree"]
    assert ref[11][1][0][1][:3] == ["FindAllSubjects", 0, 33] and ref[11][1][0][1][9][1][0][1][0] == "AddSkillPoint"
    assert not W.dsl_signature_problems(item_tree)
    files[ITEM_ACTION + ".action.dsl.amf3.deflate"] = encode_tree(item_tree)
    traw = read_raw(TERRAIN_SRC + ".amf3.deflate")[0]
    terr = wf_dsl.parse_dsl(zlib.decompress(traw, -15))["tree"]
    assert not any("INSTANT_ITEM" in str(o.get("type")) for L in terr["layers"] for o in L.get("objects", []))
    groups = [L for L in terr["layers"] if L.get("type") == "objectgroup"]
    assert len(groups) == 1
    L0 = groups[0]
    nid = max(int(o["id"]) for o in L0["objects"]) + 1
    for x, y in ITEM_SPOTS:
        L0["objects"].append({"id": nid, "type": "DIRECT_INSTANT_ITEM#" + ITEM.upper() + "_ALWAYS", "name": "", "visible": True,
                              "x": x, "y": y, "width": 12, "height": 12, "rotation": 0, "ellipse": True})
        nid += 1
    raw = wf_dsl.encode_amf3(terr)
    assert wf_dsl.parse_dsl(raw)["tree"] == terr
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    files[TERRAIN_NEW + ".amf3.deflate"] = c.compress(raw) + c.flush()
    for qid, sq, skey, key, cn, kind in VARIANTS:
        assert qid not in T["practice"]
        for k in ("field", "zone", "boss", "level"):
            assert key not in T[k], (k, key)
        src = row(T["practice"][sq])
        assert src[110] == skey
        orders = [int(row(v)[1]) for v in T["practice"].values() if row(v)[0] == src[0]]
        r = list(src)
        r[1], r[2], r[110] = str(max(orders) + 1), cn, key
        T["practice"][qid] = csv_text([r], T["practice"][sq])
        f = row(T["field"][skey])
        assert f[1] == TERRAIN_SRC
        f[2] = key
        if kind == "energy":
            f[1] = TERRAIN_NEW
        T["field"][key] = csv_text([f], T["field"][skey])
        z = row(T["zone"][skey]["0"])
        z[24] = z[26] = key
        T["zone"][key] = {"0": csv_text([z], T["zone"][skey]["0"])}
        b = row(T["boss"][skey]["100"])
        if kind == "zone":
            prog = DSL_DIR + "$zone_" + key
            tree = copy.deepcopy(dsl_tree(b[109]))
            tree[11][1].extend(zone_events())
            pr = W.dsl_signature_problems(tree)
            assert not pr, pr
            d = encode_tree(tree)
            assert wf_dsl.parse_dsl(zlib.decompress(d, -15))["tree"] == tree
            files[wf_dsl.dsl_logical(prog)] = d
            b[109] = prog
        b[1] = cn.split("·")[0]
        T["boss"][key] = {"100": csv_text([b], T["boss"][skey]["100"])}
        T["level"][key] = T["level"][skey]
        report.append({"quest": qid, "src": sq, "name": cn, "kind": kind, "key": key, "folder": r[0], "order": r[1],
                       "program": b[109], "terrain": f[1]})
    assert_item_levels(T)
    for k, lp in LP.items():
        d = q.build_node(T[k])
        back = q.parse_node(d)
        assert back == T[k] and all(back[x] == v for x, v in BASE[k].items())
        if back != BASE[k]:
            files[lp] = d
    members = {member(lp): d for lp, d in files.items()}
    path = OUT / "patch" / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members):
            zf.writestr(m, members[m])
    blob = path.read_bytes()
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
             "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.179", "version": "1.4.180",
             "quests": report}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + NL, "utf-8")
    name = "practice_quest.json"
    raw = (ASSETS / name).read_bytes()
    if b'"1112"' not in raw:
        raw = (OUT / "server15" / name).read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", NL)
    value = json.loads(text)
    assert "1111" in value and "1112" in value
    added = {}
    for rep in report:
        assert rep["quest"] not in value
        e = copy.deepcopy(value[rep["src"]])
        e["name"] = rep["name"]
        value[rep["quest"]] = e
        added[rep["quest"]] = e
    style = detect_style(text)
    if dump_like(json.loads(text), style) == text:
        out = dump_like(value, style)
    else:
        end = len(text.rstrip())
        pe = len(text[:end - 1].rstrip())
        out = text[:pe] + "," + NL + NL.join(json.dumps(added, ensure_ascii=False, indent=2).splitlines()[1:-1]) + text[pe:]
    assert json.loads(out) == value
    s17 = OUT / "server17"
    shutil.rmtree(s17, ignore_errors=True)
    s17.mkdir()
    (s17 / name).write_bytes((out.replace(NL, "\r\n") if crlf else out).encode("utf-8"))
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
