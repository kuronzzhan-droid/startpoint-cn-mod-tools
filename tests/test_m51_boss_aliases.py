"""New local quests resolve aliases without weakening baseline identity checks."""
import pytest
import wf_quest_lib as codec

from test_boss_model import source, row
from test_studio_boss_checks import fixture_editor, request
from wf.boss import schema as s
from wf.studio.boss import BossEditor
from wf.studio.drafts import DraftError


@pytest.mark.parametrize("alias", ["hard_multi:2100/1", "hard_multi:2100001"])
def test_new_shared_alias_reads_and_edits_the_same_numeric_draft(tmp_path, alias):
    editor = fixture_editor(tmp_path)
    created = editor.apply("new", request())
    identity = created["questId"]
    assert identity == "2100001"
    assert editor.canonical(alias) == identity
    assert editor.read(alias)["changeset"] == editor.read(identity)["changeset"]
    edited = editor.apply(alias, {"operation": "edit", "parameters": {"hpMultiplier": 2}})
    assert edited["questId"] == identity
    assert len(editor.store.characters()) == 1
    assert len(edited["change"]["params"]["requests"]) == 2


@pytest.mark.parametrize("alias", ["hard_multi:2100/2", "boss_battle:2100001", "practice:2100001"])
def test_new_alias_does_not_reinterpret_difficulty_or_kind(tmp_path, alias):
    editor = fixture_editor(tmp_path)
    editor.apply("new", request())
    with pytest.raises(DraftError):
        editor.read(alias)
    assert len(editor.store.characters()) == 1


class MemoryStore:
    def __init__(self, event="2100"):
        self.event = event

    def load(self, identity):
        if identity == "2100001":
            return {"changes": [{"params": {"requests": [
                {"operation": "create_shared", "ids": {"event": self.event, "node": "31"}}]}}]}
        return None


@pytest.mark.parametrize("identity", ["2100001", "hard_multi:2100/1", "hard_multi:2100001"])
def test_new_alias_requires_the_saved_event_to_derive_the_same_quest(identity):
    editor = BossEditor(source(), store=MemoryStore(event="2101"))
    with pytest.raises(ValueError):
        editor.canonical(identity)


def test_new_alias_cannot_shadow_an_existing_other_kind_id():
    base = source()
    base.files[s.QUEST_TABLES["boss_battle"]] = codec.build_node({
        "1": {"99": {"1": row(130, {0: "2100001", 2: "existing"})}}})
    editor = BossEditor(base, store=MemoryStore())
    with pytest.raises(ValueError):
        editor.canonical("hard_multi:2100/1")


def test_new_fallback_cannot_hide_an_ambiguous_baseline_id():
    base = source()
    quest_row = row(130, {0: "2100001", 2: "existing"})
    base.files[s.QUEST_TABLES["boss_battle"]] = codec.build_node({"1": {"99": {"1": quest_row}}})
    base.files[s.QUEST_TABLES["hard_multi"]] = codec.build_node({"2100": {"1": quest_row}})
    editor = BossEditor(base, store=MemoryStore())
    with pytest.raises(ValueError, match="ID 不唯一"):
        editor.canonical("2100001")
