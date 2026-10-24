"""Legacy and layered delivery metadata, with no publishing side effects."""
from __future__ import annotations

from pathlib import Path

from .archives import write_archives
from .changeset import sha256, validate_document, write_json


def write_manifests(out: Path, doc, members, records, *, requirements=None):
    old_records = [{k: r[k] for k in ("name", "size", "sha256", "members", "files")} for r in records]
    legacy = {"id": doc["id"], "type": "patch", "name": doc["name"],
              "description": doc.get("description", ""), "version": doc["to_version"],
              "depends_on": doc["from_version"], "enabled": True,
              "local_test_only": doc["local_test_only"], "archive": records[0]["name"],
              "archive_size": records[0]["size"], "chain": [r["name"] for r in records],
              "files": sorted(members), "archive_integrity": old_records,
              "created_at": doc["created_at"]}
    legacy_name = f"manifest-entry-{doc['to_version']}.json"
    write_json(out / legacy_name, legacy)
    for rec in records:
        integrity = {**rec, "logical": {n: members[n][1]["logical_path"] for n in rec["files"]},
                     "member_sha256": {n: sha256(members[n][0]) for n in rec["files"]},
                     "applies_on": doc["from_version"], "version": doc["to_version"]}
        write_json(out / rec["name"].replace(".zip", ".integrity.json"), integrity)
    write_json(out / "integrity.json", {"schema": 1, "archives": records,
               "installed_size": sum(len(data) for data, _ in members.values()),
               "member_sha256": {n: sha256(data) for n, (data, _) in members.items()}})
    layered = []
    upstream_root = out / "patches" / doc["to_version"]
    for layer in ("common", "medium", "android"):
        subset = {n: value for n, value in members.items() if value[1]["root"] == layer}
        if not subset:
            subset = {".empty": (b"", {"logical_path": ".empty"})}
        suffix = sha256("".join(sha256(data) for data, _ in subset.values()).encode())[:16]
        layer_records = write_archives(upstream_root, subset, lambda seq, layer=layer:
            f"archive-{layer}-diff/pinball-{doc['from_version']}-{doc['to_version']}-{seq}-{suffix}.zip")
        layered.extend({"relativePath": r["name"], "layer": layer, "order": r["seq"],
                        "bytes": r["size"], "sha256": r["sha256"]} for r in layer_records)
    upstream_name = f"patches/{doc['to_version']}/patch-manifest.json"
    upstream = {"schema": 1, "targetVersion": doc["to_version"], "baseVersion": doc["from_version"],
                "compatibleClient": "CN 1.8.1", "local_test_only": doc["local_test_only"], "archives": layered}
    write_json(out / upstream_name, upstream)
    if requirements is None:
        from wf.caps.requirements import requirements_document
        requirements = requirements_document(doc, members, legacy["chain"])
    requires = requirements
    validate_document(requires, "requires.schema.json")
    write_json(out / "requires.json", requires)
    assertions = {"schema": 1, "from_version": doc["from_version"], "to_version": doc["to_version"],
                  "files": [{"kind": "client", "member": n, "sha256": ent["sha256"],
                             "before_sha256": ent["before_sha256"]} for n, (_, ent) in members.items()]}
    assertions["files"] += [{"kind": "server", **{k: ent[k] for k in ("target", "sha256", "before_sha256")}}
                            for ent in doc.get("server_changes", [])]
    write_json(out / "assert-box.json", assertions)
    (out / "assert_box.py").write_bytes(Path(__file__).with_name("assert_box.py").read_bytes())
    return legacy_name, upstream_name
