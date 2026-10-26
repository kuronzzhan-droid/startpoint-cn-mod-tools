"""Public command adapters use the same local view and emit one JSON line."""
import json

import wf_quest_lib as codec
from test_studio_chain_views import chain, archive, write_manifest  # noqa: F401
from wf.studio.draft import main
from wf.studio.id_catalog import CHARACTER
from wf.view.base149 import member


def arguments(chain):
    store, manifest, zips, _ = chain
    return ["--manifest", str(manifest), "--store", str(store), "--zip-dir", str(zips)]


def output(capsys):
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    return json.loads(lines[0])


def test_ids_cli_reads_manifest_and_extra_overlay(chain, capsys):
    store, manifest, zips, _ = chain
    _, edge = archive(zips, "1.4.131", "1.4.132", {
        member(CHARACTER): codec.build_node({"199001": "mother"})})
    extra, _ = archive(zips, "1.4.132", "1.4.133", {
        member(CHARACTER): codec.build_node({"199001": "mother", "199002": "new"})})
    write_manifest(manifest, [edge])
    listing = zips / "extras.txt"
    listing.write_text(extra.name, encoding="utf-8")
    args = arguments(chain) + ["--tip", "1.4.132", "--extra-zips-file", str(listing),
                               "--drafts", str(zips / "drafts"), "ids", "check", "character", "199002"]
    assert main(args) == 0
    result = output(capsys)
    assert result["ok"] and not result["result"]["available"]
    assert result["result"]["viewVersion"] == "1.4.133"


def test_version_cli_selects_named_view_and_skips_registration(chain, capsys):
    store, manifest, zips, profile = chain
    _, edge = archive(zips, "1.4.131", "1.4.282", {})
    write_manifest(manifest, [edge])
    profile.write_text(json.dumps({"views": {"test175": {"store": str(store),
        "manifest": str(manifest), "zip_dirs": [str(zips)]}}}), encoding="utf-8")
    reservations = zips / "reservations.json"
    reservations.write_text(json.dumps({"1.4.283": {"purpose": "fixture", "owner": "fixture",
                                                          "date": "2026-10-25"}}), encoding="utf-8")
    assert main(["versions", "next", "--view", "test175", "--reservations-file", str(reservations)]) == 0
    result = output(capsys)["result"]
    assert result["next"] == "1.4.284" and result["view"] == "test175"


def test_export_cli_materializes_current_view_and_errors_as_json(chain, capsys):
    store, manifest, zips, _ = chain
    name = member("fixture")
    _, edge = archive(zips, "1.4.131", "1.4.132", {name: b"fixture"})
    write_manifest(manifest, [edge])
    target = zips / "exported"
    args = arguments(chain) + ["export-store", "--out", str(target), "--copy"]
    assert main(args) == 0 and output(capsys)["result"]["version"] == "1.4.132"
    assert (target / name).read_bytes() == b"fixture"
    assert main(args) == 1 and output(capsys)["ok"] is False
