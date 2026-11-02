"""2026-10-18 优化清单 B：按视图/草稿修订缓存，结果与不缓存逐项一致；生成改后台任务（进度、取消）。"""
from __future__ import annotations

import json
import threading
import time

import pytest

from wf.studio import perf
from wf.studio.ability import AbilityEditor
from wf.studio.drafts import DraftError, DraftStore

from test_studio_ability import Source, op
from test_studio_ability_text import setup, text_operations


def test_registry_and_parse_cache_hand_out_independent_copies():
    first_registry, second_registry = perf.registry(), perf.registry()
    assert first_registry == second_registry and first_registry is not second_registry
    first_registry[next(iter(first_registry))]["provided_by"]["patches"].append(-1)
    assert perf.registry() == second_registry
    import wf_quest_lib as codec
    raw = codec.build_node({"a": "1", "b": {"1": "x"}})
    first = perf.parsed(raw)
    first["a"] = "changed"
    first["b"]["1"] = "changed"
    assert perf.parsed(raw) == {"a": "1", "b": {"1": "x"}}
    assert perf.parsed(raw, shared=True) is perf.parsed(raw, shared=True)


def _editors(tmp_path):
    source = Source()
    store = DraftStore(tmp_path / "drafts")
    return (AbilityEditor(source, store=store, cache=True), AbilityEditor(source, store=store, cache=False))


def test_memoized_reads_follow_draft_revisions_and_match_uncached(tmp_path):
    cached, plain = _editors(tmp_path)
    first = cached.read("139985")
    assert cached.read("139985") is first           # memo hit
    assert first == plain.read("139985")
    request = {"operations": [op()]}
    assert cached.preview("139985", request) == plain.preview("139985", request)
    cached.apply("139985", request)
    after = cached.read("139985")
    assert after is not first and after == plain.read("139985")
    row = next(e for e in after["entries"] if e["key"] == "1001")["rows"][0]
    assert "20000" in row
    second = {"operations": [op(cells=[{"column": 51, "old": "20000", "new": "30000"}])]}
    assert cached.preview("139985", second)["checks"] == plain.preview("139985", second)["checks"]
    assert cached.preview("139985", second)["changes"] == plain.preview("139985", second)["changes"]


def test_memo_sees_mirror_changes(tmp_path):
    ed, server = setup(tmp_path)
    ed.caching = True
    ed.apply("139985", {"operations": text_operations()})
    panel = ed.text_panel("139985")
    assert ed.text_panel("139985") is panel
    from wf.text.model import SERVER_TARGETS
    target = server / SERVER_TARGETS[1]
    target.write_text(target.read_text("utf-8") + "\n", "utf-8")
    with pytest.raises(DraftError, match="输入已变化"):
        ed.text_panel("139985")


def test_lint_reuses_the_draft_document(tmp_path):
    ed, _ = setup(tmp_path)
    ed.caching = True
    full = ed.text_panel("139985")
    lint = ed.text_panel("139985", text={"desc_override": {"desc_override_first": {
        "old": "自身攻击力提升", "new": "生命值100%以下时攻击力提升"}}}, light=True)
    field = next(f for f in lint["fields"] if f["key"] == "desc_override_first")
    assert field["value"].startswith("生命值100%以下") and any(h["state"] == "问题" for h in field["house"])
    assert next(f for f in full["fields"] if f["key"] == "desc_override_first")["value"] == "自身攻击力提升"


def test_key_search_ranks_key_then_owner_then_description(tmp_path):
    cached, _ = _editors(tmp_path)
    names = {"139985": "英雄"}
    exact = cached.key_search("ability", "1001", cid="139985", names=names)
    assert exact["results"][0]["key"] == "1001" and exact["exact"] == "1001"
    owner = cached.key_search("ability", "英雄", cid="139985", names=names)
    assert [r["key"] for r in owner["results"]] == ["1001"]
    assert cached.key_search("ability", "untouched", cid="139985", names=names)["results"][0]["key"] == "untouched"
    none = cached.key_search("ability", "zzz-no-such", cid="139985", names=names)
    assert none["total"] == 0 and none["exact"] is None


def test_concurrent_draft_overlays_compile_once(tmp_path, monkeypatch):
    from test_studio_pixel_workshop import setup as pixel_setup  # noqa: F401 - reuse the fixture logic
    from test_studio_deliver_media import CID, Source as MediaSource
    from test_studio_pixel_workshop import BASE_CODE, CODE, Ops, family_files
    from wf.studio.pixel_workshop_ops import PixelWorkshop
    source = MediaSource({**family_files(BASE_CODE), **family_files(CODE)})
    store = DraftStore(tmp_path / "drafts")
    shop = PixelWorkshop(Ops(source, store))
    shop.remap(CID, {"base": "111007", "mapping": [{"from": "#a13b3b", "to": "#2a5cc8"}]})
    calls = []
    real = shop.draft_source

    def counted(cid):
        calls.append(cid)
        time.sleep(0.05)
        return real(cid)
    monkeypatch.setattr(shop, "draft_source", counted)
    errors = []

    def worker():
        try:
            shop.cell_png(CID, "pixelart", 2, draft=True)
            shop.analyze(CID, draft=True)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors and calls == [CID]


# -- background 「生成」 ------------------------------------------------------------

def test_background_build_reports_stages_and_cancels(tmp_path, monkeypatch):
    from test_studio_deliver_routes import _FakeSource, _json
    from wf.studio import deliver_bridge
    from wf.studio.deliver_routes import DeliverRoutes
    from wf.studio.server import StudioApp
    app = StudioApp(_FakeSource(), drafts=DraftStore(tmp_path / "drafts"))
    deliver = DeliverRoutes(app, root=tmp_path / "deliveries")
    gate = threading.Event()

    def staged(cid, *, out, progress, cancel, **kwargs):
        out.mkdir(parents=True)
        progress("media")
        gate.wait(5)
        deliver_bridge._step(progress, cancel, "deliver")
        progress("compat")
        return {"ok": True, "characterId": cid, "deviceValidation": "未执行"}

    monkeypatch.setattr(deliver_bridge, "build_draft", staged)
    job = _json(deliver.build({}, {"background": True}, cid="139985"))
    assert job["state"] == "running" and [s["id"] for s in job["stages"]] == ["media", "deliver", "compat", "check"]
    with pytest.raises(DraftError, match="已在生成中"):
        deliver.build({}, {"background": True}, cid="139985")
    _json(deliver.cancel({}, {}, cid="139985"))
    gate.set()
    for _ in range(100):
        state = _json(deliver.job({}, name=job["name"]))
        if state["state"] != "running":
            break
        time.sleep(0.02)
    assert state["state"] == "cancelled" and state["result"]["cancelled"] is True
    assert next(s for s in state["stages"] if s["id"] == "media")["state"] == "cancelled"
    assert not (tmp_path / "deliveries" / job["name"]).exists() and deliver.running == {}

    gate.set()
    done = _json(deliver.build({}, {"background": True}, cid="139985"))
    for _ in range(100):
        state = _json(deliver.job({}, name=done["name"]))
        if state["state"] != "running":
            break
        time.sleep(0.02)
    assert state["state"] == "ok"
    assert [s["state"] for s in state["stages"]] == ["done", "done", "done", "waiting"]
    listing = _json(deliver.listing({"cid": ["139985"]}))
    assert {j["name"] for j in listing["jobs"]} == {job["name"], done["name"]}
    json.dumps(listing)
