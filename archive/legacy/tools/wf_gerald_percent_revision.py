"""修订已从当前资源捕获的光杰拉德候选；只写两档动作和强化说明。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import wf_gerald_percent_skill as skill
import wf_mod_tool as core
from wf_character_revision import RevisionCandidate

STRINGS = 'master/string/custom_ability_string.orderedmap'
STRING_KEY = 'change_skill_white_wolf_gerald'
OLD_EFFECT = '造成相当于敌人当前生命值5%的时空侵蚀伤害（无视一切抗性）'
NEW_EFFECT = ('对最近的敌人造成相当于其当前生命值5%的时空侵蚀伤害；'
              '其生命值低于最大生命值5%时，改为造成相当于当前生命值100%的斩杀伤害')


def description(text):
    if text.count(OLD_EFFECT) != 1:
        raise ValueError('reviewed Gerald enhanced description changed')
    return text.replace(OLD_EFFECT, NEW_EFFECT)


def assemble(repo: Path, candidate_root: Path, *, apply=False):
    candidate = RevisionCandidate(repo, candidate_root, character_id=skill.CID,
        code_name=skill.CODE, package_version='1.3.8', snapshot_key='gerald_percent_revision',
        evidence_name='gerald-percent-revision.json')
    for level, logical in skill.ACTIVE_PATHS.items():
        candidate.emit('common', logical,
                       skill.patch_skill_bytes(candidate.read('common', logical), level))
    strings = core.read_orderedmap_file_from_bytes(candidate.read('common', STRINGS))
    candidate.splice(STRINGS, {STRING_KEY: [[description(strings[STRING_KEY])]]})
    return candidate.finish(skill.metadata(), apply=apply)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(assemble(args.repo, args.workspace, apply=args.apply),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
