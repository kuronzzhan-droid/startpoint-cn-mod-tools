# -*- coding: utf-8 -*-
"""「超·假人」：官方 7 种练习假人各做一个超级版（叠加在 1.4.180 上）。
- 无属性、四类伤害全吃；boss 与召唤小木人 HP≈90 万亿；
- 开场给 boss：永续不可驱散（全伤害 -50%、3 攻、3 防、弱体抗性 +50%）+ 可驱散 10×防御 +100%；
- 召唤小木人时：给全体敌人挂永续不可驱散那 8 个（刷新无害）；可驱散 10 个只在开场给 boss（避免召唤时把已驱散的补回来）；
- 保留原有移动/出招，所有攻击判定区 ×2，攻击程序整段在 0.5 秒后再放一次（数量 ×2）；
- 场地去掉道具（DIRECT_INSTANT_ITEM）。"""
import copy, hashlib, json, os, shutil, zipfile, zlib
os.environ.setdefault("WF_TIP", "181")
from live149 import *  # noqa
import base149
import wf_cursed_weapons_r4 as W
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import detect_style, dump_like
from typed_dummies import csv_text, DSL_DIR
import typed_dummies_v2 as V2

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.180-1.4.181-1-super-dummies-local.zip"
LP = dict(V2.LP, folder="master/quest/practice/practice_quest_folder.orderedmap",
          state="master/battle/boss/general_boss_state.orderedmap",
          var="master/battle/boss/general_boss_variable.orderedmap")
FOLDER, FOLDER_NAME, FOLDER_THUMB = "101", "超·假人", "quest/thumbnail/practice_quest/wara_6_tafu"
ALL_DMG = DSL_DIR + "$all_damage"
SUPER_DIR = "battle/action/enemy/action/boss_waraboss/boss_super_waraboss"
TYPES = [   # qid, 源 practice qid（取模板行）, 源 boss key, 新 key, 名
    ("1117", "5", "waraboss_katai", "super_dummy_katai", "超·结实假人(经典)"),
    ("1118", "4", "waraboss_hayai", "super_dummy_hayai", "超·极速假人"),
    ("1119", "3", "waraboss_tsuyoi", "super_dummy_tsuyoi", "超·强力假人"),
    ("1120", "2", "waraboss_noroi", "super_dummy_noroi", "超·诅咒假人"),
    ("1121", "1", "waraboss_mamori", "super_dummy_mamori", "超·守护假人"),
    ("1122", "77", "practice_waraboss_tough_attack_colorless", "super_dummy_tough", "超·痛苦假人"),
    ("1123", "67", "practice_waraboss_tough_attack_funnel_colorless", "super_dummy_tough_funnel", "超·痛苦假人们"),
]
NL = chr(10)
SCALE = 2.0
REPEAT_DELAY = 30


def S(v):
    return [{"min": v, "max": v}]


def scale_area(t, n=[0]):
    if isinstance(t, list):
        if t and t[0] == "CreateHitArea" and len(t) > 9 and isinstance(t[9], list):
            sh = t[9]
            if sh[0] == "Circle":
                for c in sh[1]:
                    for k in ("min", "max"):
                        if k in c and isinstance(c[k], (int, float)):
                            c[k] = type(c[k])(c[k] * SCALE) if isinstance(c[k], float) else int(c[k] * SCALE)
                n[0] += 1
            elif sh[0] == "Rectangle":
                for arr in sh[1:3]:
                    for c in arr:
                        for k in ("min", "max"):
                            if k in c and isinstance(c[k], (int, float)):
                                c[k] = c[k] * SCALE if isinstance(c[k], float) else int(c[k] * SCALE)
                n[0] += 1
        for x in t:
            scale_area(x, n)
    return n[0]


def collect(t, kind, acc):
    if isinstance(t, list):
        if t and t[0] == kind:
            acc.append(t)
        for x in t:
            collect(x, kind, acc)
    return acc


def exists(logical):
    m = member(logical)
    return m in base149._INDEX or (base149.STORE131 / m.split("production/upload/")[1]).exists() or m.split("production/upload/")[1] in BUNDLE


import io
_z = zipfile.ZipFile(r"D:/WF/out/item-rarity-frame-20260928/WorldFlipper-item-rarity-frame.apk")
BUNDLE = set(n.replace("production/android_bundle/", "") for n in zipfile.ZipFile(io.BytesIO(_z.read("assets/bundle.zip"))).namelist())


def colorless_ok(tree):
    bad = []
    for e in collect(tree, "ResolveByElement", []):
        p = e[1]; nm = p.rsplit("/", 1)[-1]
        lp = f"{p}/{nm}_colorless/{nm}_colorless"
        if not any(exists(lp + ext) for ext in (".parts.amf3.deflate", ".timeline.amf3.deflate", ".png")):
            bad.append(p)
    return bad


def main():
    T = {k: load(v) for k, v in LP.items()}
    BASE = copy.deepcopy(T)
    files, report = {}, []
    status = dsl_tree(ALL_DMG)[11][1]
    assert len(status) == 18
    permanent = [c for c in status if c[1][5] is False]           # cancelable == False
    dispellable = [c for c in status if c[1][5] is True]
    assert len(permanent) == 8 and len(dispellable) == 10, (len(permanent), len(dispellable))
    perm_all = copy.deepcopy(permanent)
    for c in perm_all:
        c[1][1] = 0
    prog_map, funnel_map = {}, {}

    def clone_prog(p):
        if p in prog_map:
            return prog_map[p]
        np_ = SUPER_DIR + "$" + p.split("/")[-1].replace("$", "__")
        prog_map[p] = np_
        t = copy.deepcopy(dsl_tree(p))
        n = scale_area(t, [0])
        for sp in collect(t, "SpawnFunnel", []):
            fk = sp[1][1]
            sp[1][1] = clone_funnel(fk)
        # 召唤后：全体敌人刷新永续状态
        def inject(block):
            out = []
            for cmd in block:
                out.append(cmd)
                if cmd[0] == "Command" and cmd[1][0] == "SpawnFunnel":
                    out.append(["Event", ["Wait", 2, "*", ["Block", [["Command", ["FindAllSubjects", 0, 51, [], [], [], [], [], ["DoNothing"],
                                                                                  ["Block", copy.deepcopy(perm_all)]]]]]]])
            return out

        def walk_blocks(x):
            if isinstance(x, list):
                if x and x[0] == "Block" and len(x) == 2 and isinstance(x[1], list):
                    x[1] = inject(x[1])
                for y in x:
                    walk_blocks(y)
        walk_blocks(t)
        root = t[11][1]
        t[11][1] = root + [["Event", ["Wait", REPEAT_DELAY, "*", ["Block", copy.deepcopy(root)]]]]
        bad = colorless_ok(t)
        assert not bad, (p, bad)
        pr = W.dsl_signature_problems(t)
        assert not pr, (p, pr)
        d = encode_tree(t)
        assert wf_dsl.parse_dsl(zlib.decompress(d, -15))["tree"] == t
        files[wf_dsl.dsl_logical(np_)] = d
        stats["areas"] += n
        return np_

    def clone_funnel(fk):
        if fk in funnel_map:
            return funnel_map[fk]
        nk = "super_" + fk
        funnel_map[fk] = nk
        assert nk not in T["funnel"] and nk not in T["flevel"]
        rows_ = {}
        for kk, v in T["funnel"][fk].items():
            r = row(v)
            if r[0] == "0":
                r[0], r[1] = "7", r[2]
                for i in range(2, 8):
                    r[i] = ""
            for i, c in enumerate(r):
                if c.startswith("battle/action/") and "$" in c:
                    r[i] = clone_prog(c)
            rows_[kk] = csv_text([r], v)
        T["funnel"][nk] = rows_
        fl = row(T["flevel"][fk])
        assert fl[4] == "hit_hp_correction_funnel"
        fl[2], fl[3] = V2.HITS, V2.FUNNEL_C3
        T["flevel"][nk] = csv_text([fl], T["flevel"][fk])
        return nk

    stats = {"areas": 0}
    assert FOLDER not in T["folder"]
    T["folder"][FOLDER] = csv_text([[FOLDER_NAME, FOLDER_THUMB]], T["folder"]["100"])
    for n, (qid, tq, skey, key, cn) in enumerate(TYPES):
        assert qid not in T["practice"]
        for k in ("field", "zone", "boss", "level", "state", "var"):
            assert key not in T[k], (k, key)
        src = row(T["practice"][tq])
        r = list(src)
        fkey = src[110]
        r[0], r[1], r[2], r[110], r[112] = FOLDER, str(n + 1), cn, key, "36000"
        r[73], r[74] = "4", "true"
        for c in (85, 86, 87, 88):
            r[c] = "600"
        T["practice"][qid] = csv_text([r], T["practice"][tq])
        f = row(T["field"][fkey])
        terr_src = f[1]
        traw = read_raw(terr_src + ".amf3.deflate")[0]
        terr = wf_dsl.parse_dsl(zlib.decompress(traw, -15))["tree"]
        removed = 0
        for L in terr["layers"]:
            if "objects" in L:
                b4 = len(L["objects"])
                L["objects"] = [o for o in L["objects"] if "DIRECT_INSTANT_ITEM" not in str(o.get("type"))]
                removed += b4 - len(L["objects"])
        if removed:
            new_terr = "battle/terrain/practice_quest/" + key
            raw = wf_dsl.encode_amf3(terr)
            assert wf_dsl.parse_dsl(raw)["tree"] == terr
            cobj = zlib.compressobj(9, zlib.DEFLATED, -15)
            files[new_terr + ".amf3.deflate"] = cobj.compress(raw) + cobj.flush()
            f[1] = new_terr
        f[2] = key
        T["field"][key] = csv_text([f], T["field"][fkey])
        z = row(T["zone"][fkey]["0"])
        assert z[24] == z[26] == skey, (z[24], skey)
        z[24] = z[26] = key
        T["zone"][key] = {"0": csv_text([z], T["zone"][fkey]["0"])}
        brows = {}
        for kk, v in T["boss"][skey].items():
            b = row(v)
            if b[0] == "0":
                b[0], b[1], b[2] = "7", cn, b[4]
                for i in range(3, 15):
                    b[i] = ""
            else:
                b[1] = cn
            for i, c in enumerate(b):
                if i != 109 and c.startswith("battle/action/") and "$" in c:
                    b[i] = clone_prog(c)
            # 开场：自身全套状态（含可驱散）；痛苦假人们原 c109 召唤 → 克隆后再接状态
            pre = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
                   ["Block", copy.deepcopy(status)]]
            if b[109]:
                # 痛苦假人们：原开场召唤 4 只小木人 → 换超级小木人，2 帧后给全体敌人挂全套（同 1112 做法）
                base_root = copy.deepcopy(dsl_tree(b[109])[11][1])
                for sp in collect(base_root, "SpawnFunnel", []):
                    sp[1][1] = clone_funnel(sp[1][1])
                full_all = copy.deepcopy(status)
                for c in full_all:
                    c[1][1] = 0
                pre[11][1] = base_root + [["Event", ["Wait", 2, "*", ["Block", [["Command", ["FindAllSubjects", 0, 51, [], [], [], [], [],
                                                                                         ["DoNothing"], ["Block", full_all]]]]]]]]
            prog = SUPER_DIR + "$pre_" + key
            pr = W.dsl_signature_problems(pre)
            assert not pr, pr
            assert not colorless_ok(pre)
            d = encode_tree(pre)
            assert wf_dsl.parse_dsl(zlib.decompress(d, -15))["tree"] == pre
            files[wf_dsl.dsl_logical(prog)] = d
            b[109], b[110] = prog, "true"
            brows[kk] = csv_text([b], v)
        T["boss"][key] = brows
        lv = row(T["level"][skey])
        assert lv[4] == "hit_hp_correction_practice", lv
        lv[1], lv[2], lv[3] = "hit_hp_basic_normal", V2.HITS, V2.BOSS_C3
        T["level"][key] = csv_text([lv], T["level"][skey])
        if skey in T["state"]:
            T["state"][key] = copy.deepcopy(T["state"][skey])
        if skey in T["var"]:
            T["var"][key] = copy.deepcopy(T["var"][skey])
        report.append({"quest": qid, "name": cn, "src_boss": skey, "key": key, "terrain": f[1], "items_removed": removed})
    for k, lp in LP.items():
        d = q.build_node(T[k])
        back = q.parse_node(d)
        assert back == T[k] and all(back[x] == v for x, v in BASE[k].items()), k
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
             "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.180", "version": "1.4.181",
             "quests": report, "programs": prog_map, "funnels": funnel_map, "hit_areas_scaled": stats["areas"]}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + NL, "utf-8")
    # server
    name = "practice_quest.json"
    raw = (OUT / "server17" / name).read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", NL)
    value = json.loads(text)
    added = {}
    for rep, t in zip(report, TYPES):
        assert rep["quest"] not in value
        e = copy.deepcopy(value["1111"])
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
    s18 = OUT / "server18"
    shutil.rmtree(s18, ignore_errors=True)
    s18.mkdir()
    (s18 / name).write_bytes((out.replace(NL, "\r\n") if crlf else out).encode("utf-8"))
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members", "hit_areas_scaled")}, ensure_ascii=False))
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print(json.dumps(funnel_map, ensure_ascii=False))


if __name__ == "__main__":
    main()
