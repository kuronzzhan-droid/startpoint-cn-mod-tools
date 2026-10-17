"""Sign the aligned-unsigned v30-perf2 APK later, the same way as sign_perf_apk.py (needs WF_COOP_DEBUG_KS_PASS set by
the operator; never printed). Writes ROOT/out/世界弹射测试服-v30-perf2.signed.apk, asserts the v29-coop debug certificate,
and updates the build report."""
import json
import os
import re
import zipfile
from pathlib import Path

from build_perf_apk import CERT, TOOLS, run, signature
from build_perf2_apk import OUT, REPORT
from common import sha


def main():
    assert os.environ.get("WF_COOP_DEBUG_KS_PASS"), "set WF_COOP_DEBUG_KS_PASS first"
    with zipfile.ZipFile(OUT) as apk:
        assert not any(signature(n) for n in apk.namelist()), "input already signed"
    target = OUT.with_name(OUT.stem + ".signed.apk")
    if target.exists():
        target.unlink()
    keystore = Path.home() / ".android" / "debug.keystore"
    run([TOOLS / "apksigner.bat", "sign", "--ks", keystore, "--ks-key-alias", "androiddebugkey", "--ks-pass",
         "env:WF_COOP_DEBUG_KS_PASS", "--key-pass", "env:WF_COOP_DEBUG_KS_PASS", "--v4-signing-enabled", "false",
         "--out", target, OUT])
    text = run([TOOLS / "apksigner.bat", "verify", "--verbose", "--print-certs", target])
    certs = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-f]{64})", text)
    assert certs == [CERT], "signer differs from v29-coop"
    run([TOOLS / "zipalign.exe", "-c", "-p", "4", target])
    report = json.loads(REPORT.read_text(encoding="utf8"))
    report["signed_apk"] = {"path": str(target), "sha256": sha(target.read_bytes()), "certificate_sha256": certs,
                            "v1": "v1 scheme (JAR signing): true" in text, "v2": "v2 scheme (APK Signature Scheme v2): true" in text}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(report["signed_apk"], ensure_ascii=False))


if __name__ == "__main__":
    main()
