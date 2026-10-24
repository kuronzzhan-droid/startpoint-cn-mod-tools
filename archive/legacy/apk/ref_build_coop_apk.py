"""Package a checked one-method SWF patch; invocation awaits live reproduction."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import zipfile
from pathlib import Path
from wf.paths import path as configured_path

from build_local_baseline import CERT, KEYSTORE, ROOT, SWF, TOOLS, run, signature
from patch_coop_grace import CAPABILITY, patch

DOWNLOADS = configured_path("downloads")
REPORT_V28 = DOWNLOADS / "世界弹射测试服-v28.build-report.json"
APK_HASHES = {"812526f535ebaf3c8d6b9f2c441220e9ba14472791420e15c51e64d3f48edf1f", "ed52c209bc0ac1a3328b11c7d1fbdb41dbafb8543207e624bff571e31fb44183"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    assert os.environ.get("WF_COOP_DEBUG_KS_PASS"), "debug signing password environment missing"
    target, work = args.output.resolve(), args.work.resolve()
    assert work.is_relative_to(ROOT.resolve()) and not work.exists(), "work must be a new ROOT path"
    assert not target.exists() and not target.with_suffix(".build-report.json").exists(), "refusing existing output"
    assert target.is_relative_to(ROOT.resolve()) or target.parent == DOWNLOADS and target.name in {"世界弹射测试服-v29-coop.apk", "世界弹射测试服-v30-coop.apk"}, "unauthorized output location/name"
    base = args.input.read_bytes()
    assert sha(base) in APK_HASHES, "unknown APK baseline"
    original_report = json.loads(REPORT_V28.read_text(encoding="utf8"))
    original_certs = run([TOOLS / "apksigner.bat", "verify", "--verbose", "--print-certs", args.input])
    assert CERT in original_certs
    work.mkdir(parents=True)
    with zipfile.ZipFile(args.input) as source:
        swf, delta, _, _, _ = patch(source.read(SWF))
        assert target.parent != DOWNLOADS or delta["baseline"] == "original_v28", "production output cannot inherit local routing"
        (work / "patched.swf").write_bytes(swf)
        (work / "patch-report.json").write_text(json.dumps(delta, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
        preserved = {}
        with zipfile.ZipFile(work / "unsigned.apk", "w") as output:
            output.comment = source.comment
            for item in source.infolist():
                if signature(item.filename):
                    continue
                payload = swf if item.filename == SWF else source.read(item.filename)
                output.writestr(item, payload)
                preserved[item.filename] = (sha(payload), item.compress_type)
    run([TOOLS / "zipalign.exe", "-p", "-f", "4", work / "unsigned.apk", work / "aligned.apk"])
    target.parent.mkdir(parents=True, exist_ok=True)
    run([TOOLS / "apksigner.bat", "sign", "--ks", KEYSTORE, "--ks-key-alias", "androiddebugkey", "--ks-pass", "env:WF_COOP_DEBUG_KS_PASS", "--key-pass", "env:WF_COOP_DEBUG_KS_PASS", "--v4-signing-enabled", "false", "--out", target, work / "aligned.apk"])
    verified = run([TOOLS / "apksigner.bat", "verify", "--verbose", "--print-certs", target])
    actual = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-f]{64})", verified)
    assert actual == [CERT], "signer changed"
    run([TOOLS / "zipalign.exe", "-c", "-p", "4", target])
    with zipfile.ZipFile(target) as output:
        assert output.testzip() is None
        assert {n for n in output.namelist() if not signature(n)} == set(preserved)
        for name, expected in preserved.items():
            assert (sha(output.read(name)), output.getinfo(name).compress_type) == expected, name
    assert args.input.read_bytes() == base, "source APK modified"
    capabilities = original_report["capability"] + (["local-replay-routing-only-v1"] if delta["baseline"] == "local_replay_v28" else []) + [CAPABILITY]
    report = {"capability": capabilities, "status": "signed_static_candidate_runtime_pending", "installed": False, "runtime_verified": False, "base_apk": str(args.input.resolve()), "base_apk_sha256": sha(base), "apk": str(target), "apk_sha256": sha(target.read_bytes()), "signer": "debug", "certificate_sha256": actual, "signature_schemes": {"v1": "v1 scheme (JAR signing): true" in verified, "v2": "v2 scheme (APK Signature Scheme v2): true" in verified}, "changed_members": [SWF, "META-INF signature"], "preserved_members": len(preserved) - 1, "source_swf_sha256": delta["source_swf_sha256"], "output_swf_sha256": delta["output_swf_sha256"], "source_abc_sha256": delta["source_abc_sha256"], "output_abc_sha256": delta["output_abc_sha256"], "methods": delta["methods"], "bodies_total": delta["bodies_total"], "bodies_changed": 1, "constant_pool_appended": delta["constant_pool_appended"], "helper_abc": original_report["helper_abc"], "constants": delta["constants"], "base_note": "Complete original v28 content preserved; only cooperative getDeferralLevel changed. Manifest, DEX and resource members are byte-identical to the selected input.", "patcher": str(Path(__file__).resolve()), "runtime_assertions": {"numeric_report": str(ROOT / "analysis/client-coop-grace-tests.json"), "device_verified": False}, "device": "not installed by this builder", "left_on": "Root records actual main-instance installation and local regression evidence.", "cache_instruction": "Install, clear application cache/app, then compare the actual extracted SWF hash. Preserve downloaded assets, Local Store, account and resource ledger.", "local_replay": delta["baseline"] == "local_replay_v28", "source_v28_build_report": str(REPORT_V28)}
    uid = original_report["uniqueappversionid"]["after"]
    report["uniqueappversionid"] = {"before": uid, "after": uid}
    report["static_validation"] = {"numeric_tests": str(ROOT / "analysis/client-coop-grace-tests.json"), "apk_independent_verification": str(ROOT / "analysis/client-coop-apk-verification.json"), "inverse_bytewise_proof": True}
    target.with_suffix(".build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"status": report["status"], "apk": str(target), "apk_sha256": report["apk_sha256"], "swf_sha256": report["output_swf_sha256"], "certificate_sha256": actual, "local_replay": report["local_replay"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
