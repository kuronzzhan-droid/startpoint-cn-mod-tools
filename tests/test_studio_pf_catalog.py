"""Synthetic CDN/APK PF catalog fixtures; no official programs are embedded."""
import io
from pathlib import Path
import zipfile

import pytest
import wf_mod_tool as core
from wf.studio import bundle_keys, delivery_inputs
from wf.studio.bundle_index import bundled_logical
from wf.studio.clone_tables import leaf
from wf.studio.deliver_media import encode_tree
from wf.studio.drafts import DraftError
from wf.studio.pf_catalog import DSL_SUFFIX, PF_TABLE, PfCatalog


class Source:
    version = "1.4.1"

    def __init__(self, files=None):
        self.files = files or {}

    def raw(self, logical):
        return self.files.get(("common", logical))

    def read_root(self, root, logical):
        return self.files.get((root, logical))


def action(multiplier=2):
    attack = ["Command", ["CreateNormalAttack", -18, 255, [], [], 0,
                           [{"min": multiplier, "max": multiplier}],
                           [{"min": 0, "max": 0}], False, False, False, False, False,
                           [{"min": 1, "max": 1}], [{"min": 1, "max": 1}], ["Fine"], True]]
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False,
            0, ["Block", [attack, ["Command", ["NotifyPowerflipEnd", 1]]]]]


def paths(key="special"):
    return [f"battle/action/power_flip/action/{key}${key}_lv{n}" for n in (1, 2, 3)]


def table(rows):
    return core.build_orderedmap_raw_rows(core.OrderedMap(PF_TABLE, list(rows),
        [leaf([row]) for row in rows.values()], Path("fixture")))


def source(key="special"):
    files = {("common", PF_TABLE): table({key: paths(key)})}
    files.update({("common", path + DSL_SUFFIX): encode_tree(action(n))
                  for n, path in enumerate(paths(key), 1)})
    return Source(files)


def archive(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as package:
        for name, raw in entries:
            package.writestr(name, raw)
    return output.getvalue()


def apk(directory, key="knight", *, name="client.apk", row=None, multiplier=2, programs=True):
    row = paths(key) if row is None else row
    files = {bundled_logical(PF_TABLE): table({key: row})}
    if programs:
        files.update({path + DSL_SUFFIX: encode_tree(action(multiplier)) for path in row})
    entries = []
    for logical, raw in files.items():
        hashed = core.sha1_path(logical)
        entries.append(("production/android_bundle/" + hashed[:2] + "/" + hashed[2:], raw))
    target = directory / name
    target.write_bytes(archive([("assets/bundle.zip", archive(entries))]))
    return target


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(bundle_keys, "REPOSITORY", tmp_path / "repository")
    monkeypatch.setattr(delivery_inputs, "configured_path", lambda _: tmp_path / "no-pathlist")
    return tmp_path / "cache"


def test_cdn_catalog_resolves_three_programs_and_records_inputs():
    catalog = PfCatalog(source(), apks=[])
    resolved = catalog.resolve("special")
    assert resolved["row"] == paths()
    assert resolved["trees"] == [action(n) for n in (1, 2, 3)]
    assert len(resolved["inputs"]) == 4
    listing = catalog.list("SPECIAL")
    assert listing["bundledAvailable"] is False
    assert "只能" in listing["warnings"][0]
    assert listing["items"][0]["key"] == "special"
    assert len(listing["items"][0]["levels"]) == 3
    assert catalog.list("absent")["items"] == []


def test_bundled_rows_and_actual_dsl_bytes(tmp_path, cache):
    catalog = PfCatalog(source(), apks=[apk(tmp_path)], cache_dir=cache)
    assert catalog.keys == {"special", "knight"}
    result = catalog.resolve("knight")
    assert result["source"] == "bundled"
    assert result["trees"] == [action()] * 3
    assert any(key.startswith("bundled:") for key in result["inputs"])
    assert catalog.detail("knight")["type"] == "knight"
    assert catalog.list()["bundledAvailable"] is True


def test_bundled_row_can_reference_dsl_from_current_view(tmp_path, cache):
    view = source("fighter")
    del view.files[("common", PF_TABLE)]
    catalog = PfCatalog(view, apks=[apk(tmp_path, "fighter", programs=False)], cache_dir=cache)
    assert catalog.resolve("fighter")["trees"] == [action(n) for n in (1, 2, 3)]


def test_view_bytes_override_bundled_dsl_and_preserve_root_identity(tmp_path, cache):
    view = Source({("common", path + DSL_SUFFIX): encode_tree(action(9)) for path in paths("knight")})
    catalog = PfCatalog(view, apks=[apk(tmp_path)], cache_dir=cache)
    assert catalog.resolve("knight")["trees"] == [action(9)] * 3
    assert catalog.read(paths("knight")[0] + DSL_SUFFIX, root="medium") is None


@pytest.mark.parametrize("kind", ["missing", "corrupt"])
def test_configured_bad_apk_is_error_not_cdn_only(tmp_path, cache, kind):
    filename = tmp_path / "bad.apk"
    if kind == "corrupt":
        filename.write_bytes(b"not an APK")
    with pytest.raises(DraftError, match="目标 APK"):
        PfCatalog(source(), apks=[filename], cache_dir=cache)


def test_client_profile_resolves_configured_apks(tmp_path, cache, monkeypatch):
    import wf.paths
    filename = apk(tmp_path)
    monkeypatch.setattr(wf.paths, "profile_data", lambda: ({"client_apks": {"target": [str(filename)]}}, None))
    assert "knight" in PfCatalog(source(), client_profile="target", cache_dir=cache).keys


@pytest.mark.parametrize("default", ["test-v34", "another-target"])
def test_omitted_client_profile_uses_default_profile(tmp_path, cache, monkeypatch, default):
    import wf.paths
    monkeypatch.setattr("wf.studio.pf_catalog.load_profiles", lambda: (default, {}))
    filename = apk(tmp_path)
    monkeypatch.setattr(wf.paths, "profile_data", lambda: (
        {"client_apks": {default: [str(filename)]}}, None))
    assert "knight" in PfCatalog(source(), cache_dir=cache).keys


def test_one_apk_cannot_supply_missing_resource_for_another(tmp_path, cache):
    selected = [apk(tmp_path), apk(tmp_path, name="second.apk", programs=False)]
    catalog = PfCatalog(Source(), apks=selected, cache_dir=cache)
    assert catalog.list()["items"][0]["selectable"] is False
    with pytest.raises(DraftError, match="部分目标 APK 缺少"):
        catalog.resolve("knight")


def test_view_resources_can_supply_all_selected_apks(tmp_path, cache):
    selected = [apk(tmp_path), apk(tmp_path, name="second.apk", programs=False)]
    view = Source({("common", path + DSL_SUFFIX): encode_tree(action(9)) for path in paths("knight")})
    assert PfCatalog(view, apks=selected, cache_dir=cache).resolve("knight")["trees"] == [action(9)] * 3


def test_conflicting_target_rows_are_present_but_not_selectable(tmp_path, cache):
    first = apk(tmp_path)
    second = apk(tmp_path, name="second.apk", row=paths("other"))
    catalog = PfCatalog(Source(), apks=[first, second], cache_dir=cache)
    assert "knight" in catalog.keys
    assert catalog.list()["items"][0]["selectable"] is False
    with pytest.raises(DraftError, match="三档行不一致"):
        catalog.resolve("knight")


def test_conflicting_target_dsl_contents_block_selection(tmp_path, cache):
    first = apk(tmp_path)
    second = apk(tmp_path, name="second.apk", multiplier=7)
    catalog = PfCatalog(Source(), apks=[first, second], cache_dir=cache)
    assert catalog.list()["items"][0]["selectable"] is False
    with pytest.raises(DraftError, match="资源内容不一致"):
        catalog.resolve("knight")


def test_cdn_bundled_key_overlap_is_not_a_valid_donor(tmp_path, cache):
    catalog = PfCatalog(source("knight"), apks=[apk(tmp_path)], cache_dir=cache)
    with pytest.raises(DraftError, match="同时存在"):
        catalog.resolve("knight")


def test_missing_and_malformed_levels_do_not_disappear():
    view = source()
    del view.files[("common", paths()[2] + DSL_SUFFIX)]
    listing = PfCatalog(view, apks=[]).list()
    assert listing["items"][0]["selectable"] is False
    assert "缺少" in listing["items"][0]["error"]
    view.files[("common", PF_TABLE)] = table({"special": paths()[:2]})
    with pytest.raises(DraftError, match="三档行无效"):
        PfCatalog(view, apks=[]).resolve("special")


def test_replayed_inputs_are_stable(tmp_path, cache):
    selected = [apk(tmp_path)]
    first = PfCatalog(source(), apks=selected, cache_dir=cache).resolve("knight")
    second = PfCatalog(source(), apks=selected, cache_dir=cache).resolve("knight")
    assert first["inputs"] == second["inputs"]


@pytest.mark.parametrize("raw", [b"bad deflate", encode_tree(None), encode_tree(["ActionDsl"])])
def test_malformed_dsl_is_a_public_input_error(raw):
    view = source()
    view.files[("common", paths()[0] + DSL_SUFFIX)] = raw
    catalog = PfCatalog(view, apks=[])
    detail = catalog.detail("special")
    assert detail["selectable"] is False
    assert "母本 DSL 无效" in detail["error"]
    assert catalog.list()["items"][0]["selectable"] is False


def test_malformed_cdn_table_is_a_public_input_error():
    with pytest.raises(DraftError, match="母本表无效"):
        PfCatalog(Source({("common", PF_TABLE): b"bad orderedmap"}), apks=[])


def test_source_read_errors_are_public_input_errors(monkeypatch):
    view = source()

    def broken(*args):
        raise OSError("source unavailable")

    monkeypatch.setattr(view, "raw", broken)
    with pytest.raises(DraftError, match="当前视图表读取失败"):
        PfCatalog(view, apks=[])
    view = source()
    catalog = PfCatalog(view, apks=[])
    monkeypatch.setattr(view, "read_root", broken)
    with pytest.raises(DraftError, match="当前视图资源读取失败"):
        catalog.resolve("special")
