"""Shared media helpers extracted from the production C tools."""
from __future__ import annotations
from PIL import Image

def fit_rgba(image: Image.Image, size: tuple[int, int],
             focus: tuple[float, float] = (0.5, 0.42)) -> Image.Image:
    """Contain an image on an exact transparent RGBA canvas."""
    source = image.convert("RGBA")
    scale = min(size[0] / source.width, size[1] / source.height)
    scaled = source.resize(
        (max(1, round(source.width * scale)),
         max(1, round(source.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    x = round(size[0] * focus[0] - scaled.width * focus[0])
    y = round(size[1] * focus[1] - scaled.height * focus[1])
    canvas.alpha_composite(scaled, (x, y))
    return canvas

def cover_rgba(image: Image.Image, size: tuple[int, int],
               focus: tuple[float, float] = (0.5, 0.25),
               padding: float = 0.04) -> Image.Image:
    """Focal-crop the visible subject so compact UI slots are actually filled.

    Generated masters commonly contain a large transparent margin.  Cropping
    from the RGBA alpha bounds first makes ``focus`` describe the character,
    not the original generation canvas.  ``fit_rgba`` remains the contain
    operation for full-shot assets.
    """
    source = image.convert("RGBA")
    bbox = source.getchannel("A").getbbox()
    if bbox is None:
        return Image.new("RGBA", size, (0, 0, 0, 0))
    left, top, right, bottom = bbox
    visible_width = right - left
    visible_height = bottom - top
    margin_x = round(visible_width * max(0.0, padding))
    margin_y = round(visible_height * max(0.0, padding))
    left = max(0, left - margin_x)
    top = max(0, top - margin_y)
    right = min(source.width, right + margin_x)
    bottom = min(source.height, bottom + margin_y)
    visible = source.crop((left, top, right, bottom))

    scale = max(size[0] / visible.width, size[1] / visible.height)
    scaled = visible.resize(
        (max(1, round(visible.width * scale)),
         max(1, round(visible.height * scale))),
        Image.Resampling.LANCZOS,
    )
    focus_x = min(1.0, max(0.0, focus[0]))
    focus_y = min(1.0, max(0.0, focus[1]))
    max_x = max(0, scaled.width - size[0])
    max_y = max(0, scaled.height - size[1])
    crop_x = round(max_x * focus_x)
    crop_y = round(max_y * focus_y)
    return scaled.crop((crop_x, crop_y, crop_x + size[0], crop_y + size[1]))

def focal_rect_rgba(image: Image.Image, size: tuple[int, int],
                    rect: tuple[float, float, float, float]) -> Image.Image:
    """Crop an explicit normalized region of the visible subject, then cover."""
    source = image.convert("RGBA")
    bbox = source.getchannel("A").getbbox()
    if bbox is None:
        return Image.new("RGBA", size, (0, 0, 0, 0))
    x0, y0, x1, y1 = rect
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError(f"invalid normalized focal rect: {rect}")
    left, top, right, bottom = bbox
    width, height = right - left, bottom - top
    crop = (
        left + round(width * x0),
        top + round(height * y0),
        left + round(width * x1),
        top + round(height * y1),
    )
    return cover_rgba(source.crop(crop), size, focus=(0.5, 0.12), padding=0)
