"""泳装勇希与水杰拉尔：2026-09-24 作者指定的键级修订。

2026-09-27 作者「能力伤害倍率都降低一些」：能力伤害攻击倍率 ×0.8 同步进本生成器——
杰拉尔 629 追击 45→36 倍（STRIKE_MULTIPLIER / STRIKE_TEXT）、能力5 行1 kind252 15→12 倍，
勇希能力2 行3 kind252 10→8 倍；产物 == wf_balance_20260927_waterab 的 revise()（测试断言）。
"""
from copy import deepcopy
import hashlib

import wf_mod_tool as core
import wf_dsl
from wf_character_revision import RevisionCandidate, encode_tree

ABILITY = 'master/ability/ability.orderedmap'
ACTION = 'master/skill/action_skill.orderedmap'
TEXT = 'master/character/character_text.orderedmap'
CAS = 'master/string/custom_ability_string.orderedmap'
CODE = 'unicorn_lancer_rose'
STRIKE_KEY = 'change_skill_' + CODE + '_oath_strike'
STRIKE_PROGRAM = f'battle/action/skill/action/ability_skill/{CODE}_oath_strike${CODE}_oath_strike'
STRIKE_MULTIPLIER = 36  # 2026-09-27：45 → 36（×0.8）
STRIKE_TEXT = f'对距离最近的敌人造成{STRIKE_MULTIPLIER}倍水属性能力伤害，威力随连击数提升'
BEFORE = {
    '1299912': 'e68125300303eb3daa454950800ae8e2de93269c8af00991a1f2b8f582beba96',
    '1299921': '13e85317214957e3b0c76e35fe7c99fde18ed372a29cc93967459d00968629cf',
    '1299922': 'd697ccc83cb782edba4177f9874704ba7c4a13ab68d822526b0da785fc7a9e78',
    '1299925': '3423b37a25b759978f174b0798233804ea626f818671c2f8d110062ae6a96819',
}


def digest_rows(rows):
    return hashlib.sha256(core.write_csv_lines(rows).encode()).hexdigest()


def baseline(key, rows):
    if digest_rows(rows) != BEFORE[key] or any(len(r) != 126 for r in rows):
        raise ValueError(f'unreviewed balance baseline: {key}')
    return deepcopy(rows)


def yuki_rows(rows):
    out = baseline('1299912', rows)
    out[1][30:32] = ['10000000']*2
    out[1][48] = '1'  # Others; Blue group remains.
    attack = list(out[1])
    attack[30:32] = ['7500000']*2
    attack[47:50] = ['252', '0', '']  # EnemyDamageByAttackBlue, all enemies.
    attack[51:53] = ['800000']*2  # 2026-09-27：10 → 8 倍（×0.8）
    attack[69] = '(None)'
    out.append(attack)
    return out


def gerald_rows(key, rows):
    out = baseline(key, rows)
    if key == '1299921':
        row = out[0]
        row[6], row[9], row[10], row[11] = '2', '600000', '600000', 'Blue'
        row[27], row[30], row[31], row[34] = '23', '100000', '100000', '(None)'
        row[28], row[35] = '0', '0'
        row[47:50], row[51:53] = ['629', '0', ''], ['0', '0']
        row[70], row[71] = STRIKE_KEY, STRIKE_PROGRAM
        return [row]
    if key == '1299922':
        added = list(out[1])
        added[47] = '388'  # AbilityDamage, party Blue, +200%.
    elif key == '1299925':
        out[0][51:53] = ['1200000']*2  # 2026-09-27：全体 252 15 → 12 倍（×0.8）
        out[1][51:53] = ['20000']*2
        added = list(out[1])
        added[47] = '695'  # SeparatedTermAbilityDamage, self +20%.
    else:
        raise ValueError('unsupported Gerald ability key')
    out.append(added)
    return out


def strike_tree():
    """One nearest enemy, no hit area, no skill invoke event, native combo bonus."""
    slv = lambda v: [{'min': v, 'max': v}]
    attack = ['CreateNormalAttack', 0, 255, [], [], 12, slv(STRIKE_MULTIPLIER), slv(0),
              True, False, False, False, False, slv(1), slv(1), ['Fine'], True]
    # FindNearSubjects: origin=-18 (ball), count=1, selector=49 (enemy), bind=0.
    find = ['FindNearSubjects', -18, 1, 49, ['DoNothing'], 0,
            ['Block', [['Command', attack]]]]
    return ['ActionDsl', 1, ['None'], False, False, False, False, False, False,
            False, 102, ['Block', [['Command', find]]]]


def skill_tree(tree):
    out = deepcopy(tree)
    attacks = list(wf_dsl.iter_dsl_commands(out, 'CreateNormalAttack'))
    expected = [(1.875, 2.25), (3.75, 4.5), (22.5, 27)]
    if len(attacks) != 3 or any(n[6] != [{'min': lo, 'max': hi}] or n[8] is not True
                                for n, (lo, hi) in zip(attacks, expected)):
        raise ValueError('unreviewed Gerald 90x skill tree')
    for node in attacks:
        node[6][0] = {k: v*5/6 for k, v in node[6][0].items()}
    return out


def apply_candidate(repo, root, role, *, apply=False):
    import zlib
    import wf_share_update_codec as codec
    cid, code = ('129991', 'psychic_yuki_swim') if role == 'yuki' else ('129992', CODE)
    candidate = RevisionCandidate(repo, root, character_id=cid, code_name=code,
        package_version='0.2.0' if role == 'yuki' else '0.1.13',
        snapshot_key='water_balance_20260924', evidence_name='water-balance-20260924.json')
    table = core.read_orderedmap_file_from_bytes(candidate.read('common', ABILITY))
    keys = [cid+'2'] if role == 'yuki' else [cid+x for x in ('1', '2', '5')]
    updates = {key: (yuki_rows(core.read_csv_lines(table[key])) if role == 'yuki'
                      else gerald_rows(key, core.read_csv_lines(table[key]))) for key in keys}
    from wf_client_legality import client_legality_problems
    for rows in updates.values():
        for row in rows:
            problems = client_legality_problems('ability', row)
            if problems:
                raise ValueError('; '.join(problems))
    candidate.splice(ABILITY, updates)
    if role == 'gerald':
        candidate.splice(CAS, {STRIKE_KEY: [[STRIKE_TEXT]]})
        candidate.emit('common', wf_dsl.dsl_logical(STRIKE_PROGRAM), encode_tree(strike_tree()))
        table = codec.unpack(candidate.read('common', ACTION))
        nested = codec.unpack(table[CODE]); row = codec.node(nested['2'])['csv'][0]
        if '90倍' not in row[1]:
            raise ValueError('unexpected Gerald skill description')
        row[1] = row[1].replace('90倍', '75倍')
        logical = wf_dsl.dsl_logical(row[7])
        tree = wf_dsl.parse_dsl(zlib.decompress(candidate.read('common', logical), -15))['tree']
        candidate.emit('common', logical, encode_tree(skill_tree(tree)))
        nested['2'] = zlib.compress(core.write_csv_lines([row]).rstrip('\n').encode())
        candidate.splice(ACTION, {CODE: codec.pack(nested)}, codec='action_nested')
        textrows = core.read_csv_lines(core.read_orderedmap_file_from_bytes(candidate.read('common', TEXT))[cid])
        textrows[0][7] = row[1]
        candidate.splice(TEXT, {cid: textrows})
        mirror = __import__('json').loads(candidate.read('server', 'cdndata/character_text.json'))[cid]
        mirror[0][7] = row[1]
        candidate.server_character_row('cdndata/character_text.json', mirror)
        caps = candidate.manifest.setdefault('required_capabilities', [])
        if 'damage-type-rules-v1' not in caps:
            caps.append('damage-type-rules-v1')
        skills = candidate.manifest['skills']
        skills['programs'] = sorted({wf_dsl.dsl_logical(p)
            for p in skills['active']['programs']} | {wf_dsl.dsl_logical(STRIKE_PROGRAM)})
        skills['active'].update(name=row[0].rstrip('＋'), min_multiplier=62.5, max_multiplier=75)
    return candidate.finish(dict(role=role, ability_keys=keys,
        damage_type='native ability' if role == 'yuki' else 'ability via segment 102',
        source='wf_water_balance_20260924.py', runtime_verified=False), apply=apply)
