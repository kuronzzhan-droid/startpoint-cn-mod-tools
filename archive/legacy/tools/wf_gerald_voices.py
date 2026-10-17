"""Build Gerald's supplied 19-recording candidate in an isolated package clone."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import re
import shutil
import zlib

import wf_assets
import wf_mod_tool as core
import wf_voice
import wf_voice_gate as gate
from wf_gerald_voice_audio import convert, sha

CODE = "unicorn_lancer_rose"
CID = "129992"
SPEECH = "master/character/character_speech.orderedmap"
BATTLE = tuple(f"battle/{prefix}_{number}" for prefix in
    ("battle_start", "outhole", "power_flip", "skill", "win") for number in (0, 1)) + ("battle/skill_ready",)
EXPECTED = {"ally/join", "ally/evolution", *BATTLE, *(f"home/home_{i}" for i in range(6))}


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def mapping(source: Path) -> dict[str, Path]:
    result = {}
    for path in source.rglob("*"):
        if not path.is_file() or path.suffix.lower() != ".mp3":
            continue
        relative = path.relative_to(source)
        if len(relative.parts) != 2:
            raise ValueError(f"Unexpected recording path: {relative}")
        slot = relative.with_suffix("").as_posix()
        home = re.fullmatch(r"home/home语音([1-6])", slot)
        if home:
            slot = f"home/home_{int(home.group(1)) - 1}"
        if slot not in EXPECTED or slot in result:
            raise ValueError(f"Unknown or duplicate voice slot: {slot}")
        result[slot] = path
    if set(result) != EXPECTED:
        raise ValueError(f"Missing supplied voice slots: {sorted(EXPECTED - set(result))}")
    return result


def subtitles(source: Path) -> tuple[dict[str, str], dict]:
    text_root = source / "语音文本"
    home = (text_root / "home语音1-6.txt").read_text(encoding="utf-8-sig")
    ally = (text_root / "加入和觉醒台词.txt").read_text(encoding="utf-8-sig")
    battle = (text_root / "战斗台词.txt").read_text(encoding="utf-8-sig")
    texts = re.findall(r"^中文[：:]\s*(.+)$", home, re.MULTILINE)
    if len(texts) != 6 or [home.count(c) for c in "①②③④⑤⑥"] != [1] * 6:
        raise ValueError("Home transcript must have exactly six numbered Chinese lines")
    result = {f"home/home_{i}": line.strip() for i, line in enumerate(texts)}
    for slot, label in (("ally/join", "加入时"), ("ally/evolution", "觉醒时")):
        matches = re.findall(re.escape(label) + r"[：:]\s*\n([^\r\n]+)", ally)
        if len(matches) != 1:
            raise ValueError(f"Missing or ambiguous transcript: {label}")
        result[slot] = matches[0].strip()
    battle_lines = {"battle/" + name: text.strip() for name, text in
                    re.findall(r"^(\w+)[：:]([^\r\n]+)", battle, re.MULTILINE)}
    if set(battle_lines) != set(BATTLE):
        raise ValueError("Battle transcript filenames do not match the 11 provided slots")
    # CharacterSpeechValues supports Home/Evolution/Join only; battle subtitles
    # remain documented mappings rather than invented runtime speech kinds.
    return result, {"battle_transcripts": battle_lines, "transcript_sources": [
        {"source": str(path), "sha256": sha(path.read_bytes())} for path in sorted(text_root.glob("*.txt"))]}


def clone(default: Path, workspace: Path, output: Path) -> dict:
    default, workspace = default.resolve(), workspace.resolve()
    if (workspace.parent.name != "gerald-voice-20260906" or workspace.name != CODE
            or default == workspace):
        raise ValueError("Only the isolated Gerald voice workspace may be changed")
    manifest_path = default / "package/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest["package_id"], str(manifest["character_id"]), manifest["package_version"]) != (CODE, CID, "0.1.7"):
        raise ValueError("Unreviewed default character package baseline")
    baseline_file = output / "baseline.json"
    if workspace.exists():
        baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
        if baseline["default_manifest_sha256"] != sha(manifest_path.read_bytes()):
            raise ValueError("Default package drifted after cloning")
        return baseline
    baseline = {"default_workspace": str(default), "candidate_workspace": str(workspace),
        "package_version": manifest["package_version"], "published_version": "1.4.773",
        "default_manifest_sha256": sha(manifest_path.read_bytes()),
        "workspace_sha256": sha((default / "workspace.json").read_bytes()),
        "root_files": {str(p.relative_to(default / "package/roots").as_posix()): sha(p.read_bytes())
                       for p in (default / "package/roots").rglob("*") if p.is_file()}}
    workspace.mkdir(parents=True)
    shutil.copytree(default / "package", workspace / "package")
    shutil.copy2(default / "workspace.json", workspace / "workspace.json")
    write_json(baseline_file, baseline)
    return baseline


def build(source: Path, default: Path, workspace: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    mapped = mapping(source)
    subtitles_by_slot, text_report = subtitles(source)
    output.mkdir(parents=True, exist_ok=True)
    baseline = clone(default, workspace, output)
    package = workspace / "package"
    ffmpeg = wf_voice.find_ffmpeg()
    if ffmpeg is None or not ffmpeg.with_name("ffprobe.exe").exists():
        raise ValueError("An existing FFmpeg and matching ffprobe are required")
    ffprobe = ffmpeg.with_name("ffprobe.exe")
    source_hashes = {str(p): sha(p.read_bytes()) for p in mapped.values()}
    entries, records, voice_files = [], [], []
    report = {"character_id": int(CID), "code_name": CODE, "sources_read_only": True,
              "ffmpeg": str(ffmpeg), "mapping": [], **text_report}
    for slot, path in sorted(mapped.items()):
        logical = f"character/{CODE}/voice/{slot}.mp3"
        target = package / "roots/common" / logical
        converted = output / "standard-mp3" / (slot + ".mp3")
        stored, audio_report = convert(path, converted, ffmpeg, ffprobe)
        key = "common/" + logical
        previous = target.read_bytes() if target.exists() else None
        target.parent.mkdir(parents=True, exist_ok=True)
        if previous != stored:
            temporary = target.with_suffix(".tmp")
            temporary.write_bytes(stored)
            temporary.replace(target)
        if wf_assets.mp3_decode(target.read_bytes()) != converted.read_bytes():
            raise ValueError("Stored audio readback mismatch")
        entries.append({"root": "common", "logical_path": logical,
            "old_sha256": baseline["root_files"].get(key), "new_sha256": sha(stored), "size": len(stored)})
        report["mapping"].append({"source": str(path), "source_sha256": source_hashes[str(path)],
                                  "slot": slot, "logical_path": logical})
        records.append({"slot": slot, **audio_report})
        voice_files.append(gate.VoiceFile(CODE, slot, stored))
    speech_path = package / "roots/common" / SPEECH
    raw_map = core.read_orderedmap_file_raw_rows(speech_path, SPEECH)
    before_keys, before_rows = list(raw_map.keys), list(raw_map.rows)
    index = raw_map.keys.index(CID)
    rows = core.read_csv_lines(zlib.decompress(raw_map.rows[index]).decode("utf-8"))
    if len(rows) != 8 or {row[4] for row in rows} != set(subtitles_by_slot):
        raise ValueError("Unexpected Gerald speech row layout")
    for row in rows:
        row[3] = subtitles_by_slot[row[4]]
    text = core.write_csv_lines(rows).rstrip("\n")
    raw_map.rows[index] = zlib.compress(text.encode("utf-8"))
    speech_path.write_bytes(core.build_orderedmap_raw_rows(raw_map))
    back = core.read_orderedmap_file_raw_rows(speech_path, SPEECH)
    if back.keys != before_keys or any(a != b for i, (a, b) in enumerate(zip(before_rows, back.rows)) if i != index):
        raise ValueError("Unrelated speech rows changed")
    if core.read_csv_lines(zlib.decompress(back.rows[index]).decode("utf-8")) != rows:
        raise ValueError("Speech subtitle CSV readback mismatch")
    entries.append({"root": "common", "logical_path": SPEECH,
        "old_sha256": baseline["root_files"]["common/" + SPEECH],
        "new_sha256": sha(speech_path.read_bytes()), "size": speech_path.stat().st_size})
    findings = [asdict(f) for f in gate.check_voice_set(voice_files)]
    structural_errors = [f for f in findings if f["level"] == "error" and f["rule"] != "over_official_max"]
    if structural_errors:
        raise ValueError(f"Voice encoding or mapping errors: {structural_errors}")
    reachability = gate.engine_reachable(list(mapped))
    if any(reachability.values()):
        raise ValueError("Some battle recordings cannot be reached")
    if any(sha(Path(p).read_bytes()) != digest for p, digest in source_hashes.items()):
        raise ValueError("A supplied recording changed during the build")
    if sha((default / "package/manifest.json").read_bytes()) != baseline["default_manifest_sha256"]:
        raise ValueError("Default package changed during candidate assembly")
    if sha((package / "manifest.json").read_bytes()) != baseline["default_manifest_sha256"]:
        raise ValueError("Candidate manifest must remain root-owned and unchanged")
    report.update({"audio": records, "speech_rows": rows, "findings": findings,
        "reachability": reachability, "structural_errors": structural_errors,
        "unrelated_speech_raw_rows_equal": True, "all_19_sources_unchanged": True,
        "missing_required_slots": [], "not_supplied_or_fabricated": ["story", "words", "matched_skill", "exchange_power_flip"],
        "performance_duration_preserved": True, "manifest_unchanged": True})
    write_json(output / "voice-report.json", report)
    write_json(output / "changed-files.json", {"files": entries,
        "claims": [{"root": "common", "logical_path": SPEECH, "keys": [CID], "already_declared": True}],
        "required_capabilities_added": [], "new_external_table_keys": []})
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "default", "workspace", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    result = build(args.source, args.default, args.workspace, args.output)
    print(json.dumps({"voices": len(result["audio"]), "speech_rows": len(result["speech_rows"]),
        "structural_errors": result["structural_errors"], "duration_findings": len(result["findings"]),
        "manifest_unchanged": result["manifest_unchanged"]}))


if __name__ == "__main__":
    main()
