"""作者确认的特克托 A+B：取消额外停球，技能树前摇 36 帧。

仅更新当前候选的两棵 DSL，不重建旧表、不覆盖后续半血重炮改动。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import zlib

import wf_dsl
import wf_seasonal7_kit_philia as philia
import wf_tekuto_no_endlag_revision as revision
from wf_character_revision import RevisionCandidate, encode_tree

WINDUP_FRAMES = 36


def final_tree(tree):
    updated = revision.compress_windup(revision.strip_ball_hold(tree),
                                       first_beam_frame=WINDUP_FRAMES)
    failures = philia.dsl_gate_failures(philia.dsl_gates(updated, element=revision.ELEMENT))
    if failures:
        raise ValueError(f'compressed skill DSL invalid: {failures}')
    return updated


def apply_candidate(repo: Path, *, apply=False):
    candidate = RevisionCandidate(repo, repo / revision.WORKSPACE_REL,
        character_id=revision.CID, code_name=revision.CODE, package_version='1.0.7',
        snapshot_key='tekuto_fast_release_20260921', evidence_name='fast-release.json')
    facts = []
    for program in revision.SKILL_PROGRAMS:
        logical = wf_dsl.dsl_logical(program)
        before = wf_dsl.parse_dsl(zlib.decompress(candidate.read('common', logical), -15))['tree']
        after = final_tree(before)
        candidate.emit('common', logical, encode_tree(after))
        facts.append(dict(logical=logical, hold_frames=revision.hold_frames(after),
                          timeline=revision.timeline(after)))
    return candidate.finish(dict(author_decision='同时取消停球并缩短前摇',
        windup_frames=WINDUP_FRAMES, client_cutin_frames=60, first_laser_seconds=1.6,
        charge_sound_unchanged_at_frame=86, ability_rows_unchanged=True, skills=facts), apply=apply)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(apply_candidate(Path(__file__).resolve().parents[1], apply=args.apply),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
