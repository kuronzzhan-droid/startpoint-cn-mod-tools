"""Resource assertions and deletion preserve unrelated compressed/value bytes."""
import json

import pytest

import wf_mod_tool as core
import wf_quest_lib as codec
from wf.boss.edit_bytes import append_values, delete_keys
from wf.boss.edit_state import BossEditState
from test_boss_edit_review import RawSource


def test_resource_replace_new_assertion_and_source_drift():
    source = RawSource({})
    source.files = {"battle/terrain/old.amf3.deflate": b"original"}
    state = BossEditState(source)
    state.set_raw("battle/terrain/new.amf3.deflate", b"candidate", new=True)
    state.set_raw("battle/terrain/old.amf3.deflate", b"edited")
    expected = state.snapshot()
    assert expected["client"]["battle/terrain/new.amf3.deflate"] is None
    assert source.files == {"battle/terrain/old.amf3.deflate": b"original"}
    source.files["battle/terrain/new.amf3.deflate"] = b"now occupied"
    changed = BossEditState(source)
    with pytest.raises(ValueError, match="collision"):
        changed.set_raw("battle/terrain/new.amf3.deflate", b"candidate", new=True)
    changed.set_raw("battle/terrain/new.amf3.deflate", b"candidate")
    changed.set_raw("battle/terrain/old.amf3.deflate", b"edited")
    with pytest.raises(ValueError, match="drift"):
        changed.verify_snapshot(expected)


@pytest.mark.parametrize("logical", ["../escape", "C:/escape", "/escape", "a\\b"])
def test_resource_path_rejects_filesystem_targets(logical):
    with pytest.raises(ValueError, match="logical path"):
        BossEditState(RawSource({})).set_raw(logical, b"data")


def test_delete_nested_leaf_keeps_other_compressed_members():
    import zlib
    keep = zlib.compress(b"retained,value", 1)
    nested = core.build_orderedmap_raw_rows(core.OrderedMap(
        "test", ["remove", "keep"], [zlib.compress(b"delete"), keep], None))
    original = core.build_orderedmap_raw_rows(core.OrderedMap("test", ["category"], [nested], None))
    source = RawSource({})
    source.files = {"master/test.orderedmap": original}
    state = BossEditState(source)
    state.delete_leaf("master/test.orderedmap", ("category", "remove"))
    actual = state.raw("master/test.orderedmap")
    outer = core.read_orderedmap_raw_rows_from_bytes(actual, "test")
    inner = core.read_orderedmap_raw_rows_from_bytes(outer.rows[0], "test")
    assert inner.keys == ["keep"] and inner.rows == [keep]
    assert codec.parse_node(actual) == {"category": {"keep": "retained,value"}}
    assert source.files["master/test.orderedmap"] == original


@pytest.mark.parametrize("removed", [["first"], ["last"], ["中间"], ["first", "中间", "last"]])
def test_delete_server_members_keeps_value_text(removed):
    raw = '{ "first": { "a" : [ 1, 2 ] }, "中间": "escaped\\\" quote", "last": [\n 3,4\n] }'.encode()
    from wf.deliver.json_merge import _json_spans
    text, before, spans = _json_spans(raw)
    result = delete_keys(raw, removed)
    final, after, new_spans = _json_spans(result)
    assert after == {k: v for k, v in before.items() if k not in removed}
    assert all(text[s:e] == final[slice(*new_spans[k])] for k, (s, e) in spans.items() if k not in removed)


def test_append_registry_preserves_old_values_and_avoids_numeric_duplicates():
    raw = b'[ 101,\n "102" ]\n'
    assert append_values(raw, [101, "102"]) is raw
    after = append_values(raw, [102, 103, 103])
    assert after.startswith(b'[ 101,\n "102",')
    assert json.loads(after) == [101, "102", 103]
