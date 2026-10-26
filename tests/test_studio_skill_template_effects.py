"""Synthetic native families: no official imagery or machine-specific inputs."""
import copy
import io

from PIL import Image
import pytest

import wf_assets
import wf_atf
from wf.studio.deliver_media import encode_png, encode_tree, png, tree
from wf.studio.drafts import DraftError
from wf.studio.skill_template_effects import clone_effects, color_transform


FAMILY = "battle/effect/skill_unique/donor"
EFFECT = FAMILY + "/beam"


class Source:
    def __init__(self, members):
        self.members = members

    def read_root(self, root, logical):
        return self.members.get((root, logical))


def fixture(directory=FAMILY, name="beam", *, frame=False, atf=False):
    base = directory + "/" + name
    sheet = directory + "/" + directory.rsplit("/", 1)[-1]
    image = Image.new("RGBA", (4, 4), (255, 0, 0, 128))
    image.putpixel((0, 0), (8, 19, 29, 0))
    texture = directory + f"/.gen/{name}/0"
    atlas = [{"n": texture, "x": 0, "y": 0, "w": 4, "h": 4,
              "r": True, "fx": -2, "fy": -3}]
    parts = {"i": [{"p": texture, "s": False}], "m": [], "a": [1], "o": [],
             "g": [{"t": 3, "s": [{"s": 0, "i": 0, "l": [{"m": 255, "t": 3}]}]}],
             "t": [{"a": 4096, "b": 0, "c": 0, "d": 4096, "x": 0, "y": 0}], "c": [], "s": 1}
    timeline = {"sequences": [{"begin": 1, "end": 3, "kind": "once", "name": "neutral"}],
                "sounds": [], "points": [], "rectangles": [], "circles": [], "matrices": []}
    members = {("common", sheet + ".png"): encode_png(image),
               ("common", sheet + ".atlas.amf3.deflate"): encode_tree(atlas),
               ("common", base + ".timeline.amf3.deflate"): encode_tree(timeline)}
    if frame:
        members["common", base + ".frame.amf3.deflate"] = encode_tree({"name": directory + f"/.gen/{name}", "scale": 1})
    else:
        members["common", base + ".parts.amf3.deflate"] = encode_tree(parts)
    if atf:
        out = io.BytesIO()
        image.save(out, "PNG")
        members["android", sheet + ".atf.deflate"] = wf_atf.deflate(wf_atf.build_cutin_atf(out.getvalue()))
    return members


def cloned(source=None, effects=None, color=None):
    return clone_effects(source or Source(fixture()), effects or [EFFECT], "new_hero", "new_skill", color)


def test_exact_palette_clone_keeps_timing_alpha_geometry_and_inputs():
    source = Source(fixture())
    before = dict(source.members)
    result = cloned(source, color={"pairs": [{"from": "#FF0000", "to": "#00FF00"}]})
    family = result["families"][0]
    target = family["target"]
    assert target.startswith("battle/effect/skill_unique/new_hero/")
    assert result["rewrite_map"][EFFECT] == target + "/beam"
    out = png(result["members"]["common", target + "/" + target.rsplit("/", 1)[-1] + ".png"])
    assert out.getpixel((1, 1)) == (0, 255, 0, 128)
    assert out.getpixel((0, 0)) == (8, 19, 29, 0)
    assert family["changedPixels"] == 15
    atlas_path = target + "/" + target.rsplit("/", 1)[-1] + ".atlas.amf3.deflate"
    atlas = tree(result["members"]["common", atlas_path])
    assert {key: atlas[0][key] for key in ("x", "y", "w", "h", "r", "fx", "fy")} == {
        "x": 0, "y": 0, "w": 4, "h": 4, "r": True, "fx": -2, "fy": -3}
    original = tree(source.members["common", EFFECT + ".parts.amf3.deflate"])
    output = tree(result["members"]["common", target + "/beam.parts.amf3.deflate"])
    assert output["g"] == original["g"] and output["t"] == original["t"]
    assert source.members == before
    assert len(family["resources"]) == 4
    assert result["inputs"] and any(item["sha256"] is None for item in result["snapshots"])


@pytest.mark.parametrize("rgb,expected", [((255, 0, 0), (0, 255, 0)), ((0, 255, 0), (0, 0, 255)),
                                          ((0, 0, 255), (255, 0, 0)), ((255, 255, 255), (255, 255, 255))])
def test_hue_rotation_covers_full_circle_without_touching_white_core(rgb, expected):
    image = Image.new("RGBA", (1, 1), (*rgb, 177))
    assert color_transform({"hueShift": 120})(image).getpixel((0, 0)) == (*expected, 177)


@pytest.mark.parametrize("color", [{"hueShift": True}, {"hueShift": float("nan")}, {"hueShift": 361},
                                    {"pairs": []}, {"pairs": [{"from": "bad", "to": "#FFFFFF"}]},
                                    {"hueShift": 0, "pairs": []}, {"unknown": 1}])
def test_invalid_color_config_is_rejected(color):
    with pytest.raises(DraftError):
        cloned(color=color)


@pytest.mark.parametrize("suffix", [".parts.amf3.deflate", ".timeline.amf3.deflate"])
def test_incomplete_animation_is_a_hard_failure(suffix):
    members = fixture()
    del members["common", EFFECT + suffix]
    with pytest.raises(DraftError, match="缺"):
        cloned(Source(members))


def test_missing_texture_is_rejected_instead_of_omitted():
    members = fixture()
    key = "common", EFFECT + ".parts.amf3.deflate"
    parts = tree(members[key])
    parts["i"][0]["p"] = FAMILY + "/.gen/missing/0"
    members[key] = encode_tree(parts)
    with pytest.raises(DraftError, match="纹理"):
        cloned(Source(members))


def test_frame_animation_document_and_name_are_cloned():
    result = cloned(Source(fixture(frame=True)))
    target = result["rewrite_map"][EFFECT]
    value = tree(result["members"]["common", target + ".frame.amf3.deflate"])
    assert value["name"] == target.rpartition("/")[0] + "/.gen/beam"
    assert len(result["members"]) == 4


def test_unchanged_sound_is_verified_and_not_rewritten_to_missing_target():
    members = fixture()
    key = "common", EFFECT + ".timeline.amf3.deflate"
    timeline = tree(members[key])
    timeline["sounds"] = [{"path": FAMILY + "/beam_sound", "begin": 1}]
    members[key] = encode_tree(timeline)
    sound = "common", FAMILY + "/beam_sound.mp3"
    members[sound] = b"synthetic audio dependency"
    result = cloned(Source(members))
    target = result["rewrite_map"][EFFECT]
    assert tree(result["members"]["common", target + ".timeline.amf3.deflate"])["sounds"] == timeline["sounds"]
    assert f"common:{sound[1]}" in result["inputs"]
    del members[sound]
    with pytest.raises(DraftError, match="依赖缺失"):
        cloned(Source(members))


def test_movieclip_external_effect_dependency_is_cloned_recursively():
    other = "battle/effect/common/child"
    members = fixture() | fixture(other, "spark")
    key = "common", EFFECT + ".parts.amf3.deflate"
    parts = tree(members[key])
    parts["m"] = [{"p": other + "/spark"}]
    members[key] = encode_tree(parts)
    result = cloned(Source(members))
    target = result["rewrite_map"][EFFECT]
    output = tree(result["members"]["common", target + ".parts.amf3.deflate"])
    assert output["m"][0]["p"] == result["rewrite_map"][other + "/spark"]
    assert len(result["families"]) == 2


def test_unresolved_movieclip_is_a_hard_failure():
    members = fixture()
    key = "common", EFFECT + ".parts.amf3.deflate"
    parts = tree(members[key])
    parts["m"] = ["unknown_clip"]
    members[key] = encode_tree(parts)
    with pytest.raises(DraftError, match="MovieClip"):
        cloned(Source(members))


def test_atf_regeneration_preserves_dimensions_and_mips():
    source = Source(fixture(atf=True))
    result = cloned(source, color={"hueShift": 120})
    original = wf_atf.parse_atf(wf_atf.inflate(source.members["android", FAMILY + "/donor.atf.deflate"]))
    outputs = [raw for (root, path), raw in result["members"].items() if root == "android"]
    assert len(outputs) == 1
    out = wf_atf.parse_atf(wf_atf.inflate(outputs[0]))
    assert (out["w"], out["h"], out["mips"]) == (original["w"], original["h"], original["mips"])
    assert out["pairs"] != original["pairs"]


def test_unsupported_atf_cannot_silently_retain_old_colors():
    members = fixture(atf=True)
    members["android", FAMILY + "/donor.atf.deflate"] = wf_atf.deflate(b"unsupported")
    with pytest.raises(DraftError, match="ATF"):
        cloned(Source(members))


def test_no_pixel_changes_preserve_original_atf_bytes():
    source = Source(fixture(atf=True))
    result = cloned(source)
    output = next(raw for (root, _), raw in result["members"].items() if root == "android")
    assert output == source.members["android", FAMILY + "/donor.atf.deflate"]


def test_target_namespace_is_deterministic_and_resists_key_sanitizing_collisions():
    source = Source(fixture())
    first = clone_effects(source, [EFFECT], "new_hero", "new:skill")
    repeated = clone_effects(source, [EFFECT], "new_hero", "new:skill")
    different = clone_effects(source, [EFFECT], "new_hero", "new_skill")
    assert first == repeated
    assert set(first["members"]).isdisjoint(different["members"])


def test_tree_input_finds_effect_without_mutating_it():
    value = {"constructor": "PlayEffect", "params": [EFFECT, 3]}
    before = copy.deepcopy(value)
    assert cloned(effects=value)["rewrite_map"].keys() == {EFFECT}
    assert value == before
