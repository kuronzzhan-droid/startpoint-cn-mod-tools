# -*- coding: utf-8 -*-
"""U_b13d0e 修复：风巨蜥 149998 land_dragon_wind_playable 像素动画时间轴。

根因（反编译 flatomo.timeline.Playhead.get_currentSequence）：按序列表顺序找第一个 currentFrame <= end 的序列，找不到即
throw "INTERNAL ERROR"。风巨蜥时间轴的 into_coffin / ghost_raise 都是 kind=pass、帧 159–163，且 163 已是全表最大 end；
ghost_neutral / revive 指回 1–2。角色倒下 → into_coffin 播完按 pass 继续走到 164 → 没有任何序列覆盖 → 幽灵移动时
MemberImpl.move → gotoAndPlayComplex → get_currentSequence 抛错（联机/单人倒下后都会触发）。全部 93 名 MOD 角色只有它一个这样。

修复：照官方序列链（into_coffin pass → ghost_raise pass → ghost_neutral loop → revive once，帧段递增不重叠）
在 164–172 追加帧：图集追加 9 条记录，复用已有贴图区域（164–168 = 入棺末帧 0163，169–172 = 待机帧 0002），
不改图片、不动既有记录；时间轴只改后四条序列的帧段。

用法：WF_TIP=157 python anim_seq_fix.py
"""
import copy
import hashlib
import json
import os
import zipfile
import zlib

os.environ.setdefault("WF_TIP", "157")
from live149 import *  # noqa
import wf_dsl

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.157-1.4.158-1-anim-seq-fix-local.zip"
BASE = "character/land_dragon_wind_playable/pixelart/"
ATLAS, TIMELINE = BASE + "sprite_sheet.atlas.amf3.deflate", BASE + "pixelart.timeline.amf3.deflate"
NEW_SEQ = {"into_coffin": ("pass", 159, 163), "ghost_raise": ("pass", 164, 168),
           "ghost_neutral": ("loop", 169, 170), "revive": ("once", 171, 172)}
ALIAS = {**{n: 163 for n in range(164, 169)}, **{n: 2 for n in range(169, 173)}}


def amf(logical):
    raw, _ = read_raw(logical)
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


def deflate(tree) -> bytes:
    raw = wf_dsl.encode_amf3(tree)
    assert wf_dsl.parse_dsl(raw)["tree"] == tree
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return c.compress(raw) + c.flush()


def current_sequence(seqs, frame):
    for s in seqs:
        if frame <= int(s["end"]):
            return s
    return None


def main() -> int:
    atlas, tl = amf(ATLAS), amf(TIMELINE)
    by_frame = {int(r["n"][-4:]): r for r in atlas}
    assert max(by_frame) == 163 and not set(ALIAS) & set(by_frame)
    new_atlas = copy.deepcopy(atlas)
    for n, src in sorted(ALIAS.items()):
        r = copy.deepcopy(by_frame[src])
        r["n"] = r["n"][:-4] + f"{n:04d}"
        new_atlas.append(r)
    new_tl = copy.deepcopy(tl)
    for s in new_tl["sequences"]:
        if s["name"] in NEW_SEQ:
            s["kind"], s["begin"], s["end"] = NEW_SEQ[s["name"]]
    seqs = new_tl["sequences"]
    # 复核：帧段递增、pass 的下一帧有序列接住、全帧段都能取到序列
    ends = [int(s["end"]) for s in seqs]
    assert ends == sorted(ends), ends
    for s in seqs:
        if s["kind"] == "pass":
            nxt = current_sequence(seqs, int(s["end"]) + 1)
            assert nxt is not None, s
    top = max(int(r["n"][-4:]) for r in new_atlas)
    assert top == max(ends) == 172
    for f in range(1, top + 1):
        assert current_sequence(seqs, f) is not None
    files = {ATLAS: deflate(new_atlas), TIMELINE: deflate(new_tl)}
    members = {member(lp): d for lp, d in files.items()}
    path = OUT / "patch" / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members):
            zf.writestr(m, members[m])
    blob = path.read_bytes()
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
             "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.157", "version": "1.4.158",
             "sequences_before": tl["sequences"], "sequences_after": seqs, "atlas_added": sorted(ALIAS)}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
