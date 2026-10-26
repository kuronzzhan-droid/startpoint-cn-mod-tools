"""Synthetic summon authoring contracts; no official media or local game store."""
import copy
import math
from pathlib import Path
import zlib

import pytest
import wf_mod_tool as core
from wf.deliver.changeset import member_name
from wf.studio.clone_tables import leaf, rows
from wf.studio.drafts import DraftError, DraftStore, schema_errors
from wf.studio.ids import check_id
from wf.studio.source import StudioSource
from test_m1_balance import valid_row

CID, MOTHER, OLD_BALL, NEW_BALL = "199010", "111007", "711", "1990101"
CHARACTER = "master/character/character.orderedmap"
TEXT = "master/character/character_text.orderedmap"
STATUS = "master/character/character_status.orderedmap"
ACTION = "master/skill/action_skill.orderedmap"
BALL = "master/battle/multiball/multiball.orderedmap"
LEVEL = "master/battle/multiball/multiball_level.orderedmap"
HP = "master/battle/multiball/multiball_hp_curve.orderedmap"
ATTACK = "master/battle/multiball/multiball_atk_curve.orderedmap"
STRINGS = "master/string/custom_ability_string.orderedmap"
PF = "master/skill/power_flip_action.orderedmap"


def ordered(entries):
    return core.build_orderedmap_raw_rows(core.OrderedMap(
        "fixture", list(entries), list(entries.values()), Path("fixture")))


def flat(data, key):
    return core.read_csv_lines(zlib.decompress(rows(data)[key]).decode("utf-8"))


def curve(data, key):
    return {int(level): float(flat(rows(data)[key], level)[0][0])
            for level in rows(rows(data)[key])}


def panel_values(tables, identity):
    level = flat(tables[LEVEL], identity)[0]
    hp, attack = curve(tables[HP], level[0]), curve(tables[ATTACK], level[3])
    return ({point: math.floor(value * float(level[1]) * float(level[2])) for point, value in hp.items()},
            {point: math.floor(value * float(level[4]) * float(level[5])) for point, value in attack.items()})


class View:
    tip, zips, extra_zips = "1.4.233", [], []
    store = Path("/__synthetic_summon_store__")

    def __init__(self, files):
        self.files = files
        self.index = {member_name(root, logical): "fixture.zip" for root, logical in files}

    def read_member(self, member):
        for key, raw in self.files.items():
            if member_name(*key) == member:
                return raw, "fixture.zip"
        raise FileNotFoundError(member)

    def read_raw(self, logical):
        try:
            return self.files["common", logical], "fixture.zip"
        except KeyError as error:
            raise FileNotFoundError(logical) from error


def fixture_files():
    mother = [""] * 37
    mother[:9] = ["fixture_mother", "mother_name", "4", "3", "Human", "fixture_tag",
                  "2", "Female", "mother_skill"]
    owner = mother.copy()
    owner[0], owner[27] = "fixture_owner", CID
    mother[27] = MOTHER
    native = ["native_ball_name", "fixture_mother", "4", "3", "Human", "native_tag",
              "2", "Female", "true", "battle/action/skill/mother_high", "母本技能", "480", "0",
              "", "", "", "", "", "", "", "(None)", "(None)", "(None)", "(None)",
              "1", "0", "false", "false"]
    skill_low = ["母本技能初阶", "说明", "", "", "400", "400", "", "battle/action/skill/mother_low"] + ["0"] * 8
    skill_high = ["母本技能", "说明", "", "", "480", "480", "", "battle/action/skill/mother_high"] + ["0"] * 8
    alternate = ["替代技能", "说明", "", "", "600", "600", "", "battle/action/skill/alternate"] + ["0"] * 8
    tables = {
        CHARACTER: ordered({MOTHER: leaf([mother]), CID: leaf([owner])}),
        TEXT: ordered({MOTHER: leaf([["合成母本"]]), CID: leaf([["合成作者"]])}),
        STATUS: ordered({MOTHER: ordered({"1": leaf([["100", "20"]]),
                                          "50": leaf([["600", "150"]]), "100": leaf([["1200", "300"]])})}),
        ACTION: ordered({"mother_skill": ordered({"1": leaf([skill_low]), "3": leaf([skill_high])}),
                         "alternate_skill": ordered({"1": leaf([alternate])})}),
        BALL: ordered({OLD_BALL: leaf([native])}),
        LEVEL: ordered({OLD_BALL: leaf([["native_hp", "100", "2", "native_atk", "20", "3"]])}),
        HP: ordered({"native_hp": ordered({"1": leaf([["1"]]), "100": leaf([["4"]])})}),
        ATTACK: ordered({"native_atk": ordered({"1": leaf([["1"]]), "100": leaf([["5"]])})}),
        STRINGS: ordered({"native_ball_name": leaf([["合成原生球"]]), "keep_text": leaf([["保持"]])}),
        PF: ordered({"fixture_pf": leaf([["fixture_pf_level1", "fixture_pf_level2", "fixture_pf_level3"]])}),
        "master/ability/ability.orderedmap": ordered({"1": leaf([valid_row("fixture_ability")])}),
        "master/ability/leader_ability.orderedmap": ordered({"1": leaf([valid_row()[:1] + valid_row()[3:]])}),
    }
    from test_studio_skill_template_core import root
    from wf.studio.deliver_media import encode_tree
    for program in ("mother_low", "mother_high", "alternate"):
        tables[f"battle/action/skill/{program}.action.dsl.amf3.deflate"] = encode_tree(root())
    for program in ("a", "b", "c"):
        tables[f"battle/action/{program}.action.dsl.amf3.deflate"] = encode_tree(root())
    tables["character/fixture_override/pixelart/sprite_sheet.png"] = b"synthetic"
    tables["character/fixture_override/ui/skill_cutin_0.png"] = b"synthetic"
    tables["character/fixture_mother/ui/skill_cutin_0.png"] = b"synthetic"
    return {("common", logical): raw for logical, raw in tables.items()}


@pytest.fixture
def summon_env(tmp_path):
    from wf.studio.summon import SummonEditor
    source = StudioSource(View(fixture_files()))
    store = DraftStore(tmp_path / "drafts")
    return source, store, SummonEditor(source, store=store)


def request(**kwargs):
    return {"template": {"kind": "character", "id": MOTHER}, "id": NEW_BALL, **kwargs}


def compiled(env):
    from wf.studio.summon import compile_summons
    source, store, _ = env
    return compile_summons(source, store, store.load(CID))["client"]


def test_preview_is_read_only_and_character_defaults_are_native_rows(summon_env):
    source, store, editor = summon_env
    before = copy.deepcopy(source.view.files)
    preview = editor.apply(CID, request(), preview=True)
    assert preview["ok"] and preview["preview"]
    assert preview["multiballId"] == NEW_BALL and preview["characterId"] == CID
    assert not store.root.exists() and source.view.files == before
    editor.apply(CID, request())
    tables = compiled(summon_env)
    ball = flat(tables[BALL], NEW_BALL)[0]
    assert len(ball) == 28 and ball[1] == "fixture_mother"
    assert ball[3] == "3" and ball[6] == "2" and ball[8] in {"true", "false"}
    assert ball[9] == "battle/action/skill/mother_high" and ball[10] == "母本技能"
    assert ball[11] == "480"
    level = flat(tables[LEVEL], NEW_BALL)[0]
    assert len(level) == 6
    hp, attack = panel_values(tables, NEW_BALL)
    assert len(hp) == len(attack) == 100
    assert {point: hp[point] for point in (1, 2, 50, 100)} == {1: 100, 2: 111, 50: 600, 100: 1200}
    assert {point: attack[point] for point in (1, 2, 50, 100)} == {1: 20, 2: 23, 50: 150, 100: 300}
    assert preview["skillTemplate"]["lifetimeFrames"] == 2147483647
    assert preview["skillTemplate"]["multiballId"] == NEW_BALL
    assert preview["skillTemplate"]["inserted"] is False
    assert source.view.files == before


def test_saved_draft_reserves_id_and_revert_releases_it(summon_env):
    source, store, editor = summon_env
    saved = editor.apply(CID, request())
    draft = store.load(CID)
    assert not schema_errors(draft)
    change = draft["changes"][0]
    assert change["kind"] == "summon_clone"
    assert change["params"]["reservations"]["multiball"] == [NEW_BALL]
    assert not check_id(source, "multiball", NEW_BALL, drafts_root=store.root)["available"]
    assert editor.read(CID)["items"][0]["multiballId"] == NEW_BALL
    assert saved["change"]["id"] == change["id"]
    store.revert(CID, change["id"])
    assert check_id(source, "multiball", NEW_BALL, drafts_root=store.root)["available"]


def test_multiball_source_preserves_unknown_columns_and_exact_curve_rows(summon_env):
    source, _, editor = summon_env
    editor.apply(CID, request(template={"kind": "multiball", "id": OLD_BALL}))
    tables = compiled(summon_env)
    old = flat(source.raw(BALL), OLD_BALL)[0]
    new = flat(tables[BALL], NEW_BALL)[0]
    assert new[1:] == old[1:]
    assert flat(tables[LEVEL], NEW_BALL) == flat(source.raw(LEVEL), OLD_BALL)
    assert HP not in tables and ATTACK not in tables
    assert flat(tables[STRINGS], new[0]) == [["合成原生球"]]


def test_multiball_scaling_preserves_curves_and_scales_native_corrections(summon_env):
    source, _, editor = summon_env
    editor.apply(CID, request(template={"kind": "multiball", "id": OLD_BALL},
                              panel={"mode": "scaled", "hp_scale": 2, "attack_scale": 0.5}))
    tables = compiled(summon_env)
    assert HP not in tables and ATTACK not in tables
    level = flat(tables[LEVEL], NEW_BALL)[0]
    assert level == ["native_hp", "100", "4", "native_atk", "20", "1.5"]
    tables.update({HP: source.raw(HP), ATTACK: source.raw(ATTACK)})
    assert panel_values(tables, NEW_BALL) == ({1: 400, 100: 1600}, {1: 30, 100: 150})


@pytest.mark.parametrize("panel,hp,attack", [
    ({"mode": "scaled", "hp_scale": 2, "attack_scale": 0.5},
     {1: 200, 50: 1200, 100: 2400}, {1: 10, 50: 75, 100: 150}),
    ({"mode": "manual", "levels": [{"level": 1, "hp": 500, "attack": 0},
                                    {"level": 100, "hp": 1000, "attack": 100}]},
     {1: 500, 100: 1000}, {1: 0, 100: 100}),
])
def test_panel_modes_produce_expected_independent_curves(summon_env, panel, hp, attack):
    _, _, editor = summon_env
    editor.apply(CID, request(panel=panel))
    tables = compiled(summon_env)
    actual_hp, actual_attack = panel_values(tables, NEW_BALL)
    assert {level: actual_hp[level] for level in hp} == hp
    assert {level: actual_attack[level] for level in attack} == attack


def test_extensions_skill_selection_and_full_table_retention(summon_env):
    source, _, editor = summon_env
    saved = editor.apply(CID, request(
        image_prefix="fixture_override", element=5, pf_type=4, assist=True,
        skill={"mode": "specified", "key": "alternate_skill", "level": "1"},
        lifetime={"seconds": 2.5}, extensions={"flip_pf": {"enabled": True, "min_interval_frames": 12},
                                              "ball_pf_action": "fixture_pf"}))
    tables = compiled(summon_env)
    ball = flat(tables[BALL], NEW_BALL)[0]
    assert (ball[1], ball[3], ball[6], ball[8], ball[9], ball[11]) == (
        "fixture_override", "5", "4", "true", "battle/action/skill/alternate", "600")
    assert flat(tables[STRINGS], "wfx_summon_flip_pf_" + NEW_BALL) == [["1:12"]]
    assert flat(tables[STRINGS], "wfx_ball_pf_action_" + NEW_BALL) == [["fixture_pf"]]
    assert {"client.summon.flip_pf@1", "client.ball.pf_action@1", "client.summon.cutin_preload@1"} <= set(saved["requires"])
    assert saved["skillTemplate"]["lifetimeFrames"] == 150
    for logical, raw in tables.items():
        for key, old in rows(source.raw(logical)).items():
            assert rows(raw)[key] == old
    assert len(ball) == 28  # Lifetime belongs to summon DSL parameters, not a guessed table column.


@pytest.mark.parametrize("overrides", [
    {"id": OLD_BALL}, {"id": "2147483648"}, {"id": "01990101"},
    {"element": 6}, {"element": True}, {"pf_type": 5},
    {"panel": {"mode": "scaled", "hp_scale": 0}},
    {"panel": {"mode": "manual", "levels": [{"level": 1, "hp": 5, "attack": 2},
                                                {"level": 1, "hp": 10, "attack": 4}]}},
    {"skill": {"mode": "specified", "key": "missing"}},
    {"lifetime": {"frames": 0}},
    {"extensions": {"ball_pf_action": "missing"}},
])
def test_invalid_requests_fail_before_any_draft_write(summon_env, overrides):
    _, store, editor = summon_env
    with pytest.raises(DraftError):
        editor.apply(CID, request(**overrides))
    assert not store.root.exists()


def test_donor_drift_is_rejected_and_multiple_summons_merge(summon_env):
    from wf.studio.summon import compile_summons
    source, store, editor = summon_env
    editor.apply(CID, request())
    editor.apply(CID, request(id="1990102", template={"kind": "multiball", "id": OLD_BALL}))
    assert {NEW_BALL, "1990102", OLD_BALL} <= set(rows(compiled(summon_env)[BALL]))
    changed = dict(source.view.files)
    changed["common", STATUS] += b"drift"
    with pytest.raises(DraftError):
        compile_summons(StudioSource(View(changed)), store, store.load(CID))


def test_auto_allocation_skips_other_draft_reservation(summon_env):
    source, _, editor = summon_env
    first = editor.apply(CID, {"template": {"kind": "character", "id": MOTHER}})
    second = editor.apply(MOTHER, {"template": {"kind": "character", "id": MOTHER}})
    assert first["multiballId"] != second["multiballId"]
    assert NEW_BALL not in source.table(BALL)


def test_updating_same_summon_replaces_change_and_releases_disabled_extension(summon_env):
    source, store, editor = summon_env
    first = editor.apply(CID, request(extensions={"flip_pf": {"enabled": True}}))
    second = editor.apply(CID, request(element=1, extensions={"flip_pf": {"enabled": False}}))
    draft = store.load(CID)
    assert len(draft["changes"]) == 1 and first["change"]["id"] == second["change"]["id"]
    assert flat(compiled(summon_env)[BALL], NEW_BALL)[0][3] == "1"
    key = "wfx_summon_flip_pf_" + NEW_BALL
    assert key not in rows(compiled(summon_env)[STRINGS])
    assert check_id(source, "string_id", key, drafts_root=store.root)["available"]


def test_compile_rechecks_new_foreign_string_reservation(summon_env):
    from wf.studio.summon import compile_summons
    source, store, editor = summon_env
    editor.apply(CID, request())
    foreign = store.load_or_new(MOTHER, "fixture_mother", source.version)
    foreign["reservations"] = {"string_id": ["studio_summon_" + NEW_BALL]}
    store._write(MOTHER, foreign)
    with pytest.raises(DraftError, match="字符串键"):
        compile_summons(source, store, store.load(CID))


def test_character_panel_preserves_native_float_order_before_ceil(summon_env):
    from wf.studio.summon import SummonEditor
    source, store, _ = summon_env
    source.view.files["common", STATUS] = ordered({MOTHER: ordered({
        "1": leaf([["1", "1"]]), "6": leaf([["6", "6"]])})})
    source = StudioSource(source.view)
    editor = SummonEditor(source, store=store)
    editor.apply(CID, request())
    hp, attack = panel_values(compiled((source, store, editor)), NEW_BALL)
    # Native interpolation uses a*(1-t)+b*t. At t=2/5 IEEE-754 yields
    # 3.0000000000000004; ceil must stay 4, unlike the rearranged a+(b-a)*t.
    assert hp[3] == attack[3] == 4
    assert hp[1] == attack[1] == 1 and hp[6] == attack[6] == 6


@pytest.mark.parametrize("pf_row", [["only_one_level"], ["level1", "", "level3"]])
def test_pf_extension_requires_three_nonempty_native_action_levels(summon_env, pf_row):
    from wf.studio.summon import SummonEditor
    source, store, _ = summon_env
    source.view.files["common", PF] = ordered({"fixture_pf": leaf([pf_row])})
    editor = SummonEditor(StudioSource(source.view), store=store)
    with pytest.raises(DraftError):
        editor.apply(CID, request(extensions={"ball_pf_action": "fixture_pf"}))
    assert not store.root.exists()


def test_json_integer_valued_numbers_encode_as_native_integer_cells(summon_env):
    _, _, editor = summon_env
    result = editor.apply(CID, request(element=4.0, pf_type=1.0, lifetime={"frames": 60.0},
        panel={"mode": "manual", "levels": [{"level": 1.0, "hp": 100, "attack": 20}]},
        extensions={"flip_pf": {"enabled": True, "min_interval_frames": 12.0}}))
    tables = compiled(summon_env)
    row = flat(tables[BALL], NEW_BALL)[0]
    assert row[3] == "4" and row[6] == "1"
    assert flat(tables[STRINGS], "wfx_summon_flip_pf_" + NEW_BALL) == [["1:12"]]
    assert result["skillTemplate"]["lifetimeFrames"] == 60
    assert type(result["skillTemplate"]["lifetimeFrames"]) is int
    assert panel_values(tables, NEW_BALL) == ({1: 100}, {1: 20})
