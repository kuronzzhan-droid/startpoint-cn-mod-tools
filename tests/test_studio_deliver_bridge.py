"""Bridge contracts: locked inputs, real M1 archives, failures and CLI dispatch."""
import json
import zipfile
from pathlib import Path

import pytest

import wf_mod_tool as core
from wf.deliver.changeset import member_name, sha256
from wf.studio import deliver_bridge as bridge
from wf.studio.draft import build_parser, main
from wf.studio.drafts import DraftError, DraftStore, new_change_id, now
from wf.view import ManifestView


@pytest.fixture
def case(tmp_path, monkeypatch):
    active, store = tmp_path / "active", tmp_path / "store"
    active.mkdir()
    store.mkdir()
    archive_name = "pinball-1.4.131-1.4.132-1-test.zip"
    character = core.build_orderedmap(core.OrderedMap("character", ["139985"], [b"demo"], Path("fixture")))
    with zipfile.ZipFile(active / archive_name, "w") as archive:
        archive.writestr(member_name("common", "master/character/character.orderedmap"), character)
        archive.writestr(member_name("common", "test.bin"), b"old")
        archive.writestr(member_name("medium", "test.bin"), b"untouched other layer")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cdn_version": "1.4.132", "patches": [
        {"version": "1.4.132", "depends_on": "1.4.131", "chain": [archive_name], "type": "patch"}]}), "utf-8")
    drafts = DraftStore(tmp_path / "drafts")
    changeset = drafts.put_change("139985", "demo", "1.4.132", {
        "id": new_change_id(), "kind": "voice_line", "title": "桥接隔离夹具", "createdAt": now(),
        "target": {"voice": "home/home_0"}, "params": {"sourceName": "fixture.mp3", "loudness": -14,
        "durationSeconds": 1, "format": {}}, "files": [], "pending": [], "checks": []})
    monkeypatch.setattr(bridge, "compile_draft", lambda *a, **kw: (
        {("common", "test.bin"): b"new"}, {}, {}, [{"old": "old", "new": "new"}], []))
    view = ManifestView("1.4.132", store=store, manifest=manifest, search_dirs=[])
    return drafts, changeset, view, tmp_path / "out"


def build(case, **kwargs):
    drafts, _, view, out = case
    return bridge.build_draft("139985", from_version="1.4.132", to_version="1.4.133",
                              store=drafts, baseline_view=view, out=out, **kwargs)


def test_bridge_real_delivery_roundtrip_and_local_inputs(case):
    result = build(case)
    assert result["ok"] and result["prepush"]["exit_code"] == 0
    out = case[-1]
    delivery = out / "delivery"
    doc = json.loads((out / "inputs/changeset.json").read_text("utf-8"))
    assert doc["members"][0]["before_sha256"] == sha256(b"old")
    with zipfile.ZipFile(next(delivery.glob("pinball-*.zip"))) as archive:
        assert archive.namelist() == [member_name("common", "test.bin")]
        assert archive.read(archive.namelist()[0]) == b"new"
    assert case[2].read_member(member_name("medium", "test.bin"))[0] == b"untouched other layer"
    assert result["compat"][0]["status"] == "未执行"
    for name in ("assert_box.py", "assert-box.json", "requires.json", "compat.json", "check.json", "baseline.lock.json"):
        assert (delivery / name).is_file()
    for line in (delivery / "SHA256SUMS").read_text("utf-8").splitlines():
        digest, rel = line.split("  ", 1)
        assert sha256((delivery / rel).read_bytes()) == digest
    assert json.loads((delivery / "prepush.json").read_text("utf-8"))["companion_reward_keys"]["executed"]


@pytest.mark.parametrize("field,value", [("baseView", "1.4.131"), ("code", "wrong"), ("characterId", "7")])
def test_stale_draft_is_rejected_before_output(case, field, value):
    drafts, changeset, _, out = case
    changeset[field] = value
    drafts._write("139985", changeset)
    with pytest.raises(DraftError, match="不一致"):
        build(case)
    assert not out.exists()


def test_tampered_source_file_is_rejected_before_compile(case):
    drafts, changeset, _, out = case
    changeset["changes"][0]["params"]["sourceFile"] = "sources/missing.mp3"
    drafts._write("139985", changeset)
    with pytest.raises(DraftError, match="缺少源文件"):
        build(case)
    assert not out.exists()


def test_outside_output_and_existing_output_rejected(case):
    from wf.paths import REPOSITORY
    with pytest.raises(PermissionError):
        bridge.build_draft("139985", from_version="1.4.132", to_version="1.4.133",
                           out=REPOSITORY.parent / "forbidden")
    case[-1].mkdir()
    (case[-1] / "keep").write_text("keep", "utf-8")
    with pytest.raises(DraftError, match="必须为空"):
        build(case)
    assert (case[-1] / "keep").read_text("utf-8") == "keep"


def test_prepush_failure_propagates_to_build_result(case, monkeypatch):
    from wf.deliver import prepush
    def fail(argv, **kwargs):
        report = Path(argv[argv.index("--json") + 1])
        report.write_text(json.dumps({"since": "1.4.132", "findings": [
            {"level": "ERROR", "fid": "test", "msg": "negative control"}]}), "utf-8")
        return 1
    monkeypatch.setattr(prepush, "main", fail)
    result = build(case)
    assert result["ok"] is False and result["prepush"]["exit_code"] == 1


def test_compat_failure_is_not_a_success(case, monkeypatch):
    from wf.rules.catalog import result
    monkeypatch.setattr(bridge, "_checks", lambda *a: ([], [result(
        "capability.missing", "问题", "缺能力", blocking=True)]))
    assert build(case)["ok"] is False


def test_cli_build_syntax_and_failure_exit(tmp_path, monkeypatch, capsys):
    args = build_parser().parse_args(["build", "139985", "--from", "1.4.233", "--to", "1.4.234",
                                     "--out", str(tmp_path / "out"), "--server-dir", str(tmp_path)])
    assert args.from_version == "1.4.233" and args.server_dir == tmp_path
    monkeypatch.setattr("wf.studio.draft_commands.run_build", lambda *a: {"ok": False, "reason": "prepush"})
    assert main(["build", "139985", "--from", "1.4.233", "--to", "1.4.234", "--out", str(tmp_path)]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


@pytest.mark.parametrize("target", ["1.4.132", "1.4.131", "broken"])
def test_build_requires_forward_version(case, target):
    with pytest.raises(DraftError):
        bridge.open_baseline("1.4.132", target, baseline_view=case[2])
