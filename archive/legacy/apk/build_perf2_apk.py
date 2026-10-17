"""Build ROOT/out/世界弹射测试服-v30-perf2.apk on top of the round-1 product (work/build/patched.swf = v30-perf SWF).

Only the SWF member of v29-coop is replaced (round-1 + round-2 patches); every other member is copied byte-identical.
Signing follows sign_perf_apk.py: needs WF_COOP_DEBUG_KS_PASS (never printed, never guessed). Without it the output is
the zipaligned UNSIGNED package; then run `python sign_perf2_apk.py` with the variable set.
"""
from __future__ import annotations

import json
import os
import re
import zipfile
from pathlib import Path

from build_perf_apk import BASE_REPORT, CERT, TOOLS, run, signature
from common import BASE_APK, BASE_APK_SHA, ROOT, SWF_MEMBER, sha
from patch_perf import COOP_AFTER_SHA
from perf2_core import apply_patches
from perf2_patches import PATCHES

ROUND1_SWF = ROOT / "work" / "build" / "patched.swf"
ROUND1_SWF_SHA = "1bc0ef24fbbc4d8adeb255f82f2befff6bf7d2fcf7c3a1547fb69031ba6a89f5"
OUT = ROOT / "out" / "世界弹射测试服-v30-perf2.apk"
REPORT = OUT.with_suffix(".build-report.json")
CAPABILITY = ["master-binarymap-index-dict-v1", "shop-eventitem-group-fastscan-v1", "shop-exchange-entry-greyout-v1",
              "battle-start-skip-status-log-v1", "party-flip-cached-members-v1"]


def main():
    work = ROOT / "work" / "build2"
    work.mkdir(parents=True, exist_ok=True)
    for stale in (work / "unsigned.apk", work / "aligned.apk", OUT, REPORT):
        assert stale.resolve().is_relative_to(ROOT.resolve())
        if stale.exists():
            stale.unlink()  # only our own previous outputs inside ROOT
    base = BASE_APK.read_bytes()
    assert sha(base) == BASE_APK_SHA, "unknown v29-coop APK"
    round1 = ROUND1_SWF.read_bytes()
    assert sha(round1) == ROUND1_SWF_SHA, "round-1 SWF differs from the v30-perf product"
    with zipfile.ZipFile(BASE_APK) as source:
        r1_report = json.loads((ROOT / "out" / "世界弹射测试服-v30-perf.build-report.json").read_text(encoding="utf8"))
        assert r1_report["output_swf_sha256"] == ROUND1_SWF_SHA
    swf, delta = apply_patches(round1, PATCHES)
    (work / "patched.swf").write_bytes(swf)
    base_report = json.loads(BASE_REPORT.read_text(encoding="utf8"))
    preserved = {}
    with zipfile.ZipFile(BASE_APK) as source, zipfile.ZipFile(work / "unsigned.apk", "w") as output:
        output.comment = source.comment
        for item in source.infolist():
            if signature(item.filename):
                continue
            payload = swf if item.filename == SWF_MEMBER else source.read(item.filename)
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
        run([TOOLS / "zipalign.exe", "-c", "-p", "4", OUT])
    else:
        OUT.write_bytes((work / "aligned.apk").read_bytes())
    with zipfile.ZipFile(OUT) as output, zipfile.ZipFile(BASE_APK) as source:
        assert output.testzip() is None
        assert {n for n in output.namelist() if not signature(n)} == set(preserved)
        for name, expected in preserved.items():
            assert (sha(output.read(name)), output.getinfo(name).compress_type) == expected, name
            if name != SWF_MEMBER:
                assert source.read(name) == output.read(name), name
        assert sha(output.read(SWF_MEMBER)) == delta["output_swf_sha256"]
        manifest_identical = source.read("AndroidManifest.xml") == output.read("AndroidManifest.xml")
        assert manifest_identical
    assert BASE_APK.read_bytes() == base, "source APK modified"
    report = {
        "capability": base_report["capability"] + CAPABILITY,
        "status": "signed_static_candidate_runtime_pending" if signed else "aligned_unsigned_static_candidate_runtime_pending",
        "signed": signed, "installed": False, "runtime_verified": False,
        "unsigned_reason": None if signed else "WF_COOP_DEBUG_KS_PASS not present; keystore not read, password not guessed. "
                                               "Run tools/sign_perf2_apk.py with it set.",
        "base_apk": str(BASE_APK), "base_apk_sha256": BASE_APK_SHA,
        "stacked_on": {"round1_swf": str(ROUND1_SWF), "round1_swf_sha256": ROUND1_SWF_SHA},
        "apk": str(OUT), "apk_sha256": sha(OUT.read_bytes()),
        "certificate_sha256_expected": [CERT], "certificate_sha256": certs,
        "changed_members": [SWF_MEMBER] + (["META-INF signature"] if signed else ["META-INF signature (removed: unsigned)"]),
        "preserved_members_byte_identical": len(preserved) - 1, "manifest_byte_identical": manifest_identical,
        "source_swf_sha256": delta["source_swf_sha256"], "output_swf_sha256": delta["output_swf_sha256"],
        "tags_changed": delta["tags_changed"],
        "coop_getDeferralLevel_preserved": {"label": "BattleDerailleur/getDeferralLevel", "sha256": COOP_AFTER_SHA},
        "patches": [{k: p.get(k) for k in ("id", "label", "tag", "status", "body", "before", "after", "header_before",
                                           "header", "inserted_at", "replaced", "pool_added", "max_stack", "max_scope")}
                    for p in delta["patches"]],
        "patcher": str(ROOT / "tools" / "perf2_apply.py"), "builder": str(Path(__file__).resolve()),
        "static_validation": str(ROOT / "analysis" / "test-perf2-results.json"),
        "cache_instruction": "Install, clear application cache/app, then compare the extracted SWF hash with output_swf_sha256.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: report[k] for k in ("status", "apk", "apk_sha256", "output_swf_sha256", "tags_changed")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
