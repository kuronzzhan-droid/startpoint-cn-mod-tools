"""赛瑞斯重做的独立候选包：保留真实双形态路由，绝不写 live。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import wf_character_requirements as requirements
import wf_seasonal7_common as C
from wf_seasonal7_specs import SeasonalSpec

CODE = "seris_dragon_king"
CID = "129999"
WORKSPACE = "work/character_packs/seris-rework-20260922/seris_dragon_king"
TEXT = "master/character/character_text.orderedmap"
IMAGE_TABLES = ("master/generated/character_image.orderedmap",
                "master/character/full_shot_image_attribute.orderedmap")
TRIMMED = "master/generated/trimmed_image.orderedmap"


def context(workspace: Path | None = None):
    spec = SeasonalSpec(
        key="seris", cid=int(CID), code=CODE, pkg_id=CODE, workspace=WORKSPACE,
        template_id=121105, template_code="ice_dragon", template_element=1,
        element=1, element_token="Water", rarity=5, pf_type=2, stance="Attacker",
        identity=int(CID), template_identity=121105, theme="苍海龙王双形态重做",
        texts={}, backdrop_colors=((44, 109, 167), (26, 40, 87)),
        required_capabilities=("seris-voice-pool-v3",),
        package_version="3.0.0", requires_client_base="1.4.1011")
    pack = C.S7Pack(spec, workspace=workspace)
    pack.check_identity()
    return pack


def _seed_raw(pack, logical, keys, *, codec="raw_outer", inner=None):
    raw = C.core.read_orderedmap_raw_rows_from_bytes(pack.live_read(logical), logical)
    rows = dict(zip(raw.keys, raw.rows))
    missing = set(keys) - rows.keys()
    if missing:
        raise ValueError(f"live seed missing {logical}: {sorted(missing)}")
    pack.write_raw_outer(logical, {k: rows[k] for k in keys}, only_missing=True,
                         codec=codec, inner=inner)


def seed(pack):
    """只补候选缺件；已完成的画稿、音频、像素和机制不会被旧 live 覆盖。"""
    sources = []
    for item in requirements.char_asset_requirements(CODE):
        if item.category != "required":
            continue
        found = pack.live_locate(item.logical_path)
        if not found:
            raise FileNotFoundError(item.logical_path)
        root, path = found
        raw = path.read_bytes()
        pack.write_asset(root, item.logical_path, raw, owner="seed", only_missing=True)
        sources.append(dict(root=root, logical_path=item.logical_path, sha256=C.sha256(raw)))
    for logical in (C.core.CHARACTER_LOGICAL, TEXT):
        pack.write_flat(logical, {CID: pack.live_flat(logical)[CID]}, only_missing=True)
    _seed_raw(pack, C.core.STATUS_LOGICAL, [CID])
    char = pack.pkg_character_row()
    if char[9:12] != ["1", "28", "22"] or char[14] != CODE:
        raise ValueError("Seris live dual-form identity/Unique22 route changed; inspect before seeding")
    for logical in (C.core.ACTION_SKILL_LOGICAL, C.core.SWITCHED_ACTION_SKILL_LOGICAL):
        nested = C.core.load_nested_table_bytes(pack.live_read(logical), logical)
        rows = nested.rows[CODE].text_rows()
        pack.write_nested(logical, CODE, rows, only_missing=True)
        for value in rows.values():
            for row in C.csv_split(value):
                for cell in row:
                    if cell.startswith("battle/action/") and pack.live_path(C.wf_dsl.dsl_logical(cell)):
                        path = C.wf_dsl.dsl_logical(cell)
                        pack.write_asset("common", path, pack.live_read(path), owner="seed", only_missing=True)
    for logical in IMAGE_TABLES:
        _seed_raw(pack, logical, [CID])
    trimmed = {k: v for k, v in pack.live_flat(TRIMMED).items() if f"character/{CODE}/" in k}
    pack.write_flat(TRIMMED, trimmed, only_missing=True)
    pack.sync_character_mirrors()
    report = dict(status="media_candidate_mechanics_pending", writes_live=False,
                  summary="独立129999候选；保留Unique22真龙切换；旧立绘/像素仅作派生前基线",
                  source_assets=sources, required=len(sources),
                  runtime_verified=False, accepted_by_user=False)
    pack.write_evidence("assets-report.json", report)
    return report


def install_voice(pack, plan: Path, standard: Path):
    """仅替换26个音频与8条字幕，严禁通用voice_ready克隆覆盖真龙技能。"""
    import wf_seasonal7_voice as V
    import wf_voice_gate as gate
    data = json.loads(Path(plan).read_text(encoding="utf-8"))
    lines = data if isinstance(data, list) else data["roles"]["seris"] if "roles" in data else data["lines"]
    by_slot = {line["slot"]: line for line in lines}
    slots = (*V.SLOTS, *(f"battle/matched_skill_{i}" for i in range(4)))
    if set(slots) != set(by_slot) or len(lines) != 26:
        raise ValueError("Seris voice plan must contain exactly the 26 native slots")
    rules = pack.live_flat("master/string/ui_string.orderedmap").get("character_voice_exclude")
    if rules is None or any(V.native_excluded(f"character/{CODE}/voice/{s}", rules) for s in slots):
        raise ValueError("native voice exclusion rules are missing or block Seris")
    route_before = pack.pkg_character_row()[9:16]
    switched_before = pack.pkg_path("common", C.core.SWITCHED_ACTION_SKILL_LOGICAL).read_bytes()
    voices, files = [], []
    for slot in slots:
        source = Path(standard) / (slot + ".mp3")
        raw = source.read_bytes()
        stored = C.wf_assets.mp3_encode(raw)
        if C.wf_assets.mp3_decode(stored) != raw:
            raise ValueError(f"MP3 storage roundtrip failed: {slot}")
        voices.append(gate.VoiceFile(CODE, slot, stored))
        files.append(dict(slot=slot, source_sha256=C.sha256(raw), sha256=C.sha256(stored)))
    findings = [vars(f) for f in gate.check_voice_set(voices)]
    errors = [f for f in findings if f["level"] == "error"]
    if errors:
        raise ValueError(f"voice validation failed: {errors}")
    for voice in voices:
        pack.write_asset("common", f"character/{CODE}/voice/{voice.slot}.mp3", voice.data, owner="voice")
    pack.write_flat(V.SPEECH_TABLE, {CID: V.speech_rows(lines)})
    if (pack.pkg_character_row()[9:16] != route_before or
            pack.pkg_path("common", C.core.SWITCHED_ACTION_SKILL_LOGICAL).read_bytes() != switched_before):
        raise AssertionError("voice installation changed the real dragon skill route")
    report = dict(status="candidate", summary="26条原生目录音频及8条字幕；真实变身技能路由未改",
                  mode="Seed Audio 2 + two-pass loudnorm", files=files, findings=findings,
                  native_route_preserved=route_before, runtime_voice_selection_verified=False)
    pack.write_evidence("voice-report.json", report)
    return report


def sync_dual_form_art(pack):
    """旧双形态客户端还请求dragon别名，必须指向本次真龙图，不能留旧图。"""
    files = []
    for root, slot, suffix in (("medium", "skill_cutin", ".png"),
                               ("android", "skill_cutin", ".atf.deflate"),
                               ("medium", "battle_control_board", ".png"),
                               ("medium", "battle_member_status", ".png")):
        prefix = f"character/{CODE}/ui/{slot}"
        raw = pack.pkg_path(root, prefix + "_1" + suffix).read_bytes()
        logical = prefix + "_dragon" + suffix
        pack.write_asset(root, logical, raw, owner="art")
        files.append(dict(root=root, logical_path=logical, sha256=C.sha256(raw)))
    report = dict(status="candidate", files=files, source="本次觉醒后真龙立绘派生")
    pack.write_evidence("art/dual-form-aliases.json", report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("step", choices=("seed", "voice", "art-aliases", "manifest"))
    p.add_argument("--workspace", type=Path)
    p.add_argument("--plan", type=Path)
    p.add_argument("--standard", type=Path)
    a = p.parse_args()
    pack = context(a.workspace)
    if a.step == "seed":
        result = seed(pack)
    elif a.step == "art-aliases":
        result = sync_dual_form_art(pack)
    elif a.step == "voice":
        if not a.plan or not a.standard:
            p.error("voice requires --plan and --standard")
        result = install_voice(pack, a.plan, a.standard)
    else:
        import wf_seasonal7_manifest
        manifest_path = pack.package / "manifest.json"
        prior = json.loads(manifest_path.read_text(encoding="utf-8"))
        prior.setdefault("snapshot", {})["seris_rework"] = dict(
            status="media_candidate_mechanics_pending", core_role_confirmed=False,
            mechanics_rewritten=False, art_accepted_by_user=False, runtime_verified=False,
            effects=pack.read_evidence("effects-report.json", {}).get("summary"),
            client_patch_capability="seris-voice-pool-v3", client_patch_installed=False)
        manifest_path.write_text(C.json_dump(prior), encoding="utf-8")
        result = wf_seasonal7_manifest.build(pack)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
