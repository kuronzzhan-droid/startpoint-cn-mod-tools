"""Independent verification of ROOT/out/世界弹射测试服-v30-perf.apk against v29-coop (does not import patch_perf)."""
from __future__ import annotations

import json
import re
import subprocess
import zipfile
from pathlib import Path
from wf.paths import root_path

from common import ABC, BASE_APK, BASE_APK_SHA, ROOT, SWF_MEMBER, abc_tags, asm, bodies, freeze, listing, sha

OUT = ROOT / "out" / "世界弹射测试服-v30-perf.apk"
TOOLS = root_path('runtimes/android-toolchain/sdk/build-tools/34.0.0')
LABEL = "MasterBinaryMap/getIndex"
BEFORE = "ec54f93d80b11c38480c43bb87966d0cf3ed05bf8bb3da7d47b0d11190517d1c"
COOP = ("BattleDerailleur/getDeferralLevel", "84e04501423fa23b0caeb53235652347b2d0d780ce526e1d7793a027951cb570")
CERT = "9bf5f20575482f79579ca52e17b21f6d6d17cbcc44ed334a7710f8bd07368201"


def signature(name):
    name = name.upper()
    return name.startswith("META-INF/") and (name.endswith((".RSA", ".DSA", ".EC", ".SF")) or name == "META-INF/MANIFEST.MF")


def main():
    assert sha(BASE_APK.read_bytes()) == BASE_APK_SHA
    with zipfile.ZipFile(BASE_APK) as src, zipfile.ZipFile(OUT) as out:
        assert out.testzip() is None
        members = {n for n in src.namelist() if not signature(n)}
        assert members == {n for n in out.namelist() if not signature(n)}
        assert [n for n in src.namelist() if not signature(n)] == [n for n in out.namelist() if not signature(n)], "member order"
        for m in members - {SWF_MEMBER}:
            assert src.read(m) == out.read(m) and src.getinfo(m).compress_type == out.getinfo(m).compress_type, m
        base_swf, new_swf = src.read(SWF_MEMBER), out.read(SWF_MEMBER)
        signed = any(signature(n) for n in out.namelist())
        manifest_same = src.read("AndroidManifest.xml") == out.read("AndroidManifest.xml")
    assert manifest_same
    bt, nt = abc_tags(base_swf), abc_tags(new_swf)
    assert [t[0] for t in bt] == [t[0] for t in nt]
    changed_tags = [t[0].decode() for a, t in zip(bt, nt) if a[4] != t[4]]
    assert changed_tags == ["boot_ffc6"], changed_tags
    old = ABC([t for t in bt if t[0] == b"boot_ffc6"][0][4])
    new = ABC([t for t in nt if t[0] == b"boot_ffc6"][0][4])
    for field in ("ints", "uints", "doubles", "strings", "namespaces", "ns_sets", "multinames", "methods", "metadata",
                  "instances", "classes", "scripts"):
        assert freeze(getattr(old, field)) == freeze(getattr(new, field)), field
    assert len(old.bodies) == len(new.bodies)
    labels = bodies.label_map(new)
    changed = [i for i in range(len(old.bodies)) if freeze(old.bodies[i]) != freeze(new.bodies[i])]
    assert [labels[i] for i in changed] == [LABEL], changed
    (i,) = changed
    ob, nb = old.bodies[i], new.bodies[i]
    assert sha(ob[5]) == BEFORE and ob[0] == nb[0] and ob[3:5] == nb[3:5] and ob[6:] == nb[6:]
    added = len(asm.decode(nb[5])) - len(asm.decode(ob[5]))
    assert asm.unsplice(nb[5], 2, added) == ob[5], "inverse splice"
    stack = asm.simulate(asm.decode(nb[5]), nb[3], new.multinames)
    assert stack[0] <= nb[1] and stack[1] <= nb[4] and stack[2] == 0
    assert asm.block_locals(asm.decode(nb[5])) <= nb[2]
    coop = bodies.resolve(new, COOP[0])
    assert sha(new.bodies[coop][5]) == COOP[1] and freeze(new.bodies[coop]) == freeze(old.bodies[coop])
    # production routing: every pushstring containing a URL/host is unchanged because pools and all other bodies are identical;
    # additionally list them for the record.
    routes = sorted({new.s(x.args[0]) for b in new.bodies for x in asm.decode(b[5]) if x.name == "pushstring" and re.search(r"https?://|:\d{4}$", new.s(x.args[0]))})[:40]
    align = subprocess.run([str(TOOLS / "zipalign.exe"), "-c", "-p", "4", str(OUT)], capture_output=True).returncode == 0
    certs = []
    if signed:
        text = subprocess.run([str(TOOLS / "apksigner.bat"), "verify", "--verbose", "--print-certs", str(OUT)], capture_output=True, text=True).stdout
        certs = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-f]{64})", text)
        assert certs == [CERT]
    (ROOT / "analysis" / "patch" / "verify.before.pcode.txt").write_text("\n".join(listing(old, ob[5])) + "\n", encoding="utf8")
    (ROOT / "analysis" / "patch" / "verify.after.pcode.txt").write_text("\n".join(listing(new, nb[5])) + "\n", encoding="utf8")
    result = {
        "passed": True, "apk": str(OUT), "apk_sha256": sha(OUT.read_bytes()), "signed": signed, "certificate_sha256": certs,
        "zipalign_ok": align, "source_swf_sha256": sha(base_swf), "output_swf_sha256": sha(new_swf),
        "changed_swf_tags": changed_tags, "unchanged_swf_tags": len(bt) - 1, "unchanged_non_swf_members": len(members) - 1,
        "manifest_byte_identical": manifest_same, "constant_pools_identical": True,
        "method_changes": [{"method": LABEL, "body": i, "before": sha(ob[5]), "after": sha(nb[5]), "header_before": ob[1:5],
                            "header_after": nb[1:5], "inserted_instructions": added, "stack_metrics": list(stack)}],
        "coop_getDeferralLevel_preserved": {"body": coop, "sha256": COOP[1]},
        "route_strings_sample": routes, "runtime_verified": False,
    }
    assert align
    (ROOT / "analysis" / "verify-perf-apk.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
