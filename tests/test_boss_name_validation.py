"""Unsafe names are rejected through both generation and draft replay."""
import copy

import pytest

from wf.boss.template import allocate, template_rows
from wf.studio.boss import compile_boss
from test_boss_edit_review import edit_state
from test_studio_boss_checks import fixture_editor, request


@pytest.mark.parametrize("name", ["a\nb", "a\rb", 'a"b', "a'b", "a::b", "a“b”", "a\u2028b"])
def test_template_rejects_csv_and_token_delimiters(tmp_path, name):
    state = edit_state(tmp_path)
    with pytest.raises(ValueError, match="name.*换行"):
        template_rows(state, {"name": name}, allocate(state))
    assert not state.client and not state.servers


def test_preview_and_saved_replay_reject_an_unsafe_name(tmp_path):
    editor = fixture_editor(tmp_path)
    assert not editor.preview("new", request(name='unsafe"name'))["ok"]
    saved = editor.apply("new", request(name="合法，共同决战"))["changeset"]
    tampered = copy.deepcopy(saved)
    tampered["changes"][0]["params"]["requests"][0]["name"] = "unsafe::name"
    with pytest.raises(ValueError, match="name.*换行"):
        compile_boss(editor.source, editor.store, tampered, server_dir=editor.server_dir)


def test_valid_name_preserves_comma_and_appends_only_the_official_token(tmp_path):
    state = edit_state(tmp_path)
    generated = template_rows(state, {"name": "丑王,奥格"}, allocate(state))
    assert generated["quest"][2] == "丑王,奥格 ::quest_rank::"
