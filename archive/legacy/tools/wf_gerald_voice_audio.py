"""Local codec/continuity checks for Gerald's supplied voice recordings."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np

import wf_assets
import wf_voice_gate as gate


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def metadata(path: Path, ffprobe: Path) -> dict:
    result = subprocess.run([str(ffprobe), "-v", "error", "-select_streams", "a:0",
        "-show_entries", "format=duration,size,bit_rate,format_name:stream=codec_name,sample_rate,channels,bit_rate,duration",
        "-of", "json", str(path)], check=True, capture_output=True, encoding="utf-8")
    return json.loads(result.stdout)


def pcm(path: Path, ffmpeg: Path, channels: int = 1) -> np.ndarray:
    result = subprocess.run([str(ffmpeg), "-v", "error", "-i", str(path), "-map", "0:a:0",
        "-f", "f32le", "-ar", "44100", "-ac", str(channels), "pipe:1"],
        check=True, capture_output=True)
    return np.frombuffer(result.stdout, dtype="<f4").reshape(-1, channels)


def amplitude(samples: np.ndarray) -> dict:
    values = samples.astype(np.float64)
    rms = float(np.sqrt(np.mean(values * values)))
    return {"samples": len(samples), "seconds": len(samples) / 44100,
            "rms_dbfs": 20 * float(np.log10(max(rms, 1e-12))),
            "peak": float(np.max(np.abs(values)))}


def convert(source: Path, converted: Path, ffmpeg: Path, ffprobe: Path) -> tuple[bytes, dict]:
    """Preserve the full performance; explicitly average the supplied stereo pair."""
    converted.parent.mkdir(parents=True, exist_ok=True)
    source_metadata = metadata(source, ffprobe)
    if source_metadata["streams"][0]["channels"] != 2:
        raise ValueError("Unreviewed source channel layout")
    temporary = converted.with_suffix(".tmp.mp3")
    command = [str(ffmpeg), "-y", "-v", "error", "-i", str(source), "-map", "0:a:0",
        "-map_metadata", "-1", "-vn", "-af", "pan=mono|c0=0.5*c0+0.5*c1",
        "-c:a", "libmp3lame", "-ar", "44100", "-ac", "1",
        "-b:a", "96k", "-minrate", "96k", "-maxrate", "96k", "-write_xing", "1",
        "-id3v2_version", "0", str(temporary)]
    subprocess.run(command, check=True, capture_output=True)
    standard = temporary.read_bytes()
    stored = wf_assets.mp3_encode(standard)
    if wf_assets.mp3_decode(stored) != standard:
        raise ValueError("MP3 storage roundtrip changed audio bytes")
    info = gate.probe(stored)
    failures = gate.check_container(gate.VoiceFile("unicorn_lancer_rose", "candidate", stored), info)
    if failures or not info["xing"] or info["tail"] != 0:
        raise ValueError(f"Invalid encoded voice stream: {failures}")
    # Full decoder consumption independently catches corrupt frames, and the Xing
    # delay/padding information lets us compare actual PCM lengths without cuts.
    stereo = pcm(source, ffmpeg, 2).astype(np.float64)
    original_pcm, encoded_pcm = stereo.mean(axis=1, keepdims=True), pcm(temporary, ffmpeg)
    original, encoded = amplitude(original_pcm), amplitude(encoded_pcm)
    # Separate floating-point decode and libmp3lame's resampling path can differ
    # by a few flush samples (48 kHz -> 44.1 kHz: observed 18 samples). Bound that
    # rounding to <1.5 ms; do not accept an MP3 frame or a shortened performance.
    if abs(original["samples"] - encoded["samples"]) > 64:
        raise ValueError("Transcoding shortened or extended the decoded performance")
    gain_db = encoded["rms_dbfs"] - original["rms_dbfs"]
    if abs(gain_db) > 1.0:
        raise ValueError(f"Unexpected transcoding gain change: {gain_db:.3f} dB")
    lr_correlation = float(np.corrcoef(stereo[:, 0], stereo[:, 1])[0, 1])
    if not np.isfinite(lr_correlation) or lr_correlation < 0:
        raise ValueError("Stereo channels require explicit phase review before mono conversion")
    temporary.replace(converted)
    return stored, {"source_metadata": source_metadata,
        "converted_metadata": metadata(converted, ffprobe), "codec": info,
        "standard_sha256": sha(standard), "storage_sha256": sha(stored),
        "storage_roundtrip_equal": True, "decode_error": False,
        "original_pcm": original, "converted_pcm": encoded,
        "sample_delta": encoded["samples"] - original["samples"],
        "sample_delta_limit": 64,
        "gain_delta_db": gain_db, "source_stereo_correlation": lr_correlation,
        "mono_mix": "0.5 * left + 0.5 * right",
        "no_trim_no_speed_no_normalization": True}
