"""Independent signed APK, ABC scope and reverse-instruction verification."""
from __future__ import annotations

import json
import re
import zipfile
from wf.paths import path as configured_path

from build_local_baseline import CERT, ROOT, SWF, TOOLS, run, signature
from inspect_v28 import ABC, asm, bodies
from patch_coop_grace import BODY_SHA, LABEL, listing, sha
from patch_local_endpoints import freeze
from verify_local_baseline import abc_tags


def verify(source_path, output_path, name):
    with zipfile.ZipFile(source_path) as source, zipfile.ZipFile(output_path) as output:
        assert output.testzip() is None
        members = {n for n in source.namelist() if not signature(n)}
        assert members == {n for n in output.namelist() if not signature(n)}
        for member in members - {SWF}:
            assert source.read(member) == output.read(member), member
            assert source.getinfo(member).compress_type == output.getinfo(member).compress_type, member
        source_swf, output_swf = source.read(SWF), output.read(SWF)
    before_tags, after_tags = abc_tags(source_swf), abc_tags(output_swf)
    assert len(before_tags) == len(after_tags)
    unchanged_tags, method_changes = 0, []
    for a, b in zip(before_tags, after_tags):
        assert a[:2] == b[:2]
        if a[2] == b[2]:
            unchanged_tags += 1
            continue
        assert a[0] == 82 and a[1] == b"boot_ffc6", "unrelated SWF tag changed"
        old, new = ABC(a[3]), ABC(b[3])
        assert new.ints == old.ints + [1560], "integer pool must append exactly 1560"
        for field in ("uints", "doubles", "strings", "namespaces", "ns_sets", "multinames", "methods", "metadata", "instances", "classes", "scripts"):
            assert freeze(getattr(old, field)) == freeze(getattr(new, field)), field
        assert len(old.bodies) == len(new.bodies) == 92601
        labels = bodies.label_map(new)
        for index, (old_body, new_body) in enumerate(zip(old.bodies, new.bodies)):
            if freeze(old_body) == freeze(new_body):
                continue
            assert labels[index] == LABEL and sha(old_body[5]) == BODY_SHA
            assert old_body[:5] == new_body[:5] and old_body[6:] == new_body[6:]
            decoded = asm.decode(new_body[5])
            assert decoded[16].name == "pushint" and new.ints[decoded[16].args[0]] == 1560
            assert decoded[17].name == "subtract_i"
            assert asm.unsplice(new_body[5], 16, 2) == old_body[5]
            assert asm.simulate(decoded, new_body[3], new.multinames)[:2] == (2, 2)
            method_changes.append({"method": LABEL, "body": index, "before": sha(old_body[5]), "after": sha(new_body[5])})
            (ROOT / f"analysis/client-{name}.actual-before.pcode.txt").write_text("\n".join(listing(old, old_body[5])) + "\n", encoding="utf8")
            (ROOT / f"analysis/client-{name}.actual-after.pcode.txt").write_text("\n".join(listing(new, new_body[5])) + "\n", encoding="utf8")
    assert len(method_changes) == 1
    sig = run([TOOLS / "apksigner.bat", "verify", "--verbose", "--print-certs", output_path])
    certificates = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-f]{64})", sig)
    assert certificates == [CERT]
    assert all(value in sig for value in ("v1 scheme (JAR signing): true", "v2 scheme (APK Signature Scheme v2): true"))
    run([TOOLS / "zipalign.exe", "-c", "-p", "4", output_path])
    result = {"passed": True, "source_apk": str(source_path), "source_apk_sha256": sha(source_path.read_bytes()), "apk": str(output_path), "apk_sha256": sha(output_path.read_bytes()), "source_swf_sha256": sha(source_swf), "output_swf_sha256": sha(output_swf), "certificate_sha256": certificates, "unchanged_non_swf_members": len(members) - 1, "unchanged_swf_tags": unchanged_tags, "changed_swf_tags": 1, "unchanged_main_method_bodies": 92600, "method_changes": method_changes, "int_pool_appended": [1560], "inverse_bytewise_proof": True, "routes_and_manifest_preserved": True, "runtime_verified": False}
    return result


def main():
    from pathlib import Path
    downloads = configured_path("downloads")
    pairs = [
        (ROOT / "client/baseline-v28-local.apk", ROOT / "client/fixed-v28-local.apk", "fixed-local"),
        (downloads / "世界弹射测试服-v28.apk", downloads / "世界弹射测试服-v29-coop.apk", "v29-coop"),
    ]
    results = [verify(*pair) for pair in pairs]
    assert results[0]["method_changes"] == results[1]["method_changes"], "local and production algorithm differs"
    report = {"passed": True, "local_and_production_target_body_identical": True, "outputs": results}
    (ROOT / "analysis/client-coop-apk-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
