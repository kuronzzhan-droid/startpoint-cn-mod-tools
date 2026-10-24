"""Local registration proves actual method/context equality and keeps unknown changes closed."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import zipfile

import pytest

from wf.apk import local_registry, register_local as registration
from wf.apk.common import ABC, abc_tags
from wf.apk.evidence import digest
from wf.apk.manifest import identity
from wf.apk.method_snapshot import Context, snapshot
from wf.caps import profiles
from wf.caps.compat import check_compat
from wf.paths import REPOSITORY
from test_m0_apk import fixture_swf
from test_m2_compat import required


def recorded():
    return json.loads((REPOSITORY / local_registry.BUILTIN).read_text("utf-8"))


def manifest(package="com.leiting.wf"):
    strings = ["manifest", "package", package, "versionCode",
               "http://schemas.android.com/apk/res/android"]
    blob, offsets = b"", []
    for value in strings:
        raw = value.encode()
        offsets.append(len(blob))
        blob += bytes([len(value), len(raw)]) + raw + b"\0"
    start = 28 + 4 * len(strings)
    pool = struct.pack("<HHI5I", 1, 28, start + len(blob), len(strings), 0, 0x100, start, 0)
    pool += struct.pack("<5I", *offsets) + blob
    attrs = struct.pack("<IIIHBBI", 0xFFFFFFFF, 1, 2, 8, 0, 3, 2)
    attrs += struct.pack("<IIIHBBI", 4, 3, 0xFFFFFFFF, 8, 0, 16, 1008001)
    element = struct.pack("<HHIII", 0x102, 16, 36 + len(attrs), 1, 0xFFFFFFFF)
    element += struct.pack("<II6H", 0xFFFFFFFF, 0, 20, 20, 2, 0, 0, 0) + attrs
    return struct.pack("<HHI", 3, 8, 8 + len(pool) + len(element)) + pool + element


def test_binary_manifest_reads_actual_identity_and_rejects_malformed_input():
    assert identity(manifest())["package_name"] == "com.leiting.wf"
    assert identity(manifest())["versionCode"] == 1008001
    for raw in (b"", manifest()[:-1], b"\x03\0\x08\0\x08\0\0\0"):
        with pytest.raises(ValueError):
            identity(raw)


@pytest.mark.parametrize("fault", ["not_zip", "missing_member", "test_package", "bad_manifest", "unknown_swf"])
def test_cli_rejects_untrusted_apk_without_creating_a_profile(tmp_path, capsys, fault):
    from wf.apk.cli import main
    apk = tmp_path / "v35negative-local.apk"
    if fault == "not_zip":
        apk.write_bytes(b"not a zip")
    else:
        with zipfile.ZipFile(apk, "w") as archive:
            archive.writestr("AndroidManifest.xml", b"bad" if fault == "bad_manifest" else
                             manifest("com.leiting.wt" if fault == "test_package" else "com.leiting.wf"))
            if fault != "missing_member":
                archive.writestr("assets/worldflipper_android_release.swf", fixture_swf())
    with pytest.raises(SystemExit) as failure:
        main(["register-local", str(apk)])
    assert failure.value.code == 2
    assert "error:" in capsys.readouterr().err
    assert not (REPOSITORY / "work/local-clients/local-v35negative").exists()


def test_same_code_with_changed_referenced_string_or_namespace_is_not_equivalent():
    abc = ABC(abc_tags(fixture_swf())[0][4])
    abc.strings += [b"before", b"namespace-before"]
    body = abc.bodies[0]
    body[5] = b"\x2c\x02\x29\x47"  # pushstring 2; pop; returnvoid
    before = Context(abc).method(body)
    code = bytes(body[5])
    abc.strings[2] = b"after"
    assert body[5] == code and Context(abc).method(body) != before
    body[5] = b"\x60\x01\x29\x47"  # getlex QName 1; pop; returnvoid
    abc.namespaces[1] = (0x16, 3)
    before = Context(abc).method(body)
    abc.strings[3] = b"namespace-after"
    assert Context(abc).method(body) != before


def test_missing_method_and_unknown_opcode_cannot_be_promoted():
    report = snapshot(fixture_swf(), {("boot_ffc6", "Absent/method")})
    assert "error" in report[("boot_ffc6", "Absent/method")]
    abc = ABC(abc_tags(fixture_swf())[0][4])
    abc.bodies[0][5] = b"\xff"
    with pytest.raises((ValueError, RuntimeError)):
        Context(abc).method(abc.bodies[0])


def test_activation_slot_default_constant_is_part_of_method_context():
    from wf.apk.abcfmt import Trait
    abc = ABC(abc_tags(fixture_swf())[0][4])
    abc.ints.append(10)
    trait = Trait()
    trait.name, trait.kind, trait.attr = 1, 0, 0
    trait.data, trait.metadata = ["slot", 1, 0, 1, 3], []
    abc.bodies[0][7] = [trait]
    before = Context(abc).method(abc.bodies[0])
    abc.ints[1] = 20
    assert Context(abc).method(abc.bodies[0]) != before


def test_private_namespaces_with_the_same_text_have_distinct_identity():
    abc = ABC(abc_tags(fixture_swf())[0][4])
    abc.namespaces = [(0, 0), (5, 0), (5, 0)]
    abc.bodies[0][5] = b"\x60\x01\x29\x47"
    before = Context(abc).method(abc.bodies[0])
    abc.multinames[1] = (7, 2, 1)
    assert Context(abc).method(abc.bodies[0]) != before


def test_newclass_includes_the_referenced_class_declaration():
    abc = ABC(abc_tags(fixture_swf())[0][4])
    abc.bodies[0][5] = b"\x58\x00\x29\x47"
    before = Context(abc).method(abc.bodies[0])
    abc.instances[0][2] ^= 1
    assert Context(abc).method(abc.bodies[0]) != before


def test_explicit_registry_is_not_broadened_by_local_registration():
    from wf.caps.registry import load_registry
    path, _ = profiles.resolve_client(client_profile="local-v35k3")
    provided = profiles.read_client(path)
    registry = load_registry()
    method = registry["client.apk.patch087@1"]["provided_by"]["methods"][0]
    method["sha256"] = "0" * 64
    method["accepted_variants"] = []
    checks = check_compat(required(["client.apk.patch087@1"], clientPatches=[]), provided, registry=registry)
    assert any(row["blocking"] for row in checks)


def test_k3_registered_evidence_is_exact_and_does_not_grant_changed_or_native_methods():
    local = recorded()
    assert local["source"]["sha256"] == "6981c48c42e43ebf6b85e5893cf40357affe4e7a31787e078f0ce28c3cd5f807"
    assert local["source"]["swf_sha256"] == "c52e01b8a536f78a06f48cce07bd3e0f23b3814b9b7f861e02a20755f74cc2c1"
    assert local["package"]["package_name"] == "com.leiting.wf"
    evidence, withheld = registration.verified_evidence(local["observations"])
    assert len(evidence["patches"]) == 101 and len(withheld) == 30
    assert {row["patch"] for row in withheld if row["kind"] == "non_swf_evidence_required"} == {79, 82, 86, 97, 98, 99, 100}
    path, selected = profiles.resolve_client(client_profile="local-v35k3")
    provided = profiles.read_client(path)
    assert selected == "local-v35k3" and len(provided["provides"]) == 123
    assert provided["unresolved"] == []
    assert profiles.load_profiles()[0] == "test-v34"
    ids = {row["id"] for row in provided["provides"]}
    assert "client.equipment.gauge_gain_rules@1" in ids
    assert "client.direct.base@1" not in ids and "client.heal.overflow_damage@1" not in ids
    assert not any(row["blocking"] for row in check_compat(required(["client.equipment.gauge_gain_rules@1"]), provided))
    assert any(row["blocking"] for row in check_compat(required(["client.direct.base@1"]), provided))


def test_withheld_sibling_capability_does_not_make_a_known_table_unregistered():
    from wf.apk.kind_branches import registry_mismatches
    from wf.caps.registry import load_registry
    registry = load_registry()
    r3 = "client.equipment.gauge_gain_rules@1"
    tables = {table: {"during_content": {"kinds": ["423"]}} for table in
              ("ability", "ability_soul", "equipment_enhancement_ability")}
    assert registry_mismatches(tables, registry, {r3}) == []
    tables["leader_ability"] = {"during_content": {"kinds": ["423"]}}
    mismatch = registry_mismatches(tables, registry, {r3})
    assert mismatch[0]["unregistered_tables"] == ["leader_ability"]
    del tables["ability_soul"]
    assert registry_mismatches(tables, registry, {r3})[0]["missing_branches"] == ["ability_soul"]


def test_legacy_gate_requires_registered_pair_and_proven_method_capability():
    import wfx_gate
    import wfx_registry
    from wf.wfx_semantics import candidate_profile_problems
    assert "ability-visuals-v1" in wfx_gate.load_profiles()["local-v35k3"].capabilities
    entry = deepcopy(profiles.load_profiles()[1]["local-v35k3"])
    catalog = wfx_registry.capabilities()
    assert candidate_profile_problems(entry, ["ability-visuals-v1"], catalog) == []
    assert candidate_profile_problems(entry, ["direct-base-v1"], catalog)
    entry["evidence"]["apk_sha256"] = "0" * 64
    assert candidate_profile_problems(entry, ["ability-visuals-v1"], catalog)


def test_legacy_cache_token_changes_when_trusted_evidence_changes(tmp_path):
    from wf.wfx_semantics import _evidence_token
    filenames = ["wf/caps/demo.yml", "wf/apk/data/v34-evidence.json",
                 "wf/apk/data/v35e-evidence.json", "wf/apk/data/v35e-method-contexts.json",
                 "schemas/capability.schema.json"]
    for name in filenames:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("initial", encoding="utf-8")
    previous = _evidence_token(tmp_path)
    for name in filenames:
        (tmp_path / name).write_text("changed", encoding="utf-8")
        current = _evidence_token(tmp_path)
        assert current != previous
        previous = current


def test_legacy_cache_does_not_skip_provides_digest_checks():
    import wfx_registry
    from wf.wfx_semantics import candidate_profile_problems
    entry = deepcopy(profiles.load_profiles()[1]["local-v35k3"])
    catalog = wfx_registry.capabilities()
    assert candidate_profile_problems(entry, ["ability-visuals-v1"], catalog) == []
    entry["provides_sha256"] = "0" * 64
    assert candidate_profile_problems(entry, ["ability-visuals-v1"], catalog)


def test_same_swf_in_a_different_registered_apk_uses_the_exact_pair(tmp_path, monkeypatch):
    import wfx_registry
    from wf.wfx_semantics import candidate_profile_problems
    original = recorded()
    repack = deepcopy(original)
    repack["profile_id"] = "local-v35-repack"
    repack["source"]["sha256"] = "c" * 64
    monkeypatch.setattr(local_registry, "registrations", lambda: iter([original, repack]))
    assert local_registry.find(original["source"]["swf_sha256"], apk_sha256="c" * 64) == repack
    entry = deepcopy(original["profile"])
    entry["evidence"]["apk_sha256"] = "c" * 64
    document = profiles.read_client(REPOSITORY / original["profile"]["provides"])
    document["source"]["sha256"] = "c" * 64
    data = registration.encode(document)
    filename = tmp_path / "repack-provides.json"
    filename.write_bytes(data)
    entry.update(provides=str(filename), provides_sha256=digest(data))
    assert candidate_profile_problems(entry, ["ability-visuals-v1"], wfx_registry.capabilities()) == []


@pytest.mark.parametrize("fault", ["hash", "context", "missing", "duplicate"])
def test_registration_proof_tampering_does_not_authorize_a_patch(fault):
    record = recorded()
    row = next(m for m in record["observations"] if m["label"] == "AbilitySoulValues$/parseAt106")
    if fault == "hash":
        row["sha256"] = "0" * 64
    elif fault == "context":
        row["context_sha256"] = "0" * 64
    elif fault == "missing":
        record["observations"].remove(row)
    else:
        record["observations"].append(deepcopy(row))
    if fault in {"missing", "duplicate"}:
        with pytest.raises(ValueError, match="exactly once"):
            registration.verified_evidence(record["observations"])
    else:
        evidence, _ = registration.verified_evidence(record["observations"])
        assert not evidence["method_capabilities"]


@pytest.fixture
def local_checkout(tmp_path, monkeypatch):
    reference = registration.reference()
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    for filename in ("client_profiles.json", "wfx_registry.json"):
        (checkout / filename).write_bytes((REPOSITORY / filename).read_bytes())
    monkeypatch.setattr(registration, "REPOSITORY", checkout)
    monkeypatch.setattr(local_registry, "REPOSITORY", checkout)
    monkeypatch.setattr(profiles, "REPOSITORY", checkout)
    monkeypatch.setattr(registration, "reference", lambda: deepcopy(reference))
    record = recorded()
    record["source"].update(sha256="a" * 64, swf_sha256="b" * 64, path=str(checkout / "v35next-local.apk"))
    monkeypatch.setattr(registration, "inspect_local", lambda path: deepcopy(record))
    return checkout, record


def test_registration_is_local_discoverable_idempotent_and_refuses_profile_collision(local_checkout):
    checkout, record = local_checkout
    result = registration.register_local("v35next-local.apk")
    assert result["ok"] and result["status"] == "registered"
    path, name = profiles.resolve_client(client_profile="local-v35next")
    assert path.is_relative_to(checkout) and name == "local-v35next"
    assert profiles.read_client(path)["source"]["sha256"] == "a" * 64
    before = {p: p.read_bytes() for p in checkout.rglob("*.json")}
    assert registration.register_local("v35next-local.apk")["status"] == "already_registered"
    assert before == {p: p.read_bytes() for p in checkout.rglob("*.json")}
    record["source"]["sha256"] = "c" * 64
    with pytest.raises(ValueError, match="another APK"):
        registration.register_local("v35next-local.apk")
    with pytest.raises(ValueError, match="must match"):
        registration.register_local("v35next-local.apk", profile="../escape")


def test_failed_write_does_not_leave_a_half_registered_client(local_checkout, monkeypatch):
    checkout, _ = local_checkout
    original = Path.write_bytes
    def fail_registration(path, data):
        if path.name == "registration.json":
            raise OSError("simulated disk failure")
        return original(path, data)
    monkeypatch.setattr(Path, "write_bytes", fail_registration)
    with pytest.raises(OSError, match="disk failure"):
        registration.register_local("v35next-local.apk")
    assert "local-v35next" not in profiles.load_profiles()[1]
    assert not (checkout / "work/local-clients/local-v35next").exists()
