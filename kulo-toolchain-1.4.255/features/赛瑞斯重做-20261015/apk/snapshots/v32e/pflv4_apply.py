"""Replay the PF Lv4 method patches (P1-P3) onto any SWF carrying the same original bodies.

usage: python pflv4_apply.py IN.swf OUT.swf [--report report.json] [--dump DIR]
Same matching rule as perf2_apply: original sha -> patched; patched sha -> left as is; anything else -> refused.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, r"D:/WF/perf-v30-20261015/tools")
from pflv4_patches import PATCHES  # noqa: E402
from perf2_core import Refused, apply_patches  # noqa: E402
from common import ABC, abc_tags, bodies, listing  # noqa: E402


def main():
    args = sys.argv[1:]
    opts = {}
    for flag in ("--report", "--dump"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = Path(args[i + 1])
            del args[i:i + 2]
    if len(args) != 2:
        raise SystemExit(__doc__)
    src, dst = Path(args[0]), Path(args[1])
    if src.resolve() == dst.resolve():
        raise SystemExit("output must differ from input")
    raw = src.read_bytes()
    try:
        out, report = apply_patches(raw, PATCHES)
    except Refused as error:
        raise SystemExit(f"REFUSED: {error}")
    dst.write_bytes(out)
    if "--report" in opts:
        opts["--report"].write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    if "--dump" in opts:
        d = opts["--dump"]
        d.mkdir(parents=True, exist_ok=True)
        tin = {n: r for n, *_x, r in abc_tags(raw)}
        tout = {n: r for n, *_x, r in abc_tags(out)}
        for p in PATCHES:
            for tag, tags in (("before", tin), ("after", tout)):
                abc = ABC(tags[p["tag"]])
                i = bodies.resolve(abc, p["label"])
                b = abc.bodies[i]
                head = f"# {p['label']} body={i} header={b[1:5]}"
                (d / f"{p['id']}.{tag}.pcode.txt").write_text("\n".join([head] + listing(abc, b[5])) + "\n", encoding="utf8")
    for p in report["patches"]:
        print(p["id"], p["status"], p["label"], p.get("after"), p.get("max_stack"), p.get("header"))
    print("output", report["output_swf_sha256"])


if __name__ == "__main__":
    main()
