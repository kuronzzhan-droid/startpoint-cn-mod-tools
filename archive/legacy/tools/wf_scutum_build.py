"""盾牌座完整离线候选装配；生产发布仍由 wf_character_flow 负责。"""
import argparse
import json
from pathlib import Path

import wf_character_pack as pack
import wf_scutum_abilities as abilities
import wf_scutum_action_table as action_table
import wf_scutum_art as art
import wf_scutum_effects as effects
import wf_scutum_icon as icon
import wf_scutum_identity as identity
import wf_scutum_pixels as pixels
import wf_scutum_skill as skill
import wf_scutum_skill_actions as actions
import wf_scutum_template_assets as templates
import wf_scutum_voice as voice
from wf_scutum_seed import Seed


def build(repo, workspace, source_dir, icon_source, output, *, pixel_source, apply=False):
    seed = Seed(repo, workspace)
    output = Path(output).resolve()
    if not output.is_relative_to(seed.repo / "work/codex_out"):
        raise ValueError("evidence output escaped ignored workspace")
    seed.begin()
    metadata = identity.build(seed)
    template_info = templates.build(seed)
    metadata["abilities"] = abilities.install(seed)
    if metadata["abilities"].get("requires_collect_hit_resolution", True):
        raise ValueError("collect hit behavior is unresolved; refusing complete assembly")
    metadata["action_table"] = action_table.install(seed)
    for key, raw in {**skill.assets(seed.official), **actions.assets()}.items():
        seed.emit(*key, raw)
    metadata["skill"] = skill.metadata()
    metadata["skill_actions"] = actions.metadata()
    metadata["effects"] = effects.build(seed)
    metadata["art"] = art.build(seed, source_dir, output / "art")
    metadata["pixels"] = pixels.build(seed, pixel_source, output / "pixel")
    metadata["voices"] = voice.build(seed, source_dir, output / "voice")
    metadata["collect_icon"] = icon.build(seed, icon_source, output / "icon")
    metadata["unique_condition"] = dict(ids=[abilities.COLLECT_UID], icons=[icon.LOGICAL])
    metadata["required_capabilities"] = []
    metadata["presentation_pending"] = False
    metadata["pixel_pending"] = False
    metadata["template_effect_source"] = template_info["effect_source"]
    result = seed.finish(metadata, apply=apply)
    if apply:
        manifest = pack.load_manifest(seed.ws.package_dir / "manifest.json")
        problems = pack.validate_manifest(manifest, seed.ws.package_dir, require_referenced_assets=True)
        if problems:
            raise ValueError(problems)
    output.mkdir(parents=True, exist_ok=True)
    (output / ("assembled.json" if apply else "plan.json")).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("repo", "workspace", "source-dir", "icon-source", "pixel-source", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = build(args.repo, args.workspace, args.source_dir, args.icon_source, args.output,
                   pixel_source=args.pixel_source, apply=args.apply)
    print(json.dumps(dict(applied=result["applied"], files=result["files"], writes_live=False)))
