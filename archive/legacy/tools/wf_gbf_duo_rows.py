"""Named, schema-checked native rows; no live-store writes."""
import json
from pathlib import Path

import wf_gui
import wf_client_legality

META = json.loads((Path(__file__).parent/'ability_enum_map.json').read_text(encoding='utf-8'))
ENUM = {name: {v:k for k,v in values.items()} for name,values in META['enums'].items()}


def row(cid, slot, effect, value=0, *, during=False, trigger=None, threshold=None,
        target='0', groups='', unit='pct', puller='0', main=False, pre=(),
        limit=None, cooldown=0, uid=None, path=None, start=None, content_uid=None):
    leader = slot == 0
    mode = 'during' if during else 'instant'
    layout = META['layouts']['leader_ability' if leader else 'ability']['blocks']
    effect_id = ENUM['CommonAbilityContentMasterValue' if during else 'InstantAbilityContentMasterValue'][effect]
    trigger = trigger or ('HpHigh' if during else 'Initial')
    trigger_id = ENUM['DuringAbilityTriggerMasterValue' if during else 'InstantAbilityTriggerMasterValue'][trigger]
    result = wf_gui.composer_generate(f'L:{cid}' if leader else f'{cid}{slot}', mode=mode,
        effect_kind=effect_id, value=value, effect_unit=unit, trigger_kind=trigger_id,
        threshold=threshold, target=str(target), groups=groups, puller=str(puller),
        action_path=path or '', string_id=f'gbf_{cid}_{slot}' if path else '')['row']
    result[0] = f'gbf_{cid}_{slot}'
    if not leader:
        result[1:5] = ['false' if main else 'true', 'attack_common', '0', '0']
    for i, cond in enumerate(pre, 1):
        off = layout[f'precondition{i}']
        kind, pull, group, threshold, unique = cond
        result[off:off+7] = [ENUM['AbilityPreconditionMasterValue'][kind], str(pull), '',
                            str(threshold), str(threshold), group, str(unique) if unique else '']
    t = layout['during_trigger' if during else 'instant_trigger']
    result[t+(5 if during else 7)] = '(None)' if limit is None else str(limit)
    if not during:
        result[t+8] = str(cooldown)
    if uid:
        result[t+(7 if during else 10)] = str(uid)
    if start is not None:
        result[t+8:t+10] = [str(start)]*2
    if during and trigger == 'HpHigh' and threshold is None:
        result[t+3:t+5] = ['0','0']
        result[t+5] = '1'
    c = layout['during_content' if during else 'instant_content']
    if not during and effect.startswith(('Condition', 'TriggerEnemyCondition')):
        result[c+10:c+14] = ['90000000','90000000','100000','100000']
        result[c+14:c+19] = ['1','(None)','(None)','(None)','(None)']
        result[c+20], result[c+25] = '0', 'false'
        result[c+27:c+29] = ['1','0']
    if content_uid:
        result[c+(9 if during else 21)] = str(content_uid)
    if effect.startswith('ChangeSkillFlag'):
        result[c+23] = f'change_skill_{cid}_{slot}'
    if problems := wf_client_legality.client_legality_problems('leader_ability' if leader else 'ability', result):
        raise ValueError(problems)
    return result


def set_fields(result, block, **fields):
    layout = META['layouts']['leader_ability' if len(result)==124 else 'ability']['blocks']
    off = layout[block]
    names = {name:i for i,name,_ in META['block_fields'][block]}
    for name, value in fields.items():
        result[off+names[name]] = str(value)
    return result


RESONANCE = ('Member', '', 'Blue', 600000, None)
LEADER_WATER = ('LeaderCharacter', '', 'Blue', '', None)


def unique_pre(uid, count=1):
    return ('ConditionAccumulationCountUnique', '0', '', count*100000, uid)


def condition_grant(result, uid, count=1):
    return set_fields(result, 'instant_content', **{
        'unique_condition_id': uid, 'number.power1': count*100000,
        'number.first_max': count*100000, 'cancelable': 1})
