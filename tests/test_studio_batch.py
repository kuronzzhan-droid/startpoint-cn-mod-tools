"""D2 contracts use synthetic orderedmaps and temporary draft roots only."""
from copy import deepcopy
import json

import pytest

from test_studio_character_clone import env, OLD, NEW
from test_m1_balance import valid_row
from wf.studio.batch import BatchEditor
from wf.studio.balance_import import parse_table, preview_rows
from wf.studio.ability import AbilityEditor
from wf.studio.ability_engine import describe
from wf.studio.clone_tables import T, leaf
from wf.studio.character_clone import clone_members, compile_clone
from wf.studio.source import StudioSource
from wf.studio.operations import DraftOps
from wf.studio.drafts import DraftError
from wf.studio.variant_rules import transform_row, change_element_row, transform_skill
from wf.studio.variant_clone import run_variant
from wf.studio.deliver_media import encode_tree
import wf_quest_lib as codec

MAPPING = {"character": "对象", "entry": "项目", "row": "行", "column": "字段", "before": "旧", "after": "新"}


def balance_body(after="20000", who=OLD):
    return {"text": f"对象\t项目\t行\t字段\t旧\t新\n{who}\t能力1\t1\tc51\t10000\t{after}\n", "mapping": MAPPING}


def service(env, tmp_path):
    return BatchEditor(env[2], tmp_path / "mapping.json", server_dir=env[3])


def test_parse_quotes_bom_and_bad_headers():
    assert parse_table('\ufeff对象,说明\r\na,"两行\n有,逗号"')[1] == [["a", "两行\n有,逗号"]]
    with pytest.raises(DraftError, match="重名"):
        parse_table("a,a\n1,2")


def test_balance_default_readonly_then_explicit_selected_apply(env, tmp_path):
    svc = service(env, tmp_path)
    body = balance_body()
    result = svc.balance_preview(body)
    assert result["rows"][0]["status"] == "可写草稿"
    assert not result["rows"][0]["selected"] and env[1].load(OLD) is None
    assert result["rows"][0]["changes"][0]["beforeDescription"] != result["rows"][0]["changes"][0]["afterDescription"]
    with pytest.raises(DraftError, match="勾选"):
        svc.balance_apply({**body, "review": result["review"]})
    output = svc.balance_apply({**body, "review": result["review"], "selected": [1]})
    assert len(output["written"]) == 1 and env[1].load(OLD)
    with pytest.raises(DraftError, match="预览"):
        svc.balance_apply({**body, "review": result["review"], "selected": [1]})


@pytest.mark.parametrize("who,after", [("不认识", "20000"), (OLD, "适当提升"), (OLD, "10000")])
def test_unconvertible_is_manual(env, tmp_path, who, after):
    assert service(env, tmp_path).balance_preview(balance_body(after, who))["rows"][0]["status"] == "需人工"


def test_mapping_persistence_and_duplicate_targets(env, tmp_path):
    svc = service(env, tmp_path)
    svc.mapping(MAPPING)
    assert BatchEditor(env[2], svc.mapping_path).mapping() == MAPPING
    body = balance_body()
    body["text"] += body["text"].splitlines()[1] + "\n"
    result = svc.balance_preview(body)
    assert all(r["status"] == "需人工" for r in result["rows"])


def test_balance_exact_chinese_name(env, tmp_path):
    preview = service(env, tmp_path).balance_preview(balance_body(who="母本"))
    assert preview["rows"][0]["status"] == "可写草稿"
    assert preview["rows"][0]["characterId"] == OLD


def test_balance_rollback_preserves_prior_work(env, tmp_path, monkeypatch):
    svc = service(env, tmp_path)
    body = balance_body("15000")
    first = svc.balance_preview(body)
    svc.balance_apply({**body, "review": first["review"], "selected": [1]})
    saved = deepcopy(env[1].load(OLD))
    body = balance_body().copy()
    body["text"] = body["text"].replace("10000", "15000")
    preview = svc.balance_preview(body)
    original = AbilityEditor.apply
    def fail_after_write(self, cid, request):
        original(self, cid, request)
        raise OSError("synthetic disk failure")
    monkeypatch.setattr(AbilityEditor, "apply", fail_after_write)
    with pytest.raises(OSError, match="synthetic"):
        svc.balance_apply({**body, "review": preview["review"], "selected": [1]})
    assert env[1].load(OLD) == saved


def test_exact_description_replacement_requires_unique_render(env):
    editor = AbilityEditor(env[0], store=env[1])
    entry = next(e for e in editor.read(OLD)["entries"] if e["slot"] == 1)
    before = entry["rows"][0]
    after = list(before)
    after[51] = "20000"
    body = f"人\t项\t前\t后\n{OLD}\t能力1\t{describe(before, 'ability')}\t{describe(after, 'ability')}"
    result = preview_rows(editor, body, {"character": "人", "entry": "项", "before": "前", "after": "后"},
                          [{"id": OLD, "name": "母本"}])
    assert result["rows"][0]["status"] == "可写草稿"


@pytest.mark.parametrize("zone,kind", [("skill", "34"), ("power_flip", "55"), ("direct", "33"), ("ability", "388"), ("all", "723")])
@pytest.mark.parametrize("table", ["ability", "leader_ability"])
def test_zone_pure_numeric_invariance_party_and_atk(table, zone, kind):
    row = valid_row()
    row[47], row[49] = "34", "White"
    if table == "leader_ability":
        row = row[:1] + row[3:]
    original = list(row)
    out, manual = transform_row(row, table, zone)
    start = 47 if table == "ability" else 45
    assert not manual and row == original
    assert out[start] == kind and out[start + 1:start + 3] == ["5", "White"]
    assert out[start + 4:start + 6] == row[start + 4:start + 6]
    atk = list(row)
    atk[start] = "32"
    assert transform_row(atk, table, zone) == (atk, [])


def test_unique_condition_never_dropped():
    row = valid_row()
    row[47], row[68] = "721", "21"
    out, manual = transform_row(row, "ability", "direct")
    assert out == row and manual
    row[47] = "565"
    assert transform_row(row, "ability", "all")[0] == row


def test_resistance_element_mapping_and_skill_purity():
    import wf_describe
    options = wf_describe.enum_options()["instant_content"]
    kinds = {v["en"]: k for k, v in options.items()}
    name = next(n for n in kinds if "ResistanceWhite" in n)
    row = valid_row()
    row[47], row[49], row[73] = kinds[name], "White", "5"
    out, manual = change_element_row(row, "ability", 4, 5)
    assert not manual and out[47] == kinds[name.replace("White", "Black")]
    assert out[49] == "Black" and out[73] == "5" and row[49] == "White"
    tree = ["ActionDsl", ["ACSkillDamage", [10], [20], [1]], ["ACAttackPoint", 1, 2, 3]]
    original = deepcopy(tree)
    after, manual = transform_skill(tree, "direct")
    assert not manual and after[1] == ["ACDirectDamage", [10], [20], [1]]
    assert after[2] == tree[2] and tree == original


def test_variants_preview_no_write_and_clone_draft(env, tmp_path):
    svc = service(env, tmp_path)
    body = {"from": OLD, "rule": "zone", "targets": [{"to": NEW, "zone": "direct"}]}
    result = svc.variants_preview(body)
    assert result["rows"][0]["status"] == "可写草稿", result
    assert env[1].load(NEW) is None
    written = svc.variants_apply({**body, "review": result["review"], "selected": [1]})
    assert written["written"][0]["characterId"] == NEW
    assert written["written"][0]["changeset"]["changes"][0]["params"]["spec"]["name"] == "母本・乘区6直接攻击"
    members = clone_members(env[0], env[1], env[1].load(NEW))
    assert codec.parse_node(members["common", T.CHAR])[OLD] == codec.parse_node(env[0].raw(T.CHAR))[OLD]


def test_cross_element_and_duplicate_ids_stay_blocked(env, tmp_path):
    svc = service(env, tmp_path)
    body = {"from": OLD, "rule": "element", "targets": [{"to": NEW, "element": 1}]}
    assert "跨属性" in svc.variants_preview(body)["rows"][0]["reason"]
    body["targets"] *= 2
    with pytest.raises(DraftError, match="重复"):
        svc.variants_preview(body)


def test_batch_variant_failure_rolls_back_created_drafts(env, tmp_path, monkeypatch):
    import wf.studio.batch as module
    svc = service(env, tmp_path)
    body = {"from": OLD, "rule": "zone", "targets": [{"to": NEW, "zone": "direct"}, {"to": str(int(NEW)+1), "zone": "ability"}]}
    preview = svc.variants_preview(body)
    original = module.run_variant
    def failing(ops, body, target, *, preview=True, server_dir=None):
        if not preview and target["to"] != NEW:
            raise OSError("synthetic second draft failure")
        return original(ops, body, target, preview=preview, server_dir=server_dir)
    monkeypatch.setattr(module, "run_variant", failing)
    with pytest.raises(OSError, match="second"):
        svc.variants_apply({**body, "review": preview["review"], "selected": [1, 2]})
    assert not env[1].directory(NEW).exists() and env[1].load(str(int(NEW)+1)) is None


def test_first_row_unison_and_during_aggregation_are_explicit():
    from wf.studio.variant_rules import remove_main_restriction
    row = valid_row()
    row[47] = "32"
    out = remove_main_restriction(row, "ability")
    assert out[1] == "true" and out[47:] == row[47:]
    row[5], row[97], row[98], row[102], row[104], row[109] = "1", "194", "5", "1", "20", "411"
    row[100:102] = ["100000", "100000"]
    row[110] = "0"
    out, manual = transform_row(row, "ability", "direct")
    assert not manual and out[98] == "9"
    row[104] = "21"
    assert transform_row(row, "ability", "direct")[0] == row


def test_manual_variant_persists_blocker_and_is_not_deliverable(env, tmp_path):
    source, store, ops, server = env
    logical = "battle/action/skill/mother.action.dsl.amf3.deflate"
    files = dict(source.view.files)
    files["common", logical] = encode_tree(["ActionDsl", ["ACSkillDamage", 10, 20, 1]])
    source = StudioSource(type(source.view)(files))
    ops = DraftOps(source, store=store)
    result = run_variant(ops, {"from": OLD, "rule": "zone"}, {"to": NEW, "zone": "direct"}, preview=False)
    assert result["variant"]["manual"] and not result["buildable"]
    with pytest.raises(DraftError, match="需人工"):
        compile_clone(source, store, store.load(NEW), server_dir=server)


def test_cli_is_preview_by_default():
    from wf.studio.draft import build_parser
    args = build_parser().parse_args(["balance-import", "--file", "sample.tsv"])
    assert args.select == [] and args.review is None


def test_routes_have_review_guards(env):
    from wf.studio.server import StudioApp
    app = StudioApp(env[0], drafts=env[1])
    response = app.dispatch("POST", "/api/studio/characters/balance/preview", {}, balance_body())
    assert response.status == 200
    body = json.loads(response.body)
    assert body["review"] and body["rows"]
    assert app.dispatch("POST", "/api/studio/characters/balance/apply", {}, balance_body()).status == 400
