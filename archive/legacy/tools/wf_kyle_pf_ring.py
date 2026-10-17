"""Kyle-only native 722 sword PF: API thunder border and direct-hit damage."""
from __future__ import annotations

import hashlib
import zlib

import wf_dsl
import wf_gerald_native_pf_dsl as donor
import wf_kyle_pf_effect as fx
import wf_midautumn_kitlib as kit
import wf_kyle_pf_quick as quick

KEY = 'kyle_moon_thunder_ring'
STRING = 'override_string_' + KEY
TABLE = 'master/skill/power_flip_action.orderedmap'
PROGRAMS = tuple(f'battle/action/power_flip/action/override/{KEY}${KEY}_lv{n}'
                 for n in (1, 2, 3))
TEXT = '赋予自身特殊强化弹射'


def leader_row(ctx):
    # The official native 722 decoder accepts all three sword levels. Kyle's
    # visual/damage replacement is unconditional while he occupies the leader slot.
    return kit.build_row(ctx, 'leader_ability', '141201#1',
        {0: 'kyle_moon', 4: '0', 7: '0', 8: '0', 9: '',
         45: '722', 80: KEY, 81: '1,2,3', 82: STRING}, element=2,
        label='kyle-native-pf')


def build_tree(raw, level):
    if level not in (1, 2, 3):
        raise ValueError('PF level must be 1, 2 or 3')
    if hashlib.sha256(raw).hexdigest() != donor.SOURCE_HASHES[f'knight_lv{level}']:
        raise ValueError('native sword PF fingerprint drift')
    original = wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']
    tree = quick.build(original, level)
    verify_tree(tree, original, level)
    return tree


def verify_tree(tree, original, level):
    quick.verify(tree, original, level)


def install(ctx):
    from wf_seasonal7_kit_zehr import apk_pf_sources
    sources, apk = apk_pf_sources(ctx.root)
    programs = []
    for level in (1, 2, 3):
        tree = build_tree(sources[f'knight_lv{level}'], level)
        ctx.write_dsl(PROGRAMS[level-1], tree)
        programs.append(PROGRAMS[level-1])
    ctx.write_flat(TABLE, {KEY: [list(PROGRAMS)]})
    assets, report = fx.build_assets(ctx.root)
    for logical, raw in assets.items():
        ctx.write_asset('common', logical, raw, owner='kyle-pf-ring')
    report.update(apk=apk, table_key=KEY, programs=programs, buff_target_as=104,
                  regular_damage_bonus='DirectAttack', source_context='DirectAttack',
                  requires_capability='damage-type-rules-v1',
                  direct_hit_counter='one per actual damage hit; missed contacts do not count',
                  native_ranges=list(quick.RADII), native_hits=list(quick.HITS),
                  quick_source='141201 wind_spgirl_4anv', burst_frames=quick.BURST_FRAMES,
                  contact_behavior='one trigger per enemy, fixed contact-point burst; native proximity limits remain',
                  hit_residue_enabled=False,
                  native_multipliers=[3.25, 4.75, 6.3])
    ctx.evidence_write('pf-ring-20260923.json', report)
    return report
