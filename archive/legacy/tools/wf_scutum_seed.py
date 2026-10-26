"""盾牌座候选包基础 I/O；所有生产输入只读，所有输出均限制于候选包。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import zlib

import wf_character_pack as pack
import wf_character_workspace as workspace
import wf_mod_tool as core
from wf_enhancement_policy import OfficialBaseline

CID, CODE = "149988", "scutum_valentine"
TEMPLATE_ID, TEMPLATE_CODE = "151002", "prince_zero"
PACKAGE_ID = "scutum-valentine-20260912"


def remap(value):
    if isinstance(value, str):
        if value == TEMPLATE_ID:
            return CID
        if re.fullmatch(str(int(TEMPLATE_ID) * 2) + r"\d{3}", value):
            return str(int(CID) * 2) + value[6:]
        return value.replace(TEMPLATE_CODE, CODE)
    if isinstance(value, list):
        return [remap(x) for x in value]
    if isinstance(value, dict):
        return {remap(k): remap(v) for k, v in value.items()}
    return value


def clone_blob(raw):
    try:
        text = zlib.decompress(raw).decode("utf-8")
    except (zlib.error, UnicodeDecodeError):
        inner = core.read_orderedmap_raw_rows_from_bytes(raw, "nested")
        inner.keys = [remap(k) for k in inner.keys]
        inner.rows = [clone_blob(v) for v in inner.rows]
        return core.build_orderedmap_raw_rows(inner)
    return zlib.compress(core.write_csv_lines(remap(core.read_csv_lines(text))).rstrip("\n").encode())


class Seed:
    def __init__(self, repo, candidate):
        self.repo = Path(repo).resolve()
        self.ws = workspace.load_workspace(candidate)
        if (str(self.ws.character_id), self.ws.code_name) != (CID, CODE):
            raise ValueError("wrong Scutum workspace")
        if not self.ws.root.resolve().is_relative_to(self.repo / "work/character_packs"):
            raise ValueError("candidate escaped workspace")
        p = json.loads((self.repo / "mod-tools/profiles.json").read_bytes())["profiles"]["cn"]
        self.store = Path(p["store"])
        if not self.store.is_absolute():
            self.store = self.repo / self.store
        self.baseline = OfficialBaseline(self.repo / ".cdn/cn", write_cache=False)
        self.manifest_raw = (self.ws.package_dir / "manifest.json").read_bytes()
        self.manifest = json.loads(self.manifest_raw)
        self.outputs, self.claims, self.sources = {}, {}, {}
        self.codecs = {}
        self.inner_keys = {}
        if CID in self.rows(core.CHARACTER_LOGICAL):
            raise ValueError("Scutum identity already exists in live; use revision workflow")

    def read(self, logical):
        return core.table_path(self.store, logical).read_bytes()

    def rows(self, logical):
        raw = self.outputs.get(("common", logical))
        if raw is None:
            raw = self.read(logical)
        return {k: core.read_csv_lines(v) for k, v in core.read_orderedmap_file_from_bytes(raw).items()}

    def official(self, logical):
        h = core.sha1_path(logical)
        raw = self.baseline.get("common", h[:2] + "/" + h[2:])
        if raw is None:
            raise FileNotFoundError(logical)
        self.sources[logical] = hashlib.sha256(raw).hexdigest()
        return raw

    def emit(self, tier, logical, raw):
        if tier not in pack.ROOT_NAMES or pack._path_problem(logical):
            raise ValueError("unsafe package asset")
        self.outputs[tier, logical] = raw

    def table(self, logical, replacements, codec="flat"):
        raw = self.outputs.get(("common", logical))
        if raw is None:
            raw = self.read(logical)
        table = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
        claim = self.claims.setdefault(("common", logical), set())
        for key, value in replacements.items():
            if key in table.keys and key not in claim:
                raise ValueError(f"existing unowned key {logical}:{key}")
            if codec == "flat":
                value = zlib.compress(core.write_csv_lines(value).rstrip("\n").encode("utf-8"))
            if key in table.keys:
                table.rows[table.keys.index(key)] = value
            else:
                table.keys.append(key); table.rows.append(value)
            claim.add(key)
        self.emit("common", logical, core.build_orderedmap_raw_rows(table))
        self.codecs["common", logical] = codec

    def clone(self, logical):
        table = core.read_orderedmap_raw_rows_from_bytes(self.read(logical), logical)
        self.table(logical, {CID: clone_blob(table.rows[table.keys.index(TEMPLATE_ID)])}, "raw_outer")

    def server(self, logical, value):
        data = json.loads((self.repo / "assets" / logical).read_bytes())
        if CID in data:
            raise ValueError("server character identity collision")
        data[CID] = value
        self.emit("server", logical, json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode())
        self.claims["server", logical] = {CID}
        self.codecs["server", logical] = "json_object"

    def begin(self):
        self.codecs = {}

    def finish(self, metadata, *, apply=False):
        manifest = deepcopy(self.manifest)
        manifest.update(package_version="0.1.0", requires_client_base="1.4.836")
        manifest["roots"] = {tier: [dict(logical_path=p, sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))
                                  for (t, p), raw in sorted(self.outputs.items()) if t == tier]
                             for tier in pack.ROOT_NAMES}
        manifest["tables"] = [dict(root=t, logical_path=p, codec_id=self.codecs[t, p],
                                   outer_keys=sorted(keys), inner_keys=self.inner_keys.get((t, p), []), semantic_claims=[])
                              for (t, p), keys in sorted(self.claims.items())]
        manifest["snapshot"]["scutum"] = metadata
        manifest["required_capabilities"] = metadata.get("required_capabilities", [])
        manifest["unique_condition"] = metadata.get("unique_condition", {})
        manifest["skills"] = {"programs": [p for t, p in self.outputs if p.endswith(".action.dsl.amf3.deflate")]}
        manifest["qa"].update(release_ready=False, workspace_input_sha256="")
        if apply:
            if (self.ws.package_dir / "manifest.json").read_bytes() != self.manifest_raw:
                raise ValueError("candidate changed during assembly")
            for (tier, logical), raw in self.outputs.items():
                path = self.ws.package_dir / "roots" / tier / logical
                if not path.resolve().is_relative_to(self.ws.package_dir.resolve()):
                    raise ValueError("output escaped package")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            (self.ws.package_dir / "manifest.json").write_bytes(pack.canonical_manifest_bytes(manifest))
        return {"writes_live": False, "applied": apply, "files": len(self.outputs), "metadata": metadata}
