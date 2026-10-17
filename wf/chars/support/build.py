"""Production primitives extracted from wf_seasonal7_build.py (C baseline)."""
from __future__ import annotations
import json


from typing import Any


from wf.chars.support import common as C  # noqa: E402


class KitContext:
    """暴露给 ``wf_seasonal7_kit_<key>.build(ctx)`` 的 API（详见 framework_api.md）。"""

    def __init__(self, pack: C.S7Pack) -> None:
        self.pack = pack
        self.spec = pack.spec
        self.root = pack.root
        self.workspace = pack.workspace
        self.package = pack.package
        self.evidence = pack.evidence
        self.store = pack.store
        # 纯函数
        self.replace_strings = C.replace_strings
        self.walk = C.walk
        self.commands = C.commands
        self.csv_split = C.csv_split
        self.csv_join = C.csv_join
        self.amf_parse = C.amf_parse
        self.amf_bytes = C.amf_bytes
        self.png_open = C.png_open
        self.png_store_bytes = C.png_store_bytes
        self.flip_ability_row = C.flip_ability_row
        self.flip_dsl_elements = C.flip_dsl_elements

    # 读
    def official_read(self, logical: str, root: str | None = None) -> bytes | None:
        return self.pack.official_read(logical, root)

    def official_flat(self, logical: str) -> dict[str, str]:
        raw = self.pack.official_read(logical, "common")
        if raw is None:
            raise FileNotFoundError(f"official baseline lacks {logical}")
        return C.core.read_orderedmap_file_from_bytes(raw)

    def official_rows(self, table: str, key: str) -> list[list[str]]:
        logical = table if "/" in table else f"master/ability/{table}.orderedmap"
        return C.csv_split(self.official_flat(logical)[key])

    def live_read(self, logical: str) -> bytes:
        return self.pack.live_read(logical)

    def live_flat(self, logical: str) -> dict[str, str]:
        return self.pack.live_flat(logical)

    def template_flat(self, logical: str) -> dict[str, str]:
        return self.pack.template_flat(logical)

    def template_dsl(self, program_or_logical: str):
        return self.pack.template_dsl(program_or_logical)

    def pkg_flat(self, logical: str, root: str = "common") -> dict[str, str]:
        return self.pack.pkg_flat(logical, root)

    def pkg_nested(self, outer_key: str, logical: str = C.core.ACTION_SKILL_LOGICAL) -> dict[str, list[str]]:
        """包内嵌套表某外键的内层行：{inner_key: cells}（不存在返回 {}）。"""
        if not self.pack.pkg_has("common", logical):
            return {}
        table = C.core.load_nested_table_bytes(self.pack.pkg_path("common", logical).read_bytes(), logical)
        if outer_key not in table.rows:
            return {}
        return {k: C.csv_split(v)[0] for k, v in table.rows[outer_key].text_rows().items()}

    def program_path(self, level: str) -> str:
        from wf.chars.support import tables as T
        return T.program_path(self.spec, level)

    # 写（包副本优先 + 认领合并）
    def write_flat(self, logical: str, rows, root: str = "common", **kw):
        return self.pack.write_flat(logical, rows, root, **kw)

    def write_raw_outer(self, logical: str, blobs, root: str = "common", **kw):
        return self.pack.write_raw_outer(logical, blobs, root, **kw)

    def write_nested(self, logical: str, outer_key: str, inner_rows, **kw):
        return self.pack.write_nested(logical, outer_key, inner_rows, **kw)

    def write_server(self, logical: str, rows, **kw):
        return self.pack.write_server(logical, rows, **kw)

    def write_dsl(self, program_or_logical: str, tree, **kw):
        kw.setdefault("owner", "kit")
        return self.pack.write_dsl(program_or_logical, tree, **kw)

    def write_asset(self, root: str, logical: str, data: bytes, **kw):
        kw.setdefault("owner", "kit")
        return self.pack.write_asset(root, logical, data, **kw)

    def claim(self, logical: str, keys, codec: str = "flat", root: str = "common", inner=None, *,
              replace_inner: bool = False):
        return self.pack.claim(logical, keys, codec, root, inner, replace_inner=replace_inner)

    def unclaim(self, logical: str, keys=(), **kw):
        """撤销认领并把包内行还原为底表（见 ``S7Pack.unclaim``）。"""
        return self.pack.unclaim(logical, keys, **kw)

    def register_outputs(self, owner: str, entries) -> None:
        """登记非表产物归属（记录 sha256；assets 重跑不会覆盖）。直接写盘的工具必须调用。"""
        self.pack.register_outputs(owner, entries)

    def clone_effect_family(self, src_dir: str, dst_subdir: str, fx_names=None, **kw):
        return C.clone_effect_family(self.pack, src_dir, dst_subdir, fx_names, **kw)

    def rewrite_effect_refs(self, tree, family, *, strict: bool = False):
        return C.rewrite_effect_refs(tree, family, strict=strict)

    def sync_character_mirrors(self):
        return self.pack.sync_character_mirrors()

    def evidence_write(self, name: str, value: Any):
        return self.pack.write_evidence(name, value)

    def report(self, value: dict[str, Any]) -> None:
        """写 evidence/kit-report.json（manifest 整合器读取 skills/unique_condition/
        required_capabilities/summary/panel/notes/status）。"""
        self.pack.write_evidence("kit-report.json", value)


def step_init(pack: C.S7Pack) -> dict[str, Any]:
    """直接建 workspace 壳（目录名 s7-<key> ≠ package_id，flow init 会以 package_id 作目录名）。"""
    import wf_character_workspace as ws
    spec = pack.spec
    marker = pack.workspace / "workspace.json"
    payload = ws._workspace_payload(spec.template_id, spec.cid, spec.code, spec.pkg_id)
    if marker.is_file():
        current = json.loads(marker.read_text(encoding="utf-8"))
        if current != payload:
            raise C.S7Error(f"existing workspace.json differs from spec: {current}")
        created = False
    else:
        if pack.workspace.exists() and any(pack.workspace.iterdir()):
            raise C.S7Error(f"workspace destination is non-empty without workspace.json: {pack.workspace}")
        for root_name in C.ROOT_NAMES:
            (pack.package / "roots" / root_name).mkdir(parents=True, exist_ok=True)
        pack.evidence.mkdir(parents=True, exist_ok=True)
        ws._atomic_json(marker, payload)
        ws._atomic_json(pack.package / "manifest.json",
                        ws._draft_manifest(spec.cid, spec.code, spec.pkg_id))
        created = True
    for root_name in C.ROOT_NAMES:
        (pack.package / "roots" / root_name).mkdir(parents=True, exist_ok=True)
    pack.evidence.mkdir(parents=True, exist_ok=True)
    loaded = ws.load_workspace(pack.workspace)
    pack.write_evidence("spec.json", spec.to_dict())
    return {"workspace": str(loaded.root), "created": created, "package_id": loaded.package_id,
            "character_id": loaded.character_id, "code_name": loaded.code_name}
