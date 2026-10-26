"""Exercise the real delivery and HTTP/CLI contracts for weapon-set candidates."""
import json
import zipfile

import pytest
import wf_quest_lib as codec

from test_boss_shop_weapon import state  # noqa: F401
from test_studio_weapon_routes import app, call, clone, live, _request, headers  # noqa: F401
from test_studio_weapon_set import workshop, full_set  # noqa: F401
from wf.boss.shop_model import ENH_SHOP
from wf.deliver.changeset import member_name
from wf.studio.deliver_bridge import build_draft
from wf.studio.draft import build_parser
from wf.studio.weapon_cli import run_weapon
from wf.studio.weapon_editor import WeaponEditor
from wf.studio.weapon_store import WeaponDraftStore
from wf.studio.source import StudioSource
from wf.view import ManifestView


@pytest.mark.parametrize("awakening", [False, True])
def test_weapon_set_real_delivery_requires_and_shared_table_gates(workshop, tmp_path, monkeypatch, awakening):
    files = workshop.source.view.files
    for name in ("ability", "leader_ability"):
        files[f"master/ability/{name}.orderedmap"] = codec.build_node({})
    archive = tmp_path / "pinball-1.4.131-1.4.132-1-fixture.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for logical, raw in files.items():
            output.writestr(member_name("common", logical), raw)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cdn_version": "1.4.132", "patches": [{"version": "1.4.132",
        "depends_on": "1.4.131", "chain": [archive.name], "type": "patch"}]}), encoding="utf-8")
    store = tmp_path / "store"
    store.mkdir()
    view = ManifestView("1.4.132", store=store, manifest=manifest, search_dirs=[tmp_path])
    source = StudioSource(view, official_root=tmp_path / "no-official")
    drafts = WeaponDraftStore(tmp_path / "drafts-set")
    editor = WeaponEditor(source, store=drafts, server_dir=workshop.weapons.server_dir)
    wid = editor.apply("weapon_clone", {"sourceWeapon": "5010005"})["weaponId"]
    spec = full_set()
    if not awakening:
        spec.pop("awakeningMaterial")
    editor.apply("weapon_set", {"id": wid, **spec}, wid=wid)
    drafts.save(wid)
    provides = tmp_path / "provides.json"
    provides.write_text(json.dumps({"schema": "wf-apk-provides/1", "source": {
        "kind": "swf", "basis": "synthetic branches", "swf_sha256": "a" * 64},
        "patches": [], "provides": [], "unresolved": [], "limitations": []}), encoding="utf-8")
    monkeypatch.setattr("wf.apk.kinds.inspect_provides", lambda *a, **kw: {
        "source": {"swf_sha256": "a" * 64}, "mismatches": [], "tables": {
        name: {"instant_content": {"kinds": ["32", "34"]}}
        for name in ("ability_soul", "equipment_enhancement_ability")}})
    pathlist = tmp_path / "paths.txt"
    pathlist.write_text("\n".join(files), encoding="utf-8")
    result = build_draft(wid, from_version="1.4.132", to_version="1.4.133", out=tmp_path / "delivery-set",
        baseline_view=view, store=drafts, provides=provides, server_dir=workshop.weapons.server_dir, pathlist=pathlist)
    delivery = tmp_path / "delivery-set/delivery"
    requirements = json.loads((delivery / "requires.json").read_bytes())["requires"]
    assert "equipment_enhancement_shop.per_level" in requirements["serverFeatures"]
    assert "equipment_dissolve.generate_ability_soul" in requirements["serverFeatures"]
    if awakening:
        assert not result["ok"]
        assert "equipment-awakening-material-v1" in requirements["clientCapabilities"]
        assert any(c.get("blocking") for c in result["compatChecks"])
    else:
        assert result["ok"], result
    assert result["keyDiff"]["status"] != "blocked"
    assert result["prepush"]["exit_code"] == 0
    packed = {}
    for filename in delivery.glob("pinball-*.zip"):
        with zipfile.ZipFile(filename) as archive:
            packed.update({name: archive.read(name) for name in archive.namelist()})
    stages = codec.parse_node(packed[member_name("common", ENH_SHOP)])
    assert all(str(int(wid) * 100 + index) in stages for index in range(1, 10))


def test_weapon_set_cli_uses_same_preview_and_options(workshop, tmp_path):
    parser = build_parser()
    choices = run_weapon(parser.parse_args(["weapon", "set-options", "--server-dir", str(workshop.weapons.server_dir)]),
                         workshop.source, workshop.ops.store)
    assert any(item["name"] == "测试星铁" for item in choices["materials"])
    wid = clone(workshop)["weaponId"]
    spec = tmp_path / "request.json"
    spec.write_text(json.dumps(full_set(), ensure_ascii=False), encoding="utf-8")
    args = parser.parse_args(["weapon", "set", wid, "--request", str(spec), "--preview",
                              "--server-dir", str(workshop.weapons.server_dir)])
    before = workshop.weapons.store.load(wid)
    result = run_weapon(args, workshop.source, workshop.ops.store)
    assert result["rows"]["client"] and result["rows"]["server"]
    assert workshop.weapons.store.load(wid) == before


def test_weapon_set_http_guards(live):
    port, guard, app = live
    code, _ = _request(port, "POST", "/api/studio/weapons/5010005/set", {"noSoul": True},
                       headers(guard, Origin="https://evil.invalid"))
    assert code == 403
    code, _ = _request(port, "GET", "/api/studio/weapons/set-options", headers=headers(guard, Host="evil.invalid"))
    assert code == 403
