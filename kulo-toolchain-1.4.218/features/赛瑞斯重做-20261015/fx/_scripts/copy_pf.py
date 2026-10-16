# -*- coding: utf-8 -*-
"""官方五类型 PF 特效的「静音副本」：搬进 skill_unique/seris_dragon_king/pfq_<类型>/。
- png：官方 sheet 字节原样复制（不重排，零画质变化）；
- atlas：条目逐字段保留（含 fx/fy/fw/fh/r），只把 n 的目录前缀换成新目录（两段式 .gen/<基名>/<帧> 不变）；
- parts：只改 i[].p 前缀，其余逐字节语义不动；
- timeline：sounds 清空，sequences 等原样。
新目录名 = 官方目录名映射，sheet 名 = 目录名（预载规则 <dir>/<dirname>.png）。
"""
import json
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fxlib as X  # noqa: E402

OFF = "battle/effect/powerflip/"
NEW = "battle/effect/skill_unique/seris_dragon_king/"
DIRS = {"effect_powerflip_attack_spin": "pfq_spin", "effect_powerflip_attack_fight": "pfq_fight",
        "effect_powerflip_attack_beam": "pfq_beam", "effect_powerflip_attack_support": "pfq_support",
        "effect_powerflip_attack_special": "pfq_special"}
SRC = Path(r"D:/WF/out/赛瑞斯重做-20261015/build/pf_src")
OUT = X.FX / "pf_quiet"


def dec(raw):
    return X.wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


def used_paths():
    ps = set()
    def walk(x):
        if isinstance(x, list):
            if len(x) >= 3 and x[0] == "ShowEffect" and isinstance(x[2], list) and x[2][0] == "SpecifyEffectDirectly":
                ps.add(x[2][1])
            for y in x:
                walk(y)
    for f in SRC.glob("*.json"):
        walk(json.loads(f.read_text("utf8")))
    return sorted(ps)


def main():
    paths = used_paths()
    files, mapping, budget = {}, {}, {}
    for p in paths:
        d, name = p[len(OFF):].split("/")
        nd = DIRS[d]
        mapping[p] = f"{NEW}{nd}/{name}"
    for d, nd in DIRS.items():
        od, ndl = OFF + d, NEW + nd
        png_raw, _ = X.read_raw(f"{od}/{d}.png")
        im = X.png_read(png_raw)
        files[f"{ndl}/{nd}.png"] = png_raw                                   # 原字节（已是存储态魔数）
        at = dec(X.read_raw(f"{od}/{d}.atlas.amf3.deflate")[0])
        for a in at:
            assert a["n"].startswith(od + "/.gen/"), a["n"]
            a["n"] = ndl + a["n"][len(od):]
        files[f"{ndl}/{nd}.atlas.amf3.deflate"] = X.enc_amf(at)
        names = {a["n"] for a in at}
        budget[nd] = {"from": od, "sheet": list(im.size), "packed_px": (im.width + 2) * (im.height + 2)}
        for p in [q for q in paths if q.startswith(od + "/")]:
            name = p.split("/")[-1]
            parts = dec(X.read_raw(f"{p}.parts.amf3.deflate")[0])
            for i in parts["i"]:
                assert i["p"].startswith(od + "/.gen/" + name + "/"), i["p"]
                i["p"] = ndl + i["p"][len(od):]
                assert i["p"] in names, i["p"]
            files[f"{ndl}/{name}.parts.amf3.deflate"] = X.enc_amf(parts)
            tl = dec(X.read_raw(f"{p}.timeline.amf3.deflate")[0])
            budget[nd].setdefault("stripped_se", {})[name] = [s["path"].split("/")[-1] + "@" + str(s["begin"]) for s in tl["sounds"]]
            tl["sounds"] = []
            files[f"{ndl}/{name}.timeline.amf3.deflate"] = X.enc_amf(tl)
    man = []
    for lp, data in sorted(files.items()):
        loc = OUT / "game" / lp
        loc.parent.mkdir(parents=True, exist_ok=True)
        loc.write_bytes(data)
        man.append({"logical": lp, "local": str(loc), "roots": ["upload"], "sha256": X.sha256(data), "size": len(data),
                    "replaces_existing": False})
    (OUT / "path_map.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), "utf-8")
    (OUT / "manifest_part.json").write_text(json.dumps(man, ensure_ascii=False, indent=2), "utf-8")
    (OUT / "budget.json").write_text(json.dumps(budget, ensure_ascii=False, indent=2), "utf-8")
    print(len(files), "files;", sum(b["packed_px"] for b in budget.values()), "px")
    for k, v in budget.items():
        print(k, v["sheet"], v["packed_px"], v.get("stripped_se"))


if __name__ == "__main__":
    main()
