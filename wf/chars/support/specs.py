"""Production primitives extracted from wf_seasonal7_specs.py (C baseline)."""
from __future__ import annotations
import dataclasses


from dataclasses import dataclass, field


from typing import Any, Mapping


ELEMENT_TOKENS = ("Red", "Blue", "Yellow", "Green", "White", "Black")


ELEMENT_COLORS = ("red", "blue", "yellow", "green", "white", "black")


ELEMENT_SE_DIRS = ("fire", "water", "thunder", "wind", "light", "dark")


ELEMENT_WORDS = ("火", "水", "雷", "风", "光", "暗")


BATCH_DIR = "work/character_packs/seasonal7-20260916"


REQUIRES_CLIENT_BASE = "1.4.858"


PACKAGE_VERSION = "1.0.0"


@dataclass(frozen=True)
class SeasonalSpec:
    key: str
    cid: int
    code: str
    pkg_id: str
    workspace: str            # 相对仓库根
    template_id: int
    template_code: str
    template_element: int     # 母本 character c3（0 基），构建时与母本行核对
    element: int              # 新角色 c3（0 基）
    element_token: str
    rarity: int
    pf_type: int              # c6
    stance: str               # c26
    identity: int             # c27：自身 cid（校园先例）或 template_identity（官方惯例），待作者拍板
    template_identity: int    # 母本官方行 c27（tables 构建时与母本行核对）
    theme: str
    texts: dict[str, Any]     # None = 从母本继承（技能名/描述/CV）
    backdrop_colors: tuple[tuple[int, int, int], tuple[int, int, int]]
    gacha_se_map: dict[str, str] = field(default_factory=dict)
    required_capabilities: tuple[str, ...] = ()
    # kit 自有键的占用断言扩展点：{logical_path: (key, ...)}。``*.orderedmap`` 查 live 客户端表外层键，
    # ``*.json`` 查仓库 ``assets/<path>`` 顶层键；批内 7 个 spec 之间也互斥。
    extra_keys: dict[str, tuple[str, ...]] = field(default_factory=dict)
    requires_client_base: str = REQUIRES_CLIENT_BASE
    package_version: str = PACKAGE_VERSION

    @property
    def cid_s(self) -> str:
        return str(self.cid)

    @property
    def template_id_s(self) -> str:
        return str(self.template_id)

    @property
    def ability_keys(self) -> list[str]:
        return [f"{self.cid}{slot}" for slot in range(1, 7)]

    @property
    def mana_prefix(self) -> str:
        return str(self.cid * 2)

    @property
    def template_mana_prefix(self) -> str:
        return str(self.template_id * 2)

    @property
    def element_flip(self) -> bool:
        return self.template_element != self.element

    @property
    def template_token(self) -> str:
        return ELEMENT_TOKENS[self.template_element]

    def to_dict(self) -> dict[str, Any]:
        value = dataclasses.asdict(self)
        value["backdrop_colors"] = [list(c) for c in self.backdrop_colors]
        value["required_capabilities"] = list(self.required_capabilities)
        value["extra_keys"] = {k: list(v) for k, v in sorted(self.extra_keys.items())}
        return value
