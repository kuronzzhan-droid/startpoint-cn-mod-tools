"""Read the game's two native square avatars; never crop full illustrations."""
from __future__ import annotations


def character_avatars(code: str, media) -> dict[str, str]:
    result = {}
    for form, name in ((0, "before"), (1, "after")):
        for kind in ("square", "thumbnail"):
            logical = f"character/{code}/ui/{kind}_{form}.png"
            if media.has(logical):
                url = media.image(logical)
                if url:
                    result[name] = url
                    break
    return result
