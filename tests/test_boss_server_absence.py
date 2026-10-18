"""Missing optional server files remain absent in draft and delivery assertions."""
import json

import pytest

from wf.boss.edit_state import digest
from wf.deliver.archives import write_archives
from wf.deliver.assert_box import verify
from wf.deliver.changeset import load_changeset, member_name
from wf.deliver.manifests import write_manifests
from wf.studio.deliver_bridge import _stage, compile_draft
from test_studio_boss_checks import fixture_editor, request


def test_missing_optional_reward_files_survive_real_delivery_assertions(tmp_path):
    editor = fixture_editor(tmp_path)
    absent = [f"assets/{name}_cnmod.json" for name in ("score_reward", "rare_score_reward")]
    for target in absent:
        (editor.server_dir / target).unlink()
    draft = editor.apply("new", request())["changeset"]
    inputs = draft["changes"][0]["params"]["inputs"]
    assert all(inputs["server"][target] is None for target in absent)
    compiled = compile_draft(editor.source, editor.store, draft, server_dir=editor.server_dir)
    assert all(compiled[2][target] is None for target in absent)

    # Use the production staging, archive and assertion writers with binary fixtures.
    view = editor.source.view
    members = {member_name("common", logical): raw for logical, raw in view.files.items()}
    view.read_member = lambda name: (members[name], "fixture")
    filename = _stage(tmp_path / "out", draft, editor.source, compiled, "1.4.237")
    document, client, _ = load_changeset(filename)
    out = tmp_path / "delivery"
    records = write_archives(out, client, lambda seq: f"candidate-{seq}.zip")
    write_manifests(out, document, client, records)
    assertions = json.loads((out / "assert-box.json").read_text("utf-8"))
    assertions["files"] = [entry for entry in assertions["files"] if entry["kind"] == "server"]
    actual = {entry["target"]: entry["before_sha256"] for entry in assertions["files"]}
    assert all(actual[target] is None for target in absent)
    assert actual["assets/hard_multi_event_quest.json"] == digest(
        (editor.server_dir / "assets/hard_multi_event_quest.json").read_bytes())
    assert verify(assertions, phase="pre", manifest={"cdn_version": "1.4.236"},
                  server_dir=editor.server_dir) == []
    assert all(not (editor.server_dir / target).exists() for target in absent)

    # Appearance of even an empty file is drift from the saved absence assertion.
    (editor.server_dir / absent[0]).write_bytes(b"{}\n")
    assert verify(assertions, phase="pre", manifest={"cdn_version": "1.4.236"},
                  server_dir=editor.server_dir)
    with pytest.raises(ValueError, match="SHA-256 drift"):
        compile_draft(editor.source, editor.store, draft, server_dir=editor.server_dir)
