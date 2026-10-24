"""List main-ABC method bodies that v29-coop changed relative to the original (decompiled) SWF."""
import json
from collections import Counter

from common import ORIGINAL_SWF, ROOT, abc_tags, asm, bodies, listing, main_abc, read_base_swf, sha


import re

_IDX = re.compile(r"^(#\d+ )ofs[0-9a-f]+: (newfunction|newclass|callstatic|callmethod|newcatch) \[\d+")


def norm(lines):
    return [_IDX.sub(r"\1\2 [*", line).split(" ofs", 1)[-1] if _IDX.match(line) else line for line in lines]


def label_index(abc):
    labels = bodies.label_map(abc)
    counts = Counter(labels.values())
    return {label: (index, abc.bodies[index]) for index, label in labels.items() if counts[label] == 1}


def main():
    base = read_base_swf()
    original = ORIGINAL_SWF.read_bytes()
    new_abc, _ = main_abc(base)
    old_abc, _ = main_abc(original)
    old_map, new_map = label_index(old_abc), label_index(new_abc)
    changed, added, removed = [], sorted(set(new_map) - set(old_map)), sorted(set(old_map) - set(new_map))
    outdir = ROOT / "analysis" / "v28-patched-methods"
    outdir.mkdir(parents=True, exist_ok=True)
    for label in sorted(set(old_map) & set(new_map)):
        (oi, ob), (ni, nb) = old_map[label], new_map[label]
        if ob[5] == nb[5] and ob[1:5] == nb[1:5]:
            continue
        try:
            if norm(listing(old_abc, ob[5])) == norm(listing(new_abc, nb[5])):
                continue  # pool/method-index renumbering only
        except Exception:
            pass
        changed.append({"label": label, "old_body": oi, "new_body": ni, "old_sha": sha(ob[5]), "new_sha": sha(nb[5]),
                        "old_len": len(ob[5]), "new_len": len(nb[5]), "old_header": ob[1:5], "new_header": nb[1:5]})
        safe = "".join(ch if ch.isalnum() or ch in "_-." else "_" for ch in label.replace("/", "__"))
        (outdir / f"{safe}.orig.pcode.txt").write_text("\n".join(listing(old_abc, ob[5])) + "\n", encoding="utf8")
        (outdir / f"{safe}.v29.pcode.txt").write_text("\n".join(listing(new_abc, nb[5])) + "\n", encoding="utf8")
    tags = [(t[0].decode("utf8", "replace"), sha(t[4]), len(t[4])) for t in abc_tags(base)]
    otags = [(t[0].decode("utf8", "replace"), sha(t[4]), len(t[4])) for t in abc_tags(original)]
    report = {"base_swf_sha256": sha(base), "original_swf_sha256": sha(original),
              "bodies": [len(old_abc.bodies), len(new_abc.bodies)],
              "strings": [len(old_abc.strings), len(new_abc.strings)],
              "multinames": [len(old_abc.multinames), len(new_abc.multinames)],
              "ints": [len(old_abc.ints), len(new_abc.ints)],
              "changed": changed, "added_labels": added, "removed_labels": removed,
              "base_abc_tags": tags, "original_abc_tags": otags}
    (ROOT / "analysis" / "v29-vs-original.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf8")
    for c in changed:
        print(c["label"], c["old_len"], "->", c["new_len"], c["old_header"], c["new_header"])
    print("added", added[:50])
    print("removed", removed[:50])
    print("tags base", [(t[0], t[2]) for t in tags])
    print("tags orig", [(t[0], t[2]) for t in otags])
    print({k: report[k] for k in ("bodies", "strings", "multinames", "ints")})


if __name__ == "__main__":
    main()
