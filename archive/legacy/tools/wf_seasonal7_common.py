# -*- coding: utf-8 -*-
"""季节换装七角色：规格驱动角色包的共用原语。

写入边界：只写 ``<workspace>/package/roots/**`` 与 ``<workspace>/evidence/**``；
live store、``assets/``、``.cdn/`` 只读。表写入一律「包内已有副本优先，否则 live」，
所以 tables / kit 多次写同一张表时键会累积；认领按 (root, logical_path) 合并并持久化到
``evidence/table_claims.json``（重复运行幂等）。
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import re
import sys
import zlib
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_assets  # noqa: E402
import wf_dsl  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_specs as specs_mod  # noqa: E402
from wf_seasonal7_specs import SeasonalSpec  # noqa: E402

ROOT = Path(os.environ.get("WF_S7_ROOT") or core.project_root())
ROOT_NAMES = ("common", "medium", "android", "server")
CLIENT_ROOTS = ("common", "medium", "android")
STORE_ROOT_MAP = {"upload": "common", "medium": "medium", "android": "android",
                  "medium_upload": "medium", "android_upload": "android", "common": "common"}
SUPPORTED_CODECS = ("flat", "raw_outer", "action_nested", "switched_nested", "json_object")
NESTED_CODECS = {core.ACTION_SKILL_LOGICAL: "action_nested",
                 core.SWITCHED_ACTION_SKILL_LOGICAL: "switched_nested"}
DSL_SUFFIX = ".action.dsl.amf3.deflate"
CLAIMS_FILE = "table_claims.json"
OWNED_FILE = "owned_outputs.json"
SOURCES_FILE = "template_sources.json"


class S7Error(RuntimeError):
    pass


# ---------------------------------------------------------------- 纯函数工具

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def csv_join(rows: list[list[str]]) -> str:
    return core.write_csv_lines(rows).rstrip("\n")


def csv_split(text: str) -> list[list[str]]:
    return core.read_csv_lines(text)


def as_text(value: str | list) -> str:
    if isinstance(value, str):
        return value
    if value and isinstance(value[0], str):
        return csv_join([list(value)])
    return csv_join([list(r) for r in value])


def png_open(raw: bytes):
    from PIL import Image
    return Image.open(io.BytesIO(wf_assets.png_decode(raw))).convert("RGBA")


def png_store_bytes(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return wf_assets.png_encode(buf.getvalue())


def amf_parse(raw: bytes):
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


def amf_bytes(tree) -> bytes:
    """单一 compressobj（两个对象会造坏流）；只接受裸树，写后回读自检。"""
    if isinstance(tree, dict) and set(tree) >= {"tree"} and "numbers" in tree:
        raise S7Error("amf_bytes got a {tree,numbers} wrapper; pass the bare tree")
    raw = zlib.compress(wf_dsl.encode_amf3(tree), 9)[2:-4]
    if amf_parse(raw) != tree:
        raise S7Error("AMF3 roundtrip differs")
    return raw


def walk(node):
    yield node
    if isinstance(node, list):
        for child in node:
            yield from walk(child)
    elif isinstance(node, dict):
        for child in node.values():
            yield from walk(child)


def commands(tree, name: str) -> list[list]:
    return [n for n in walk(tree) if isinstance(n, list) and n and n[0] == name]


def replace_strings(node, substitutions: Mapping[str, str]):
    """递归替换字符串（含 dict 键）；数值/布尔原样保留，输入不变。"""
    if isinstance(node, str):
        for old, new in substitutions.items():
            node = node.replace(old, new)
        return node
    if isinstance(node, list):
        return [replace_strings(item, substitutions) for item in node]
    if isinstance(node, dict):
        return {replace_strings(k, substitutions): replace_strings(v, substitutions)
                for k, v in node.items()}
    return node


def dir_prefix_map(old_code: str, new_code: str) -> dict[str, str]:
    """``character/<old>/`` → ``character/<new>/``：带尾斜杠，前缀型 code 也不会误伤。"""
    return {f"character/{old_code}/": f"character/{new_code}/"}


def merge_claims(existing: list[dict], additions: Iterable[dict]) -> list[dict]:
    """按 (root, logical_path) 合并认领：outer/inner/semantic 取并集，codec 冲突报错。

    输出顺序 = 首次出现顺序；outer_keys 排序；inner_keys 按 outer_key 排序、keys 保持首见顺序。
    纯函数，重复合并同一批认领结果不变（幂等）。
    """
    order: list[tuple[str, str]] = []
    table: dict[tuple[str, str], dict] = {}
    for claim in [*existing, *additions]:
        root, logical = claim["root"], claim["logical_path"]
        codec = claim["codec_id"]
        if root not in ROOT_NAMES:
            raise S7Error(f"claim root invalid: {root}")
        if codec not in SUPPORTED_CODECS:
            raise S7Error(f"claim codec invalid: {codec}")
        key = (root, logical)
        if key not in table:
            order.append(key)
            table[key] = {"codec_id": codec, "outer": set(), "inner": {}, "semantic": []}
        entry = table[key]
        if entry["codec_id"] != codec:
            raise S7Error(f"claim codec conflict {root}:{logical}: {entry['codec_id']} vs {codec}")
        entry["outer"].update(str(k) for k in claim.get("outer_keys", []))
        for item in claim.get("inner_keys", []):
            keys = entry["inner"].setdefault(item["outer_key"], [])
            for k in item["keys"]:
                if k not in keys:
                    keys.append(k)
            entry["outer"].add(item["outer_key"])
        for sem in claim.get("semantic_claims", []):
            if sem not in entry["semantic"]:
                entry["semantic"].append(sem)
    result = []
    for root, logical in order:
        entry = table[(root, logical)]
        result.append({
            "codec_id": entry["codec_id"],
            "inner_keys": [{"keys": list(entry["inner"][o]), "outer_key": o}
                           for o in sorted(entry["inner"])],
            "logical_path": logical,
            "outer_keys": sorted(entry["outer"]),
            "root": root,
            "semantic_claims": list(entry["semantic"]),
        })
    return result


# ---------------------------------------------------------------- 元素翻转

# instant content 元素参数（c73）为 1 基的 kind：720 OverrideCharacterElement（写 5=光）。
ONE_BASED_ELEMENT_INSTANT_KINDS = frozenset({"720"})


def _flip_group_cell(value: str, old: str, new: str) -> str:
    parts = value.split(",")
    if old not in parts:
        return value
    return ",".join(new if p == old else p for p in parts)


def flip_ability_row(row: list[str], table: str, old_el: int, new_el: int,
                     label: str = "") -> tuple[list[str], list[dict]]:
    """词条/队长行元素翻转（参照 wf_gui.element_convert）：

    - character_groups 类元素 token（逗号分列，只换旧元素 token）；
    - ability c2 雕像组 ``<prefix>_<oldcolor>``；
    - content 块 element 数值列（instant_content+26 / during_content+10）等于旧元素时。
      例外：instant kind 720 OverrideCharacterElement 的 c73 是 **1 基**元素（记忆卡
      wf-character-groups-semantics），按 old+1 → new+1 比较/改写。
    判他方元素的枚举 kind 不动。
    """
    import wf_describe
    if old_el == new_el:
        return list(row), []
    old_tok, new_tok = specs_mod.ELEMENT_TOKENS[old_el], specs_mod.ELEMENT_TOKENS[new_el]
    old_color, new_color = specs_mod.ELEMENT_COLORS[old_el], specs_mod.ELEMENT_COLORS[new_el]
    blocks = wf_describe.layout(table)["blocks"]
    instant_kind_col = blocks["instant_content"]
    instant_el_col = blocks["instant_content"] + 26
    el_cols = {instant_el_col, blocks["during_content"] + 10}
    instant_kind = row[instant_kind_col] if len(row) > instant_kind_col else ""
    out, changes = list(row), []
    for ci, value in enumerate(out):
        after = value
        if value:
            after = _flip_group_cell(value, old_tok, new_tok)
            if table == "ability" and ci == 2 and value.endswith("_" + old_color):
                after = value[: -len(old_color)] + new_color
            if ci == instant_el_col and instant_kind in ONE_BASED_ELEMENT_INSTANT_KINDS:
                if value == str(old_el + 1):
                    after = str(new_el + 1)
            elif ci in el_cols and value == str(old_el):
                after = str(new_el)
        if after != value:
            changes.append({"cell": label, "col": ci, "before": value, "after": after})
            out[ci] = after
    return out, changes


def flip_dsl_elements(tree, old_el: int, new_el: int) -> tuple[Any, list[dict]]:
    """DSL 显式元素 = 内部+1：CreateNormalAttack[2] 与 FindAllSubjects(33)[3] 旧元素 → 新元素。"""
    if old_el == new_el:
        return tree, []
    tree = copy.deepcopy(tree)
    old_code, new_code = old_el + 1, new_el + 1
    changes: list[dict] = []
    for node in walk(tree):
        if not (isinstance(node, list) and node and isinstance(node[0], str)):
            continue
        if node[0] == "CreateNormalAttack" and len(node) > 2 and node[2] == old_code:
            node[2] = new_code
            changes.append({"node": "CreateNormalAttack[2]", "before": old_code, "after": new_code})
        elif (node[0] == "FindAllSubjects" and len(node) > 3 and node[2] == 33
              and isinstance(node[3], list) and old_code in node[3]):
            before = list(node[3])
            node[3] = [new_code if v == old_code else v for v in node[3]]
            changes.append({"node": "FindAllSubjects(33)[3]", "before": before, "after": node[3]})
        elif node[0] == "ACToleranceOfElement" and len(node) > 2 and node[2] == old_code:
            changes.append({"node": "ACToleranceOfElement[2]", "before": old_code,
                            "after": old_code, "note": "他方/抗性元素，未翻转"})
    return tree, changes


def replace_element_words(text: str, old_el: int, new_el: int) -> str:
    if old_el == new_el or not text:
        return text
    old, new = specs_mod.ELEMENT_WORDS[old_el], specs_mod.ELEMENT_WORDS[new_el]
    return text.replace(f"{old}属性", f"{new}属性")


# ---------------------------------------------------------------- 角色包上下文

class S7Pack:
    """绑定单个 spec 的包读写上下文。所有路径可注入（测试用临时目录）。"""

    def __init__(self, spec: SeasonalSpec, *, root: Path | None = None,
                 store: Path | None = None, workspace: Path | None = None,
                 server_base: Path | None = None, baseline=None,
                 use_official: bool = True) -> None:
        self.spec = spec
        self.root = Path(root) if root is not None else ROOT
        if store is None:
            profile = core.resolve_profile()
            if profile is None:
                raise S7Error("cannot resolve live store profile")
            store = profile.store
        self.store = Path(store)
        self.workspace = Path(workspace) if workspace is not None else self.root / spec.workspace
        self.package = self.workspace / "package"
        self.evidence = self.workspace / "evidence"
        self.server_base = Path(server_base) if server_base is not None else self.root / "assets"
        self._baseline = baseline
        self.use_official = use_official
        self._sources: dict[str, dict] | None = None

    # ---------------- 基础路径 / 安全写
    @property
    def batch_dir(self) -> Path:
        return self.root / specs_mod.BATCH_DIR

    def check_identity(self) -> None:
        marker = self.workspace / "workspace.json"
        if not marker.is_file():
            raise S7Error(f"workspace not initialised: {self.workspace}")
        payload = json.loads(marker.read_text(encoding="utf-8"))
        want = (self.spec.pkg_id, self.spec.template_id, self.spec.cid, self.spec.code)
        got = (payload.get("package_id"), payload.get("template_character_id"),
               payload.get("character_id"), payload.get("code_name"))
        if want != got:
            raise S7Error(f"workspace identity {got} != spec {want}")

    def pkg_path(self, root: str, logical: str) -> Path:
        if root not in ROOT_NAMES:
            raise S7Error(f"unsupported package root {root}")
        norm = logical.replace("\\", "/")
        if ":" in norm or norm.startswith("/") or any(p in ("", ".", "..") for p in norm.split("/")):
            raise S7Error(f"logical path is not a safe relative asset path: {logical}")
        base = (self.package / "roots" / root).resolve()
        path = (self.package / "roots" / root / Path(*norm.split("/"))).resolve()
        if not path.is_relative_to(base):
            raise S7Error(f"package path escapes root: {logical}")
        return path

    def write_pkg(self, root: str, logical: str, data: bytes) -> Path:
        self.check_identity()
        path = self.pkg_path(root, logical)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file() and path.read_bytes() == data:
            return path          # 字节相同不改 mtime（hash-cache 友好）
        path.write_bytes(data)
        if path.read_bytes() != data:
            raise OSError(f"package write readback failed: {root}:{logical}")
        return path

    def pkg_has(self, root: str, logical: str) -> bool:
        return self.pkg_path(root, logical).is_file()

    def evidence_path(self, name: str) -> Path:
        path = (self.evidence / name).resolve()
        if not path.is_relative_to(self.evidence.resolve()):
            raise S7Error(f"evidence path escapes: {name}")
        return path

    def write_evidence(self, name: str, value: Any) -> Path:
        path = self.evidence_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json_dump(value)
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
        return path

    def read_evidence(self, name: str, default: Any = None) -> Any:
        path = self.evidence_path(name)
        if not path.is_file():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    # ---------------- live / 官方基线读取
    def live_path(self, logical: str) -> Path | None:
        loc = wf_assets.locate(self.store, logical)
        return None if loc is None else loc[1]

    def live_locate(self, logical: str) -> tuple[str, Path] | None:
        loc = wf_assets.locate(self.store, logical)
        return None if loc is None else (STORE_ROOT_MAP.get(loc[0], loc[0]), loc[1])

    def live_read(self, logical: str) -> bytes:
        path = self.live_path(logical)
        if path is None:
            raise FileNotFoundError(f"live store lacks {logical}")
        return path.read_bytes()

    def live_table_bytes(self, logical: str) -> bytes:
        path = core.table_path(self.store, logical)
        if not path.is_file():
            raise FileNotFoundError(f"live store lacks table {logical}")
        return path.read_bytes()

    @property
    def baseline(self):
        if self._baseline is None and self.use_official:
            from wf_enhancement_policy import OfficialBaseline
            self._baseline = OfficialBaseline(self.root / ".cdn/cn",
                                              cache_dir=self.root / "mod-tools/work/official-baseline",
                                              write_cache=False)
        return self._baseline

    def official_read(self, logical: str, root: str | None = None) -> bytes | None:
        """从官方 CDN 归档（OfficialBaseline, 官方链尾 1.4.54）读原始字节；不存在返回 None。

        ``root=None`` 时在 common/medium/android 中找唯一根。被自制增强改过的母本（如 131020
        的词条/队长/DSL）必须用它取官方原值。
        """
        if not self.use_official or self.baseline is None:
            return None
        digest = core.sha1_path(logical)
        rel = digest[:2] + "/" + digest[2:]
        try:
            if root is None:
                found = [r for r in CLIENT_ROOTS if self.baseline.identity(r, rel) is not None]
                if len(found) != 1:
                    return None
                root = found[0]
            return self.baseline.get(root, rel)
        except Exception:                       # 归档不可用时降级为 live（调用方记录来源）
            return None

    def official_identity(self, logical: str) -> tuple[str, int, int] | None:
        if not self.use_official or self.baseline is None:
            return None
        digest = core.sha1_path(logical)
        rel = digest[:2] + "/" + digest[2:]
        try:
            for r in CLIENT_ROOTS:
                ident = self.baseline.identity(r, rel)
                if ident is not None:
                    return (r, ident[0], ident[1])
        except Exception:
            return None
        return None

    def _record_source(self, logical: str, source: str, raw: bytes, note: str = "") -> None:
        if self._sources is None:
            self._sources = self.read_evidence(SOURCES_FILE, {}) or {}
        entry = {"source": source, "sha256": sha256(raw), "size": len(raw)}
        if note:
            entry["note"] = note
        if self._sources.get(logical) != entry:
            self._sources[logical] = entry
            self.write_evidence(SOURCES_FILE, dict(sorted(self._sources.items())))

    def template_table_bytes(self, logical: str) -> bytes:
        """母本行取数：官方基线优先，缺失时 live。表 splice 的底仍然是 live/包副本。"""
        raw = self.official_read(logical, "common")
        if raw is not None:
            self._record_source(logical, "official", raw)
            return raw
        raw = self.live_table_bytes(logical)
        self._record_source(logical, "live", raw, "official baseline missing")
        return raw

    def template_asset(self, logical: str) -> tuple[str, bytes, str]:
        """母本资产：live 与官方 (crc,size) 一致用 live；不一致且官方存在用官方（自制改过）。"""
        loc = self.live_locate(logical)
        ident = self.official_identity(logical)
        if loc is None and ident is None:
            raise FileNotFoundError(f"template asset absent in live and official: {logical}")
        if loc is not None:
            raw = loc[1].read_bytes()
            if ident is None or (zlib.crc32(raw) & 0xFFFFFFFF, len(raw)) == (ident[1], ident[2]):
                return loc[0], raw, "live" if ident is None else "live=official"
        raw = self.official_read(logical, ident[0])
        if raw is None:
            raise FileNotFoundError(f"official asset unreadable: {logical}")
        return ident[0], raw, "official(live differs)" if loc is not None else "official(live missing)"

    def template_flat(self, logical: str) -> dict[str, str]:
        return core.read_orderedmap_file_from_bytes(self.template_table_bytes(logical))

    def template_raw(self, logical: str) -> dict[str, bytes]:
        om = core.read_orderedmap_raw_rows_from_bytes(self.template_table_bytes(logical), logical)
        return dict(zip(om.keys, om.rows))

    def template_dsl(self, program_or_logical: str) -> Any:
        logical = program_or_logical if program_or_logical.endswith(DSL_SUFFIX) \
            else wf_dsl.dsl_logical(program_or_logical)
        raw = self.official_read(logical, "common")
        source = "official"
        if raw is None:
            raw = self.live_read(logical)
            source = "live"
        self._record_source(logical, source, raw)
        return amf_parse(raw)

    def live_flat(self, logical: str) -> dict[str, str]:
        return core.read_orderedmap_file_from_bytes(self.live_table_bytes(logical))

    # ---------------- 认领
    def load_claims(self) -> list[dict]:
        return list(self.read_evidence(CLAIMS_FILE, []) or [])

    def claim(self, logical: str, keys: Iterable[str], codec: str = "flat",
              root: str = "common", inner: list[dict] | None = None, *,
              replace_inner: bool = False) -> list[dict]:
        """并入认领。``replace_inner=True``：``inner`` 里出现的 outer_key 的内层认领整体替换
        （而非并集），与 ``write_nested(replace_inner=True)`` 删掉的内层键同步。"""
        existing = self.load_claims()
        if replace_inner and inner:
            replaced = {item["outer_key"] for item in inner}
            existing = [dict(c, inner_keys=[i for i in c.get("inner_keys", [])
                                            if i["outer_key"] not in replaced])
                        if (c["root"], c["logical_path"]) == (root, logical) else c
                        for c in existing]
        merged = merge_claims(existing, [{
            "codec_id": codec, "inner_keys": inner or [], "logical_path": logical,
            "outer_keys": sorted(str(k) for k in keys), "root": root, "semantic_claims": []}])
        self.write_evidence(CLAIMS_FILE, merged)
        return merged

    def unclaim(self, logical: str, keys: Iterable[str] = (), *, root: str = "common",
                inner_outer_key: str | None = None, inner_keys: Iterable[str] = ()) -> dict[str, Any]:
        """撤销认领，并把包内对应行还原成底表（live / server base）。

        底表有该键 = 恢复底表原行；没有 = 删行。认领清空后，若包内表与底表逐行相同则删除包内表文件。

        - flat / raw_outer / json_object：``keys`` 为外层键；
        - action_nested / switched_nested：``inner_outer_key`` + ``inner_keys`` 删内层键；
          只给 ``keys`` 则整条外层键撤销。
        """
        self.check_identity()
        keys = [str(k) for k in keys]
        inner_keys = [str(k) for k in inner_keys]
        claims = self.load_claims()
        entry = next((c for c in claims if (c["root"], c["logical_path"]) == (root, logical)), None)
        if entry is None:
            raise S7Error(f"no claim for {root}:{logical}")
        codec = entry["codec_id"]
        path = self.pkg_path(root, logical)
        if not path.is_file():
            raise S7Error(f"claimed table missing in package: {root}:{logical}")
        removed: dict[str, Any] = {"root": root, "logical_path": logical, "outer": [], "inner": []}
        if root == "server":
            import wf_character_pack as pack_mod
            server = self.server_base / Path(*logical.split("/"))
            base_raw = server.read_bytes() if server.is_file() else b"{}"
            base = json.loads(base_raw)
            data = json.loads(path.read_bytes())
            for key in keys:
                if key in base:
                    data[key] = base[key]
                else:
                    data.pop(key, None)
                removed["outer"].append(key)
            extra = {k: v for k, v in data.items() if base.get(k, object()) != v}
            dropped = [k for k in base if k not in data]
            if dropped:
                raise S7Error(f"package server table lacks base keys {dropped[:5]}: {logical}")
            path.write_bytes(pack_mod.merge_server_json_object(base_raw, extra) if extra else base_raw)
            new_entry = dict(entry, outer_keys=[k for k in entry["outer_keys"] if k not in keys])
        else:
            table = core.table_path(self.store, logical)
            base_raw = table.read_bytes() if table.is_file() else None
            if codec in ("action_nested", "switched_nested") and inner_outer_key is not None:
                nested = core.load_nested_table_bytes(path.read_bytes(), logical)
                live_nested = core.load_nested_table_bytes(base_raw, logical) if base_raw else None
                if inner_outer_key not in nested.rows:
                    raise S7Error(f"outer key {inner_outer_key} absent from package {logical}")
                current = nested.rows[inner_outer_key].text_rows()
                live_inner = (live_nested.rows[inner_outer_key].text_rows()
                              if live_nested is not None and inner_outer_key in live_nested.rows else {})
                for key in inner_keys:
                    if key in live_inner:
                        current[key] = live_inner[key]
                    else:
                        current.pop(key, None)
                    removed["inner"].append(key)
                new_entry = dict(entry, inner_keys=[])
                for item in entry.get("inner_keys", []):
                    kept = [k for k in item["keys"]
                            if not (item["outer_key"] == inner_outer_key and k in inner_keys)]
                    if kept:
                        new_entry["inner_keys"].append({"keys": kept, "outer_key": item["outer_key"]})
                if not current and not live_inner:
                    del nested.rows[inner_outer_key]
                    new_entry["outer_keys"] = [k for k in entry["outer_keys"] if k != inner_outer_key]
                    removed["outer"].append(inner_outer_key)
                else:
                    nested.rows[inner_outer_key] = core.OrderedMap(
                        f"{logical}#{inner_outer_key}", list(current),
                        [v.encode("utf-8") for v in current.values()], Path("<memory>"))
                path.write_bytes(core.build_nested_table(nested, logical))
            else:
                om = core.read_orderedmap_raw_rows_from_bytes(path.read_bytes(), logical)
                live: dict[str, bytes] = {}
                if base_raw is not None:
                    lom = core.read_orderedmap_raw_rows_from_bytes(base_raw, logical)
                    live = dict(zip(lom.keys, lom.rows))
                rows = dict(zip(om.keys, om.rows))
                for key in keys:
                    if key in live:
                        rows[key] = live[key]
                    else:
                        rows.pop(key, None)
                    removed["outer"].append(key)
                out_keys = [k for k in om.keys if k in rows]
                path.write_bytes(core.build_orderedmap_raw_rows(
                    core.OrderedMap(logical, out_keys, [rows[k] for k in out_keys], Path(logical))))
                new_entry = dict(entry, outer_keys=[k for k in entry["outer_keys"] if k not in keys],
                                 inner_keys=[i for i in entry.get("inner_keys", [])
                                             if i["outer_key"] not in keys])
        remaining = list(claims)
        index = remaining.index(entry)
        if new_entry["outer_keys"] or new_entry.get("inner_keys"):
            remaining[index] = new_entry
        else:
            del remaining[index]
            removed["table_claim_dropped"] = True
            if self._rows_equal_base(root, logical):
                path.unlink()
                removed["package_table_deleted"] = True
        self.write_evidence(CLAIMS_FILE, merge_claims([], remaining))
        return removed

    def _rows_equal_base(self, root: str, logical: str) -> bool:
        path = self.pkg_path(root, logical)
        if root == "server":
            server = self.server_base / Path(*logical.split("/"))
            return server.is_file() and json.loads(path.read_bytes()) == json.loads(server.read_bytes())
        table = core.table_path(self.store, logical)
        if not table.is_file():
            return False
        if logical in NESTED_CODECS:
            a = core.load_nested_table_bytes(path.read_bytes(), logical)
            b = core.load_nested_table_bytes(table.read_bytes(), logical)
            return ({k: v.text_rows() for k, v in a.rows.items()}
                    == {k: v.text_rows() for k, v in b.rows.items()})
        a = core.read_orderedmap_raw_rows_from_bytes(path.read_bytes(), logical)
        b = core.read_orderedmap_raw_rows_from_bytes(table.read_bytes(), logical)
        return dict(zip(a.keys, a.rows)) == dict(zip(b.keys, b.rows))

    # ---------------- 所有权登记（后续步骤不覆盖他人产物）
    # evidence/owned_outputs.json：{"root:logical": {"owner": 步骤名, "sha256": 登记时盘上字节}}。
    # 旧格式（值为纯字符串 owner）读时兼容，sha256 视为未知。
    def _owned_raw(self) -> dict[str, dict]:
        raw = self.read_evidence(OWNED_FILE, {}) or {}
        return {k: (dict(v) if isinstance(v, dict) else {"owner": v, "sha256": None})
                for k, v in raw.items()}

    def owned_outputs(self) -> dict[str, str]:
        return {k: v["owner"] for k, v in self._owned_raw().items()}

    def owned_record(self, root: str, logical: str) -> dict | None:
        return self._owned_raw().get(f"{root}:{logical}")

    def register_outputs(self, owner: str, entries: Iterable[tuple[str, str]]) -> None:
        """登记产物归属，同时记录登记时盘上字节的 sha256（用来识别「登记后被他人改过」）。"""
        owned = self._owned_raw()
        for root, logical in entries:
            path = self.pkg_path(root, logical)
            owned[f"{root}:{logical}"] = {"owner": owner,
                                          "sha256": sha256(path.read_bytes()) if path.is_file() else None}
        self.write_evidence(OWNED_FILE, dict(sorted(owned.items())))

    def owner_of(self, root: str, logical: str) -> str | None:
        record = self.owned_record(root, logical)
        return None if record is None else record["owner"]

    def modified_since_registration(self, root: str, logical: str,
                                    fallback_sha: str | None = None) -> bool | None:
        """盘上字节是否已不同于登记时（无登记 sha 时用 ``fallback_sha``）；无从判断返回 None。"""
        path = self.pkg_path(root, logical)
        if not path.is_file():
            return None
        record = self.owned_record(root, logical)
        want = (record or {}).get("sha256") or fallback_sha
        if want is None:
            return None
        return sha256(path.read_bytes()) != want

    # ---------------- 表写入（包副本优先）
    def table_base(self, root: str, logical: str) -> tuple[bytes, str]:
        path = self.pkg_path(root, logical)
        if path.is_file():
            return path.read_bytes(), "package"
        if root == "server":
            server = self.server_base / Path(*logical.split("/"))
            if not server.is_file():
                raise FileNotFoundError(f"server base lacks {logical}")
            return server.read_bytes(), "server"
        return self.live_table_bytes(logical), "live"

    def write_flat(self, logical: str, rows: Mapping[str, str | list],
                   root: str = "common", *, only_missing: bool = False) -> list[str]:
        base_raw, _origin = self.table_base(root, logical)
        base_om = core.read_orderedmap_raw_rows_from_bytes(base_raw, logical)
        if len(set(base_om.keys)) != len(base_om.keys):
            raise S7Error(f"base table has duplicate keys: {logical}")
        base = core.read_orderedmap_file_from_bytes(base_raw)
        keys, chunks = list(base_om.keys), list(base_om.rows)
        texts = dict(base)
        written, changed = [], False
        for key, value in rows.items():
            key = str(key)
            if only_missing and key in base:
                continue
            text = as_text(value)
            texts[key] = text
            written.append(key)
            if key in base and base[key] == text:
                continue           # 内容相同：保留原压缩字节
            chunk = zlib.compress(text.encode("utf-8")) if text else b""
            if key in base:
                chunks[keys.index(key)] = chunk
            else:
                keys.append(key)
                chunks.append(chunk)
            changed = True
        # 未改动行保留原 zlib 字节，只有新增/改动行重压缩。
        raw = core.build_orderedmap_raw_rows(core.OrderedMap(logical, keys, chunks, Path(logical))) \
            if changed else base_raw
        after = core.read_orderedmap_file_from_bytes(raw)
        if any(after.get(k) != v for k, v in base.items() if k not in written):
            raise S7Error(f"unclaimed row drift in {logical}")
        if any(after.get(k) != texts[k] for k in written):
            raise S7Error(f"flat roundtrip failed in {logical}")
        if changed or not self.pkg_has(root, logical):
            self.write_pkg(root, logical, raw)
        self.claim(logical, [str(k) for k in rows], "flat", root)
        return written

    def write_raw_outer(self, logical: str, blobs: Mapping[str, bytes],
                        root: str = "common", *, only_missing: bool = False,
                        codec: str = "raw_outer", inner: list[dict] | None = None) -> list[str]:
        base_raw, _origin = self.table_base(root, logical)
        om = core.read_orderedmap_raw_rows_from_bytes(base_raw, logical)
        before = dict(zip(om.keys, om.rows))
        keys, rows = list(om.keys), list(om.rows)
        written, changed = [], False
        for key, blob in blobs.items():
            key = str(key)
            if only_missing and key in before:
                continue
            written.append(key)
            if before.get(key) == blob:
                continue
            if key in before:
                rows[keys.index(key)] = blob
            else:
                keys.append(key)
                rows.append(blob)
            changed = True
        raw = core.build_orderedmap_raw_rows(core.OrderedMap(logical, keys, rows, Path(logical))) \
            if changed else base_raw
        back = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
        after = dict(zip(back.keys, back.rows))
        if any(after.get(k) != v for k, v in before.items() if k not in written):
            raise S7Error(f"raw row splice changed unowned rows: {logical}")
        if changed or not self.pkg_has(root, logical):
            self.write_pkg(root, logical, raw)
        self.claim(logical, [str(k) for k in blobs], codec, root, inner)
        return written

    def write_nested(self, logical: str, outer_key: str, inner_rows: Mapping[str, str | list],
                     *, only_missing: bool = False, replace_inner: bool = False) -> list[str]:
        """嵌套表（action_skill / switched_action_skill）：只动 ``outer_key`` 的内层行。"""
        codec = NESTED_CODECS.get(logical)
        if codec is None:
            raise S7Error(f"unsupported nested table {logical}")
        base_raw, _origin = self.table_base("common", logical)
        nested = core.load_nested_table_bytes(base_raw, logical)
        if only_missing and outer_key in nested.rows:
            self.claim(logical, [outer_key], codec, "common",
                       [{"outer_key": outer_key, "keys": list(nested.rows[outer_key].keys)}])
            if not self.pkg_has("common", logical):
                self.write_pkg("common", logical, base_raw)
            return []
        current: dict[str, str] = {}
        if outer_key in nested.rows and not replace_inner:
            current = nested.rows[outer_key].text_rows()
        for k, v in inner_rows.items():
            current[str(k)] = as_text(v)
        nested.rows[outer_key] = core.OrderedMap(
            f"{logical}#{outer_key}", list(current),
            [v.encode("utf-8") for v in current.values()], Path("<memory>"))
        raw = core.build_nested_table(nested, logical)
        back = core.load_nested_table_bytes(raw, logical)
        for key, inner in core.load_nested_table_bytes(base_raw, logical).rows.items():
            if key != outer_key and back.rows[key].text_rows() != inner.text_rows():
                raise S7Error(f"nested splice changed foreign outer key {key}")
        if back.rows[outer_key].text_rows() != current:
            raise S7Error(f"nested roundtrip failed for {outer_key}")
        self.write_pkg("common", logical, raw)
        self.claim(logical, [outer_key], codec, "common",
                   [{"outer_key": outer_key, "keys": list(current)}], replace_inner=replace_inner)
        return list(inner_rows)

    def write_server(self, logical: str, rows: Mapping[str, Any], *,
                     only_missing: bool = False) -> list[str]:
        import wf_character_pack as pack
        base_raw, _origin = self.table_base("server", logical)
        base = pack.load_server_json_mirror(base_raw, logical)
        additions = {str(k): v for k, v in rows.items() if not (only_missing and str(k) in base)}
        changed = any(base.get(k, object()) != v for k, v in additions.items())
        raw = pack.merge_server_json_object(base_raw, additions) if changed else base_raw
        back = json.loads(raw)
        if any(back.get(k) != v for k, v in base.items() if k not in additions):
            raise S7Error(f"server splice changed unowned rows: {logical}")
        if any(back.get(k) != v for k, v in additions.items()):
            raise S7Error(f"server splice roundtrip failed: {logical}")
        if changed or not self.pkg_has("server", logical):
            self.write_pkg("server", logical, raw)
        self.claim(logical, [str(k) for k in rows], "json_object", "server")
        return list(additions)

    def write_dsl(self, program_or_logical: str, tree, *, only_missing: bool = False,
                  owner: str | None = None) -> str:
        logical = program_or_logical if program_or_logical.endswith(DSL_SUFFIX) \
            else wf_dsl.dsl_logical(program_or_logical)
        if only_missing and self.pkg_has("common", logical):
            return logical
        raw = amf_bytes(tree)
        self.write_pkg("common", logical, raw)
        if owner:
            self.register_outputs(owner, [("common", logical)])
        return logical

    def write_asset(self, root: str, logical: str, data: bytes, *, owner: str | None = None,
                    respect_owner: str | None = None, only_missing: bool = False) -> bool:
        """写非表文件。``respect_owner``=当前步骤名：已被其他步骤登记的产物不覆盖。"""
        if only_missing and self.pkg_has(root, logical):
            return False
        if respect_owner is not None:
            holder = self.owner_of(root, logical)
            if holder is not None and holder != respect_owner and self.pkg_has(root, logical):
                return False
        self.write_pkg(root, logical, data)
        if owner:
            self.register_outputs(owner, [(root, logical)])
        return True

    # ---------------- 包内读取
    def pkg_flat(self, logical: str, root: str = "common") -> dict[str, str]:
        return core.read_orderedmap_file_from_bytes(self.pkg_path(root, logical).read_bytes())

    def pkg_character_row(self) -> list[str]:
        return csv_split(self.pkg_flat("master/character/character.orderedmap")[self.spec.cid_s])[0]

    def pkg_character_text_row(self) -> list[str]:
        return csv_split(self.pkg_flat("master/character/character_text.orderedmap")[self.spec.cid_s])[0]

    def sync_character_mirrors(self) -> dict[str, Any]:
        """三层镜像按包内客户端行重建：cdndata/character(_text).json 与 character.json。"""
        crow = self.pkg_character_row()
        trow = self.pkg_character_text_row()
        cid = self.spec.cid_s
        self.write_server("cdndata/character.json", {cid: [crow]})
        self.write_server("cdndata/character_text.json", {cid: [trow]})
        server_char = {"element": int(crow[3]), "name": trow[0],
                       "rarity": int(crow[2]), "skill_count": 6}
        self.write_server("character.json", {cid: server_char})
        return {"character": crow, "character_text": trow, "server_character": server_char}

    def pkg_dsl_programs(self) -> list[str]:
        base = self.package / "roots" / "common"
        if not base.is_dir():
            return []
        return sorted(p.relative_to(base).as_posix() for p in base.rglob("*" + DSL_SUFFIX))


# ---------------------------------------------------------------- 特效族克隆

def clone_effect_family(pack: S7Pack, src_dir: str, dst_subdir: str,
                        fx_names: Iterable[str] | None = None, *, layout: str = "codename",
                        png_transform: Callable[[Any], Any] | None = None,
                        owner: str = "effects") -> dict[str, Any]:
    """把 ``battle/effect/skill_unique/<donor>/`` 复制到新角色命名空间。

    目录形态（记忆卡 wf-effect-family-under-codename + 09-10 更正）：
    - ``layout="codename"``（默认，基诺维先例）：``skill_unique/<code>/<dst_subdir>/``
    - ``layout="sibling"``（奈芙提姆先例）：``skill_unique/<code>_<dst_subdir>/``
    两种形态都满足预载器规则：sheet 必须是 ``<dir>/<dir>.png/.atlas``；atlas ``n`` 与 parts
    ``i[].p`` 的 ``<dir>/.gen/<基名>/<帧>`` 前缀整体改写；parts/timeline 基名保留；timeline 内嵌 SE
    路径原文保留。返回 ``{"prefix_map", "copied_bases", "effects", "missing_effects", "files", …}``。
    kit 改 DSL 引用一律用 :func:`rewrite_effect_refs`（按路径段只改写已复制的基名，并对 dst
    目录下的悬空引用报错）；``prefix_map`` 仅在整族复制且无缺失时非 None。
    """
    src_dir = src_dir.rstrip("/")
    if not src_dir.startswith("battle/effect/"):
        raise S7Error(f"effect family must live under battle/effect/: {src_dir}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_]*", dst_subdir):
        raise S7Error(f"invalid effect subdir {dst_subdir}")
    donor = src_dir.rsplit("/", 1)[-1]
    code = pack.spec.code
    if layout == "codename":
        dst_dir = f"battle/effect/skill_unique/{code}/{dst_subdir}"
    elif layout == "sibling":
        dst_dir = f"battle/effect/skill_unique/{code}_{dst_subdir}"
    else:
        raise S7Error(f"unknown effect layout {layout}")
    dst_name = dst_dir.rsplit("/", 1)[-1]
    prefix_map = {src_dir + "/": dst_dir + "/"}

    atlas_logical = f"{src_dir}/{donor}.atlas.amf3.deflate"
    sheet_logical = f"{src_dir}/{donor}.png"
    root, atlas_raw, atlas_src = pack.template_asset(atlas_logical)
    atlas = amf_parse(atlas_raw)
    bases = sorted({m.group(1) for item in atlas if isinstance(item, dict)
                    for m in [re.match(re.escape(src_dir) + r"/\.gen/([^/]+)/", str(item.get("n", "")))]
                    if m})
    pathlist = pack.root / "mod-tools/WF_PATHLIST_recovered.txt"
    if pathlist.is_file():
        for line in pathlist.read_text("utf-8").splitlines():
            line = line.strip()
            m = re.fullmatch(re.escape(src_dir) + r"/([^/]+)\.(parts|timeline)\.amf3\.deflate", line)
            if m:
                bases.append(m.group(1))
    wanted = sorted(set(fx_names) if fx_names is not None else set(bases))
    files, effects, missing = [], [], []

    def put(src_logical: str, dst_logical: str, data: bytes, source: str, src_raw: bytes) -> None:
        pack.write_asset(root, dst_logical, data, owner=owner)
        files.append({"source": src_logical, "target": dst_logical, "root": root,
                      "source_sha256": sha256(src_raw), "sha256": sha256(data), "provenance": source})

    new_atlas = replace_strings(atlas, prefix_map)
    atlas_names = {item["n"] for item in new_atlas if isinstance(item, dict) and "n" in item}
    put(atlas_logical, f"{dst_dir}/{dst_name}.atlas.amf3.deflate", amf_bytes(new_atlas),
        atlas_src, atlas_raw)
    _r, sheet_raw, sheet_src = pack.template_asset(sheet_logical)
    sheet_out = sheet_raw
    if png_transform is not None:
        sheet_out = png_store_bytes(png_transform(png_open(sheet_raw)))
    put(sheet_logical, f"{dst_dir}/{dst_name}.png", sheet_out, sheet_src, sheet_raw)
    texture_problems = []
    for base in wanted:
        present = False
        for kind in ("parts", "timeline"):
            logical = f"{src_dir}/{base}.{kind}.amf3.deflate"
            try:
                _root, raw, src = pack.template_asset(logical)
            except FileNotFoundError:
                continue
            present = True
            tree = amf_parse(raw)
            new_tree = replace_strings(tree, prefix_map) if kind == "parts" else tree
            data = raw if new_tree == tree else amf_bytes(new_tree)
            put(logical, f"{dst_dir}/{base}.{kind}.amf3.deflate", data, src, raw)
            if kind == "parts" and isinstance(new_tree, dict):
                refs = {i["p"] for i in new_tree.get("i", []) if isinstance(i, dict) and "p" in i}
                lost = sorted(refs - atlas_names)
                if lost:
                    texture_problems.append({"effect": base, "missing": lost[:10]})
        if present:
            effects.append({"source": f"{src_dir}/{base}", "target": f"{dst_dir}/{base}"})
        else:
            missing.append(base)
    if texture_problems:
        raise S7Error(f"cloned parts reference textures outside atlas: {texture_problems}")
    copied = sorted({e["target"].rsplit("/", 1)[-1] for e in effects})
    complete = fx_names is None and not missing
    result = {"src_dir": src_dir, "dst_dir": dst_dir, "layout": layout, "donor": donor,
              "dst_name": dst_name, "copied_bases": copied, "complete_family": complete,
              # 目录级前缀映射只在整族复制且无缺失时给出；子集复制必须用 rewrite_effect_refs，
              # 否则未复制特效的引用会被改到包内不存在的 dst 路径（进战斗数据不足/C8003）。
              "prefix_map": prefix_map if complete else None,
              "effects": effects, "missing_effects": missing, "files": files}
    registry = pack.read_evidence("effect-families.json", {}) or {}
    registry[dst_dir] = {k: v for k, v in result.items() if k != "files"} | {"file_count": len(files)}
    pack.write_evidence("effect-families.json", dict(sorted(registry.items())))
    return result


_EFFECT_BASE_RE = re.compile(r"(?:\.gen/)?([^/.]+)")


def rewrite_effect_refs(tree, family: Mapping[str, Any], *, strict: bool = False) -> tuple[Any, dict]:
    """按 ``clone_effect_family`` 的结果改写 DSL/任意树里的特效引用（按路径段，不做裸子串替换）。

    - ``<src_dir>/<基名>``（及 ``.parts/.timeline`` 后缀、``.gen/<基名>/`` 帧路径、sheet/atlas 名）
      只有基名在 ``copied_bases``（或是 donor sheet 名）时才改写到 ``<dst_dir>/``；
    - 未复制基名的引用保留原官方路径（跨 code 直接引用官方特效合法），列入 ``kept_donor``；
      ``strict=True`` 时对它们报错；
    - 改写后树里任何 ``<dst_dir>/`` 引用若指向未复制的基名（例如先前用错误前缀映射改过）一律报错。
    返回 ``(新树, {"rewritten": n, "kept_donor": [...]})``；输入树不变。
    """
    src_dir, dst_dir = family["src_dir"].rstrip("/"), family["dst_dir"].rstrip("/")
    copied = set(family.get("copied_bases") or [])
    sheet_names = {family.get("donor"), family.get("dst_name")} - {None}
    kept: set[str] = set()
    dangling: set[str] = set()
    count = 0

    def base_of(rest: str) -> str | None:
        m = _EFFECT_BASE_RE.match(rest)
        return m.group(1) if m else None

    def fix(value: str) -> str:
        nonlocal count
        if value.startswith(src_dir + "/"):
            base = base_of(value[len(src_dir) + 1:])
            if base in copied or base == family.get("donor"):
                rest = value[len(src_dir) + 1:]
                if base == family.get("donor") and base not in copied:
                    rest = rest.replace(family["donor"], family.get("dst_name", family["donor"]), 1)
                count += 1
                return f"{dst_dir}/{rest}"
            kept.add(value)
            return value
        if value.startswith(dst_dir + "/"):
            base = base_of(value[len(dst_dir) + 1:])
            if base not in copied and base not in sheet_names:
                dangling.add(value)
        return value

    def rec(node):
        if isinstance(node, str):
            return fix(node)
        if isinstance(node, list):
            return [rec(item) for item in node]
        if isinstance(node, dict):
            return {rec(k): rec(v) for k, v in node.items()}
        return node

    new_tree = rec(tree)
    if dangling:
        raise S7Error(f"effect refs under {dst_dir} point at bases that were not copied: {sorted(dangling)[:10]}")
    if strict and kept:
        raise S7Error(f"effect refs still point at donor {src_dir} (not copied): {sorted(kept)[:10]}")
    return new_tree, {"rewritten": count, "kept_donor": sorted(kept)}
