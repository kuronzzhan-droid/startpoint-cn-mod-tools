# -*- coding: utf-8 -*-
"""深渊武器二期 9 把图标：RetroDiffusion rd_pro__default 20×20，参考现有深渊图标（lv0 / lv120 各两张）。

用法：python gen_icons.py [slug ...] [--lv 0|120|both] [--n 2] [--tag x]
候选写到 ../art/cand/<slug>_lv<lv>_<tag><i>.png；挑选后拷到 ../art/final/<slug>.png / <slug>_lv120.png。
"""
import argparse
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ART = HERE.parent / "art"
sys.path.insert(0, str(HERE.parent.parent / "icons"))
import rd  # noqa: E402

REF = ART / "ref"
STYLE0 = ("20x20 pixel art RPG weapon item icon, dark navy outline, glossy highlights, small colored sparkle pixels around, "
          "transparent background, diagonal composition, ")
STYLE120 = ("20x20 pixel art RPG weapon item icon, awakened upgraded version, brighter glowing colors, gold trim, "
            "white star sparkles around, transparent background, diagonal composition, ")
SUBJECT = {
    "light_03": "a white dove feather quill with golden light glow",
    "dark_03": "a bubble tea cup with black tapioca pearls and purple taro milk, straw, dark purple aura",
    "dark_04": "a crimson blood moon crescent orb with dark red aura",
    "thunder_03": "a green onion leek shaped like a microphone with yellow lightning sparks",
    "wind_03": "a carrot shaped sword with green leaf hilt and wind swirl",
    "wind_04": "a surfboard with teal green wave pattern",
    "fire_03": "a beach volleyball with red orange stripes and flames",
    "fire_04": "a red motorcycle helmet with flame decals",
    "water_03": "a ship wooden plank board with blue waves and rope",
}


REFS = {}


def refs(lv: str) -> list[Image.Image]:
    names = REFS.get(lv, ("fire_01", "wind_02"))
    if lv == "120":
        names = tuple(n + "_lv120" for n in names)
    return [Image.open(REF / f"item_equipment_mod_abyss_{n}.png").convert("RGBA") for n in names]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*")
    ap.add_argument("--lv", default="both")
    ap.add_argument("--n", type=int, default=2)
    ap.add_argument("--tag", default="a")
    ap.add_argument("--extra", default="")
    ap.add_argument("--refs", default="")
    a = ap.parse_args()
    if a.refs:
        REFS["0"] = REFS["120"] = tuple(a.refs.split(","))
    out = ART / "cand"
    out.mkdir(parents=True, exist_ok=True)
    for slug in a.slugs or list(SUBJECT):
        for lv in (("0", "120") if a.lv == "both" else (a.lv,)):
            prompt = (STYLE0 if lv == "0" else STYLE120) + SUBJECT[slug] + a.extra
            imgs = rd.generate(prompt, 20, 20, refs=refs(lv), n=a.n)
            for i, im in enumerate(imgs):
                p = out / f"{slug}_lv{lv}_{a.tag}{i}.png"
                im.save(p)
                print(p.name, im.size, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
