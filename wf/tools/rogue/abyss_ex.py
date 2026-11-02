"""EX native-condition evidence and verified sequential five-boss topology."""
from __future__ import annotations

import copy
import hashlib
import math
import json
from pathlib import Path
import zlib

FIVE_CURSE = 'battle/action/enemy/action/mod/five_boss/five_boss_curse$'
DAMAGE_AC = {'ACAbilityDamageResistance': 0, 'ACDirectAttackDamageResistance': 1,
             'ACPowerFlipDamageResistance': 2, 'ACSkillDamageResistance': 3}


def without_five_curse(node, cells, join):
    """Remove only the old mode's periodic aura from private EX clones."""
    if isinstance(node, dict):
        return {key: without_five_curse(value, cells, join) for key, value in node.items()}
    row = cells(node)
    for i in range(109, min(161, len(row))):
        if FIVE_CURSE in row[i]:
            row[i] = ','.join(p for p in row[i].split(',') if not p.startswith(FIVE_CURSE))
    return join(row, isinstance(node, bytes))


def nodes(tree):
    if isinstance(tree, list):
        yield tree
        for child in tree:
            yield from nodes(child)
    elif isinstance(tree, dict):
        for child in tree.values():
            yield from nodes(child)


def strings(tree):
    if isinstance(tree, bytes):
        yield tree.decode('utf-8')
    elif isinstance(tree, str):
        yield tree
    elif isinstance(tree, (list, tuple)):
        for child in tree:
            yield from strings(child)
    elif isinstance(tree, dict):
        for child in tree.values():
            yield from strings(child)


def upper(value):
    if isinstance(value, list) and len(value) == 1:
        return upper(value[0])
    if isinstance(value, dict) and set(value) == {'min', 'max'}:
        return max(upper(value['min']), upper(value['max']))
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    raise ValueError('native resistance uses an unbounded expression')


def condition_bounds(tree):
    """Conservative bound: count every condition regardless of target or branch."""
    damage = [0.0] * 4
    element = [0.0] * 7
    for node in nodes(tree):
        if not node or not isinstance(node[0], str):
            continue
        name = node[0]
        if name in DAMAGE_AC:
            damage[DAMAGE_AC[name]] += max(0, upper(node[2])) * max(1, upper(node[3]))
        elif name == 'ACToleranceOfElement':
            target = int(node[2])
            strength = max(0, upper(node[3])) * max(1, upper(node[4]))
            if strength == 0:
                continue # A known nonpositive resistance cannot close any lane.
            # ToleranceOfElementTarget is an enum, not a bitmask. Native ALL
            # applies to all six; OWNER cannot be bounded without actor context.
            if target in range(1, 7):
                element[target] += strength
            elif target == 254:
                for e in range(1, 7): element[e] += strength
            else:
                raise ValueError(f'unclassified native element target: {target}')
        elif name.startswith('AC') and ('DamageResistance' in name or 'Invincib' in name):
            raise ValueError(f'unclassified native immunity: {name}')
    return damage, element


class NativeLaneAudit:
    def __init__(self, read_raw, parse_dsl, cells):
        self.read_raw, self.parse_dsl, self.cells = read_raw, parse_dsl, cells
        self.cache = {}

    def audit(self, codes, level, general_boss, select_level):
        receipts = []
        viable = {(e, d) for e in range(1, 7) for d in range(4)}
        for code in codes:
            if code not in general_boss:
                raise ValueError(f'{code}: EX hard-condition carrier is not general_boss')
            source = general_boss[code]
            selected = select_level(source, level)
            if selected is None:
                raise ValueError(f'{code}: missing native level')
            source = source[str(selected)] if isinstance(source, dict) else source
            digest = hashlib.sha256(str(source).encode()).hexdigest()
            key = (code, selected, digest)
            if key not in self.cache:
                programs = set()
                for text in strings(source):
                    for cell in self.cells(text):
                        programs.update(p for p in cell.split(',')
                                        if p.startswith('battle/action/') and '$' in p
                                        and not p.startswith(FIVE_CURSE))
                damage, element, evidence = [0.0]*4, [0.0]*7, {}
                while programs:
                    program = sorted(programs)[0]
                    programs.remove(program)
                    logical = program + '.action.dsl.amf3.deflate'
                    if logical in evidence:
                        continue
                    raw = self.read_raw(logical)
                    tree = self.parse_dsl(zlib.decompress(raw, -15))['tree']
                    evidence[logical] = hashlib.sha256(raw).hexdigest()
                    dd, ee = condition_bounds(tree)
                    damage = [a+b for a,b in zip(damage, dd)]
                    element = [a+b for a,b in zip(element, ee)]
                    programs.update(p for p in strings(tree)
                                    if p.startswith('battle/action/') and '$' in p
                                    and not p.startswith(FIVE_CURSE)
                                    and not p.endswith('.deflate'))
                if not evidence:
                    raise ValueError(f'{code}: no native action evidence')
                self.cache[key] = {'code': code, 'level': selected, 'row_sha256': digest,
                                   'damage_bound': damage, 'element_bound': element,
                                   'actions': evidence}
            receipt = self.cache[key]
            receipts.append(receipt)
            viable &= {(e,d) for e in range(1,7) for d in range(4)
                       if receipt['damage_bound'][d] < 1 and receipt['element_bound'][e] < 999}
        if not viable:
            raise ValueError('native Bosses have no common verified output lane')
        return viable, copy.deepcopy(receipts)


def sequential_pair(source_field, field_data, zones, pair, cells, join):
    """Keep the verified terrain/actors, remove the third slot without adding a wave."""
    if not source_field.startswith('mod_five_boss_var_s1_') or len(set(pair)) != 2:
        raise ValueError('EX final requires two distinct verified stage-one actors')
    field = cells(field_data[source_field])
    zone = copy.deepcopy(zones[field[2]])
    if set(zone) != {'0'}:
        raise ValueError('verified sequential donor must have one active wave')
    row = cells(zone['0'])
    originals = [row[i] for i in (24,28,32)]
    if row[22] != '1' or any(code not in originals for code in pair):
        raise ValueError('pair is not part of the donor sequential encounter')
    for slot, code in enumerate(pair):
        for kind, index in ((23+4*slot,24+4*slot),(25+4*slot,26+4*slot)):
            row[kind], row[index] = '1', code
    row[31:35] = ['(None)', '', '(None)', '']
    zone['0'] = join(row, isinstance(zone['0'], bytes))
    return zone


def safe_field_menu(builder):
    """Keep proven field programs; do not add another effective damage immunity."""
    catalog = json.loads(builder.rogue_config_path('rogue_field_menu.json').read_text('utf-8'))
    evidence = {row['program']: row for row in catalog}
    menu = []
    known = {'Attack', 'SkillDamage', 'DirectDamage', 'PowerFlipDamage',
             'SkillGaugeCharging', 'ComboBoost', 'ComboRestriction', 'BuffRejection',
             'HealRejection', 'Piercing', 'Slip', 'Speedup', 'ConvertToAttack',
             'ElementResistance', 'SeparatedTerm2ndDamage'}
    for field in builder.field_menu_all():
        if field[3] not in builder.FIELD_RANDOM_CATS:
            continue
        row = evidence.get(field[1])
        if row is None:
            continue
        if row['cmd'] in {'CreateFlood', 'CreateWindAttack', 'CreateGravitationalField'}:
            menu.append(field)
        elif row['cmd'] in {'StartModifierField', 'StartBuffField'} and row.get('kinds'):
            effects = row['kinds']
            if all(effect['kind'] in known and (effect.get('value') is None or
                   isinstance(effect['value'], (int, float)) and math.isfinite(effect['value'])
                   and effect['value'] > -1) for effect in effects):
                menu.append(field)
    return menu


def output_lane(builder, cards, viable, native_evidence):
    """Check combined soft, hard and stacked reductions against native bounds."""
    damage = builder.damage_resistance_totals(cards)
    elements = builder._resistance_totals_by_target(cards, 'element_resistance')
    if len([d for d in range(4) if damage.get(d, 0) >= 1]) != 2:
        return None
    for e, d in sorted(viable):
        if (elements.get(e, 0) < 99 and damage.get(d, 0) < 1 and
                all(proof['damage_bound'][d] + damage.get(d, 0) < 1 and
                    proof['element_bound'][e] + elements.get(e, 0) < 99
                    for proof in native_evidence)):
            return [e, d]
    return None


def roll_curses(builder, floor, rng, viable, capabilities, runtime, *, native_evidence=(), history=()):
    lanes = builder.abyss_modes.roll_ex_lanes(rng, floor, viable)
    cards = [
        {'name': 'EX属性禁域', 'element_resistance': [(e,999,False) for e in lanes['blocked_elements']],
         'text': '·'.join(builder.ELEMENT_DATA_CN[e] for e in lanes['blocked_elements'])+'属性伤害降至0.1%'},
        {'name': 'EX伤害封锁', 'damage_resistance': [(d,1,False) for d in lanes['immune_damage']],
         'text': '·'.join(builder.COND_KIND_CN[d] for d in lanes['immune_damage'])+'免疫'}]
    pool = builder._curse_pool((floor-1)//10, rng,
        stack_layers=builder.stacked_resistance_layers_for_depth(floor, 30))
    blocked = builder.curse_pacing_blocks(floor, 30, history, tier='hell')
    menu = safe_field_menu(builder)
    def allowed(candidate):
        return (not builder.curse_capability_block(candidate, capabilities) and
                not builder.curse_conflict(cards+[candidate]) and
                not builder.curse_runtime_conflict(cards+[candidate], **runtime) and
                output_lane(builder, cards+[candidate], viable, native_evidence) is not None)
    field_requested = int(builder.required_field_slots(floor, 30) > 0 or rng.random() < .65)
    if field_requested and capabilities['effective']['field_action']:
        for field in rng.sample(menu, len(menu)):
            card = {'name': '深渊法阵', 'caster': field, 'text': f'{field[0]}·{field[2]}'}
            if allowed(card):
                cards.append(card)
                break
    # Element restrictions and the two immunities are owned by the mandatory
    # cards. The complete remaining curse pool is eligible, subject to the
    # normal capability, pacing, attack and combined-output gates.
    optional = [c for c in pool if not c.get('time') and not c.get('caster')
                and not c.get('element_resistance') and not c.get('gimmick')
                and c.get('name') not in blocked]
    rng.shuffle(optional)
    target = 1 + (floor > 10) + (floor > 20)
    selected = 0
    for card in optional:
        if selected >= target:
            break
        if card.get('atk', 1) > 1 and any(c.get('atk', 1) > 1 for c in cards):
            continue
        if not allowed(card):
            continue
        if builder._has_dragon_heart([card]) and not any(
                c.get('caster') and c['caster'][3] != '加成' for c in cards):
            continue
        cards.append(card)
        selected += 1
    lane = output_lane(builder, cards, viable, native_evidence)
    if lane is None:
        raise ValueError('EX curse bundle has no native-compatible output lane')
    lanes['open_lane'] = lane
    result = builder.apply_picks({'capability_profile': capabilities}, cards)
    applied = len(result['casters'])
    result.update(field_requested=field_requested, field_applied=applied,
                  field_deficit=field_requested-applied,
                  field_deficit_reason='no compatible field carrier' if field_requested > applied else None,
                  ex_lanes=lanes)
    if builder.curse_runtime_conflict(cards, **runtime):
        raise ValueError('EX final curse bundle violates runtime limits')
    return result
