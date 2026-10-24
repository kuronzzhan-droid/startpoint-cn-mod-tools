"""Write before/after P-code of every round-2 patched body to analysis/patch2/ (round-1 SWF -> perf2 SWF)."""
from common import ABC, ROOT, abc_tags, bodies, listing

from perf2_core import apply_patches
from perf2_patches import PATCHES


def main():
    src = (ROOT / "work" / "build" / "patched.swf").read_bytes()
    out, rep = apply_patches(src, PATCHES)
    t_in, t_out = {n: r for n, *_x, r in abc_tags(src)}, {n: r for n, *_x, r in abc_tags(out)}
    outdir = ROOT / "analysis" / "patch2"
    outdir.mkdir(parents=True, exist_ok=True)
    for p in PATCHES:
        if p["id"] == "P1":
            continue
        a, b = ABC(t_in[p["tag"]]), ABC(t_out[p["tag"]])
        i = bodies.resolve(a, p["label"])
        safe = p["id"] + "_" + p["label"].replace("/", "__").replace("$", "S")
        for tag, abc in (("before", a), ("after", b)):
            body = abc.bodies[i]
            head = f"# {p['label']} tag={p['tag'].decode()} body={i} header={body[1:5]}"
            (outdir / f"{safe}.{tag}.pcode.txt").write_text("\n".join([head] + listing(abc, body[5])) + "\n", encoding="utf8")
        print(safe)


if __name__ == "__main__":
    main()
