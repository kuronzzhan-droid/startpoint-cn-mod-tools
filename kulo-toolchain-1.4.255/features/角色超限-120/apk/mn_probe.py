import sys, zipfile
sys.path.insert(0, r"D:/WF/perf-v30-20261015/tools")
from common import ABC, abc_tags, bodies, listing, sha, SWF_MEMBER, MAIN, asm
APK = r"D:/WF/perf-v30-20261015/out/世界弹射测试服-v30-perf2.signed.apk"
swf = zipfile.ZipFile(APK).read(SWF_MEMBER)
abc = ABC([t for t in abc_tags(swf) if t[0] == MAIN][0][4])
for name in sys.argv[1:]:
    hits = [i for i in range(1, len(abc.multinames)) if abc.mn_name(i) == name]
    print(name, [(i, hex(abc.multinames[i][0]), abc.multinames[i]) for i in hits][:8])
    print("  string idx", [i for i in range(1, len(abc.strings)) if abc.strings[i] == name.encode()])
