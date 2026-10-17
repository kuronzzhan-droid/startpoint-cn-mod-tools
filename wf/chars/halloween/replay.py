"""Rebuild all four Halloween packages from source tables, art and approved WAVs.

No TTS/image generation, services, device access, or deployment is invoked.
The recipe explicitly selects the verified pre-222 Seriol formula for 221.
Ordinary kit construction keeps the later fix; expected ZIPs are never inputs.
"""
from __future__ import annotations
import importlib
import json
import os
import shutil
from wf.paths import path, REPOSITORY
from wf.view.safety import restrict_writes


def build_kit(key, pack, build_api):
    context = build_api.KitContext(pack)
    context.historical_version = "1.4.221"
    return importlib.import_module("wf.chars.halloween.kit_" + key).build(context)


def main():
    observed_reads = restrict_writes()
    from wf.chars.halloween import env
    os.environ["WF_TARGET_STORE"] = str(env.STORE)
    from wf.chars.halloween import common, art, pixel, voice
    from wf.chars.support import build, tables, assets
    env.ROOT.mkdir(parents=True, exist_ok=True)
    env.TEMP.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = os.environ["TMP"] = str(env.TEMP)
    # The original package root has this identical path enumeration input.
    target = env.ROOT / "mod-tools/WF_PATHLIST_recovered.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(env.INPUT / "pkgroot/mod-tools/WF_PATHLIST_recovered.txt", target)
    report_file = env.RUN_ROOT / "build-report.json"
    report = json.loads(report_file.read_text("utf-8")) if report_file.exists() else {}
    if report and report.get("historical_version") != "1.4.221":
        raise ValueError("run directory belongs to a different recipe mode; choose a fresh WF_REPLAY_RUN")
    report["historical_version"] = "1.4.221"
    for key in ("ludi", "momiya", "seriol", "recital"):
        pack = common.pack_for(key)
        steps = report.setdefault(key, {})
        for name, run in [
            ("init", lambda: build.step_init(pack)),
            ("tables", lambda: tables.build(pack)),
            ("kit", lambda: build_kit(key, pack, build)),
            ("assets", lambda: assets.build(pack)),
            ("pixel", lambda: pixel.build(pack)),
            ("art", lambda: art.build(key)),
            ("voice", lambda: voice.install(key)),
        ]:
            if name in steps and not (isinstance(steps[name], dict) and "error" in steps[name]):
                print(key, name, "already completed in this run", flush=True)
                continue
            print(key, name, flush=True)
            try:
                steps[name] = run()
                report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), "utf-8")
            except Exception as exc:
                steps[name] = {"error": type(exc).__name__ + ": " + str(exc)}
                (env.RUN_ROOT / "build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), "utf-8")
                raise
        (env.RUN_ROOT / "build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), "utf-8")
    from wf.view.recipe_inputs import verify_halloween_view, local_api_origins
    verification = verify_halloween_view(observed_reads)
    if verification["verified_read_members"] or "view_verification" not in report:
        report["view_verification"] = verification
    report["api_origins"] = local_api_origins()
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), "utf-8")
    from wf.view import character_pack
    character_pack.hw_env.ROOT = env.ROOT
    character_pack.main(["1.4.220", "1.4.221", "--out", str(env.RUN_ROOT / "delivery")])

if __name__ == "__main__":
    main()
