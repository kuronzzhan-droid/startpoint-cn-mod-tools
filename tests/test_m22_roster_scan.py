"""Full-roster scan must retain official characters and explicit APK evidence."""
import io
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

from wf.caps.scan_bundle import BundleFallbackView
from wf.caps.scan_source import ScanSource
from wf.view.base149 import member


def test_all_characters_retains_unchanged_official_and_modified():
    official = [""] * 25
    official[0] = "official"
    modified = official.copy()
    modified[0] = "modified"
    tables = {"character": {"1": [official], "2": [modified]}, "text": {"1": [["原生"]]}}
    baseline = {"character": {"1": [official], "2": [official]}}
    source = ScanSource.__new__(ScanSource)
    source.table = lambda name, old=False: (baseline if old else tables).get(name, {})
    assert [row["id"] for row in source.characters()] == ["2"]
    source.all_characters = True
    records = source.characters()
    assert [(r["id"], r["origin"]) for r in records] == [("1", "official"), ("2", "modified")]
    assert records[0]["name"] == "原生"


def make_apk(path, logical, raw=b"bundle", *, common=None):
    bundle = io.BytesIO()
    relative = member(logical).removeprefix("production/upload/")
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("production/android_bundle/" + relative, raw)
        if common is not None:
            archive.writestr("production/common_bundle/" + relative, common)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("assets/bundle.zip", bundle.getvalue())


def missing(_):
    raise FileNotFoundError("absent from store")


def test_bundle_fallback_records_member_and_preserves_manifest_precedence(tmp_path):
    logical = "battle/skill/alk.action.dsl.amf3.deflate"
    apk = tmp_path / "test.apk"
    make_apk(apk, logical)
    view = SimpleNamespace(read_raw=missing, verify=lambda: {"tip": "1.4.238"})
    fallback = BundleFallbackView(view, apk)
    assert fallback.read_raw(logical)[0] == b"bundle"
    evidence = fallback.bundle_evidence()
    assert len(evidence["apk_sha256"]) == 64
    assert logical in evidence["members"]
    view.read_raw = lambda _: (b"manifest", "patch")
    assert fallback.read_raw(logical) == (b"manifest", "patch")
    assert fallback.verify() == {"tip": "1.4.238"}
    apk.write_bytes(b"changed")
    with pytest.raises(ValueError, match="source changed"):
        fallback.verify()


def test_bundle_missing_or_ambiguous_member_is_not_silently_empty(tmp_path):
    logical = "battle/skill/alk.action.dsl.amf3.deflate"
    apk = tmp_path / "test.apk"
    make_apk(apk, logical, common=b"different")
    fallback = BundleFallbackView(SimpleNamespace(read_raw=missing), apk)
    with pytest.raises(ValueError, match="ambiguous"):
        fallback.read_raw(logical)
    with pytest.raises(FileNotFoundError):
        fallback.read_raw("battle/skill/missing.action.dsl.amf3.deflate")


def test_roster_inference_follows_referenced_unique_without_claiming_all_characters(monkeypatch):
    from wf.caps import roster_requirements as module
    from wf.caps.facts import CHARACTER
    from wf_quest_lib import build_node
    data = build_node({"1": "first", "2": "second"})
    source = SimpleNamespace(view=SimpleNamespace(read_raw=lambda _: (data, "source")))
    def infer(members, **options):
        raw, entry = members[CHARACTER]
        assert module.parse_table(raw, CHARACTER) == {"2": "second"}
        assert module.parse_table(options["read_raw"](CHARACTER), CHARACTER) == {}
        return {"clientCapabilities": ["specific@1"]}
    monkeypatch.setattr(module, "infer_requirements", infer)
    assert module.CharacterRequirements(source, {}).infer("2") == {"clientCapabilities": ["specific@1"]}
