"""Build a signed local replay clone from v28; never install or contact servers."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import zipfile
from pathlib import Path
from wf.paths import path as configured_path, root_path

from inspect_v28 import APK, ROOT
from manifest_local import patch_manifest
from patch_local_endpoints import patch_swf

TOOLS = root_path('runtimes/android-toolchain/sdk/build-tools/34.0.0')
KEYSTORE = configured_path("android_keystore")
CERT = "9bf5f20575482f79579ca52e17b21f6d6d17cbcc44ed334a7710f8bd07368201"
SWF = "assets/worldflipper_android_release.swf"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def signature(name):
    name = name.upper()
    return name.startswith("META-INF/") and (name.endswith((".RSA", ".DSA", ".EC", ".SF")) or name == "META-INF/MANIFEST.MF")


def run(args):
    result = subprocess.run(list(map(str, args)), capture_output=True, text=True, encoding="utf8", errors="replace")
    if result.returncode:
        raise RuntimeError(f"{Path(str(args[0])).name} failed with {result.returncode}; signing output suppressed")
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    hosts = ["10.0.2.2:8001", "127.0.0.1:8001"]
    if os.environ.get("WF_LEGACY_APK_LAN_HOST"):
        hosts.append(os.environ["WF_LEGACY_APK_LAN_HOST"])
    parser.add_argument("--host", choices=hosts, required=True)
    args = parser.parse_args()
    assert os.environ.get("WF_COOP_DEBUG_KS_PASS"), "debug signing password environment missing"
    target = ROOT / "client/baseline-v28-local.apk"
    assert not target.exists(), "refusing existing APK output"
    work = ROOT / "client/baseline-build"
    work.mkdir(exist_ok=True)
    base = APK.read_bytes()
    assert sha(base) == "812526f535ebaf3c8d6b9f2c441220e9ba14472791420e15c51e64d3f48edf1f"
    with zipfile.ZipFile(APK) as source:
        swf, route = patch_swf(source.read(SWF), args.host)
        manifest, manifest_report = patch_manifest(source.read("AndroidManifest.xml"))
        (work / "local.swf").write_bytes(swf)
        with zipfile.ZipFile(work / "unsigned.apk", "w") as output:
            output.comment = source.comment
            preserved = {}
            for item in source.infolist():
                if signature(item.filename):
                    continue
                payload = swf if item.filename == SWF else manifest if item.filename == "AndroidManifest.xml" else source.read(item.filename)
                output.writestr(item, payload)
                preserved[item.filename] = (sha(payload), item.compress_type)
    run([TOOLS / "zipalign.exe", "-p", "-f", "4", work / "unsigned.apk", work / "aligned.apk"])
    run([TOOLS / "apksigner.bat", "sign", "--ks", KEYSTORE, "--ks-key-alias", "androiddebugkey", "--ks-pass", "env:WF_COOP_DEBUG_KS_PASS", "--key-pass", "env:WF_COOP_DEBUG_KS_PASS", "--v4-signing-enabled", "false", "--out", target, work / "aligned.apk"])
    verification = run([TOOLS / "apksigner.bat", "verify", "--verbose", "--print-certs", target])
    cert = re.search(r"Signer #1 certificate SHA-256 digest: ([0-9a-f]{64})", verification)
    assert cert and cert.group(1) == CERT, "baseline certificate differs"
    run([TOOLS / "zipalign.exe", "-c", "-p", "4", target])
    with zipfile.ZipFile(target) as output:
        assert output.testzip() is None
        assert {n for n in output.namelist() if not signature(n)} == set(preserved)
        for name, expected in preserved.items():
            assert (sha(output.read(name)), output.getinfo(name).compress_type) == expected, name
    assert APK.read_bytes() == base, "base APK modified"
    report = {"status": "signed_local_replay_baseline_runtime_pending", "installed": False, "runtime_verified": False, "base_apk": str(APK), "base_apk_sha256": sha(base), "apk": str(target), "apk_sha256": sha(target.read_bytes()), "certificate_sha256": [CERT], "signature_schemes": {"v1": "v1 scheme (JAR signing): true" in verification, "v2": "v2 scheme (APK Signature Scheme v2): true" in verification}, "capability": ["local-replay-routing-only-v1"], "changed_members": ["AndroidManifest.xml", SWF, "META-INF signature"], "preserved_members": len(preserved) - 2, "manifest": manifest_report, "routes": route, "no_combat_changes": True, "warning": "Local replay only; final distributable must be built separately from original v28 without routing/package edits."}
    target.with_suffix(".build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: report[k] for k in ("status", "apk", "apk_sha256", "certificate_sha256", "no_combat_changes")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
