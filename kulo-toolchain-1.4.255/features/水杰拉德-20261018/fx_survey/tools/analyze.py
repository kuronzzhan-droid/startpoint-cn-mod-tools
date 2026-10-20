# -*- coding: utf-8 -*-
"""Analyze every skill effect .parts: structure + bbox + DSL usage -> fx_index.json"""
import json, csv, collections, sys, math, time
from pathlib import Path
import wfio, fxlib

DEC = wfio.DEC
t0 = time.time()

# ---------- master tables ----------
chars = {}
for r in csv.reader(open(DEC / "master/character/character.csv", encoding="utf-8-sig")):
    if len(r) < 28:
        continue
    chars[r[1]] = {"id": r[0], "code": r[1], "rarity": r[3], "element": r[4], "role": r[27], "pix": r[9]}
names = {}
for r in csv.reader(open(DEC / "master/character/character_text.csv", encoding="utf-8-sig")):
    if len(r) > 5:
        names[r[0]] = {"name": r[1], "title": r[4], "skill": r[5]}
skill_rows = [r for r in csv.reader(open(DEC / "master/skill/action_skill.csv", encoding="utf-8-sig")) if len(r) > 9]
dsl2skill = collections.defaultdict(list)
for r in skill_rows:
    dsl2skill[r[9]].append({"key": r[0], "lv": r[1], "sname": r[2], "desc": r[3], "icon": r[4]})

# ---------- DSL ShowEffect usages ----------
se = json.loads(Path("showeffects.json").read_text(encoding="utf-8"))
se = [r for r in se if r["dsl"].startswith("battle/action/skill") or r["dsl"].startswith("battle/action/power_flip")]
# add alk (rare4) from store (not in wf-decrypted)
for p in ["battle/action/skill/action/rare4/alk$alk_1", "battle/action/skill/action/rare4/alk$alk_2"]:
    b = wfio.read_store(p + ".action.dsl.amf3.deflate")
    if b:
        tree = wfio.amf_decode(b)
        import scan_dsl_helpers as H
        for cmd, ctx in H.find(tree):
            a = cmd[1:]
            se.append({"dsl": p, "name": a[0], "effect": a[1], "subject": a[2], "layer": a[3][0], "lifetime": a[4],
                       "coord": a[5], "x": a[6], "y": a[7], "rot": a[8], "trackPos": a[9], "trackDir": a[10], "scale": a[11], "ctx": ctx, "src": "store131"})

ELEM_SUFFIX = {0: "red", 1: "blue", 2: "yellow", 3: "green", 4: "white", 5: "black", 6: "colorless"}

def resolve(eff, char_elem):
    if eff[0] == "SpecifyEffectDirectly":
        return [eff[1]]
    base = eff[1]
    nm = base.split("/")[-1]
    e = eff[2]
    if e in ELEM_SUFFIX:
        sfx = [ELEM_SUFFIX[e]]
    else:  # 255 = use character element
        sfx = [ELEM_SUFFIX.get(int(char_elem), "blue")] if char_elem not in (None, "") else ["blue"]
    return [f"{base}/{nm}_{s}/{nm}_{s}" for s in sfx]

def char_of_dsl(dsl):
    rows = dsl2skill.get(dsl, [])
    keys = [x["key"] for x in rows]
    stem = dsl.split("/")[-1].split("$")[0]
    for k in keys + [stem]:
        if k in chars:
            return k
    return keys[0] if keys else stem

usage = collections.defaultdict(list)
for r in se:
    code = char_of_dsl(r["dsl"])
    ce = chars.get(code, {}).get("element")
    for p in resolve(r["effect"], ce):
        sc = r["scale"]
        sval = None
        if isinstance(sc, list) and sc and sc[0] == "Some":
            v = sc[1][0] if isinstance(sc[1], list) else sc[1]
            if isinstance(v, dict):
                sval = v.get("max", v.get("min"))
            else:
                sval = v
        usage[p].append({"dsl": r["dsl"], "char": code, "name": r["name"], "subject": r["subject"], "layer": r["layer"],
                         "lifetime": r["lifetime"][0] if isinstance(r["lifetime"], list) else r["lifetime"],
                         "life_arg": r["lifetime"][1] if isinstance(r["lifetime"], list) and len(r["lifetime"]) > 1 else None,
                         "coord": r["coord"][0] if isinstance(r["coord"], list) else r["coord"], "x": r["x"], "y": r["y"], "rot": r["rot"],
                         "scale": sval, "ctx": r.get("ctx", [])})

# ---------- effect list: every skill_unique parts in manifest + every referenced effect ----------
plist = set()
for line in open(DEC / "_manifest.csv", encoding="utf-8-sig"):
    parts = line.rstrip("\n").split(",")
    if len(parts) < 3:
        continue
    lp = parts[2]
    if lp.startswith("battle/effect/skill_unique/") and lp.endswith(".parts.amf3.deflate"):
        plist.add(lp[:-len(".parts.amf3.deflate")])
for p in usage:
    if p.startswith("battle/effect/"):
        plist.add(p)
print("effects to analyze", len(plist))

atlas_cache = {}

def get_textures(dirpath):
    if dirpath in atlas_cache:
        return atlas_cache[dirpath]
    nm = dirpath.split("/")[-1]
    atlas, asrc = wfio.load_amf(f"{dirpath}/{nm}.atlas")
    png, psrc = wfio.load_png(f"{dirpath}/{nm}.png")
    res = None
    if atlas is not None and png is not None:
        res = {"tex": fxlib.frame_textures(png, atlas), "png_size": png.size, "atlas_n": len(atlas),
               "src": (asrc, psrc), "png_path": f"{dirpath}/{nm}.png"}
    atlas_cache[dirpath] = res
    return res

index = []
for k, P in enumerate(sorted(plist)):
    rec = {"path": P, "usage": usage.get(P, [])}
    parts, psrc = wfio.load_amf(P + ".parts")
    tl, tsrc = wfio.load_amf(P + ".timeline")
    rec["src"] = psrc
    if parts is None:
        rec["error"] = "parts missing"
        index.append(rec)
        continue
    rec["frames"] = int(parts["g"][0]["t"])
    rec["default_scale"] = parts.get("s")
    rec["n_images"] = len(parts.get("i", []))
    rec["n_graphics"] = len(parts.get("g", []))
    rec["n_matrices"] = len(parts.get("t", []))
    nstrip = nkf = 0
    blends = collections.Counter(); cvals = collections.Counter(); tweens = collections.Counter(); kinds = collections.Counter()
    for g in parts["g"]:
        for s in g["s"]:
            nstrip += 1
            kinds[(int(s["s"]) & 0xFFFFFFFF) >> 30] += 1
            for kf in s["l"]:
                nkf += 1
                blends[(int(kf["m"]) >> 8) & 0xF] += 1
                if kf.get("c") is not None and int(kf["c"]) != fxlib.DEFAULT_C:
                    cvals[int(kf["c"]) & 0xFFFFFFFF] += 1
                tweens[(int(kf.get("t", 0) or 0) >> 16) & 3] += 1
    rec["n_strips"] = nstrip; rec["n_keyframes"] = nkf
    rec["blends"] = dict(blends); rec["c_count"] = sum(cvals.values()); rec["c_top"] = [[hex(v), n] for v, n in cvals.most_common(6)]
    rec["tweens"] = dict(tweens); rec["seg_kinds"] = dict(kinds)
    if tl:
        rec["sequences"] = tl.get("sequences", [])
        rec["sounds"] = [s.get("path") if isinstance(s, dict) else s for s in tl.get("sounds", [])][:6]
    dirs = sorted(set(im["p"].split("/.gen/")[0] for im in parts.get("i", []) if "/.gen/" in im["p"]))
    rec["atlas_dirs"] = dirs
    textures = {}
    pngs = []
    for d in dirs:
        t = get_textures(d)
        if t:
            textures.update(t["tex"])
            pngs.append({"png": t["png_path"], "size": t["png_size"], "atlas_n": t["atlas_n"], "src": t["src"]})
        else:
            rec.setdefault("missing_atlas", []).append(d)
    rec["pngs"] = pngs
    miss = [im["p"] for im in parts.get("i", []) if im["p"] not in textures]
    rec["missing_frames"] = len(miss)
    # bbox per frame
    union = None
    best_area = 0; best_f = 0; fb = []
    for f in range(rec["frames"]):
        bb = fxlib.frame_bbox(parts, textures, f)
        fb.append(bb)
        if bb is None:
            continue
        if union is None:
            union = list(bb)
        else:
            union = [min(union[0], bb[0]), min(union[1], bb[1]), max(union[2], bb[2]), max(union[3], bb[3])]
        ar = (bb[2] - bb[0]) * (bb[3] - bb[1])
        if ar > best_area:
            best_area = ar; best_f = f
    rec["bbox"] = union
    rec["max_area_frame"] = best_f
    rec["max_frame_bbox"] = fb[best_f] if fb and fb[best_f] else None
    index.append(rec)
    if k % 100 == 0:
        print(k, P, round(time.time() - t0, 1), flush=True)

Path("fx_index.json").write_text(json.dumps({"chars": chars, "names": names, "dsl2skill": dsl2skill, "effects": index}, ensure_ascii=False), encoding="utf-8")
print("done", len(index), round(time.time() - t0, 1))
