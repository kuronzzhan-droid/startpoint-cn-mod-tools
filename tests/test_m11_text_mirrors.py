"""Counterexamples for sparse dual mirrors and byte-preserving JSON edits."""
import json

import pytest

from test_m1_text import edit_for, workspace  # noqa: F401 - shared synthetic view
from wf.text import TextWorkspace
from wf.text.edit import prepare_edit, stage_edit
from wf.text.json_patch import patch_columns
from wf.text.model import RANK_TARGET, SERVER_TARGET, sha256


def title_edit(workspace):
    return edit_for(workspace, character_text={"3": {"old": "白狼骑士", "new": "月下骑士"}})


def metadata():
    return dict(id="text-1", name="文本", from_version="1.4.1", to_version="1.4.2",
                slug="text", created_at="2026-10-17")


def test_missing_rank_source_is_a_hard_failure(workspace):
    missing = TextWorkspace(workspace.view, workspace.server_path)
    with pytest.raises(ValueError, match="character_text_rank_p5b.json"):
        prepare_edit(missing, title_edit(missing))


@pytest.mark.parametrize("target", [SERVER_TARGET, RANK_TARGET])
def test_sparse_mirrors_keep_absent_character_absent(workspace, target):
    workspace.server_paths[target].write_bytes(b'{ "untouched" : [ [ "keep" ] ] }\r\n')
    current = TextWorkspace(workspace.view, workspace.server_path, workspace.rank_path)
    prepared = prepare_edit(current, title_edit(current))
    assert prepared["servers"][target] == current.server_raws[target]
    other = RANK_TARGET if target == SERVER_TARGET else SERVER_TARGET
    assert json.loads(prepared["servers"][other])["1"][0][3] == "月下骑士"
    assert "1" not in json.loads(prepared["servers"][target])


def test_missing_character_in_both_mirrors_is_a_hard_failure(workspace):
    for path in workspace.server_paths.values():
        path.write_bytes(b"{}")
    current = TextWorkspace(workspace.view, workspace.server_path, workspace.rank_path)
    with pytest.raises(ValueError, match="missing from both"):
        prepare_edit(current, title_edit(current))


def test_rank_input_participates_in_snapshot_and_staging_assertions(workspace, tmp_path):
    edit = title_edit(workspace)
    workspace.rank_path.write_bytes(workspace.rank_path.read_bytes() + b"\n")
    current = TextWorkspace(workspace.view, workspace.server_path, workspace.rank_path)
    with pytest.raises(ValueError, match="snapshot changed"):
        prepare_edit(current, edit)
    prepared = prepare_edit(current, title_edit(current))
    current.rank_path.write_bytes(current.rank_path.read_bytes() + b"\n")
    output = tmp_path / "rank-drift"
    with pytest.raises(ValueError, match="character_text_rank_p5b.json changed"):
        stage_edit(prepared, output, metadata())
    assert not output.exists()


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_edit_changes_only_selected_tokens_in_both_mirrors(workspace, tmp_path, newline):
    original = {}
    for index, (target, path) in enumerate(workspace.server_paths.items()):
        source = json.loads(path.read_bytes())
        source["1"].append(["白狼骑士", "do not change this extra row"])
        source = {"z-first": {"escaped": "\\u4e2d", "same": "白狼骑士"}, **source,
                  "a-last": [1, 2, {"space": "  "}]}
        raw = (json.dumps(source, ensure_ascii=False, indent="\t" if index else 4)
               + "\n").replace("\n", newline).encode("utf-8")
        path.write_bytes(raw)
        original[target] = raw
    current = TextWorkspace(workspace.view, workspace.server_path, workspace.rank_path)
    prepared = prepare_edit(current, title_edit(current))
    for target, raw in original.items():
        # The selected c3 is the second occurrence; the other character, nested
        # metadata, extra row, separators and every indentation byte survive.
        token = '"白狼骑士"'.encode()
        offset = raw.index(token, raw.index(token) + len(token))
        expected = raw[:offset] + '"月下骑士"'.encode() + raw[offset + len(token):]
        assert prepared["servers"][target] == expected
        assert current.server_paths[target].read_bytes() == raw
    target = stage_edit(prepared, tmp_path / "minimal", metadata())
    entries = json.loads(target.read_bytes())["server_changes"]
    assert {entry["target"]: entry["before_sha256"] for entry in entries} == {
        key: sha256(raw) for key, raw in original.items()}
    assert prepared["document"]["server_character_text_rank_p5b"][0][3] == "月下骑士"


def test_string_token_replacement_preserves_escaped_neighbors_and_embedded_newlines():
    raw = b'{"2":[["keep"]], "1": [["\\u4e2d", "old", "escaped\\nline"]]}\r\n'
    new = 'quote " slash \\ and\r\nnewline'
    assert patch_columns(raw, "1", {1: new}) == raw.replace(
        b'"old"', json.dumps(new, ensure_ascii=False).encode())
    assert patch_columns(raw, "1", {1: "old"}) is raw


def test_ambiguous_json_keys_cannot_be_rewritten():
    with pytest.raises(ValueError, match="duplicate JSON key"):
        patch_columns(b'{"1":[["first"]],"1":[["second"]]}', "1", {0: "new"})


def test_cli_read_accepts_rank_and_exposes_its_snapshot(workspace, tmp_path, monkeypatch):
    import wf.view
    from wf.text.cli import main
    workspace.view.verify = lambda: None
    monkeypatch.setattr(wf.view, "ManifestView", lambda **kwargs: workspace.view)
    output = tmp_path / "read.json"
    assert main(["read", "1", "--tip", "1.4.1", "--server-text", str(workspace.server_path),
                 "--rank-text", str(workspace.rank_path), "--output", str(output)]) == 0
    document = json.loads(output.read_bytes())
    assert document["server_character_text_rank_p5b"][0][3] == "白狼骑士"
    assert document["sources"][RANK_TARGET] == sha256(workspace.rank_path.read_bytes())
