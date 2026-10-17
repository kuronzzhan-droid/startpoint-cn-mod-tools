"""雷吉斯三档技能和夏勇希锚点的独立候选修订；不直接写live。"""
import json
import zlib
from pathlib import Path

import wf_dsl
import wf_mod_tool as C
from wf_character_revision import RevisionCandidate, encode_tree
import wf_regis_surge_stages as R
import wf_yuki_leader_anchor as Y

ABILITY = 'master/ability/ability.orderedmap'
LEADER = 'master/ability/leader_ability.orderedmap'
CAS = 'master/string/custom_ability_string.orderedmap'
TEXT = 'master/character/character_text.orderedmap'
ACTION = 'master/skill/action_skill.orderedmap'


def logical(code, level):
    return f'battle/action/skill/action/rare5/{code}${code}_{level}.action.dsl.amf3.deflate'


def apply_candidate(repo, name, *, apply=False):
    cid, code = (R.CID, R.CODE) if name == 'regis' else ('129991', 'psychic_yuki_swim')
    c = RevisionCandidate(repo, repo/f'work/character_packs/s7-{name}',
        character_id=cid, code_name=code, package_version='1.0.5',
        snapshot_key='surge_anchor_20260917', evidence_name='surge-anchor-20260917.json')
    for level in (1, 2):
        path = logical(code, level)
        tree = wf_dsl.parse_dsl(zlib.decompress(c.read('common', path), -15))['tree']
        c.emit('common', path, encode_tree((R if name == 'regis' else Y).revise_skill(tree)))
    if name == 'regis':
        def rows(table, key):
            return C.read_csv_lines(C.read_orderedmap_file_from_bytes(c.read('common', table))[key])
        leader, third = R.revise_rows(rows(LEADER, cid), rows(ABILITY, cid+'3'), rows(ABILITY, cid+'1'))
        c.splice(LEADER, {cid: leader})
        c.splice(ABILITY, {cid+'3': third})
        c.splice(CAS, {key: [[R.revise_text(slot, rows(CAS, key)[0][0])]] for slot, key in
                      ((0, 'desc_override_'+code), (3, 'desc_override_'+code+'_3'))})
        text = rows(TEXT, cid)
        for row in text:
            row[5] = row[7] = R.DESCRIPTION
        c.splice(TEXT, {cid: text})
        inner = C.load_nested_table_bytes(c.read('common', ACTION), ACTION).rows[code]
        for level, csv in inner.text_rows().items():
            cells = C.read_csv_lines(csv)
            cells[0][1] = R.DESCRIPTION
            inner.set_text_rows({level: C.write_csv_lines(cells).rstrip('\n')})
        c.splice(ACTION, {code: C.build_orderedmap(inner)}, codec='action_nested')
        c.server_character_row('cdndata/character_text.json', text)
    return c.finish(dict(role=name, stage_thresholds=[3, 5] if name == 'regis' else None,
                         texture_changes=False, apk_changes=False), apply=apply)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('role', choices=('regis', 'yuki'))
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()
    print(json.dumps(apply_candidate(Path(__file__).resolve().parents[1], args.role,
                                    apply=args.apply), ensure_ascii=False))
