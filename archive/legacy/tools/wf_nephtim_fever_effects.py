"""克隆奈芙提姆光/暗原生特效到本角色私有路径。"""
from io import BytesIO
from pathlib import Path
import zlib

from PIL import Image

import wf_dsl
from wf_assets import png_encode
from wf_character_revision import encode_tree
from wf_nephtim_fever_powerflip import with_bundle_fallback
from wf_nephtim_fever_skill import BALL_FX, CODE, LIGHT_FADE_FX, SKILL_FX, STATE_ICON

ICON_PATH = Path(__file__).resolve().parent / "assets/nephtim-fever-icons/starry-tea.png"


def _native_reader(read, bundle_path):
    """仅当 CDN 缺资源时，读取本仓库主目录的原生 bundle。"""
    fallback = None

    def load(path):
        nonlocal fallback
        if fallback is not None:
            return fallback(path)
        try:
            raw = read(path)
        except FileNotFoundError:
            raw = None
        if raw is not None:
            return raw
        source = Path(bundle_path) if bundle_path is not None else next(
            (parent / "弹国服/bundle.zip" for parent in Path(__file__).resolve().parents
             if (parent / "弹国服/bundle.zip").is_file()), None)
        if source is None:
            raise FileNotFoundError(f"missing official asset and local bundle: {path}")
        fallback = with_bundle_fallback(read, source)
        return fallback(path)

    return load


def _remap(value, substitutions):
    if isinstance(value, str):
        for old, new in substitutions:
            value = value.replace(old, new)
        return value
    if isinstance(value, list):
        return [_remap(item, substitutions) for item in value]
    if isinstance(value, dict):
        return {_remap(key, substitutions): _remap(item, substitutions)
                for key, item in value.items()}
    return value


def _clone(read, source_dir, old_sheet, target_dir, new_sheet, names):
    replacements = [(source_dir + old, target_dir + new) for old, new in names]
    replacements += [(source_dir, target_dir), (old_sheet, new_sheet)]
    files = {}
    paths = [(old_sheet + suffix, new_sheet + suffix)
             for suffix in (".png", ".atlas.amf3.deflate")]
    paths += [(old + suffix, new + suffix) for old, new in names
              for suffix in (".parts.amf3.deflate", ".timeline.amf3.deflate")]
    for old, new in paths:
        raw = read(source_dir + old)
        if not isinstance(raw, bytes):
            raise ValueError(f"missing native effect asset: {source_dir + old}")
        if old.endswith(".amf3.deflate"):
            tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
            raw = encode_tree(_remap(tree, replacements))
        files["common", target_dir + new] = raw
    return files


def assets(read, *, bundle_path=None):
    read = _native_reader(read, bundle_path)
    files = {}
    half = "ruin_girl_halfanv"
    half_new = CODE + "_fever"
    files.update(_clone(read, "battle/effect/skill_unique/" + half + "/", half,
        SKILL_FX, half_new, [(half + suffix, half_new + suffix)
                            for suffix in ("_all", "_1blue", "_2yellow")]))
    for kind, old_sheet, old_base in (("light", "ruin_girl", "multiball_ruin_girl_effect"),
                                      ("dark", "ruin_girl_3halfanv", "ruin_girl_3halfanv_multiball")):
        new_sheet = CODE + "_" + kind + "_call"
        suffixes = ["_ready_generation", "_ready_left", "_ready_right", "_appear"]
        if kind == "dark":
            suffixes.append("_disappear")
        files.update(_clone(read, "battle/effect/skill_unique/" + old_sheet + "/", old_sheet,
            BALL_FX[kind], new_sheet, [(old_base + suffix, new_sheet + suffix) for suffix in suffixes]))
    general = "multiball_general_effect"
    fade_dir, fade_name = LIGHT_FADE_FX.rsplit("/", 1)
    files.update(_clone(read, "battle/effect/skill_general/multiball/" + general + "/", general,
        fade_dir + "/", CODE + "_light_fade", [(general + "_disappear", fade_name)]))
    raw = ICON_PATH.read_bytes()
    with Image.open(BytesIO(raw)) as icon:
        if icon.size != (48, 48) or icon.mode != "RGBA" or icon.getextrema()[3] != (0, 255):
            raise ValueError("starry tea icon must be 48x48 RGBA with real alpha")
    files["common", STATE_ICON + ".png"] = png_encode(raw)
    return files
