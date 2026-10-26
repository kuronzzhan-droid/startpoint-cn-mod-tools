"""Compilation rechecks IDs in other saved drafts, including restored conflicts."""
from __future__ import annotations

import json

import pytest
import wf_quest_lib as codec

from wf.boss import schema as s
from wf.studio.boss import compile_boss
from wf.view.base149 import join
from test_studio_boss_checks import fixture_editor, request
from test_boss_shop_weapon import state as shop_state  # noqa: F401


def save(editor, quest, payload):
    applied = editor.apply(quest, payload)
    return editor.store.save(applied["questId"])


def tamper(editor, draft, mutate):
    """Model a restored/manually changed saved JSON, outside the editor guard."""
    mutate(draft["changes"][0]["params"]["requests"][0])
    path = editor.store.directory(draft["characterId"]) / "changeset.json"
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    return editor.store.load(draft["characterId"])


def compile_saved(editor, draft):
    return compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)


def test_compile_rechecks_other_saved_draft_folder_node(tmp_path):
    editor = fixture_editor(tmp_path)
    first = save(editor, "new", request(name="First"))
    second = save(editor, "new", request(name="Second"))
    assert compile_saved(editor, first)["client"]
    assert compile_saved(editor, second)["client"]
    node = first["changes"][0]["params"]["requests"][0]["ids"]["node"]
    second = tamper(editor, second, lambda payload: payload["ids"].update(node=node))
    with pytest.raises(ValueError, match="collision.*node"):
        compile_saved(editor, second)


@pytest.fixture
def editor(tmp_path, shop_state):
    editor = fixture_editor(tmp_path)
    raw = editor.source.view
    raw.files.update(shop_state.base.files)
    for source in (shop_state.server_dir / "assets").iterdir():
        (editor.server_dir / "assets" / source.name).write_bytes(source.read_bytes())
    quests = codec.parse_node(raw.files[s.QUEST_TABLES["hard_multi"]])
    values = s.parse_rows(quests["1006"]["1"])[0]
    values[0] = "1007001"
    quests["1007"] = {"1": join(values)}
    raw.files[s.QUEST_TABLES["hard_multi"]] = codec.build_node(quests)
    events = codec.parse_node(raw.files[s.EVENT])
    values = s.parse_rows(events["1006"])[0]
    values[16] = "1"  # native currency association with fixture shop category 81
    events["1006"] = events["1007"] = join(values)
    raw.files[s.EVENT] = codec.build_node(events)
    return editor


def test_compile_rechecks_product_id_from_other_saved_quest(editor):
    payload = {"operation": "shop_add", "shop": {"category": "81", "sourceProduct": "100"}}
    first = save(editor, "1006001", payload)
    second = save(editor, "1007001", payload)
    assert compile_saved(editor, first)["client"] and compile_saved(editor, second)["client"]
    identity = first["changes"][0]["params"]["requests"][0]["shop"]["productId"]
    second = tamper(editor, second, lambda req: req["shop"].update(productId=identity))
    with pytest.raises(ValueError, match="collision"):
        compile_saved(editor, second)


@pytest.mark.parametrize("field", ["id", "enhancementProducts"])
def test_compile_rechecks_weapon_and_enhancement_ids_from_other_saved_quest(editor, field):
    payload = {"operation": "weapon_clone", "weapon": {"sourceWeapon": "5010005", "name": "Copy"}}
    first = save(editor, "1006001", payload)
    second = save(editor, "1007001", payload)
    assert compile_saved(editor, first)["client"] and compile_saved(editor, second)["client"]
    value = first["changes"][0]["params"]["requests"][0]["weapon"][field]
    second = tamper(editor, second, lambda req: req["weapon"].update({field: value}))
    # A foreign stage ID also violates the native weapon * 100 + stage mapping;
    # reject that invalid allocation before looking for an occupied stage ID.
    reason = ("collision" if field == "id" else
              r"^allocated enhancement product ID must match weapon ID \* 100 \+ stage$")
    with pytest.raises(ValueError, match=reason):
        compile_saved(editor, second)


def test_compile_reserves_enhancement_namespace_from_other_saved_quest(editor):
    payload = {"operation": "weapon_clone", "weapon": {"sourceWeapon": "5010005"}}
    first = save(editor, "1006001", payload)
    second = save(editor, "1007001", payload)
    assert compile_saved(editor, second)["client"]
    spec = second["changes"][0]["params"]["requests"][0]["weapon"]
    # The candidate keeps its valid stage mapping; the other restored draft
    # now reserves its stage namespace and compilation must still block it.
    tamper(editor, first, lambda req: req["weapon"].update(
        enhancementProducts=spec["enhancementProducts"]))
    with pytest.raises(ValueError, match="ID collision: " + spec["id"]):
        compile_saved(editor, second)
