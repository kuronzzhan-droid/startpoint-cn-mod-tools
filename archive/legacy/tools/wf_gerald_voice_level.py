"""Isolated Gerald loudness candidate; only nineteen voice files may change."""
from __future__ import annotations

from wf.paths import root_path

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from wf_gerald_voice_level_audio import plan, render

BASE = Path(('${WF_ROOT}/startpoint-cn'.replace("${WF_ROOT}", str(root_path()))))
DEFAULT = BASE / "work/character_packs/unicorn_lancer_rose"
WORKSPACE = BASE / "work/character_packs/gerald-voice-level-20260906/unicorn_lancer_rose"
OUTPUT = BASE / "work/codex_out/gerald-voice-level-20260906"
SOURCE_REPORT = BASE / "work/codex_out/gerald-voice-20260906/voice-report.json"
FFMPEG = Path("C:/ProgramData/HP/LCDDisplayHelper/bin/ffmpeg.exe")
FFPROBE = FFMPEG.with_name("ffprobe.exe")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def snapshot(path: Path) -> dict:
    return {p.relative_to(path).as_posix(): sha(p.read_bytes())
            for p in path.rglob("*") if p.is_file()}


def atomic(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(raw)
    try:
        os.replace(temporary, path)
        if path.read_bytes() != raw:
            raise OSError("file readback failed")
    finally:
        temporary.unlink(missing_ok=True)


def record(name: str, value) -> None:
    atomic(OUTPUT / name, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def prepare() -> tuple[dict, list]:
    mapping = json.loads(SOURCE_REPORT.read_bytes())["mapping"]
    if len(mapping) != 19 or len({x["logical_path"] for x in mapping}) != 19:
        raise ValueError("expected exactly nineteen unique voice recordings")
    for item in mapping:
        if sha(Path(item["source"]).read_bytes()) != item["source_sha256"]:
            raise ValueError("original voice source drifted")
        if not item["logical_path"].startswith("character/unicorn_lancer_rose/voice/"):
            raise ValueError("voice logical path escaped Gerald")
    current = snapshot(DEFAULT / "package")
    workspace_hash = sha((DEFAULT / "workspace.json").read_bytes())
    baseline_path = OUTPUT / "baseline.json"
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_bytes())
        if current != baseline["default_files"] or workspace_hash != baseline["workspace_sha256"]:
            raise ValueError("default package or workspace changed since baseline")
    else:
        identity = json.loads((DEFAULT / "package/manifest.json").read_bytes())
        if (identity.get("character_id"), identity.get("package_version")) != (129992, "0.1.8"):
            raise ValueError("expected Gerald default 775 / package 0.1.8")
        if WORKSPACE.exists():
            raise ValueError("candidate directory exists without this tool's baseline")
        WORKSPACE.mkdir(parents=True)
        shutil.copytree(DEFAULT / "package", WORKSPACE / "package")
        shutil.copyfile(DEFAULT / "workspace.json", WORKSPACE / "workspace.json")
        baseline = {"workspace": str(WORKSPACE), "default_files": current,
                    "workspace_sha256": workspace_hash, "sources": mapping,
                    "package_version": "0.1.8", "baseline_release": "1.4.775"}
        record("baseline.json", baseline)
    if not (WORKSPACE / "package/manifest.json").is_file():
        raise ValueError("candidate clone missing")
    return baseline, mapping


def run(*, apply: bool = False) -> dict:
    baseline, mapping = prepare()
    before = snapshot(WORKSPACE / "package")
    voices = {"roots/common/" + x["logical_path"] for x in mapping}
    if (set(before) != set(baseline["default_files"]) or
        any(digest != baseline["default_files"][path]
            for path, digest in before.items() if path not in voices)):
        raise ValueError("candidate non-audio files changed; refuse before rendering or writing")
    def first_pass(item):
        source = Path(item["source"])
        output = OUTPUT / "measurement-pass" / (item["slot"].replace("/", "_") + ".mp3")
        return plan(source, item["slot"], output, FFMPEG, FFPROBE)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        plans = list(pool.map(first_pass, mapping))
    record("plans.json", plans)
    report = {"applied": apply, "manifest_updated": False, "sources_unchanged": True,
              "default_unchanged": True, "voice_count": 19, "plans": plans}
    if not apply:
        if snapshot(WORKSPACE / "package") != baseline["default_files"]:
            raise ValueError("dry-run candidate is no longer an unchanged baseline")
        record("dry-run.json", report)
        return report
    def second_pass(pair):
        item, proposed = pair
        output = OUTPUT / "standard-mp3" / (item["slot"] + ".mp3")
        raw, measured = render(Path(item["source"]), proposed, output, FFMPEG, FFPROBE)
        return item, raw, measured
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        prepared = list(pool.map(second_pass, zip(mapping, plans)))
    changed, measurements = [], []
    package = WORKSPACE / "package"
    for item, raw, measured in prepared:
        relative = "roots/common/" + item["logical_path"]
        path = (package / relative).resolve(strict=True)
        if not path.is_relative_to(package.resolve()):
            raise ValueError("candidate voice path escaped the clone")
        atomic(path, raw)
        changed.append({"root": "common", "logical_path": item["logical_path"],
                        "old_sha256": baseline["default_files"][relative],
                        "new_sha256": sha(raw), "size": len(raw)})
        measurements.append(measured)
    after = snapshot(package)
    changed_paths = {k for k, digest in after.items() if baseline["default_files"].get(k) != digest}
    expected = {"roots/common/" + x["logical_path"] for x in mapping}
    if set(after) != set(baseline["default_files"]) or changed_paths != expected:
        raise ValueError("candidate differs outside exactly nineteen voice files")
    if snapshot(DEFAULT / "package") != baseline["default_files"]:
        raise ValueError("default package changed during candidate rendering")
    if sha((WORKSPACE / "workspace.json").read_bytes()) != baseline["workspace_sha256"]:
        raise ValueError("candidate workspace metadata changed")
    for item in mapping:
        if sha(Path(item["source"]).read_bytes()) != item["source_sha256"]:
            raise ValueError("original voice source changed during candidate rendering")
    report.update({"files": changed, "measurements": measurements,
                   "only_nineteen_audio_changed": True, "runtime_verified": False,
                   "min_final_lufs": min(x["final"]["lufs_i"] for x in measurements),
                   "max_final_lufs": max(x["final"]["lufs_i"] for x in measurements),
                   "max_true_peak_dbtp": max(x["final"]["true_peak_dbtp"] for x in measurements)})
    record("changed-files.json", changed)
    record("candidate-report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    result = run(apply=parser.parse_args().apply)
    print(json.dumps({k: v for k, v in result.items() if k not in {"plans", "measurements", "files"}}, indent=2))
