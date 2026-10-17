# -*- coding: utf-8 -*-
"""七角色季节换装版的规格表（规格驱动角色包框架的唯一身份来源）。

只描述「新角色是谁、母本是谁」；不读写任何 store。占用断言
(:func:`occupancy_problems`) 只读 live store 与仓库 ``assets/``，调用方决定何时执行。

角色专属覆盖：``mod-tools/wf_seasonal7_kit_<key>.py`` 可声明模块级
``TEXTS = {...}``（合并进 texts）与 ``SPEC = {...}``（覆盖可调字段，如
``backdrop_colors``/``gacha_se_map``/``required_capabilities``/``extra_keys``/``identity``）。
身份字段（cid/code/pkg_id/template_*）禁止被覆盖。

``identity``（character c27）只允许两种取值：自身 cid（校园先例，当前默认）或母本行的 c27
（``template_identity``，官方季节版惯例指向本体）。选哪种**待作者拍板**，框架两种都接受。
"""
from __future__ import annotations

import dataclasses
import glob
import hashlib
import importlib
import json
import re
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

ELEMENT_TOKENS = ("Red", "Blue", "Yellow", "Green", "White", "Black")
ELEMENT_COLORS = ("red", "blue", "yellow", "green", "white", "black")
ELEMENT_SE_DIRS = ("fire", "water", "thunder", "wind", "light", "dark")
ELEMENT_WORDS = ("火", "水", "雷", "风", "光", "暗")
STANCES = frozenset({"Attacker", "Tank", "Healer", "Supporter", "Jammer", "Balance"})
PF_TYPES = frozenset({0, 1, 2, 3, 4})
BATCH_DIR = "work/character_packs/seasonal7-20260916"
REQUIRES_CLIENT_BASE = "1.4.858"
PACKAGE_VERSION = "1.0.0"
IDENTITY_FIELDS = ("key", "cid", "code", "pkg_id", "workspace", "template_id",
                   "template_code", "template_element", "template_identity")
TEXT_FIELDS = ("name", "furigana", "profile", "title", "skill1", "desc1",
               "skill2", "desc2", "leader", "cv")


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


def _texts(name: str, furigana: str, title: str, profile: str, leader: str) -> dict[str, Any]:
    # skill1/desc1/skill2/desc2/cv = None：继承母本（占位 DSL 与母本相同，描述与行为一致）
    return {"name": name, "furigana": furigana, "title": title, "profile": profile,
            "leader": leader, "skill1": None, "desc1": None, "skill2": None,
            "desc2": None, "cv": None}


_RAW_SPECS: tuple[SeasonalSpec, ...] = (
    SeasonalSpec(
        key="regis", cid=139994, code="rec_android_seaside", pkg_id="s7-regis-20260916",
        workspace="work/character_packs/s7-regis", template_id=131020,
        template_code="rec_android_1anv", template_element=2, element=2,
        element_token="Yellow", rarity=5, pf_type=2, stance="Supporter", identity=139994, template_identity=231003,
        theme="白花礼服机人·海边约会",
        texts=_texts("雷吉斯", "LEIJISI", "海风与白花的机人绅士",
                     "换上白花礼服的机人绅士，把约会地点选在了夏日的海边栈桥。"
                     "他说这只是为了记录人类在海风中的表情——至于那顶草帽为什么准备了两顶，他笑而不答。",
                     "海边约会的邀请函"),
        backdrop_colors=((104, 162, 190), (30, 48, 74)),
    ),
    SeasonalSpec(
        key="tekuto", cid=139993, code="super_robot_tailcoat", pkg_id="s7-tekuto-20260916",
        workspace="work/character_packs/s7-tekuto", template_id=131092,
        template_code="super_robot", template_element=2, element=2,
        element_token="Yellow", rarity=5, pf_type=2, stance="Attacker", identity=139993, template_identity=131092,
        theme="黑黄燕尾礼服·重炮护卫",
        texts=_texts("特克托", "TEKETUO", "燕尾礼服的重炮护卫",
                     "被朋友们拉去参加舞会的机人青年，换上了黑黄配色的燕尾礼服。"
                     "为了保护大家，他把重炮也一起带进了会场——虽然大家都说那样一点都不优雅。",
                     "礼服下的守护炮火"),
        backdrop_colors=((170, 138, 46), (30, 26, 22)),
    ),
    SeasonalSpec(
        key="zantetsu", cid=159998, code="samurai_robot_plum", pkg_id="s7-zantetsu-20260916",
        workspace="work/character_packs/s7-zantetsu", template_id=151117,
        template_code="samurai_robot_smr22", template_element=4, element=4,
        element_token="White", rarity=5, pf_type=0, stance="Attacker", identity=159998, template_identity=131044,
        theme="白梅羽织·石栏陪伴",
        texts=_texts("斩铁", "ZHANTIE", "白梅羽织的钢铁武士",
                     "披上白梅纹羽织的钢铁武士，在早春的石栏边静静等待同伴。"
                     "梅香之中，他说剑道与陪伴同样需要耐心——然后又一次偷偷确认了茶点是否带齐。",
                     "梅下同行之约"),
        backdrop_colors=((196, 132, 150), (52, 36, 50)),
    ),
    SeasonalSpec(
        key="zehr", cid=159997, code="guildknight_leader_tavern", pkg_id="s7-zehr-20260916",
        workspace="work/character_packs/s7-zehr", template_id=151069,
        template_code="guildknight_leader", template_element=4, element=4,
        element_token="White", rarity=5, pf_type=0, stance="Attacker", identity=159997, template_identity=151069,
        theme="松衬衣与暗红领巾·酒馆中年骑士",
        texts=_texts("泽赫尔", "ZEHEER", "酒馆里的骑士团长",
                     "脱下团长制服、系上暗红领巾的中年骑士，今晚又溜进了熟悉的酒馆。"
                     "他总说只是来打听消息，可柜台后的老板很清楚，他只是想喝上一杯安静的酒。",
                     "酒馆打烊前的一杯"),
        backdrop_colors=((140, 60, 56), (36, 30, 28)),
    ),
    SeasonalSpec(
        key="philia", cid=159996, code="wind_oracle_yukata", pkg_id="s7-philia-20260916",
        workspace="work/character_packs/s7-philia", template_id=141165,
        template_code="wind_oracle_meteor23", template_element=3, element=4,
        element_token="White", rarity=5, pf_type=3, stance="Supporter", identity=159996, template_identity=141002,
        theme="白青浴衣·绣球与风剑",
        texts=_texts("菲莉亚", "FEILIYA", "绣球花下的光之巫女",
                     "穿上白青浴衣参加夏日祭典的巫女少女。绣球花开满了小路，"
                     "她握着缠绕光芒的风剑，想把这份热闹与温柔都守护下来。",
                     "绣球花开的祭典之夜"),
        backdrop_colors=((104, 170, 190), (32, 48, 74)),
        # 母本 141165 抽卡演出为风 SE（帧 5/35/95）；元素翻转为光时换同类光 SE
        # （三个目标 mp3 均在 live store，且都被官方光角色抽卡演出使用过）。
        gacha_se_map={
            "sound_effect/wind/se_impact_wind": "sound_effect/light/se_light_sparkling_hard_explosion",
            "sound_effect/wind/se_swirling_wind_stick": "sound_effect/light/se_light_bright_shooting_star",
            "sound_effect/wind/se_single_tornado": "sound_effect/light/se_light_release",
        },
    ),
    SeasonalSpec(
        key="primula", cid=169992, code="blackflower_wiz_yukata", pkg_id="s7-primula-20260916",
        workspace="work/character_packs/s7-primula", template_id=161123,
        template_code="blackflower_wiz_smr22", template_element=5, element=5,
        element_token="Black", rarity=5, pf_type=2, stance="Supporter", identity=169992, template_identity=161069,
        theme="紫百合浴衣·夏夜扇舞",
        texts=_texts("普莉姆拉", "PULIMULA", "夏夜扇舞的百合魔女",
                     "换上紫百合浴衣的少女魔女，在夏夜的祭典上第一次跳起了扇舞。"
                     "灯笼的光映在扇面上，她有些害羞，却还是想让大家看到自己绽放的样子。",
                     "百合绽放的夏夜"),
        backdrop_colors=((128, 86, 160), (36, 28, 56)),
    ),
    SeasonalSpec(
        key="yuki", cid=129991, code="psychic_yuki_swim", pkg_id="s7-yuki-20260916",
        workspace="work/character_packs/s7-yuki", template_id=121147,
        template_code="psychic_yuki_ny23", template_element=1, element=1,
        element_token="Blue", rarity=5, pf_type=4, stance="Supporter", identity=129991, template_identity=121070,
        theme="蓝白泳装·海边与雪花屏障",
        texts=_texts("见岛勇希", "JIANDAOYONGXI", "海边雪花的结界少女",
                     "换上蓝白泳装来到海边的涩谷少女。在炽热的阳光下，"
                     "她展开雪花般的结界为大家遮阳——虽然嘴上说着只是顺便，笑容却一直没有停下。",
                     "海边的雪花结界"),
        backdrop_colors=((86, 148, 206), (26, 42, 76)),
    ),
)


def _validate_static(specs: tuple[SeasonalSpec, ...]) -> None:
    seen: dict[str, dict[Any, str]] = {name: {} for name in (
        "key", "cid", "code", "pkg_id", "workspace")}
    for spec in specs:
        for name in seen:
            value = getattr(spec, name)
            if value in seen[name]:
                raise AssertionError(f"duplicate spec {name}={value!r}: "
                                     f"{seen[name][value]} / {spec.key}")
            seen[name][value] = spec.key
        if not re.fullmatch(r"[a-z][a-z0-9_]*", spec.code):
            raise AssertionError(f"{spec.key}: invalid code_name {spec.code}")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", spec.pkg_id):
            raise AssertionError(f"{spec.key}: invalid package_id {spec.pkg_id}")
        if spec.code == spec.template_code or spec.cid == spec.template_id:
            raise AssertionError(f"{spec.key}: target equals template")
        # 新 code 可能以母本 code 为前缀（super_robot → super_robot_tailcoat），
        # common 的替换一律按路径段/整格边界匹配，不做裸子串替换。
        if not (0 <= spec.element <= 5) or ELEMENT_TOKENS[spec.element] != spec.element_token:
            raise AssertionError(f"{spec.key}: element {spec.element} != token {spec.element_token}")
        if spec.stance not in STANCES:
            raise AssertionError(f"{spec.key}: illegal stance {spec.stance}")
        if spec.pf_type not in PF_TYPES:
            raise AssertionError(f"{spec.key}: illegal pf_type {spec.pf_type}")
        if spec.rarity != 5:
            raise AssertionError(f"{spec.key}: seasonal batch is ★5 only")
        if spec.identity not in (spec.cid, spec.template_identity):
            raise AssertionError(f"{spec.key}: identity {spec.identity} must be cid {spec.cid} "
                                 f"or template c27 {spec.template_identity}")
        if not isinstance(spec.extra_keys, Mapping):
            raise AssertionError(f"{spec.key}: extra_keys must be a mapping")
        for logical, keys in spec.extra_keys.items():
            if not (isinstance(logical, str) and (logical.endswith(".orderedmap") or logical.endswith(".json"))
                    and not logical.startswith("/") and ".." not in logical.split("/")):
                raise AssertionError(f"{spec.key}: extra_keys logical invalid: {logical!r}")
            if isinstance(keys, str) or not all(isinstance(k, str) and k for k in keys):
                raise AssertionError(f"{spec.key}: extra_keys[{logical}] must be a sequence of non-empty str")
        if set(spec.texts) != set(TEXT_FIELDS):
            raise AssertionError(f"{spec.key}: texts fields {sorted(spec.texts)}")
        if spec.element_flip:
            old_dir = ELEMENT_SE_DIRS[spec.template_element]
            for src, dst in spec.gacha_se_map.items():
                if not src.startswith(f"sound_effect/{old_dir}/"):
                    raise AssertionError(f"{spec.key}: gacha SE map source {src} not old element")
        if spec.cid // 10000 != {0: 11, 1: 12, 2: 13, 3: 14, 4: 15, 5: 16}[spec.element]:
            raise AssertionError(f"{spec.key}: cid {spec.cid} does not follow element prefix")
        if not (Path(spec.workspace).as_posix().startswith("work/character_packs/s7-")):
            raise AssertionError(f"{spec.key}: workspace outside s7-* sandbox")


_validate_static(_RAW_SPECS)
SPECS: dict[str, SeasonalSpec] = {spec.key: spec for spec in _RAW_SPECS}


def kit_module_name(key: str) -> str:
    return f"wf_seasonal7_kit_{key}"


def load_kit_module(key: str):
    """导入角色 kit 模块；不存在返回 None。"""
    if not (HERE / f"{kit_module_name(key)}.py").is_file():
        return None
    return importlib.import_module(kit_module_name(key))


def get_spec(key: str, *, with_kit: bool = True) -> SeasonalSpec:
    if key not in SPECS:
        raise KeyError(f"unknown seasonal7 character: {key}; known {sorted(SPECS)}")
    spec = SPECS[key]
    if not with_kit:
        return spec
    module = load_kit_module(key)
    if module is None:
        return spec
    changes: dict[str, Any] = {}
    overrides = dict(getattr(module, "SPEC", {}) or {})
    for name in overrides:
        if name in IDENTITY_FIELDS or name == "texts":
            raise ValueError(f"kit SPEC may not override identity/texts field {name}")
        if name not in {f.name for f in dataclasses.fields(SeasonalSpec)}:
            raise ValueError(f"kit SPEC unknown field {name}")
    if "extra_keys" in overrides:
        overrides["extra_keys"] = {str(k): tuple(v) for k, v in dict(overrides["extra_keys"]).items()}
    changes.update(overrides)
    texts = dict(spec.texts)
    for name, value in dict(getattr(module, "TEXTS", {}) or {}).items():
        if name not in TEXT_FIELDS:
            raise ValueError(f"kit TEXTS unknown field {name}")
        texts[name] = value
    changes["texts"] = texts
    merged = dataclasses.replace(spec, **changes)
    _validate_static(tuple(merged if s.key == key else s for s in _RAW_SPECS))
    return merged


def all_keys() -> list[str]:
    return list(SPECS)


# ---------------------------------------------------------------- 占用断言（只读）

SERVER_JSONS = ("cdndata/character.json", "cdndata/character_text.json",
                "character.json", "mana_node.json", "mana_board.json")


def _token_regex(tokens: list[str]) -> re.Pattern:
    body = "|".join(re.escape(t) for t in sorted(set(tokens), key=len, reverse=True))
    return re.compile(r"(?<![0-9A-Za-z_])(" + body + r")(?![0-9A-Za-z_])")


def _fingerprint(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        try:
            st = path.stat()
        except OSError:
            continue
        digest.update(f"{path}|{st.st_size}|{st.st_mtime_ns}\n".encode("utf-8"))
    return digest.hexdigest()


def occupancy_problems(specs: list[SeasonalSpec], *, repo_root: Path, store: Path,
                       cache_path: Path | None = None) -> dict[str, list[str]]:
    """每个 spec 的占用问题清单（空 = 未占用）。

    检查：cid / 队长键 / cid*10+slot 词条键 / code_name（character c0/c8、action_skill 外层键）
    在 live store；``character/<code>/`` 37 项必需资产与母本同名路径在三根；
    cid、词条键、code 作为独立 token 出现在仓库 ``assets/*.json``/``assets/cdndata/*.json``；
    玛纳节点前缀 ``cid*2`` + 3 位在 live 客户端两表与服务端两 JSON 中未出现；
    ``spec.extra_keys``（kit 自有键：unique_condition / custom_ability_string / power_flip_action /
    switched_action_skill / multiball …）在 live 表或仓库 JSON 中未占用，且批内互斥。
    缓存指纹包含上述全部表文件与 JSON。
    """
    import wf_assets
    import wf_mod_tool as core
    from wf_character_requirements import char_asset_requirements

    json_files = [Path(p) for p in sorted(glob.glob(str(repo_root / "assets" / "*.json"))
                                         + glob.glob(str(repo_root / "assets" / "cdndata" / "*.json")))]
    table_logicals = ["master/character/character.orderedmap",
                      "master/ability/ability.orderedmap",
                      "master/ability/leader_ability.orderedmap",
                      "master/skill/action_skill.orderedmap",
                      "master/mana_board/mana_node.orderedmap",
                      "master/generated/mana_board.orderedmap",
                      "master/character/character_text.orderedmap"]
    extra_logicals = sorted({lg for s in specs for lg in s.extra_keys})
    extra_client = [lg for lg in extra_logicals if lg.endswith(".orderedmap")]
    extra_server = [lg for lg in extra_logicals if lg.endswith(".json")]
    fp_paths = json_files + [core.table_path(store, lg) for lg in table_logicals + extra_client]         + [repo_root / "assets" / Path(*lg.split("/")) for lg in extra_server]
    fingerprint = _fingerprint(fp_paths)
    spec_sig = hashlib.sha256(json.dumps([s.to_dict() for s in specs], sort_keys=True,
                                         ensure_ascii=False).encode("utf-8")).hexdigest()
    if cache_path is not None and cache_path.is_file():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("fingerprint") == fingerprint and cached.get("spec_sig") == spec_sig:
                return {k: list(v) for k, v in cached["problems"].items()}
        except (OSError, ValueError, KeyError):
            pass

    problems: dict[str, list[str]] = {s.key: [] for s in specs}
    chars = core.load_table(table_logicals[0], store).text_rows()
    abilities = core.load_table(table_logicals[1], store).text_rows()
    leaders = core.load_table(table_logicals[2], store).text_rows()
    texts = core.load_table(table_logicals[6], store).text_rows()
    action = core.read_orderedmap_file_raw_rows(core.table_path(store, table_logicals[3]),
                                                table_logicals[3])
    char_codes: dict[str, str] = {}
    for key, text in chars.items():
        rows = core.read_csv_lines(text)
        if rows and rows[0]:
            char_codes[rows[0][0]] = key
            if len(rows[0]) > 8:
                char_codes.setdefault(rows[0][8], key)

    def mana_ids(logical: str) -> set[str]:
        om = core.read_orderedmap_file_raw_rows(core.table_path(store, logical), logical)
        found: set[str] = set()
        for blob in om.rows:
            try:
                boards = core.read_orderedmap_raw_rows_from_bytes(blob, "boards")
                for board in boards.rows:
                    slots = core.read_orderedmap_raw_rows_from_bytes(board, "slots")
                    for raw in slots.rows:
                        for row in core.read_csv_lines(zlib.decompress(raw).decode("utf-8")):
                            if row:
                                found.add(row[0])
            except Exception:
                continue
        return found

    live_mana = mana_ids(table_logicals[4]) | mana_ids(table_logicals[5])
    for spec in specs:
        out = problems[spec.key]
        if spec.template_id_s not in chars:
            out.append(f"template {spec.template_id} missing from live character table")
        for label, table, keys in (("character", chars, [spec.cid_s]),
                                   ("character_text", texts, [spec.cid_s]),
                                   ("leader_ability", leaders, [spec.cid_s]),
                                   ("ability", abilities, spec.ability_keys)):
            for key in keys:
                if key in table:
                    out.append(f"live {label} key occupied: {key}")
        if spec.code in char_codes:
            out.append(f"live code_name occupied by character {char_codes[spec.code]}: {spec.code}")
        if spec.code in action.keys:
            out.append(f"live action_skill outer key occupied: {spec.code}")
        for req in char_asset_requirements(spec.code):
            if wf_assets.locate(store, req.logical_path):
                out.append(f"live asset path occupied: {req.logical_path}")
        pattern = re.compile(r"^" + re.escape(spec.mana_prefix) + r"\d{3}$")
        hits = sorted(n for n in live_mana if pattern.match(n))
        if hits:
            out.append(f"live mana node prefix {spec.mana_prefix} occupied: {hits[:5]}")
    # ---- kit 自有键（extra_keys）：live 占用 + 批内互斥
    extra_live: dict[str, set[str]] = {}
    for logical in extra_client:
        path = core.table_path(store, logical)
        extra_live[logical] = set(core.read_orderedmap_file_raw_rows(path, logical).keys)             if path.is_file() else set()
    for logical in extra_server:
        path = repo_root / "assets" / Path(*logical.split("/"))
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except ValueError:
            data = {}
        extra_live[logical] = set(data) if isinstance(data, dict) else set()
    batch_owner: dict[tuple[str, str], str] = {}
    for spec in specs:
        for logical, keys in sorted(spec.extra_keys.items()):
            for key in keys:
                if key in extra_live.get(logical, set()):
                    problems[spec.key].append(f"live extra key occupied: {logical}#{key}")
                other = batch_owner.setdefault((logical, key), spec.key)
                if other != spec.key:
                    problems[spec.key].append(f"extra key shared within batch with {other}: {logical}#{key}")
                    problems[other].append(f"extra key shared within batch with {spec.key}: {logical}#{key}")
    token_owner: dict[str, str] = {}
    for spec in specs:
        for token in [spec.cid_s, spec.code, *spec.ability_keys]:
            token_owner[token] = spec.key
    mana_re = re.compile(r"(?<![0-9])(" + "|".join(re.escape(s.mana_prefix) for s in specs)
                         + r")\d{3}(?![0-9])")
    prefix_owner = {s.mana_prefix: s.key for s in specs}
    token_re = _token_regex(list(token_owner))
    for path in json_files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(repo_root).as_posix()
        for token in sorted(set(token_re.findall(text))):
            problems[token_owner[token]].append(f"{rel}: token {token} occupied")
        if path.name in ("mana_node.json", "mana_board.json"):
            for prefix in sorted(set(mana_re.findall(text))):
                problems[prefix_owner[prefix]].append(f"{rel}: mana prefix {prefix} occupied")
    if cache_path is not None:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps({"fingerprint": fingerprint, "spec_sig": spec_sig,
                                              "problems": problems}, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        except OSError:
            pass
    return problems


def assert_unoccupied(specs: list[SeasonalSpec], *, repo_root: Path, store: Path,
                      cache_path: Path | None = None) -> None:
    problems = occupancy_problems(specs, repo_root=repo_root, store=store, cache_path=cache_path)
    bad = {k: v for k, v in problems.items() if v}
    if bad:
        raise AssertionError("seasonal7 identity occupied: " + json.dumps(bad, ensure_ascii=False))


if __name__ == "__main__":
    print(json.dumps({k: s.to_dict() for k, s in SPECS.items()}, ensure_ascii=False, indent=1))
