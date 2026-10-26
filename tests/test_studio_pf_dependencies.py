"""Synthetic PF dependency closure checks; no official assets are committed."""
import pytest
import zlib

import wf_character_requirements as requirements
from wf.studio.deliver_media import encode_tree
from wf.studio.drafts import DraftError
from wf.studio.pf_dependencies import prepare_dependencies


class Catalog:
    def __init__(self, files):
        self.files = files
        self.reads = []

    def read(self, logical, root="common"):
        self.reads.append((root, logical))
        return self.files.get((root, logical))


def family(path, *, sounds=()):
    ref = requirements.MasterAssetReference("skill_effect", path, "fixture")
    paths = requirements.required_asset_paths(ref)
    cell = path.rsplit("/", 1)[0] + "/.gen/fixture/a"
    files = dict(zip(paths, (encode_tree({"i": [{"p": cell}]}),
                 encode_tree({"sounds": [{"path": item} for item in sounds]}),
                 b"synthetic-stored-image", encode_tree([{"n": cell}]))))
    return {("common", key): raw for key, raw in files.items()}


FX = "battle/effect/skill_unique/demo/private/burst"


def test_pf_dependencies_effect_sound_optional_atf_and_dsl():
    sound = "sound_effect/fixture/burst"
    files = family(FX, sounds=[sound])
    files["common", sound + ".mp3"] = b"fixture-sound"
    texture = "battle/effect/skill_unique/demo/private/private.atf.deflate"
    files["android", texture] = b"fixture-atf"
    catalog = Catalog(files)
    original = dict(files)
    program = "battle/action/power_flip/action/custom$child"
    dependencies, checks = prepare_dependencies(catalog, [
        ["SpecifyEffectDirectly", FX], ["InvokeSkill", program]], 5)
    assert len(dependencies) == 7
    assert all(item["sha256"] for item in dependencies if item["status"] == "existing")
    assert next(item for item in dependencies if item["kind"] == "dsl")["status"] == "compiled_reference"
    assert ("common", program + ".action.dsl.amf3.deflate") not in catalog.reads
    assert catalog.files == original
    assert all(check["level"] == "info" for check in checks)


@pytest.mark.parametrize("slot", range(4))
def test_pf_dependencies_reject_missing_family_member(slot):
    files = family(FX)
    del files[list(files)[slot]]
    with pytest.raises(DraftError, match="预载依赖缺失"):
        prepare_dependencies(Catalog(files), [["SpecifyEffectDirectly", FX]], 2)


def test_pf_dependencies_resolve_context_checks_all_colours():
    base = "battle/effect/hit/fixture"
    files = {}
    for element in range(7):
        files.update(family(requirements.resolve_effect_by_element(base, element)))
    dependencies, checks = prepare_dependencies(Catalog(files), [["ResolveByElement", base, 255]], 5)
    assert len(dependencies) == 28
    assert all(base + "." not in item["logical"] for item in dependencies)
    assert any(check["code"] == "pf.preload.element-context" for check in checks)
    del files[next(key for key in files if "fixture_red" in key[1])]
    with pytest.raises(DraftError, match="fixture_red"):
        prepare_dependencies(Catalog(files), [["ResolveByElement", base, 255]], 5)


def test_pf_dependencies_explicit_colour_ignores_attack_element():
    base = "battle/effect/hit/fixture"
    expected = requirements.resolve_effect_by_element(base, 0)
    dependencies, _ = prepare_dependencies(Catalog(family(expected)), [["ResolveByElement", base, 1]], 5)
    assert len(dependencies) == 4
    assert all("fixture_red" in item["logical"] for item in dependencies)


def test_pf_dependencies_end_animation_and_atlas_closure():
    files = family(FX) | family(FX + "_end")
    dependencies, _ = prepare_dependencies(Catalog(files), [["SpecifyEffectDirectly", FX]], 0)
    assert len(dependencies) == 6  # The two animations share their image and atlas.
    atlas = next(key for key in files if key[1].endswith(".atlas.amf3.deflate"))
    files[atlas] = encode_tree([])
    with pytest.raises(DraftError, match="parts 引用不在目录 atlas"):
        prepare_dependencies(Catalog(files), [["SpecifyEffectDirectly", FX]], 0)


def test_pf_dependencies_reject_missing_sound_and_bad_selector():
    with pytest.raises(DraftError, match="sound_effect/fixture/missing.mp3"):
        prepare_dependencies(Catalog(family(FX, sounds=["sound_effect/fixture/missing"])),
                             [["SpecifyEffectDirectly", FX]], 5)
    with pytest.raises(DraftError, match="合法路径和元素码"):
        prepare_dependencies(Catalog({}), [["ResolveByElement", FX, True]], 5)
    assert prepare_dependencies(Catalog({}), [[], [], []], 0)[0] == []


@pytest.mark.parametrize("malformed", [b"\xff", b"truncated-double"])
def test_pf_dependencies_decode_errors_are_actionable(malformed):
    files = family(FX)
    if malformed == b"truncated-double":
        encoder = zlib.compressobj(wbits=-15)
        malformed = encoder.compress(b"\x05\x00") + encoder.flush()
    files["common", FX + ".parts.amf3.deflate"] = malformed
    with pytest.raises(DraftError, match="元数据无法解码"):
        prepare_dependencies(Catalog(files), [["SpecifyEffectDirectly", FX]], 5)
