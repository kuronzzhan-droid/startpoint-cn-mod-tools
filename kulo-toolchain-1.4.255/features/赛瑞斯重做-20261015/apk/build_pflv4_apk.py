"""赛瑞斯 PF Lv4 APK：v31-overlimit120（未签名）+ P1-P3 方法补丁。

只替换 1 个成员：assets/worldflipper_android_release.swf。其余成员内容逐字节、压缩方式逐个保留（同 build_overlimit_apk）。
输出 zipalign -p 4 后的**未签名**包；本脚本不签名、不安装、不推送。
用法：python build_pflv4_apk.py
"""
from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, r"D:/WF/perf-v30-20261015/tools")
from build_perf_apk import TOOLS, run, signature  # noqa: E402
from common import SWF_MEMBER, sha  # noqa: E402
from perf2_core import apply_patches  # noqa: E402
from pflv4_patches import PATCHES, LV4_COLOR, SE_PATH, TWINKLE_RED, TWINKLE_EVERY  # noqa: E402

BASE_APK = Path(os.environ.get("WF_PFLV4_BASE_APK",
                               r"D:/WF/out/角色超限-120/apk/out/世界弹射测试服-v31-overlimit120.apk"))
BASE_APK_SHA = "e9d4db2ebabf6a9c41f06daeac1a0a48f5b975de4678c4211f4dcf89c60c1749"
SIGNED_SIBLING = BASE_APK.with_name(BASE_APK.stem + ".signed.apk")
BASE_SWF_SHA = "b473110bc12f8264dd784804d3434aa9a825ad7edcf8644feaa5874c920c6c6e"
OUT = Path(os.environ.get("WF_PFLV4_OUT", str(HERE / "out" / "世界弹射测试服-v32f-pflv4.apk")))
REPORT = OUT.with_suffix(".build-report.json")
CAPABILITY = ["pf-lv4-v1f"]


def main():
    base = BASE_APK.read_bytes()
    if "WF_PFLV4_BASE_APK" not in os.environ:
        assert sha(base) == BASE_APK_SHA, "base APK is not v31-overlimit120 (unsigned)"
    work = HERE / "work"
    work.mkdir(exist_ok=True)
    OUT.parent.mkdir(exist_ok=True)
    assert not OUT.name.endswith(".signed.apk"), "refusing to write a .signed.apk name"
    for stale in (work / "unsigned.apk", work / "aligned.apk", OUT, REPORT):
        if stale.exists():
            stale.unlink()
    with zipfile.ZipFile(BASE_APK) as source:
        swf0 = source.read(SWF_MEMBER)
        if "WF_PFLV4_BASE_APK" not in os.environ:
            assert sha(swf0) == BASE_SWF_SHA, "base SWF is not v31-overlimit120"
        sibling = None
        if SIGNED_SIBLING.exists():
            with zipfile.ZipFile(SIGNED_SIBLING) as s:
                sibling = sha(s.read(SWF_MEMBER))
        swf, delta = apply_patches(swf0, PATCHES)
        assert all(p["status"] == "applied" for p in delta["patches"]), delta["patches"]
        repl = {SWF_MEMBER: swf}
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
    OUT.write_bytes((work / "aligned.apk").read_bytes())
    with zipfile.ZipFile(OUT) as output, zipfile.ZipFile(BASE_APK) as source:
        assert output.testzip() is None
        assert [n for n in output.namelist()] == [n for n in source.namelist() if not signature(n)]
        unchanged = 0
        for name, expected in preserved.items():
            assert (sha(output.read(name)), output.getinfo(name).compress_type) == expected, name
            if name not in repl:
                assert source.read(name) == output.read(name), name
                assert source.getinfo(name).compress_type == output.getinfo(name).compress_type, name
                unchanged += 1
        assert source.read("AndroidManifest.xml") == output.read("AndroidManifest.xml")
        assert sha(output.read(SWF_MEMBER)) == delta["output_swf_sha256"]
    assert BASE_APK.read_bytes() == base
    (work / "unsigned.apk").unlink()
    (work / "aligned.apk").unlink()
    report = {
        "capability_added": CAPABILITY, "revision": "v32f: v32e + red twinkle three replay on entry and every 60f (red()), spark red, charge not forced, single chime", "signed": False, "status": "aligned_unsigned_static_candidate_runtime_pending",
        "base_apk": str(BASE_APK), "base_apk_sha256": sha(base), "base_swf_sha256": sha(swf0),
        "signed_sibling_swf_sha256": sibling, "signed_sibling_swf_identical": sibling == sha(swf0),
        "apk": str(OUT), "apk_sha256": sha(OUT.read_bytes()), "apk_size": OUT.stat().st_size,
        "changed_members": sorted(repl), "unchanged_members": unchanged,
        "output_swf_sha256": delta["output_swf_sha256"],
        "constants": {"LV4_COLOR": f"0x{LV4_COLOR:06X}", "SE_PATH": SE_PATH, "TWINKLE_RED": TWINKLE_RED, "TWINKLE_EVERY": TWINKLE_EVERY},
        "patches": [{k: p.get(k) for k in ("id", "label", "status", "before", "after", "header_before", "header",
                                           "max_stack", "inserted_at", "blocks", "new_locals", "closures_preserved",
                                           "before_len", "after_len", "pool_added")}
                    for p in delta["patches"]],
        "cache_instruction": "安装后清 cache/app 再进游戏（AIR SWF 缓存）。bundle.zip 未变，不会重新解包。",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: report[k] for k in ("status", "apk", "apk_sha256", "output_swf_sha256",
                                             "signed_sibling_swf_identical", "unchanged_members")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
