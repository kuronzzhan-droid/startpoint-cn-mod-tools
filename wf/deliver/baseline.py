"""Resolve delivery baselines from manifests, without copying their archives."""
from __future__ import annotations

import json
from pathlib import Path

from wf.view import ManifestView
from wf.view.chain import VERSION, manifest_entries, version


def check_versions(doc, view):
    if view.tip != doc["from_version"]:
        raise ValueError("问题: baseline view tip must equal from_version")
    entries = manifest_entries(view.manifest, view.search_dirs, view.manifests)
    target = doc["to_version"]
    if any(entry.get("version") == target for entry in entries):
        raise ValueError(f"问题: to_version {target} already occupied; same-version recast is forbidden")
    newer = [entry["version"] for entry in entries
             if entry.get("enabled", True) is not False
             and VERSION.fullmatch(str(entry.get("version", "")))
             and version(entry["version"]) > version(doc["from_version"])]
    header = json.loads(view.manifest.read_text("utf-8-sig")).get("cdn_version")
    if header and version(header) > version(doc["from_version"]):
        newer.append(header)
    if newer:
        raise ValueError(f"问题: from_version {doc['from_version']} is stale; manifest reaches {max(newer, key=version)}")


def resolve_baseline(doc, *, base_store=None, baseline_manifest=None, baseline_active=None,
                     baseline_zips=(), baseline_zip_dirs=(), baseline_manifests=(),
                     baseline_view=None, view_lock=None, base_version="1.4.131",
                     no_baseline_i_know=False, **_unused):
    """An escape waives missing client provenance, never contradictory evidence."""
    if baseline_view is not None:
        if not isinstance(baseline_view, ManifestView):
            raise ValueError("baseline_view must be a wf view ManifestView")
        view = baseline_view
    else:
        manifest = Path(baseline_manifest) if baseline_manifest is not None else None
        if manifest is None and baseline_active is not None:
            manifest = Path(baseline_active).parent / "manifest.json"
        if manifest is None:
            if baseline_zips or view_lock or baseline_zip_dirs or baseline_manifests:
                raise ValueError("问题: baseline archives/lock require --baseline-manifest")
            if not no_baseline_i_know:
                raise ValueError("问题: delivery requires a wf view or --baseline-manifest; "
                                 "explicit --no-baseline-i-know is required to waive it")
            if base_store is not None and not Path(base_store).is_dir():
                raise ValueError("base store is not a directory")
            return None
        dirs = [Path(p) for p in baseline_zip_dirs]
        if baseline_active is not None:
            dirs.append(Path(baseline_active))
        dirs.extend(Path(p).parent for p in baseline_zips)
        store = Path(base_store) if base_store is not None else None
        if store is not None and (store / "upload").is_dir():
            store = store / "upload"
        view = ManifestView(doc["from_version"], store=store, manifest=manifest,
                            search_dirs=dirs, manifests=list(baseline_manifests),
                            base_version=base_version, lock=view_lock)
    check_versions(doc, view)
    view.verify()
    selected = {p.resolve() for p in view.zips}
    if any(Path(p).resolve() not in selected for p in baseline_zips):
        raise ValueError("问题: baseline ZIP is not selected by the manifest chain")
    return view


def verify_client(doc, members, view, *, base_store=None, archives=()):
    """Check changed bytes against the exact source view, then its overlay."""
    from .assert_box import verify
    from .changeset import sha256
    errors = []
    if view is None:
        if base_store is None:
            return errors
        assertions = {"from_version": doc["from_version"], "to_version": doc["to_version"],
                      "files": [{"kind": "client", "member": name,
                                 "before_sha256": entry["before_sha256"], "sha256": entry["sha256"]}
                                for name, (_, entry) in members.items()]}
        return verify(assertions, phase="pre", manifest={"cdn_version": doc["from_version"]}, store=base_store)
    for name, (raw, entry) in members.items():
        try:
            before = view.read_member(name)[0]
        except FileNotFoundError:
            before = None
        actual = sha256(before) if before is not None else None
        if actual != entry["before_sha256"]:
            errors.append(f"{name}: expected {entry['before_sha256']}, got {actual}")
    # Re-read generated candidate bytes instead of trusting the in-memory payload.
    if archives:
        import zipfile
        actual = {}
        for path in archives:
            with zipfile.ZipFile(path) as archive:
                actual.update({name: sha256(archive.read(name)) for name in archive.namelist()})
        if actual != {name: entry["sha256"] for name, (_, entry) in members.items()}:
            errors.append("candidate post hashes differ from change set")
    check_versions(doc, view)
    view.verify()
    return errors
