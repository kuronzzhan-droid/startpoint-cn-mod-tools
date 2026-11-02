"""Shared, deterministic policy for the normal/EX split (HP before curses)."""
from __future__ import annotations
from copy import deepcopy
import math

NORMAL_EVENT = 700099
EX_EVENT = 700100
TOKEN = 2370099
TICKETS = {999013, 999014}
NORMAL_ITEMS = {TOKEN, *TICKETS, 10002, 12001, 99, 52, 55, 58, 61, 64, 67}

def set_finite_quest_prerequisite(row: list[str], event: int, floor: int) -> None:
    """The first Boss may use a later-round donor; never inherit its gate."""
    if not 1 <= floor <= 98:
        raise ValueError('finite floor must be 1..98')
    row[9:14] = (['(None)', '', '', '', '(None)'] if floor == 1 else
                 ['16', str(event), '', str(floor-1), str(event*1000+floor-1)])

def base_hp(mode: str, floor: int) -> int:
    if not 1 <= floor <= 30:
        raise ValueError('finite floor must be 1..30')
    if mode == 'normal':
        # Floor 1 retains the existing warmup; Boss curve starts at floor 2.
        if floor == 1:
            raise ValueError('normal warmup has no Boss HP budget')
        return round(2_000_000_000 + (floor - 2) * 8_000_000_000 / 28)
    if mode == 'ex':
        per_boss = round(20_000_000_000 + (floor - 1) * 15_000_000_000 / 29)
        return per_boss * (2 if floor == 30 else 1)
    raise ValueError(f'unknown abyss mode: {mode}')

def attack_factor(mode: str, floor: int) -> float:
    if not 1 <= floor <= 30 or mode not in ('normal', 'ex'):
        raise ValueError('invalid mode/floor')
    return 1.0 if mode == 'normal' else (1.10 if floor <= 10 else 1.15 if floor <= 20 else 1.20)

def roll_ex_lanes(rng, floor: int, viable_lanes: set[tuple[int, int]]) -> dict:
    """Pick from externally verified native damage lanes; no invented fallback proof."""
    if not 1 <= floor <= 30 or not viable_lanes or any(
        e not in range(1,7) or d not in range(4) for e,d in viable_lanes
    ):
        raise ValueError('EX requires a verified native element/damage lane')
    element, damage = rng.choice(sorted(viable_lanes))
    # Increasing pressure by band; counts always stay within the agreed bounds.
    extra_probability = (0.25, 0.50, 0.75)[(floor-1)//10]
    elements = sorted(rng.sample([e for e in range(1,7) if e != element],
                                4 if rng.random() < extra_probability else 3))
    damages = sorted(rng.sample([d for d in range(4) if d != damage],
                               2))
    return {'blocked_elements': elements, 'immune_damage': damages,
            'open_lane': [element, damage]}

def is_five_boss_source(field: str, bosses=(), provenance=()) -> bool:
    """Include donor ancestry so private clones cannot bypass the source gate."""
    return any(str(value).startswith(('mod_five_boss_', 'mod_fb_'))
               for value in (field, *bosses, *provenance))

def scaled_chance(value, scale):
    if isinstance(value, dict):
        return {**value, 'start': round(value['start']*scale, 12),
                'per_round': round(value.get('per_round',0)*scale, 12)}
    return round(float(value)*scale, 12)


def additional_reward_rows(config: dict) -> dict:
    """Compile every actual server (group,index) reference for the result reader.

    The response supplies the rolled quantity; each master entry defines one
    item unit. Missing groups crash AdditionalRewardLogic with C8601.
    """
    result = {}
    for drop in config.get('per_round_drops', []):
        group = drop.get('additional_reward_group_id')
        if not group:
            continue
        if drop.get('type') != 'item':
            raise ValueError('unverified additional reward type')
        start = int(drop.get('additional_reward_index_start', 1))
        for index in range(start, start+int(drop.get('slots', 1))):
            key = str(index)
            row = f'abyss_ex_reward_{index},0,{int(drop["id"])},5,1'
            entries = result.setdefault(str(group), {})
            if key in entries and entries[key] != row:
                raise ValueError('conflicting additional reward slot')
            entries[key] = row
    return result

def split_rewards(baseline: dict) -> dict:
    """Derive both modes from a frozen pre-split merged snapshot, never sequentially."""
    normal=deepcopy(baseline['config'])
    ex=deepcopy(baseline['config'])
    normal['per_round_drops']=[]
    for row in baseline['config']['per_round_drops']:
        if row['id'] not in NORMAL_ITEMS:
            continue
        row=deepcopy(row)
        if row['id'] == TOKEN:
            # Preserve exact expected yield without rounding 1 token down to zero.
            guaranteed=int(row.get('guaranteed_slots',0))
            scaled=guaranteed*0.7
            whole=math.floor(scaled+1e-9)
            start=int(row.get('additional_reward_index_start',1))
            if whole:
                normal['per_round_drops'].append({**row,'slots':whole,'guaranteed_slots':whole,'chance':1})
            fraction=round(scaled-whole,12)
            if fraction:
                normal['per_round_drops'].append({**row,'slots':1,'guaranteed_slots':0,'chance':fraction,
                    'additional_reward_index_start':start+whole})
            remaining=int(row.get('slots',1))-guaranteed
            if remaining:
                normal['per_round_drops'].append({**row,'slots':remaining,'guaranteed_slots':0,
                    'chance':scaled_chance(row.get('chance',1),.7),
                    'additional_reward_index_start':start+guaranteed})
        else:
            if row['id'] in TICKETS:
                if row.get('guaranteed_slots',0):
                    raise ValueError('fixed ticket source requires explicit stochastic conversion')
                row['chance']=scaled_chance(row.get('chance',1),.7)
            normal['per_round_drops'].append(row)
    normal['folder_clear_random']=[deepcopy(row) for row in baseline['config'].get('folder_clear_random',[])
        if set(row['pool']) <= NORMAL_ITEMS]
    # Dream emblems are a fixed 800 clear reward; no random supplement.
    normal['folder_clear_chance']=[{**row,'chance':scaled_chance(row['chance'],.7) if row['id'] in TICKETS else row['chance']}
        for row in normal.get('folder_clear_chance',[]) if row['id'] in NORMAL_ITEMS]
    for row in ex['per_round_drops']:
        if row['id'] in {TOKEN,*TICKETS}:
            row['count']*=2
        row['additional_reward_group_id']=237010000
    for row in ex.get('folder_clear_chance',[]):
        if row['id'] in {TOKEN,*TICKETS}:
            row['count']*=2
    ex['show_reward_list_endless']=False
    ex['pool_draws']=0
    ex['drop_pool']=[]
    fixed=baseline['fixed']
    normal_fixed=[{**row,'count':800 if row['id']==99 else round(row['count']*.7) if row['id']==TOKEN else row['count']}
        for row in fixed if row['id'] in NORMAL_ITEMS]
    ex_fixed=[{**row,'count':row['count']*2 if row['id'] in {TOKEN,*TICKETS} else row['count']} for row in fixed]
    return {'normal':normal,'ex':ex,'normal_fixed':normal_fixed,'ex_fixed':ex_fixed}
