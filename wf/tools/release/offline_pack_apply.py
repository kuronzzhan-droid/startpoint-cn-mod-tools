#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线整包(武器/模式)投递器 —— 把 flow 认不了的包接到既有发布链上。

## 为什么需要它

本仓已有两条发布通道,离线包一条都走不进去:

  1. ``wf_character_flow.py publish`` —— 只吃**角色工作区**(``workspace.json`` +
     character-pack schema)。武器包/模式包没有那两份契约,``flow status`` 会以
     ``invalid workspace.json`` 正确拒绝。**不要硬塞。**
  2. ``wf_publish.py`` —— 只会把 **store 里已有的字节**打成 diff 边
     (``wf_publish._prepare_files`` 读 ``source_root / relative``),它**不吃包**。

也就是说:缺的不是闸门,是一个「把包写进 store/assets」的**投递器**。本文件补的
就是那一段;铸边仍然交给 ``wf_publish.py``,不另起炉灶。

    离线包.zip ──[本文件 plan]──> plan.json(声明 claim + 服务端增量)
               ──[本文件 apply]──> store/<xx>/<rest> + assets/*.json
               ──[wf_publish --tables ...]──> 链上一条新边

## 三条硬纪律(全部是真机事故换来的)

1. **行级合并,永不整文件覆盖。** ``wf_publish`` 的投递单位是整个文件,本地这份
   比线上少一个键 = 发布即删内容(1.4.278 顶掉基诺维、杰拉德包删三个 PF 键)。
   包里那份整表是**建包当时**的快照,直接落盘就会把之后线上新增的行抹掉。所以
   这里只把 claim 过的行 rebase 到**当前线上**整表上,顺序无关,两个武器包因此
   可以同一轮先后落地。合并复用 ``wf_release.merge_claimed_table_bytes``
   (已被角色发布链覆盖测试),不再写第二份合并实现。

2. **服务端 JSON 必须递归深合并。** 死亡使者的 ``event_item_shop.delta.json``
   写的是 ``["2"]["59001"]``,而线上 ``"2"`` 已经存在且底下有 4 个子项;顶层
   ``dict.update`` 会把那 4 个静默抹掉。深度 >0 的数组要求**逐字节相等**,不做
   union —— 猜测式合并数组是这一类文件里最容易静默毁数据的动作。

3. **绝不裸跑 ``wf_publish.py``。** ``wf_publish`` 只有在 ``--tables`` 缺席时才
   读 ``work/sync_pending.json``,也只有那时才在末尾把它清空
   (见 ``wf_publish.py`` 的 ``_explicit_logicals`` 分支与 ``main`` 末尾)。作者
   pending 里那 12 条是他自己的账,所以本文件的 ``publish`` 子命令**永远**显式
   传 ``--tables``,并在调用前后核对 pending 的 sha256;不一致就报错。

## 包声明的闸门

三个包自己都写着 ``publishing_allowed=false`` / ``review_only=true``。作者可以
授权翻开,但本工具不把这个字段当没看见:必须显式 ``--author-approved``,而且
被翻开的每一条都会原样记进 plan/receipt 的 ``gate_overrides``。

## 用法

    # 只读演练:校验 + 漂移 + 冲突 + 在内存里把合并跑完
    python mod-tools/wf_offline_pack_apply.py plan \\
        --pack <a.zip> --pack <b.zip> --out work/offline_apply/plan.json

    # 落盘(备份 + 原子写),要求 plan 已产出、服务端已停
    python mod-tools/wf_offline_pack_apply.py apply \\
        --plan work/offline_apply/plan.json --pack-id <id> --author-approved

    # 铸边(永远带 --tables,从不碰 pending)
    python mod-tools/wf_offline_pack_apply.py publish \\
        --plan work/offline_apply/plan.json --pack-id <id>
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

TOOLS = Path(__file__).resolve().parents[3]
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_mod_tool as core  # noqa: E402

SCHEMA_VERSION = 1
PLAN_SCHEMA = "wf-offline-pack-apply-plan/v1"

# 包 manifest 的 schema -> 适配器。新离线包在这里登记,不改既有工具。
ADAPTERS: dict[str, str] = {
    "wf-five-boss-weapon-package/v1": "five_boss_weapon",
    "wf-abyss-weapon-awakening-review/v1": "abyss_weapon_awakening",
    "wf-five-boss-mode-package/v2": "five_boss_mode",
}

SERVER_ASSETS_DIR = ROOT / "assets"
PENDING_PATH = TOOLS / "work" / "sync_pending.json"


class ApplyError(RuntimeError):
    """投递未提交:要么在校验阶段停下,要么已经回滚。"""


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _read_json_bytes(payload: bytes, label: str) -> Any:
    try:
        return json.loads(payload.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - 报出上下文比类型重要
        raise ApplyError(f"{label}: 不是合法 JSON ({type(exc).__name__}: {exc})") from exc


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def server_running(repo_root: Path = ROOT) -> bool:
    """与 wf_release._server_running 同判据:从 .env 读监听地址后探测。"""
    values: dict[str, str] = {}
    try:
        lines = (repo_root / ".env").read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        token = line.strip()
        if not token or token.startswith("#") or "=" not in token:
            continue
        key, value = token.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    host = os.environ.get("CN_LISTEN_HOST") or values.get("CN_LISTEN_HOST") or "127.0.0.1"
    port = os.environ.get("CN_LISTEN_PORT") or values.get("CN_LISTEN_PORT") or "8001"
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1"
    try:
        with socket.create_connection((host, int(port)), timeout=0.3):
            return True
    except (OSError, ValueError):
        return False


# ---------------------------------------------------------------------------
# orderedmap 编解码:codec 由**双向探测**决定,不靠表名白名单猜
# ---------------------------------------------------------------------------

def detect_codec(candidate: bytes, live: bytes, logical: str) -> str:
    """选一个 candidate 与 live 都能解、且 live 能原样重建键集的 codec。

    ``flat`` 解压行(zlib),``raw_outer`` 把行当不透明字节。很多表两个都能解
    (行本来就是 zlib 时 raw_outer 也不报错),此时优先 ``flat``:它与既有角色
    发布链对同名表的处理一致,产出的字节形状不会在两条通道之间分叉。
    """
    for codec, compressed in (("flat", True), ("raw_outer", False)):
        try:
            core._strict_orderedmap_rows(  # type: ignore[attr-defined]
                candidate, label=f"candidate:{logical}", compressed_rows=compressed)
            core._strict_orderedmap_rows(  # type: ignore[attr-defined]
                live, label=f"live:{logical}", compressed_rows=compressed)
        except Exception:
            continue
        return codec
    raise ApplyError(f"{logical}: candidate 与 live 没有共同可解的 codec")


def read_rows(payload: bytes, codec: str, label: str) -> tuple[list[str], list[bytes]]:
    return core._strict_orderedmap_rows(  # type: ignore[attr-defined]
        payload, label=label, compressed_rows=(codec == "flat"))


def merge_rows(claim_logical: str, codec: str, claimed: Sequence[str],
               candidate: bytes, live: bytes) -> bytes:
    """行级 rebase。合并实现复用 wf_release,不写第二份。"""
    import wf_character_pack as character_pack
    import wf_release

    claim = character_pack.TableClaim(
        root="common",
        logical_path=claim_logical,
        codec_id=codec,
        outer_keys=tuple(claimed),
    )
    try:
        return wf_release.merge_claimed_table_bytes(claim, candidate, live)
    except Exception as exc:  # noqa: BLE001
        raise ApplyError(f"{claim_logical}: 行级合并失败 ({exc})") from exc


def nested_inner_diff(candidate_row: bytes, live_row: bytes) -> dict[str, Any] | None:
    """一行本身又是一张 orderedmap 时,把内层 diff 摊出来;不是嵌套返回 None。

    外层整行替换在嵌套表上等于「用包里那份内层表整体顶掉线上那份」—— 与整表
    覆盖同一类事故,只是往下沉了一层。本函数让 plan 能看见它,而不是静默做掉。
    """
    for compressed in (True, False):
        try:
            cand_keys, cand_rows = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
                candidate_row, label="candidate-inner", compressed_rows=compressed)
            live_keys, live_rows = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
                live_row, label="live-inner", compressed_rows=compressed)
        except Exception:
            continue
        cand_map = dict(zip(cand_keys, cand_rows))
        live_map = dict(zip(live_keys, live_rows))
        return {
            "compressed": compressed,
            "added": [k for k in cand_keys if k not in live_map],
            "changed": [k for k in cand_keys if k in live_map and live_map[k] != cand_map[k]],
            "dropped": [k for k in live_keys if k not in cand_map],
        }
    return None


def build_rows(keys: Sequence[str], rows: Sequence[bytes], *, compressed: bool) -> bytes:
    """keys/rows -> orderedmap 字节。复用 core 的两个 builder,不重写编码。"""
    ordered = core.OrderedMap("<in-memory>", list(keys), list(rows), Path("."))
    return (core.build_orderedmap(ordered) if compressed
            else core.build_orderedmap_raw_rows(ordered))


def graft_inner_added(candidate_row: bytes, live_row: bytes,
                      compressed: bool, added: Sequence[str]) -> bytes:
    """把包里**新增**的内层键嫁接到线上那份内层表上,线上原有内层行一字不改。

    外层做行级合并的同一条纪律往下沉一层:包是快照,线上是真相。包里"改动"了的
    内层行按定义是快照漂移,不是投递意图 —— 一律丢弃,由调用方显式记账。
    """
    cand_keys, cand_rows = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
        candidate_row, label="graft-candidate-inner", compressed_rows=compressed)
    live_keys, live_rows = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
        live_row, label="graft-live-inner", compressed_rows=compressed)
    cand_map = dict(zip(cand_keys, cand_rows))
    out_keys = list(live_keys)
    out_rows = list(live_rows)
    for key in added:
        if key in set(live_keys):
            raise ApplyError(f"内层嫁接: {key} 线上已存在,不是新增")
        if key not in cand_map:
            raise ApplyError(f"内层嫁接: 包里没有内层键 {key}")
        out_keys.append(key)
        out_rows.append(cand_map[key])
    return build_rows(out_keys, out_rows, compressed=compressed)


def verify_merged(logical: str, codec: str, claimed: Sequence[str],
                  candidate: bytes, live: bytes, merged: bytes) -> None:
    """合并后逐行复核 —— codec 选错、编码器跑偏都在这里露头。

    判据三条:
      * 键集合 == live 键 ∪ claim 键(既不多也不少);
      * 每个**没 claim** 的键,行字节与 live 相同(证明不是整表快照覆盖);
      * 每个 claim 过的键,行字节与包里那份相同(证明确实投递了包的内容)。
    """
    live_keys, live_rows = read_rows(live, codec, f"live:{logical}")
    cand_keys, cand_rows = read_rows(candidate, codec, f"candidate:{logical}")
    out_keys, out_rows = read_rows(merged, codec, f"merged:{logical}")
    live_map = dict(zip(live_keys, live_rows))
    cand_map = dict(zip(cand_keys, cand_rows))
    out_map = dict(zip(out_keys, out_rows))

    expected = list(live_keys) + [k for k in claimed if k not in live_map]
    if out_keys != expected:
        missing = [k for k in expected if k not in out_map]
        extra = [k for k in out_keys if k not in set(expected)]
        raise ApplyError(
            f"{logical}: 合并后键集合不符 (缺 {missing[:8]} / 多 {extra[:8]})")
    claimed_set = set(claimed)
    for key in out_keys:
        if key in claimed_set:
            if out_map[key] != cand_map.get(key):
                raise ApplyError(f"{logical}: claim 行 {key} 的字节不是包里那份")
        else:
            if out_map[key] != live_map.get(key):
                raise ApplyError(f"{logical}: 未 claim 的行 {key} 被改动了")


# ---------------------------------------------------------------------------
# 服务端 JSON 深合并
# ---------------------------------------------------------------------------

@dataclass
class MergeOp:
    action: str          # add | append | replace
    path: tuple[str, ...]
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"action": self.action, "path": list(self.path), "detail": self.detail}


def deep_merge_json(live: Any, delta: Any, *, path: tuple[str, ...] = (),
                    ops: list[MergeOp] | None = None,
                    allow_overwrite: bool = False, depth: int = 0) -> Any:
    """把 delta 递归合进 live,返回合并结果(live 不被原地改写)。

    * dict:逐键递归。目标键不存在 = 整棵子树原样加入。
    * list:**只有根层**(depth==0)做保序 union;深度 >0 的数组要求逐字节相等,
      否则报冲突。理由见模块头第 2 条 —— 猜测式合并嵌套数组会静默改语义。
    * 标量:相等则无操作;不等要 ``allow_overwrite`` 才放行,并记一条 replace。
    """
    if ops is None:
        ops = []
    where = "/".join(path) or "<root>"

    if isinstance(delta, dict):
        if not isinstance(live, dict):
            raise ApplyError(f"服务端合并冲突 {where}: 包给的是对象,线上是 {type(live).__name__}")
        out = dict(live)
        for key, value in delta.items():
            if key in out:
                out[key] = deep_merge_json(
                    out[key], value, path=path + (key,), ops=ops,
                    allow_overwrite=allow_overwrite, depth=depth + 1)
            else:
                out[key] = copy.deepcopy(value)
                ops.append(MergeOp("add", path + (key,)))
        return out

    if isinstance(delta, list):
        if not isinstance(live, list):
            raise ApplyError(f"服务端合并冲突 {where}: 包给的是数组,线上是 {type(live).__name__}")
        if depth > 0:
            if canonical_json(live) != canonical_json(delta):
                raise ApplyError(
                    f"服务端合并冲突 {where}: 嵌套数组不一致,本工具不做猜测式数组合并")
            return list(live)
        out = list(live)
        seen = {canonical_json(item) for item in out}
        for item in delta:
            token = canonical_json(item)
            if token in seen:
                continue
            seen.add(token)
            out.append(copy.deepcopy(item))
            ops.append(MergeOp("append", path, token.decode("utf-8")[:120]))
        return out

    if live == delta:
        return live
    if not allow_overwrite:
        raise ApplyError(
            f"服务端合并冲突 {where}: 线上已有不同的值 "
            f"({json.dumps(live, ensure_ascii=False)[:80]} -> "
            f"{json.dumps(delta, ensure_ascii=False)[:80]})")
    ops.append(MergeOp("replace", path, json.dumps(delta, ensure_ascii=False)[:120]))
    return copy.deepcopy(delta)


JSON_STYLE_CANDIDATES: tuple[dict[str, Any], ...] = tuple(
    style
    for ensure_ascii in (False, True)
    for style in (
        {"ensure_ascii": ensure_ascii, "separators": (", ", ": ")},
        {"ensure_ascii": ensure_ascii, "separators": (",", ":")},
        *({"ensure_ascii": ensure_ascii, "indent": indent}
          for indent in (0, 1, 2, 3, 4, "\t")),
    )
)


def detect_json_style(raw: bytes, value: Any) -> dict[str, Any]:
    """认出 assets/*.json 原本的排版,好让写回只动该动的那几行。

    这 11 个文件的排版**不统一**:热重载那一批(event_item_shop 等)是紧凑单行,
    另外六个是 1/2/4 空格缩进,equipment_ids 还是 indent=0。统一改成一种写法会让
    作者的 WIP diff 里出现整文件重排,把真正的改动淹掉,所以按文件各自还原。
    """
    text = raw.decode("utf-8")
    body = text.rstrip("\n")
    trailing = text[len(body):]
    for candidate in JSON_STYLE_CANDIDATES:
        try:
            if json.dumps(value, **candidate) == body:
                return {**candidate, "trailing": trailing, "matched": True}
        except (TypeError, ValueError):
            continue
    return {"ensure_ascii": False, "separators": (", ", ": "),
            "trailing": trailing, "matched": False}


def dump_json_like(value: Any, style: Mapping[str, Any]) -> bytes:
    kwargs = {k: v for k, v in style.items() if k not in {"trailing", "matched"}}
    if isinstance(kwargs.get("separators"), list):  # 从 plan JSON 读回来会变成 list
        kwargs["separators"] = tuple(kwargs["separators"])
    return (json.dumps(value, **kwargs) + style.get("trailing", "")).encode("utf-8")


def diff_json_additions(baseline: Any, candidate: Any, *,
                        path: tuple[str, ...] = ()) -> Any | None:
    """从「整文件包」里提取相对 baseline 的新增/变更子树,得到一个等价 delta。

    觉醒包给的是**整个** ``assets/*.json``,而不是增量。直接落盘会把之后线上的
    其它改动(比如同轮先落地的死亡使者行)抹掉,所以先把它降级成 delta。
    返回 None 表示这一支没有差异。
    """
    if isinstance(baseline, dict) and isinstance(candidate, dict):
        out: dict[str, Any] = {}
        for key, value in candidate.items():
            if key not in baseline:
                out[key] = copy.deepcopy(value)
                continue
            sub = diff_json_additions(baseline[key], value, path=path + (key,))
            if sub is not None:
                out[key] = sub
        removed = [k for k in baseline if k not in candidate]
        if removed:
            where = "/".join(path) or "<root>"
            raise ApplyError(
                f"包里的整文件在 {where} 少了线上已有的键 {removed[:8]} —— 陈旧快照,拒绝投递")
        return out or None
    if isinstance(baseline, list) and isinstance(candidate, list):
        base_tokens = {canonical_json(i) for i in baseline}
        added = [i for i in candidate if canonical_json(i) not in base_tokens]
        cand_tokens = {canonical_json(i) for i in candidate}
        removed = [i for i in baseline if canonical_json(i) not in cand_tokens]
        if removed:
            where = "/".join(path) or "<root>"
            raise ApplyError(
                f"包里的整文件在 {where} 少了线上已有的数组元素({len(removed)} 个) —— 陈旧快照,拒绝投递")
        return added or None
    if baseline == candidate:
        return None
    return copy.deepcopy(candidate)


# ---------------------------------------------------------------------------
# 包读取
# ---------------------------------------------------------------------------

@dataclass
class TablePayload:
    logical: str
    member: str
    payload: bytes


@dataclass
class ResourcePayload:
    logical: str
    member: str
    payload: bytes
    channel: str = "common"


@dataclass
class ServerPayload:
    asset: str            # assets/ 下的文件名
    member: str
    kind: str             # delta | full
    value: Any


@dataclass
class LoadedPack:
    pack_id: str
    adapter: str
    zip_path: Path
    zip_sha256: str
    manifest: dict[str, Any]
    tables: list[TablePayload] = field(default_factory=list)
    resources: list[ResourcePayload] = field(default_factory=list)
    server: list[ServerPayload] = field(default_factory=list)
    declared_baselines: dict[str, str] = field(default_factory=dict)
    gate_flags: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    excluded_members: list[str] = field(default_factory=list)


def _verify_checksums(archive: zipfile.ZipFile, pack_id: str) -> None:
    """SHA256SUMS + manifest.members 双向核对。"""
    names = set(archive.namelist())
    if "SHA256SUMS" in names:
        listed: dict[str, str] = {}
        for line in archive.read("SHA256SUMS").decode("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            digest, _, name = line.partition("  ")
            if not name:
                digest, _, name = line.partition(" ")
            listed[name.strip().lstrip("*")] = digest.strip()
        for name, digest in listed.items():
            if name not in names:
                raise ApplyError(f"{pack_id}: SHA256SUMS 列了不存在的成员 {name}")
            actual = sha256_bytes(archive.read(name))
            if actual != digest:
                raise ApplyError(
                    f"{pack_id}: {name} 哈希不符 (SHA256SUMS={digest} 实际={actual})")
        uncovered = [
            n for n in names
            if n not in listed and n != "SHA256SUMS" and not n.endswith("/")
        ]
        if uncovered:
            raise ApplyError(f"{pack_id}: SHA256SUMS 没覆盖 {uncovered[:6]}")
    members = archive.read("manifest.json")
    manifest = _read_json_bytes(members, f"{pack_id}: manifest.json")
    declared = manifest.get("members")
    if isinstance(declared, list):
        for entry in declared:
            if not isinstance(entry, dict):
                continue
            name = entry.get("path")
            digest = entry.get("sha256")
            size = entry.get("size")
            if not isinstance(name, str) or not isinstance(digest, str):
                continue
            if name not in names:
                raise ApplyError(f"{pack_id}: manifest 列了不存在的成员 {name}")
            body = archive.read(name)
            if sha256_bytes(body) != digest:
                raise ApplyError(f"{pack_id}: manifest 成员 {name} 哈希不符")
            if isinstance(size, int) and len(body) != size:
                raise ApplyError(f"{pack_id}: manifest 成员 {name} 大小不符")


def _gate_flags(manifest: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "publishing_allowed", "publishingAllowed", "review_only", "reviewOnly",
        "deployable", "content_deployable", "activation_enabled",
        "runtime_verified", "required_server_capability", "publish_actions_present",
    )
    return {k: manifest[k] for k in keys if k in manifest}


def _load_five_boss_weapon(archive: zipfile.ZipFile, manifest: dict[str, Any],
                           pack_id: str, prefix: str = "") -> LoadedPack:
    """死亡使者形态:roots/common 已经是 store 地址,服务端给的是 .delta.json。"""
    pack = LoadedPack(
        pack_id=pack_id, adapter="five_boss_weapon", zip_path=Path(archive.filename or ""),
        zip_sha256="", manifest=manifest, gate_flags=_gate_flags(manifest),
    )
    logicals = manifest.get("client_logicals") or []
    address_map: dict[str, str] = {}
    for logical in logicals:
        digest = core.sha1_path(logical)
        address_map[f"{prefix}roots/common/{digest[:2]}/{digest[2:]}"] = logical
    resources_member = f"{prefix}evidence/resources.json"
    resource_map: dict[str, tuple[str, str]] = {}
    if resources_member in archive.namelist():
        evidence = _read_json_bytes(archive.read(resources_member), resources_member)
        for asset in evidence.get("assets", []):
            member = f"{prefix}{asset['member']}"
            resource_map[member] = (asset["logical"], asset.get("channel", "common"))

    for name in sorted(archive.namelist()):
        if not name.startswith(f"{prefix}roots/"):
            continue
        if name in address_map:
            pack.tables.append(TablePayload(address_map[name], name, archive.read(name)))
        elif name in resource_map:
            logical, channel = resource_map[name]
            digest = core.sha1_path(logical)
            expected = f"{prefix}roots/common/{digest[:2]}/{digest[2:]}"
            if expected != name:
                raise ApplyError(
                    f"{pack_id}: 资源 {logical} 的 store 地址与成员名不符 "
                    f"(成员={name} 期望={expected})")
            pack.resources.append(
                ResourcePayload(logical, name, archive.read(name), channel))
        elif name.startswith(f"{prefix}roots/server/assets/"):
            base = name.rsplit("/", 1)[-1]
            if not base.endswith(".delta.json"):
                raise ApplyError(f"{pack_id}: 服务端成员 {name} 不是 .delta.json")
            asset = base[: -len(".delta.json")] + ".json"
            pack.server.append(ServerPayload(
                asset, name, "delta", _read_json_bytes(archive.read(name), name)))
        elif not name.endswith("/"):
            raise ApplyError(f"{pack_id}: roots 下有认不出的成员 {name}")

    found = {t.logical for t in pack.tables}
    missing = [lg for lg in logicals if lg not in found]
    if missing:
        raise ApplyError(f"{pack_id}: manifest 声明的表在包里缺失 {missing}")
    return pack


def _load_abyss_awakening(archive: zipfile.ZipFile, manifest: dict[str, Any],
                          pack_id: str) -> LoadedPack:
    """觉醒形态:roots/common 用明文逻辑路径,服务端给的是**整文件**。"""
    pack = LoadedPack(
        pack_id=pack_id, adapter="abyss_weapon_awakening",
        zip_path=Path(archive.filename or ""), zip_sha256="", manifest=manifest,
        gate_flags=_gate_flags(manifest),
    )
    snapshot = manifest.get("sourceSnapshot") or {}
    for key, digest in snapshot.items():
        kind, _, name = str(key).partition(":")
        if kind == "client":
            pack.declared_baselines[f"client:{name}"] = digest
        elif kind == "server":
            pack.declared_baselines[f"server:{name}"] = digest
        else:
            pack.notes.append(f"未纳入漂移比对的基线声明: {key}")

    for name in sorted(archive.namelist()):
        if name.startswith("roots/common/"):
            pack.tables.append(
                TablePayload(name[len("roots/common/"):], name, archive.read(name)))
        elif name.startswith("roots/server/assets/"):
            asset = name.rsplit("/", 1)[-1]
            pack.server.append(ServerPayload(
                asset, name, "full", _read_json_bytes(archive.read(name), name)))
        elif name.startswith("client-patch/"):
            pack.excluded_members.append(name)
            pack.notes.append(
                f"{name}: APK 客户端补丁,本通道**不投递**(APK 由作者另行构建签名)")

    marker = manifest.get("clientPatchMarker")
    if marker:
        pack.notes.append(
            f"包声明的 APK 门禁标记 = {marker};数据投递不改变设备上已装 APK 的门禁档位")
    return pack


def _grep_src(patterns: Sequence[str]) -> list[str]:
    """在 src/ 全树(含未跟踪文件)搜字面量,返回命中文件的相对路径。

    刻意不走 git ls-files:集成中的代码常常还没提交,按已跟踪文件搜会给出假阴性。
    """
    src = ROOT / "src"
    if not src.is_dir():
        return []
    hits: list[str] = []
    for path in src.rglob("*.ts"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(pat in text for pat in patterns):
            hits.append(path.relative_to(ROOT).as_posix())
    return sorted(hits)


def _missing_runtime_targets(runtime_members: Sequence[str]) -> list[str]:
    """server-runtime/{source,test}/<repo 相对路径>.snapshot -> 本仓是否已有该文件。"""
    missing: list[str] = []
    for name in runtime_members:
        if not name.endswith(".snapshot"):
            continue
        rest = name[len("server-runtime/"):]
        for prefix in ("source/", "test/"):
            if rest.startswith(prefix):
                rest = rest[len(prefix):]
                break
        else:
            continue
        target = ROOT / rest[: -len(".snapshot")]
        if not target.is_file():
            missing.append(target.relative_to(ROOT).as_posix())
    return missing


def _load_five_boss_mode(archive: zipfile.ZipFile, manifest: dict[str, Any],
                         pack_id: str) -> LoadedPack:
    """五重决战形态:四类载荷,只有其中两类是本通道能投的数据。"""
    pack = LoadedPack(
        pack_id=pack_id, adapter="five_boss_mode", zip_path=Path(archive.filename or ""),
        zip_sha256="", manifest=manifest, gate_flags=_gate_flags(manifest),
    )
    names = archive.namelist()

    runtime = [n for n in names if n.startswith("server-runtime/")]
    modes = [n for n in names if n.startswith(("modes.d/", "modes-src/"))]
    pack.excluded_members.extend(sorted(runtime + modes))

    if runtime:
        # 本通道从不投源码。但源码可能已由别的途径(分支合并/人工集成)进了 src/,
        # 那种情况下再拿"需要改 src/"当阻断就是假阴性 —— 逐个核对快照对应的落点。
        missing = sorted(_missing_runtime_targets(runtime))
        n_snap = len([n for n in runtime if n.endswith(".snapshot")])
        if missing:
            pack.blockers.append(
                f"包含 {n_snap} 份服务端 TypeScript 源码快照(server-runtime/),"
                f"其中 {len(missing)} 份在本仓 src/ 里没有对应文件,落地需要改 src/ —— "
                f"本通道只投数据,不改服务端源码。缺: {missing[:6]}")
        else:
            pack.notes.append(
                f"server-runtime/ 的 {n_snap} 份源码快照在本仓 src/ 里都已存在(已由其他途径集成);"
                "本通道仍然不投源码,只投数据")
    if modes:
        # 注意:这里必须真的 grep。历史版本写死了阻断却在文案里声称做过 grep,
        # 装载器落地后依然一律拦下 —— 典型假阴性。
        hits = _grep_src(("modes.d", "modes-allowlist", "requiresServerCapabilities"))
        if not hits:
            pack.blockers.append(
                "包含 modes.d 模式插件,但本仓 src/ 里没有任何 modes.d 装载器"
                "(grep modes.d / requiresServerCapabilities / modes-allowlist 全零命中),"
                "插件永远不会被加载")
        else:
            pack.notes.append(
                f"modes.d 装载器已在本仓 src/ 落地({len(hits)} 个文件命中);"
                "本通道不投插件本体,请确认 modes.d/ 下已就位")
    capability = manifest.get("required_server_capability")
    if capability:
        cap_hits = _grep_src((capability,))
        if not cap_hits:
            pack.blockers.append(
                f"包要求服务端显式提供能力 {capability};本仓无该能力的任何实现或声明")
        else:
            pack.notes.append(
                f"服务端能力 {capability} 已在本仓声明({len(cap_hits)} 个文件命中)")

    route_prefix = "content/route-review/"
    if any(n.startswith(route_prefix) for n in names):
        route_manifest = _read_json_bytes(
            archive.read(route_prefix + "manifest.json"), route_prefix + "manifest.json")
        for name in sorted(names):
            if not name.startswith(route_prefix + "roots/"):
                continue
            if name.startswith(route_prefix + "roots/common/"):
                pack.tables.append(TablePayload(
                    name[len(route_prefix + "roots/common/"):], name, archive.read(name)))
            elif name.startswith(route_prefix + "roots/server/assets/"):
                base = name.rsplit("/", 1)[-1]
                if not base.endswith(".delta.json"):
                    raise ApplyError(f"{pack_id}: 路线服务端成员 {name} 不是 .delta.json")
                pack.server.append(ServerPayload(
                    base[: -len(".delta.json")] + ".json", name, "delta",
                    _read_json_bytes(archive.read(name), name)))
        pack.notes.append(
            f"content/route-review 的 route_id={route_manifest.get('route_id')}"
            " 是纯数据,但门票只能由缺失的服务端运行时发放")

    dbr_prefix = "content/deathbringer/"
    if any(n.startswith(dbr_prefix) for n in names):
        seal = manifest.get("deathbringer_seal_sha256")
        pack.notes.append(
            "content/deathbringer 与独立的死亡使者包内容重复"
            f"(seal={seal});本通道不重复投递,请只发独立包")
        pack.excluded_members.extend(sorted(n for n in names if n.startswith(dbr_prefix)))
    return pack


def load_pack(zip_path: Path, *, pack_id: str | None = None) -> LoadedPack:
    zip_path = Path(zip_path)
    body = zip_path.read_bytes()
    digest = sha256_bytes(body)
    with zipfile.ZipFile(zip_path) as archive:
        if "manifest.json" not in archive.namelist():
            raise ApplyError(f"{zip_path.name}: 缺 manifest.json,不是离线包")
        manifest = _read_json_bytes(archive.read("manifest.json"), "manifest.json")
        schema = manifest.get("schema")
        adapter = ADAPTERS.get(str(schema))
        if adapter is None:
            raise ApplyError(
                f"{zip_path.name}: 未登记的包 schema {schema!r};"
                f"已知 {sorted(ADAPTERS)}")
        resolved_id = (
            pack_id or manifest.get("package_id") or manifest.get("packageId")
            or zip_path.stem)
        _verify_checksums(archive, resolved_id)
        if adapter == "five_boss_weapon":
            pack = _load_five_boss_weapon(archive, manifest, resolved_id)
        elif adapter == "abyss_weapon_awakening":
            pack = _load_abyss_awakening(archive, manifest, resolved_id)
        else:
            pack = _load_five_boss_mode(archive, manifest, resolved_id)
    pack.zip_path = zip_path
    pack.zip_sha256 = digest
    return pack


# ---------------------------------------------------------------------------
# 计划
# ---------------------------------------------------------------------------

@dataclass
class Environment:
    store: Path
    assets: Path

    @classmethod
    def resolve(cls, store: Path | None = None, assets: Path | None = None) -> "Environment":
        if store is None:
            value = core.resolve_active_store(ROOT, profile=core.resolve_profile())
            if not value:
                raise ApplyError("未找到数据包 store。" + core.TARGET_STORE_HINT)
            store = Path(value)
        return cls(store=Path(store).resolve(), assets=Path(assets or SERVER_ASSETS_DIR).resolve())

    def table_path(self, logical: str) -> Path:
        return core.table_path(self.store, logical)

    def asset_path(self, name: str) -> Path:
        return self.assets / name


def plan_pack(pack: LoadedPack, env: Environment, *,
              author_approved: bool,
              tolerate_live_keys: Iterable[str] = (),
              graft_inner: Iterable[str] = ()) -> dict[str, Any]:
    """只读:核对基线、导出 claim、把合并整个跑一遍(结果不落盘)。"""
    graft_inner = set(graft_inner)
    report: dict[str, Any] = {
        "pack_id": pack.pack_id,
        "adapter": pack.adapter,
        "zip": str(pack.zip_path),
        "zip_sha256": pack.zip_sha256,
        "gate_flags": pack.gate_flags,
        # 包自己声明的 seal:本工具**不重算**(算法在各自的打包器里,那些打包器只
        # 存在于对应 worktree)。完整性由 SHA256SUMS + manifest.members 双向核对
        # 保证 —— 覆盖同一批字节,只是不复算那一个摘要。
        "declared_seal": pack.manifest.get("seal_sha256") or pack.manifest.get("sealSha256"),
        "seal_recomputed": False,
        "gate_overrides": [],
        "blockers": list(pack.blockers),
        "notes": list(pack.notes),
        "excluded_members": list(pack.excluded_members),
        "tables": [],
        "resources": [],
        "server": [],
        "publish_logicals": [],
    }

    restrictive = [
        f"{key}={value!r}" for key, value in pack.gate_flags.items()
        if (key in {"publishing_allowed", "publishingAllowed", "deployable",
                    "activation_enabled"} and value is False)
        or (key in {"review_only", "reviewOnly"} and value is True)
    ]
    if restrictive:
        if not author_approved:
            report["blockers"].append(
                "包自己声明了限制标志(" + ", ".join(restrictive) +
                ");作者授权后加 --author-approved 才放行")
        else:
            report["gate_overrides"] = restrictive

    # --- 声明基线漂移 ------------------------------------------------------
    drift: list[dict[str, Any]] = []
    for key, expected in sorted(pack.declared_baselines.items()):
        kind, _, name = key.partition(":")
        path = env.table_path(name) if kind == "client" else env.asset_path(name)
        actual = sha256_bytes(path.read_bytes()) if path.exists() else None
        drift.append({
            "target": key, "expected": expected, "actual": actual,
            "same": actual == expected,
        })
    report["declared_baselines"] = drift
    drifted = [d["target"] for d in drift if not d["same"]]
    if drifted:
        report["blockers"].append(f"包声明的基线与线上不一致: {drifted}")

    # --- 客户端表 ----------------------------------------------------------
    for table in pack.tables:
        live_path = env.table_path(table.logical)
        entry: dict[str, Any] = {
            "logical": table.logical,
            "member": table.member,
            "store_relative": "/".join(live_path.parts[-2:]),
            "candidate_sha256": sha256_bytes(table.payload),
        }
        if not live_path.exists():
            entry["status"] = "live-missing"
            report["blockers"].append(f"{table.logical}: 线上 store 里没有这张表")
            report["tables"].append(entry)
            continue
        live = live_path.read_bytes()
        codec = detect_codec(table.payload, live, table.logical)
        cand_keys, cand_rows = read_rows(table.payload, codec, f"candidate:{table.logical}")
        live_keys, live_rows = read_rows(live, codec, f"live:{table.logical}")
        cand_map = dict(zip(cand_keys, cand_rows))
        live_map = dict(zip(live_keys, live_rows))
        added = [k for k in cand_keys if k not in live_map]
        changed = [k for k in cand_keys if k in live_map and live_map[k] != cand_map[k]]
        dropped = [k for k in live_keys if k not in cand_map]
        claimed = added + changed
        entry.update({
            "codec": codec, "live_sha256": sha256_bytes(live),
            "live_rows": len(live_keys), "candidate_rows": len(cand_keys),
            "added": added, "changed": changed, "dropped": dropped,
            "claimed_keys": claimed,
            # apply 时用它判断「plan 之后有人动过这些行」
            "claimed_baseline": {
                k: (sha256_bytes(live_map[k]) if k in live_map else None) for k in claimed
            },
        })
        tolerated = set(tolerate_live_keys)
        unexpected = [k for k in dropped if k not in tolerated]
        if unexpected:
            entry["status"] = "stale-snapshot"
            report["blockers"].append(
                f"{table.logical}: 包里少了线上已有的 {len(unexpected)} 个键 "
                f"{unexpected[:6]} —— 陈旧快照,发出去就是删内容。"
                "(如果线上已经落了同轮另一个包的行,请回到 apply 之前的基线重跑 plan,"
                "或用 --tolerate-live-key 逐个列出可以缺的键)")
            report["tables"].append(entry)
            continue
        if dropped:
            entry["tolerated_dropped"] = dropped
            report["notes"].append(
                f"{table.logical}: 包里没有线上的 {dropped} —— 已按 --tolerate-live-key 放行;"
                "行级合并会原样保留它们")
        if not claimed:
            entry["status"] = "no-op"
            report["tables"].append(entry)
            continue

        # 嵌套行:外层整行替换会把内层整张表顶掉,必须先摊开看
        nested: dict[str, Any] = {}
        for key in changed:
            inner = nested_inner_diff(cand_map[key], live_map[key])
            if inner is None:
                continue
            nested[key] = inner
            if inner["dropped"]:
                report["blockers"].append(
                    f"{table.logical}[{key}]: 这一行是嵌套表,包里那份少了线上已有的"
                    f" {len(inner['dropped'])} 个内层键 {inner['dropped'][:6]}")
            elif inner["changed"] and table.logical not in graft_inner:
                report["blockers"].append(
                    f"{table.logical}[{key}]: 这一行是嵌套表,整行替换会连带改写"
                    f" {len(inner['changed'])} 个内层键 {inner['changed'][:6]};"
                    "本通道只做外层行级合并,不做内层合并"
                    "(只想投包里新增的内层键,用 --graft-inner 指定这张表)")
        if nested:
            entry["nested"] = nested

        # --graft-inner:内层也按行级合并 —— 只嫁接包里新增的内层键,
        # 线上原有内层行一字不动,包里"改动"的内层行按快照漂移丢弃并记账。
        grafted: dict[str, Any] = {}
        if table.logical in graft_inner and nested:
            if any(n["dropped"] for n in nested.values()):
                report["blockers"].append(
                    f"{table.logical}: --graft-inner 不接受内层删除(包比线上少内层键)")
                entry["status"] = "nested-conflict"
                report["tables"].append(entry)
                continue
            payload_keys, payload_rows = read_rows(
                table.payload, codec, f"graft-candidate:{table.logical}")
            payload_map = dict(zip(payload_keys, payload_rows))
            new_rows: dict[str, bytes] = {}
            for key, inner in nested.items():
                if not inner["added"] and not inner["changed"]:
                    continue
                new_rows[key] = graft_inner_added(
                    payload_map[key], live_map[key], inner["compressed"], inner["added"])
                grafted[key] = {
                    "grafted_inner": list(inner["added"]),
                    "ignored_inner_changes": list(inner["changed"]),
                }
                report["notes"].append(
                    f"{table.logical}[{key}]: 内层嫁接 {len(inner['added'])} 个新增键"
                    f" {inner['added'][:6]};包里另有 {len(inner['changed'])} 个内层行与线上不同,"
                    "按快照漂移丢弃,线上内容原样保留")
            if new_rows:
                entry["grafted"] = grafted
                table = replace(table, payload=build_rows(
                    payload_keys,
                    [new_rows.get(k, r) for k, r in zip(payload_keys, payload_rows)],
                    compressed=(codec == "flat")))
                cand_keys, cand_rows = read_rows(
                    table.payload, codec, f"candidate:{table.logical}")
                cand_map = dict(zip(cand_keys, cand_rows))
                nested = {}

        if any(n["dropped"] or n["changed"] for n in nested.values()):
            entry["status"] = "nested-conflict"
            report["tables"].append(entry)
            continue

        merged = merge_rows(table.logical, codec, claimed, table.payload, live)
        verify_merged(table.logical, codec, claimed, table.payload, live, merged)
        entry["status"] = "ready"
        entry["merged_sha256"] = sha256_bytes(merged)
        entry["merged_size"] = len(merged)
        report["tables"].append(entry)
        report["publish_logicals"].append(table.logical)

    # --- 资源(PNG 等,已是 store 形态,整文件落盘) -------------------------
    for resource in pack.resources:
        live_path = env.table_path(resource.logical)
        digest = core.sha1_path(resource.logical)
        exists = live_path.exists()
        same = exists and live_path.read_bytes() == resource.payload
        entry = {
            "logical": resource.logical, "member": resource.member,
            "channel": resource.channel,
            "store_relative": f"{digest[:2]}/{digest[2:]}",
            "sha256": sha256_bytes(resource.payload),
            "size": len(resource.payload),
            "live_exists": exists, "live_same": same,
            "status": "no-op" if same else ("overwrite" if exists else "new"),
        }
        if resource.channel != "common":
            report["blockers"].append(
                f"{resource.logical}: channel={resource.channel},本通道只投 common 层")
        if exists and not same:
            report["blockers"].append(
                f"{resource.logical}: store 里已有不同字节的同名资源,拒绝静默覆盖")
        report["resources"].append(entry)
        if not same:
            report["publish_logicals"].append(resource.logical)

    # --- 服务端 JSON -------------------------------------------------------
    for payload in pack.server:
        path = env.asset_path(payload.asset)
        entry: dict[str, Any] = {
            "asset": payload.asset, "member": payload.member, "kind": payload.kind,
        }
        if not path.exists():
            entry["status"] = "missing"
            report["blockers"].append(f"assets/{payload.asset}: 线上不存在")
            report["server"].append(entry)
            continue
        live_raw = path.read_bytes()
        live = _read_json_bytes(live_raw, f"assets/{payload.asset}")
        style = detect_json_style(live_raw, live)
        entry["style"] = style
        if not style["matched"]:
            report["notes"].append(
                f"assets/{payload.asset}: 认不出原排版,写回会整文件重排"
                "(语义不变,但作者的 diff 会被淹掉)")
        if payload.kind == "delta":
            delta = payload.value
        else:
            delta = diff_json_additions(live, payload.value)
            if delta is None:
                entry["status"] = "no-op"
                entry["delta"] = None
                report["server"].append(entry)
                continue
        ops: list[MergeOp] = []
        merged = deep_merge_json(live, delta, ops=ops)
        entry.update({
            "status": "no-op" if not ops else "ready",
            "live_sha256": sha256_bytes(live_raw),
            "delta": delta,
            "ops": [op.as_dict() for op in ops],
            "merged_sha256": sha256_bytes(dump_json_like(merged, style)),
        })
        report["server"].append(entry)

    return report


def cross_pack_conflicts(reports: Sequence[Mapping[str, Any]]) -> list[str]:
    """同一目标被两个包同时 claim,且内容不一致 —— 必须在落盘前挡住。"""
    problems: list[str] = []
    table_claims: dict[tuple[str, str], tuple[str, str]] = {}
    for report in reports:
        for table in report.get("tables", []):
            for key in table.get("claimed_keys", []):
                token = (table["logical"], key)
                previous = table_claims.get(token)
                if previous is not None and previous[1] != table.get("candidate_sha256"):
                    problems.append(
                        f"{table['logical']}[{key}] 被 {previous[0]} 与 "
                        f"{report['pack_id']} 同时 claim")
                table_claims[token] = (report["pack_id"], table.get("candidate_sha256", ""))
    server_paths: dict[tuple[str, str, str], str] = {}
    for report in reports:
        for entry in report.get("server", []):
            for op in entry.get("ops", []):
                # append 的目标是同一个根数组但元素不同 —— 那是并集,不是冲突,
                # 所以把元素本身也算进身份;add/replace 只按路径判定。
                identity = op.get("detail", "") if op["action"] == "append" else ""
                token = (entry["asset"], "/".join(op["path"]), identity)
                previous = server_paths.get(token)
                if previous is not None and previous != report["pack_id"]:
                    where = token[1] or "<root>"
                    problems.append(
                        f"assets/{entry['asset']}:{where}"
                        f"{'[' + identity + ']' if identity else ''} 被 {previous} 与 "
                        f"{report['pack_id']} 同时写入")
                server_paths[token] = report["pack_id"]
    resource_paths: dict[str, tuple[str, str]] = {}
    for report in reports:
        for entry in report.get("resources", []):
            previous = resource_paths.get(entry["logical"])
            if previous is not None and previous[1] != entry["sha256"]:
                problems.append(
                    f"{entry['logical']} 被 {previous[0]} 与 {report['pack_id']} "
                    "以不同字节投递")
            resource_paths[entry["logical"]] = (report["pack_id"], entry["sha256"])
    return problems


# ---------------------------------------------------------------------------
# 落盘
# ---------------------------------------------------------------------------

def apply_pack(pack: LoadedPack, report: Mapping[str, Any], env: Environment, *,
               dry_run: bool, backup_suffix: str) -> dict[str, Any]:
    """把 plan 里的 claim 合到**当前**线上。dry_run 时全程只在内存里做。"""
    if report.get("blockers"):
        raise ApplyError(
            f"{pack.pack_id}: plan 里还有 {len(report['blockers'])} 条阻断,拒绝落盘")

    table_payloads = {t.logical: t.payload for t in pack.tables}
    resource_payloads = {r.logical: r.payload for r in pack.resources}
    writes: list[tuple[Path, bytes]] = []
    receipt: dict[str, Any] = {
        "pack_id": pack.pack_id, "dry_run": dry_run, "tables": [],
        "resources": [], "server": [],
    }

    for entry in report.get("tables", []):
        if entry.get("status") != "ready":
            continue
        logical = entry["logical"]
        codec = entry["codec"]
        claimed = list(entry["claimed_keys"])
        candidate = table_payloads[logical]
        path = env.table_path(logical)
        live = path.read_bytes()
        live_keys, live_rows = read_rows(live, codec, f"live:{logical}")
        live_map = dict(zip(live_keys, live_rows))
        for key, expected in (entry.get("claimed_baseline") or {}).items():
            actual = sha256_bytes(live_map[key]) if key in live_map else None
            if actual != expected:
                raise ApplyError(
                    f"{logical}[{key}]: plan 之后线上这一行变了 "
                    f"(plan 记录 {expected}, 现在 {actual}) —— 重跑 plan")
        # 线上在 plan 之后新增的键**不**是问题:行级合并原样保留它们,而
        # verify_merged 会逐行证明这一点。陈旧快照那道闸在 plan 阶段对着干净基线
        # 已经走过了,这里再判一次只会把「同轮先落地的另一个包」误伤成陈旧。
        if sha256_bytes(live) != entry.get("live_sha256"):
            receipt.setdefault("live_moved", []).append(logical)
        merged = merge_rows(logical, codec, claimed, candidate, live)
        verify_merged(logical, codec, claimed, candidate, live, merged)
        writes.append((path, merged))
        receipt["tables"].append({
            "logical": logical, "claimed": len(claimed),
            "before_sha256": sha256_bytes(live), "after_sha256": sha256_bytes(merged),
        })

    for entry in report.get("resources", []):
        if entry.get("status") == "no-op":
            continue
        logical = entry["logical"]
        path = env.table_path(logical)
        writes.append((path, resource_payloads[logical]))
        receipt["resources"].append({"logical": logical, "sha256": entry["sha256"]})

    for entry in report.get("server", []):
        if entry.get("status") != "ready":
            continue
        path = env.asset_path(entry["asset"])
        live_raw = path.read_bytes()
        live = _read_json_bytes(live_raw, f"assets/{entry['asset']}")
        ops: list[MergeOp] = []
        merged = deep_merge_json(live, entry["delta"], ops=ops)
        # 排版按**当前**这份文件重新认一次:plan 与 apply 之间可能有别的包写过它。
        payload = dump_json_like(merged, detect_json_style(live_raw, live))
        writes.append((path, payload))
        receipt["server"].append({
            "asset": entry["asset"], "ops": len(ops),
            "before_sha256": sha256_bytes(live_raw),
            "after_sha256": sha256_bytes(payload),
        })

    receipt["write_count"] = len(writes)
    if dry_run:
        receipt["writes"] = [str(p) for p, _ in writes]
        return receipt

    backups: list[tuple[Path, Path]] = []
    written: list[Path] = []
    try:
        for path, payload in writes:
            if path.exists():
                backup = path.with_name(path.name + backup_suffix)
                if backup.exists():
                    raise ApplyError(f"备份文件已存在,拒绝覆盖: {backup}")
                backup.write_bytes(path.read_bytes())
                backups.append((backup, path))
            atomic_write(path, payload)
            written.append(path)
    except BaseException:
        for backup, path in reversed(backups):
            try:
                path.write_bytes(backup.read_bytes())
            except OSError:
                pass
        for path in written:
            if not any(path == target for _, target in backups):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
        raise
    receipt["backups"] = [str(b) for b, _ in backups]
    receipt["writes"] = [str(p) for p in written]
    return receipt


# ---------------------------------------------------------------------------
# 铸边:永远显式 --tables
# ---------------------------------------------------------------------------

def pending_fingerprint(path: Path = PENDING_PATH) -> str | None:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError:
        return None


def run_publish(logicals: Sequence[str], *, extra: Sequence[str] = (),
                dry_run: bool = False) -> int:
    """调 wf_publish.py。**从不**裸跑 —— 裸跑会清空作者的 sync_pending.json。"""
    if not logicals:
        raise ApplyError("没有要发布的逻辑路径")
    command = [
        sys.executable, "-X", "utf8", str(TOOLS / "wf_publish.py"),
        "--tables", ",".join(logicals), *extra,
    ]
    before = pending_fingerprint()
    print("发布命令   : " + " ".join(command[:5]) + f" <{len(logicals)} 条逻辑路径>")
    if dry_run:
        print("(--dry-run:未执行)")
        return 0
    result = subprocess.run(command, cwd=str(ROOT))
    after = pending_fingerprint()
    if before != after:
        raise ApplyError(
            f"sync_pending.json 在发布前后变了 ({before} -> {after}) —— 立刻人工核对")
    print(f"pending 指纹: {after} (未变)")
    return result.returncode


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_report(report: Mapping[str, Any]) -> None:
    print("=" * 78)
    print(f"包 {report['pack_id']}  ({report['adapter']})")
    print(f"  zip sha256 : {report['zip_sha256']}")
    if report["gate_flags"]:
        print(f"  包声明闸门 : {json.dumps(report['gate_flags'], ensure_ascii=False)}")
    if report.get("declared_seal"):
        print(f"  包声明 seal: {report['declared_seal']} (未重算,完整性由 "
              "SHA256SUMS + manifest.members 双向核对保证)")
    if report["gate_overrides"]:
        print(f"  已翻开     : {report['gate_overrides']}  (--author-approved)")
    for entry in report.get("declared_baselines", []):
        mark = "SAME " if entry["same"] else "DRIFT"
        print(f"  基线 {mark} {entry['target']}")
    for table in report.get("tables", []):
        status = table.get("status", "?")
        if status == "live-missing":
            print(f"  表 [{status}] {table['logical']}")
            continue
        print(f"  表 [{status}] {table['logical']}  codec={table.get('codec')} "
              f"live={table.get('live_rows')} 包={table.get('candidate_rows')} "
              f"+{len(table.get('added', []))} ~{len(table.get('changed', []))} "
              f"-{len(table.get('dropped', []))}")
        if table.get("claimed_keys"):
            keys = table["claimed_keys"]
            print(f"      claim: {keys[:8]}{'...' if len(keys) > 8 else ''}")
    for entry in report.get("resources", []):
        print(f"  资源 [{entry['status']}] {entry['logical']} -> "
              f"{entry['store_relative']} ({entry['size']} B)")
    for entry in report.get("server", []):
        print(f"  服务端 [{entry.get('status')}] assets/{entry['asset']} "
              f"({entry['kind']}, {len(entry.get('ops', []))} 处写入)")
        for op in entry.get("ops", [])[:6]:
            print(f"      {op['action']:8s} {'/'.join(op['path']) or '<root>'}")
        if len(entry.get("ops", [])) > 6:
            print(f"      ... 共 {len(entry['ops'])} 处")
    for note in report.get("notes", []):
        print(f"  [记录] {note}")
    for blocker in report.get("blockers", []):
        print(f"  [阻断] {blocker}")
    logicals = report.get("publish_logicals", [])
    print(f"  发布清单   : {len(logicals)} 条逻辑路径")


def cmd_plan(args: argparse.Namespace) -> int:
    env = Environment.resolve(args.store, args.assets)
    reports = []
    packs = []
    for zip_path in args.pack:
        pack = load_pack(Path(zip_path))
        packs.append(pack)
        reports.append(plan_pack(
            pack, env, author_approved=args.author_approved,
            tolerate_live_keys=args.tolerate_live_key,
            graft_inner=args.graft_inner))
    conflicts = cross_pack_conflicts(reports)
    for report in reports:
        _print_report(report)
    print("=" * 78)
    if conflicts:
        print("跨包冲突:")
        for problem in conflicts:
            print(f"  !! {problem}")
    else:
        print("跨包冲突   : 无(键空间不相交)")
    if server_running():
        print("服务端     : 8001 在监听 —— apply / publish 前必须先停")
    else:
        print("服务端     : 未监听")
    print(f"pending 指纹: {pending_fingerprint()} (只读)")

    plan = {
        "schema": PLAN_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "store": str(env.store),
        "assets": str(env.assets),
        "pending_sha256": pending_fingerprint(),
        "cross_pack_conflicts": conflicts,
        "packs": reports,
    }
    blocked = [r["pack_id"] for r in reports if r["blockers"]]
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"计划已写入 : {out}")
    if args.dry_run_apply:
        for pack, report in zip(packs, reports):
            if report["blockers"]:
                print(f"[跳过 dry-run apply] {pack.pack_id}: 有阻断")
                continue
            receipt = apply_pack(pack, report, env, dry_run=True, backup_suffix="")
            print(f"[dry-run apply] {pack.pack_id}: {receipt['write_count']} 个写入点全部验证通过")
    if conflicts or blocked:
        print(f"[BLOCKED] 冲突 {len(conflicts)} 条;被阻断的包 {blocked}")
        return 2
    return 0


def _load_plan(path: Path, pack_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    if plan.get("schema") != PLAN_SCHEMA:
        raise ApplyError(f"计划 schema 不符: {plan.get('schema')!r}")
    for report in plan.get("packs", []):
        if report.get("pack_id") == pack_id:
            return plan, report
    raise ApplyError(f"计划里没有包 {pack_id}")


def cmd_apply(args: argparse.Namespace) -> int:
    plan, report = _load_plan(Path(args.plan), args.pack_id)
    env = Environment.resolve(args.store or plan.get("store"), args.assets or plan.get("assets"))
    pack = load_pack(Path(report["zip"]), pack_id=args.pack_id)
    if pack.zip_sha256 != report["zip_sha256"]:
        raise ApplyError("包的 sha256 与计划不符,重跑 plan")
    if plan.get("cross_pack_conflicts"):
        raise ApplyError("计划里有跨包冲突,拒绝落盘")
    # 翻开包自己的闸门要在 plan 与 apply 两处各说一次:plan 那次是「看看会发生
    # 什么」,这次是「真写盘」。默认拒绝,免得别人拿着别人产的 plan 直接落盘。
    if report.get("gate_overrides") and not args.author_approved:
        raise ApplyError(
            f"{args.pack_id}: 计划里翻开了包声明的闸门 {report['gate_overrides']};"
            "落盘要再加一次 --author-approved")
    if not args.dry_run and server_running():
        raise ApplyError("服务端还在监听,先停 8001 再落盘")
    before = pending_fingerprint()
    suffix = args.backup_suffix or time.strftime(f".bak-offlineapply-{args.pack_id}-%Y%m%d-%H%M%S")
    receipt = apply_pack(pack, report, env, dry_run=args.dry_run, backup_suffix=suffix)
    after = pending_fingerprint()
    if before != after:
        raise ApplyError(f"sync_pending.json 变了 ({before} -> {after})")
    receipt["pending_sha256"] = after
    receipt["publish_logicals"] = report["publish_logicals"]
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if args.receipt:
        Path(args.receipt).parent.mkdir(parents=True, exist_ok=True)
        Path(args.receipt).write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    plan, report = _load_plan(Path(args.plan), args.pack_id)
    if report.get("blockers"):
        raise ApplyError(
            f"{args.pack_id}: plan 里还有 {len(report['blockers'])} 条阻断,拒绝铸边")
    env = Environment.resolve(args.store or plan.get("store"), args.assets or plan.get("assets"))
    logicals = report["publish_logicals"]
    # 「apply 跑过没有」的判据:claim 过的行必须已经在线上。没跑就铸边 = 发一条
    # 只含线上原样字节的空边,链号白涨一格,而且下一条边的 from 会对不上预期。
    missing: list[str] = []
    for table in report.get("tables", []):
        if table.get("status") != "ready":
            continue
        live_path = env.table_path(table["logical"])
        if not live_path.exists():
            missing.append(table["logical"])
            continue
        live_keys, _ = read_rows(
            live_path.read_bytes(), table["codec"], f"live:{table['logical']}")
        absent = [k for k in table["claimed_keys"] if k not in set(live_keys)]
        if absent:
            missing.append(f"{table['logical']}{absent[:4]}")
    for resource in report.get("resources", []):
        if resource.get("status") == "no-op":
            continue
        if not (env.store / resource["store_relative"]).is_file():
            missing.append(resource["logical"])
    if missing:
        raise ApplyError(
            f"{args.pack_id}: 这些 claim 还不在线上 {missing[:6]} —— 先跑 apply 再铸边")
    if not args.dry_run and server_running():
        raise ApplyError("服务端还在监听,先停 8001 再铸边")
    return run_publish(logicals, extra=args.publish_arg or (), dry_run=args.dry_run)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="离线整包投递器(武器/模式)")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="只读演练:校验 + 漂移 + 冲突 + 内存合并")
    plan.add_argument("--pack", action="append", required=True, help="离线包 zip(可多次)")
    plan.add_argument("--out", help="把计划写到这个 JSON")
    plan.add_argument("--store", help="覆盖 store 根")
    plan.add_argument("--assets", help="覆盖服务端 assets 目录")
    plan.add_argument("--author-approved", action="store_true",
                      help="作者已授权翻开包自己声明的 review/publishing 闸门")
    plan.add_argument("--dry-run-apply", action="store_true",
                      help="额外把落盘流程在内存里整个跑一遍")
    plan.add_argument("--tolerate-live-key", action="append", default=[],
                      help="允许包里缺这个线上已有的键(同轮另一个包刚落地的行);可多次")
    plan.add_argument("--graft-inner", action="append", default=[], metavar="LOGICAL",
                      help="这张表的嵌套行做内层行级合并:只嫁接包里新增的内层键,"
                           "线上原有内层行一字不动,包里改动过的内层行按快照漂移丢弃;可多次")
    plan.set_defaults(func=cmd_plan)

    apply_cmd = sub.add_parser("apply", help="按计划落盘(备份 + 原子写)")
    apply_cmd.add_argument("--plan", required=True)
    apply_cmd.add_argument("--pack-id", required=True)
    apply_cmd.add_argument("--store")
    apply_cmd.add_argument("--assets")
    apply_cmd.add_argument("--author-approved", action="store_true")
    apply_cmd.add_argument("--backup-suffix")
    apply_cmd.add_argument("--receipt")
    apply_cmd.add_argument("--dry-run", action="store_true")
    apply_cmd.set_defaults(func=cmd_apply)

    publish = sub.add_parser("publish", help="调 wf_publish.py 铸边(永远带 --tables)")
    publish.add_argument("--plan", required=True)
    publish.add_argument("--pack-id", required=True)
    publish.add_argument("--store")
    publish.add_argument("--assets")
    publish.add_argument("--publish-arg", action="append",
                         help="透传给 wf_publish.py 的额外参数")
    publish.add_argument("--dry-run", action="store_true")
    publish.set_defaults(func=cmd_publish)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ApplyError as exc:
        print(f"[ERR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
