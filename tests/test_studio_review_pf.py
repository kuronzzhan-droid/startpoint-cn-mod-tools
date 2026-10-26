"""PF catalogue/check/compiler must agree on occupancy and selectability."""
import json
from types import SimpleNamespace
import pytest

from test_studio_pf_clone import env, action, CID, request, with_effect  # noqa: F401
from test_studio_pf_catalog import apk, cache, paths, table, source  # noqa: F401
from test_studio_timeline import root, cmd
from wf.studio.deliver_media import encode_tree
from wf.studio.drafts import DraftError
from wf.studio.pf_actions import clone
from wf.studio.pf_catalog import PfCatalog, PF_TABLE, DSL_SUFFIX, STANDARD_TYPES
from wf.studio.pf_dsl import summary, transform
from wf.studio.ids import check_id, collect_occupancy
from wf.studio.pf_routes import PFActionsRoutes


def test_standard_keys_are_reserved_without_apk_and_all_drafts_are_checked(env, monkeypatch):
    monkeypatch.setattr("wf.studio.pf_catalog.resolve_apks", lambda *args: [])
    for key in STANDARD_TYPES:
        assert not check_id(env.source, "power_flip_action", key)["available"]
        with pytest.raises(DraftError, match="占用|内置"):
            clone(env, CID, request(key), apks=[])
    clone(env, CID, request(), apks=[])
    route = PFActionsRoutes(SimpleNamespace(source=env.source, ops=env))
    occupied = json.loads(route.check({"key": ["my_pf"]}).body)
    assert occupied["available"] is False and occupied["status"] == "occupied"
    unknown = json.loads(route.check({"key": ["unused_pf"]}).body)
    assert unknown["available"] is None and unknown["status"] == "unchecked"


def test_default_apks_are_used_by_build_resolution_and_generic_ids(tmp_path, cache, monkeypatch):
    from wf.studio.delivery_safety import resolve_apks
    selected = apk(tmp_path, key="private_bundled")
    monkeypatch.setattr("wf.caps.profiles.load_profiles", lambda: ("fixture", {}))
    monkeypatch.setattr("wf.studio.pf_catalog.load_profiles", lambda: ("fixture", {}))
    monkeypatch.setattr("wf.paths.profile_data", lambda: ({"client_apks": {"fixture": [str(selected)]}}, None))
    assert resolve_apks(None) == [selected.resolve()]
    occupancy = collect_occupancy(source(), pf_catalog=PfCatalog(source(), cache_dir=cache))
    assert not check_id(source(), "power_flip_action", "private_bundled", occupancy=occupancy)["available"]


def test_malformed_row_in_one_apk_does_not_hide_healthy_catalog(tmp_path, cache):
    a = apk(tmp_path, key="broken", row=["bad"], name="a.apk", programs=False)
    b = apk(tmp_path, key="healthy", name="b.apk")
    catalog = PfCatalog(source(), apks=[a, b], cache_dir=cache)
    items = {item["key"]: item for item in catalog.list()["items"]}
    assert items["broken"]["selectable"] is False and items["special"]["selectable"] is True


@pytest.mark.parametrize("child", [None, b"bad deflate", "ratio"])
def test_catalog_preflights_children_before_advertising_cloneable(env, child):
    child_path = "battle/action/skill/child"
    for path in paths():
        env.source.files["common", path + DSL_SUFFIX] = encode_tree(root(
            cmd("CreateTargetAttack", -18, 0, 0, ["Specify", 30], child_path)))
    if child is not None:
        raw = encode_tree(root(cmd("CreateRatioAttack", -18, 2, [{"min": .1, "max": .1}]))) if child == "ratio" else child
        env.source.files["common", child_path + DSL_SUFFIX] = raw
    catalog = PfCatalog(env.source, apks=[])
    assert not catalog.detail("special")["selectable"]
    assert not next(i for i in catalog.list()["items"] if i["key"] == "special")["selectable"]
    with pytest.raises(DraftError):
        clone(env, CID, request(), apks=[])


def test_child_summary_and_dynamic_control_flow_never_claim_a_total(env):
    child_path = "battle/action/skill/child"
    for path in paths():
        env.source.files["common", path + DSL_SUFFIX] = encode_tree(root(
            cmd("CreateTargetAttack", -18, 0, 0, ["Specify", 30], child_path)))
    env.source.files["common", child_path + DSL_SUFFIX] = encode_tree(action(3))
    detail = PfCatalog(env.source, apks=[]).detail("special")
    first = detail["levels"][0]
    assert first["markers"] == [133]
    assert first["hitCount"] == 1 and first["nominalMultiplier"] is None
    value = action(1)
    # Unknown commands/callback semantics may have a valid signature; summary is conservative.
    value[11][1].append(cmd("RemoveEventFromOwner", "event"))
    assert summary(value)["nominalMultiplier"] is None
    value = action(1)
    value[11] = ["Block", [["Event", ["CollisionOfBallAndEnemy", -18, "event", False, 9, value[11]]]]]
    assert summary(value)["nominalMultiplier"] is None


def test_effect_mapping_only_accepts_exact_referenced_families(env):
    old, new = "battle/effect/powerflip/demo", "battle/effect/skill_unique/private/fx"
    with_effect(env, old + "/burst")
    from wf.studio.deliver_media import tree
    value = tree(env.source.raw(paths()[0] + DSL_SUFFIX))
    for candidate in ("battle/effect", old + "/burst"):
        matched = set()
        changed = transform(value, "暗", 1, {candidate: new}, matched)
        assert not matched and changed == transform(value, "暗", 1)
    matched = set()
    transform(value, "暗", 1, {old: new}, matched)
    assert matched == {old}


from test_studio_character_clone import env as clone_env  # noqa: E402,F401


def test_pf_uses_private_effects_staged_only_in_character_clone(clone_env):
    from test_studio_character_clone import NEW, request as character_request
    from test_studio_pf_dependencies import family
    from test_studio_timeline import show
    from wf.studio.character_clone import clone as clone_character
    from wf.studio.deliver_bridge import compile_draft
    from wf.studio.drafts import sha256
    source, store, ops, server = clone_env
    old, new = "battle/effect/powerflip/demo", "battle/effect/skill_unique/clone_demo/private"
    source.view.files["common", PF_TABLE] = table({"special": paths()})
    for level, path in enumerate(paths(), 1):
        value = action(level)
        value[11][1].append(show("fx", old + "/burst", -18, ["SpecifyEffectLifetimeDirectly", 30]))
        source.view.files["common", path + DSL_SUFFIX] = encode_tree(value)
    source.view.files.update(family(old + "/burst"))
    clone_character(ops, character_request(), server_dir=server)
    draft = store.load(NEW)
    staged = family(new + "/burst")
    for (root_name, logical), raw in staged.items():
        relative = f"files/clone/{root_name}/{logical}"
        store.write_file(NEW, relative, raw)
        draft["changes"][0]["files"].append({"root": root_name, "logical": logical,
            "draft": relative, "sha256": sha256(raw), "size": len(raw), "encoding": "stored",
            "approximate": False, "base": {"sha256": None, "layer": "synthetic clone"}})
    store.restore(NEW, draft)
    saved = clone(ops, NEW, request(effects={old: new}), apks=[])
    assert all(level["effectFamilies"] == [new] for level in saved["levels"])
    members = compile_draft(source, store, store.load(NEW), server_dir=server, apks=[])[0]
    assert all(members[key] == raw for key, raw in staged.items())
    assert all(source.raw(logical) is None for _, logical in staged)
