"""Append manifest entries to kulo's asset-patch manifest for live use.

usage: python append_manifest.py <manifest.json> <entry.json>...
Entries are appended in the given order; local_test_only is dropped and
"(测试服)"/"(本地)" name prefixes are removed, since kulo is the live chain.
"""
import json
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
raw = path.read_bytes()
text = raw.decode("utf-8-sig")
crlf = "\r\n" in text
trailing = text.endswith("\n")
data = json.loads(text)


def dumps(obj):
    out = json.dumps(obj, ensure_ascii=False, indent=2) + ("\n" if trailing else "")
    return out.replace("\n", "\r\n") if crlf else out


if dumps(data) != text:
    sys.exit("manifest does not round-trip; refusing")
patches = data["patches"]
tail = data["cdn_version"]
have = {p["version"] for p in patches}
for entry_path in sys.argv[2:]:
    entry = json.loads(Path(entry_path).read_text(encoding="utf-8-sig"))
    if entry["version"] in have:
        sys.exit(f"{entry['version']} already in manifest")
    if entry.get("depends_on") != tail:
        sys.exit(f"{entry['version']} depends_on {entry.get('depends_on')} but tail is {tail}")
    entry.pop("local_test_only", None)
    entry["name"] = re.sub(r"^\s*[（(](测试服|本地)[)）]\s*", "", entry.get("name", ""))
    patches.append(entry)
    have.add(entry["version"])
    tail = entry["version"]
    print("appended", tail, entry["name"])
data["cdn_version"] = tail
path.write_bytes(dumps(data).encode("utf-8"))
