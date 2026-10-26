"""PF donor rows and three-level ActionDsl programs from a view and target APKs."""
from __future__ import annotations

import copy
import struct
import zipfile
import zlib

import wf_mod_tool as core
from wf.caps.profiles import load_profiles
from wf.deliver.changeset import relative_path
from wf.rules.dsl_signature import validate_action_dsl
from .bundle_index import bundled_logical
from .deliver_media import read_root, tree as decode_tree
from .delivery_safety import resolve_apks
from .drafts import DraftError
from .pf_bundle import PfBundle, digest

PF_TABLE = "master/skill/power_flip_action.orderedmap"
DSL_SUFFIX = ".action.dsl.amf3.deflate"
STANDARD_TYPES = {"knight", "fighter", "ranged", "special", "supporter"}


def _rows(raw, logical):
    try:
        table = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
        return dict(zip(table.keys, table.rows))
    except (ValueError, TypeError, IndexError, KeyError, struct.error, zlib.error) as exc:
        raise DraftError(f"PF 母本表无效：{logical}：{exc}") from exc


def _decode_row(raw, key):
    try:
        values = core.read_csv_lines(zlib.decompress(raw).decode("utf-8"))
        if len(values) != 1 or len(values[0]) != 3:
            raise ValueError("expected exactly three level paths")
        for path in values[0]:
            relative_path(path)
            if not path.startswith("battle/action/"):
                raise ValueError("expected battle/action logical paths")
        return values[0]
    except (ValueError, UnicodeError, zlib.error) as exc:
        raise DraftError(f"PF 母本 {key} 的三档行无效：{exc}") from exc


def _type(key, row):
    if key in STANDARD_TYPES:
        return key
    # Variant keys usually retain the native action family's program stem.
    stem = row[0].rsplit("/", 1)[-1].split("$", 1)[0]
    return stem if stem in STANDARD_TYPES else "custom"


def decode_program(raw, logical):
    """Reject malformed donor programs with the same public draft error shape."""
    try:
        value = decode_tree(raw)
        validate_action_dsl(value)
        return value
    except (ValueError, TypeError, IndexError, KeyError, struct.error, zlib.error) as exc:
        raise DraftError(f"PF 母本 DSL 无效：{logical}：{exc}") from exc


class PfCatalog:
    """Read-only donor catalog; invalid configured APKs fail closed."""

    def __init__(self, source, client_profile=None, apks=None, cache_dir=None):
        self.source = source
        self.inputs = {}
        self.warnings = []
        self._rows, self._sources, self._conflicts = {}, {}, {}
        try:
            if apks is None and client_profile is None:
                client_profile = load_profiles()[0]
            self._bundles = [PfBundle(apk, PF_TABLE, cache_dir)
                             for apk in resolve_apks(client_profile, apks)]
        except (OSError, ValueError, TypeError, KeyError, zipfile.BadZipFile, RuntimeError, zlib.error) as exc:
            raise DraftError(f"目标 APK 内置 PF 目录读取失败：{exc}") from exc
        self.bundled_available = bool(self._bundles)
        if not self._bundles:
            self.warnings.append("未配置目标 APK，只能选择当前 CDN 视图中的 PF 母本；内置键碰撞尚未核对。")
        try:
            raw = source.raw(PF_TABLE)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise DraftError(f"PF 当前视图表读取失败：{exc}") from exc
        if raw is not None:
            self.inputs["cdn:common:" + PF_TABLE] = digest(raw)
            for key, row in _rows(raw, PF_TABLE).items():
                self._add(key, row, "cdn")
        logical = bundled_logical(PF_TABLE)
        for bundle in self._bundles:
            self.inputs["apk:" + bundle.sha256] = bundle.sha256
            raw = bundle.read(logical)
            if raw is None:
                continue
            self.inputs["bundled:" + bundle.sha256 + ":" + logical] = digest(raw)
            rows = _rows(raw, logical)
            if sorted(rows) != bundle.index["tables"].get(PF_TABLE, []):
                raise DraftError("APK PF 三档表与内置键索引不一致")
            for key, row in rows.items():
                self._add(key, row, "bundled")

    @property
    def keys(self):
        """All occupied CDN/bundled keys, including donors that cannot resolve."""
        return set(self._rows)

    def _add(self, key, raw, origin):
        if key in self._rows:
            if self._sources[key] != origin:
                self._conflicts[key] = "母本键同时存在于 CDN 与 APK 内置表，违反内置键约束"
            elif _decode_row(self._rows[key], key) != _decode_row(raw, key):
                self._conflicts[key] = "多个目标 APK 的同名 PF 三档行不一致"
            return
        self._rows[key], self._sources[key] = raw, origin

    def read(self, logical, root="common"):
        """Read the exact view root first, then a compatible APK bundled asset."""
        relative_path(logical)
        if root not in {"common", "android", "medium", "small", "ios"}:
            raise DraftError("无效 PF 资源根：" + str(root))
        try:
            raw = read_root(self.source, root, logical)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise DraftError(f"PF 当前视图资源读取失败：{root}/{logical}：{exc}") from exc
        if raw is not None:
            self.inputs[f"cdn:{root}:{logical}"] = digest(raw)
            return raw
        if root not in {"common", "android"}:
            return None
        found = [(bundle, value) for bundle in self._bundles
                 if (value := bundle.read(logical)) is not None]
        if not found:
            return None
        if len(found) != len(self._bundles):
            raise DraftError("部分目标 APK 缺少 PF 资源，不能由另一 APK 代替：" + logical)
        hashes = {digest(value) for _, value in found}
        if len(hashes) != 1:
            raise DraftError("多个目标 APK 的同名 PF 资源内容不一致：" + logical)
        for bundle, value in found:
            self.inputs[f"bundled:{bundle.sha256}:{root}:{logical}"] = digest(value)
        return found[0][1]

    def resolve(self, key):
        if key not in self._rows:
            raise DraftError("PF 母本不存在：" + str(key))
        if key in self._conflicts:
            raise DraftError(self._conflicts[key] + "：" + key)
        row = _decode_row(self._rows[key], key)
        trees = []
        for path in row:
            logical = path if path.endswith(DSL_SUFFIX) else path + DSL_SUFFIX
            raw = self.read(logical)
            if raw is None:
                raise DraftError("PF 母本缺少三档 DSL：" + logical)
            trees.append(decode_program(raw, logical))
        return {"key": key, "source": self._sources[key], "row": row,
                "trees": trees, "inputs": dict(self.inputs)}

    def detail(self, key):
        from .pf_dsl import summary
        donor = self.resolve(key)
        levels = [{"level": number, "path": path, **summary(value)}
                  for number, (path, value) in enumerate(zip(donor["row"], donor["trees"]), 1)]
        return {"key": key, "source": donor["source"], "type": _type(key, donor["row"]),
                "levels": levels, "warnings": list(self.warnings), "selectable": True}

    def list(self, q=""):
        if not isinstance(q, str):
            raise DraftError("PF 搜索 q 必须为字符串")
        items = []
        for key in sorted(self._rows):
            if q.casefold() not in key.casefold():
                continue
            item = {"key": key, "source": self._sources[key]}
            try:
                detail = self.detail(key)
                item.update(type=detail["type"], selectable=True,
                            levels=[{"level": level["level"],
                                     "nominalMultiplier": copy.deepcopy(level["nominalMultiplier"])}
                                    for level in detail["levels"]])
            except (DraftError, ValueError, TypeError, KeyError, zlib.error) as exc:
                item.update(type=key if key in STANDARD_TYPES else "custom", selectable=False,
                            levels=[], error=str(exc))
            items.append(item)
        return {"items": items, "warnings": list(self.warnings),
                "bundledAvailable": self.bundled_available}
