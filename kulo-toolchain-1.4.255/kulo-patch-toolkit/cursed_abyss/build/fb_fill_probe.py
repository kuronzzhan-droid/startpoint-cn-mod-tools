from fb_layer0_gate import *
import hashlib
v = View(); allsh = {}
for qid in R0 + R1:
    a, _ = round_assets(v, qid)
    for s, (d, o) in sheets_from_anims(v, a).items():
        allsh.setdefault(s, [d, o, set()])[2].add(qid)
tot_s = tot_r = 0
out = []
for s, (d, o, qs) in allsh.items():
    raw = v.file(s + ".atlas.amf3.deflate")
    if raw is None:
        out.append((0, s, d, "NO ATLAS", len(qs))); continue
    recs = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
    uniq = {(r["x"], r["y"], r["w"], r["h"]) for r in recs}
    ra = sum((w + 2) * (h + 2) for x, y, w, h in uniq)
    out.append((area(d) - ra, s, d, f"regions={len(recs)} uniq={len(uniq)} fill={ra/area(d):.2f}", len(qs)))
out.sort(reverse=True)
for r in out[:45]: print("%.3f %-100s %s %s q=%d" % (r[0] / 1e6, r[1], r[2], r[3], r[4]))
# timeline identity of dup families
for fam in ("enemy_shot_wave_circle_fast/enemy_shot_wave_circle_fast_black/enemy_shot_wave_circle_fast_black",
            "enemy_shot_wave_circle_middle/enemy_shot_wave_circle_middle_black/enemy_shot_wave_circle_middle_black",
            "enemy_shot_wave_circle_slow/enemy_shot_wave_circle_slow_black/enemy_shot_wave_circle_slow_black"):
    base = "battle/effect/enemy_general/" + fam
    for suf in (".timeline.amf3.deflate", ".atlas.amf3.deflate", ".parts.amf3.deflate", ".png"):
        b = v.file(base + suf); print(fam.split("/")[0], suf, None if b is None else hashlib.sha1(b).hexdigest()[:10], None if b is None else len(b))
