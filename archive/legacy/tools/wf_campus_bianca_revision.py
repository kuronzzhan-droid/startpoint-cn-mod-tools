"""仅修订碧安卡候选玩法；保留每个非自有行和所有 UI/语音/定位文件。"""
from __future__ import annotations

import hashlib
import json
import zlib

import wf_campus_bianca as B
import wf_campus_bianca_data as D
import wf_character_pack as pack
import wf_describe
import wf_mod_tool as core


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Revision:
    def __init__(self):
        self.builder = B.Builder(apply=False)
        self.ws = self.builder.ws
        self.original = self.builder.original_manifest
        self.manifest = json.loads(self.original)
        self.inputs, self.outputs = {}, {}
        self.index = {(root, entry["logical_path"]): entry
                      for root, entries in self.manifest["roots"].items() for entry in entries}

    def path(self, root, logical):
        if (root, logical) not in self.index or pack._path_problem(logical):
            raise ValueError(f"unclaimed revision file: {root}:{logical}")
        path = self.ws.package_dir / "roots" / root / logical
        if not path.resolve().is_relative_to((self.ws.package_dir / "roots" / root).resolve()):
            raise ValueError("revision escaped candidate root")
        for component in (path, *path.parents):
            if component.is_symlink() or getattr(component, "is_junction", lambda: False)():
                raise ValueError("revision path contains reparse component")
        return path

    def read(self, root, logical):
        raw = self.path(root, logical).read_bytes()
        if sha(raw) != self.index[root, logical]["sha256"]:
            raise ValueError(f"candidate drift: {root}:{logical}")
        self.inputs[root, logical] = raw
        return raw

    def splice(self, logical, replacements, *, compressed=True):
        table = core.read_orderedmap_raw_rows_from_bytes(self.read("common", logical), logical)
        if not set(replacements).issubset(table.keys):
            raise ValueError("revision cannot add candidate identities")
        claim = next(c for c in self.manifest["tables"] if c["root"] == "common" and c["logical_path"] == logical)
        if set(replacements) != set(claim["outer_keys"]):
            raise ValueError("revision must replace exactly the owned table keys")
        before = dict(zip(table.keys, table.rows))
        for key, value in replacements.items():
            raw = zlib.compress(core.write_csv_lines(value).rstrip("\n").encode("utf-8")) if compressed else value
            table.rows[table.keys.index(key)] = raw
        for key, raw in zip(table.keys, table.rows):
            if key not in replacements and before[key] != raw:
                raise ValueError("unowned table row changed")
        self.outputs["common", logical] = core.build_orderedmap_raw_rows(table)

    def plan(self):
        ability = D.ability_rows(self.builder.official_rows("master/ability/ability.orderedmap"))
        leader = D.leader_rows(self.builder.official_rows("master/ability/leader_ability.orderedmap"))
        self.splice("master/ability/ability.orderedmap", ability)
        self.splice("master/ability/leader_ability.orderedmap", {D.CID: leader})
        self.splice("master/character/character_text.orderedmap", {D.CID: [D.text_row()]})
        self.builder.build_skills()
        logical = "master/skill/action_skill.orderedmap"
        table = core.read_orderedmap_raw_rows_from_bytes(self.builder.outputs["common", logical], logical)
        self.splice(logical, {D.CODE: table.rows[table.keys.index(D.CODE)]}, compressed=False)
        for key, raw in self.builder.outputs.items():
            if key[1].endswith(".action.dsl.amf3.deflate"):
                self.read(*key)
                self.outputs[key] = raw
        key = ("server", "cdndata/character_text.json")
        server = json.loads(self.read(*key))
        server[D.CID] = [D.text_row()]
        self.outputs[key] = json.dumps(server, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        for key, raw in self.outputs.items():
            self.index[key].update(sha256=sha(raw), size=len(raw))
        snapshot = self.manifest["snapshot"]["campus_bianca"]
        snapshot.update(D.snapshot(), gameplay_revision="fire-fever-ability-20260911",
                        donor_characters=[111003, 131013, 131020, 151001, 151009, 151045, 151027],
                        ability_condition_donor="crystal_swordman")
        self.manifest["qa"].update(release_ready=False, workspace_input_sha256="")
        self.panels = ["队长：" + wf_describe.describe_line(r, "leader_ability") for r in leader]
        for key, rows in ability.items():
            self.panels.extend(f"能力{key[-1]}：" + wf_describe.describe_line(r, "ability") for r in rows)
        self.panels.insert(0, D.DESCRIPTION)
        return self

    def apply(self):
        if (self.ws.package_dir / "manifest.json").read_bytes() != self.original:
            raise ValueError("manifest changed after revision planning")
        # 所有未修改资产也检查声明 hash，拒绝在并发 UI/语音写入中封存清单。
        prior = json.loads(self.original)
        for root, entries in prior["roots"].items():
            for entry in entries:
                if sha(self.path(root, entry["logical_path"]).read_bytes()) != entry["sha256"]:
                    raise ValueError(f"candidate changed after planning: {root}:{entry['logical_path']}")
        for key, raw in self.outputs.items():
            if self.path(*key).read_bytes() != self.inputs[key]:
                raise ValueError("revision target drift")
            self.path(*key).write_bytes(raw)
            if self.path(*key).read_bytes() != raw:
                raise OSError("revision readback mismatch")
        (self.ws.package_dir / "manifest.json").write_bytes(pack.canonical_manifest_bytes(self.manifest))
        evidence = dict(writes_live=False, files=[dict(root=r, logical_path=p,
                        before_sha256=sha(self.inputs[r, p]), after_sha256=sha(raw))
                        for (r, p), raw in self.outputs.items()], snapshot=D.snapshot(),
                        official_sources=self.builder.provenance)
        (self.ws.evidence_dir / "bianca-fever-revision.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        (self.ws.evidence_dir / "bianca-fever-kit-panel.txt").write_text("\n".join(self.panels) + "\n", encoding="utf-8")


def revise(*, apply=False):
    revision = Revision().plan()
    if apply:
        revision.apply()
    return dict(apply=apply, files=len(revision.outputs), writes_live=False,
                workspace=str(B.WORKSPACE), panels=revision.panels)
