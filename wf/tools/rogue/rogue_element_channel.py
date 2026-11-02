"""Finalize rolled curses for the opt-in Android quest resistance channel.

The caller must verify the client capability and route every generated element
condition away from Boss pre-actions. This module never changes native scripts.
"""
from __future__ import annotations
import copy
import json
from decimal import Decimal, localcontext
import math
import re
from wf.tools.rogue import rogue_build as rb

PREFIX = '【属性伤害：'
ELEMENTS = '火水雷风光暗'

def encode(totals: dict[int, float]) -> str:
    if not totals or any(isinstance(k, bool) or k not in range(1, 7) for k in totals):
        raise ValueError('invalid element targets')
    if any(not math.isfinite(v) or not 0 <= v <= 999999 for v in totals.values()):
        raise ValueError('invalid element resistance')
    if sum(v >= 99 for v in totals.values()) == 6:
        raise ValueError('all elements banned')
    tokens = []
    with localcontext() as context:
        context.prec = 48
        for element, value in sorted(totals.items()):
            percent = Decimal(100) / (Decimal(str(value)) + 1)
            text = format(percent, 'f').rstrip('0').rstrip('.') if '.' in format(percent, 'f') else format(percent, 'f')
            tokens.append(f'{ELEMENTS[element-1]}={text}%')
    result = PREFIX + ';'.join(tokens) + '】'
    recovered = decode(result)
    # Same fixed-point resolution as the existing Decimal implementation.
    assert {k:math.floor(v*100000+0.5) for k,v in recovered.items()} == {
        k:math.floor(v*100000+0.5) for k,v in totals.items()}
    return result

def decode(text: str) -> dict[int, float]:
    if text.count(PREFIX) != 1:
        raise ValueError('one resistance block required')
    block = text.split(PREFIX,1)[1]
    if '】' not in block: raise ValueError('unterminated resistance block')
    tokens = block.split('】',1)[0].split(';')
    if not 1 <= len(tokens) <= 6: raise ValueError('invalid element count')
    result = {}
    bans = 0
    for token in tokens:
        match = re.fullmatch(r'([火水雷风光暗])=([0-9]+(?:\.[0-9]+)?)%',token)
        if not match: raise ValueError('invalid element token')
        element = ELEMENTS.index(match[1])+1
        percent = float(match[2])
        if element in result or not math.isfinite(percent) or not 0.0001 <= percent <= 100:
            raise ValueError('invalid or duplicate percentage')
        bans += percent <= 1
        result[element] = 100/percent-1
    if bans == 6: raise ValueError('all elements banned')
    return result

def finalize_curse(original: dict, seed: int, round_no: int) -> tuple[dict, str, dict]:
    picks, receipt = rb.guarantee_element_bans(original['picks'],rb.element_ban_rng(seed,round_no))
    final = copy.deepcopy(original)
    # The explicit caller has verified the new quest carrier, even for floors
    # that have no General Boss. Keep every other capability restriction.
    profile = final.get('capability_profile')
    if isinstance(profile, dict):
        profile['effective']['hard_element_resistance'] = True
        profile['quest_element_channel'] = 'cn.rules.QuestElementResistance/v1'
    rb.apply_picks(final,picks,original.get('combo'))
    for key in ['conds','damage_resistance','stacked_resistance','hp','atk','tp','fever','time','gimmick','caster','casters']:
        assert json.dumps(final[key],sort_keys=True) == json.dumps(original[key],sort_keys=True), ('non-element curse changed',round_no,key)
    assert final['picks'][:len(original['picks'])] == original['picks']
    elements = final['element_resistance']
    if any(cancelable for _,_,cancelable in elements):
        raise ValueError('quest initial conditions cannot preserve cancelable element cards')
    totals = rb._resistance_totals_by_target(final['picks'],'element_resistance')
    block = encode(totals)
    assert 2 <= sum(v >= 99-1e-9 for v in decode(block).values()) <= 5
    receipt.update(channel='quest_initial_conditions',config_block=block,
                   totals={str(k):v for k,v in sorted(totals.items())},
                   original_cards_preserved=True,configuration_verified=True,
                   boss_dsl_migration_required=bool(original['element_resistance']))
    final['element_ban_receipt'] = receipt
    return final, block, receipt

def pre_action_programs(cell: str) -> list[str]:
    """GeneralBossValues c109 is String[], not Option<String>.

    The client treats only an empty string as []; '(None)' is a literal DSL
    path and triggers asset recovery (8100) before the battle starts.
    """
    programs = [] if cell == '' else cell.split(',')
    if any(not name or name == '(None)' for name in programs):
        raise ValueError('invalid General Boss pre_action path list: ' + repr(cell))
    return programs


def rewrite_pre_action_programs(cell: str, replacements: dict[str, str | None]) -> str:
    result = []
    for name in pre_action_programs(cell):
        replacement = replacements.get(name, name)
        if replacement is not None and replacement not in result:
            result.append(replacement)
    encoded = ','.join(result)
    pre_action_programs(encoded)
    return encoded


def replacement_program(curse: dict):
    """Return old/new generated program IDs; None removes an element-only call."""
    damage = curse['damage_resistance']; elements = curse['element_resistance']; stacked = curse['stacked_resistance']
    if not elements: return None
    old, old_tree = rb.immunity_program(damage,elements,stacked)
    if damage or stacked:
        new, new_tree = rb.immunity_program(damage,[],stacked)
    else:
        new, new_tree = None, None
    return old, old_tree, new, new_tree
