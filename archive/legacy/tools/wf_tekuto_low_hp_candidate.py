"""特克托半血重炮候选写入，保留原有图集及语音。"""
import json
import zlib
from pathlib import Path
import wf_dsl
import wf_mod_tool as C
from wf_character_revision import RevisionCandidate, encode_tree
import wf_tekuto_low_hp as T
from wf_surge_anchor_candidate import ABILITY, LEADER, CAS, logical

UNIQUE='master/character/unique_condition.orderedmap'


def apply_candidate(repo, *, apply=False):
    c=RevisionCandidate(repo,repo/'work/character_packs/s7-tekuto',
        character_id=T.CID,code_name=T.CODE,package_version='1.0.5',
        snapshot_key='low_hp_20260917',evidence_name='low-hp-20260917.json')
    def rows(table,key):
        return C.read_csv_lines(C.read_orderedmap_file_from_bytes(c.read('common',table))[key])
    leader,third=T.revise_rows(rows(LEADER,T.CID),rows(ABILITY,T.CID+'3'))
    c.splice(LEADER,{T.CID:leader})
    c.splice(ABILITY,{T.CID+'3':third})
    c.splice(UNIQUE,{T.CANNON:T.revise_unique(rows(UNIQUE,T.CANNON))})
    c.splice(CAS,{'change_skill_2_'+T.CODE:[[T.SHIELD_TEXT]]})
    for level in (1,2):
        path=logical(T.CODE,level)
        tree=wf_dsl.parse_dsl(zlib.decompress(c.read('common',path),-15))['tree']
        c.emit('common',path,encode_tree(T.revise_skill(tree)))
    return c.finish(dict(hp_lte_percent=50,skill_growth_percent=100,interval_frames=120,
        growth_cap=None,engine_stacks=2,cannon_frames=900,shield_max_hp_percent=15),apply=apply)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply',action='store_true')
    print(json.dumps(apply_candidate(Path(__file__).resolve().parents[1],apply=p.parse_args().apply),ensure_ascii=False))
