"""The real CLI build uses the named view and every selected local ZIP."""
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from wf.studio import draft
from wf.studio.character_clone import clone
from wf.studio.clone_tables import T
from wf.studio.operations import DraftOps
from wf.studio.source import build_source
from wf.deliver.changeset import member_name

from test_studio_character_clone import NEW, OLD, env, request


def write_archive(directory, before, after, sequence, files):
    archive = directory / f"pinball-{before}-{after}-{sequence}-fixture.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for (root, logical), raw in files.items():
            bundle.writestr(member_name(root, logical), raw)
    return archive


@pytest.mark.parametrize("explicit_baseline", [False, True], ids=["named", "baseline-overrides"])
def test_real_cli_build_preserves_named_base_and_multipart_extras(env, tmp_path, monkeypatch,
                                                               explicit_baseline):
    source, store, original_ops, server = env
    archives = tmp_path / "archives"
    archives.mkdir()
    base = tmp_path / "baseline"
    base.mkdir()
    # Missing either extra must break the clone/build: these are actual donor inputs.
    extra_logicals = (T.TEXT, T.SPEECH)
    baseline_files = {key: raw for key, raw in source.view.files.items()
                      if key[1] not in extra_logicals}
    baseline = write_archive(archives, "1.4.200", "1.4.233", 1, baseline_files)
    extras = [write_archive(archives, "1.4.233", "1.4.235", index,
                            {("common", logical): source.view.files["common", logical]})
              for index, logical in enumerate(extra_logicals, 1)]
    listing = archives / "extras.txt"
    listing.write_text("\n".join(path.name for path in extras) + "\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cdn_version": "1.4.233", "patches": [
        {"version": "1.4.233", "depends_on": "1.4.200", "chain": [baseline.name],
         "type": "patch"}]}), encoding="utf-8")
    supplemental = tmp_path / "supplemental.json"
    supplemental.write_text('{"patches": []}', encoding="utf-8")
    selected = {"manifest": str(manifest), "store": str(base), "zip_dirs": [str(archives)],
                "base_version": "1.4.200", "tip": "1.4.233", "manifests": [str(supplemental)]}
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"views": {"test": selected}}), encoding="utf-8")
    monkeypatch.setenv("WF_PATHS_PROFILE", str(profile))
    monkeypatch.delenv("WF_STUDIO_VIEW", raising=False)
    selected_source = build_source(view_name="test", extra_lists=[listing])
    assert selected_source.version == "1.4.235"
    clone_ops = DraftOps(selected_source, store=store, characters=original_ops.character_list)
    clone(clone_ops, request(), server_dir=server)
    pathlist = tmp_path / "paths.txt"
    pathlist.write_text("\n".join(sorted({item["logical"]
                        for item in store.load(NEW)["changes"][0]["files"]})), encoding="utf-8")
    argv = ["--drafts", str(store.root), "--view", "test", "--extra-zips-file", str(listing),
            "build", NEW, "--from", "1.4.235", "--to", "1.4.236", "--out", str(tmp_path / "build"),
            "--server-dir", str(server), "--pathlist", str(pathlist), "--allow-unknown-client"]
    if explicit_baseline:
        # Build-specific options override the named defaults, while keeping extras.
        selected.update(manifest=str(tmp_path / "missing.json"), store=str(tmp_path / "missing-store"),
                        zip_dirs=[str(tmp_path / "missing-zips")], base_version="1.4.199",
                        manifests=[str(tmp_path / "missing-supplemental.json")])
        profile.write_text(json.dumps({"views": {"test": selected}}), encoding="utf-8")
        argv.extend(["--baseline-manifest", str(manifest), "--base-store", str(base),
                     "--base-version", "1.4.200", "--baseline-zip-dir", str(archives),
                     "--baseline-manifest-extra", str(supplemental)])
    result = draft.run(draft.build_parser().parse_args(argv))
    assert result["ok"], json.dumps(result, ensure_ascii=False, indent=2)
    delivery = Path(result["delivery"])
    document = json.loads((delivery / "delivery-manifest.json").read_text(encoding="utf-8"))
    assert (document["from_version"], document["to_version"]) == ("1.4.235", "1.4.236")
    lock = json.loads((delivery / "baseline.lock.json").read_text(encoding="utf-8"))
    assert (lock["base_version"], lock["tip"]) == ("1.4.200", "1.4.233")
    assert lock["zips"] == [{"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                            for path in [baseline, *extras]]
    staged = json.loads((tmp_path / "build/inputs/changeset.json").read_text(encoding="utf-8"))
    assert staged["from_version"] == "1.4.235" and len(staged["server_changes"]) == 5
    assert OLD in selected_source.table("character") and NEW not in selected_source.table("character")
