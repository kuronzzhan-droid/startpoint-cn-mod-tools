"""Produce reviewable artifacts; never install, publish, or contact a service."""
from __future__ import annotations

from pathlib import Path

from wf.view.safety import local_output
from .archives import write_archives
from .baseline import resolve_baseline
from .changeset import load_changeset, sha256, validate_document, write_json
from .gate import run_prepush
from .dsl_gate import check_candidate
from .manifests import write_manifests


def build_delivery(changeset: Path, out: Path, *, provides=None, client_profile=None,
                   allow_unknown_client=False, **prepush_options) -> dict:
    from wf.caps.profiles import resolve_client
    provides, selected_profile = resolve_client(provides, client_profile,
                                               allow_unknown_client=allow_unknown_client)
    doc, members, server = load_changeset(changeset)
    out = local_output(out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"delivery output must be empty: {out}")
    baseline = resolve_baseline(doc, **prepush_options)
    out.mkdir(parents=True, exist_ok=True)
    check_candidate(out, members, baseline, prepush_options.get("base_store"))
    from wf.caps.requirements import requirements_document
    from .prepush_base import View
    fallback = View([], prepush_options["base_store"]) if prepush_options.get("base_store") else None

    def read_raw(logical):
        if baseline is not None:
            return baseline.read_raw(logical)
        raw = fallback.raw(logical) if fallback is not None else None
        if raw is None:
            raise FileNotFoundError(logical)
        return raw

    # Parse and derive before creating archives; malformed capability data must
    # never produce an apparently complete deliverable.
    requirements = requirements_document(doc, members, ["pending.zip"], read_raw=read_raw, server=server)
    if provides is not None:
        from wf.caps.kind_compat import check_kind_sites
        from wf.caps.profiles import read_client
        from wf.caps.registry import load_registry
        kind_checks = check_kind_sites(requirements["requires"], read_client(provides), load_registry())
        blocked = [check for check in kind_checks if check["blocking"]]
        if blocked:
            raise ValueError("问题: " + "; ".join(check["message"] for check in blocked))
    records = write_archives(out, members, lambda seq:
        f"pinball-{doc['from_version']}-{doc['to_version']}-{seq}-{doc['slug']}.zip")
    requirements["pack"]["archives"] = [record["name"] for record in records]
    legacy, upstream = write_manifests(out, doc, members, records, requirements=requirements)
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
                "requires": "requires.json", "assertions": "assert-box.json", "dsl_gate": "dsl-629.json",
                "baseline": {"no_baseline_i_know": baseline is None,
                             "tip": baseline.tip if baseline is not None else None,
                             "lock": "baseline.lock.json" if baseline is not None else None},
                "prepush": {"status": "未执行", "exit_code": None, "since": doc["from_version"],
                            "report": "prepush.json", "log": "prepush.log", "limitations": []}}
    write_json(out / "delivery-manifest.json", delivery)
    try:
        delivery["prepush"] = run_prepush(out, doc, records, server,
                                        baseline=baseline, members=members, **prepush_options)
        if baseline is not None:
            baseline.save_lock(out / "baseline.lock.json")
    except Exception as exc:
        delivery["prepush"].update(status="问题", exit_code=2, limitations=[str(exc)])
        write_json(out / "delivery-manifest.json", delivery)
        raise
    from .client_compatibility import write_compatibility
    delivery["client_compatibility"] = write_compatibility(
        out, requirements, provides, allow_unknown_client=allow_unknown_client,
        client_profile=selected_profile)
    validate_document(delivery, "delivery-manifest.schema.json")
    write_json(out / "delivery-manifest.json", delivery)
    # Snapshot copies and logs remain auditable, but are not installation artifacts.
    sums = []
    for file in sorted(out.rglob("*")):
        if file.is_file() and file.name != "SHA256SUMS" and "validation" not in file.relative_to(out).parts:
            sums.append(f"{sha256(file.read_bytes())}  {file.relative_to(out).as_posix()}")
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n", "utf-8")
    return delivery
