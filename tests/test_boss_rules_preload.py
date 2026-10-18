"""C8016 rejection reads real compressed DSL, not a claimed shim flag."""
import copy
import zlib

import wf_dsl

from wf.rules.boss_preload import DslEvidence, FUNNEL, GENERAL, preload_check, tier


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


def test_preload_reads_same_first_native_band_as_client():
    assert tier({"100": "first", "49": "later"}, 10) == ["first"]
    assert tier({"49": "only"}, 100) == []


def test_unproven_attribute_change_requires_explicit_acknowledgment():
    before, after = documents()
    for view in (None, View()):
        if view:
            view.tables[GENERAL] = {}
        blocked = preload_check(after, baseline=before, view=view)
        assert blocked["status"] == "待验证" and blocked["blocking"]
        assert preload_check(after, baseline=before, view=view,
                             context={"acknowledgePreload": "true"})["blocking"]
        waived = preload_check(after, baseline=before, view=view,
                               context={"acknowledgePreload": True})
        assert waived["status"] == "待验证" and not waived["blocking"]
        assert waived["acknowledgment"] == {
            "acknowledgePreload": True, "scope": "unproven-preload-only"}


def test_zako_summoning_stays_blocked_until_explicit_acknowledgment():
    before, after = documents()
    view = View()
    view.put("battle/action/summon.action.dsl.amf3.deflate", ["SpawnFunnel", ["Zako", "eye"]])
    check = preload_check(after, baseline=before, view=view)
    assert check["status"] == "待验证" and check["blocking"]
    assert any("Zako" in item for item in check["limitations"])


def test_known_c8016_family_cannot_be_waived_or_declared_safe_without_view():
    before, after = documents()
    before["enemies"][0]["code"] = after["enemies"][0]["code"] = "arch_evil_multi"
    check = preload_check(after, baseline=before, context={"acknowledgePreload": True})
    assert check["status"] == "问题" and check["blocking"]
    assert "C8016_BLOCKED_BOSS_PREFIXES" in check["issues"][0]
    assert preload_check(before, baseline=before)["status"] == "不适用"


def test_acknowledgment_cannot_waive_a_proven_missing_shim():
    before, after = documents()
    check = preload_check(after, baseline=before, view=View(), context={"acknowledgePreload": True})
    assert check["status"] == "问题" and check["blocking"]


def test_closure_splits_comma_references_in_roots_and_nested_programs():
    view = View()
    view.put("battle/action/root.action.dsl.amf3.deflate", [
        "battle/action/summon,battle/action/extra"])
    view.put("battle/action/extra.action.dsl.amf3.deflate", ["Wait", 1])
    evidence = DslEvidence(view)
    found = evidence.closure(["battle/action/root, battle/action/funnel"])
    assert set(found) == {"battle/action/root", "battle/action/funnel", "battle/action/summon", "battle/action/extra"}
    assert not evidence.missing
