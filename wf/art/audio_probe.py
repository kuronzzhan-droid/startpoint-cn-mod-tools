"""Shared media helpers extracted from the production C tools."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path
import numpy as np

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
