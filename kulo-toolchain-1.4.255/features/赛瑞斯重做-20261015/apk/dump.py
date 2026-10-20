"""Dump P-code of methods from an SWF: python dump.py SWF OUTDIR label..."""
import sys
sys.path.insert(0, r"D:/WF/perf-v30-20261015/tools")
from pathlib import Path
from common import ABC, abc_tags, bodies, listing, sha, MAIN
swf = Path(sys.argv[1]).read_bytes()
abc = ABC([t for t in abc_tags(swf) if t[0] == MAIN][0][4])
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
for label in sys.argv[3:]:
    i = bodies.resolve(abc, label)
    b = abc.bodies[i]
    m = abc.methods[b[0]] if hasattr(abc, "methods") else None
    lines = [f"# {label} body={i} method={b[0]} header={b[1:5]} exc={b[6]} traits={b[7]} sha={sha(b[5])}"] + listing(abc, b[5])
    (out / (label.replace("/", "__").replace("$","_S") + ".txt")).write_text("\n".join(lines) + "\n", encoding="utf8")
    print(label, i, b[1:5], len(lines), sha(b[5]))
