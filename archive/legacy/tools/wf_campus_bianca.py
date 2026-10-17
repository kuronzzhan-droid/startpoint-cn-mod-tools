"""只读现有资源，装配校园碧安卡候选；不提供发布或live写入口。"""
from __future__ import annotations

from wf.paths import root_path

import argparse
import hashlib
import io
import json
import re
import zlib
from pathlib import Path

from PIL import Image

import wf_assets as assets
import wf_campus_bianca_data as data
import wf_character_pack as pack
import wf_character_requirements as requirements
import wf_character_workspace as workspace
import wf_dsl
import wf_mod_tool as core
from wf_enhancement_policy import OfficialBaseline

ROOT = Path(('${WF_ROOT}/startpoint-cn'.replace("${WF_ROOT}", str(root_path()))))
WORKSPACE = ROOT / "work/character_packs" / data.PACKAGE_ID
REPORT = ROOT / "work/codex_out/campus-trio-20260911/bianca"
PALETTE = {(133, 93, 156): (115, 40, 62), (186, 59, 76): (158, 57, 69),
           (134, 39, 39): (90, 29, 49), (160, 103, 61): (173, 126, 73),
           (69, 37, 10): (83, 52, 38)}
EFFECT_CODES = {"lady_summoner_xm20": "campus_bianca_breath",
                "lady_summoner": "campus_bianca_dragon"}


def effect_remap(value):
    for old, new in EFFECT_CODES.items():
        value = data.remap(value, old, new)
    return value


def amf_bytes(tree):
    raw = wf_dsl.encode_amf3(tree)
    if wf_dsl.parse_dsl(raw)["tree"] != tree:
        raise ValueError("AMF3 roundtrip mismatch")
    obj = zlib.compressobj(9, zlib.DEFLATED, -15)
    return obj.compress(raw) + obj.flush()


def clone_blob(blob, remap):
    try:
        text = zlib.decompress(blob).decode("utf-8")
    except (zlib.error, UnicodeDecodeError):
        inner = core.read_orderedmap_raw_rows_from_bytes(blob, "nested")
        inner.keys = [remap(k) for k in inner.keys]
        inner.rows = [clone_blob(v, remap) for v in inner.rows]
        return core.build_orderedmap_raw_rows(inner)
    rows = [[remap(v) for v in row] for row in core.read_csv_lines(text)]
    return zlib.compress(core.write_csv_lines(rows).rstrip("\n").encode("utf-8"))


class Builder:
    def __init__(self, *, apply=False):
        self.ws = workspace.load_workspace(WORKSPACE)
        if (self.ws.character_id, self.ws.code_name) != (int(data.CID), data.CODE):
            raise ValueError("wrong candidate identity")
        if self.ws.package_dir.resolve() != (WORKSPACE / "package").resolve():
            raise ValueError("package escaped assigned workspace")
        profile = json.loads((ROOT / "mod-tools/profiles.json").read_bytes())["profiles"]["cn"]
        source_store = Path(profile["store"])
        self.store = source_store if source_store.is_absolute() else ROOT / source_store
        self.baseline = OfficialBaseline(ROOT / ".cdn/cn", cache_dir=ROOT / "mod-tools/work/official-baseline", write_cache=False)
        self.apply = apply
        self.original_manifest = (self.ws.package_dir / "manifest.json").read_bytes()
        prior = json.loads(self.original_manifest)
        if apply and prior.get("snapshot", {}).get("campus_bianca", {}).get("original_portraits_pending_replacement") is False:
            raise ValueError("portraits already installed; bootstrap cannot overwrite completed art")
        self.outputs = {}
        self.claims = []
        self.provenance = []

    def emit(self, root, logical, raw):
        if pack._path_problem(logical):
            raise ValueError("invalid logical path")
        self.outputs[root, logical] = raw

    def claim(self, logical, keys, codec="flat", root="common", inner=None):
        self.claims.append(dict(root=root, logical_path=logical, codec_id=codec,
                                outer_keys=list(keys), inner_keys=inner or [],
                                semantic_claims=[]))

    def flat(self, logical, rows):
        table = core.load_table(logical, self.store)
        if any(key in table.keys for key in rows):
            raise ValueError(f"target keys occupied in live: {logical}")
        table.set_text_rows({k: core.write_csv_lines(v).rstrip("\n")
                             if not isinstance(v, str) else v for k, v in rows.items()})
        self.emit("common", logical, core.build_orderedmap(table))
        self.claim(logical, rows)

    def raw(self, logical, remap=lambda x: x):
        table = core.read_orderedmap_file_raw_rows(core.table_path(self.store, logical), logical)
        if data.CID in table.keys:
            raise ValueError(f"target raw key occupied: {logical}")
        blob = clone_blob(table.rows[table.keys.index(data.TEMPLATE_ID)], remap)
        table.keys.append(data.CID)
        table.rows.append(blob)
        self.emit("common", logical, core.build_orderedmap_raw_rows(table))
        self.claim(logical, [data.CID], "raw_outer")

    def read_rows(self, logical):
        return {k: core.read_csv_lines(v) for k, v in
                core.load_table(logical, self.store).text_rows().items()}

    def official(self, logical):
        digest = core.sha1_path(logical)
        raw = self.baseline.get("common", digest[:2] + "/" + digest[2:])
        if raw is None:
            raise ValueError(f"official donor absent: {logical}")
        self.provenance.append(dict(source=logical, source_sha256=hashlib.sha256(raw).hexdigest(),
                                    official_tail=self.baseline.official_tail))
        return raw

    def official_rows(self, logical):
        return {k: core.read_csv_lines(v) for k, v in core.read_orderedmap_file_from_bytes(self.official(logical)).items()}

    def build_tables(self):
        character = self.read_rows(core.CHARACTER_LOGICAL)[data.TEMPLATE_ID][0]
        character[0] = character[8] = data.CODE
        character[17] = data.CID
        character[18] = data.LEADER
        character[19:25] = [data.CID + str(i) for i in range(1, 7)]
        character[27] = "211002"  # 保留碧安卡官方同一人物约束，不能与她自身版本同队。
        character[26] = "Supporter"
        self.flat(core.CHARACTER_LOGICAL, {data.CID: [character]})
        self.flat("master/character/character_text.orderedmap", {data.CID: [data.text_row()]})
        self.flat("master/character/character_awake_status.orderedmap", {data.CID: "0,0"})
        for logical in ("master/character/character_status.orderedmap",
                        "master/character/character_gacha_sound.orderedmap",
                        "master/generated/character_image.orderedmap",
                        "master/character/full_shot_image_attribute.orderedmap"):
            self.raw(logical)
        old, new = str(int(data.TEMPLATE_ID) * 2), str(int(data.CID) * 2)
        def mana(value):
            return new + value[len(old):] if re.fullmatch(old + r"\d{3}", value) else value
        for logical in ("master/generated/mana_board.orderedmap", "master/mana_board/mana_node.orderedmap"):
            self.raw(logical, mana)
        for logical in ("master/mana_board/upskill.orderedmap",
                        "master/mana_board/mana_board2_open_condition.orderedmap",
                        "master/skill_preview/skill_preview_character.orderedmap",
                        "master/stance_detail/character_stance_detail.orderedmap",
                        "master/character/character_speech.orderedmap"):
            rows = self.read_rows(logical)[data.TEMPLATE_ID]
            rows = data.remap(rows, data.TEMPLATE_CODE, data.CODE)
            rows = [[data.CID if v == data.TEMPLATE_ID else v for v in row] for row in rows]
            self.flat(logical, {data.CID: rows})
        logical = "master/generated/trimmed_image.orderedmap"
        source = self.read_rows(logical)
        self.flat(logical, {f"character/{data.CODE}/ui/{stem}": source[f"character/{data.TEMPLATE_CODE}/ui/{stem}"]
                           for stem in ("full_shot_1440_1920_0", "full_shot_1440_1920_1", "skill_cutin_0", "skill_cutin_1")})
        logical = "master/ability/ability.orderedmap"
        self.flat(logical, data.ability_rows(self.official_rows(logical)))
        logical = "master/ability/leader_ability.orderedmap"
        self.flat(logical, {data.CID: data.leader_rows(self.official_rows(logical))})
        for logical, value in (("cdndata/character.json", [character]),
                               ("cdndata/character_text.json", [data.text_row()]),
                               ("character.json", dict(element=0, name=data.NAME, rarity=5, skill_count=6)),
                               ("mana_node.json", None)):
            source = json.loads((ROOT / "assets" / logical).read_bytes())
            if data.CID in source:
                raise ValueError("server target key occupied")
            if value is None:
                value = {board: {mana(key): node for key, node in nodes.items()}
                         for board, nodes in source[data.TEMPLATE_ID].items()}
            source[data.CID] = value
            self.emit("server", logical, json.dumps(source, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            self.claim(logical, [data.CID], "json_object", "server")

    def tree(self, logical):
        return wf_dsl.parse_dsl(zlib.decompress(self.official(logical), -15))["tree"]

    def build_skills(self):
        logical = "master/skill/action_skill.orderedmap"
        table = core.load_action_skill_table(self.store)
        if data.CODE in table.keys:
            raise ValueError("skill target occupied")
        official = core.read_orderedmap_raw_rows_from_bytes(self.official(logical), logical)
        entries = core.decode_action_skill_row(official.rows[official.keys.index(data.TEMPLATE_CODE)])
        for level, row in entries:
            n = int(level)
            dragon = self.tree(f"battle/action/skill/action/rare4/lady_summoner$lady_summoner_{level}.action.dsl.amf3.deflate")
            breath = self.tree(row[7] + ".action.dsl.amf3.deflate")
            clarisse = self.tree(f"battle/action/skill/action/rare5/clarisse$clarisse_{level}.action.dsl.amf3.deflate")
            ability = self.tree(f"battle/action/skill/action/rare5/crystal_swordman$crystal_swordman_{level}.action.dsl.amf3.deflate")
            fever = self.tree(f"battle/action/skill/action/rare5/illusionist_smr20$illusionist_smr20_{level}.action.dsl.amf3.deflate")
            tree = data.skill_tree(dragon, breath, clarisse, ability, fever, n)
            row[0:2] = [data.SKILL + ("＋" if n == 2 else ""), data.DESCRIPTION]
            row[4:6] = ["550", "500" if n == 2 else "550"]
            row[7] = f"battle/action/skill/action/rare5/{data.CODE}${data.CODE}_{level}"
            self.emit("common", row[7] + ".action.dsl.amf3.deflate", amf_bytes(effect_remap(tree)))
        table.keys.append(data.CODE)
        table.rows.append(core.encode_action_skill_row(entries))
        self.emit("common", logical, core.build_orderedmap_raw_rows(table))
        self.claim(logical, [data.CODE], "action_nested", inner=[dict(outer_key=data.CODE, keys=["1", "2"])])

    def copy_asset(self, logical, destination=None):
        found = assets.locate(self.store, logical)
        if not found:
            return False
        root, source = found
        root = "common" if root == "upload" else root
        raw = source.read_bytes()
        target = destination or logical
        if target != logical and logical.endswith(".amf3.deflate"):
            tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
            if logical.startswith("battle/effect/"):
                tree = effect_remap(tree)
            else:
                tree = data.remap(data.remap(tree, data.TEMPLATE_CODE, data.CODE), data.PIXEL_CODE + "/pixelart/", data.CODE + "/pixelart/")
            if "/battle/character_detail_skill_preview" in logical:
                tree["config"]["end_frame"] = 780
                # 原版角色自己的真实技能按键回放，延长观察六路小龙的时间。
            raw = amf_bytes(tree)
        if target != logical and "/pixelart/" in logical and logical.endswith(".png"):
            image = Image.open(io.BytesIO(assets.png_decode(raw))).convert("RGBA")
            recolored = Image.new("RGBA", image.size)
            recolored.putdata([(*PALETTE.get((r, g, b), (r, g, b)), a)
                               for r, g, b, a in image.get_flattened_data()])
            buf = io.BytesIO(); recolored.save(buf, format="PNG")
            raw = assets.png_encode(buf.getvalue())
            self.emit("common", target, raw)
        else:
            self.emit(root, target, raw)
        self.provenance.append(dict(source=logical, target=target, root=root,
                                   source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
        return True

    def build_assets(self):
        for requirement in requirements.char_asset_requirements(data.CODE):
            if requirement.category != "required":
                continue
            source_code = data.PIXEL_CODE if "/pixelart/" in requirement.logical_path else data.TEMPLATE_CODE
            self.copy_asset(requirement.logical_path.replace(data.CODE, source_code), requirement.logical_path)
        for item in assets.char_asset_manifest(self.store, data.TEMPLATE_CODE):
            if item["exists"] and "/voice/" in item["logical"] and any(x in item["logical"] for x in ("/ally/", "/battle/", "/home/")):
                self.copy_asset(item["logical"], item["logical"].replace(data.TEMPLATE_CODE, data.CODE))
        # 原生技能效果目录独立克隆，不能把已占用的官方文件声明成本包资产。
        prefixes = ("battle/effect/skill_unique/lady_summoner/", "battle/effect/skill_unique/lady_summoner_xm20/")
        paths = (ROOT / "mod-tools/WF_PATHLIST_recovered.txt").read_text(encoding="utf-8").splitlines()
        for source_code in EFFECT_CODES:
            for suffix in (".png", ".atlas.amf3.deflate"):
                paths.append(f"battle/effect/skill_unique/{source_code}/{source_code}{suffix}")
        for logical in sorted(set(paths)):
            if logical.startswith(prefixes):
                self.copy_asset(logical, effect_remap(logical))

    def finish(self):
        manifest = json.loads((self.ws.package_dir / "manifest.json").read_bytes())
        manifest.update(package_version="0.1.0", requires_client_base="1.4.599", tables=self.claims)
        manifest["roots"] = {root: [dict(logical_path=logical, sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))
                                    for (r, logical), raw in sorted(self.outputs.items()) if r == root]
                             for root in pack.ROOT_NAMES}
        manifest["skills"] = {"programs": [logical for root, logical in self.outputs
                                            if root == "common" and logical.endswith(".action.dsl.amf3.deflate")]}
        manifest["snapshot"]["campus_bianca"] = dict(source_versions=[211002, 111021], donor_character=111003,
            **data.snapshot(),
            original_portraits_pending_replacement=True, voice_mode="official_xm20_inherited",
            skill_preview="Bianca original input replay extended to 780 frames; no game capture")
        manifest["qa"].update(release_ready=False, workspace_input_sha256="")
        if self.apply:
            if (self.ws.package_dir / "manifest.json").read_bytes() != self.original_manifest:
                raise ValueError("candidate manifest changed during build")
            old = json.loads(self.original_manifest)
            for root, entries in old["roots"].items():
                for entry in entries:
                    target = self.ws.package_dir / "roots" / root / entry["logical_path"]
                    if not target.resolve().is_relative_to(self.ws.package_dir.resolve()):
                        raise ValueError("prior output escaped package")
                    if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != entry["sha256"]:
                        raise ValueError(f"candidate input drift: {root}:{entry['logical_path']}")
            for root, entries in old["roots"].items():
                for entry in entries:
                    key = (root, entry["logical_path"])
                    if key not in self.outputs:
                        target = self.ws.package_dir / "roots" / root / entry["logical_path"]
                        if not target.resolve().is_relative_to(self.ws.package_dir.resolve()):
                            raise ValueError("old generated output escaped package")
                        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == entry["sha256"]:
                            target.unlink()
            for (root, logical), raw in self.outputs.items():
                target = self.ws.package_dir / "roots" / root / logical
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.resolve().is_relative_to(self.ws.package_dir.resolve()):
                    raise ValueError("output escaped package")
                target.write_bytes(raw)
            (self.ws.package_dir / "manifest.json").write_bytes(pack.canonical_manifest_bytes(manifest))
            (self.ws.evidence_dir / "bianca-provenance.json").write_text(json.dumps(self.provenance, ensure_ascii=False, indent=2), encoding="utf-8")
        return dict(apply=self.apply, files=len(self.outputs), tables=len(self.claims),
                    workspace=str(WORKSPACE), writes_live=False)


def build(*, apply=False):
    builder = Builder(apply=apply)
    builder.build_tables(); builder.build_skills(); builder.build_assets()
    return builder.finish()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--revise-fever-kit", action="store_true", help="only revise candidate gameplay; preserve UI, positioning and voices")
    args = parser.parse_args()
    if args.revise_fever_kit:
        from wf_campus_bianca_revision import revise
        result = revise(apply=args.apply)
    else:
        result = build(apply=args.apply)
    print(json.dumps(result, ensure_ascii=False))
