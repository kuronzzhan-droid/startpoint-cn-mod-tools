# -*- coding: utf-8 -*-
"""中秋批次：角色包上下文（``MAPack``）与 ★4/★3 母本补洞。

``MAPack`` 只在 :class:`wf_seasonal7_common.S7Pack` 上改两件事：

1. ``batch_dir`` 指向本批目录（inspect 副本、占用缓存、art 默认路径都跟着走）；
2. ``template_raw`` 在**母本不是 ★5** 时，把按稀有度分档的 raw_outer 行换成同 pf 类型的
   官方 ★5 donor 行（海豹球先例 ``wf_spheal_mascot.SphealPack.template_raw``）。

为什么只换 ``character_status``（实测，2026-09-20，官方基线）：

===========  ===  ==========================  ===========================================
母本          ★    Lv100 HP/ATK                玛纳盘
===========  ===  ==========================  ===========================================
211020 妮可拉  4   3320 / 674                  41 节点，总消耗 293240
231069 黑      4   3248 / 700                  41 节点，总消耗 293240
241006 蕾贝卡  4   3412 / 653                  41 节点，总消耗 293240
官方 ★5 中位   5   3307 / **806**              41 节点，总消耗 293240
===========  ===  ==========================  ===========================================

- ATK 差是真的（653–700 vs ★5 中位 806）⇒ ``character_status`` 必须换 ★5 donor。
- **玛纳消耗与稀有度无关**：249 个官方 ★5 与 164 个官方 ★4 的 mana_node 总消耗都只有
  {113240（23 节点）, 293240（41 节点）} 两档，三个 ★4 母本全在 41/293240 这档；材料数量签名
  在官方 ★5 里分别有 172 / 172 / 61 个同签名先例。换 donor 只会白白重映射节点前缀、
  还要连 ``mana_board`` 一起换（结构不一致的风险），**默认不换**（:data:`RARITY_UPGRADES`
  的 ``mana_donor`` 留空；真要换时机制已实现并有测试）。
- ``character_gacha_sound`` 只有 ★3 母本缺行（361007 / 331004），本批 12 人没用到；
  ``gacha_donor`` 是为这种情况留的补洞口，缺行才补，有行不动。

技能程序路径 ``rare4 → rare5`` 不需要额外处理：``wf_seasonal7_tables.program_path`` 用的是
``spec.rarity``（=5），DSL 母本则从母本 action_skill 内层行 c7 取（仍是 rare4），两边自动分开。
技能文案档位也不用处理：三个 ★4 母本的 action_skill 内层键同样是 ``{"1","2"}``（实读）。
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_seasonal7_common as C  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
from wf_seasonal7_common import S7Error, S7Pack  # noqa: E402

STATUS = "master/character/character_status.orderedmap"
GACHA_SOUND = "master/character/character_gacha_sound.orderedmap"
MANA_NODE = "master/mana_board/mana_node.orderedmap"
MANA_BOARD = "master/generated/mana_board.orderedmap"
CHARACTER = "master/character/character.orderedmap"


@dataclass(frozen=True)
class RarityUpgrade:
    """非 ★5 母本的 raw_outer 补洞方案（donor 一律取官方基线的官方 ★5 行）。"""
    template_id: int
    status_donor: str                     # 必填：character_status 换成这一行
    gacha_donor: str | None = None        # 母本缺 gacha_sound 行时才补（★3 母本）
    mana_donor: str | None = None         # 默认 None：实测玛纳消耗与稀有度无关（见模块 docstring）
    why: str = ""


# donor 选取规则（可复算，见 :func:`donor_candidates`）：在官方基线里取
# 「新角色元素 + 母本 pf 类型 + ★5 + 普通可玩 ID（11xxxx–16xxxx）」的全部角色，
# 按 Lv100 ATK 排序取中位数那一个（偶数个取靠下的一个，平手取 ID 小的）。
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

        import wf_seasonal7_tables as T
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


def pack_for(spec, **kwargs) -> MAPack:
    return MAPack(spec, **kwargs)


# ---------------------------------------------------------------- 只读核实工具

def _official_characters(pack: S7Pack) -> dict[str, list[str]]:
    raw = pack.official_read(CHARACTER, "common")
    if raw is None:
        raise S7Error("official baseline unavailable: cannot verify rarity donors")
    rows = C.core.read_orderedmap_file_from_bytes(raw)
    return {key: C.csv_split(text)[0] for key, text in rows.items()}


def _lv100(pack: S7Pack, cid: str) -> tuple[int, int] | None:
    import zlib
    raw = pack.official_read(STATUS, "common")
    if raw is None:
        return None
    om = C.core.read_orderedmap_raw_rows_from_bytes(raw, STATUS)
    table = dict(zip(om.keys, om.rows))
    if cid not in table:
        return None
    inner = C.core.read_orderedmap_raw_rows_from_bytes(table[cid], "status")
    levels = dict(zip(inner.keys, inner.rows))
    if "100" not in levels:
        return None
    row = C.core.read_csv_lines(zlib.decompress(levels["100"]).decode("utf-8"))[0]
    return int(row[0]), int(row[1])


def donor_candidates(pack: S7Pack, element: int, pf_type: int) -> list[dict[str, Any]]:
    """官方 ★5、指定元素与 pf 类型、普通可玩 ID 的候选（按 Lv100 ATK 升序）。"""
    out = []
    for cid, row in _official_characters(pack).items():
        if not (cid.isdigit() and len(cid) == 6 and 11 <= int(cid) // 10000 <= 16):
            continue
        if row[2] != "5" or row[3] != str(element) or row[6] != str(pf_type):
            continue
        stats = _lv100(pack, cid)
        if stats is None:
            continue
        out.append({"cid": cid, "code": row[0], "hp": stats[0], "atk": stats[1]})
    return sorted(out, key=lambda item: (item["atk"], int(item["cid"])))


def median_donor(pack: S7Pack, element: int, pf_type: int) -> dict[str, Any] | None:
    """donor 选取规则的可复算实现：候选按 ATK 升序，取下标 ``(n-1)//2``。"""
    rows = donor_candidates(pack, element, pf_type)
    return rows[(len(rows) - 1) // 2] if rows else None


def rarity_problems(pack: S7Pack) -> list[str]:
    """核实本角色的稀有度补洞：母本 ★、donor 是否官方 ★5 同 pf、donor 是否落在中位规则上。"""
    spec = pack.spec
    chars = _official_characters(pack)
    problems: list[str] = []
    tid = spec.template_id_s
    if tid not in chars:
        return [f"template {tid} missing from official character table"]
    template_rarity = chars[tid][2]
    entry = RARITY_UPGRADES.get(spec.key)
    if template_rarity == "5":
        if entry is not None:
            problems.append(f"template {tid} is already ★5 but a rarity upgrade is registered")
        return problems
    if entry is None:
        problems.append(f"template {tid} is ★{template_rarity} but no rarity upgrade is registered "
                        f"(character_status would stay in the ★{template_rarity} band)")
        return problems
    donor = entry.status_donor
    if donor not in chars:
        problems.append(f"status donor {donor} missing from official character table")
        return problems
    row = chars[donor]
    if row[2] != "5":
        problems.append(f"status donor {donor} is ★{row[2]}, not ★5")
    if row[6] != str(spec.pf_type):
        problems.append(f"status donor {donor} pf_type {row[6]} != spec pf_type {spec.pf_type}")
    expected = median_donor(pack, spec.element, spec.pf_type)
    if expected is not None and expected["cid"] != donor:
        problems.append(f"status donor {donor} is not the median-ATK ★5 candidate "
                        f"({expected['cid']} {expected['code']} ATK{expected['atk']}); "
                        "更新 RARITY_UPGRADES 或在文档里登记理由")
    return problems


def gacha_flip_gaps(pack: S7Pack) -> list[str]:
    """元素翻转时母本 gacha_sound 里仍指向旧元素、却没有 ``gacha_se_map`` 的 SE。

    ``wf_seasonal7_tables._gacha_transform`` 命中这些格会直接抛错；``--step check`` 提前报出来。
    """
    import wf_seasonal7_tables as T
    spec = pack.spec
    if not spec.element_flip:
        return []
    old_dir = MS.ELEMENT_SE_DIRS[spec.template_element]
    rows = pack.template_raw(GACHA_SOUND)
    if spec.template_id_s not in rows:
        return [f"template gacha_sound row missing: {spec.template_id_s}"]
    found: set[str] = set()

    def collect(node: Any) -> None:
        if isinstance(node, dict):
            for value in node.values():
                collect(value)
        elif isinstance(node, str):
            for row in C.csv_split(node):
                for cell in row:
                    for part in cell.split(","):
                        if part.startswith(f"sound_effect/{old_dir}/"):
                            found.add(part)

    collect(T.decode_blob(rows[spec.template_id_s]))
    return sorted(se for se in found if se not in spec.gacha_se_map)
