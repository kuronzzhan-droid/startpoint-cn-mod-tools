"""浴菲莉亚能力3与泽赫尔35连击/慢速重斩修订；kit重建后最后应用。"""
from copy import deepcopy
from pathlib import Path
import hashlib,json,zlib,argparse
import wf_mod_tool as core
import wf_dsl
from wf_client_legality import client_legality_problems
from wf_character_revision import RevisionCandidate,encode_tree
from wf_zehr_slow_spin import slow_timeline,slow_attack
from wf_zehr_spin_animation import smooth_parts

ABILITY='master/ability/ability.orderedmap'
CAS='master/string/custom_ability_string.orderedmap'
ZEHR_LEADER_TEXT=('光属性共鸣时，光属性角色攻击力＋400%、强化弹射伤害＋200%\n'
    '赋予专属强化弹射：剑士型与辅助型同时生效，回旋斩持续时间延长、单击威力提升\n'
    '每达成35连击，强化弹射伤害＋50%\n'
    '每发动强化弹射，光属性角色攻击力＋35%\n'
    '光属性共鸣时，每发动3次强化弹射，接下来6次弹射各追加9连击\n'
    '改变冲刺方向：朝点击侧斜下方冲刺，保留头目弱点与传送舱锁定')
SPECS={
 'philia':('159996','wind_oracle_yukata','89990cbd600fbb81e2b2af2a8056f8142dcdfd5433f5aa2c1e23b345a7813aa2'),
 'zehr':('159997','guildknight_leader_tavern','58ecd83ec7d4e88bf98c2e48989bcb6b2d87efbe9f4695319b15668131ade409'),
}


def rows_sha(rows):return hashlib.sha256(core.write_csv_lines(rows).encode()).hexdigest()


def revise_rows(role,rows):
    if rows_sha(rows)!=SPECS[role][2]:raise ValueError('reviewed ability-3 rows changed')
    result=deepcopy(rows)
    if role=='philia':
        for effect in ('32','55'):
            row=deepcopy(rows[4])
            row[27:32]=['2','','','500000','500000']
            # PowerFlipDamage is team-wide in the native schema; only ATK
            # consumes a target field. Do not leave a misleading ignored target.
            row[47:50]=[effect,'2' if effect=='32' else '','']
            row[51:53]=['50000','50000']
            result.append(row)
    else:
        if result[5][47]!='226' or result[5][27]!='12':raise ValueError('combo row moved')
        result[5][30:32]=['3500000','3500000']
    for row in result:
        errors=client_legality_problems('ability',row)
        if errors:raise ValueError(str(errors))
    return result


def apply_candidate(repo,role,*,apply=False):
    cid,code,_=SPECS[role]
    candidate=RevisionCandidate(repo,repo/'work/character_packs'/('s7-'+role),
        character_id=cid,code_name=code,package_version='1.0.1',
        snapshot_key='pf_revision_20260917',evidence_name='pf-revision-20260917.json')
    old=core.read_orderedmap_file_from_bytes(candidate.read('common',ABILITY))[cid+'3']
    rows=revise_rows(role,core.read_csv_lines(old))
    candidate.splice(ABILITY,{cid+'3':rows})
    metadata=dict(role=role,other_ability_rows_preserved=True)
    if role=='philia':
        metadata.update(resonance='Light x6',every_power_flips=5,leader_attack=50,
                        power_flip_damage=50,trigger_limit=None)
    else:
        texts=core.read_orderedmap_file_from_bytes(candidate.read('common',CAS))
        key='desc_override_'+code+'_3'
        before=core.read_csv_lines(texts[key])
        if str(before).count('每达成15连击')!=1:raise ValueError('ability override drift')
        after=deepcopy(before);after[0][0]=after[0][0].replace('每达成15连击','每达成35连击')
        pf_key='override_string_'+code+'_dual_pf'
        candidate.splice(CAS,{key:after,'desc_override_'+code:[[ZEHR_LEADER_TEXT]],pf_key:[[
            '剑士型＋辅助型强化弹射同时生效。剑士型回旋斩持续更久，以较慢的转速造成更高的单次伤害；辅助型强化弹射赋予的贯穿、浮游效果持续时间延长。']]})
        budgets=[]
        import wf_seasonal7_kit_zehr as kit
        for level,name in enumerate(('one','two','three'),1):
            logical=f'battle/action/power_flip/action/override/{code}_pf${code}_pf_lv{level}.action.dsl.amf3.deflate'
            tree=wf_dsl.parse_dsl(zlib.decompress(candidate.read('common',logical),-15))['tree']
            result,budget=slow_attack(tree)
            errors=wf_dsl.player_side_dsl_problems(result)+kit.typed_signature_problems(result)
            if errors:raise ValueError(str(errors))
            candidate.emit('common',logical,encode_tree(result));budgets.append(budget)
            stem=f'battle/effect/skill_unique/{code}/pf_spin/powerflip_attack_spin_{name}'
            for suffix,transform in [('parts',lambda tree:smooth_parts(tree,ornament=level>1)),('timeline',slow_timeline)]:
                logical=stem+'.'+suffix+'.amf3.deflate'
                value=wf_dsl.parse_dsl(zlib.decompress(candidate.read('common',logical),-15))['tree']
                candidate.emit('common',logical,encode_tree(transform(value)))
        metadata.update(combo_threshold=35,combo_added=5,spin_speed=0.33,budgets=budgets,
                        auxiliary_attack_unchanged=True,texture_atlas_unchanged=True)
    return candidate.finish(metadata,apply=apply)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--character',choices=SPECS,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    print(json.dumps(apply_candidate(Path(__file__).resolve().parents[1],args.character,
                                    apply=args.apply),ensure_ascii=False))
