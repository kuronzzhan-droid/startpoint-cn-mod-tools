"""雷吉斯两处Fever回槽和菲莉亚随机五向PF的键级候选修订。"""
import zlib

import wf_dsl
import wf_mod_tool as C
from wf_character_revision import RevisionCandidate, encode_tree
import wf_regis_surge_stages as R
import wf_seasonal7_kit_philia as K
from wf_philia_random_pf import revise_pf
from wf_philia_wind_revision import PF_TEXT

LEADER = 'master/ability/leader_ability.orderedmap'


def apply_candidate(repo, role, *, apply=False):
    if role not in ('regis', 'philia'):
        raise ValueError(role)
    cid, code = (R.CID, R.CODE) if role == 'regis' else ('159996', K.CODE)
    c = RevisionCandidate(repo, repo/f'work/character_packs/s7-{role}',
        character_id=cid, code_name=code, package_version='1.0.9' if role == 'philia' else '1.0.6',
        snapshot_key='gauge_random_pf_20260917', evidence_name='gauge-random-pf.json')
    def rows(logical, key):
        return C.read_csv_lines(C.read_orderedmap_file_from_bytes(c.read('common', logical))[key])
    if role == 'regis':
        leader, third = R.revise_rows(rows(LEADER, cid), rows(K.ABILITY, cid+'3'),
                                     rows(K.ABILITY, cid+'1'))
        c.splice(LEADER, {cid: leader})
        c.splice(K.ABILITY, {cid+'3': third})
        c.splice(K.CAS, {key: [[R.revise_text(slot, rows(K.CAS, key)[0][0])]] for slot, key in
                        ((0, 'desc_override_'+code), (3, 'desc_override_'+code+'_3'))})
    else:
        for program in K.PF_PROGRAMS:
            path = wf_dsl.dsl_logical(program)
            tree = wf_dsl.parse_dsl(zlib.decompress(c.read('common', path), -15))['tree']
            c.emit('common', path, encode_tree(revise_pf(tree)))
        c.splice(K.CAS, {K.CAS_PF_OVERRIDE: [[PF_TEXT]]})
    return c.finish(dict(role=role, texture_changes=False, apk_changes=False,
        multipliers_unchanged=role != 'philia', random_directions=5 if role == 'philia' else None,
        blade_damage_factor=1.25 if role == 'philia' else None,
        rain_total_damage=[3, 5, 7] if role == 'philia' else None,
        angular_spacing_degrees=72 if role == 'philia' else None), apply=apply)
