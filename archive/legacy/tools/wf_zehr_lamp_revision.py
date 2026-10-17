"""泽赫尔灯火：共鸣55连击、15秒；持有时每连击增加5% PF伤害。"""
from copy import deepcopy

from wf_character_revision import RevisionCandidate
import wf_mod_tool as core
from wf_seasonal7_kit_philia import row_problems

CID = '159997'
CODE = 'guildknight_leader_tavern'
ABILITY = 'master/ability/ability.orderedmap'
CAS = 'master/string/custom_ability_string.orderedmap'
UNIQUE = 'master/character/unique_condition.orderedmap'
ICON = " <icon id='main'>  "


def revise_rows(first, third):
    a, b = deepcopy(first), deepcopy(third)
    # Remove only the unconditional +150% ATK row, never the opening gauge.
    attack = [r for r in a if r[5] == '0' and r[27] == '0' and r[47] == '32']
    if attack:
        if len(attack) != 1 or attack[0][51:53] != ['150000'] * 2:
            raise ValueError('A1 unconditional attack drift')
        a.remove(attack[0])
    grants = [r for r in a if r[47] == '461' and r[68] in (CID, CID+'1')]
    gains = [r for r in b if r[5] == '0' and r[47] in ('32', '55')]
    if len(grants) != 2 or len(gains) != 2:
        raise ValueError('lamp/wick grant or linked A3 gain drift')
    for r in grants + gains:
        if r[27] not in ('12', '13') or r[35] != '300':
            raise ValueError('lamp trigger or cooldown drift')
        # All four originally shared BallFlipWithComboHigh. Keep rewards in
        # sync with the new lamp grant, including their existing 5s cooldown.
        r[6:13] = ['2', '', '', '600000', '600000', 'White', '']
        r[27] = '12'
        r[30:32] = ['5500000'] * 2
    combo = [r for r in b if r[47] == '226']
    multi = [r for r in b if r[5] == '1' and r[97] == '194' and r[109] == '413']
    if len(combo) != 1 or len(multi) != 1 or combo[0][12] != CID or multi[0][104] != CID:
        raise ValueError('lamp A3 effect drift')
    combo[0][30:32] = ['3500000'] * 2
    combo[0][51:53] = ['1500000'] * 2
    multi[0][113:115] = ['15000'] * 2
    # Native ComboHigh returns floor(current combo / threshold). No trigger
    # limit means no stack cap; during content23 is additive PF damage, not413.
    growth = deepcopy(multi[0])
    growth[6:13] = deepcopy(combo[0][6:13])
    growth[97:109] = ['2', '', '', '100000', '100000', '(None)', '', '', '', '', '', 'false']
    growth[109:126] = ['23', '', '', '', '5000', '5000', '', '', '', '', '', '', '', '', '', '', '']
    existing = [r for r in b if r[5] == '1' and r[97] == '2' and r[109] == '23']
    if existing:
        old_growth = deepcopy(growth)
        old_growth[113:115] = ['2000'] * 2
        if existing not in ([old_growth], [growth]):
            raise ValueError('combo PF growth drift')
        existing[0][113:115] = ['5000'] * 2
    else:
        b.append(growth)
    for r in a + b:
        if errors := row_problems('ability', r):
            raise ValueError(errors)
    return a, b


def revise_unique(rows):
    result = deepcopy(rows)
    if len(result) != 1 or result[0][3] not in ('720', '900'):
        raise ValueError('lamp duration drift')
    result[0][3] = '900'
    return result


def revise_text(slot, text):
    lines = text.replace('（每5秒1次）', '（CT 5s）').split('\n')
    if slot == 1:
        lines = [s for s in lines if s.strip() != (ICON+'自身攻击力＋150%').strip()]
        for i, line in enumerate(lines):
            if '并累积1层「灯芯」' in line:
                lines[i] = ICON+'光属性共鸣时，每达成55连击，赋予自身「灯火正旺」15秒，并累积1层「灯芯」（CT 5s）'
    elif slot == 3:
        lines = [s.replace('额外乘区＋40%', '额外乘区＋15%')
                 .replace('每达成15连击，连击＋5', '每达成35连击，连击＋15')
                 .replace('每达成35连击，连击＋5', '每达成35连击，连击＋15') for s in lines]
        lines = [s for s in lines if s not in (
            ICON+'持有「灯火正旺」期间，每1连击，强化弹射伤害＋2%',
            ICON+'持有「灯火正旺」期间，每1连击，强化弹射伤害＋5%')]
        extra = ICON+'持有「灯火正旺」期间，强化弹射伤害随连击数提高'
        if extra not in lines:
            lines.append(extra)
    else:
        raise ValueError(slot)
    return '\n'.join(lines)


def apply_candidate(repo, *, apply=False):
    c = RevisionCandidate(repo, repo/'work/character_packs/s7-zehr',
        character_id=CID, code_name=CODE, package_version='1.0.6',
        snapshot_key='lamp_combo_20260917', evidence_name='lamp-combo-20260917.json')
    def rows(table, key):
        return core.read_csv_lines(core.read_orderedmap_file_from_bytes(c.read('common', table))[key])
    a, b = revise_rows(rows(ABILITY, CID+'1'), rows(ABILITY, CID+'3'))
    c.splice(ABILITY, {CID+'1': a, CID+'3': b})
    c.splice(UNIQUE, {CID: revise_unique(rows(UNIQUE, CID))})
    c.splice(CAS, {f'desc_override_{CODE}_{s}': [[revise_text(s, rows(CAS, f'desc_override_{CODE}_{s}')[0][0])]]
                   for s in (1, 3)})
    return c.finish(dict(resonance='White x6', lamp_combo=55, lamp_frames=900,
        cooldown_frames=300, combo_reward=[35, 15], pf_per_combo_percent=5,
        pf_combo_limit=None, lamp_multiplier_percent=15, a1_attack_removed=True), apply=apply)


if __name__ == '__main__':
    import argparse, json
    from pathlib import Path
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true')
    print(json.dumps(apply_candidate(Path(__file__).resolve().parents[1], apply=p.parse_args().apply), ensure_ascii=False))
