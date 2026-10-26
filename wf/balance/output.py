"""Local review artifacts and the shared deliver change-set contract."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from wf.view.safety import local_output


def write_result(recipe, result, output, verification):
    output = local_output(output)
    changeset = {key: recipe[key] for key in ("id", "name", "from_version", "to_version", "slug", "created_at", "local_test_only")}
    changeset.update(schema="wf-change-set/1", experimental=recipe.get("experimental", False),
                     capabilities=recipe.get("capabilities", []), members=[], changes=result.changes)
    # Preflight every path and detect collisions before creating the first file.
    payloads = {}
    for name, data in sorted(result.files.items()):
        relative = "payload/" + name
        target = local_output(output / relative)
        if not target.is_relative_to(output):
            raise ValueError(f"member escapes output: {name}")
        payloads[target] = data
        changeset["members"].append({"root": "common", "logical_path": result.logical_paths[name],
            "source": relative, "sha256": hashlib.sha256(data).hexdigest(),
            "before_sha256": result.before_sha256[name]})
    archive_name = f"pinball-{recipe['from_version']}-{recipe['to_version']}-1-{recipe['slug']}-local.zip"
    archive_path = local_output(output / archive_name)
    metadata = [output / "changeset.json", output / "balance-report.json", archive_path]
    if any(path.exists() for path in [*payloads, *metadata]):
        raise FileExistsError(f"balance output already exists; choose a fresh output directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    for target, data in payloads.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(result.files.items()):
            archive.writestr(name, data)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None or any(archive.read(name) != data for name, data in result.files.items()):
            raise ValueError("balance archive readback failed")
    (output / "changeset.json").write_text(json.dumps(changeset, ensure_ascii=False, indent=2) + "\n", "utf-8")
    report = {"schema": "wf-balance-report/1", "recipe": recipe["id"], "status": "满足",
        "member_count": len(result.files), "operation_count": len(result.changes),
        "cell_count": sum(len(change["cells"]) for change in result.changes),
        "touched_keys": result.touched_keys, "view_verification": verification,
        "warnings": result.warnings, "dsl_gate": result.dsl_gate, "ownership": result.ownership,
        "archive": archive_name, "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        "installed_bytes": sum(map(len, result.files.values())), "changeset": "changeset.json"}
    (output / "balance-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return report
