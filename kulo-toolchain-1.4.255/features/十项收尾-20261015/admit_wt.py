# 仅本地副本：准入加 v33 测试包 build（密钥取自 v33.swf 内唯一 64 位 hex）
import json, re, zlib
from pathlib import Path
cfg = Path(__file__).resolve().parent / "localsrv" / "config"
b = Path(r"D:/WF/bughunt-20261015/apk/work/v33.swf").read_bytes()
if b[:3] == b"CWS":
    b = b[:8] + zlib.decompress(b[8:])
hs = sorted(set(re.findall(rb"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", b)))
assert len(hs) == 1, hs
BID = "android-181-testserver-wt-v17b-20261007"
c = json.loads((cfg / "client-admission.json").read_text("utf-8-sig"))
k = json.loads((cfg / "client-admission.keys.json").read_text("utf-8-sig"))
if BID not in k:
    c["builds"].append({"id": BID, "name": "local wt v33 test", "platform": "android", "enabled": True, "allowUntil": None})
    k[BID] = hs[0].decode()
    (cfg / "client-admission.json").write_text(json.dumps(c, ensure_ascii=False, indent=2), "utf-8")
    (cfg / "client-admission.keys.json").write_text(json.dumps(k, indent=2), "utf-8")
print("ok", len(c["builds"]))
