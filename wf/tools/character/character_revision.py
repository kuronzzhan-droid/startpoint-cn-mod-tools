"""已发布角色修订的候选包 I/O；保留非自有行与展示资产。"""
from __future__ import annotations

import copy
import hashlib
import json
import zlib
from pathlib import Path

import wf_character_pack as pack
import wf_character_workspace as workspace
import wf_dsl
import wf_mod_tool as core
from wf_enhancement_policy import OfficialBaseline

PRESENTATION_TABLES = {"master/generated/character_image.orderedmap",
                       "master/generated/trimmed_image.orderedmap",
                       "master/character/full_shot_image_attribute.orderedmap",
                       "master/character/character_speech.orderedmap"}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encode_tree(tree) -> bytes:
    raw = wf_dsl.encode_amf3(tree)
    if wf_dsl.parse_dsl(raw)["tree"] != tree:
        raise ValueError("AMF3 roundtrip mismatch")
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    return compressor.compress(raw) + compressor.flush()


class RevisionCandidate:
    def __init__(self, repo_root: Path, candidate_root: Path, *,
                 character_id: str, code_name: str, package_version: str,
                 snapshot_key: str, evidence_name="revision.json",
                 baseline_factory=OfficialBaseline, reviewed_input_drift=None):
        self.cid, self.code = character_id, code_name
        self.package_version, self.snapshot_key = package_version, snapshot_key
        self.evidence_name = evidence_name
        self.repo = repo_root.resolve()
        self.ws = workspace.load_workspace(candidate_root)
        if self.ws.character_id != int(self.cid) or self.ws.code_name != self.code:
            raise ValueError("candidate identity differs from assigned character")
        if not self.ws.root.resolve().is_relative_to(self.repo / "work/character_packs"):
            raise ValueError("candidate must be under the ignored character workspace")
        self.manifest_bytes = (self.ws.package_dir / "manifest.json").read_bytes()
        self.manifest = json.loads(self.manifest_bytes)
        self.before = copy.deepcopy(self.manifest)
        profile = json.loads((self.repo / "mod-tools/profiles.json").read_bytes())["profiles"]["cn"]
        store = Path(profile["store"])
        self.store = store if store.is_absolute() else self.repo / store
        self.baseline = baseline_factory(
            self.repo / ".cdn/cn", cache_dir=self.repo / "mod-tools/work/official-baseline",
            write_cache=False,
        )
        self.index = {(tier, entry["logical_path"]): entry
                      for tier, entries in self.manifest["roots"].items() for entry in entries}
        self.original = {}
        self.reviewed_input_drift = reviewed_input_drift or {}
        seen_drift = set()
        for key, entry in self.index.items():
            raw = self.path(*key).read_bytes()
            if digest(raw) != entry["sha256"] or len(raw) != entry["size"]:
                # Explicit hashes acknowledge reviewed existing WIP, never silently reseal it.
                if self.reviewed_input_drift.get(key) != digest(raw):
                    raise ValueError(f"candidate drift: {key}")
                seen_drift.add(key)
            self.original[key] = raw
        if seen_drift != set(self.reviewed_input_drift):
            raise ValueError("reviewed candidate drift changed or contains unrelated entries")
        self.outputs = {}
        self.sources = {}

    def path(self, tier: str, logical: str) -> Path:
        if tier not in self.manifest["roots"] or pack._path_problem(logical):
            raise ValueError("unsafe candidate path")
        path = self.ws.package_dir / "roots" / tier / logical
        if not path.resolve().is_relative_to(self.ws.package_dir.resolve()):
            raise ValueError("candidate path escaped")
        for component in (path, *path.parents):
            if component.is_symlink() or getattr(component, "is_junction", lambda: False)():
                raise ValueError("candidate path has a reparse component")
        return path

    def official(self, logical: str, tier: str = "common") -> bytes:
        hashed = core.sha1_path(logical)
        raw = self.baseline.get(tier, hashed[:2] + "/" + hashed[2:])
        if raw is None:
            raise ValueError(f"official source absent: {tier}:{logical}")
        self.sources[tier, logical] = digest(raw)
        return raw

    def official_rows(self, logical: str) -> dict:
        return {key: core.read_csv_lines(text) for key, text in
                core.read_orderedmap_file_from_bytes(self.official(logical)).items()}

    def official_tree(self, logical: str):
        return wf_dsl.parse_dsl(zlib.decompress(self.official(logical), -15))["tree"]

    def read(self, tier: str, logical: str) -> bytes:
        key = (tier, logical)
        if key in self.outputs:
            return self.outputs[key]
        if key in self.original:
            return self.original[key]
        if tier != "common" or not logical.startswith("master/"):
            raise ValueError(f"new source must be an explicit common master: {key}")
        return core.table_path(self.store, logical).read_bytes()

    def emit(self, tier: str, logical: str, raw: bytes):
        self.path(tier, logical)
        self.outputs[tier, logical] = raw

    def splice(self, logical: str, replacements: dict, *, codec="flat"):
        """保持未声明行的压缩字节；新增键不能与已有 live 键碰撞。"""
        table = core.read_orderedmap_raw_rows_from_bytes(self.read("common", logical), logical)
        old_rows = dict(zip(table.keys, table.rows))
        claim = next((item for item in self.manifest["tables"]
                      if item["root"] == "common" and item["logical_path"] == logical), None)
        owned = set(claim["outer_keys"]) if claim else set()
        for key, value in replacements.items():
            panel_override = (
                logical == "master/string/custom_ability_string.orderedmap"
                and key in {"desc_override_" + self.code,
                            *(f"desc_override_{self.code}_{slot}" for slot in range(1, 7))}
            )
            if key not in owned and not (key.startswith(self.cid) or key.startswith(self.code)
                                        or key.startswith("change_skill_" + self.code)
                                        or panel_override):
                raise ValueError(f"new key is outside the assigned character namespace: {key}")
            if key in old_rows and key not in owned:
                raise ValueError(f"unowned existing key: {logical}:{key}")
            if codec == "flat":
                value = zlib.compress(core.write_csv_lines(value).rstrip("\n").encode("utf-8"))
            elif codec not in {"raw_outer", "action_nested"}:
                raise ValueError("unsupported candidate codec")
            if key in table.keys:
                table.rows[table.keys.index(key)] = value
            else:
                table.keys.append(key)
                table.rows.append(value)
        assert all(raw == old_rows[key] for key, raw in zip(table.keys, table.rows)
                   if key in old_rows and key not in replacements)
        if claim is None:
            claim = dict(root="common", logical_path=logical, codec_id=codec,
                         outer_keys=[], inner_keys=[], semantic_claims=[])
            self.manifest["tables"].append(claim)
        if claim["codec_id"] != codec:
            raise ValueError("cannot change an installed table codec")
        claim["outer_keys"] = sorted(owned | set(replacements))
        self.emit("common", logical, core.build_orderedmap_raw_rows(table))

    def server_character_row(self, logical: str, value):
        key = ("server", logical)
        if key not in self.original:
            raise ValueError("cannot add a server mirror")
        rows = json.loads(self.original[key])
        if self.cid not in rows:
            raise ValueError("candidate server identity missing")
        rows[self.cid] = value
        self.emit(*key, json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    def finish(self, metadata: dict, *, apply=False) -> dict:
        for key, raw in self.outputs.items():
            # 玩法修订不得回退本角色已生成立绘、裁图、ATF、语音和定位数据。
            if key in self.original and (key[0] in {"medium", "android"}
                                        or "/voice/" in key[1] or "/ui/" in key[1]
                                        or key[1] in PRESENTATION_TABLES):
                if raw != self.original[key]:
                    raise ValueError(f"protected presentation asset changed: {key}")
            entry = self.index.get(key)
            if entry is None:
                entry = dict(logical_path=key[1])
                self.manifest["roots"][key[0]].append(entry)
            entry.update(sha256=digest(raw), size=len(raw))
        self.manifest["package_version"] = self.package_version
        self.manifest["snapshot"][self.snapshot_key] = metadata
        self.manifest["qa"].update(release_ready=False, workspace_input_sha256="")
        for entries in self.manifest["roots"].values():
            entries.sort(key=lambda item: item["logical_path"])
        evidence = dict(writes_live=False, applied=apply, metadata=metadata,
                        reviewed_input_drift=[dict(root=k[0], logical_path=k[1], sha256=v)
                                              for k, v in self.reviewed_input_drift.items()],
                        changed_files=[dict(root=tier, logical_path=logical,
                                            before_sha256=digest(self.original[tier, logical])
                                            if (tier, logical) in self.original else None,
                                            after_sha256=digest(raw))
                                       for (tier, logical), raw in self.outputs.items()],
                        official_sources=[dict(root=tier, logical_path=logical, sha256=value)
                                          for (tier, logical), value in self.sources.items()])
        if apply:
            if (self.ws.package_dir / "manifest.json").read_bytes() != self.manifest_bytes:
                raise ValueError("manifest changed after plan")
            for key, raw in self.original.items():
                if self.path(*key).read_bytes() != raw:
                    raise ValueError(f"candidate changed after plan: {key}")
            for key, raw in self.outputs.items():
                path = self.path(*key)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                if path.read_bytes() != raw:
                    raise OSError("candidate write readback mismatch")
            (self.ws.package_dir / "manifest.json").write_bytes(pack.canonical_manifest_bytes(self.manifest))
            (self.ws.evidence_dir / self.evidence_name).write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        return evidence
