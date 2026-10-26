"""Conservative image-prefix evidence for native summon preload."""
from .drafts import DraftError
from .summon_tables import CHAR, BALL, EMPTY, single


def validate_image(tables, row):
    prefix = row[1]
    characters = {single(value, CHAR)[0] for value in tables.table(CHAR).values()}
    balls = {single(value, BALL)[1] for value in tables.table(BALL).values()}

    def exists(logical):
        raw = tables.source.raw(logical)
        tables.original[logical] = raw
        return raw is not None

    if prefix not in characters | balls and not any(exists(f"character/{prefix}/pixelart/{name}.png")
                                                    for name in ("sprite_sheet", "pixelart")):
        raise DraftError("image_prefix 在角色、multiball 与像素资源中均不存在：" + prefix)
    if row[9] not in EMPTY and prefix not in characters and not exists(f"character/{prefix}/ui/skill_cutin_0.png"):
        raise DraftError("带主动技能的纯球体缺少 skill_cutin_0 证据：" + prefix)
