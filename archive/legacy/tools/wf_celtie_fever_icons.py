"""装载快门库存与星风心得的独立图标，并编码为客户端存储态 PNG。"""
from io import BytesIO
from pathlib import Path

from PIL import Image

from wf_assets import png_encode

ICON_PATH = Path(__file__).resolve().parent / "assets/celtie-fever-icons/starwind-shutter.png"
GAIN_ICON_PATH = ICON_PATH.with_name("starwind-insight.png")


def _icon_bytes(path):
    raw = path.read_bytes()
    with Image.open(BytesIO(raw)) as icon:
        if icon.size != (48, 48) or icon.mode != "RGBA":
            raise ValueError("starwind status requires a 48x48 RGBA icon")
        if icon.getextrema()[3] != (0, 255):
            raise ValueError("starwind status requires visible content and transparency")
    return png_encode(raw)


def stock_icon_bytes():
    return _icon_bytes(ICON_PATH)


def gain_icon_bytes():
    return _icon_bytes(GAIN_ICON_PATH)
