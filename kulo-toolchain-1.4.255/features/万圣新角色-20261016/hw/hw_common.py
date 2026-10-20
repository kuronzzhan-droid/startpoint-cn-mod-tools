# -*- coding: utf-8 -*-
"""万圣四角色包上下文:MAPack(★4/★3 母本 status/gacha 补洞)+ 读 1.4.220 视图 store,不用官方 .cdn 基线。"""
from __future__ import annotations
import hw_env
from pathlib import Path
import wf_midautumn_common as MC
from wf_midautumn_common import RarityUpgrade
import hw_specs as HS

# donor = 同元素同 pf 类型官方 ★5 按 Lv100 ATK 中位(hw_build --step donors 复算)
RARITY: dict[str, RarityUpgrade] = {
    "ludi": RarityUpgrade(template_id=231009, status_donor="131098",
                          why="母本 ★4 雷 pf4;官方 ★5 雷 pf4 六人 ATK 627-891,取 131098 spider_ninja 3267/786(上中位)"),
    "recital": RarityUpgrade(template_id=341003, status_donor="141005", gacha_donor="141005",
                             why="母本 ★3 风 pf3 且缺 gacha_sound;官方 ★5 风 pf3 十人取中位 141005 bigwing_shaman 706"),
}


class HWPack(MC.MAPack):
    def __init__(self, spec, **kw):
        kw.setdefault("root", hw_env.ROOT)
        kw.setdefault("store", hw_env.STORE)
        kw.setdefault("server_base", hw_env.SERVER_BASE)
        kw.setdefault("use_official", False)
        super().__init__(spec, **kw)

    @property
    def batch_dir(self) -> Path:
        return self.root / HS.BATCH_DIR

    @property
    def upgrade(self):
        return RARITY.get(self.spec.key)

    def official_flat(self, logical):
        return self.live_flat(logical)

    def official_read(self, logical, root=None):
        """无官方 .cdn 基线:一律读 1.4.220 视图(母本四人未被自制增强改过,见 PROGRESS)。"""
        loc = self.live_locate(logical)
        if loc is None or (root is not None and loc[0] != root):
            return None
        return loc[1].read_bytes()

    def official_identity(self, logical):
        return None


def pack_for(key: str, **kw) -> HWPack:
    return HWPack(HS.get_spec(key), **kw)
