"""Translate provider timestamps to the trimmed delivery timeline.

Text matching remains based on the complete original subtitle. Trimming silence
must never hide an inserted word from the content gate.
"""
from __future__ import annotations

import numpy as np


def acoustic_timing(samples, sample_rate: int = 44100) -> dict:
    """10 ms RMS timing, matching the official-corpus -38 dB relative gate.

    Word alignment gaps include consonants and breaths. They are not acoustic
    silence and cannot be compared to thresholds measured from decoded audio.
    """
    a = np.asarray(samples, dtype=np.float64).reshape(-1)
    if not len(a) or not np.isfinite(a).all():
        raise ValueError('empty or non-finite audio')
    win = sample_rate // 100
    n = len(a) // win
    if n < 1:
        raise ValueError('audio shorter than one analysis window')
    rms = np.sqrt((a[:n * win].reshape(n, win) ** 2).mean(1) + 1e-12)
    active = rms > max(float(rms.max()), 1e-6) * 10 ** (-38 / 20)
    idx = np.flatnonzero(active)
    if float(np.max(np.abs(a))) < 1e-6 or not len(idx):
        raise ValueError('silent audio')
    best = run = 0
    for voiced in active[idx[0]:idx[-1] + 1]:
        run = 0 if voiced else run + 1
        best = max(best, run)
    return dict(method='rms-10ms-relative-38db',
                max_inner_gap_seconds=round(best * win / sample_rate, 3),
                active_span_seconds=round((idx[-1] - idx[0] + 1) * win / sample_rate, 3),
                leading_quiet_seconds=round(idx[0] * win / sample_rate, 3),
                trailing_quiet_seconds=round(len(a) / sample_rate - (idx[-1] + 1) * win / sample_rate, 3))


def delivery_gap(metrics: dict, qc: dict) -> tuple[float | None, float]:
    timing = qc.get('delivery_timing') or {}
    if timing.get('method') == 'rms-10ms-relative-38db':
        return timing['max_inner_gap_seconds'], timing['active_span_seconds']
    return metrics.get('max_inner_gap_seconds'), float(qc.get('seconds') or 0.0)


def raw_level_is_blocking(qc: dict, floor: float) -> bool:
    """Raw gain is diagnostic once a complete two-pass master has been checked.

    Uniformly scaling a valid source must not reject the same final audio.
    Legacy/incomplete reports retain the old raw-level gate. Final loudness,
    clipping, peak and bounded limiting are still checked independently.
    """
    raw = qc.get('raw_lufs_i')
    if raw is None or not np.isfinite(raw) or raw <= -69:
        return True
    complete = (qc.get('mastering_mode') == 'two_pass'
                and qc.get('storage_roundtrip_equal') is True
                and (qc.get('source_pcm') or {}).get('peak', 0) > 1e-6
                and (qc.get('mastered_pcm') or {}).get('samples', 0) > 0
                and abs(qc.get('sample_delta', 1e9)) <= qc.get('sample_delta_limit', 0))
    return raw < floor and not complete


def delivery_edges(metrics: dict, qc: dict) -> tuple[float | None, float | None]:
    timing = qc.get('delivery_timing') or {}
    if timing.get('method') == 'rms-10ms-relative-38db':
        # These values already describe the final audio. Provider word alignment
        # may end early; applying source trim offsets again would also be wrong.
        return timing['leading_quiet_seconds'], timing['trailing_quiet_seconds']
    lead, tail = metrics.get('lead_in_seconds'), metrics.get('tail_seconds')
    trim = qc.get('trim')
    if trim and lead is not None and tail is not None:
        source_seconds = float(metrics.get('duration') or
                               (qc.get('source_pcm') or {}).get('seconds') or 0)
        lead = max(0.0, float(lead) - float(trim['start_seconds']))
        tail = max(0.0, float(tail) - max(0.0, source_seconds - float(trim['end_seconds'])))
    if lead is None or tail is None:
        # New reports measure the actual deliverable; retain legacy fallback.
        pcm = qc.get('mastered_pcm') or {}
        if 'leading_quiet_seconds' not in pcm or 'trailing_quiet_seconds' not in pcm:
            pcm = qc.get('source_pcm') or {}
        lead, tail = pcm.get('leading_quiet_seconds'), pcm.get('trailing_quiet_seconds')
    return (None if lead is None else round(float(lead), 3),
            None if tail is None else round(float(tail), 3))


def delivery_dead_air(metrics: dict, qc: dict) -> float:
    lead, tail = delivery_edges(metrics, qc)
    seconds = float(qc.get('seconds') or metrics.get('duration') or 0)
    if seconds > 0 and lead is not None and tail is not None:
        return min(1.0, (lead + tail) / seconds)
    return float(metrics.get('dead_air_share') or 0)
