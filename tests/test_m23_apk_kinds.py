"""Real ABC fixtures distinguish a base parser from an R3 parser without APKs."""
import hashlib
import json
import struct
import zipfile

import pytest
import wf_describe

from wf.apk import asm
from wf.apk.abcfmt import ABC, Trait
from wf.apk.cli import main
from wf.apk.kind_branches import TABLE_CLASSES, SCALAR_BLOCKS, branch_kinds, registry_mismatches
from wf.apk.kinds import inspect_profile, inspect_provides, inspect_swf, kind_supported
from wf.caps import profiles


def _code(string_indices):
    instructions = []
    for offset, index in enumerate(string_indices):
        instructions.extend([("getlocal_1",), ("pushstring", index),
                             ("ifne", f"next{offset}"), ("pushnull",),
                             ("returnvalue",), ("label", f"next{offset}")])
    return asm.encode(asm.assemble(instructions + [("pushnull",), ("returnvalue",)]))[0]


def _fixture_swf(*, equipment_r3):
    abc = ABC(struct.pack("<HH", 16, 46) + b"\x01" * 7 + b"\0" * 5)
    abc.strings = [b"", b"0", b"423"]
    abc.namespaces = [(0, 0), (0x16, 0)]
    abc.multinames = [(0,)]
    abc.methods = [[0, [], 0, 0, None, None]]
    abc.bodies = [[0, 0, 1, 0, 0, b"\x47", [], []]]

    def name(text):
        abc.strings.append(text.encode())
        abc.multinames.append((7, 1, len(abc.strings) - 1))
        return len(abc.multinames) - 1

    for table, class_name in TABLE_CLASSES.items():
        class_index, traits = name(class_name), []
        for block, column in wf_describe.layout(table)["blocks"].items():
            if block in SCALAR_BLOCKS:
                continue
            method = len(abc.methods)
            abc.methods.append([0, [0], 0, 0, None, None])
            trait = Trait()
            trait.name, trait.kind, trait.attr = name(f"parseAt{column}"), 1, 0
            trait.data, trait.metadata = ["method", 0, method], []
            traits.append(trait)
            supported = [1]
            if block == "during_content" and (table == "ability" or equipment_r3 and table in {
                    "ability_soul", "equipment_enhancement_ability"}):
                supported.append(2)
            abc.bodies.append([method, 2, 2, 0, 0, _code(supported), [], []])
        abc.instances.append([class_index, 0, 0, None, [], 0, []])
        abc.classes.append([0, traits])
    raw = abc.serialize()
    assert ABC(raw).serialize() == raw
    content = b"\0" * 4 + b"boot_ffc6\0" + raw
    body = b"\0" * 5 + struct.pack("<HI", (82 << 6) | 63, len(content)) + content + b"\0\0"
    return b"FWS\x0a" + struct.pack("<I", len(body) + 8) + body


def _registry():
    def cap(tables):
        return {"data_surface": {"kinds": [423], "allowed_tables": tables,
                                 "kind_bindings": [{"block": "during_content", "kind": 423}],
                                 "allowed_blocks": ["during_content"]}}
    return {"base423": cap(["ability"]),
            "r3": cap(["ability_soul", "equipment_enhancement_ability"])}


def _profile(monkeypatch, tmp_path, *, equipment_r3):
    source = tmp_path / "fixture.swf"
    source.write_bytes(_fixture_swf(equipment_r3=equipment_r3))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    available = ["base423", "r3"] if equipment_r3 else ["base423"]
    provides = {"source": {"path": str(source), "swf_sha256": digest},
                "provides": [{"id": value} for value in available]}
    record = {"evidence": {"swf_path": str(source), "swf_sha256": digest}}
    monkeypatch.setattr(profiles, "load_profiles", lambda: ("fixture", {"fixture": record}))
    monkeypatch.setattr(profiles, "resolve_client", lambda **kwargs: (tmp_path / "provides.json", "fixture"))
    monkeypatch.setattr(profiles, "read_client", lambda path: provides)
    return source, provides, record


@pytest.mark.parametrize("equipment_r3", [False, True])
def test_actual_abc_body_branches_and_hashes(tmp_path, equipment_r3):
    source = tmp_path / "client.swf"
    original = _fixture_swf(equipment_r3=equipment_r3)
    source.write_bytes(original)
    report = inspect_swf(source)
    assert set(report["tables"]) == set(TABLE_CLASSES)
    assert kind_supported(report, "ability", "during_content", 423)
    for table in ("ability_soul", "equipment_enhancement_ability"):
        assert kind_supported(report, table, "during_content", 423) is equipment_r3
        method = report["tables"][table]["during_content"]
        assert method["sha256"] == hashlib.sha256(_code([1, 2] if equipment_r3 else [1])).hexdigest()
    assert not kind_supported(report, "leader_ability", "during_content", 423)
    assert not kind_supported(report, "ability_soul", "instant_content", 423)
    assert source.read_bytes() == original


def test_cli_base_fixture_does_not_list_equipment_423(monkeypatch, tmp_path, capsys):
    _profile(monkeypatch, tmp_path, equipment_r3=False)
    monkeypatch.setattr("wf.caps.registry.load_registry", _registry)
    assert main(["kinds", "--profile", "fixture"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["profile"] == "fixture"
    assert "423" not in report["tables"]["ability_soul"]["during_content"]["kinds"]
    assert "423" not in report["tables"]["equipment_enhancement_ability"]["during_content"]["kinds"]


def test_cli_registry_disagreement_returns_nonzero(monkeypatch, tmp_path, capsys):
    _, provides, _ = _profile(monkeypatch, tmp_path, equipment_r3=False)
    provides["provides"].append({"id": "r3"})
    monkeypatch.setattr("wf.caps.registry.load_registry", _registry)
    assert main(["kinds", "--profile", "fixture"]) == 1
    mismatch = json.loads(capsys.readouterr().out)["mismatches"][0]
    assert mismatch["missing_branches"] == ["ability_soul", "equipment_enhancement_ability"]


def test_profile_sha_is_binding_and_changed_file_cannot_reuse_cache(monkeypatch, tmp_path):
    source, _, _ = _profile(monkeypatch, tmp_path, equipment_r3=True)
    assert not inspect_profile("fixture", registry=_registry())["mismatches"]
    source.write_bytes(_fixture_swf(equipment_r3=False))
    with pytest.raises(ValueError, match="SWF 哈希"):
        inspect_profile("fixture", registry=_registry())


def test_apk_reads_member_without_extracting(tmp_path):
    source = tmp_path / "client.apk"
    raw = _fixture_swf(equipment_r3=True)
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("assets/worldflipper_android_release.swf", raw)
    before = set(tmp_path.iterdir())
    report = inspect_swf(source, expected_sha256=hashlib.sha256(raw).hexdigest())
    assert report["source"]["member"] == "assets/worldflipper_android_release.swf"
    assert kind_supported(report, "ability_soul", "during_content", 423)
    assert set(tmp_path.iterdir()) == before


def test_provides_fallback_matches_hash_not_profile_label(monkeypatch, tmp_path):
    _, provides, _ = _profile(monkeypatch, tmp_path, equipment_r3=True)
    provides["source"]["path"] = "not-present.swf"
    assert not inspect_provides(provides, registry=_registry())["mismatches"]
    provides["source"]["swf_sha256"] = "0" * 64
    with pytest.raises(FileNotFoundError, match="实际 SWF/APK"):
        inspect_provides(provides, registry=_registry())


def test_unprovided_extensions_are_not_required_but_union_is_checked(tmp_path):
    source = tmp_path / "base.swf"
    source.write_bytes(_fixture_swf(equipment_r3=False))
    tables = inspect_swf(source)["tables"]
    assert not registry_mismatches(tables, _registry(), {"base423"})
    errors = registry_mismatches(tables, _registry(), {"base423", "r3"})
    assert errors[0]["missing_branches"] == ["ability_soul", "equipment_enhancement_ability"]
    source.write_bytes(_fixture_swf(equipment_r3=True))
    assert not registry_mismatches(inspect_swf(source)["tables"], _registry(), {"base423", "r3"})


def test_literal_without_comparison_and_unreachable_branch_are_excluded():
    raw = asm.encode(asm.assemble([
        ("pushstring", 1), ("pop",), ("returnvoid",),
        ("getlocal_1",), ("pushstring", 1), ("ifne", "done"),
        ("returnvoid",), ("label", "done"), ("returnvoid",),
    ]))[0]
    assert branch_kinds(raw, [b"", b"423"]) == []


def test_malformed_swf_is_an_explicit_error(tmp_path):
    source = tmp_path / "broken.swf"
    source.write_bytes(b"CWS\x0a" + struct.pack("<I", 99) + b"invalid-zlib")
    with pytest.raises(ValueError, match="SWF/ABC 无法解析"):
        inspect_swf(source)
