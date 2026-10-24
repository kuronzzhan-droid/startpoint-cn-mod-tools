# -*- coding: utf-8 -*-
"""发布/分享出口的客户端能力闸门（扩展词条框架 B1-0，设计稿 4.9）。

一批待投递的数据要求接收方客户端具备哪些 capability，按下列来源传递推导：
  1. 词条五表（ability / leader_ability / ability_soul / equipment_enhancement_ability / ex_ability）
     每条记录按触发模式实际解析的块：先查「表 × 补丁构造」是否在补丁扩展过的解析器范围
     （wf_client_patch_scope，范围外 = C7050，任何档案都拒绝），再取补丁构造（422/423/424/724）
     与解析器扩展的 capability → wf_client_legality.required_client_capabilities；
  2. 同一批记录里引用固有状态 uid 的列（case 声明 unique_condition_id 的块；422/423/424 借用该列
     装参数/规则码，不算）→ 该 uid 的 string_id 以 ``wfx:`` 开头 → 效果码 → capability；
     uid 按「本批 unique_condition ⊕ 出口给的上下文（源 store / 链尾 / 同批其他边）」解析；
     以 wfx 开头却不是登记前缀的 sid（写错、首尾空白）按静默失效拒绝；
  3. DSL 里的 ``ACUnique(uid)`` 与 ``Trace("wfx:…")``；以及伤害段覆盖（根头 / CreateHitArea 的
     buffTargetAs ≥100 → damage-type-rules-v1，语义级：未装补丁读成 0，按技能伤害结算，不崩，
     判据 = wf_battle_rules.dsl_capabilities，与诅咒武器生成器共用）；
  4. custom_ability_string 键：desc_override_*（面板覆盖）、wfx_text_<uid>；
  5. unique_condition 的 wfx 行本身（没被引用也报，避免孤儿）。
再与接收方档案（client_profiles.json）比对：缺崩溃级 / 语义必需级 → 拒绝；外观级 → 警告。
没有豁免开关：数据要发给谁，就换成谁的档案；档案里没有的能力，只能改数据。

**无 wfx 行、也不用任何补丁构造的数据，在任何档案上都是空操作通过。**
例外：补丁构造写在补丁没扩展解析器的表里（如队长表 422）是崩溃级，任何档案都拒绝。

出口覆盖见 GATED_EXITS / UNGATED_EXITS（tests/test_wfx_gate.py 钉住）：闸门接在出口包装层，
不在共享原语里；没接的出口逐个写明原因，改这些出口时同步这两张表。
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

MOD_DIR = Path(__file__).resolve().parent
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_battle_rules  # noqa: E402
import wf_wfx  # noqa: E402
import wfx_registry  # noqa: E402

PROFILES_PATH = MOD_DIR / "client_profiles.json"

ABILITY_TABLE_LOGICALS = {
    "ability": "master/ability/ability.orderedmap",
    "leader_ability": "master/ability/leader_ability.orderedmap",
    "ability_soul": "master/ability/ability_soul.orderedmap",
    "equipment_enhancement_ability":
        "master/equipment_enhancement/equipment_enhancement_ability.orderedmap",
    "ex_ability": "master/ex_boost/ex_ability.orderedmap",
}
UNIQUE_CONDITION_LOGICAL = "master/character/unique_condition.orderedmap"
CUSTOM_STRING_LOGICAL = "master/string/custom_ability_string.orderedmap"
CHARACTER_LOGICAL = "master/character/character.orderedmap"
GATE_TABLE_LOGICALS = {
    **ABILITY_TABLE_LOGICALS,
    "unique_condition": UNIQUE_CONDITION_LOGICAL,
    "custom_ability_string": CUSTOM_STRING_LOGICAL,
    "character": CHARACTER_LOGICAL,
}
DSL_SUFFIX = ".action.dsl.amf3.deflate"
# 触发模式 → 客户端构造函数实际解析的块（瞬发行的 instant_precontent 也会被解析）。
MODE_BLOCKS = {
    "0": ("precondition1", "precondition2", "precondition3",
          "instant_trigger", "instant_precontent", "instant_content"),
    "1": ("precondition1", "precondition2", "precondition3",
          "during_accumulation_trigger", "during_trigger", "during_content"),
    "2": (),
}
LEVEL_TAGS = {"crash": "会崩", "semantic": "会静默失效", "cosmetic": "文字不生效"}
_MAX_INFLATE = 64 << 20

#: 接了能力闸门的出口（模块 → 接法）。
GATED_EXITS = {
    "wf_publish": "main()：打包/--list 前 check_publish，--client-profile 默认 local-mumu",
    "wf_character_flow": "preflight/publish：check_package，--client-profile 默认 local-mumu",
    "wf_release": "CLI publish（绕过 flow 直接发包）：check_package，--client-profile 默认 local-mumu",
    "wf_share_variant": "plan/build：每个变体 check_entries，--client-profile 必填，可叠加随包补丁（裁决 #3）",
    "wf_scoped_release": "publish_archives_and_manifest：逐边 check_entries，client_profile 必填",
    "wf_local_scoped_release": "publish_local_scoped_plans：client_profile 透传给 wf_scoped_release",
}
#: 尚未接闸门的出口与原因（有意识的豁免/待办，不是遗漏）。
UNGATED_EXITS = {
    "wf_local_cdn_publish": "只能发布 COMPATIBILITY_EDGE_DIGEST 钉死的 1.4.311→1.4.312 冻结边，内容不可变，装不进新数据",
    "wf_balance_suite --export-pack": "只打包文件名带 -mod 的旧边（止于 1.4.200；wf_publish 已不再产出该命名），不含补丁构造与 wfx 数据",
    "wf_dev_catalog export-pack": "整链归档逐字节导出给 dev fork 收方；B1-0 未接闸门（待作者决定是否强制 --client-profile）。"
                                  "链上已有装备表 423 等本机专属能力，导出前须人工核对收方补丁",
    "wf_dev_catalog export-overlay": "公开 Release Patch Overlay 批次；同上未接闸门；公开链投递每次都须作者当次明说（CLAUDE.md 授权分级）",
}


class GateError(ValueError):
    """档案不存在 / 档案文件不合法等无法判定的情况。"""


# ------------------------------------------------------------------ 档案

@dataclass(frozen=True)
class ClientProfile:
    name: str
    capabilities: frozenset[str]
    description: str = ""


def _read_profiles(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GateError(f"客户端档案文件读不出: {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise GateError(f"{path} schema_version 必须为 1")
    if not isinstance(data.get("profiles"), dict) or not data["profiles"]:
        raise GateError(f"{path} profiles 必须是非空对象")
    return data


def load_profiles(path: Path = PROFILES_PATH) -> dict[str, ClientProfile]:
    """读取并校验：capability 必须登记在注册表，且不能声明 status=planned（尚无 APK）的能力。"""
    data = _read_profiles(path)
    if Path(path).resolve() == PROFILES_PATH.resolve():
        from wf.apk.local_registry import registrations
        for record in registrations():
            data["profiles"].setdefault(record["profile_id"], record["profile"])
    catalog = wfx_registry.capabilities()
    profiles: dict[str, ClientProfile] = {}
    for name, entry in data["profiles"].items():
        names = entry.get("capabilities") if isinstance(entry, dict) else None
        if not isinstance(names, list) or not all(isinstance(item, str) for item in names):
            raise GateError(f"档案 {name} 的 capabilities 必须是字符串列表")
        if len(set(names)) != len(names):
            raise GateError(f"档案 {name} 的 capabilities 有重复")
        unknown = sorted(set(names) - set(catalog))
        if unknown:
            raise GateError(f"档案 {name} 声明了注册表里没有的 capability: {unknown}")
        from wf.wfx_semantics import candidate_profile_problems
        problems = candidate_profile_problems(entry, names, catalog)
        if problems:
            raise GateError(f"档案 {name}：" + "；".join(problems))
        profiles[name] = ClientProfile(name, frozenset(names), str(entry.get("description", "")))
    default = data.get("default_publish_profile")
    if default not in profiles:
        raise GateError(f"default_publish_profile={default!r} 不是已登记的档案")
    return profiles


def default_publish_profile(path: Path = PROFILES_PATH) -> str:
    return str(_read_profiles(path)["default_publish_profile"])


def resolve_profile(profile: str | ClientProfile, path: Path = PROFILES_PATH) -> ClientProfile:
    if isinstance(profile, ClientProfile):
        return profile
    profiles = load_profiles(path)
    if profile not in profiles:
        raise GateError(f"未知客户端档案 {profile!r}；已登记: {', '.join(profiles)}（{path.name}）")
    return profiles[profile]


# ------------------------------------------------------------------ 随包补丁（作者裁决 #3）

@dataclass(frozen=True)
class BundledPatch:
    """随分享包一起交付的客户端补丁包：接收方档案按「装上它之后」计算（作者裁决 2026-09-28 #3）。

    证据是补丁构建器产出的报告（prepare-report.json / patch-report.json）里的 capabilities_added：
    只并入这个补丁**本层新增**的能力。build-summary 的 candidate_capabilities 是整包（含继承层）
    能力，等于假设收方与本机同基线，裁决 #3 明确不许，所以不接受。"""
    report: str
    sha256: str
    name: str
    capabilities_added: tuple[str, ...]
    base_abc_sha256: str | None = None
    target_abc_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "report": self.report, "reportSha256": self.sha256,
                "capabilitiesAdded": list(self.capabilities_added),
                "baseAbcSha256": self.base_abc_sha256, "targetAbcSha256": self.target_abc_sha256}


def load_bundled_patch(path: Path | str) -> BundledPatch:
    import hashlib

    source = Path(path)
    try:
        raw = source.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise GateError(f"随包补丁报告读不出: {source}: {exc}") from exc
    if not isinstance(data, dict):
        raise GateError(f"随包补丁报告 {source} 不是 JSON 对象")
    added = data.get("capabilities_added")
    if added is None:
        hint = ("(这是整包 build-summary:candidate_capabilities 含继承层,不能当作随包补丁的新增能力;"
                "改给同目录 swf/ 下的 prepare-report.json 或 patch-report.json)"
                if "candidate_capabilities" in data else "")
        raise GateError(f"随包补丁报告 {source} 没有 capabilities_added{hint}")
    if not isinstance(added, list) or not added or not all(isinstance(item, str) for item in added):
        raise GateError(f"随包补丁报告 {source} 的 capabilities_added 必须是非空字符串列表")
    catalog = wfx_registry.capabilities()
    unknown = sorted(set(added) - set(catalog))
    if unknown:
        raise GateError(f"随包补丁 {source} 声明了注册表里没有的 capability: {unknown}")
    unavailable = sorted(f"{item} (status={catalog[item]['status']})"
                         for item in added if catalog[item]["status"] != "shipped")
    if unavailable:
        raise GateError(f"随包补丁 {source} 声明了不可随包发布的 capability: {unavailable}")

    def first(*keys: str) -> str | None:
        for key in keys:
            if isinstance(data.get(key), str) and data[key]:
                return data[key]
        return None

    name = first("patch", "capability") or source.parent.parent.name or source.stem
    return BundledPatch(str(source), hashlib.sha256(raw).hexdigest(), name, tuple(added),
                        first("source_abc_sha256", "swf_abc_sha256", "base_abc_sha256"),
                        first("output_abc_sha256", "target_abc_sha256"))


def with_bundled_patches(profile: ClientProfile, patches: Iterable[BundledPatch]) -> ClientProfile:
    """档案 ∪ 随包补丁新增能力；没有随包补丁时原样返回（不改名）。"""
    patches = list(patches)
    if not patches:
        return profile
    added = frozenset(item for patch in patches for item in patch.capabilities_added)
    names = ", ".join(patch.name for patch in patches)
    return ClientProfile(f"{profile.name}+随包补丁", profile.capabilities | added,
                         f"{profile.description}; 装上随包补丁 {names} 之后")


# ------------------------------------------------------------------ 报告

@dataclass(frozen=True)
class Requirement:
    capability: str
    level: str
    source: str
    reason: str


@dataclass
class GateReport:
    profile: str
    capabilities: frozenset[str]
    requirements: list[Requirement] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def required_capabilities(self) -> list[str]:
        return sorted({item.capability for item in self.requirements})

    def missing_capabilities(self) -> list[str]:
        return sorted({item.capability for item in self.requirements} - set(self.capabilities))

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "ok": self.ok,
            "required_capabilities": self.required_capabilities(),
            "missing_capabilities": self.missing_capabilities(),
            "requirement_count": len(self.requirements),
            "problems": list(self.problems),
            "warnings": list(self.warnings),
        }

    def lines(self) -> list[str]:
        """人读摘要（只含 GBK 可编码字符：wf_publish 预检子进程的 stdout 是 cp936）。"""
        required = self.required_capabilities()
        if self.ok:
            head = (f"[通过] 档案 {self.profile}: 本批数据无客户端能力需求" if not required else
                    f"[通过] 档案 {self.profile}: 需要 {len(required)} 项能力,均已具备 ({', '.join(required)})")
            out = [head]
        else:
            out = [f"[阻断] 档案 {self.profile}: {problem}" for problem in self.problems]
        out += [f"[警告] 档案 {self.profile}: {warning}" for warning in self.warnings]
        return out


# ------------------------------------------------------------------ 解码

def _records(text: str) -> list[list[str]]:
    if not text:
        return []
    return [row for row in csv.reader(io.StringIO(text)) if row]


def _norm_uid(value: Any) -> str | None:
    text = str(value).strip()
    if text.lstrip("-").isdigit():
        return str(int(text))
    return None


def decode_rows(payload: bytes) -> dict[str, str]:
    """orderedmap → {键: 行文本}；逐行容错（未压缩的明文行按原字节解），索引坏则抛。"""
    import wf_mod_tool as core

    keys, pairs, index_len = core.parse_index(payload)
    data = payload[4 + index_len:]
    out: dict[str, str] = {}
    previous = 0
    for key, (_key_end, row_end) in zip(keys, pairs):
        chunk = data[previous:row_end]
        previous = row_end
        if not chunk:
            out[key] = ""
            continue
        try:
            raw = zlib.decompress(chunk)
        except zlib.error:
            raw = chunk
        out[key] = raw.decode("utf-8", errors="replace")
    return out


def decode_keys(payload: bytes) -> list[str]:
    import wf_mod_tool as core

    return list(core.parse_index(payload)[0])


def _inflate(payload: bytes) -> bytes | None:
    try:
        inflater = zlib.decompressobj(-15)
        data = inflater.decompress(payload, _MAX_INFLATE)
        if inflater.unconsumed_tail:
            return None
        return data
    except (zlib.error, ValueError, TypeError):
        return None


def _parse_dsl(data: bytes) -> Any:
    import wf_dsl

    return wf_dsl.parse_dsl(data)["tree"]


# ------------------------------------------------------------------ 推导

def _wfx_index(published: Mapping[str, str] | None,
               context: Mapping[str, str] | None) -> dict[str, tuple[str, str, Any]]:
    """uid → (sid, 分类, WfxSpec 或错误串)；published 覆盖 context。只收 wfx 家族的行。"""
    merged: dict[str, str] = dict(context or {})
    merged.update(published or {})
    index: dict[str, tuple[str, str, Any]] = {}
    for key, text in merged.items():
        uid = _norm_uid(key)
        records = _records(text)
        if uid is None or not records:
            continue
        sid = records[0][0]            # 不 strip:客户端按原值 split(":"),首尾空白即不是效果行
        kind = wf_wfx.classify_sid(sid)
        if kind is None:
            continue
        if kind == "effect":
            try:
                index[uid] = (sid, kind, wf_wfx.decode_sid(sid))
            except wf_wfx.WfxError as exc:
                index[uid] = (sid, kind, str(exc))
        else:
            index[uid] = (sid, kind, None)
    return index


def _spec_requirements(spec: wf_wfx.WfxSpec, source: str, why: str) -> list[Requirement]:
    effect = spec.effect or {}
    out = []
    for capability in wf_wfx.required_capabilities(spec):
        level = wfx_registry.capability_level(capability) or "crash"
        if capability == effect.get("capability") and effect.get("gate") == "warn":
            level = "cosmetic"
        out.append(Requirement(capability, level, source,
                               f"{why} 码 {spec.code} {effect.get('label', '')}"))
    return out


class _Collector:
    def __init__(self, index: dict[str, tuple[str, str, Any]]):
        self.index = index
        self.requirements: list[Requirement] = []
        self.problems: list[str] = []
        self.warnings: list[str] = []

    def configuration(self, table, key, value, source):
        from wf.wfx_config import configuration_checks
        names, problems, warnings = configuration_checks(table, key, value)
        self.problems.extend(f"{source}：{item}" for item in problems)
        self.warnings.extend(f"{source}：{item}" for item in warnings)
        for name in names:
            self.requirements.append(Requirement(
                name, wfx_registry.capability_level(name) or "semantic", source, "v35配置标记"))

    def uid_ref(self, uid_value: Any, source: str, why: str) -> None:
        uid = _norm_uid(uid_value)
        if uid is None or uid not in self.index:
            return
        sid, kind, spec = self.index[uid]
        if kind == "effect" and isinstance(spec, wf_wfx.WfxSpec):
            self.requirements += _spec_requirements(spec, source, f"{why} uid {uid}")
            if spec.effect.get("todo"):
                self.warnings.append(f"{source} uid {uid}：" + "；".join(spec.effect["todo"]))
            if spec.effect.get("stack_note"):
                self.warnings.append(f"{source} uid {uid}：{spec.effect['stack_note']}")
        elif kind == "effect":
            self.problems.append(f"{source} {why}了 uid {uid},其 string_id {sid!r} 不合法: {spec}")
        elif kind == "reserved":
            self.problems.append(f"{source} {why}了 uid {uid},其 string_id {sid!r} 使用保留前缀(尚无客户端实现)")
        elif kind == "lookalike":
            self.problems.append(
                f"[{LEVEL_TAGS['semantic']}] {source} {why}了 uid {uid},其 string_id {sid!r} 以 wfx 开头"
                f"但不是登记前缀 {wf_wfx.sid_prefix()!r}(多半写错):客户端不会当作效果状态")


def _block_uid_columns(kind: str) -> dict[str, tuple[int, int]]:
    """块名 → (块基址, unique_condition_id 在块内的偏移)。"""
    import wf_describe
    from wf_client_legality import BLOCK_FIELDS_KEY

    blocks = {name: int(index) for name, index in wf_describe.layout(kind)["blocks"].items()}
    fields = wf_describe.enum_map()["block_fields"]
    out: dict[str, tuple[int, int]] = {}
    for block, base in blocks.items():
        for offset, name, _label in fields.get(BLOCK_FIELDS_KEY.get(block, block), ()):
            if name == "unique_condition_id":
                out[block] = (base, int(offset))
    return out


def _ability_requirements(kind: str, key: str, text: str, collector: _Collector) -> None:
    import wf_describe
    from wf_client_legality import BLOCK_CASE_KEY, TRIGGER_MODE_BLOCKS, required_client_capabilities
    from wf_client_patch_scope import patch_parser_scope_problems
    from wf.wfx_tags import ability_tags

    layout = wf_describe.layout(kind)
    blocks = {name: int(index) for name, index in layout["blocks"].items()}
    cases = wf_describe.enum_map()["cases"]
    uid_columns = _block_uid_columns(kind)
    borrowing = wfx_registry.patch_kinds_borrowing_uid_column()
    precontent_kinds = set(wfx_registry.load()["uid_reference_blocks"]["instant_precontent_uid_kinds"])
    mode_col = blocks["precondition1"] - 1
    for number, record in enumerate(_records(text)):
        source = f"{kind}[{key}]#{number}"

        def cell(index: int) -> str:
            return (record[index] if index < len(record) else "").strip()

        # 1a. 表 × 构造是否在补丁扩展过的解析器范围(设计稿 4.9 第 1 条)。范围外 = 该表 parseAt 抛
        #     C7050,与接收方装了哪些补丁无关(没有任何已发布补丁扩展它):任何档案都拒绝。
        #     required_client_capabilities 对范围外的构造刻意返回空,只看它会漏掉这类行。
        for problem in patch_parser_scope_problems(
                kind, record, blocks, TRIGGER_MODE_BLOCKS.get(cell(mode_col), ())):
            collector.problems.append(
                f"[{LEVEL_TAGS['crash']}] {source} {problem};没有任何已发布的客户端补丁扩展该表解析器,"
                "换哪个档案都不能放行,只能改数据(批 2 共享解析 wfx-parsers-v1 之前)")
        for capability in required_client_capabilities(kind, record):
            collector.requirements.append(Requirement(
                capability, wfx_registry.capability_level(capability) or "crash", source,
                "补丁构造/解析器扩展"))
        for column, tag in ability_tags(kind, record):
            collector.configuration("character_tag", tag, None, f"{source} c{column}")
        if not collector.index:
            continue
        for block in MODE_BLOCKS.get(cell(mode_col), ()):
            if block not in blocks or block not in uid_columns:
                continue
            base, offset = uid_columns[block]
            value = cell(base)
            if block == "instant_precontent":
                reads_uid = value in precontent_kinds
            else:
                case = cases.get(BLOCK_CASE_KEY.get(block, block), {}).get(value)
                reads_uid = (case is not None and "unique_condition_id" in case["fields"]
                             and (block, value) not in borrowing)
            if reads_uid:
                collector.uid_ref(cell(base + offset), source, f"{block} kind {value} 引用")


def _walk_dsl(tree: Any):
    stack = [tree]
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            if len(node) > 1 and node[0] == "ACUnique" and type(node[1]) is int:
                yield "uid", node[1]
            elif len(node) > 1 and node[0] == "Trace" and isinstance(node[1], str):
                yield "trace", node[1]
            stack.extend(reversed(node))
        elif isinstance(node, dict):
            stack.extend(node.values())


def check(rows: Mapping[str, Mapping[str, str]] | None = None,
          dsl: Mapping[str, Any] | None = None,
          strings: Iterable[str] = (),
          profile: str | ClientProfile | None = None,
          *,
          unique_context: Mapping[str, str] | None = None,
          input_problems: Iterable[str] = (),
          input_warnings: Iterable[str] = ()) -> GateReport:
    """rows = {表种类: {键: 行文本}}（含 custom_ability_string 的值及 character）；
    dsl = {标签: 已解码 DSL 树}；strings = 兼容旧调用方的 custom_ability_string 键；
    unique_context = 本批不含 unique_condition 时，用来解析 uid 的现行表（通常取 store）。"""
    resolved = resolve_profile(profile if profile is not None else default_publish_profile())
    rows = rows or {}
    published_unique = rows.get("unique_condition") or {}
    collector = _Collector(_wfx_index(published_unique, unique_context))
    collector.problems.extend(input_problems)
    collector.warnings.extend(input_warnings)

    # 5. unique_condition 的 wfx 行本身
    for key, text in published_unique.items():
        records = _records(text)
        if not records:
            continue
        record = records[0]
        kind = wf_wfx.classify_sid(record[0])
        if kind is None:
            continue
        source = f"unique_condition[{key}]"
        # sid 按原值判(不 strip);其余列由 unique_row_problems 自己去空白
        tag = f"[{LEVEL_TAGS['semantic']}] " if kind == "lookalike" else ""
        for problem in wf_wfx.unique_row_problems(list(record)):
            collector.problems.append(f"{tag}{source} {problem}")
        if kind == "lookalike":
            continue
        if _norm_uid(key) is None:
            collector.problems.append(f"{source} 键不是整数 uid,施加行/DSL 无法引用它")
        if kind == "effect":
            try:
                spec = wf_wfx.decode_sid(record[0])
            except wf_wfx.WfxError:
                continue          # 已由 unique_row_problems 报出
            collector.requirements += _spec_requirements(spec, source, "效果状态行")
            if spec.effect.get("todo"):
                collector.warnings.append(f"{source}：" + "；".join(spec.effect["todo"]))
            if spec.effect.get("stack_note"):
                collector.warnings.append(f"{source}：{spec.effect['stack_note']}")

    # 1+2. 词条五表
    for kind in ABILITY_TABLE_LOGICALS:
        for key, text in (rows.get(kind) or {}).items():
            _ability_requirements(kind, key, text, collector)

    # 3. DSL
    trace_prefix = wfx_registry.load()["dsl"]["trace_prefix"]
    trace_capability = wfx_registry.load()["dsl"]["trace_capability"]
    for label, tree in (dsl or {}).items():
        for what, value in _walk_dsl(tree):
            if what == "uid":
                collector.uid_ref(value, f"DSL {label}", "ACUnique 施加")
            elif value.startswith(trace_prefix):
                for capability in wfx_registry.capability_closure([trace_capability]):
                    collector.requirements.append(Requirement(
                        capability, wfx_registry.capability_level(capability) or "crash",
                        f"DSL {label}", f"Trace({value!r})"))
        # 伤害段覆盖:Environment.getBuffTargetAs 原生只认 0-4,≥100 走 default 分支返回空值(读成 0)
        # → 按技能伤害结算,不崩但伤害归属丢失 ⇒ 语义级(注册表里该能力的 crash 级指 424 行的解析器)
        segments = wf_battle_rules.dsl_segment_overrides(tree)
        if segments:
            for capability in wfx_registry.capability_closure(wf_battle_rules.dsl_capabilities(tree)):
                collector.requirements.append(Requirement(
                    capability, "semantic", f"DSL {label}",
                    f"buffTargetAs 段覆盖 {sorted(set(segments))}(未装补丁按技能伤害结算,归属丢失)"))

    # 4. custom_ability_string 键
    from wf_client_legality import panel_override_capability

    string_rules = wfx_registry.load().get("string_keys", {})
    custom_rows = rows.get("custom_ability_string") or {}
    string_keys = list(dict.fromkeys([*strings, *custom_rows]))
    for key in string_keys:
        capability = panel_override_capability(key)
        if capability is not None:
            collector.requirements.append(Requirement(
                capability, wfx_registry.capability_level(capability) or "cosmetic",
                f"custom_ability_string[{key}]", "面板/装备说明覆盖"))
        for prefix, rule in string_rules.items():
            if key.startswith(prefix):
                for capability in wfx_registry.capability_closure([rule["capability"]]):
                    collector.requirements.append(Requirement(
                        capability, rule["level"], f"custom_ability_string[{key}]", rule.get("note", prefix)))

    for key in string_keys:
        collector.configuration("custom_ability_string", key, custom_rows.get(key),
                                f"custom_ability_string[{key}]")
    from wf.wfx_tags import tag_tokens
    for key, text in (rows.get("character") or {}).items():
        for number, record in enumerate(_records(text)):
            if len(record) > 5:
                for tag in tag_tokens(record[5]):
                    collector.configuration("character_tag", tag, None, f"character[{key}]#{number} c5")

    return _evaluate(resolved, collector)


def _evaluate(profile: ClientProfile, collector: _Collector) -> GateReport:
    catalog = wfx_registry.capabilities()
    grouped: dict[tuple[str, str], list[Requirement]] = {}
    for item in collector.requirements:
        grouped.setdefault((item.capability, item.level), []).append(item)
    problems = list(collector.problems)
    warnings = list(collector.warnings)
    order = {"crash": 0, "semantic": 1, "cosmetic": 2}
    for (capability, level), items in sorted(grouped.items(),
                                            key=lambda pair: (order.get(pair[0][1], 9), pair[0][0])):
        if capability in profile.capabilities:
            continue
        sources = sorted({item.source for item in items})
        where = ", ".join(sources[:6]) + (f" 等 {len(sources)} 处" if len(sources) > 6 else "")
        entry = catalog.get(capability)
        note = "" if entry is None else (
            "(该能力尚无客户端实现)" if entry["status"] == "planned" else "")
        if entry is None:
            problems.append(f"[未登记] 需要注册表里没有的 capability {capability}: {where}")
        elif level == "cosmetic":
            warnings.append(f"[{LEVEL_TAGS[level]}] 缺 {capability}{note}: {items[0].reason}; 来源 {where}")
        else:
            problems.append(f"[{LEVEL_TAGS[level]}] 缺 {capability}{note}: {items[0].reason}; 来源 {where}")
    return GateReport(profile.name, profile.capabilities, collector.requirements, problems, warnings)


# ------------------------------------------------------------------ 出口适配

@dataclass(frozen=True)
class PayloadEntry:
    """一个待投递文件。logical 已知时按逻辑路径识别，否则按 upload 相对路径 xx/hash 识别。"""
    label: str
    read: Callable[[], bytes]
    logical: str | None = None
    rel: str | None = None
    root: str = "common"


def _rel_to_kind() -> dict[str, str]:
    import wf_mod_tool as core

    out = {}
    for kind, logical in GATE_TABLE_LOGICALS.items():
        digest = core.sha1_path(logical)
        out[f"{digest[:2]}/{digest[2:]}"] = kind
    return out


def check_entries(entries: Iterable[PayloadEntry], profile: str | ClientProfile | None = None,
                  *, unique_context: Mapping[str, str] | None = None) -> GateReport:
    """通用入口：识别表与 DSL，解码后调 check。只看 common 层（medium/android 是图片等资产）。"""
    resolved = resolve_profile(profile if profile is not None else default_publish_profile())
    by_logical = {logical: kind for kind, logical in GATE_TABLE_LOGICALS.items()}
    by_rel = _rel_to_kind()
    rows: dict[str, dict[str, str]] = {}
    warnings: list[str] = []
    problems: list[str] = []
    candidates: list[tuple[str, bytes, bool]] = []   # (标签, 解压后字节, 是否确知是 DSL)

    def read(entry: PayloadEntry) -> bytes | None:
        # 读不出的待投递文件无法判定(发布本身也读不出它):拦下并写明,不抛裸异常
        try:
            return entry.read()
        except OSError as exc:
            problems.append(f"[读不出] {entry.label}: {type(exc).__name__}: {exc}(能力闸门无法判定,先修文件)")
            return None

    for entry in entries:
        if entry.root != "common":
            continue
        rel = (entry.rel or "").replace("production/upload/", "")
        kind = by_logical.get(entry.logical) if entry.logical else by_rel.get(rel)
        if kind is not None:
            payload = read(entry)
            if payload is None:
                continue
            try:
                rows[kind] = decode_rows(payload)
            except Exception as exc:
                # 索引都解不开 = 客户端同样读不出这张表,它投递不了任何效果行;能力闸门只判能力,
                # 不越权替表结构校验拦发布(与 B1-0 之前行为一致),只留警告。
                warnings.append(f"{entry.label} ({GATE_TABLE_LOGICALS[kind]}) 不是可解码的 orderedmap,"
                                f"能力闸门跳过它: {type(exc).__name__}: {exc}")
            continue
        if entry.logical is not None and not entry.logical.endswith(DSL_SUFFIX):
            continue
        raw = read(entry)
        data = _inflate(raw) if raw is not None else None
        if data is not None:
            candidates.append((entry.label, data, entry.logical is not None))
    dsl: dict[str, Any] = {}
    # 不再按「有无 wfx」预筛:伤害段覆盖(buffTargetAs ≥100)不带 wfx 字样,也要解析才能判定
    for label, data, known in candidates:
        try:
            dsl[label] = _parse_dsl(data)
        except Exception as exc:
            if known:
                warnings.append(f"DSL {label} 无法解析,能力闸门跳过它: {type(exc).__name__}: {exc}")
    return check(rows, dsl, (), resolved, unique_context=unique_context,
                 input_problems=problems, input_warnings=warnings)


def unique_context_from_entries(entries: Iterable[PayloadEntry]) -> dict[str, str] | None:
    """一组待投递/链上条目里 unique_condition 表的行(后出现的覆盖先出现的);没有返回 None。

    出口用它给 check_entries 补 uid 上下文:本批不带 unique_condition、但引用了之前边/链尾里
    的 wfx 行时,不给上下文就推导不到(设计稿 4.9 第 2 条)。解不开的表跳过(check_entries 另报)。"""
    by_rel = _rel_to_kind()
    rows: dict[str, str] | None = None
    for entry in entries:
        if entry.root != "common":
            continue
        rel = (entry.rel or "").replace("production/upload/", "")
        is_unique = (entry.logical == UNIQUE_CONDITION_LOGICAL if entry.logical
                     else by_rel.get(rel) == "unique_condition")
        if not is_unique:
            continue
        try:
            decoded = decode_rows(entry.read())
        except Exception:
            continue
        rows = {**(rows or {}), **decoded}
    return rows


def merge_unique_context(*contexts: Mapping[str, str] | None) -> dict[str, str] | None:
    """依次叠加(后者覆盖前者);全空返回 None。"""
    merged: dict[str, str] = {}
    for context in contexts:
        merged.update(context or {})
    return merged or None


def store_unique_context(stores: Iterable[Path | None]) -> dict[str, str] | None:
    """第一个有 unique_condition 表的 store 的现行行（解析 uid 用）；都没有返回 None。"""
    import wf_mod_tool as core

    for store in stores:
        if store is None:
            continue
        path = core.table_path(Path(store), UNIQUE_CONDITION_LOGICAL)
        if path.is_file():
            try:
                return decode_rows(path.read_bytes())
            except Exception:
                return None
    return None


def check_publish(entries: Iterable[tuple[str, bytes]], store: Path | None,
                  profile: str | ClientProfile | None = None) -> GateReport:
    """wf_publish：entries = [(archive 名或 xx/hash, 字节)]，只传 upload 层。"""
    payloads = []
    for name, payload in entries:
        rel = name.replace("production/upload/", "")
        payloads.append(PayloadEntry(label=rel, rel=rel, read=lambda data=payload: data))
    return check_entries(payloads, profile, unique_context=store_unique_context([store]))


def check_package(package_dir: Path, stores: Iterable[Path], profile: str | ClientProfile | None = None
                  ) -> GateReport:
    """wf_character_flow：包 roots/common 下的词条表、固有状态表、字符串表与全部 DSL。"""
    common = Path(package_dir) / "roots" / "common"
    payloads: list[PayloadEntry] = []
    for logical in GATE_TABLE_LOGICALS.values():
        path = common / Path(*logical.split("/"))
        if path.is_file():
            payloads.append(PayloadEntry(label=logical, logical=logical, read=path.read_bytes))
    if common.is_dir():
        for path in sorted(common.rglob("*" + DSL_SUFFIX)):
            logical = path.relative_to(common).as_posix()
            payloads.append(PayloadEntry(label=logical, logical=logical, read=path.read_bytes))
    return check_entries(payloads, profile, unique_context=store_unique_context(stores))


# ------------------------------------------------------------------ CLI

def main(argv: list[str] | None = None) -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="客户端能力闸门(扩展词条框架)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("profiles", help="列出客户端档案")
    run = sub.add_parser("check", help="按档案检查 store 里的表(默认 pending 列表)")
    run.add_argument("--client-profile", required=True)
    run.add_argument("--tables", help="逗号分隔的表别名/逻辑路径(同 wf_publish)")
    args = parser.parse_args(argv)
    if args.command == "profiles":
        default = default_publish_profile()
        for name, profile in load_profiles().items():
            mark = " (默认发布档案)" if name == default else ""
            print(f"{name}{mark}: {len(profile.capabilities)} 项 - {profile.description}")
            for capability in sorted(profile.capabilities):
                print(f"    {capability}")
        return 0
    import wf_mod_tool as core
    import wf_publish

    store_value = core.resolve_active_store(MOD_DIR.parent, profile=core.resolve_profile())
    if not store_value:
        print("未找到数据包 store。")
        return 2
    store = Path(store_value)
    if args.tables:
        rels = [wf_publish._relative_for_logical(item) for item in wf_publish._explicit_logicals(args.tables)]
    else:
        rels = [str(item) for item in json.loads(wf_publish.PENDING.read_text(encoding="utf-8"))] \
            if wf_publish.PENDING.is_file() else []
    entries = [(rel, (store / rel).read_bytes()) for rel in rels
               if not rel.startswith(("medium:", "android:")) and (store / rel).is_file()]
    try:
        report = check_publish(entries, store, args.client_profile)
    except GateError as exc:
        print(f"[ERR] {exc}")
        return 2
    for line in report.lines():
        print(line)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
