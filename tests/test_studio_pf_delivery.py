"""PF compilation through real manifest delivery and existing shared-table gates."""
import json
from types import SimpleNamespace
import zipfile

import pytest

from wf.deliver.changeset import member_name
from wf.studio import bundle_keys
from wf.studio.deliver_bridge import build_draft
from wf.studio.drafts import DraftStore
from wf.studio.pf_actions import clone
from wf.studio.pf_catalog import PF_TABLE
from wf.studio.source import StudioSource
from wf.view import ManifestView

from test_studio_pf_catalog import apk, source, table


@pytest.mark.parametrize("bundled", [False, True])
def test_pf_real_build_keeps_old_keys_and_registers_ownership(tmp_path, monkeypatch, bundled):
    monkeypatch.setattr(bundle_keys, "REPOSITORY", tmp_path / "synthetic-repository")
    monkeypatch.setattr("wf.studio.delivery_inputs.configured_path", lambda _: tmp_path / "no-pathlist")
    monkeypatch.setattr("wf.paths.profile_data", lambda: ({}, tmp_path / "local.json"))
    donor = source()
    character = [""] * 37
    character[0], character[2], character[3], character[6], character[27] = "hero", "3", "0", "4", "123456"
    donor.files["common", "master/character/character.orderedmap"] = table({"123456": character})
    for name in ("ability", "leader_ability"):
        donor.files["common", f"master/ability/{name}.orderedmap"] = table({"fixture": ["fixture"] + [""] * 125})
    active = tmp_path / "active"
    active.mkdir()
    archive = active / "pinball-1.4.131-1.4.132-1-fixture.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for (root, logical), data in donor.files.items():
            output.writestr(member_name(root, logical), data)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cdn_version": "1.4.132", "patches": [
        {"version": "1.4.132", "depends_on": "1.4.131", "chain": [archive.name], "type": "patch"}]}), "utf-8")
    base_store = tmp_path / "base"
    base_store.mkdir()
    view = ManifestView("1.4.132", store=base_store, manifest=manifest, search_dirs=[])
    current = StudioSource(view)
    drafts = DraftStore(tmp_path / "drafts")
    ops = SimpleNamespace(source=current, store=drafts, character=lambda _: {"code": "hero"})
    apks = [apk(tmp_path)] if bundled else []
    cache = tmp_path / "cache"
    clone(ops, "123456", {"key": "new_dark_pf", "source": "knight" if bundled else "special",
                           "element": "暗", "scale": [1, 2, 3]}, apks=apks, cache_dir=cache)
    result = build_draft("123456", from_version="1.4.132", to_version="1.4.133",
                         out=tmp_path / "output", store=drafts, baseline_view=view,
                         allow_unknown_client=True, apk=apks, bundle_cache_dir=cache)
    assert result["ok"], result
    assert result["bundleCheck"]["status"] == ("ok" if bundled else "skipped")
    assert result["keyDiff"]["status"] == "ok"
    changes = next(t for t in result["keyDiff"]["tables"] if t["logical"] == PF_TABLE)
    assert changes["added"] == changes["owned"] == ["new_dark_pf"]
    assert changes["removed"] == changes["changed"] == changes["foreign"] == []
    assert result["deviceValidation"] == "未执行"
    assert (tmp_path / "output/delivery/key-diff.md").is_file()
    assert (tmp_path / "output/delivery/bundle-check.json").is_file()
