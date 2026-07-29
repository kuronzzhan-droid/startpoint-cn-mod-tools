#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""去增强策略引擎:把 mod 链终态里的"个人增强"剥回官方原值,只留内容行。

用途:对外分享时产出 content-only 变体(纯内容包)——收方只想要
「三自制角色 + 15 把深渊武器 + 700099 随机塔模式」,不想要我们自服的
平衡总包/白虎重做/敌人血量上调等个人增强。

三条硬规则(2026-07-29 定案,见 docs/去增强变体.md):

  1. **官方基准 = 官方 CDN 归档,不是 store 备份**。官方全量包
     (.cdn/cn/archive-<root>-full/pinball-<base>-<seq>-<hex>.zip)加官方
     增量(archive-<root>-diff 里 to 版本 ≤ OFFICIAL_TAIL 且 tag 非 mod*)
     按版本序重放,末次写入即官方原值。store 里的 .bak-wfmod-* 备份**不可
     信**:最早的 gui 备份才等于官方,平衡套件自己的"锁定基准"已经带了它
     前一轮的增量行。本模块解析出的 ability_soul / equipment_enhancement_ability
     基准与 build_abyss_weapon_balance_patch.py 里钉死的哈希逐字节一致
     (PINNED_BASELINES,启动即校验),两条独立路径互为交叉验证。

  2. **纠缠表禁止文件级排除,只能按行重建**。ability/leader_ability/
     character_status/ability_soul/character/action_skill 等表既装官方行、
     又装深渊武器行和自制角色行,整文件丢掉 = 客户端 C8601。重建规则:
     官方 key 一律取官方值(官方 key 的嵌套子 key 同理);live 里多出来的
     key(自制角色/武器/模式行)原样保留并追加在官方行之后。官方行只被
     "加嵌套子行"(zone.treasure_cave_area 那种模式场地)时,官方子行取官方值、
     新增子行保留。live 里被删掉的官方行会被重新补回。

  3. **官方资产文件(非表)按 drop-list 丢弃**。白虎技能 DSL
     (battle/.../white_tiger$white_tiger_2.action.dsl.amf3.deflate)是全链
     唯一被改的官方资产文件,不下发即等于收方保留官方原件。

模块只做策略与重建,不写 zip、不碰 CDN;打包由 wf_share_variant.py 负责。

CLI:
  python mod-tools/wf_enhancement_policy.py audit            # 审计当前链终态
  python mod-tools/wf_enhancement_policy.py audit --json     # 机器可读
  python mod-tools/wf_enhancement_policy.py baseline --prime # 预热官方基准索引
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

MOD_DIR = Path(__file__).resolve().parent
ROOT = MOD_DIR.parent
sys.path.insert(0, str(MOD_DIR))

import wf_quest_lib as quest  # noqa: E402
import wf_mod_tool as core  # noqa: E402

# ------------------------------------------------------------------ 常量

# CN 官方链尾:此版本之后的所有增量边都是我们自己发的(tag 一律 mod*)
OFFICIAL_TAIL = "1.4.54"
CLIENT_ROOTS = ("common", "medium", "android")
ARCHIVE_PREFIXES = {
    "common": "production/upload/",
    "medium": "production/medium_upload/",
    "android": "production/android_upload/",
}
ROOT_OF_PREFIX = {value.rstrip("/"): key for key, value in ARCHIVE_PREFIXES.items()}

FULL_RE = re.compile(r"^pinball-(\d+\.\d+\.\d+)-(\d+)-([0-9a-f]+)\.zip$")
DIFF_RE = re.compile(r"^pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-(\d+)-(.+)\.zip$")
MEMBER_RE = re.compile(r"^[0-9a-f]{2}/[0-9a-f]{38}$")

# 个人增强的官方资产文件:不进纯内容变体(收方保留自己的官方原件)
DROP_LOGICALS: tuple[str, ...] = (
    "battle/action/skill/action/rare4/white_tiger$white_tiger_2.action.dsl.amf3.deflate",
)

# 已知会被增强改写的表(仅用于审计提示;实际重建是数据驱动的,不依赖本清单)
KNOWN_ENHANCED_TABLES: tuple[str, ...] = (
    "master/ability/ability.orderedmap",
    "master/ability/leader_ability.orderedmap",
    "master/ability/ability_soul.orderedmap",
    "master/character/character_status.orderedmap",
    "master/character/character.orderedmap",          # 行 10 白虎
    "master/skill/action_skill.orderedmap",           # 行 white_tiger
    "master/equipment_enhancement/equipment_enhancement_ability.orderedmap",
    "master/battle/boss/boss_level.orderedmap",       # 官方 boss 血量 ×4
    "master/generated/character_image.orderedmap",
    "master/generated/trimmed_image.orderedmap",
    "master/quest/event/rush_event_quest.orderedmap",              # 官方 700007
    "master/quest/event/rush_event_battle_quest_correction.orderedmap",
)

# 官方基准哈希钉死点:与 build_abyss_weapon_balance_patch.py 的 SOUL/WAB 常量
# 同源,任一条对不上就说明官方归档被动过或解析口径变了,必须停机排查。
PINNED_BASELINES: dict[str, tuple[int, str]] = {
    "master/ability/ability_soul.orderedmap": (
        38_313, "70dd53d7e1f9078199a017d49c0adb2946ecb6e91abfbc42f4b6a4da4b0a2e1e"),
    "master/equipment_enhancement/equipment_enhancement_ability.orderedmap": (
        3_640, "b9aa82f7c7483af88f758bcdaeed6474178e57a076d86b660d0bab902996e0ae"),
}

# 内容行识别规则:命中 = 我们自己的内容(自制角色/深渊武器/模式);
# 不命中的新增行不会被删,但会在审计里单列出来等人工判定。
CONTENT_KEY_PATTERNS: tuple[str, ...] = (
    r"^mod_",                                            # wf_rogue_build 生成的模式行
    r"^(111991|119998|119999|129999|139999|149999)\d*$",  # 自制角色 + 金丝雀(含 ability 后缀)
    r"^80001(0[1-9]|1[0-5])$",                           # 深渊武器 8000101-8000115
    r"^97001(0[1-9]|1[0-5])$",                           # 兑换商店条目
    r"^2370099$",                                        # 模式代币
    r"^700099\d*$",                                      # 700099 模式 event/quest
    r"^(seris_dragon_king|stella_summer_goddess|white_wolf_gerald)",
    r"^resistance_princess_canary2$",
    r"^override_",                                       # power_flip_action 覆写
    r"^ability_skill_(white_tiger_pf|white_wolf_moon_fang)$",
    r"^character/(kyle_wolf_knight|seris_dragon_king|stella_summer_goddess"
    r"|white_wolf_gerald|resistance_princess_canary2)/",
)
# 表内点名放行(模式给官方枚举续号,靠模式匹配认不出来)
EXTRA_CONTENT_KEYS: dict[str, frozenset[str]] = {
    "master/character/unique_condition.orderedmap": frozenset({"22", "23"}),
}

ABYSS_WEAPONS: tuple[str, ...] = tuple(str(8000100 + n) for n in range(1, 16))
SHOP_ITEMS: tuple[str, ...] = tuple(str(9700100 + n) for n in range(1, 16))
RELEASED_CHARACTERS: tuple[str, ...] = ("129999", "139999", "149999")

# 纯内容变体必须携带的行(金样验证的"齐全"判据):三自制角色 + 15 把深渊武器
# + 700099 模式。缺任何一条即判失败,防止重建把内容一起洗掉。
EXPECTED_CONTENT_ROWS: dict[str, tuple[str, ...]] = {
    "master/character/character.orderedmap": RELEASED_CHARACTERS,
    "master/character/character_status.orderedmap": RELEASED_CHARACTERS,
    "master/character/character_text.orderedmap": RELEASED_CHARACTERS,
    "master/ability/leader_ability.orderedmap": RELEASED_CHARACTERS,
    "master/mana_board/mana_node.orderedmap": RELEASED_CHARACTERS,
    "master/skill/action_skill.orderedmap": (
        "seris_dragon_king", "stella_summer_goddess", "white_wolf_gerald"),
    "master/skill/power_flip_action.orderedmap": (
        "white_wolf_gerald_pf", "override_seris_human_powerflip",
        "override_seris_dragon_special"),
    "master/ability/ability_soul.orderedmap": ABYSS_WEAPONS,
    "master/item/equipment.orderedmap": ABYSS_WEAPONS,
    "master/item/equipment_status.orderedmap": ABYSS_WEAPONS,
    "master/item/item.orderedmap": ("2370099", *ABYSS_WEAPONS),
    "master/shop/event_item_shop.orderedmap": SHOP_ITEMS,
    "master/quest/event/event_list.orderedmap": ("700099",),
    "master/quest/event/rush_event.orderedmap": ("700099",),
    "master/quest/event/rush_event_quest.orderedmap": ("700099",),
    "master/quest/event/rush_event_quest_folder.orderedmap": ("700099",),
}

CACHE_DIR = MOD_DIR / "work" / "official-baseline"

# 服务端侧的个人增强(不在客户端包里,本引擎管不到,只能声明给收方)。
# 白虎专项重做的服务端落点,2026-07-29 用户拍板归入个人增强。
SERVER_SIDE_ENHANCEMENTS: tuple[dict[str, str], ...] = (
    {
        "file": "assets/character.json",
        "row": "10",
        "field": "rarity",
        "ours": "5",
        "official": "4",
        "note": "白虎(角色 10)专项重做的服务端落点",
    },
    {
        "file": "assets/cdndata/character.json",
        "row": "10",
        "field": "col9 / col14 / col15 / col16",
        "ours": "4 / starbreak_hunter_meteor23 / false / false",
        "official": "(None) / 空 / 空 / 空",
        "note": "白虎 special 演出槽,与上一条同族",
    },
)


# ------------------------------------------------------------------ 工具

def vkey(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def bump_version(version: str) -> str:
    parts = version.split(".")
    return ".".join([*parts[:-1], str(int(parts[-1]) + 1)])


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def member_name(root: str, rel: str) -> str:
    return ARCHIVE_PREFIXES[root] + rel


def split_member(name: str) -> tuple[str, str] | None:
    """zip 成员名 → (root, rel);不是三层 upload 成员则 None。"""
    normalized = name.replace("\\", "/").strip("/")
    head, _, rel = normalized.rpartition("/")
    head, _, tail = head.rpartition("/")
    rel = f"{tail}/{rel}"
    root = ROOT_OF_PREFIX.get(head)
    if root is None or not MEMBER_RE.fullmatch(rel):
        return None
    return root, rel


_LOGICAL_INDEX: dict[str, str] | None = None


def logical_index() -> dict[str, str]:
    """rel(xx/38hex) → 逻辑路径。来自 WF_PATHLIST_recovered.txt(仓内已跟踪)。"""
    global _LOGICAL_INDEX
    if _LOGICAL_INDEX is None:
        index: dict[str, str] = {}
        pathlist = MOD_DIR / "WF_PATHLIST_recovered.txt"
        if pathlist.is_file():
            for line in pathlist.read_text(encoding="utf-8", errors="replace").splitlines():
                logical = line.strip()
                if logical:
                    index[quest.hashed_rel(logical)] = logical
        for logical in (*DROP_LOGICALS, *KNOWN_ENHANCED_TABLES):
            index.setdefault(quest.hashed_rel(logical), logical)
        _LOGICAL_INDEX = index
    return _LOGICAL_INDEX


def logical_of(rel: str) -> str | None:
    return logical_index().get(rel)


def drop_rels(logicals: Iterable[str] = DROP_LOGICALS) -> dict[str, str]:
    """逻辑路径 → rel 的 drop-list(sha1 不可逆,必须正向算)。"""
    return {quest.hashed_rel(logical): logical for logical in logicals}


# ------------------------------------------------------------------ 官方基准

@dataclass(frozen=True)
class BaselineEntry:
    rel: str
    crc: int
    size: int
    archive: Path
    member: str


class BaselineUnavailable(RuntimeError):
    """官方归档不可用(.cdn 未挂载/被裁剪),纯内容变体无法构建。"""


class OfficialBaseline:
    """官方 CDN 归档索引:rel → 官方原值(按版本序末次写入)。

    只读 zip 目录信息(CRC32+size)建索引,字节按需解压,故对 6GB 全量包也很快。
    索引缓存在 mod-tools/work/official-baseline/,归档目录变动时自动失效。
    """

    def __init__(
        self,
        cdn_root: Path,
        *,
        official_tail: str = OFFICIAL_TAIL,
        cache_dir: Path | None = None,
        verify_pinned: bool = True,
    ) -> None:
        self.cdn_root = Path(cdn_root)
        self.official_tail = official_tail
        self.cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
        self._index: dict[str, dict[str, BaselineEntry]] = {}
        self._verify_pinned = verify_pinned
        self._verified = False

    # -- 归档发现 ---------------------------------------------------
    def archives(self, root: str) -> list[Path]:
        """官方归档按客户端应用顺序:全量包(seq 序)→ 官方增量(to 版本序)。"""
        full_dir = self.cdn_root / f"archive-{root}-full"
        diff_dir = self.cdn_root / f"archive-{root}-diff"
        order: list[tuple[tuple, Path]] = []
        if full_dir.is_dir():
            for path in full_dir.glob("*.zip"):
                match = FULL_RE.match(path.name)
                if match:
                    order.append(((0, int(match.group(2)), 0), path))
        if diff_dir.is_dir():
            for path in diff_dir.glob("*.zip"):
                match = DIFF_RE.match(path.name)
                if match is None:
                    continue
                to_version, seq, tag = match.group(2), int(match.group(3)), match.group(4)
                if tag.startswith("mod") or vkey(to_version) > vkey(self.official_tail):
                    continue  # mod* 或超过官方链尾 = 我们自己发的边
                order.append(((1, vkey(to_version), seq), path))
        order.sort(key=lambda item: item[0])
        return [path for _key, path in order]

    def _stamp(self, root: str, archives: list[Path]) -> str:
        digest = hashlib.sha256()
        digest.update(self.official_tail.encode())
        for path in archives:
            stat = path.stat()
            # 必须带绝对路径:只用文件名会让内容相同、位置不同的两套 CDN 撞戳,
            # 索引里的 archive 指向已删除的目录 → 读基准时 FileNotFoundError。
            digest.update(f"{path}:{stat.st_size}:{int(stat.st_mtime)}".encode())
        return digest.hexdigest()

    def _load_index(self, root: str) -> dict[str, BaselineEntry]:
        cached = self._index.get(root)
        if cached is not None:
            return cached
        archives = self.archives(root)
        if not archives:
            raise BaselineUnavailable(
                f"没找到官方归档:{self.cdn_root / f'archive-{root}-full'} —— "
                "纯内容变体需要官方原值做基准,请挂载 .cdn 或用 --cdn 指定")
        stamp = self._stamp(root, archives)
        scope = hashlib.sha256(str(self.cdn_root.resolve()).encode()).hexdigest()[:12]
        cache_file = self.cache_dir / f"index-{root}-{self.official_tail}-{scope}.json"
        index: dict[str, BaselineEntry] = {}
        if cache_file.is_file():
            try:
                payload = json.loads(cache_file.read_text(encoding="utf-8"))
                if payload.get("stamp") == stamp:
                    index = {
                        rel: BaselineEntry(rel, item[0], item[1], Path(item[2]), item[3])
                        for rel, item in payload["entries"].items()
                    }
                    archive_set = {entry.archive for entry in index.values()}
                    if any(not path.is_file() for path in archive_set):
                        index = {}   # 缓存指向已消失的归档,重建
            except (OSError, ValueError, KeyError, IndexError):
                index = {}
        if not index:
            for path in archives:
                try:
                    with zipfile.ZipFile(path) as archive:
                        for info in archive.infolist():
                            if info.is_dir():
                                continue
                            parsed = split_member(info.filename)
                            if parsed is None or parsed[0] != root:
                                continue
                            rel = parsed[1]
                            index[rel] = BaselineEntry(
                                rel, info.CRC, info.file_size, path, info.filename)
                except zipfile.BadZipFile:
                    continue
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps({
                "stamp": stamp,
                "root": root,
                "officialTail": self.official_tail,
                "entries": {
                    rel: [entry.crc, entry.size, str(entry.archive), entry.member]
                    for rel, entry in index.items()
                },
            }, ensure_ascii=False), encoding="utf-8")
        self._index[root] = index
        if root == "common" and self._verify_pinned and not self._verified:
            self._verify_pinned_baselines(index)
            self._verified = True
        return index

    def _verify_pinned_baselines(self, index: dict[str, BaselineEntry]) -> None:
        for logical, (size, digest) in PINNED_BASELINES.items():
            rel = quest.hashed_rel(logical)
            entry = index.get(rel)
            if entry is None:
                raise BaselineUnavailable(
                    f"官方归档里找不到钉死基准 {logical};官方全量包不完整,拒绝继续")
            data = self._read(entry)
            if len(data) != size or sha256(data) != digest:
                raise BaselineUnavailable(
                    f"官方基准与钉死值不符:{logical} size={len(data)} "
                    f"sha256={sha256(data)[:16]} —— 官方归档被动过或解析口径变了")

    @staticmethod
    def _read(entry: BaselineEntry) -> bytes:
        with zipfile.ZipFile(entry.archive) as archive:
            return archive.read(entry.member)

    # -- 查询 -------------------------------------------------------
    def identity(self, root: str, rel: str) -> tuple[int, int] | None:
        entry = self._load_index(root).get(rel)
        return None if entry is None else (entry.crc, entry.size)

    def get(self, root: str, rel: str) -> bytes | None:
        entry = self._load_index(root).get(rel)
        return None if entry is None else self._read(entry)

    def stats(self, root: str = "common") -> dict:
        index = self._load_index(root)
        return {"root": root, "entries": len(index), "archives": len(self.archives(root))}


# ------------------------------------------------------------------ 表重建

def merge_official(official, live):
    """官方节点 + live 节点 → 干净节点。

    官方 key 取官方值;官方 key 双方都是 dict 时递归(允许模式往官方行里加
    嵌套子行,如 zone.treasure_cave_area);live 独有的 key 追加在末尾。
    """
    if not isinstance(official, dict) or not isinstance(live, dict):
        return official
    merged: dict[str, object] = {}
    for key, value in official.items():
        counterpart = live.get(key)
        if isinstance(value, dict) and isinstance(counterpart, dict):
            merged[key] = merge_official(value, counterpart)
        else:
            merged[key] = value
    for key, value in live.items():
        if key not in official:
            merged[key] = value
    return merged


@dataclass
class RebuildDetail:
    logical: str | None
    official_rows: int = 0
    live_rows: int = 0
    reverted_rows: list[str] = field(default_factory=list)
    restored_rows: list[str] = field(default_factory=list)   # live 里被删掉的官方行
    nested_extended_rows: list[str] = field(default_factory=list)
    kept_rows: list[str] = field(default_factory=list)
    unrecognized_rows: list[str] = field(default_factory=list)
    changed: bool = False

    def as_dict(self) -> dict:
        return {
            "logical": self.logical,
            "officialRows": self.official_rows,
            "liveRows": self.live_rows,
            "revertedRows": self.reverted_rows,
            "restoredRows": self.restored_rows,
            "nestedExtendedRows": self.nested_extended_rows,
            "keptRows": len(self.kept_rows),
            "unrecognizedRows": self.unrecognized_rows,
            "changed": self.changed,
        }


class Policy:
    """内容行识别 + drop-list。"""

    def __init__(
        self,
        *,
        drop_logicals: Iterable[str] = DROP_LOGICALS,
        content_patterns: Iterable[str] = CONTENT_KEY_PATTERNS,
        extra_content_keys: dict[str, frozenset[str]] | None = None,
        extra_drop_keys: dict[str, frozenset[str]] | None = None,
    ) -> None:
        self.drop_logicals = tuple(drop_logicals)
        self.drop_rels = drop_rels(self.drop_logicals)
        self._patterns = tuple(re.compile(p) for p in content_patterns)
        self.extra_content_keys = dict(extra_content_keys or EXTRA_CONTENT_KEYS)
        self.extra_drop_keys = dict(extra_drop_keys or {})

    def is_content_key(self, logical: str | None, key: str) -> bool:
        if logical and key in self.extra_content_keys.get(logical, frozenset()):
            return True
        return any(pattern.search(key) for pattern in self._patterns)

    def is_dropped_key(self, logical: str | None, key: str) -> bool:
        return bool(logical) and key in self.extra_drop_keys.get(logical, frozenset())


def rebuild_table(
    official_bytes: bytes,
    live_bytes: bytes,
    *,
    logical: str | None = None,
    policy: Policy | None = None,
) -> tuple[bytes, RebuildDetail]:
    """官方原值 + live 新增行 → 干净表字节。内容未变时原样返回 live 字节。"""
    policy = policy or Policy()
    official = quest.parse_node(official_bytes)
    live = quest.parse_node(live_bytes)
    detail = RebuildDetail(logical=logical)
    if not isinstance(official, dict) or not isinstance(live, dict):
        raise ValueError(f"{logical or '<unknown>'}: 不是顶层 orderedmap,不能按行重建")
    detail.official_rows = len(official)
    detail.live_rows = len(live)

    for key, value in official.items():
        counterpart = live.get(key)
        if counterpart is None:
            detail.restored_rows.append(key)
        elif counterpart != value:
            if isinstance(value, dict) and isinstance(counterpart, dict) and all(
                counterpart.get(sub) == val for sub, val in value.items()
            ):
                detail.nested_extended_rows.append(key)
            else:
                detail.reverted_rows.append(key)
    for key in live:
        if key in official:
            continue
        if policy.is_dropped_key(logical, key):
            continue
        detail.kept_rows.append(key)
        if not policy.is_content_key(logical, key):
            detail.unrecognized_rows.append(key)

    merged = merge_official(official, live)
    for key in list(merged):
        if key not in official and policy.is_dropped_key(logical, key):
            del merged[key]
    if merged == live:
        detail.changed = False
        return live_bytes, detail

    rebuilt = quest.build_node(merged)
    if quest.parse_node(rebuilt) != merged:
        raise RuntimeError(f"{logical or '<unknown>'}: 重建后回读不一致,拒绝产出")
    detail.changed = True
    return rebuilt, detail


# ------------------------------------------------------------------ 条目裁决

@dataclass(frozen=True)
class EntrySource:
    root: str
    rel: str
    crc: int
    size: int
    read: Callable[[], bytes]
    compress_size: int = 0


@dataclass
class Verdict:
    root: str
    rel: str
    logical: str | None
    action: str                       # keep / drop / rebuild
    reason: str
    data: bytes | None = None         # rebuild 时的新字节
    detail: RebuildDetail | None = None

    def as_dict(self) -> dict:
        payload = {
            "root": self.root, "rel": self.rel, "logical": self.logical,
            "action": self.action, "reason": self.reason,
        }
        if self.detail is not None:
            payload["detail"] = self.detail.as_dict()
        return payload


def judge_entry(
    source: EntrySource,
    baseline: OfficialBaseline,
    policy: Policy,
    *,
    official_file_action: str = "drop",
) -> Verdict:
    """单条目裁决:保留 / 丢弃 / 按行重建。"""
    logical = logical_of(source.rel)
    if source.rel in policy.drop_rels:
        return Verdict(source.root, source.rel, policy.drop_rels[source.rel], "drop",
                       "个人增强改写的官方资产,按 drop-list 不下发")
    official_identity = baseline.identity(source.root, source.rel)
    if official_identity is None:
        return Verdict(source.root, source.rel, logical, "keep", "官方基准里没有,判为自制内容")
    if official_identity == (source.crc, source.size):
        return Verdict(source.root, source.rel, logical, "keep", "与官方原值一致")

    official_bytes = baseline.get(source.root, source.rel)
    assert official_bytes is not None
    live_bytes = source.read()
    if official_bytes == live_bytes:
        return Verdict(source.root, source.rel, logical, "keep", "与官方原值一致")

    is_table = (logical or "").endswith(".orderedmap")
    if not is_table:
        try:
            is_table = isinstance(quest.parse_node(live_bytes), dict)
        except ValueError:
            is_table = False
    if is_table:
        data, detail = rebuild_table(official_bytes, live_bytes, logical=logical, policy=policy)
        if not detail.changed:
            return Verdict(source.root, source.rel, logical, "keep",
                           "官方行未被改写,只有内容新增行", detail=detail)
        return Verdict(source.root, source.rel, logical, "rebuild",
                       f"官方行回滚 {len(detail.reverted_rows)} 行"
                       + (f"、补回 {len(detail.restored_rows)} 行" if detail.restored_rows else ""),
                       data=data, detail=detail)
    if official_file_action == "revert":
        return Verdict(source.root, source.rel, logical, "rebuild",
                       "被改写的官方资产文件,回滚为官方原件", data=official_bytes)
    return Verdict(source.root, source.rel, logical, "drop",
                   "被改写的官方资产文件,不下发(收方保留自己的官方原件)")


def plan_content_only(
    sources: Iterable[EntrySource],
    baseline: OfficialBaseline,
    policy: Policy | None = None,
    *,
    official_file_action: str = "drop",
) -> tuple[dict[tuple[str, str], Verdict], dict]:
    """对终态条目集做完整裁决,返回 (verdicts, 摘要)。"""
    policy = policy or Policy()
    verdicts: dict[tuple[str, str], Verdict] = {}
    summary = {
        "entries": 0, "kept": 0, "dropped": 0, "rebuilt": 0,
        "revertedRows": 0, "restoredRows": 0, "nestedExtendedRows": 0,
        "droppedLogicals": [], "rebuiltTables": [], "unrecognizedAdditions": {},
    }
    for source in sources:
        verdict = judge_entry(source, baseline, policy,
                              official_file_action=official_file_action)
        verdicts[(source.root, source.rel)] = verdict
        summary["entries"] += 1
        if verdict.action == "drop":
            summary["dropped"] += 1
            summary["droppedLogicals"].append(verdict.logical or verdict.rel)
        elif verdict.action == "rebuild":
            summary["rebuilt"] += 1
        else:
            summary["kept"] += 1
        detail = verdict.detail
        if detail is None:
            continue
        summary["revertedRows"] += len(detail.reverted_rows)
        summary["restoredRows"] += len(detail.restored_rows)
        summary["nestedExtendedRows"] += len(detail.nested_extended_rows)
        if verdict.action == "rebuild":
            summary["rebuiltTables"].append({
                "logical": detail.logical or verdict.rel,
                "reverted": len(detail.reverted_rows),
                "restored": len(detail.restored_rows),
                "nestedExtended": len(detail.nested_extended_rows),
                "kept": len(detail.kept_rows),
            })
        if detail.unrecognized_rows:
            summary["unrecognizedAdditions"][detail.logical or verdict.rel] = \
                detail.unrecognized_rows
    summary["rebuiltTables"].sort(key=lambda item: -item["reverted"])
    return verdicts, summary


# ------------------------------------------------------------------ 金样校验

def verify_content_only(
    sources: Iterable[EntrySource],
    baseline: OfficialBaseline,
    policy: Policy | None = None,
    *,
    expect_content_keys: dict[str, Iterable[str]] | None = None,
) -> list[str]:
    """纯内容变体的成品校验,返回违规清单(空 = 通过)。

    逐条目断言:① 官方行逐行等于官方原值(允许官方行里多出嵌套子行);
    ② 官方行一个都不少;③ drop-list 里的条目确实不在包里;
    ④ expect_content_keys 指定的模式/角色行齐全。
    """
    policy = policy or Policy()
    expected = dict(expect_content_keys or {})
    problems: list[str] = []
    seen_keys: dict[str, set[str]] = {}
    for source in sources:
        logical = logical_of(source.rel)
        if source.rel in policy.drop_rels:
            problems.append(
                f"drop-list 条目仍在包里: {policy.drop_rels[source.rel]}")
            continue
        wanted = logical in expected
        official_identity = baseline.identity(source.root, source.rel)
        if official_identity is None or official_identity == (source.crc, source.size):
            if wanted:
                _record_keys(seen_keys, logical, source.read(), problems)
            continue
        official_bytes = baseline.get(source.root, source.rel)
        live_bytes = source.read()
        if official_bytes == live_bytes:
            if wanted:
                _record_keys(seen_keys, logical, live_bytes, problems)
            continue
        try:
            official = quest.parse_node(official_bytes)
            live = quest.parse_node(live_bytes)
        except ValueError:
            problems.append(f"{logical or source.rel}: 改写了官方非表文件,纯内容变体不该带")
            continue
        if not isinstance(official, dict) or not isinstance(live, dict):
            problems.append(f"{logical or source.rel}: 官方文件被改写且不是表,无法校验")
            continue
        name = logical or source.rel
        seen_keys[name] = set(live)
        for key, value in official.items():
            if key not in live:
                problems.append(f"{name}: 官方行 {key} 丢失")
                continue
            counterpart = live[key]
            if counterpart == value:
                continue
            if isinstance(value, dict) and isinstance(counterpart, dict) and all(
                counterpart.get(sub) == val for sub, val in value.items()
            ):
                continue  # 官方子行原值 + 模式新增子行
            problems.append(f"{name}: 官方行 {key} 与官方原值不符(增强残留)")
    for logical, keys in expected.items():
        present = seen_keys.get(logical)
        if present is None:
            problems.append(f"{logical}: 期望携带内容行,但包里没有这张表")
            continue
        missing = [key for key in keys if key not in present]
        if missing:
            problems.append(f"{logical}: 内容行缺失 {missing}")
    return problems


def _record_keys(
    seen: dict[str, set[str]], logical: str | None, data: bytes, problems: list[str]
) -> None:
    if not logical:
        return
    try:
        node = quest.parse_node(data)
    except ValueError:
        problems.append(f"{logical}: 无法解析为表,内容行校验落空")
        return
    if isinstance(node, dict):
        seen[logical] = set(node)


# ------------------------------------------------------------------ 链终态

def chain_sources(
    cdn_root: Path,
    repo_root: Path,
    *,
    since: str = OFFICIAL_TAIL,
    base: str | None = None,
) -> tuple[list[EntrySource], dict]:
    """重放 mod 链([since, tail])得到终态条目集,复用 wf_chain_squash 的可见图。"""
    import wf_chain_squash as squash  # 延迟导入:审计以外的用法不需要

    graph = squash.build_visible_graph(Path(cdn_root), Path(repo_root))
    start = base or since
    tail, path_edges = squash.find_path(graph, start)
    final, conflicts = squash.replay(graph, path_edges)
    sources: list[EntrySource] = []
    for name, entry in final.items():
        parsed = split_member(name)
        if parsed is None:
            continue
        root, rel = parsed

        def _read(zip_path: Path = entry.zip_path, member: str = name) -> bytes:
            with zipfile.ZipFile(zip_path) as archive:
                return archive.read(member)

        sources.append(EntrySource(root, rel, entry.crc, entry.size, _read,
                                   entry.compress_size))
    meta = {
        "since": start, "tail": tail, "edges": len(path_edges),
        "entries": len(sources), "conflicts": conflicts,
    }
    return sources, meta


# ------------------------------------------------------------------ CLI

def _resolve_cdn(cdn: str | None) -> Path:
    if cdn:
        return Path(cdn).resolve()
    try:
        return Path(core.resolve_cdn_root_lax())
    except Exception:
        return ROOT / ".cdn" / "cn"


def cmd_audit(args: argparse.Namespace) -> int:
    cdn_root = _resolve_cdn(args.cdn)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else ROOT
    baseline = OfficialBaseline(cdn_root, official_tail=args.official_tail)
    sources, meta = chain_sources(cdn_root, repo_root, since=args.since)
    verdicts, summary = plan_content_only(
        sources, baseline, Policy(), official_file_action=args.official_file_action)
    payload = {"chain": meta, "summary": summary,
               "drops": [v.as_dict() for v in verdicts.values() if v.action == "drop"],
               "rebuilds": [v.as_dict() for v in verdicts.values() if v.action == "rebuild"]}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"链: {meta['since']} → {meta['tail']}({meta['edges']} 条边,"
          f"终态 {meta['entries']} 条目)")
    print(f"裁决: 保留 {summary['kept']} / 重建 {summary['rebuilt']} / 丢弃 {summary['dropped']}")
    print(f"官方行回滚 {summary['revertedRows']} 行、补回 {summary['restoredRows']} 行、"
          f"保留模式嵌套子行 {summary['nestedExtendedRows']} 行")
    for table in summary["rebuiltTables"]:
        print(f"  [重建] {table['logical']}  回滚 {table['reverted']}"
              f" 补回 {table['restored']} 嵌套 {table['nestedExtended']}"
              f" 保留新增 {table['kept']}")
    for logical in summary["droppedLogicals"]:
        print(f"  [丢弃] {logical}")
    if summary["unrecognizedAdditions"]:
        print("[注意] 以下新增行不在内容识别规则内(已保留,请人工确认归属):")
        for logical, keys in summary["unrecognizedAdditions"].items():
            print(f"  {logical}: {keys[:12]}")
    return 0


def cmd_baseline(args: argparse.Namespace) -> int:
    baseline = OfficialBaseline(_resolve_cdn(args.cdn), official_tail=args.official_tail)
    for root in (args.root,) if args.root else CLIENT_ROOTS:
        try:
            stats = baseline.stats(root)
        except BaselineUnavailable as exc:
            print(f"[跳过] {root}: {exc}")
            continue
        print(f"{root}: {stats['entries']} 条官方条目(来自 {stats['archives']} 个官方归档)")
    print(f"钉死基准校验通过({len(PINNED_BASELINES)} 项)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cdn", help="CDN 根(默认 WF_CDN_DIR 或 <repo>/.cdn/cn)")
    parser.add_argument("--repo-root", help="仓库根(默认按脚本位置)")
    parser.add_argument("--official-tail", default=OFFICIAL_TAIL,
                        help=f"官方链尾版本(默认 {OFFICIAL_TAIL},之后的边全是我们发的)")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="审计当前链终态的增强面")
    audit.add_argument("--since", default=OFFICIAL_TAIL, help="链起点(默认官方链尾)")
    audit.add_argument("--official-file-action", choices=("drop", "revert"), default="drop",
                       help="被改写的官方资产文件:丢弃(默认)或回滚为官方原件")
    audit.add_argument("--json", action="store_true")
    audit.set_defaults(func=cmd_audit)

    base = sub.add_parser("baseline", help="预热/校验官方基准索引")
    base.add_argument("--root", choices=CLIENT_ROOTS, help="只处理某一层")
    base.add_argument("--prime", action="store_true", help="(兼容位:建索引本身即预热)")
    base.set_defaults(func=cmd_baseline)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except BaselineUnavailable as exc:
        print(f"[ERR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
