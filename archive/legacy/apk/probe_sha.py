"""Read-only: print full code sha / header of named methods in a SWF (default: round-1 patched.swf).
usage: python probe_sha.py [swf] TAG::Label ...   (TAG omitted = boot_ffc6)"""
import sys
from pathlib import Path

from common import ABC, ROOT, abc_tags, bodies, sha


def main():
    args = sys.argv[1:]
    swf_path = ROOT / "work" / "build" / "patched.swf"
    if args and args[0].endswith(".swf"):
        swf_path = Path(args.pop(0))
    swf = swf_path.read_bytes()
    tags = {name: raw for name, *_r, raw in abc_tags(swf)}
    cache = {}
    for want in args:
        tag, label = (want.split("::", 1) if "::" in want else ("boot_ffc6", want))
        abc = cache.setdefault(tag, ABC(tags[tag.encode()]))
        try:
            i = bodies.resolve(abc, label)
        except Exception as error:  # noqa: BLE001
            print(want, "ERROR", error)
            continue
        b = abc.bodies[i]
        print(want, "body", i, "method", b[0], "header", b[1:5], "len", len(b[5]), "exc", len(b[6]), "sha", sha(b[5]))


if __name__ == "__main__":
    main()
