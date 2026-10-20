# -*- coding: utf-8 -*-
"""水杰拉德包上下文:MAPack + 读 1.4.238 视图 store,不用官方 .cdn 基线。母本拉绮夏已是 ★5,无需升稀有度。"""
from __future__ import annotations
import wg_env
from pathlib import Path
import wf_midautumn_common as MC
from wf_midautumn_common import RarityUpgrade
import wg_specs as HS

# donor = 同元素同 pf 类型官方 ★5 按 Lv100 ATK 中位(hw_build --step donors 复算)
RARITY: dict[str, RarityUpgrade] = {}


class HWPack(MC.MAPack):
    def __init__(self, spec, **kw):
        kw.setdefault("root", wg_env.ROOT)
        kw.setdefault("store", wg_env.STORE)
        kw.setdefault("server_base", wg_env.SERVER_BASE)
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
        """无官方 .cdn 基线:一律读 1.4.238 视图。"""
        loc = self.live_locate(logical)
        if loc is None or (root is not None and loc[0] != root):
            return None
        return loc[1].read_bytes()

    def official_identity(self, logical):
        return None


def pack_for(key: str, **kw) -> HWPack:
    return HWPack(HS.get_spec(key), **kw)
