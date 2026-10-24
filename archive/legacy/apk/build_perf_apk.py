"""Build ROOT/out/世界弹射测试服-v30-perf.apk from v29-coop: replace only the SWF member, zipalign, sign if possible.

Signing needs WF_COOP_DEBUG_KS_PASS (debug keystore password) in the environment; this script never prints it and
never guesses it. Without it the output is the zipaligned UNSIGNED package (status says so); run sign_perf_apk.py later.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import zipfile
from pathlib import Path
from wf.paths import path as configured_path, root_path

from common import BASE_APK, BASE_APK_SHA, ROOT, SWF_MEMBER, read_base_swf, sha
from patch_perf import CAPABILITY, patch

TOOLS = root_path('runtimes/android-toolchain/sdk/build-tools/34.0.0')
CERT = "9bf5f20575482f79579ca52e17b21f6d6d17cbcc44ed334a7710f8bd07368201"
OUT = ROOT / "out" / "世界弹射测试服-v30-perf.apk"
REPORT = OUT.with_suffix(".build-report.json")
BASE_REPORT = configured_path("downloads", '世界弹射测试服-v29-coop.build-report.json')


def signature(name):
    name = name.upper()
    return name.startswith("META-INF/") and (name.endswith((".RSA", ".DSA", ".EC", ".SF")) or name == "META-INF/MANIFEST.MF")


def run(args):
    result = subprocess.run(list(map(str, args)), capture_output=True, text=True, encoding="utf8", errors="replace")
    if result.returncode:
        raise RuntimeError(f"{Path(str(args[0])).name} failed with {result.returncode}")
    return result.stdout


def main():
    work = ROOT / "work" / "build"
    work.mkdir(parents=True, exist_ok=True)
    for stale in (work / "unsigned.apk", work / "aligned.apk"):
        if stale.exists():
            stale.unlink()
    for target in (OUT, REPORT):
        assert target.resolve().is_relative_to(ROOT.resolve())
        if target.exists():
            target.unlink()  # our own previous output inside ROOT/out only
    base = BASE_APK.read_bytes()
    assert sha(base) == BASE_APK_SHA, "unknown v29-coop APK"
    base_report = json.loads(BASE_REPORT.read_text(encoding="utf8"))
    base_certs = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-f]{64})",
                            run([TOOLS / "apksigner.bat", "verify", "--verbose", "--print-certs", BASE_APK]))
    assert base_certs == [CERT], "v29-coop certificate differs from expected debug certificate"
    swf, delta, _old, _new, _changed = patch(read_base_swf())
    (work / "patched.swf").write_bytes(swf)
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
        verified = run([TOOLS / "apksigner.bat", "verify", "--verbose", "--print-certs", OUT])
        certs = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-f]{64})", verified)
        assert certs == [CERT], "signer changed"
        run([TOOLS / "zipalign.exe", "-c", "-p", "4", OUT])
    else:
        OUT.write_bytes((work / "aligned.apk").read_bytes())
    with zipfile.ZipFile(OUT) as output:
        assert output.testzip() is None
        assert {n for n in output.namelist() if not signature(n)} == set(preserved)
        for name, expected in preserved.items():
            assert (sha(output.read(name)), output.getinfo(name).compress_type) == expected, name
    with zipfile.ZipFile(BASE_APK) as source, zipfile.ZipFile(OUT) as output:
        for name in preserved:
            if name != SWF_MEMBER:
                assert source.read(name) == output.read(name), name
        manifest_identical = source.read("AndroidManifest.xml") == output.read("AndroidManifest.xml")
        assert manifest_identical
    assert BASE_APK.read_bytes() == base, "source APK modified"
    report = {
        "capability": base_report["capability"] + CAPABILITY,
        "status": "signed_static_candidate_runtime_pending" if signed else "aligned_unsigned_static_candidate_runtime_pending",
        "signed": signed, "installed": False, "runtime_verified": False,
        "unsigned_reason": None if signed else "WF_COOP_DEBUG_KS_PASS not present in environment; keystore not read, password not guessed. Run tools/sign_perf_apk.py with it set.",
        "base_apk": str(BASE_APK), "base_apk_sha256": BASE_APK_SHA,
        "apk": str(OUT), "apk_sha256": sha(OUT.read_bytes()),
        "certificate_sha256_expected": [CERT], "certificate_sha256_base": base_certs, "certificate_sha256": certs,
        "changed_members": [SWF_MEMBER] + (["META-INF signature"] if signed else ["META-INF signature (removed: unsigned)"]),
        "preserved_members_byte_identical": len(preserved) - 1, "manifest_byte_identical": manifest_identical,
        "source_swf_sha256": delta["source_swf_sha256"], "output_swf_sha256": delta["output_swf_sha256"],
        "source_abc_sha256": delta["source_abc_sha256"], "output_abc_sha256": delta["output_abc_sha256"],
        "bodies_total": delta["bodies_total"], "bodies_changed": delta["bodies_changed"],
        "constant_pool_appended": delta["constant_pool_appended"],
        "coop_getDeferralLevel_preserved": delta["coop_getDeferralLevel_preserved"],
        "methods": delta["methods"],
        "helper_abc": "all v29 helper DoABC2 tags (cn.*) copied byte-identical",
        "uniqueappversionid": base_report.get("uniqueappversionid"),
        "patcher": str(ROOT / "tools" / "patch_perf.py"), "builder": str(Path(__file__).resolve()),
        "static_validation": {"tests": str(ROOT / "analysis" / "test-perf-results.json"),
                              "apk_verification": str(ROOT / "analysis" / "verify-perf-apk.json")},
        "cache_instruction": "Install, clear application cache/app, then compare the extracted SWF hash with output_swf_sha256.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: report[k] for k in ("status", "apk", "apk_sha256", "output_swf_sha256", "certificate_sha256_base")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
