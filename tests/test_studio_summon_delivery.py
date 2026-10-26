"""Real summon draft compilation through the shared delivery and PR 26 gates."""
import json
from pathlib import Path
import zipfile

import pytest

from wf.deliver.changeset import member_name
from wf.studio.clone_tables import leaf
from wf.studio.drafts import DraftStore
from wf.studio.source import StudioSource
from wf.view import ManifestView

from test_studio_bundle_keys import apk_file, bundled_member
from test_studio_character_clone import env as clone_env, NEW as CLONED_CID, request as clone_request
from test_studio_summon import (
    BALL, CID, NEW_BALL, PF, STRINGS, fixture_files, flat, ordered, request, rows,
)


@pytest.fixture
def delivery_env(tmp_path, monkeypatch):
    from wf.studio.summon import SummonEditor
    # The synthetic APK cache stays outside the simulated repository while all
    # test artifacts remain under pytest's configured work/ basetemp.
    monkeypatch.setattr("wf.studio.bundle_keys.REPOSITORY", tmp_path / "repository")
    active, base = tmp_path / "active", tmp_path / "store"
    active.mkdir()
    base.mkdir()
    archive = active / "pinball-1.4.131-1.4.233-1-synthetic.zip"
    files = fixture_files()
    with zipfile.ZipFile(archive, "w") as bundle:
        for (root, logical), raw in files.items():
            bundle.writestr(member_name(root, logical), raw)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cdn_version": "1.4.233", "patches": [{
        "version": "1.4.233", "depends_on": "1.4.131", "chain": [archive.name], "type": "patch"}]}),
        encoding="utf-8")
    view = ManifestView("1.4.233", store=base, manifest=manifest, search_dirs=[active])
    source = StudioSource(view)
    store = DraftStore(tmp_path / "drafts")
    editor = SummonEditor(source, store=store)
    pathlist = tmp_path / "paths.txt"
    pathlist.write_text("\n".join(sorted(logical for _, logical in files)), encoding="utf-8")
    apk = apk_file(tmp_path, [
        (bundled_member(PF), ordered({"native_pf": leaf([["native"]])})),
        (bundled_member(BALL), ordered({"800": leaf([["native"]])})),
    ])
    return source, store, editor, view, pathlist, apk


def build(env, out, **kwargs):
    from wf.studio.deliver_bridge import build_draft
    _, store, _, view, pathlist, apk = env
    return build_draft(CID, from_version="1.4.233", to_version="1.4.234", out=out,
                       store=store, baseline_view=view, pathlist=pathlist,
                       allow_unknown_client=True, apk=[apk], bundle_cache_dir=out.parent / "cache", **kwargs)


def test_build_draft_preserves_keys_infers_p13_and_passes_bundle_gates(delivery_env, tmp_path):
    source, store, editor, *_ = delivery_env
    editor.apply(CID, request(extensions={"flip_pf": {"enabled": True, "min_interval_frames": 10},
                                          "ball_pf_action": "fixture_pf"}))
    before = source.raw(BALL)
    result = build(delivery_env, tmp_path / "delivery")
    assert result["ok"], result
    assert result["bundleCheck"]["status"] == "ok"
    assert result["clientExtensions"]["status"] == "ok"
    assert result["keyDiff"]["ok"] and result["keyDiff"]["counts"]["removed"] == 0
    assert result["keyDiff"]["counts"]["foreign"] == result["keyDiff"]["counts"]["unknown"] == 0
    ball = next(row for row in result["keyDiff"]["tables"] if row["logical"] == BALL)
    assert ball["added"] == ball["owned"] == [NEW_BALL]
    delivery = Path(result["delivery"])
    requires = json.loads((delivery / "requires.json").read_text(encoding="utf-8"))
    assert {"client.summon.flip_pf@1", "client.ball.pf_action@1", "client.summon.cutin_preload@1"} <= set(
        requires["requires"]["clientCapabilities"])
    assert not json.loads((tmp_path / "delivery/inputs/changeset.json").read_text(encoding="utf-8"))["server_changes"]
    assert source.raw(BALL) == before and store.load(CID)["changes"][0]["kind"] == "summon_clone"
    assert all((delivery / name).is_file() for name in (
        "bundle-check.json", "key-diff.json", "client-extensions.json", "requires.json", "SHA256SUMS"))


def test_target_apk_collision_blocks_real_delivery(delivery_env, tmp_path):
    _, _, editor, _, _, apk = delivery_env
    editor.apply(CID, request())
    apk_file(tmp_path, [(bundled_member(BALL), ordered({NEW_BALL: leaf([["bundled collision"]])}))],
             name=apk.name)
    result = build(delivery_env, tmp_path / "collision")
    assert not result["ok"]
    assert result["bundleCheck"]["status"] == "collision"
    assert any(entry["blocking"] for entry in result["safetyChecks"])


def test_compile_composes_with_existing_custom_string_overlay(delivery_env):
    from wf.studio.summon import compile_summons
    source, store, editor, *_ = delivery_env
    editor.apply(CID, request(extensions={"flip_pf": {"enabled": True}}))
    original = rows(source.raw(STRINGS))
    overlay = ordered({**original, "other_draft_text": leaf([["同一草稿已有文本"]])})
    compiled = compile_summons(source, store, store.load(CID), members={("common", STRINGS): overlay})
    assert flat(compiled["client"][STRINGS], "other_draft_text") == [["同一草稿已有文本"]]
    assert flat(compiled["client"][STRINGS], "wfx_summon_flip_pf_" + NEW_BALL) == [["1"]]


def test_summon_compiles_inside_new_character_clone_draft(clone_env):
    from wf.studio.character_clone import clone
    from wf.studio.deliver_bridge import compile_draft
    from wf.studio.summon import SummonEditor
    from test_studio_summon import ATTACK, HP, LEVEL, OLD_BALL
    source, store, ops, server = clone_env
    for key, raw in fixture_files().items():
        if key[1] in {BALL, LEVEL, HP, ATTACK, STRINGS, PF}:
            source.view.files[key] = raw
    clone(ops, clone_request(), server_dir=server)
    editor = SummonEditor(source, store=store)
    editor.apply(CLONED_CID, request(template={"kind": "multiball", "id": OLD_BALL}))
    draft = store.load(CLONED_CID)
    compiled, servers, _, _, _ = compile_draft(source, store, draft, server_dir=server)
    assert {change["kind"] for change in draft["changes"]} == {"character_clone", "summon_clone"}
    assert NEW_BALL in rows(compiled["common", BALL]) and len(servers) == 5
