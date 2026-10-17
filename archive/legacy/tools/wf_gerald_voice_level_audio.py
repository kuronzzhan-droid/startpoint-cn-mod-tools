"""Measured fixed-gain voice rendering; optional bounded lookahead limiter."""
from __future__ import annotations

import math
from pathlib import Path
import re
import subprocess

import numpy as np

import wf_assets
import wf_voice_gate as gate
from wf_gerald_voice_audio import metadata, pcm

TARGET_LUFS = -14.0
PEAK_CEILING = -1.65  # Measured after MP3 decode, with margin below -1.5 dBTP.
LIMITER_CEILING = -1.2  # LAME attenuation is measured; final peak is checked again.
PRESERVE_DYNAMIC = frozenset({"home/home_2", "home/home_4", "home/home_5"})


def run(ffmpeg: Path, args: list[str]):
    result = subprocess.run([str(ffmpeg), "-hide_banner", "-nostats", *args], capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-2000:])
    return result


def measure(path: Path, ffmpeg: Path) -> dict:
    text = run(ffmpeg, ["-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "NUL"])
    summary = text.stderr.decode("utf-8", errors="replace").rsplit("Summary:", 1)[1]
    number = lambda pattern: float(re.search(pattern, summary).group(1))
    return {"lufs_i": number(r"I:\s+([-\d.]+) LUFS"),
            "true_peak_dbtp": number(r"Peak:\s+([-\d.]+) dBFS"),
            "lra_lu": number(r"LRA:\s+([-\d.]+) LU")}


def mono_filter(source: Path, ffprobe: Path) -> str:
    channels = metadata(source, ffprobe)["streams"][0]["channels"]
    if channels != 2:
        raise ValueError("source channel layout changed")
    return "pan=mono|c0=0.5*c0+0.5*c1"


def encode(source: Path, output: Path, ffmpeg: Path, ffprobe: Path,
           gain: float = 0, limiter_ceiling: float | None = None) -> dict:
    filters = mono_filter(source, ffprobe)
    if limiter_ceiling is None:
        filters += f",aresample=44100,volume={gain:.8f}dB"
    else:
        limit = 10 ** (limiter_ceiling / 20)
        filters += (f",aresample=176400,volume={gain:.8f}dB,"
                    f"alimiter=limit={limit:.12f}:attack=5:release=80:level=false:latency=true,"
                    "aresample=44100")
    output.parent.mkdir(parents=True, exist_ok=True)
    run(ffmpeg, ["-y", "-v", "error", "-i", str(source), "-map", "0:a:0",
        "-map_metadata", "-1", "-vn", "-af", filters, "-c:a", "libmp3lame",
        "-compression_level", "0", "-ar", "44100", "-ac", "1", "-b:a", "96k",
        "-minrate", "96k", "-maxrate", "96k", "-write_xing", "1", "-id3v2_version", "0", str(output)])
    return measure(output, ffmpeg)


def oversampled_peak(source: Path, ffmpeg: Path, ffprobe: Path) -> float:
    raw = run(ffmpeg, ["-v", "error", "-i", str(source), "-af", mono_filter(source, ffprobe),
                      "-ar", "176400", "-ac", "1", "-f", "f32le", "pipe:1"]).stdout
    peak = float(np.max(np.abs(np.frombuffer(raw, dtype="<f4"))))
    return 20 * math.log10(peak)


def plan(source: Path, slot: str, output: Path, ffmpeg: Path, ffprobe: Path) -> dict:
    baseline = encode(source, output, ffmpeg, ffprobe)
    peak = oversampled_peak(source, ffmpeg, ffprobe)
    desired_gain = TARGET_LUFS - baseline["lufs_i"]
    ceiling = None
    if slot in PRESERVE_DYNAMIC:
        gain = min(desired_gain, PEAK_CEILING - baseline["true_peak_dbtp"])
    elif baseline["true_peak_dbtp"] + desired_gain <= PEAK_CEILING:
        gain = desired_gain
    else:
        ceiling = LIMITER_CEILING
        gain = min(desired_gain, ceiling - peak + 2.0)
    return {"slot": slot, "baseline_encoded": baseline, "source_oversampled_peak_dbfs": peak,
            "gain_db": gain, "limiter_ceiling_dbfs": ceiling,
            "max_limiter_reduction_bound_db": 0 if ceiling is None else max(0, peak + gain - ceiling),
            "preserve_dynamic": slot in PRESERVE_DYNAMIC,
            "predicted_lufs": baseline["lufs_i"] + gain}


def render(source: Path, proposed: dict, output: Path, ffmpeg: Path, ffprobe: Path) -> tuple[bytes, dict]:
    gain, ceiling = proposed["gain_db"], proposed["limiter_ceiling_dbfs"]
    attempts = []
    for _ in range(3):
        measured = encode(source, output, ffmpeg, ffprobe, gain, ceiling)
        attempts.append({"gain_db": gain, "limiter_ceiling_dbfs": ceiling, **measured})
        if measured["true_peak_dbtp"] <= -1.6:
            break
        adjustment = PEAK_CEILING - measured["true_peak_dbtp"]
        gain += adjustment
        if ceiling is not None:
            ceiling += adjustment  # Scale ceiling too; preserve the limiter's gain envelope.
    else:
        raise ValueError("final MP3 true peak did not reach the conservative ceiling")
    reduction = (0 if ceiling is None else
                 max(0, proposed["source_oversampled_peak_dbfs"] + gain - ceiling))
    if reduction > 2.00001:
        raise ValueError("limiter attenuation exceeds the approved 2 dB bound")
    raw = output.read_bytes()
    stored = wf_assets.mp3_encode(raw)
    info = gate.probe(stored)
    errors = gate.check_container(gate.VoiceFile("unicorn_lancer_rose", proposed["slot"], stored), info)
    if errors or wf_assets.mp3_decode(stored) != raw or info["tail"] != 0:
        raise ValueError(f"voice container/roundtrip failure: {errors}")
    original, final = pcm(source, ffmpeg), pcm(output, ffmpeg)
    sample_delta = len(final) - len(original)
    if abs(sample_delta) > 64:
        raise ValueError(f"voice performance length changed: {sample_delta} samples")
    if measured["lufs_i"] < proposed["baseline_encoded"]["lufs_i"] + 2.0:
        raise ValueError("candidate failed to produce a meaningful loudness improvement")
    return stored, {**proposed, "gain_db": gain, "limiter_ceiling_dbfs": ceiling,
        "max_limiter_reduction_bound_db": reduction, "attempts": attempts, "final": measured,
        "codec": info, "decoded_seconds": len(final) / 44100, "sample_delta": sample_delta,
        "lookahead_compensated": ceiling is not None, "limiter_auto_gain": False,
        "full_decode_no_error": True, "storage_roundtrip_equal": True}
