"""PF clone contracts using complete synthetic ActionDsl programs."""
import copy
from types import SimpleNamespace
import zlib

import pytest
import wf_mod_tool as core
from wf.dsl.references import linked_programs
from wf.rules.dsl_signature import validate_action_dsl
from wf.studio.deliver_bridge import compile_draft
from wf.studio.deliver_media import encode_tree, tree as decode_tree
from wf.studio.drafts import DraftError, DraftStore
from wf.studio.ids import next_id
from wf.studio.pf_actions import clone, draft_keys
from wf.studio.pf_catalog import DSL_SUFFIX, PF_TABLE
from wf.studio.pf_dsl import nodes, summary
from test_studio_pf_catalog import Source, apk, cache, paths, table
from test_studio_pf_dependencies import family
from test_studio_timeline import attack, cmd, hit_area, root, show, wait


CID = "199997"


def action(level):
    area = hit_area(-18, 30, level + 1, [], [attack(-18, level)], bta=133 if level == 3 else 0)
    area[1][12] = ["NWay", 2, 0.5]
    value = root(cmd("SetPowerFilpSuppress", 70), area,
                 wait(30, cmd("NotifyPowerflipEnd", -18)), bta=133)
    validate_action_dsl(value)
    return value


@pytest.fixture
def env(tmp_path):
    files = {("common", PF_TABLE): table({"special": paths(), "other_existing": paths()})}
    files.update({("common", path + DSL_SUFFIX): encode_tree(action(level))
                  for level, path in enumerate(paths(), 1)})
    source = Source(files)
    store = DraftStore(tmp_path / "drafts")
    ops = SimpleNamespace(source=source, store=store, character=lambda cid: {"code": "fixture_" + cid})
    return ops


def request(key="my_pf", **options):
    return {"source": "special", "key": key, "element": "暗", "scale": 2, **options}


def replay(ops, cid=CID):
    return compile_draft(ops.source, ops.store, ops.store.load(cid), apks=[])


def unpack(raw):
    ordered = core.read_orderedmap_raw_rows_from_bytes(raw, PF_TABLE)
    return dict(zip(ordered.keys, ordered.rows))


def test_pf_clone_preview_then_save_and_replay_without_mutating_donor(env):
    before = copy.deepcopy(env.source.files)
    preview = clone(env, CID, request(dryRun=True), apks=[])
    assert preview["preview"] and preview["buildable"]
    assert len(preview["files"]) == 4
    assert not env.store.root.exists()
    saved = clone(env, CID, request(), apks=[])
    assert saved["change"]["kind"] == "pf_action_clone"
    assert saved["change"]["params"]["reservations"] == {"power_flip_action": ["my_pf"]}
    assert "dryRun" not in saved["change"]["params"]["spec"]
    members, servers, server_before, assertions, checks = replay(env)
    assert len(members) == 4 and not servers and not server_before
    assert assertions[0]["key"] == "my_pf"
    assert not any(check.get("blocking") or check.get("level") == "error" for check in checks)
    assert env.source.files == before
    assert draft_keys(env.store, CID)["items"][0]["reference"] == "my_pf"


def test_pf_clone_scales_each_tier_and_preserves_complete_lifecycle(env):
    clone(env, CID, request(scale=[0.5, 2, 3]), apks=[])
    members = replay(env)[0]
    for level, scale in enumerate([0.5, 2, 3], 1):
        new = decode_tree(members["common", f"battle/action/power_flip/studio/my_pf$lv{level}" + DSL_SUFFIX])
        original = action(level)
        normal = list(nodes(new, "CreateNormalAttack"))[0]
        assert normal[2] == 6
        assert normal[6] == [{"min": level * scale, "max": level * scale}]
        assert list(nodes(new, "CreateHitArea"))[0][24] == (133 if level == 3 else 0)
        normal[2], normal[6] = 255, [{"min": level, "max": level}]
        assert new == original  # Restoring permitted fields recovers the entire donor.


def test_pf_clone_shared_table_preserves_old_compressed_rows_and_compresses_new(env):
    old = unpack(env.source.raw(PF_TABLE))
    clone(env, CID, request(), apks=[])
    rows = unpack(replay(env)[0]["common", PF_TABLE])
    assert list(rows) == [*old, "my_pf"]
    assert {key: rows[key] for key in old} == old
    decoded = core.read_csv_lines(zlib.decompress(rows["my_pf"]).decode("utf-8"))
    assert decoded == [[f"battle/action/power_flip/studio/my_pf$lv{n}" for n in (1, 2, 3)]]


def test_pf_clone_multiple_changes_share_one_table_and_reserve_each_key(env):
    clone(env, CID, request("first_pf"), apks=[])
    clone(env, CID, request("second_pf", element="水", scale=3), apks=[])
    members, _, _, assertions, _ = replay(env)
    assert len(members) == 7
    assert list(unpack(members["common", PF_TABLE]))[-2:] == ["first_pf", "second_pf"]
    assert [entry["key"] for entry in assertions] == ["first_pf", "second_pf"]
    assert [entry["key"] for entry in draft_keys(env.store, CID)["items"]] == ["first_pf", "second_pf"]
    for cid in (CID, "199996"):
        with pytest.raises(DraftError, match="草稿预留"):
            clone(env, cid, request("first_pf"), apks=[])


def test_pf_clone_rejects_existing_cdn_and_bundled_keys(env, tmp_path, cache):
    with pytest.raises(DraftError, match="CDN 或 APK 内置表占用"):
        clone(env, CID, request("other_existing"), apks=[])
    target = apk(tmp_path)
    with pytest.raises(DraftError, match="CDN 或 APK 内置表占用"):
        clone(env, CID, request("knight"), apks=[target], cache_dir=cache)
    assert not env.store.root.exists()


def test_pf_clone_source_drift_blocks_saved_replay(env):
    clone(env, CID, request(), apks=[])
    donor = action(1)
    list(nodes(donor, "SetPowerFilpSuppress"))[0][1] = 99
    env.source.files["common", paths()[0] + DSL_SUFFIX] = encode_tree(donor)
    with pytest.raises(DraftError, match="输入已变化"):
        replay(env)


@pytest.mark.parametrize("scale", [0, -1, float("nan"), float("inf"), True, [1, 2]])
def test_pf_clone_rejects_invalid_multiplier_without_writing(env, scale):
    with pytest.raises((DraftError, ValueError)):
        clone(env, CID, request(scale=scale), apks=[])
    assert not env.store.root.exists()


def test_pf_clone_rejects_unused_or_nonprivate_effect_mapping(env):
    with pytest.raises(DraftError, match="未引用指定特效族"):
        clone(env, CID, request(effects={"battle/effect/unused": "battle/effect/skill_unique/fixture/private"}), apks=[])
    with pytest.raises(DraftError, match="私有特效族|skill_unique"):
        clone(env, CID, request(effects={"battle/effect/unused": "battle/effect/another"}), apks=[])
    assert not env.store.root.exists()


def test_pf_clone_recursively_clones_and_rewrites_child_programs(env):
    child = "battle/action/skill/shared_child"
    grandchild = "battle/action/skill/shared_grandchild"
    child_tree = root(cmd("CreateTargetAttack", -18, 0, 0, ["Specify", 30], grandchild),
                      hit_area(-18, 30, 1, [], [attack(-18, 7)], bta=133))
    grandchild_tree = root(hit_area(-18, 30, 1, [], [attack(-18, 11)], bta=133))
    for value in (child_tree, grandchild_tree):
        validate_action_dsl(value)
    for path in paths():
        donor = decode_tree(env.source.raw(path + DSL_SUFFIX))
        donor[11][1].append(cmd("CreateTargetAttack", -18, 0, 0, ["Specify", 30], child))
        env.source.files["common", path + DSL_SUFFIX] = encode_tree(donor)
    env.source.files["common", child + DSL_SUFFIX] = encode_tree(child_tree)
    env.source.files["common", grandchild + DSL_SUFFIX] = encode_tree(grandchild_tree)
    before = copy.deepcopy(env.source.files)
    clone(env, CID, request(scale=[1, 2, 3]), apks=[])
    members = replay(env)[0]
    assert len(members) == 10  # A private root, child and grandchild for each tier, plus PFA.
    for level in (1, 2, 3):
        root_path = f"battle/action/power_flip/studio/my_pf$lv{level}" + DSL_SUFFIX
        root_tree = decode_tree(members["common", root_path])
        child_path, = linked_programs(root_tree)
        assert child_path.startswith(f"battle/action/power_flip/studio/my_pf$lv{level}_sub_")
        copied_child = decode_tree(members["common", child_path])
        assert list(nodes(copied_child, "CreateNormalAttack"))[0][6][0]["max"] == 7 * level
        grandchild_path, = linked_programs(copied_child)
        copied_grandchild = decode_tree(members["common", grandchild_path])
        assert list(nodes(copied_grandchild, "CreateNormalAttack"))[0][6][0]["max"] == 11 * level
        assert not ({child + DSL_SUFFIX, grandchild + DSL_SUFFIX} & {child_path, grandchild_path})
    assert env.source.files == before


def with_effect(ops, effect):
    for path in paths():
        value = decode_tree(ops.source.raw(path + DSL_SUFFIX))
        value[11][1].append(show("fixture", effect, -18, ["SpecifyEffectLifetimeDirectly", 30]))
        validate_action_dsl(value)
        ops.source.files["common", path + DSL_SUFFIX] = encode_tree(value)


def test_pf_clone_reuses_existing_private_effect_family(env):
    old = "battle/effect/powerflip/fixture"
    new = "battle/effect/skill_unique/demo/private"
    with_effect(env, old + "/burst")
    env.source.files.update(family(old + "/burst") | family(new + "/burst"))
    before = copy.deepcopy(env.source.files)
    result = clone(env, CID, request(effects={old: new}), apks=[])
    assert all(level["effectFamilies"] == [new] for level in result["levels"])
    assert len(result["dependencies"]) == 4
    assert all(item["logical"].startswith(new + "/") for item in result["dependencies"])
    members = replay(env)[0]
    assert len(members) == 4  # Existing FX are referenced, not copied into this change.
    for level in (1, 2, 3):
        value = decode_tree(members["common", f"battle/action/power_flip/studio/my_pf$lv{level}" + DSL_SUFFIX])
        assert list(nodes(value, "SpecifyEffectDirectly")) == [["SpecifyEffectDirectly", new + "/burst"]]
    assert env.source.files == before


def test_pf_clone_missing_private_effect_prevents_draft_write(env):
    old = "battle/effect/powerflip/fixture"
    new = "battle/effect/skill_unique/demo/private"
    with_effect(env, old + "/burst")
    env.source.files.update(family(old + "/burst") | family(new + "/burst"))
    del env.source.files["common", new + "/private.atlas.amf3.deflate"]
    with pytest.raises(DraftError, match="预载依赖缺失.*private.atlas"):
        clone(env, CID, request(effects={old: new}), apks=[])
    assert not env.store.root.exists()


def test_pf_clone_scales_dynamic_terms_preserving_mul_and_lv3_marker(env):
    terms = [{"min": 1, "max": 2, "mul": 807}, {"min": 3, "max": 5}]
    for path in paths():
        value = decode_tree(env.source.raw(path + DSL_SUFFIX))
        list(nodes(value, "CreateNormalAttack"))[0][6] = copy.deepcopy(terms)
        env.source.files["common", path + DSL_SUFFIX] = encode_tree(value)
    response = clone(env, CID, request(scale=2.5), apks=[])
    assert all(level["nominalMultiplier"] is None for level in response["levels"])
    members = replay(env)[0]
    for level in (1, 2, 3):
        value = decode_tree(members["common", f"battle/action/power_flip/studio/my_pf$lv{level}" + DSL_SUFFIX])
        assert list(nodes(value, "CreateNormalAttack"))[0][6] == [
            {"min": 2.5, "max": 5.0, "mul": 807}, {"min": 7.5, "max": 12.5}]
        assert list(nodes(value, "CreateHitArea"))[0][24] == (133 if level == 3 else 0)


def test_pf_clone_cyclic_child_reference_is_finite_and_private(env):
    child = "battle/action/skill/cyclic_child"
    value = root(cmd("CreateTargetAttack", -18, 0, 0, ["Specify", 30], child))
    validate_action_dsl(value)
    env.source.files["common", child + DSL_SUFFIX] = encode_tree(value)
    for path in paths():
        env.source.files["common", path + DSL_SUFFIX] = encode_tree(value)
    clone(env, CID, request(), apks=[])
    members = replay(env)[0]
    assert len(members) == 7
    for level in (1, 2, 3):
        generated = f"battle/action/power_flip/studio/my_pf$lv{level}" + DSL_SUFFIX
        target, = linked_programs(decode_tree(members["common", generated]))
        assert linked_programs(decode_tree(members["common", target])) == {target}
        assert target != child + DSL_SUFFIX


def test_pf_summary_unknown_formation_has_no_misleading_total():
    value = action(3)
    list(nodes(value, "CreateHitArea"))[0][12] = ["Line", 3, 10, False]
    validate_action_dsl(value)
    report = summary(value)
    assert report["hitCount"] == 1
    assert report["coefficients"][0]["terms"] == [{"min": 3, "max": 3}]
    assert report["markers"] == [133]
    assert report["nominalMultiplier"] is None


def test_pf_clone_bundled_donor_with_empty_cdn_table(env, tmp_path, cache):
    env.source.files["common", PF_TABLE] = table({})
    target = apk(tmp_path)
    spec = request(source="knight")
    preview = clone(env, CID, spec, preview=True, apks=[target], cache_dir=cache)
    assert preview["ok"] and preview["preview"]
    assert preview["sourceKind"] == "bundled"
    assert not env.store.root.exists()
    saved = clone(env, CID, spec, apks=[target], cache_dir=cache)
    assert saved["changeset"]["changes"][0]["params"]["reservations"] == {"power_flip_action": ["my_pf"]}
    members, _, _, assertions, _ = compile_draft(
        env.source, env.store, env.store.load(CID), apks=[target], bundle_cache_dir=cache)
    assert len(members) == 4
    assert list(unpack(members["common", PF_TABLE])) == ["my_pf"]
    assert assertions[0]["source"] == "knight"
    assert unpack(env.source.raw(PF_TABLE)) == {}


def test_pf_clone_next_id_skips_draft_reservation(env):
    first = next_id(env.source, "power_flip_action", drafts_root=env.store.root)
    assert first["id"] == "studio_pf_1"
    assert first["available"] and first["skipped"] == []
    assert not env.store.root.exists()
    clone(env, CID, request(first["id"]), apks=[])
    second = next_id(env.source, "power_flip_action", drafts_root=env.store.root)
    assert second["id"] == "studio_pf_2"
    assert second["available"]
    assert [item["id"] for item in second["skipped"]] == ["studio_pf_1"]
    assert second["skipped"][0]["owners"][0]["owner"] == CID
