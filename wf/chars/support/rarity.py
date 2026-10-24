"""Production primitives extracted from wf_midautumn_common.py (C baseline)."""
from __future__ import annotations
from dataclasses import dataclass


from pathlib import Path


from types import SimpleNamespace
MS = SimpleNamespace(BATCH_DIR="work/character_packs/halloween-20261016", UNIQUE_CONDITION_LOGICAL="master/character/unique_condition.orderedmap")  # noqa: E402


from wf.chars.support.common import S7Error, S7Pack  # noqa: E402


STATUS = "master/character/character_status.orderedmap"


GACHA_SOUND = "master/character/character_gacha_sound.orderedmap"


MANA_NODE = "master/mana_board/mana_node.orderedmap"


MANA_BOARD = "master/generated/mana_board.orderedmap"


@dataclass(frozen=True)
class RarityUpgrade:
    """非 ★5 母本的 raw_outer 补洞方案（donor 一律取官方基线的官方 ★5 行）。"""
    template_id: int
    status_donor: str                     # 必填：character_status 换成这一行
    gacha_donor: str | None = None        # 母本缺 gacha_sound 行时才补（★3 母本）
    mana_donor: str | None = None         # 默认 None：实测玛纳消耗与稀有度无关（见模块 docstring）
    why: str = ""


RARITY_UPGRADES: dict[str, RarityUpgrade] = {
    "nicola": RarityUpgrade(
        template_id=211020, status_donor="111153",
        why="母本 211020 是 ★4（Lv100 3320/674）；donor 111153 flame_blessgirl 火/pf4/★5 4059/799"),
    "kuro": RarityUpgrade(
        template_id=231069, status_donor="131080",
        why="母本 231069 是 ★4（Lv100 3248/700）；donor 131080 psychic_tohru 雷/pf1/★5 3069/825"),
    "rebecca": RarityUpgrade(
        template_id=241006, status_donor="161147",
        why="母本 241006 是 ★4（Lv100 3412/653）；donor 161147 horn_mypace 暗/pf3/★5 3927/766"),
}


class MAPack(S7Pack):
    """中秋批次角色包上下文。

    ``record_sources=False``：只读体检用——母本取数不再把 ``evidence/template_sources.json``
    写进 workspace（否则 ``--step check`` 会在 ``init`` 之前把目录弄成「非空且没有
    workspace.json」，init 直接拒绝）。
    """

    def __init__(self, spec, *, record_sources: bool = True, **kwargs) -> None:
        super().__init__(spec, **kwargs)
        self.record_sources = record_sources

    @property
    def batch_dir(self) -> Path:
        return self.root / MS.BATCH_DIR

    def _record_source(self, logical: str, source: str, raw: bytes, note: str = "") -> None:
        if not self.record_sources:
            return
        super()._record_source(logical, source, raw, note)

    @property
    def upgrade(self) -> RarityUpgrade | None:
        entry = RARITY_UPGRADES.get(self.spec.key)
        if entry is not None and entry.template_id != self.spec.template_id:
            raise S7Error(f"{self.spec.key}: rarity upgrade targets template {entry.template_id} "
                          f"but spec template is {self.spec.template_id}")
        return entry

    def template_raw(self, logical: str) -> dict[str, bytes]:
        rows = super().template_raw(logical)
        entry = self.upgrade
        if entry is None:
            return rows
        tid = self.spec.template_id_s
        donor = self._donor_for(logical, entry)
        if donor is None:
            return rows
        donor_id, required = donor
        if not required and tid in rows:
            return rows                     # 补洞型（gacha_sound）：母本有行就不动
        if donor_id not in rows:
            raise S7Error(f"rarity donor {donor_id} missing from official {logical}")
        rows = dict(rows)
        blob = rows[donor_id]
        if logical in (MANA_NODE, MANA_BOARD):
            blob = self._remap_donor_mana(blob, donor_id)
        rows[tid] = blob
        return rows

    @staticmethod
    def _donor_for(logical: str, entry: RarityUpgrade) -> tuple[str, bool] | None:
        """(donor 行键, 是否无条件替换)；返回 None 表示这张表不参与补洞。"""
        if logical == STATUS:
            return entry.status_donor, True
        if logical == GACHA_SOUND and entry.gacha_donor:
            return entry.gacha_donor, False
        if logical in (MANA_NODE, MANA_BOARD) and entry.mana_donor:
            return entry.mana_donor, True
        return None

    def _remap_donor_mana(self, blob: bytes, donor_id: str) -> bytes:
        """donor 的玛纳节点前缀先改回**母本**前缀，tables 后面那一步才能照常改成新角色前缀。"""
        import re

        from wf.chars.support import tables as T
        donor_prefix = str(int(donor_id) * 2)
        node_re = re.compile(r"^" + re.escape(donor_prefix) + r"(\d{3})$")
        template_prefix = self.spec.template_mana_prefix

        def transform(cell: str) -> str:
            if cell == donor_id:
                return self.spec.template_id_s
            m = node_re.match(cell)
            if m:
                return template_prefix + m.group(1)
            return cell

        return T.clone_blob(blob, transform)
