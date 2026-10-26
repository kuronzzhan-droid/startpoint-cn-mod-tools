"""Dump P-code of helper DoABC2 tags and of named main-ABC methods from v29-coop (read-only)."""
import sys

from common import ABC, ROOT, abc_tags, bodies, listing, main_abc, read_base_swf, sha

HELPERS = [b"cn.shop.ShopFirstOpen", b"cn/loading/PartyDerivedCache", b"cn.loading.GcGate", b"cn.loading.BattlePackSlicer"]


def dump_abc(abc, title):
    labels = bodies.label_map(abc)
    out = [f"### {title}"]
    for i, body in enumerate(abc.bodies):
        out.append(f"\n## body {i} {labels.get(i, 'anon')} header={body[1:5]} sha={sha(body[5])[:16]} exc={body[6]}")
        out += listing(abc, body[5])
    return out


def main():
    swf = read_base_swf()
    outdir = ROOT / "analysis" / "v29-pcode"
    outdir.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) == 1:
        for name, *_rest, raw in abc_tags(swf):
            if name in HELPERS:
                abc = ABC(raw)
                safe = name.decode().replace("/", ".")
                (outdir / f"helper.{safe}.txt").write_text("\n".join(dump_abc(abc, safe)) + "\n", encoding="utf8")
                print("helper", safe, len(abc.bodies))
        return
    abc, _ = main_abc(swf)
    labels = bodies.label_map(abc)
    for want in sys.argv[1:]:
        hits = [i for i, label in labels.items() if label == want or (want.endswith("*") and label.startswith(want[:-1]))]
        for i in hits:
            body = abc.bodies[i]
            safe = "".join(ch if ch.isalnum() or ch in "_-." else "_" for ch in labels[i].replace("/", "__"))
            text = [f"# {labels[i]} body={i} method={body[0]} header={body[1:5]} sha={sha(body[5])} exc={body[6]}"] + listing(abc, body[5])
            (outdir / f"{safe}.txt").write_text("\n".join(text) + "\n", encoding="utf8")
            print(labels[i], i, len(body[5]), body[1:5])
        if not hits:
            print("NOT FOUND", want)


if __name__ == "__main__":
    main()
