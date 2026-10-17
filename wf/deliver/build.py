"""Produce reviewable artifacts; never install, publish, or contact a service."""
from __future__ import annotations

from pathlib import Path

from wf.view.safety import local_output
from .archives import write_archives
from .changeset import load_changeset, sha256, validate_document, write_json
from .gate import run_prepush
from .manifests import write_manifests


def build_delivery(changeset: Path, out: Path, **prepush_options) -> dict:
    doc, members, server = load_changeset(changeset)
    out = local_output(out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"delivery output must be empty: {out}")
    out.mkdir(parents=True, exist_ok=True)
    records = write_archives(out, members, lambda seq:
        f"pinball-{doc['from_version']}-{doc['to_version']}-{seq}-{doc['slug']}.zip")
    legacy, upstream = write_manifests(out, doc, members, records)
    for rel, raw in server.items():
        target = local_output(out / "server" / rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    delivery = {"schema": "wf-delivery-manifest/1", "id": doc["id"],
                "from_version": doc["from_version"], "to_version": doc["to_version"],
                "local_test_only": doc["local_test_only"], "archives": records,
                "installed_size": sum(len(raw) for raw, _ in members.values()),
                "download_size": sum(r["size"] for r in records),
                "upstream_manifest": upstream, "legacy_manifest": legacy,
                "requires": "requires.json", "assertions": "assert-box.json",
                "prepush": {"status": "未执行", "exit_code": None, "since": doc["from_version"],
                            "report": "prepush.json", "log": "prepush.log", "limitations": []}}
    write_json(out / "delivery-manifest.json", delivery)
    try:
        delivery["prepush"] = run_prepush(out, doc, records, server, **prepush_options)
    except Exception as exc:
        delivery["prepush"].update(status="问题", exit_code=2, limitations=[str(exc)])
        write_json(out / "delivery-manifest.json", delivery)
        raise
    validate_document(delivery, "delivery-manifest.schema.json")
    write_json(out / "delivery-manifest.json", delivery)
    # Snapshot copies and logs remain auditable, but are not installation artifacts.
    sums = []
    for file in sorted(out.rglob("*")):
        if file.is_file() and file.name != "SHA256SUMS" and "validation" not in file.relative_to(out).parts:
            sums.append(f"{sha256(file.read_bytes())}  {file.relative_to(out).as_posix()}")
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n", "utf-8")
    return delivery
