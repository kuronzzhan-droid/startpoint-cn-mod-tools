"""Independent check of out/世界弹射测试服-v30-perf2.apk: re-extract the SWF, re-apply nothing, compare against a fresh
CLI replay from v29-coop, list changed tags/bodies, zipalign -c. Writes analysis/verify-perf2-apk.json."""
import json
import subprocess
import sys
import zipfile

from build_perf_apk import TOOLS, run, signature
from build_perf2_apk import OUT, REPORT
from common import ABC, BASE_APK, ROOT, SWF_MEMBER, abc_tags, bodies, freeze, read_base_swf, sha

SCRATCH = ROOT / "work" / "build2"


def main():
    report = json.loads(REPORT.read_text(encoding="utf8"))
    with zipfile.ZipFile(OUT) as apk, zipfile.ZipFile(BASE_APK) as base:
        swf = apk.read(SWF_MEMBER)
        others_identical = all(apk.read(n) == base.read(n) for n in base.namelist() if n != SWF_MEMBER and not signature(n))
        order_identical = [n for n in apk.namelist() if not signature(n)] == [n for n in base.namelist() if not signature(n)]
        compress_identical = all(apk.getinfo(n).compress_type == base.getinfo(n).compress_type
                                 for n in base.namelist() if not signature(n))
    assert sha(swf) == report["output_swf_sha256"]
    base_swf = read_base_swf()
    (SCRATCH / "v29.swf").write_bytes(base_swf)
    cli = subprocess.run([sys.executable, str(ROOT / "tools" / "perf2_apply.py"), str(SCRATCH / "v29.swf"),
                          str(SCRATCH / "replayed.swf")], capture_output=True, text=True)
    assert cli.returncode == 0, cli.stdout + cli.stderr
    replay_identical = (SCRATCH / "replayed.swf").read_bytes() == swf
    t_base, t_new = {n: r for n, *_x, r in abc_tags(base_swf)}, {n: r for n, *_x, r in abc_tags(swf)}
    changed_tags = sorted(n.decode() for n in t_base if t_base[n] != t_new.get(n))
    per_tag = {}
    for name in changed_tags:
        a, b = ABC(t_base[name.encode()]), ABC(t_new[name.encode()])
        labels = bodies.label_map(b)
        per_tag[name] = sorted(labels.get(i, str(i)) for i in range(len(a.bodies)) if freeze(a.bodies[i]) != freeze(b.bodies[i]))
    run([TOOLS / "zipalign.exe", "-c", "-p", "4", OUT])
    result = {"apk": str(OUT), "apk_sha256": sha(OUT.read_bytes()), "swf_sha256": sha(swf),
              "non_swf_members_byte_identical": others_identical, "member_order_identical": order_identical,
              "compression_identical": compress_identical, "cli_replay_from_v29_coop_identical": replay_identical,
              "changed_tags_vs_v29_coop": changed_tags, "changed_bodies_vs_v29_coop": per_tag, "zipalign_ok": True,
              "cli_stdout": cli.stdout.strip().splitlines()}
    assert others_identical and order_identical and compress_identical and replay_identical
    (ROOT / "analysis" / "verify-perf2-apk.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
