"""Read actual 221/222 PF3 members and prove the 629 regression gate."""
import hashlib
import json
from pathlib import Path
import zipfile
import zlib

from wf.dsl import sanitize_for_629, forbidden_629
from wf.dsl.check import check_tree
from wf.paths import root_path
from wf.view.safety import local_output, restrict_writes
from wf_dsl import parse_dsl


def main():
    restrict_writes()
    base = root_path("out/万圣新角色-20261016")
    member = "production/upload/89/45fd1ab9d8e6c8f32572e98fdf60ece8ddc46d"
    results = {}
    for version in ("1.4.221", "1.4.222"):
        hits = []
        for filename in sorted((base / f"delivery-{version}").glob("*.zip")):
            with zipfile.ZipFile(filename) as archive:
                if member in archive.namelist():
                    hits.append(archive.read(member))
        assert len(hits) == 1
        raw = hits[0]
        source = parse_dsl(zlib.decompress(raw, -15))["tree"]
        checks = check_tree(source, kind=629)
        assert checks[0]["status"] == "满足", checks
        assert checks[1]["status"] == ("问题" if version.endswith("221") else "满足"), checks
        cleaned = sanitize_for_629(source)
        assert not forbidden_629(cleaned)
        results[version] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "checks": checks,
                            "sanitized_safe": True}
    target = local_output("work/m1/dsl/acceptance.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
