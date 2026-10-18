"""C8016 rejection reads real compressed DSL, not a claimed shim flag."""
import copy
import zlib

import wf_dsl

from wf.rules.boss_preload import FUNNEL, GENERAL, preload_check


class View:
    def __init__(self):
        boss = [""] * 161
        boss[0], boss[25], boss[41], boss[111] = "3", "battle/marker/test", "p0", "battle/action/summon"
        funnel = ["1", "battle/action/funnel"]
        self.tables = {GENERAL: {"boss": {"100": boss}}, FUNNEL: {"funnel": {"100": funnel}}}
        self.files = {}
        self.put("battle/action/summon.action.dsl.amf3.deflate", ["SpawnFunnel", ["Funnel", "funnel"]])
        self.put("battle/action/funnel.action.dsl.amf3.deflate", ["ResolveByElement", "battle/effect/shot", 255])
        self.put("battle/marker/test.timeline.amf3.deflate", {"points": [
            {"path": "enemy_action1", "frames": [{"data": [1]}]}]})

    def table(self, logical):
        return self.tables.get(logical)

    def raw(self, logical):
        return self.files.get(logical)

    def put(self, logical, value):
        compressor = zlib.compressobj(wbits=-15)
        raw = wf_dsl.encode_amf3(value)
        self.files[logical] = compressor.compress(raw) + compressor.flush()


def documents():
    before = {"quest": {"fields": {"recommended_element": "0"}},
              "enemies": [{"code": "boss", "level": 100}]}
    after = copy.deepcopy(before)
    after["quest"]["fields"]["recommended_element"] = "2"
    return before, after


def test_changed_element_without_actual_shim_blocks_even_if_metadata_claims_it():
    before, after = documents()
    after["preload_shims"] = True
    check = preload_check(after, baseline=before, view=View())
    assert check["status"] == "问题"
    assert check["blocking"]
    assert "C8016" in check["issues"][0]


def test_exact_fixed_dsl_in_unused_marker_slot_passes():
    before, after = documents()
    view = View()
    view.tables[GENERAL]["boss"]["100"][160] = "battle/action/shim"
    view.put("battle/action/shim.action.dsl.amf3.deflate", ["ResolveByElement", "battle/effect/shot", 1])
    check = preload_check(after, baseline=before, view=view)
    assert check["status"] == "满足"
    assert check["proofs"][0]["slots"] == [50]


def test_triggered_or_wrong_attribute_shim_blocks():
    before, after = documents()
    view = View()
    view.tables[GENERAL]["boss"]["100"][160] = "battle/action/shim"
    view.put("battle/action/shim.action.dsl.amf3.deflate", ["ResolveByElement", "battle/effect/shot", 3])
    assert preload_check(after, baseline=before, view=view)["blocking"]
    view.put("battle/action/shim.action.dsl.amf3.deflate", ["ResolveByElement", "battle/effect/shot", 1])
    view.put("battle/marker/test.timeline.amf3.deflate", {"points": [
        {"path": "enemy_action50", "frames": [{"data": [1]}]}]})
    assert preload_check(after, baseline=before, view=view)["blocking"]


def test_absent_marker_and_missing_baseline_are_not_passed():
    before, after = documents()
    view = View()
    view.tables[GENERAL]["boss"]["100"][160] = "battle/action/shim"
    view.put("battle/action/shim.action.dsl.amf3.deflate", ["ResolveByElement", "battle/effect/shot", 1])
    del view.files["battle/marker/test.timeline.amf3.deflate"]
    assert preload_check(after, baseline=before, view=view)["status"] == "待验证"
    assert preload_check(after, view=view)["status"] == "未执行"


def test_party_restriction_alone_does_not_change_enemy_attribute():
    before, after = documents()
    after["quest"]["fields"] = {"recommended_element": "0", "restriction": "1"}
    assert preload_check(after, baseline=before, view=View())["status"] == "不适用"
