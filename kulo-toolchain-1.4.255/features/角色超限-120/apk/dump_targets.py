import sys, zipfile
sys.path.insert(0, r"D:/WF/perf-v30-20261015/tools")
from common import ABC, abc_tags, bodies, listing, sha, SWF_MEMBER, MAIN
APK = r"D:/WF/perf-v30-20261015/out/世界弹射测试服-v30-perf2.signed.apk"
swf = zipfile.ZipFile(APK).read(SWF_MEMBER)
print("swf", sha(swf))
abc = ABC([t for t in abc_tags(swf) if t[0] == MAIN][0][4])
for label in sys.argv[1:]:
    i = bodies.resolve(abc, label)
    b = abc.bodies[i]
    out = [f"# {label} body={i} header={b[1:5]} exc={b[6]} sha={sha(b[5])}"] + listing(abc, b[5])
    open("pcode/" + label.replace("/", "__") + ".txt", "w", encoding="utf8").write("\n".join(out) + "\n")
    print(label, i, b[1:5], len(out))
