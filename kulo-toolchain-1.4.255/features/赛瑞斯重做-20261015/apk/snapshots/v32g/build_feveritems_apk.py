"""Fever 道具 APK：v32f（P1-P3）+ B1-B4 方法补丁。

只替换 1 个成员：assets/worldflipper_android_release.swf。其余成员内容逐字节、压缩方式逐个保留（同 build_pflv4_apk）。
输出 zipalign -p 4 后的**未签名**包；本脚本不签名、不安装、不推送。
用法：
  python build_feveritems_apk.py            # 测试服线：out/世界弹射测试服-v32f-pflv4.apk → out/世界弹射测试服-v32g-pflv4-feveritems.apk
  python build_feveritems_apk.py --local    # 本地 wf 线：local/wf-local-pflv4f.apk → local/wf-local-pflv4g.apk
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, r"D:/WF/perf-v30-20261015/tools")
from build_perf_apk import TOOLS, run, signature  # noqa: E402
from common import SWF_MEMBER, sha  # noqa: E402
from perf2_core import apply_patches  # noqa: E402
import feveritems_patches as F  # noqa: E402

LINES = {
    "test": {"base": HERE / "out" / "世界弹射测试服-v32f-pflv4.apk",
             "base_apk_sha": "51dd8cd35f22cf7143967623dce6aace628539f050a197181004b62e8b5433c4",
             "base_swf_sha": "10cf1685e5e13a1469e13b8eec0ec42b78715dcdc52639eabe7f6582013f4544",
             "out": HERE / "out" / "世界弹射测试服-v32g-pflv4-feveritems.apk"},
    "local": {"base": HERE / "local" / "wf-local-pflv4f.apk",
              "base_apk_sha": "6afb1352a8122c8fe20420fec1837be76aac25e67915f2e235588740b89f7d22",
              "base_swf_sha": "0562c73d47cd97f6705c785c61bf30b1a073c94fa3581657d2095a651b0beced",
              "out": HERE / "local" / "wf-local-pflv4g.apk"},
}
CAPABILITY = ["pf-lv4-v1f", "fever-items-v1"]


def main():
    line = LINES["local" if "--local" in sys.argv[1:] else "test"]
    base_apk, out = line["base"], line["out"]
    base = base_apk.read_bytes()
    assert sha(base) == line["base_apk_sha"], f"base APK sha differs: {base_apk}"
    assert not out.name.endswith(".signed.apk")
    work = HERE / "work"
    work.mkdir(exist_ok=True)
    report_path = out.with_suffix(".build-report.json")
    for stale in (work / "fi_unsigned.apk", work / "fi_aligned.apk", out, report_path):
        if stale.exists():
            stale.unlink()
    with zipfile.ZipFile(base_apk) as source:
        swf0 = source.read(SWF_MEMBER)
        assert sha(swf0) == line["base_swf_sha"], "base SWF is not v32f"
        swf, delta = apply_patches(swf0, F.PATCHES)
        assert all(p["status"] == "applied" for p in delta["patches"]), delta["patches"]
        repl = {SWF_MEMBER: swf}
        preserved = {}
        with zipfile.ZipFile(work / "fi_unsigned.apk", "w") as output:
            output.comment = source.comment
            for item in source.infolist():
                if signature(item.filename):
                    continue
                payload = repl.get(item.filename, source.read(item.filename))
                output.writestr(item, payload)
                preserved[item.filename] = (sha(payload), item.compress_type)
    run([TOOLS / "zipalign.exe", "-p", "-f", "4", work / "fi_unsigned.apk", work / "fi_aligned.apk"])
    run([TOOLS / "zipalign.exe", "-c", "-p", "4", work / "fi_aligned.apk"])
    out.write_bytes((work / "fi_aligned.apk").read_bytes())
    with zipfile.ZipFile(out) as output, zipfile.ZipFile(base_apk) as source:
        assert output.testzip() is None
        assert output.namelist() == [n for n in source.namelist() if not signature(n)]
        unchanged = 0
        for name, expected in preserved.items():
            assert (sha(output.read(name)), output.getinfo(name).compress_type) == expected, name
            if name not in repl:
                assert source.read(name) == output.read(name), name
                assert source.getinfo(name).compress_type == output.getinfo(name).compress_type, name
                unchanged += 1
        assert source.read("AndroidManifest.xml") == output.read("AndroidManifest.xml")
        assert sha(output.read(SWF_MEMBER)) == delta["output_swf_sha256"]
    assert base_apk.read_bytes() == base
    (work / "fi_unsigned.apk").unlink()
    (work / "fi_aligned.apk").unlink()
    report = {
        "capability_added": CAPABILITY, "revision": "v32g: v32f + fever-items B1-B4", "signed": False,
        "status": "aligned_unsigned_static_candidate_runtime_pending",
        "base_apk": str(base_apk), "base_apk_sha256": sha(base), "base_swf_sha256": sha(swf0),
        "apk": str(out), "apk_sha256": sha(out.read_bytes()), "apk_size": out.stat().st_size,
        "changed_members": sorted(repl), "unchanged_members": unchanged,
        "output_swf_sha256": delta["output_swf_sha256"],
        "constants": {"MARKER_UID_BASE": F.MARKER_UID_BASE, "MARKER_SLOTS": F.MARKER_SLOTS, "ITEM_LV": F.ITEM_LV,
                      "SID_FORMAT": "fever:items:<key>|<key>...[:label]"},
        "patches": [{k: p.get(k) for k in ("id", "label", "status", "before", "after", "header_before", "header",
                                           "max_stack", "inserted_at", "blocks", "new_locals", "before_len",
                                           "after_len", "pool_added")}
                    for p in delta["patches"]],
        "cache_instruction": "安装后清 cache/app 再进游戏（AIR SWF 缓存）。bundle.zip 未变，不会重新解包。",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: report[k] for k in ("status", "apk", "apk_sha256", "output_swf_sha256", "unchanged_members")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
