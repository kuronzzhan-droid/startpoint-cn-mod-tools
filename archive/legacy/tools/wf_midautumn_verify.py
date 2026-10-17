#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中秋批次(20260920)角色包机械验证器 —— 一次性工具。

    python mod-tools/wf_midautumn_verify.py --workspace work/character_packs/ma-kyle \
        [--design work/character_packs/midautumn-20260920/design/kyle.json] [--gbf] \
        [--pixel-freeform] --out work/character_packs/midautumn-20260920/impl/kyle/verify.json

``--pixel-freeform``：角色像素不是「母本 8 件套逐色映射直替」（例如索恩的三张静态图程序化合成
全序列，裁决 §4／作者决定），sheet 尺寸天然不等于母本快照；同 ``--gbf`` 一样把
``art/pixel-sheet-dims`` 降级为 warning 并登记，不放宽默认（逐色映射直替角色的）路径。

退出码:0 = 全过(只剩 warning),1 = 有 blocking 项,2 = 工具本身出错。

只读 ``<workspace>/package``(以及只读的 live store / 官方归档),不写包、不发布。
每项输出 ``{name, pass, level, evidence}``;``level`` ∈ {blocking, warning}。

判据全部来自既有库,本文件不重写解析器:
  * 行合法性  → ``wf_client_legality``(``client_legality_problems`` /
    ``declared_block_field_problems`` / ``invoke_skill_string_problems`` /
    ``character_stance_problems`` / ``required_client_capabilities``)
  * 列布局    → ``wf_describe.layout`` / ``enum_map``(块基址 + 块内字段偏移)
  * DSL       → ``wf_dsl.parse_dsl`` / ``encode_amf3`` + ``wf_dsl_sig.COMMANDS/EVENTS``
  * 面板文案  → ``wf_midautumn_kitlib.panel_problems``
  * 语音      → ``wf_voice_gate.check_voice_set``(容器/时长/重复/可达性)
  * 图集      → 子进程 ``wf_atlas_budget_check.py --pack <ws> --quiet``
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zlib
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_client_patch_scope as SCOPE  # noqa: E402
import wf_describe  # noqa: E402
import wf_dsl  # noqa: E402
import wf_dsl_sig as SIG  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_voice_gate as VG  # noqa: E402

SCHEMA = "ma-verify/1"
BLOCKING = "blocking"
WARNING = "warning"

# ---------------------------------------------------------------- 常量

ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
UNIQUE = "master/character/unique_condition.orderedmap"
CAS = "master/string/custom_ability_string.orderedmap"
CHARACTER = "master/character/character.orderedmap"
CHARACTER_TEXT = "master/character/character_text.orderedmap"
SPEECH = "master/character/character_speech.orderedmap"
SWITCHED = "master/skill/switched_action_skill.orderedmap"

DSL_SUFFIX = ".action.dsl.amf3.deflate"
CLIENT_ROOTS = ("common", "medium", "android")

# 裁决 §8:队长表写这三个 kind = C7050(客户端 LeaderAbilityValues 没有这些解析分支)。
LEADER_FORBIDDEN_KINDS = ("422", "724", "713")

# 前置 188 数的是固有状态「实例数」(恒为 1),阈值是 ×100000 定点数 ——
# 写 >100000(即 ≥2 个实例)永不成立。裁决 §8。
PRECONDITION_INSTANCE_COUNT_KINDS = ("188",)
PRECONDITION_INSTANCE_MAX = 100000

# 叠层类内容 kind:引用了上限 (None) 的固有状态 = 上限 1,叠层全死
# (记忆卡 wf-unique-cap-none-trap)。
STACKING_CONTENT_KINDS = ("461",)
STACKING_DSL_COMMANDS = ("ACUnique",)

# 629 = InvokeSkill;525 = 技能点/固有状态消耗。同一触发下 629 必须排在消耗行之前
# (记忆卡 wf-dsl-row-assembly-discipline)。
INVOKE_SKILL_KIND = "629"
CONSUME_KIND = "525"

# 自制服务端时钟钉在 2025-08-05,晚于它的期间列一律隐形(记忆卡 wf-custom-server-time-trap)。
SERVER_CLOCK_DATE = (2025, 8, 5)
DATE_RE = re.compile(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})")

# 真实存在的客户端补丁 capability 全集(wf_client_legality 的能力表)。
KNOWN_CAPABILITIES = frozenset(
    {name for gated in L.CLIENT_PATCH_CONTENT_KINDS.values() for name in gated.values()}
    | {name for by_table in SCOPE.PATCH_PARSER_CAPABILITIES.values() for name in by_table.values()}
    | {L.PANEL_OVERRIDE_V1, L.PANEL_OVERRIDE_V2, L.EQUIPMENT_DESC_OVERRIDE, L.EQUIPMENT_ENHANCED_LOOK,
       L.EQUIPMENT_ENHANCED_PARTY_FRAME}
    | set(L.ENHANCED_LOOK_PREFIX_CAPABILITIES.values())
    | set(L.EQUIPMENT_KEY_PREFIX_CAPABILITIES.values())
)

# 详情页/编成必需的 UI 双槽件(每个都要 _0 与 _1 两份)。
CORE_UI_BASES = (
    "full_shot_1440_1920", "square", "square_132_132",
    "square_round_136_136", "square_round_95_95",
    "thumb_level_up", "thumb_party_main", "thumb_party_unison",
    "battle_control_board", "battle_member_status", "cutin_skill_chain",
    "skill_cutin",
)

VOICE_ROUTE_COLS = range(9, 17)          # character c9–c16
VOICE_ROUTE_KINDS = ("0", "1", "3")      # HpHigh / ConditionExist / ChangeSkillFlag
VOICE_SLOT_COUNT = 22                    # 本批生成槽位数(GBF 复用包内原声,不要求)

# GBF 两人用的是包内已有原声(裁决 §5,不重新生成),容器规格偏离不是本批引入的缺陷 ——
# 只降级这几条**纯规格**判据;解不出帧、混淆态缺失、时长超官方 max 仍然是阻断项。
GBF_TOLERATED_CONTAINER_RULES = frozenset({"bad_bitrate", "bad_srate", "bad_channels",
                                           "not_cbr", "bad_tail"})

DEFAULT_ATLAS_THRESHOLD = 3.5
GBF_ATLAS_THRESHOLD = 5.0


class VerifyError(RuntimeError):
    pass


# ---------------------------------------------------------------- 结果容器

class Report:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []

    def add(self, name: str, ok: bool, level: str, evidence: Any) -> None:
        self.checks.append({"name": name, "pass": bool(ok), "level": level,
                            "evidence": evidence})

    def result(self, problems: Sequence[str], name: str, level: str,
               evidence_ok: Any = None, *, limit: int = 40) -> None:
        """``problems`` 为空 = 通过;否则把前 ``limit`` 条当证据。"""
        if problems:
            self.add(name, False, level,
                     {"problems": list(problems)[:limit], "total": len(problems)})
        else:
            self.add(name, True, level, evidence_ok if evidence_ok is not None else "ok")

    @property
    def blocking(self) -> list[dict[str, Any]]:
        return [c for c in self.checks if not c["pass"] and c["level"] == BLOCKING]


# ---------------------------------------------------------------- 低层读取

def read_orderedmap(raw: bytes) -> dict[str, str]:
    """容错 orderedmap 解码:行块可能是 zlib,也可能是历史遗留的明文
    (记忆卡 wf-orderedmap-plain-row-trap —— 明文行不能让整张表读不出来)。"""
    keys, pairs, index_len = core.parse_index(raw)
    blob = raw[4 + index_len:]
    out: dict[str, str] = {}
    prev = 0
    for key, (_start, row_end) in zip(keys, pairs):
        chunk = blob[prev:row_end]
        prev = row_end
        if not chunk:
            out[key] = ""
            continue
        try:
            out[key] = zlib.decompress(chunk).decode("utf-8")
        except zlib.error:
            out[key] = chunk.decode("utf-8", "replace")
    return out


def split_rows(text: str) -> list[list[str]]:
    """一键多记录的 CSV 文本 → 行列表(直接用仓库的 CSV 口径,别自造方言)。"""
    if not text:
        return []
    return [row for row in core.read_csv_lines(text) if row]


def split_rows_lenient(text: str) -> list[list[str]] | None:
    """CSV 解析失败返回 None —— 有些认领表(mana_board 等)根本不是 CSV。"""
    try:
        return split_rows(text)
    except Exception:
        return None


def png_dims(data: bytes) -> tuple[int, int] | None:
    """PNG 尺寸。CDN 下发的 PNG 魔数是小写 ``\\x89png``(记忆卡 wf-boss-skeleton-routes),
    包内件与母本快照两种形态都要认。"""
    if len(data) < 24 or data[:8].lower() != b"\x89png\r\n\x1a\n":
        return None
    return (int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big"))


# ---------------------------------------------------------------- 包上下文

class Pack:
    """只读的包视图。除 live store 解析外不碰 workspace 以外的任何东西。"""

    def __init__(self, workspace: Path, root: Path) -> None:
        self.root = root
        self.workspace = workspace
        self.package = workspace / "package"
        self.roots = self.package / "roots"
        self.evidence = workspace / "evidence"
        if not self.roots.is_dir():
            raise VerifyError(f"package roots missing: {self.roots}")
        self.manifest = self._json(self.package / "manifest.json") or {}
        ws_json = self._json(workspace / "workspace.json") or {}
        self.cid = str(self.manifest.get("character_id") or ws_json.get("character_id") or "")
        self.code = str(self.manifest.get("code_name") or ws_json.get("code_name") or "")
        if not self.cid or not self.code:
            raise VerifyError("cannot resolve character_id / code_name from package")
        self._tables: dict[tuple[str, str], dict[str, str] | None] = {}
        self._store: Path | None | bool = False

    # -- 基础

    @staticmethod
    def _json(path: Path) -> Any:
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def path(self, root: str, logical: str) -> Path:
        return self.roots / root / Path(*logical.split("/"))

    def has(self, root: str, logical: str) -> bool:
        return self.path(root, logical).is_file()

    def table(self, logical: str, root: str = "common") -> dict[str, str] | None:
        cached = self._tables.get((root, logical), False)
        if cached is not False:
            return cached           # type: ignore[return-value]
        path = self.path(root, logical)
        value: dict[str, str] | None = None
        if path.is_file() and logical.endswith(".orderedmap"):
            try:
                value = read_orderedmap(path.read_bytes())
            except Exception:
                value = None        # 认领表里混着非 orderedmap(server/*.json 等)
        self._tables[(root, logical)] = value
        return value

    def rows(self, logical: str, key: str, root: str = "common") -> list[list[str]]:
        table = self.table(logical, root) or {}
        return split_rows(table.get(key, ""))

    def dsl_programs(self) -> list[str]:
        base = self.roots / "common"
        if not base.is_dir():
            return []
        return sorted(p.relative_to(base).as_posix() for p in base.rglob("*" + DSL_SUFFIX))

    def dsl_tree(self, logical: str) -> tuple[Any, bytes]:
        raw = (self.roots / "common" / Path(*logical.split("/"))).read_bytes()
        plain = zlib.decompress(raw, -15)
        return wf_dsl.parse_dsl(plain)["tree"], plain

    # -- live store(只读;解析不了就降级)

    @property
    def store(self) -> Path | None:
        if self._store is False:
            try:
                import wf_assets  # noqa: F401  (确认可用)
                profile = core.resolve_profile()
                self._store = Path(profile.store) if profile is not None else None
            except Exception:
                self._store = None
        return self._store           # type: ignore[return-value]

    def live_has(self, logical: str) -> bool:
        store = self.store
        if store is None:
            return False
        try:
            import wf_assets
            return wf_assets.locate(store, logical) is not None
        except Exception:
            return False

    # -- 本角色名下的键

    def claimed(self) -> dict[tuple[str, str], set[str]]:
        """manifest ``tables[]`` 的认领表 → {(root, logical): {外层键}}。"""
        out: dict[tuple[str, str], set[str]] = {}
        for entry in self.manifest.get("tables") or []:
            key = (entry.get("root") or "common", entry.get("logical_path") or "")
            out.setdefault(key, set()).update(str(k) for k in entry.get("outer_keys") or [])
        claims = self._json(self.evidence / "table_claims.json")
        for entry in claims or []:
            key = (entry.get("root") or "common", entry.get("logical_path") or "")
            out.setdefault(key, set()).update(str(k) for k in entry.get("outer_keys") or [])
        return out

    def owned_keys(self, logical: str, root: str = "common") -> list[str]:
        """认领的键 ∪ 由 cid/code 推出的键,并且确实存在于包内表里。"""
        table = self.table(logical, root) or {}
        keys = set(self.claimed().get((root, logical), set()))
        keys |= set(self.derived_keys(logical))
        return sorted(k for k in keys if k in table)

    def derived_keys(self, logical: str) -> set[str]:
        if logical == ABILITY:
            return {f"{self.cid}{slot}" for slot in range(1, 11)}
        if logical in (LEADER, CHARACTER, CHARACTER_TEXT, SPEECH):
            return {self.cid}
        if logical == UNIQUE:
            table = self.table(UNIQUE) or {}
            return {k for k in table if k.startswith(self.cid) and len(k) == len(self.cid) + 2}
        if logical == CAS:
            table = self.table(CAS) or {}
            return {k for k in table
                    if k.startswith(L.PANEL_OVERRIDE_KEY_PREFIX + self.code)
                    or k.startswith(self.code)}
        if logical == SWITCHED:
            return {self.code + "_voice_ready", self.code}
        return set()

    def cas_keys(self) -> frozenset[str]:
        """custom_ability_string 里能被 629 引用的全部键(包内整张表)。"""
        return frozenset(self.table(CAS) or {})


# ---------------------------------------------------------------- 列布局助手

def _blocks(kind: str) -> dict[str, int]:
    return {k: int(v) for k, v in wf_describe.layout(kind)["blocks"].items()}


def _field_offsets(block: str) -> dict[str, int]:
    fields = wf_describe.enum_map()["block_fields"].get(block, ())
    return {name: int(offset) for offset, name, _label in fields}


def cell(row: Sequence[str], index: int) -> str:
    return (row[index] if 0 <= index < len(row) else "").strip()


def trigger_mode(kind: str, row: Sequence[str]) -> str:
    return cell(row, _blocks(kind)["precondition1"] - 1)


def content_kinds(kind: str, row: Sequence[str]) -> dict[str, str]:
    """{块名: 该块的 kind 单元格}(只取 instant/during/opening 三个内容块)。"""
    blocks = _blocks(kind)
    out = {}
    for block in ("instant_content", "during_content", "opening"):
        offsets = _field_offsets(block)
        if "kind" not in offsets:
            continue
        out[block] = cell(row, blocks[block] + offsets["kind"])
    return out


def preconditions(kind: str, row: Sequence[str]) -> list[dict[str, str]]:
    blocks = _blocks(kind)
    offsets = _field_offsets("precondition")
    out = []
    for n in (1, 2, 3):
        base = blocks[f"precondition{n}"]
        out.append({"slot": str(n),
                    "kind": cell(row, base + offsets["kind"]),
                    "threshold": cell(row, base + offsets["threshold.power1"]),
                    "threshold_max": cell(row, base + offsets["threshold.first_max"]),
                    "unique_condition_id": cell(row, base + offsets["unique_condition_id"])})
    return out


def referenced_unique_ids(kind: str, row: Sequence[str]) -> dict[str, set[str]]:
    """{固有状态 ID: {引用它的内容 kind}} —— 用来判断 (None) 上限是否真的被叠层用到。"""
    blocks = _blocks(kind)
    out: dict[str, set[str]] = {}
    for block in ("instant_content", "during_content"):
        offsets = _field_offsets(block)
        if "unique_condition_id" not in offsets:
            continue
        uid = cell(row, blocks[block] + offsets["unique_condition_id"])
        content = cell(row, blocks[block] + offsets["kind"])
        if uid and uid not in ("(None)", "0"):
            out.setdefault(uid, set()).add(content)
    return out


# ---------------------------------------------------------------- 1. 行检查

def check_rows(pack: Pack, rep: Report) -> None:
    ability_keys = pack.owned_keys(ABILITY)
    leader_keys = pack.owned_keys(LEADER)
    unique_keys = pack.owned_keys(UNIQUE)
    cas_keys = pack.cas_keys()

    if not ability_keys and not leader_keys:
        rep.add("rows/present", False, BLOCKING,
                {"problems": [f"package has no owned ability/leader rows for cid {pack.cid}"]})
        return
    rep.add("rows/present", True, BLOCKING,
            {"ability_keys": ability_keys, "leader_keys": leader_keys,
             "unique_keys": unique_keys})

    legality: list[str] = []
    leader_kind_hits: list[str] = []
    invoke: list[str] = []
    order: list[str] = []
    precond: list[str] = []
    statue: list[str] = []
    uid_refs: dict[str, set[str]] = {}

    for kind, keys in (("ability", ability_keys), ("leader_ability", leader_keys)):
        for key in keys:
            rows = pack.rows(ABILITY if kind == "ability" else LEADER, key)
            if not rows:
                legality.append(f"{kind} {key}: no records")
                continue
            # --- c2 雕像组:一键内必须单值(裁决 §8;官方 790 个多记录键 0 个混用)
            if kind == "ability" and len({cell(r, 2) for r in rows}) != 1:
                statue.append(f"ability {key}: c2 statue_group mixed "
                              f"{sorted({cell(r, 2) for r in rows})}")
            seen: dict[str, dict[str, int]] = {}
            for i, row in enumerate(rows):
                tag = f"{kind} {key}#{i}"
                for problem in L.client_legality_problems(kind, list(row)):
                    legality.append(f"{tag}: {problem}")
                for problem in L.declared_block_field_problems(kind, list(row)):
                    legality.append(f"{tag}: {problem}")
                for problem in L.invoke_skill_string_problems(list(row), cas_keys, kind):
                    invoke.append(f"{tag}: {problem}")
                kinds = content_kinds(kind, row)
                if kind == "leader_ability":
                    for block, value in kinds.items():
                        if value in LEADER_FORBIDDEN_KINDS:
                            leader_kind_hits.append(
                                f"{tag}: {block} kind={value} 在队长表 = C7050"
                                "(这些 kind 只有 AbilityValues 有解析分支)")
                mode = trigger_mode(kind, row)
                instant = kinds.get("instant_content", "")
                if instant in (INVOKE_SKILL_KIND, CONSUME_KIND):
                    seen.setdefault(mode, {}).setdefault(instant, i)
                for pre in preconditions(kind, row):
                    if pre["kind"] not in PRECONDITION_INSTANCE_COUNT_KINDS:
                        continue
                    for label in ("threshold", "threshold_max"):
                        value = pre[label]
                        if value.lstrip("-").isdigit() and int(value) > PRECONDITION_INSTANCE_MAX:
                            precond.append(
                                f"{tag}: precondition{pre['slot']} kind={pre['kind']} "
                                f"{label}={value} >{PRECONDITION_INSTANCE_MAX}"
                                "(188 数固有状态实例数,恒为 1,阈值 ≥2 永不成立)")
                for uid, contents in referenced_unique_ids(kind, row).items():
                    uid_refs.setdefault(uid, set()).update(contents)
            for mode, hits in seen.items():
                if CONSUME_KIND in hits and INVOKE_SKILL_KIND in hits \
                        and hits[CONSUME_KIND] < hits[INVOKE_SKILL_KIND]:
                    order.append(
                        f"{kind} {key}: 触发模式 {mode} 下 525 消耗行(#{hits[CONSUME_KIND]})"
                        f"排在 629 行(#{hits[INVOKE_SKILL_KIND]})之前")

    rep.result(legality, "rows/client-legality", BLOCKING,
               {"rows_checked": len(ability_keys) + len(leader_keys)})
    rep.result(leader_kind_hits, "rows/leader-forbidden-kinds", BLOCKING,
               {"forbidden": list(LEADER_FORBIDDEN_KINDS)})
    rep.result(invoke, "rows/invoke-skill-string", BLOCKING,
               {"custom_ability_string_keys": len(cas_keys)})
    rep.result(order, "rows/invoke-before-consume", BLOCKING)
    rep.result(precond, "rows/precondition-188-threshold", BLOCKING)
    rep.result(statue, "rows/ability-statue-group-single", BLOCKING)

    # --- 固有状态:8 位 ID + 叠层上限
    dsl_stacking = _dsl_stacking_unique_ids(pack)
    id_problems: list[str] = []
    cap_blocking: list[str] = []
    cap_warning: list[str] = []
    unique_table = pack.table(UNIQUE) or {}
    for key in unique_keys:
        if not (key.isdigit() and len(key) == 8):
            id_problems.append(f"unique_condition {key}: ID 非 8 位"
                               "(裁决 §1;7 位与基诺维 1699901/02 撞过)")
        rows = split_rows(unique_table.get(key, ""))
        if not rows:
            id_problems.append(f"unique_condition {key}: no record")
            continue
        cap = cell(rows[0], 4)
        if cap not in ("", "(None)"):
            continue
        users = sorted(uid_refs.get(key, set()) & set(STACKING_CONTENT_KINDS))
        dsl_used = key in dsl_stacking
        detail = (f"unique_condition {key}: c4 累计上限={cap!r} = 上限 1"
                  "(记忆卡 wf-unique-cap-none-trap;无上限写 99)")
        if users or dsl_used:
            cap_blocking.append(detail + f";被叠层使用 rows_kind={users} dsl={dsl_used}")
        else:
            cap_warning.append(detail + ";本包未见 461/ACUnique 叠层引用")
    rep.result(id_problems, "unique/id-8-digits", BLOCKING, {"keys": unique_keys})
    rep.result(cap_blocking, "unique/stacking-cap-not-none", BLOCKING)
    rep.result(cap_warning, "unique/cap-none-unused", WARNING)


def _dsl_stacking_unique_ids(pack: Pack) -> set[str]:
    """包内 DSL 里被 ACUnique 之类命令叠层的固有状态 ID(字符串或整数形参都认)。"""
    found: set[str] = set()
    for program in pack.dsl_programs():
        try:
            tree, _ = pack.dsl_tree(program)
        except Exception:
            continue
        for node in _walk(tree):
            if not _is_call(node):
                continue
            name, args = node[1][0], node[1][1:]
            if not any(token in str(name) for token in STACKING_DSL_COMMANDS):
                continue
            for arg in args:
                for value in _scalars(arg):
                    text = str(value)
                    if text.isdigit() and len(text) == 8:
                        found.add(text)
    return found


# ---------------------------------------------------------------- 2. DSL 检查

def _is_call(node: Any) -> bool:
    return (isinstance(node, list) and len(node) == 2 and node[0] in ("Command", "Event")
            and isinstance(node[1], list) and node[1] and isinstance(node[1][0], str))


def _walk(node: Any) -> Iterable[Any]:
    yield node
    if isinstance(node, list):
        for item in node:
            yield from _walk(item)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _walk(value)


def _scalars(node: Any) -> Iterable[Any]:
    if isinstance(node, (list, tuple)):
        for item in node:
            yield from _scalars(item)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _scalars(value)
    else:
        yield node


def _strings(node: Any) -> Iterable[str]:
    for value in _scalars(node):
        if isinstance(value, str):
            yield value


def dsl_roundtrip_problems(program: str, tree: Any, plain: bytes) -> list[str]:
    problems = []
    if isinstance(tree, dict) and "tree" in tree and "numbers" in tree:
        problems.append(f"{program}: 编码体是 {{tree,numbers}} 包装壳而不是裸树"
                        "(记忆卡 wf-dsl-encode-wrapper-trap;进战斗 F1034)")
        return problems
    try:
        encoded = wf_dsl.encode_amf3(tree)
    except Exception as exc:
        problems.append(f"{program}: re-encode failed: {exc}")
        return problems
    if encoded != plain and wf_dsl.parse_dsl(encoded)["tree"] != tree:
        problems.append(f"{program}: parse→encode→parse 语义不一致")
    return problems


EXPRESSION_TYPE = "ActionDslExpression"
DONOTHING = ["DoNothing"]


def dsl_shape_problems(program: str, tree: Any) -> tuple[list[str], list[str], list[str]]:
    """(DoNothing/Command Wait 类硬错, 签名形参不符, 未知构造名 warning)

    ``["DoNothing"]`` 本身是 ``IfTargetNotFound`` 的合法枚举构造(官方 FindAllSubjects
    第 8 参就这么写),**只有落在 ``ActionDslExpression`` 位(分支体)才是 F1009**
    —— 记忆卡 wf-dsl-donothing-enum-trap。所以判据必须带签名,不能裸搜。
    """
    hard: list[str] = []
    sig: list[str] = []
    unknown: list[str] = []

    def expression(node: Any, where: str) -> None:
        """这个位置期望一棵表达式。"""
        if isinstance(node, list) and node == DONOTHING:
            hard.append(f"{program}: {where} 是表达式位,写了 [\"DoNothing\"]"
                        "(它是 IfTargetNotFound 枚举;空分支要写 [\"Block\",[]];进游戏 F1009)")
            return
        visit(node, where)

    def visit(node: Any, where: str) -> None:
        if isinstance(node, list) and len(node) == 2 and node[0] == "Block" \
                and isinstance(node[1], list):
            for i, item in enumerate(node[1]):
                expression(item, f"{where}/Block[{i}]")
            return
        if _is_call(node):
            tag, payload = node[0], node[1]
            name, args = payload[0], payload[1:]
            table = SIG.COMMANDS if tag == "Command" else SIG.EVENTS
            other = SIG.EVENTS if tag == "Command" else SIG.COMMANDS
            spot = f"{where}/{tag}:{name}"
            if name not in table:
                if name in other:
                    flip = "Event" if tag == "Command" else "Command"
                    hard.append(f"{program}: {spot} 其实是 {flip} 构造"
                                "(类别写错会被静默吞掉;记忆卡 wf-dsl-command-wait-trace-trap)")
                else:
                    unknown.append(f"{program}: {spot} 是未知构造名"
                                   "(未知构造名下落索引 0,不崩不报,节点被静默吞掉)")
                for i, arg in enumerate(args):
                    visit(arg, f"{spot}#{i + 1}")
                return
            expect = table[name]
            if len(args) != len(expect):
                sig.append(f"{program}: {spot} 参数 {len(args)} 个,官方签名 {len(expect)} 个")
            for i, (want, got) in enumerate(zip(expect, args)):
                slot = f"{spot}#{i + 1}"
                if want == EXPRESSION_TYPE:
                    expression(got, slot)
                    continue
                if want == "Array" and not isinstance(got, list):
                    sig.append(f"{program}: {slot} 官方签名是 Array,这里是裸 "
                               f"{type(got).__name__}={got!r}"
                               "(记忆卡 wf-dsl-param-shape-f1034;详情页 F1034)")
                elif want in ("int", "Number") and isinstance(got, list):
                    sig.append(f"{program}: {slot} 官方签名是 {want},这里是 Array")
                visit(got, slot)
            for i, arg in enumerate(args[len(expect):], start=len(expect)):
                visit(arg, f"{spot}#{i + 1}")
            return
        if isinstance(node, list):
            for i, item in enumerate(node):
                visit(item, f"{where}[{i}]")
        elif isinstance(node, dict):
            for key, value in node.items():
                visit(value, f"{where}.{key}")

    visit(tree, "root")
    return hard, sig, unknown


# ---------------------------------------------------------------- DSL 坐标系取向
#
# 事故 U_4f5401(2026-09-20,作者真机):堆栈 Unit.getDirCD ← ActionEffect.calcDir ←
# ActionEffect.stepPos ← ActionEffect.new ← ActionEffectManager.show ←
# ActionEvaluator.evalCommand ← … ← resolveCollisionOfHitArea。
#
# 反编译判据(弹国服/scripts/pinball/…):
#   * ``ActionEffect.as:165-166`` 构造函数**无条件**调 stepPos()/stepDir() → calcDir();
#     ``ActionHitArea.as:490-491`` 与 ``ActionCollider.as:67-68`` 同构。
#     所以坐标系一写错,节点一创建就抛,和 tracking 开关无关 = 必崩。
#   * ``calcDir``(ActionEffect.as:496-515 / ActionHitArea.as:1189 / ActionCollider.as:144)
#     switch CoordSys.index:0=AB 取常量 -π/2;1=CD 取 ``target.getDirCD()``;
#     2=EF 取 ``target.getDirEF()``;3=GH 取指向 params[0] 的角度。
#   * ``getDirCD()`` 在这些主体上是 ``throw "INTERNAL ERROR"``:
#       enemy/Unit.as:957、enemy/EnemyImpl.as:3553、squad/ball/BallImpl.as:2049、
#       squad/member/MemberImpl.as:6254、squad/SquadImpl.as:2384(转发给球)、
#       zone/item/ExecutableInstantItem.as:694(转发给球)、
#       battle/action/dsl/Mate.as:420(``getDirEF`` 414 行也抛)。
#     安全的只有 ``ActionHitArea.as:1118``(返回 r)、``ActionCustomPosition.as:418``
#     (-1/-2 场地固定点)、``Marker.as:421`` / ``ImaginaryTarget.as:418``(参照点)、
#     CoffinImpl / AssistYakumonoImpl / SkillInvokerImpl(都返回 -π/2)。
#
# 官方正向对照(官方 CDN 归档,1069 棵与官方逐字节相同的玩家技能树):
#   ShowEffect 主体=命中对象绑定 → AB 155 / GH 22 / **CD 0 / EF 0**;
#   ShowEffect 主体=球 → AB 835 / EF 198 / GH 207 / CD 0;主体=自身 → AB 137 / CD 0;
#   ShowEffect 主体=判定区绑定 → CD 548(这才是 CD 的唯一官方用法)。
#
# 主体绑定种类(取自 ActionEvaluator.as 的 lookup/bind 位):
BUILTIN_SUBJECT_KINDS = {-1: "fixedpoint", -2: "fixedpoint",   # SpecialPointZoneBounds
                         -17: "self", -18: "ball", -33: "mate"}
# 玩家侧技能/PF 里这些主体的 getDirCD() 必抛:
COORDSYS_CD_THROWS = frozenset({"self", "ball", "found", "hittarget", "mate"})
COORDSYS_EF_THROWS = frozenset({"mate"})
COORDSYS_SAFE = frozenset({"hitarea", "fixedpoint"})
# 命令 → [(主体参下标, 坐标系参下标)](下标按命令参数,不含命令名)
COORDSYS_USES: dict[str, tuple[tuple[int, int], ...]] = {
    "ShowEffect": ((2, 5),),                    # ActionEvaluator case 10
    "MoveBall": ((0, 1),),                      # case 13 → subject.applyMovement
    "StopBall": ((0, 1),),                      # case 14
    "CreateHitArea": ((1, 2),),                 # case 24
    "MoveHitArea": ((0, 1),),                   # case 25
    "CreateReferencePoint": ((0, 1),),          # case 32
    "CreateShockWaveAttack": ((1, 2),),         # case 34
    "CreateCollider": ((0, 4),),                # case 95
}
# 命令 → [(绑定 id 参下标, 绑定种类, 作用域 Block 参下标)]
COORDSYS_BINDERS: dict[str, tuple[tuple[int, str, int], ...]] = {
    "FindAllSubjects": ((0, "found", 8),),
    "FindNearSubjects": ((4, "found", 5),),
    "FindMultiballSubjects": ((0, "found", 4), (0, "found", 5)),
    # p20 = 判定区自身,p21 = 被打中的对象(ActionHitAreaGroup.resolveCollision →
    # ActionEvaluator.resolveCollisionOfHitArea:1469-1472 的两条 bind)
    "CreateHitArea": ((18, "hitarea", 19), (20, "hitarea", 22), (21, "hittarget", 22)),
    "CreateShockWaveAttack": ((10, "hitarea", 12), (11, "hittarget", 12)),
    "CreateReferencePoint": ((9, "hitarea", 10),),
    "CreateReferencePointAtSpecifiedPosition": ((3, "hitarea", 4),),
}


def _coordsys_tag(node: Any) -> str | None:
    if isinstance(node, list) and node and isinstance(node[0], str):
        return node[0]
    return None


def dsl_coordsys_problems(program: str, tree: Any) -> list[str]:
    """坐标系取向落在会 ``throw`` 的主体上 = 客户端 U_4f5401 必崩。

    只判**能确定种类**的主体(内建 id 与本文件建模过的绑定);种类未知的绑定不报,
    以免把没建模的命令误伤成阻断项。
    """
    problems: list[str] = []

    def visit(node: Any, env: dict[int, str]) -> None:
        if isinstance(node, list):
            if len(node) == 2 and node[0] == "Command" and isinstance(node[1], list) \
                    and node[1] and isinstance(node[1][0], str):
                command(node[1], env)
                return
            for item in node:
                visit(item, env)
        elif isinstance(node, dict):
            for value in node.values():
                visit(value, env)

    def command(call: list, env: dict[int, str]) -> None:
        name, params = call[0], call[1:]
        for subject_at, coord_at in COORDSYS_USES.get(name, ()):
            if subject_at >= len(params) or coord_at >= len(params):
                continue
            subject = params[subject_at]
            tag = _coordsys_tag(params[coord_at])
            if not isinstance(subject, int) or tag is None:
                continue
            kind = env.get(subject, BUILTIN_SUBJECT_KINDS.get(subject))
            if kind is None or kind in COORDSYS_SAFE:
                continue
            if (tag == "CD" and kind in COORDSYS_CD_THROWS) or \
                    (tag == "EF" and kind in COORDSYS_EF_THROWS):
                problems.append(
                    f"{program}: {name} 主体 {subject}({kind}) 的坐标系写了 {tag},"
                    f"该主体 getDir{tag}() 是 throw \"INTERNAL ERROR\" —— 节点一创建就崩"
                    f"(U_4f5401);官方惯例写 [\"AB\"],要朝向才用 [\"GH\", <合法目标>]")
        binders = COORDSYS_BINDERS.get(name, ())
        scoped = {block_at for _bind_at, _kind, block_at in binders if block_at < len(params)}
        for block_at in sorted(scoped):
            inner = dict(env)
            for bind_at, kind, at in binders:
                if at == block_at and bind_at < len(params) and isinstance(params[bind_at], int):
                    inner[params[bind_at]] = kind
            visit(params[block_at], inner)
        for index, param in enumerate(params):
            if index not in scoped:
                visit(param, env)

    visit(tree, {})
    return problems


_ASSET_REF_RE = re.compile(r"^(battle|character|sound|se|bgm)/[\w./$-]+$")


def _resolve_by_element_bases(node: Any) -> Iterable[str]:
    """树里所有 ``["ResolveByElement", "<基路径>", <属性码>]`` 的基路径。

    基路径是客户端运行时按属性派生分色路径的模板，**本身不是资产**
    （逐字同 ``wf_character_requirements.py`` 的 ``_iter_effect_nodes`` 结论；
    按字面路径校验它必然误报缺失，见该文件 235 行注释与
    ``resolve_effect_by_element``：真实路径是
    ``f"{base}/{name}_{colour}/{name}_{colour}"``）。这里只需要把基路径从
    字面资产扫描里摘掉，实际是否可解析已经由 ``flow inspect`` 的
    ``master_reference`` 走正确派生逻辑核实过。
    """
    if isinstance(node, (list, tuple)):
        if node and node[0] == "ResolveByElement" and len(node) > 1 and isinstance(node[1], str):
            yield node[1]
        for item in node:
            yield from _resolve_by_element_bases(item)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _resolve_by_element_bases(value)


def dsl_asset_problems(pack: Pack, program: str, tree: Any) -> tuple[list[str], list[str]]:
    """引用的特效/音效基名能否在包内或 live store 解析。返回 (硬错, 无法判定的 warning)。"""
    missing: list[str] = []
    undecided: list[str] = []
    resolve_bases = set(_resolve_by_element_bases(tree))
    for value in sorted(set(_strings(tree))):
        if not _ASSET_REF_RE.match(value):
            continue
        if value in resolve_bases:
            continue
        candidates = [value + suffix for suffix in
                      (".parts.amf3.deflate", ".timeline.amf3.deflate", ".atlas.amf3.deflate",
                       ".png", ".mp3", ".atf.deflate", "")]
        if any(pack.has(root, c) for root in CLIENT_ROOTS for c in candidates):
            continue
        if pack.store is None:
            undecided.append(f"{program}: {value} 不在包内,live store 不可用,无法判定")
            continue
        if any(pack.live_has(c) for c in candidates):
            continue
        missing.append(f"{program}: 引用 {value} 在包内和 live store 都解析不到")
    return missing, undecided


def check_dsl(pack: Pack, rep: Report) -> None:
    programs = pack.dsl_programs()
    if not programs:
        rep.add("dsl/present", False, WARNING, {"problems": ["package has no DSL program"]})
        return
    roundtrip: list[str] = []
    hard: list[str] = []
    sig: list[str] = []
    unknown: list[str] = []
    missing: list[str] = []
    undecided: list[str] = []
    parse_fail: list[str] = []
    coordsys: list[str] = []
    lookup_scope: list[str] = []
    for program in programs:
        try:
            tree, plain = pack.dsl_tree(program)
        except Exception as exc:
            parse_fail.append(f"{program}: parse failed: {exc}")
            continue
        roundtrip += dsl_roundtrip_problems(program, tree, plain)
        a, b, c = dsl_shape_problems(program, tree)
        hard += a
        sig += b
        unknown += c
        d, e = dsl_asset_problems(pack, program, tree)
        missing += d
        undecided += e
        coordsys += dsl_coordsys_problems(program, tree)
        lookup_scope += [f"{program}: {p}"
                         for p in L.action_dsl_lookup_scope_problems(tree)]
    rep.result(parse_fail, "dsl/parse", BLOCKING, {"programs": programs})
    rep.result(roundtrip, "dsl/roundtrip", BLOCKING, {"programs": len(programs)})
    rep.result(hard, "dsl/forbidden-constructs", BLOCKING)
    rep.result(sig, "dsl/official-signature", BLOCKING)
    rep.result(unknown, "dsl/unknown-construct", WARNING)
    rep.result(missing, "dsl/asset-refs-resolve", BLOCKING)
    rep.result(undecided, "dsl/asset-refs-undecided", WARNING)
    rep.result(coordsys, "dsl/coordsys-on-enemy-subject", BLOCKING,
               {"programs": len(programs)})
    # 每个 lookup 位都要在当前作用域链上可见,否则战斗中 ClientError 16103
    # (2026-09-21 凯尔强化天雷事故;官方 7051 棵树正向对照 0 误报)
    rep.result(lookup_scope, "dsl/lookup-scope", BLOCKING, {"programs": len(programs)})

    # 克隆的特效族必须挂在 code_name 目录下(记忆卡 wf-effect-family-under-codename)
    stray: list[str] = []
    effect_root = pack.roots / "common" / "battle" / "effect"
    if effect_root.is_dir():
        for path in sorted(effect_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(effect_root).as_posix()
            parts = rel.split("/")
            # <family>/<code_name>/<子目录>/... ;包里自带的特效族必须走本角色 code 目录
            if pack.code not in parts:
                stray.append(f"battle/effect/{rel} 不在 {pack.code}/ 目录下"
                             "(兄弟目录名 = 进战斗「数据不足」)")
    rep.result(stray, "dsl/effect-family-under-codename", BLOCKING,
               {"code_name": pack.code})


# ---------------------------------------------------------------- 3. manifest 能力

def check_capabilities(pack: Pack, rep: Report) -> None:
    declared = [str(c) for c in pack.manifest.get("required_capabilities") or []]
    bogus = [c for c in declared if c not in KNOWN_CAPABILITIES]
    rep.result([f"required_capabilities 里的 {c!r} 不是真实能力名"
                f"(真实全集 {sorted(KNOWN_CAPABILITIES)})" for c in bogus],
               "manifest/capability-names-real", BLOCKING, {"declared": declared})

    needed: set[str] = set()
    for kind, logical in (("ability", ABILITY), ("leader_ability", LEADER)):
        for key in pack.owned_keys(logical):
            for row in pack.rows(logical, key):
                needed.update(L.required_client_capabilities(kind, list(row)))
    cas_keys = pack.owned_keys(CAS)
    for key in cas_keys:
        needed.update(L.required_client_capabilities(L.CUSTOM_ABILITY_STRING_KIND, [key]))
    # 带装备详情覆盖前缀却不是补丁会拼出的三种键形:能力照报,但客户端永远读不到这一行(惰性死行)
    rep.result([p for key in cas_keys for p in L.equipment_desc_override_key_problems(key)],
               "cas/equipment-desc-override-key-shape", BLOCKING,
               {"equipment_override_keys": sorted(k for k in cas_keys
                                                  if L.panel_override_capability(k) == L.EQUIPMENT_DESC_OVERRIDE)})
    # 装备外观族键(enhanced_pixelart_tier2_* / enhanced_frame_override_* / enhanced_party_frame_override_* /
    # rarity_frame_override_*):键尾是图标路径、值一行一格,
    # 第二图标档的值 "<等级>,<路径>" 含逗号,没加引号会被 CSV 拆成两格 → 客户端静默不生效
    look_keys = sorted(k for k in cas_keys if L.enhanced_look_capability(k))
    look_problems: list[str] = []
    for key in look_keys:
        rows = pack.rows(CAS, key)
        if len(rows) != 1 or len(rows[0]) != 1:
            look_problems.append(f"custom_ability_string[{key!r}] 必须恰好一行一格(值含逗号时整格加引号),"
                                 f"实际 {rows!r}")
            continue
        look_problems += L.enhanced_look_problems(key, rows[0][0])
    rep.result(look_problems, "cas/equipment-enhanced-look-shape", BLOCKING, {"enhanced_look_keys": look_keys})
    # 装备行为键(awakening_material_* / equipment_sort_pin_*):键尾是装备 ID 的规范十进制串,值是规范正整数,一行一格
    behaviour_keys = sorted(k for k in cas_keys if L.equipment_key_capability(k))
    behaviour_problems: list[str] = []
    for key in behaviour_keys:
        rows = pack.rows(CAS, key)
        if len(rows) != 1 or len(rows[0]) != 1:
            behaviour_problems.append(f"custom_ability_string[{key!r}] 必须恰好一行一格,实际 {rows!r}")
            continue
        behaviour_problems += L.equipment_key_problems(key, rows[0][0])
    rep.result(behaviour_problems, "cas/equipment-behaviour-key-shape", BLOCKING,
               {"equipment_behaviour_keys": behaviour_keys})

    declared_set = set(declared)
    problems = []
    for name in sorted(needed - declared_set):
        problems.append(f"行/DSL 用到 {name!r} 但 manifest 没声明")
    rep.result(problems, "manifest/capability-covers-rows", BLOCKING,
               {"needed": sorted(needed), "declared": declared})
    rep.result([f"manifest 声明了 {name!r} 但本包的行里没用到" for name in
                sorted(declared_set - needed - {L.PANEL_OVERRIDE_V1})],
               "manifest/capability-no-extras", WARNING,
               {"declared": declared, "needed": sorted(needed)})


# ---------------------------------------------------------------- 4. 期间/语音

def check_periods(pack: Pack, rep: Report) -> None:
    """自制内容的期间列不许晚于服务端时钟(2025-08-05),否则整块隐形。"""
    late: list[str] = []
    for (root, logical), keys in sorted(pack.claimed().items()):
        table = pack.table(logical, root)
        if table is None:
            continue
        for key in sorted(keys):
            text = table.get(key, "")
            rows = split_rows_lenient(text)
            # 非 CSV 的认领表(mana_board 等)按整段文本扫日期,列号写 ?
            cells = ([(f"c{col}", value) for row in rows for col, value in enumerate(row)]
                     if rows is not None else [("c?", text)])
            for label, value in cells:
                for m in DATE_RE.finditer(value):
                    date = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    if date > SERVER_CLOCK_DATE:
                        late.append(f"{logical} {key} {label}={m.group(0)!r} 晚于服务端时钟 "
                                    "2025-08-05(记忆卡 wf-custom-server-time-trap;整块隐形)")
    rep.result(late, "period/server-clock", BLOCKING,
               {"cutoff": "%04d-%02d-%02d" % SERVER_CLOCK_DATE})


def check_voice(pack: Pack, rep: Report, *, gbf: bool) -> None:
    crow = pack.rows(CHARACTER, pack.cid)
    if not crow:
        rep.add("voice/character-row", False, BLOCKING,
                {"problems": [f"character.orderedmap lacks {pack.cid}"]})
        return
    row = crow[0]
    rep.result(L.character_stance_problems(list(row)), "character/stance", BLOCKING,
               {"stance": cell(row, L.CHARACTER_STANCE_COL)})

    route = [cell(row, i) for i in VOICE_ROUTE_COLS]
    problems = []
    # c9 = '(None)'/空 是官方「没有第二条语音路由」的哨兵(584 行里 564 行如此),不是错
    if any(v not in ("", "(None)") for v in route):
        kind = route[0]
        if kind not in VOICE_ROUTE_KINDS:
            problems.append(f"c9 语音路由 kind={kind!r} 不在 {VOICE_ROUTE_KINDS}"
                            "(2=多球会出编成缤带,4=IsUnison 主位永不成立)")
        elif kind == "1" and not (route[1] or route[2]):
            problems.append("c9 kind=1(ConditionExist) 但 c10/c11 固有状态列都空")
        elif kind == "3":
            switched = pack.table(SWITCHED) or {}
            want = pack.code + "_voice_ready"
            if want not in switched:
                problems.append(f"c9 kind=3(ChangeSkillFlag) 但 switched_action_skill 缺 {want!r}")
    rep.result(problems, "voice/route-shape", BLOCKING, {"c9_c16": route})

    speech = pack.table(SPEECH) or {}
    rep.result([] if pack.cid in speech else
               [f"character_speech.orderedmap lacks {pack.cid}(主页气泡字幕整块缺)"],
               "voice/speech-row", BLOCKING, {"rows": len(speech)})

    voice_dir = pack.roots / "common" / "character" / pack.code / "voice"
    files = sorted(voice_dir.rglob("*.mp3")) if voice_dir.is_dir() else []
    slots = [p.relative_to(voice_dir).as_posix()[:-4] for p in files]
    if not gbf:
        canon = [s for s in slots if s in _canonical_slots()]
        missing = sorted(set(_canonical_slots()) - set(canon))
        rep.result([f"缺生成槽 {s}" for s in missing], "voice/slot-coverage", BLOCKING,
                   {"files": len(files), "canonical_present": len(canon),
                    "canonical_total": VOICE_SLOT_COUNT})
    else:
        rep.add("voice/slot-coverage", bool(files), WARNING,
                {"files": len(files), "note": "GBF 复用包内原声,不要求 22 生成槽"})

    if not files:
        rep.add("voice/gate", False, BLOCKING, {"problems": ["package has no voice mp3"]})
        return
    voice_files = [VG.VoiceFile(pack.code, slot, path.read_bytes())
                   for slot, path in zip(slots, files)]
    findings = VG.check_voice_set(voice_files)
    errors, warns, container = [], [], []
    for f in findings:
        line = f"{f.rule} {f.slot}: {f.detail}"
        if f.level != "error":
            warns.append(line)
        elif gbf and f.rule in GBF_TOLERATED_CONTAINER_RULES:
            container.append(line)
        else:
            errors.append(line)
    rep.result(errors, "voice/gate", BLOCKING, {"files": len(voice_files)})
    rep.result(warns, "voice/gate-warnings", WARNING, {"files": len(voice_files)})
    if gbf:
        rep.result(container, "voice/container-spec", WARNING,
                   {"files": len(voice_files),
                    "note": "裁决 §5:GBF 两人用包内已有语音、不重新生成 —— "
                            "容器规格偏离按批次差异降级为 warning 并登记"})


def _canonical_slots() -> tuple[str, ...]:
    import wf_seasonal7_voice as V
    return tuple(V.SLOTS)


# ---------------------------------------------------------------- 5. 美术

def check_art(pack: Pack, rep: Report, *, gbf: bool = False, pixel_freeform: bool = False) -> None:
    ui: dict[str, set[str]] = {}
    for root in CLIENT_ROOTS:
        base = pack.roots / root / "character" / pack.code / "ui"
        if not base.is_dir():
            continue
        for path in base.iterdir():
            if not path.is_file():
                continue
            stem = path.name.split(".")[0]
            if stem.endswith("_0") or stem.endswith("_1"):
                ui.setdefault(stem[:-2], set()).add(stem[-1])

    problems = [f"UI 件 {base} 只有 _{sorted(got)[0]} 槽,缺另一槽"
                for base, got in sorted(ui.items()) if got != {"0", "1"}]
    problems += [f"缺必需 UI 件 {base}_0/_1" for base in CORE_UI_BASES if base not in ui]
    rep.result(problems, "art/ui-slot-pairs", BLOCKING,
               {"bases": sorted(ui), "core_required": list(CORE_UI_BASES)})

    qa = pack.manifest.get("qa") or {}
    missing = [str(m) for m in qa.get("missing_required") or []]
    rep.result([f"manifest.qa.missing_required: {m}" for m in missing],
               "art/required-assets", BLOCKING,
               {"present": qa.get("required_assets_present"),
                "total": qa.get("required_assets_total")})

    # --- 像素 sheet 尺寸与母本一致(母本 native 快照存在 evidence/)
    dims: list[str] = []
    for name, native in (("sprite_sheet", "native-sprite_sheet.png"),
                         ("special_sprite_sheet", "native-special_sprite_sheet.png")):
        pkg = pack.path("common", f"character/{pack.code}/pixelart/{name}.png")
        ref = pack.evidence / native
        if not pkg.is_file():
            dims.append(f"包内缺 pixelart/{name}.png")
            continue
        if not ref.is_file():
            continue
        got, want = png_dims(pkg.read_bytes()), png_dims(ref.read_bytes())
        if got != want:
            dims.append(f"pixelart/{name}.png 尺寸 {got} != 母本 {want}"
                        "(缩 PNG = 缩角色;记忆卡 wf-sprite-sheet-packer-dedup-fix)")
    # GBF 两人是原创角色、像素自绘,不是母本逐色映射直替 —— 尺寸本来就不同族,
    # 这一项对它们不适用,降级为 warning 并登记(裁决 §4 只对「有官方母本」的角色要求直替)。
    # pixel_freeform 同理:角色像素走「静态图程序化合成全序列」等非逐色映射直替路线
    # (例如索恩,作者决定 + 裁决 §4),sheet 按内容去重打包,尺寸天然与母本快照不同。
    freeform = gbf or pixel_freeform
    rep.result(dims, "art/pixel-sheet-dims", WARNING if freeform else BLOCKING,
               None if dims else "ok")
    if freeform and dims:
        rep.checks[-1]["evidence"]["note"] = (
            "GBF 原创角色像素自绘,与 donor 母本不同尺寸属批次差异,已降级登记" if gbf else
            "非逐色映射直替(程序化合成/去重打包),与 donor 母本不同尺寸属预期差异,已降级登记")

    rep.add("art/pixel-alpha", True, WARNING, _alpha_report(pack))


CHARACTER_SEGMENT = re.compile(rb"character/([A-Za-z0-9_]+)/")
# 二进制媒体:不是文本容器,里面出现的字节序列没有路径语义,不扫。
BINARY_SUFFIXES = (".png", ".mp3", ".atf", ".jpg", ".jpeg", ".ogg", ".wav")


def _inflate(data: bytes) -> bytes:
    for wbits in (15, -15, 31):
        try:
            return zlib.decompress(data, wbits)
        except zlib.error:
            continue
    return data


def check_donor_code_leak(pack: Pack, rep: Report) -> None:
    """包内 ``character/<新 code>/`` 目录下任何文件都不许内嵌别人的 ``character/<X>/`` 路径。

    20260920 真机事故:像素代理把母本 atlas/frame/timeline「字节不动」交付并登记
    owner=pixel,盖掉了 ``assets`` 步已改写好 code 的正确版本;客户端照母本纹理 id 取图,
    领取演出报 C8003「影像短片尚未加载」。

    判据按**路径段**精确匹配(``character/<seg>/``),所以母本 code 是新 code 的前缀
    (``sorceress_teacher`` vs ``sorceress_teacher_moon``)不会漏判也不会误判;
    只看 ``character/`` 命名空间 —— DSL/表里直接引用官方特效路径
    (``battle/effect/skill_unique/<母本>/…``)是裁决 §4 的合法设计,不在这条里。
    """
    problems: list[str] = []
    scanned = 0
    for root in CLIENT_ROOTS:
        base = pack.roots / root / "character" / pack.code
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.name.lower().endswith(BINARY_SUFFIXES):
                continue
            scanned += 1
            leaks = []
            for found in CHARACTER_SEGMENT.findall(_inflate(path.read_bytes())):
                other = found.decode("ascii")
                if other != pack.code and other not in leaks:
                    leaks.append(other)
            if leaks:
                rel = path.relative_to(pack.roots).as_posix()
                problems.append(f"{rel} 内嵌别人的纹理路径 " +
                                ", ".join(f"character/{c}/" for c in leaks) +
                                "(客户端会去取母本图集 → 领取演出 C8003;"
                                "该文件应由 assets 步从母本克隆并改写 code)")
    rep.result(problems, "assets/donor-code-leak", BLOCKING,
               {"files_scanned": scanned, "code": pack.code})


# ---- 像素三件套的自洽（判据来自反编译的客户端播放器，不是推测）
#
# `弹国服/scripts/flatomo/animation/frame/FrameAnimationSource.as`（AIR 反编译原文）::
#
#     _loc8_ = Std.parseInt(_loc7_.substr(param2.name.length));   # _loc7_ = 纹理 id
#     while(_loc3_ < _loc8_) { imageFrames[_loc3_] = _loc6_; _loc3_++; }
#     getImageFrame(tick) => imageFrames[tick - 1]
#
# 三条可机械检查的后果：
#   A. 帧号是拿 **frame.name 的长度**去 `substr` 切出来的 —— 纹理 id 必须是
#      `<frame.name><4 位帧号>`，且 `frame.name` 必须等于本角色自己的
#      `character/<code>/pixelart/{pixelart,special}`。name 指向母本时容器
#      （`ViewAssetContainer/getTextureIds`）按母本名去找，找不到就是领取演出
#      C8003「影像短片尚未加载」（20260920 澄波响/米娅真机事故）。
#   B. `while(_loc3_ < _loc8_)` 从上一条的帧号往后填，**图集条目必须按帧号升序**；
#      乱序会让后面的记录一格都填不到（区间为空）。
#   C. 填表只填到最后一条记录的帧号；`tick > 末帧号` 时 `imageFrames[tick-1]`
#      是 undefined，`int(undefined)` = 0 ⇒ **回落到第 0 条记录**（画面跳回第一帧）。
#      所以最后一条记录的帧号必须等于末序列的 `end`。
#
# **反过来，「序列 begin 之前必须有图可沿用」是错的判据，不要加**：帧是
# END 语义（记录 N 覆盖「上一条记录+1 .. N」这一段），官方 908 张 sheet 里
# 894 张的首条记录都晚于首序列 begin（`neutral loop 1..2` 配首帧 0002 是全库常态，
# `spirit_fire` 更是 `neutral loop 1..600` 只配一条 0600），按「沿用前一帧」
# 判会把官方全判红。20260920 审计曾据此误报索恩 special_land「113 帧只有 1 帧有图」。
PIXEL_SHEETS = (("pixelart", "sprite_sheet"), ("special", "special_sprite_sheet"))


def check_pixel_frames(pack: Pack, rep: Report) -> None:
    """像素 frame/atlas/timeline 三者自洽（判据见上方注释）。"""
    name_problems: list[str] = []
    cover_problems: list[str] = []
    checked: list[str] = []
    base = pack.roots / "common" / "character" / pack.code / "pixelart"

    def read(path: Path) -> Any:
        return wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]

    for kind, stem in PIXEL_SHEETS:
        frame_path = base / f"{kind}.frame.amf3.deflate"
        atlas_path = base / f"{stem}.atlas.amf3.deflate"
        timeline_path = base / f"{kind}.timeline.amf3.deflate"
        if not (frame_path.is_file() and atlas_path.is_file()):
            continue                      # 缺件由 files/keys 那几项管,这里只查自洽
        try:
            frame = read(frame_path)
            entries = read(atlas_path)
        except Exception as exc:
            name_problems.append(f"{kind}: frame/atlas 解不出（{exc}）")
            continue
        checked.append(kind)
        want = f"character/{pack.code}/pixelart/{kind}"
        got = frame.get("name") if isinstance(frame, dict) else None
        if got != want:
            name_problems.append(
                f"{kind}.frame 的 name={got!r}，必须是 {want!r}"
                "（客户端按 name 找纹理容器并按 len(name) 切帧号，指向别人 = 领取演出 C8003）")
            continue                      # name 不对时帧号切法无意义,不再往下判
        numbers: list[int] = []
        for entry in entries if isinstance(entries, list) else []:
            ident = str((entry or {}).get("n") or "")
            tail = ident[len(want):]
            if not ident.startswith(want) or not tail.isdigit():
                name_problems.append(
                    f"{kind}: 图集条目 {ident!r} 不是 <frame.name>+帧号"
                    "（客户端 substr(len(name)) 后 parseInt 会取到垃圾）")
                continue
            numbers.append(int(tail))
        if not numbers:
            continue
        if numbers != sorted(numbers):
            name_problems.append(
                f"{kind}: 图集条目没有按帧号升序（前几条 {numbers[:6]}）"
                "（填表从上一条帧号往后填,乱序会让后面的记录覆盖不到任何 tick）")
        if not timeline_path.is_file():
            continue
        try:
            timeline = read(timeline_path)
        except Exception as exc:
            cover_problems.append(f"{kind}: timeline 解不出（{exc}）")
            continue
        ends = [int(s["end"]) for s in (timeline.get("sequences") or [])
                if isinstance(s, dict) and str(s.get("end", "")).lstrip("-").isdigit()]
        if ends and max(numbers) != max(ends):
            cover_problems.append(
                f"{kind}: 图集末帧号 {max(numbers)} != 末序列 end {max(ends)}"
                "（tick 超过末帧号时 imageFrames 是 undefined,画面回落到第 0 条记录）")

    rep.result(name_problems, "pixel/frame-name-and-ids", BLOCKING,
               {"code": pack.code, "sheets": checked})
    rep.result(cover_problems, "pixel/atlas-covers-sequence-end", BLOCKING,
               {"code": pack.code, "sheets": checked,
                "note": "官方 908 张 sheet 里 906 张满足；两个例外都是 *_assist 援护角色"})


def _alpha_report(pack: Pack) -> Any:
    """半透明像素计数(只报告,不判红;全透明区域 RGB 不检查)。"""
    try:
        from PIL import Image
    except Exception:
        return {"note": "Pillow unavailable; alpha not inspected"}
    out = {}
    base = pack.roots / "common" / "character" / pack.code / "pixelart"
    if not base.is_dir():
        return {"note": "no pixelart dir"}
    import io
    for path in sorted(base.glob("*.png")):
        try:
            # 包内 PNG 魔数是小写 \x89png,PIL 只认大写 —— 喂它之前先还原
            data = path.read_bytes()
            if data[:8] != b"\x89PNG\r\n\x1a\n":
                data = b"\x89PNG\r\n\x1a\n" + data[8:]
            with Image.open(io.BytesIO(data)) as img:
                alpha = img.convert("RGBA").getchannel("A")
        except Exception as exc:
            out[path.name] = {"error": str(exc)}
            continue
        hist = alpha.histogram()
        out[path.name] = {"opaque": hist[255], "transparent": hist[0],
                          "semi": sum(hist[1:255])}
    return out


# ---------------------------------------------------------------- 6. 图集预算

def check_atlas(pack: Pack, rep: Report, *, gbf: bool, threshold: float | None) -> None:
    limit = threshold if threshold is not None else (
        GBF_ATLAS_THRESHOLD if gbf else DEFAULT_ATLAS_THRESHOLD)
    tool = HERE / "wf_atlas_budget_check.py"
    cmd = [sys.executable, str(tool), "--pack", str(pack.workspace), "--quiet"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=600)
    except Exception as exc:
        rep.add("atlas/budget", False, WARNING,
                {"problems": [f"atlas budget check failed to run: {exc}"]})
        return
    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    try:
        payload = json.loads(lines[-1])
    except Exception:
        rep.add("atlas/budget", False, WARNING,
                {"problems": ["atlas budget check produced no JSON line"],
                 "stderr": (proc.stderr or "")[-500:]})
        return
    subject = payload.get("subject") or {}
    pct = subject.get("layer0_pct")
    problems = []
    if isinstance(pct, (int, float)) and pct > limit:
        problems.append(f"subject.layer0_pct={pct} > 阈值 {limit}")
    for scenario in payload.get("scenarios") or []:
        # 基线本身已红是作者已知的既有状态,不算本包的新增红项(验收口径:新增红项才算)
        if scenario.get("fits") is False and scenario.get("baseline_fits") is not False:
            problems.append(f"场景 {scenario.get('scenario')} fits=false"
                            f"(基线 baseline_fits={scenario.get('baseline_fits')},"
                            f"本包边际 {scenario.get('marginal_pct')}%)")
    rep.result(problems, "atlas/budget", BLOCKING,
               {"threshold_pct": limit, "layer0_pct": pct,
                "layer0_sheets": subject.get("layer0_sheets"),
                "scenarios": [{"scenario": s.get("scenario"), "fits": s.get("fits"),
                               "baseline_fits": s.get("baseline_fits"),
                               "marginal_pct": s.get("marginal_pct")}
                              for s in payload.get("scenarios") or []]})


# ---------------------------------------------------------------- 7. 面板文案

def _panel_text(value: str) -> bool:
    """这一格是不是真要上面板的文案。``(None)`` 是官方哨兵,不是文案(空值哨兵陷阱)。"""
    text = (value or "").strip()
    return bool(text) and text != "(None)"


def check_panel(pack: Pack, rep: Report) -> None:
    problems: list[str] = []
    checked = 0
    cas = pack.table(CAS) or {}
    for key in pack.owned_keys(CAS):
        for i, row in enumerate(split_rows(cas.get(key, ""))):
            for col, value in enumerate(row):
                if not _panel_text(value):
                    continue
                checked += 1
                problems += [f"custom_ability_string {key}#{i} c{col}: {p}"
                             for p in KL.panel_problems(value)]
    unique = pack.table(UNIQUE) or {}
    for key in pack.owned_keys(UNIQUE):
        for row in split_rows(unique.get(key, "")):
            name = cell(row, 1)
            if _panel_text(name):
                checked += 1
                problems += [f"unique_condition {key} name: {p}"
                             for p in KL.panel_problems(name)]
    text = pack.table(CHARACTER_TEXT) or {}
    for row in split_rows(text.get(pack.cid, "")):
        for col, value in enumerate(row):
            if not _panel_text(value):
                continue
            checked += 1
            problems += [f"character_text c{col}: {p}" for p in KL.panel_problems(value)]
    rep.result(problems, "panel/forbidden-words", BLOCKING,
               {"texts_checked": checked,
                "rules": list(KL.FORBIDDEN_PANEL_WORDS)})


MAIN_ICON_TAG = "<icon id='main'>"


def check_panel_override_markup(pack: Pack, rep: Report) -> None:
    """``desc_override_<code>_<slot>`` 整槽接管后客户端不再逐行画主位限制图标。

    作者真机 2026-09-21 连报四个角色:漏写图标(看不到 Ⓜ)、写成字面「Ⓜ」(渲染成白字)、
    多条记录用「／」挤成一行(不分行)。判据:主位限制槽(整键 c1 全为 false)的覆盖串每一行
    都带 ``<icon id='main'>``;非主位槽一行都不带;任何覆盖串不含字面「Ⓜ」;多记录槽不许单行「／」。
    """
    problems: list[str] = []
    checked = 0
    cas = pack.table(CAS) or {}
    ability = pack.table(ABILITY) or {}
    prefix = L.PANEL_OVERRIDE_KEY_PREFIX + pack.code

    def lines_of(key: str) -> list[str]:
        rows = split_rows(cas.get(key, ""))
        return cell(rows[0], 0).split("\n") if rows else []

    for slot in range(1, 7):
        rows = split_rows(ability.get(f"{pack.cid}{slot}", ""))
        key = f"{prefix}_{slot}"
        if not rows or key not in cas:
            continue
        checked += 1
        main_only = {cell(row, 1) for row in rows} == {"false"}
        lines = lines_of(key)
        with_icon = sum(1 for line in lines if MAIN_ICON_TAG in line)
        if main_only and with_icon != len(lines):
            problems.append(f"{key}: main-only slot but {with_icon}/{len(lines)} lines carry {MAIN_ICON_TAG}")
        if not main_only and with_icon:
            problems.append(f"{key}: not a main-only slot but {with_icon} lines carry {MAIN_ICON_TAG}")
        if any("Ⓜ" in line for line in lines):
            problems.append(f"{key}: literal 'Ⓜ' renders as plain white text, use {MAIN_ICON_TAG}")
        if len(lines) == 1 and len(rows) > 1 and "／" in lines[0]:
            problems.append(f"{key}: {len(rows)} records squeezed into one line with '／', use line breaks")
    if prefix in cas:
        checked += 1
        lines = lines_of(prefix)
        if len(lines) == 1 and "／" in lines[0]:
            problems.append(f"{prefix}: leader override squeezed into one line with '／', use line breaks")
        if any("Ⓜ" in line for line in lines):
            problems.append(f"{prefix}: literal 'Ⓜ' in leader override")
    rep.result(problems, "panel/override-markup", BLOCKING, {"overrides_checked": checked})


# ---------------------------------------------------------------- 设计稿对照(可选)

def check_design(pack: Pack, rep: Report, design: Path | None) -> None:
    if design is None:
        return
    try:
        payload = json.loads(design.read_text(encoding="utf-8"))
    except Exception as exc:
        rep.add("design/load", False, WARNING,
                {"problems": [f"cannot read design json: {exc}"]})
        return
    problems = []
    plan = payload.get("plan") or {}
    want_unique = set(str(k) for k in (plan.get("unique_conditions") or {}).get("add", []) or []
                      if isinstance(k, str))
    got_unique = set(pack.owned_keys(UNIQUE))
    for key in sorted(want_unique - got_unique):
        problems.append(f"design 声明固有状态 {key},包里没有")
    want_ability = set(str(k) for k in ((plan.get("ability") or {}).get("keys") or {}))
    got_ability = set(pack.owned_keys(ABILITY))
    for key in sorted(want_ability - got_ability):
        problems.append(f"design 声明 ability 键 {key},包里没有")
    rep.result(problems, "design/plan-covered", WARNING,
               {"path": str(design), "schema": payload.get("schema"),
                "deviations": len(payload.get("deviations") or [])})


# ---------------------------------------------------------------- 入口

def verify(workspace: Path, *, root: Path, design: Path | None = None,
           gbf: bool = False, pixel_freeform: bool = False, threshold: float | None = None,
           skip_atlas: bool = False) -> dict[str, Any]:
    pack = Pack(workspace, root)
    rep = Report()
    check_rows(pack, rep)
    check_dsl(pack, rep)
    check_capabilities(pack, rep)
    check_periods(pack, rep)
    check_voice(pack, rep, gbf=gbf)
    check_art(pack, rep, gbf=gbf, pixel_freeform=pixel_freeform)
    check_donor_code_leak(pack, rep)
    check_pixel_frames(pack, rep)
    if not skip_atlas:
        check_atlas(pack, rep, gbf=gbf, threshold=threshold)
    check_panel(pack, rep)
    check_panel_override_markup(pack, rep)
    check_design(pack, rep, design)
    blocking = rep.blocking
    return {
        "schema": SCHEMA,
        "workspace": workspace.as_posix(),
        "package_id": pack.manifest.get("package_id"),
        "character_id": pack.cid,
        "code_name": pack.code,
        "gbf": bool(gbf),
        "pixel_freeform": bool(pixel_freeform),
        "status": "PASS" if not blocking else "BLOCKED",
        "exit_code": 0 if not blocking else 1,
        "counts": {
            "total": len(rep.checks),
            "failed_blocking": len(blocking),
            "failed_warning": len([c for c in rep.checks
                                   if not c["pass"] and c["level"] == WARNING]),
        },
        "blocking": [c["name"] for c in blocking],
        "checks": rep.checks,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="中秋批次角色包机械验证(只读;0=全过 1=有阻断项 2=工具出错)")
    parser.add_argument("--workspace", required=True,
                        help="workspace 目录(仓库根相对路径或绝对路径)")
    parser.add_argument("--design", help="B/design/<key>.json(可选,做覆盖对照)")
    parser.add_argument("--gbf", action="store_true",
                        help="GBF 两人包:图集阈值 5.0,不要求 22 个生成语音槽")
    parser.add_argument("--pixel-freeform", action="store_true",
                        help="像素非母本逐色映射直替(如程序化合成全序列):"
                             "art/pixel-sheet-dims 降级为 warning")
    parser.add_argument("--threshold", type=float, help="覆盖图集 layer0_pct 阈值")
    parser.add_argument("--skip-atlas", action="store_true", help="跳过图集预算子进程")
    parser.add_argument("--out", required=True, help="verify.json 落点")
    parser.add_argument("--root", help="仓库根(默认自动探测)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve() if args.root else Path(core.project_root())
    workspace = Path(args.workspace)
    if not workspace.is_absolute():
        workspace = root / workspace
    design = None
    if args.design:
        design = Path(args.design)
        if not design.is_absolute():
            design = root / design
    try:
        payload = verify(workspace.resolve(), root=root, design=design, gbf=args.gbf,
                         pixel_freeform=args.pixel_freeform,
                         threshold=args.threshold, skip_atlas=args.skip_atlas)
    except Exception as exc:
        out = {"schema": SCHEMA, "status": "ERROR", "exit_code": 2, "error": str(exc)}
        print(json.dumps(out, ensure_ascii=False))
        return 2
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = root / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    for check in payload["checks"]:
        if check["pass"]:
            continue
        print("[%s] %s" % (check["level"].upper(), check["name"]))
        for problem in (check.get("evidence") or {}).get("problems", [])[:6]:
            print("    " + str(problem))
    print(json.dumps({k: payload[k] for k in
                      ("status", "exit_code", "counts", "blocking")}, ensure_ascii=False))
    return int(payload["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
