"""Synthetic end-to-end clone reservations, text recovery and batch mirrors."""
import json
from copy import deepcopy
import pytest
import wf_quest_lib as codec
from wf.balance.rows import split_leaf
from test_studio_character_clone import env, OLD, NEW, View, ordered
from test_m1_balance import valid_row
from wf.studio.clone_tables import T, leaf
from wf.studio.source import StudioSource
from wf.studio.operations import DraftOps
from wf.studio.variant_clone import run_variant
from wf.studio.character_clone import clone_members, compile_clone
from wf.studio.ability import AbilityEditor
from wf.studio.batch import BatchEditor
from wf.studio.clone_ids import linked_check, next_linked
from wf.studio.ids import check_id
from wf.studio.drafts import DraftError
from wf.studio.deliver_media import encode_tree

CUSTOM = "master/string/custom_ability_string.orderedmap"
CODE = f"variant_{OLD}_{NEW}"
BODY = {"from": OLD, "rule": "zone"}
TARGET = {"to": NEW, "zone": "direct"}


def changed_source(env, changes):
    files = {**env[0].view.files, **{("common", k): v for k, v in changes.items()}}
    source = StudioSource(View(files))
    return source, DraftOps(source, store=env[1])


def mirrors(server):
    for path in list(server.rglob("*.json")):
        dest = server / "assets" / path.relative_to(server)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())
    (server / "assets/cdndata/character_text_rank_p5b.json").write_text("{}", encoding="utf-8")


def reserve(store, table, key):
    directory = store.directory("888888")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "changeset.json").write_text(json.dumps({"characterId": "888888", "code": "other", "updatedAt": "test", "savedAt": None,
        "changes": [{"kind": "ability_edit", "params": {"requests": [{"operations": [
            {"op": "attach_key", "table": table, "key": key, "rows": []}]}]}}]}), encoding="utf-8")


@pytest.mark.parametrize("table,key", [("ability", NEW + "1"), ("leader_ability", NEW), ("action_skill", CODE)])
def test_other_draft_key_conflict_rejected_before_write(env, table, key):
    reserve(env[1], table, key)
    with pytest.raises(DraftError, match="占用|预留"):
        run_variant(env[2], BODY, TARGET, preview=False)
    assert not env[1].directory(NEW).exists()


def test_linked_ids_skip_mana_orphan_and_ability_and_honor_start(env):
    source, store, ops, _ = env
    reserve(store, "ability", NEW + "1")
    orphan = str(int(NEW) + 1)
    store.directory(orphan).mkdir()
    assert not linked_check(ops, NEW)["available"]
    assert not linked_check(ops, orphan)["available"]
    assert next_linked(ops, NEW, donor=OLD)["id"] == str(int(NEW) + 2)
    source, ops = changed_source(env, {T.MANA_BOARD: ordered({NEW: ordered({"1": leaf([["1"]])})})})
    assert any("mana_node" in r for r in linked_check(ops, NEW)["reasons"])


def test_http_server_dir_reaches_batch_and_rejects_mirror_collision(env):
    from wf.studio.server import StudioApp
    app = StudioApp(env[0], drafts=env[1], server_dir=env[3])
    assert app.batch.service.server_dir == env[3]
    path = env[3] / "character.json"
    path.write_text(json.dumps({NEW: {}}), encoding="utf-8")
    result = app.batch.service.variants_preview({**BODY, "targets": [TARGET]})
    assert result["rows"][0]["status"] == "需人工" and "服务端" in result["rows"][0]["reason"]
    assert env[1].load(NEW) is None


def test_linked_id_http_returns_conflicts(env):
    from wf.studio.server import StudioApp
    reserve(env[1], "leader_ability", NEW)
    app = StudioApp(env[0], drafts=env[1])
    response = app.dispatch("GET", "/api/studio/characters/variants/ids/check", {"id": [NEW], "from": [OLD]})
    assert response.status == 200 and not json.loads(response.body)["available"]
    response = app.dispatch("GET", "/api/studio/characters/variants/ids/next", {"near": [NEW], "from": [OLD]})
    assert response.status == 200 and json.loads(response.body)["id"] == str(int(NEW) + 1)


def test_first_row_string_identity_changes_and_reserves_override(env):
    first, second = valid_row("donor_override"), valid_row("donor_override")
    first[47], second[47] = "32", "34"
    source, ops = changed_source(env, {T.LEADER: ordered({"3": leaf([r[:1] + r[3:] for r in [first, second]])}),
                                     CUSTOM: ordered({"desc_override_donor_override": leaf([["旧技能伤害文案"]])})})
    result = run_variant(ops, BODY, TARGET, preview=False)
    rows = split_leaf(codec.parse_node(clone_members(source, env[1], env[1].load(NEW))["common", T.LEADER])[NEW], "leader_ability")
    sid = rows[0][0]
    assert sid == rows[1][0] and sid != "donor_override" and rows[0][45] == "32" and rows[1][45] == "33"
    assert any(m.get("textKey") == "desc_override_" + sid for m in result["variant"]["manual"])
    for key in [sid, "desc_override_" + sid]:
        assert not check_id(source, "string_id", key, drafts_root=env[1].root)["available"]


@pytest.mark.parametrize("prefix", ["", "desc_override_"])
def test_generated_string_collision_rejected(env, prefix):
    sid = prefix + CODE + "_" + NEW + "1"
    source, ops = changed_source(env, {CUSTOM: ordered({sid: leaf([["existing"]])})})
    with pytest.raises(DraftError, match="文本键已占用"):
        run_variant(ops, BODY, TARGET, preview=False)
    assert env[1].load(NEW) is None


def test_manual_first_row_still_unisonable_and_status_honest(env):
    row = valid_row("manual")
    row[47], row[68] = "721", "21"
    other = valid_row("next")
    document = {str(100+i): leaf([valid_row()]) for i in range(6)}
    document["100"] = leaf([row, other])
    source, ops = changed_source(env, {T.ABILITY: ordered(document)})
    svc = BatchEditor(ops, server_dir=env[3])
    result = svc.variants_preview({**BODY, "targets": [TARGET]})
    assert result["rows"][0]["status"] == "含需人工（仅存草稿，阻断交付）"
    svc.variants_apply({**BODY, "targets": [TARGET], "selected": [1], "review": result["review"]})
    rows = split_leaf(codec.parse_node(clone_members(source, env[1], env[1].load(NEW))["common", T.ABILITY])[NEW + "1"], "ability")
    assert rows[0][1] == rows[1][1] == "true" and rows[0][47] == "721"
    with pytest.raises(DraftError, match="需人工"):
        compile_clone(source, env[1], env[1].load(NEW), server_dir=env[3])


def test_clone_text_sync_unblocks_compile_and_undo_reblocks(env):
    mirrors(env[3])
    before = {p: p.read_bytes() for p in env[3].rglob("*.json")}
    source, ops = changed_source(env, {
        "battle/action/skill/mother.action.dsl.amf3.deflate": encode_tree(["ActionDsl", ["ACSkillDamage", 10, 20, 1]]),
        CUSTOM: ordered({"desc_override_mother_0": leaf([["母本覆盖技能伤害"]])})})
    result = run_variant(ops, BODY, TARGET, preview=False, server_dir=env[3])
    pending = result["variant"]["manual"]
    editor = AbilityEditor(source, store=env[1], server_dir=env[3], cache=False)
    panel = editor.text_panel(NEW)
    assert panel
    req = {"text": {"action_skill": {"1": {"c1": {"old": "说明", "new": "赋予全队直接攻击伤害提升"}}},
                    "desc_override": {m["textKey"]: {"old": None, "new": "赋予自身攻击力提升"} for m in pending if "textKey" in m}}}
    with pytest.raises(DraftError, match="需人工"):
        compile_clone(source, env[1], env[1].load(NEW), server_dir=env[3])
    updated = editor.apply(NEW, req)
    change = next(c for c in updated["changeset"]["changes"] if c["kind"] == "character_clone")
    assert not change["params"]["variant"]["manual"]
    assert not any(c["code"] == "variant.incomplete" for c in change["checks"])
    members, servers, _, _, _ = compile_clone(source, env[1], env[1].load(NEW), server_dir=env[3])
    assert split_leaf(codec.parse_node(members["common", T.ACTION])[CODE]["1"], "action_skill")[0][1] == "赋予全队直接攻击伤害提升"
    assert json.loads(servers["assets/cdndata/character_text.json"])[NEW][0][5] == "赋予全队直接攻击伤害提升"
    draft = deepcopy(env[1].load(NEW))
    draft["changes"] = [c for c in draft["changes"] if c["kind"] != "ability_edit"]
    env[1].restore(NEW, draft)
    with pytest.raises(DraftError, match="需人工"):
        compile_clone(source, env[1], draft, server_dir=env[3])
    assert before == {p: p.read_bytes() for p in before}


def test_wfx_identity_protects_the_whole_multiline_key(env):
    first, second = valid_row("wfx_mechanism"), valid_row("ordinary")
    first[47], second[47] = "32", "34"
    document = {str(100+i): leaf([valid_row()]) for i in range(6)}
    document["100"] = leaf([first, second])
    source, ops = changed_source(env, {T.ABILITY: ordered(document)})
    run_variant(ops, BODY, TARGET, preview=False)
    rows = split_leaf(codec.parse_node(clone_members(source, env[1], env[1].load(NEW))["common", T.ABILITY])[NEW + "1"], "ability")
    assert rows == [first, second]


def test_draft_program_path_collision_rejected(env):
    reserve(env[1], "ability", "other")
    path = env[1].directory("888888") / "changeset.json"
    draft = json.loads(path.read_text("utf-8"))
    draft["changes"][0]["files"] = [{"logical": f"battle/action/skill/{CODE}_variant_1.action.dsl.amf3.deflate"}]
    path.write_text(json.dumps(draft), encoding="utf-8")
    source, ops = changed_source(env, {
        "battle/action/skill/mother.action.dsl.amf3.deflate": encode_tree(["ActionDsl", ["ACSkillDamage", 1, 2, 3]])})
    with pytest.raises(DraftError, match="程序路径已经存在"):
        run_variant(ops, BODY, TARGET, preview=False)
    assert env[1].load(NEW) is None


def test_batch_replays_existing_text_draft_with_server_dir(env):
    from test_studio_batch import balance_body
    mirrors(env[3])
    source, ops = changed_source(env, {CUSTOM: ordered({"filler": leaf([["unused"]])})})
    primary = env[3] / "assets/cdndata/character_text.json"
    primary.write_text(json.dumps({OLD: source.table("text")[OLD]}), encoding="utf-8")
    editor = AbilityEditor(source, store=env[1], server_dir=env[3], cache=False)
    editor.apply(OLD, {"text": {"action_skill": {"1": {"c1": {"old": "说明", "new": "对敌人造成伤害"}}}}})
    svc = BatchEditor(ops, server_dir=env[3])
    body = balance_body()
    result = svc.balance_preview(body)
    assert result["rows"][0]["status"] == "可写草稿"
    svc.balance_apply({**body, "selected": [1], "review": result["review"]})
    assert len(env[1].load(OLD)["changes"][0]["params"]["requests"]) == 2
