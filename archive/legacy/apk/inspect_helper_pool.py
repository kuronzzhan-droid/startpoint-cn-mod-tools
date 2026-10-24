"""Read-only: print the constant pool (namespaces, multinames) of one helper DoABC2 tag in v29-coop."""
import sys

from common import ABC, abc_tags, read_base_swf

NAME = sys.argv[1].encode() if len(sys.argv) > 1 else b"cn.shop.ShopFirstOpen"


def main():
    for name, *_rest, raw in abc_tags(read_base_swf()):
        if name != NAME:
            continue
        abc = ABC(raw)
        print("strings", len(abc.strings), "namespaces", len(abc.namespaces), "ns_sets", len(abc.ns_sets),
              "multinames", len(abc.multinames), "bodies", len(abc.bodies))
        for i, (k, s) in enumerate(abc.namespaces):
            print("ns", i, hex(k), abc.s(s) if i else "")
        for i, st in enumerate(abc.ns_sets):
            print("nsset", i, st)
        for i, m in enumerate(abc.multinames):
            print("mn", i, hex(m[0]) if i else "", m[1:], abc.mn_name(i) if i else "")
        return
    raise SystemExit("tag not found")


if __name__ == "__main__":
    main()
