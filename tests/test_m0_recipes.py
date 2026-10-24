"""Boundary and byte-comparison regressions for historical delivery recipes."""
from __future__ import annotations
import zipfile
from wf.view.base149 import HistoricalView, member
from wf.view.compare import compare_zip
from wf.view.stage_all import csv_text, detect_style, dump_like


def _archive(path, name, value, stamp=(2020, 1, 1, 0, 0, 0)):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        info = zipfile.ZipInfo(name, stamp)
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, value)


def test_historical_view_preserves_overlay_order_and_base(tmp_path):
    active = tmp_path / "active"
    store = tmp_path / "store"
    active.mkdir(); store.mkdir()
    name = member("master/table.orderedmap")
    location = store / name.removeprefix("production/upload/")
    location.parent.mkdir(); location.write_bytes(b"base")
    earlier = active / "pinball-1.4.131-1.4.132-1-data-local.zip"
    later = active / "pinball-1.4.132-1.4.133-1-data-local.zip"
    _archive(earlier, name, b"first")
    _archive(later, name, b"later")
    extra = tmp_path / "extra.zip"
    _archive(extra, name, b"extra")
    assert HistoricalView(store=store, active=active, tip=131).read_raw("master/table.orderedmap")[0] == b"base"
    assert HistoricalView(store=store, active=active, tip=132).read_raw("master/table.orderedmap")[0] == b"first"
    assert HistoricalView(store=store, active=active, tip=133, extra_zips=[extra]).read_raw("master/table.orderedmap")[0] == b"extra"
    assert location.read_bytes() == b"base"


def test_zip_comparison_separates_timestamps_from_content(tmp_path):
    old, new = tmp_path / "old.zip", tmp_path / "new.zip"
    _archive(old, "data", b"same")
    _archive(new, "data", b"same", (2021, 2, 3, 4, 5, 6))
    result = compare_zip(old, new)
    assert result["equal_members"] == 1
    assert not result["container_equal"]
    assert result["container_equal_without_dos_timestamps"]
    _archive(new, "data", b"different", (2021, 2, 3, 4, 5, 6))
    result = compare_zip(old, new)
    assert result["different_members"] == 1
    assert not result["container_equal_without_dos_timestamps"]


def test_staging_preserves_csv_and_json_style():
    assert csv_text([["comma,cell", "line\nbreak"]]) == '\"comma,cell\",\"line\nbreak\"\n'
    text = '{\n  "a": 1\n}\n'
    assert dump_like({"a": 1}, detect_style(text)) == text


def test_historical_pf3_formula_keeps_221_and_default_keeps_222_fix(monkeypatch):
    # Preserve the process environment despite the legacy pack-context adapter.
    import os
    monkeypatch.setenv("WF_TARGET_STORE", os.environ.get("WF_TARGET_STORE", ""))
    from wf.chars.halloween import kit_seriol
    original = ["ActionDsl"] + [None] * 10 + [["Block", [
        ["Command", ["SetPowerFilpSuppress", True]],
        ["Command", ["CreateHitArea"]],
        ["Event", ["Wait", 1, "*", ["Block", [["Command", ["NotifyPowerflipEnd"]]]]]],
    ]]]
    monkeypatch.setattr(kit_seriol.K, "load_tree", lambda *_: original)
    historical = kit_seriol.pf3_tree(None, preserve_221=True)
    current = kit_seriol.pf3_tree(None)
    assert historical[10] == current[10] == 133
    assert "SetPowerFilpSuppress" in repr(historical)
    assert "NotifyPowerflipEnd" in repr(historical)
    assert "SetPowerFilpSuppress" not in repr(current)
    assert "NotifyPowerflipEnd" not in repr(current)
    assert original[10] is None
