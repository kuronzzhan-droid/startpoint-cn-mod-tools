"""装载校园碧安卡专属状态图标，编码为客户端存储态 PNG。"""
from io import BytesIO
from pathlib import Path

from PIL import Image

from wf_assets import png_encode

ASSET_DIR = Path(__file__).resolve().parent / "assets/bianca-dragon-icons"
ICON_NAMES = {
    "campus_bianca_dragon_summon": "summon",
    "campus_bianca_dragon_breath": "breath",
    "lady_summoner_campus_fever_stack": "fever_stack",
}


def build_icon_assets():
    """保持已发布的三个路径；拒绝错误尺寸、模式或复制占位图。"""
    result = {}
    for logical_name, filename in ICON_NAMES.items():
        raw = (ASSET_DIR / (filename + ".png")).read_bytes()
        with Image.open(BytesIO(raw)) as icon:
            if icon.size != (48, 48) or icon.mode != "RGBA":
                raise ValueError(f"invalid native status icon: {filename}")
            if icon.getextrema()[3] != (0, 255):
                raise ValueError(f"status icon requires visible content and transparency: {filename}")
        result[f"battle/common/unique_condition/{logical_name}.png"] = png_encode(raw)
    if len(set(result.values())) != len(ICON_NAMES):
        raise ValueError("status icons must have distinct artwork")
    return result
