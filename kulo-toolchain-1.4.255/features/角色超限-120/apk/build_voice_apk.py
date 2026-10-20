"""v33：在 v32l（赛瑞斯最终候选）上叠通用技能准备轮换补丁 V1-V3，只换 SWF，出对齐后的未签名 APK。

usage: python build_voice_apk.py BASE.apk OUT.apk VARIANT(v32l|local32l)
其余成员逐字节保留（含 bundle.zip / 超限 O1-O7 / 赛瑞斯补丁）；签名交协调。
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_overlimit_apk import TOOLS, run, signature  # noqa: E402
import voice_patches as VP  # noqa: E402
from perf2_core import apply_patches  # noqa: E402
from common import SWF_MEMBER  # noqa: E402


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    base_apk, out, variant = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    PATCHES = VP.patches(variant)
    assert base_apk.resolve() != out.resolve() and not out.exists(), out
    base = base_apk.read_bytes()
    work = HERE / "work"
    work.mkdir(exist_ok=True)
    unsigned, aligned = work / "voice-unsigned.apk", work / "voice-aligned.apk"
    for stale in (unsigned, aligned):
        if stale.exists():
            stale.unlink()
    with zipfile.ZipFile(base_apk) as source:
        swf0 = source.read(SWF_MEMBER)
        swf, delta = apply_patches(swf0, PATCHES)
        assert all(p["status"] == "applied" for p in delta["patches"]), delta["patches"]
        again, d2 = apply_patches(swf, PATCHES)
        assert again == swf and all(p["status"] == "already_present" for p in d2["patches"])
        preserved = {}
        with zipfile.ZipFile(unsigned, "w") as output:
            output.comment = source.comment
            for item in source.infolist():
                if signature(item.filename):
                    continue
                payload = swf if item.filename == SWF_MEMBER else source.read(item.filename)
                output.writestr(item, payload)
                preserved[item.filename] = (sha(payload), item.compress_type)
    run([TOOLS / "zipalign.exe", "-p", "-f", "4", unsigned, aligned])
    run([TOOLS / "zipalign.exe", "-c", "-p", "4", aligned])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(aligned.read_bytes())
    with zipfile.ZipFile(out) as output, zipfile.ZipFile(base_apk) as source:
        assert output.testzip() is None
        assert {n for n in output.namelist() if not signature(n)} == set(preserved)
        for name, expected in preserved.items():
            assert (sha(output.read(name)), output.getinfo(name).compress_type) == expected, name
            if name != SWF_MEMBER:
                assert source.read(name) == output.read(name), name
    assert base_apk.read_bytes() == base
    report = {"status": "aligned_unsigned_static_candidate_runtime_pending", "base_apk": str(base_apk),
              "base_apk_sha256": sha(base), "apk": str(out), "apk_sha256": sha(out.read_bytes()),
              "changed_members": [SWF_MEMBER], "input_swf_sha256": sha(swf0),
              "output_swf_sha256": delta["output_swf_sha256"],
              "patches": [{k: p.get(k) for k in ("id", "label", "status", "before", "after", "header", "max_stack",
                                                  "inserted_at", "inserted")} for p in delta["patches"]],
              "cache_instruction": "安装后清 cache/app 再进游戏。"}
    out.with_suffix(".build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                                      encoding="utf8")
    print(json.dumps({k: report[k] for k in ("apk", "apk_sha256", "output_swf_sha256")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
