"""角色超限 Lv120 APK：v30-perf2 + O1-O4 方法补丁 + 内置等级表（bundle.zip 两个成员）。

只替换 3 个成员：SWF（O1-O4）、assets/bundle.zip（level_cap_iosbundled 的 ★5 行 80,4→80,8；
character_level_iosbundled 的 ★5 补 101-120 级）、assets/bundle.zip.sha1（新 bundle 的 sha1，触发客户端重新解包）。
其余成员逐字节保留。签名沿用 perf2：有 WF_COOP_DEBUG_KS_PASS 才签，否则输出 zipalign 后的未签名包。
用法：python build_overlimit_apk.py
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, r"D:/WF/perf-v30-20261015/tools")
sys.path.insert(0, r"D:/WF/startpoint-cn-kulo/tools/fantasy-gauntlet-mod-tools")
from build_perf_apk import CERT, TOOLS, run, signature  # noqa: E402
from common import SWF_MEMBER, sha  # noqa: E402
from overlimit_patches import PATCHES  # noqa: E402
from perf2_core import apply_patches  # noqa: E402
import wf_mod_tool as M  # noqa: E402
import wf_quest_lib as q  # noqa: E402
import wf_dsl  # noqa: E402
import zlib  # noqa: E402
from PIL import Image  # noqa: E402

BASE_APK = Path(os.environ.get("WF_OVERLIMIT_BASE_APK", r"D:/WF/perf-v30-20261015/out/世界弹射测试服-v30-perf2.signed.apk"))
BASE_APK_SHA = None  # 首次运行记录，见报告 base_apk_sha256
BASE_SWF_SHA = "f1cf73182abede54d862876f2d876f137082378ee709bf6d45ac13ad16b4fd22"
OUT = HERE / "out" / os.environ.get("WF_OVERLIMIT_OUT_NAME", "世界弹射测试服-v31-overlimit120.apk")
REPORT = OUT.with_suffix(".build-report.json")
CAPABILITY = ["overlimit120-v1"]

SALT = q.SALT
LEVEL_CAP = "master/character/level_cap_iosbundled.orderedmap"
CHAR_LEVEL = "master/character/character_level_iosbundled.orderedmap"
LEVEL_CAP_5 = ("80,4,5,3,3", "80,8,5,3,3")
EXP_100 = 379988
EXP_PER_LEVEL = 15000          # 81-100 级是每级 11300
EXT_LEVELS = range(101, 121)
PEDESTAL_PNG = "character_pedestal/sprite_sheet.png"
PEDESTAL_ATLAS = "character_pedestal/sprite_sheet.atlas.amf3.deflate"
PEDESTAL_TIERS = {6: "B", 7: "C"}   # 作者 1015：开启超限=第二排 B；满突破 Lv120 + 觉醒满=第三排 C
PEDESTAL_AI = Path(r"D:/WF/out/角色超限-120/art/pedestal/ai")
COLORS = ["red", "blue", "yellow", "green", "white", "black"]


def bundle_member(logical: str) -> str:
    h = hashlib.sha1((logical + SALT).encode()).hexdigest()
    return f"production/android_bundle/{h[:2]}/{h[2:]}"


def patch_level_cap(raw: bytes) -> bytes:
    om = M.read_orderedmap_raw_rows_from_bytes(raw, LEVEL_CAP)
    t = q.parse_node(raw)
    assert t == {"4": "70,6,5,1.5,1.5", "5": LEVEL_CAP_5[0]}, t
    om.rows[om.keys.index("5")] = q.build_node(LEVEL_CAP_5[1])
    out = M.build_orderedmap_raw_rows(om)
    back = q.parse_node(out)
    assert back == {"4": t["4"], "5": LEVEL_CAP_5[1]}, back
    return out


def patch_char_level(raw: bytes) -> bytes:
    om = M.read_orderedmap_raw_rows_from_bytes(raw, CHAR_LEVEL)
    t = q.parse_node(raw)
    five = dict(t["5"])
    assert list(five)[-1] == "100" and five["100"] == str(EXP_100), five["100"]
    assert all(str(lv) not in five for lv in EXT_LEVELS)
    for lv in EXT_LEVELS:
        five[str(lv)] = str(EXP_100 + (lv - 100) * EXP_PER_LEVEL)
    om.rows[om.keys.index("5")] = q.build_node(five)
    out = M.build_orderedmap_raw_rows(om)
    back = q.parse_node(out)
    assert back["4"] == t["4"] and back["3"] == t["3"] and back["5"] == five
    assert back["5"]["120"] == "679988"
    return out


def _png_in(raw: bytes) -> Image.Image:
    fixed = bytearray(raw)
    if fixed[1:4] == b"png":
        fixed[1:4] = b"PNG"
    return Image.open(io.BytesIO(bytes(fixed))).convert("RGBA")


def patch_pedestal(png_raw: bytes, atlas_raw: bytes) -> tuple[bytes, bytes]:
    """台座图集末尾追加 24 帧 <color>_{6,7}[_half]；原有帧坐标与像素不动。"""
    atlas = wf_dsl.AMF3Reader(zlib.decompress(atlas_raw, -15)).read_value() if hasattr(wf_dsl, "AMF3Reader")         else M.AMF3Reader(zlib.decompress(atlas_raw, -15)).read_value()
    enc0 = wf_dsl.encode_amf3(atlas)
    assert zlib.decompress(atlas_raw, -15) == enc0, "atlas AMF3 roundtrip differs"
    by = {e["n"]: e for e in atlas}
    sheet = _png_in(png_raw)
    frames = []
    for tier, cand in PEDESTAL_TIERS.items():
        for k in range(12):
            color, half = COLORS[k // 2], k % 2 == 1
            ref = by[f"character_pedestal/common/{color}_5{'_half' if half else ''}"]
            img = Image.open(PEDESTAL_AI / f"{cand}_{k}.png").convert("RGBA")
            crop = img.crop(img.getbbox())
            assert crop.size == (ref["w"], ref["h"]), (cand, k, crop.size, ref)
            frames.append((f"character_pedestal/common/{color}_{tier}{'_half' if half else ''}", crop, ref))
    y = sheet.size[1]
    height = y + sum(c.size[1] + 1 for _, c, _ in frames)
    out = Image.new("RGBA", (sheet.size[0], height), (0, 0, 0, 0))
    out.paste(sheet, (0, 0))
    new_atlas = list(atlas)
    for name, crop, ref in frames:
        assert name not in by
        out.paste(crop, (1, y))
        new_atlas.append({"n": name, "w": crop.size[0], "h": crop.size[1], "x": 1, "y": y,
                          "fx": ref["fx"], "fy": ref["fy"], "fw": ref["fw"], "fh": ref["fh"]})
        y += crop.size[1] + 1
    assert list(out.crop((0, 0) + sheet.size).getdata()) == list(sheet.getdata())
    buf = io.BytesIO()
    out.save(buf, "PNG")
    png = bytearray(buf.getvalue())
    if png_raw[1:4] == b"png":
        png[1:4] = b"png"
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    atlas_out = co.compress(wf_dsl.encode_amf3(new_atlas)) + co.flush()
    return bytes(png), atlas_out


def patch_bundle(bundle: bytes) -> tuple[bytes, dict]:
    targets = {bundle_member(LEVEL_CAP): patch_level_cap, bundle_member(CHAR_LEVEL): patch_char_level}
    pedestal = None
    if PEDESTAL_TIERS:
        src0 = zipfile.ZipFile(io.BytesIO(bundle))
        pedestal = patch_pedestal(src0.read(bundle_member(PEDESTAL_PNG)), src0.read(bundle_member(PEDESTAL_ATLAS)))
        targets[bundle_member(PEDESTAL_PNG)] = lambda _raw: pedestal[0]
        targets[bundle_member(PEDESTAL_ATLAS)] = lambda _raw: pedestal[1]
    src = zipfile.ZipFile(io.BytesIO(bundle))
    buf = io.BytesIO()
    changed = {}
    with zipfile.ZipFile(buf, "w") as dst:
        dst.comment = src.comment
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename in targets:
                new = targets[info.filename](data)
                changed[info.filename] = {"before_sha256": sha(data), "after_sha256": sha(new),
                                          "before_size": len(data), "after_size": len(new)}
                data = new
            dst.writestr(info, data)
    assert set(changed) == set(targets), changed
    out = buf.getvalue()
    a, b = zipfile.ZipFile(io.BytesIO(bundle)), zipfile.ZipFile(io.BytesIO(out))
    assert a.namelist() == b.namelist() and b.testzip() is None
    for n in a.namelist():
        if n not in targets:
            assert a.read(n) == b.read(n), n
    return out, changed


def main():
    base = BASE_APK.read_bytes()
    work = HERE / "work"
    work.mkdir(exist_ok=True)
    OUT.parent.mkdir(exist_ok=True)
    for stale in (work / "unsigned.apk", work / "aligned.apk", OUT, REPORT):
        if stale.exists() and stale != BASE_APK:
            stale.unlink()
    with zipfile.ZipFile(BASE_APK) as source:
        swf0 = source.read(SWF_MEMBER)
        if "WF_OVERLIMIT_BASE_APK" not in os.environ:
            assert sha(swf0) == BASE_SWF_SHA, "base SWF is not v30-perf2"
        swf, delta = apply_patches(swf0, PATCHES)
        bundle, bundle_changes = patch_bundle(source.read("assets/bundle.zip"))
        digest = hashlib.sha1(bundle).hexdigest().encode()
        assert digest != source.read("assets/bundle.zip.sha1")
        repl = {SWF_MEMBER: swf, "assets/bundle.zip": bundle, "assets/bundle.zip.sha1": digest}
        preserved = {}
        with zipfile.ZipFile(work / "unsigned.apk", "w") as output:
            output.comment = source.comment
            for item in source.infolist():
                if signature(item.filename):
                    continue
                payload = repl.get(item.filename, source.read(item.filename))
                output.writestr(item, payload)
                preserved[item.filename] = (sha(payload), item.compress_type)
    run([TOOLS / "zipalign.exe", "-p", "-f", "4", work / "unsigned.apk", work / "aligned.apk"])
    run([TOOLS / "zipalign.exe", "-c", "-p", "4", work / "aligned.apk"])
    signed = bool(os.environ.get("WF_COOP_DEBUG_KS_PASS"))
    certs = []
    if signed:
        keystore = Path.home() / ".android" / "debug.keystore"
        run([TOOLS / "apksigner.bat", "sign", "--ks", keystore, "--ks-key-alias", "androiddebugkey", "--ks-pass",
             "env:WF_COOP_DEBUG_KS_PASS", "--key-pass", "env:WF_COOP_DEBUG_KS_PASS", "--v4-signing-enabled", "false",
             "--out", OUT, work / "aligned.apk"])
        certs = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-f]{64})",
                           run([TOOLS / "apksigner.bat", "verify", "--verbose", "--print-certs", OUT]))
        assert certs == [CERT], "signer changed"
    else:
        OUT.write_bytes((work / "aligned.apk").read_bytes())
    with zipfile.ZipFile(OUT) as output, zipfile.ZipFile(BASE_APK) as source:
        assert output.testzip() is None
        assert {n for n in output.namelist() if not signature(n)} == set(preserved)
        for name, expected in preserved.items():
            assert (sha(output.read(name)), output.getinfo(name).compress_type) == expected, name
            if name not in repl:
                assert source.read(name) == output.read(name), name
        assert source.read("AndroidManifest.xml") == output.read("AndroidManifest.xml")
    assert BASE_APK.read_bytes() == base
    report = {
        "capability_added": CAPABILITY, "signed": signed, "certificate_sha256": certs,
        "status": "signed_static_candidate_runtime_pending" if signed else "aligned_unsigned_static_candidate_runtime_pending",
        "base_apk": str(BASE_APK), "base_apk_sha256": sha(base), "base_swf_sha256": BASE_SWF_SHA,
        "apk": str(OUT), "apk_sha256": sha(OUT.read_bytes()),
        "changed_members": sorted(repl), "output_swf_sha256": delta["output_swf_sha256"],
        "bundle_sha1": digest.decode(), "bundle_members_changed": bundle_changes,
        "patches": [{k: p.get(k) for k in ("id", "label", "status", "before", "after", "header", "max_stack", "inserted_at")}
                    for p in delta["patches"]],
        "cache_instruction": "安装后清 cache/app 再进游戏；首次启动会因 bundle.zip.sha1 变化重新解包内置资源。",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: report[k] for k in ("status", "apk", "apk_sha256", "output_swf_sha256", "bundle_sha1")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
