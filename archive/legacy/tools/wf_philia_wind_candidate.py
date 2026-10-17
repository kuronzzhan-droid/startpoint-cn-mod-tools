"""修订菲莉亚五个 DSL 与对应三层说明；保留能力、语音及图像资产。"""
import json
from pathlib import Path
import zlib

import wf_dsl
import wf_mod_tool as core
from wf_character_revision import RevisionCandidate, encode_tree
import wf_seasonal7_kit_philia as K
from wf_philia_wind_revision import PF_TEXT, revise_skill, revise_pf, skill_description
import wf_philia_combo_stock as stock


def apply_candidate(repo, *, apply=False):
    c = RevisionCandidate(repo, repo/'work/character_packs/s7-philia',
        character_id='159996', code_name=K.CODE, package_version='1.0.3',
        snapshot_key='wind_impact_20260917', evidence_name='wind-impact-20260917.json')
    reports = []
    for kind, programs, transform in (
        ('skill', [f'{K.SKILL_SRC}{K.CODE}${K.CODE}_{n}' for n in (1, 2)], revise_skill),
        ('pf', K.PF_PROGRAMS, revise_pf),
    ):
        for program in programs:
            logical = wf_dsl.dsl_logical(program)
            tree = wf_dsl.parse_dsl(zlib.decompress(c.read('common', logical), -15))['tree']
            updated = transform(tree)
            gates = K.dsl_gates(updated)
            errors = K.dsl_gate_failures(gates)
            if errors:
                raise ValueError(f'{program}: {errors}')
            c.emit('common', logical, encode_tree(updated))
            reports.append(dict(kind=kind, program=program, gates=gates))
    c.splice(K.CAS, {K.CAS_PF_OVERRIDE: [[PF_TEXT]], K.CAS_CHANGE_SKILL: [[stock.DESCRIPTION]]})
    abilities = core.read_orderedmap_file_from_bytes(c.read('common', K.ABILITY))
    a1, a4 = stock.revise_abilities(core.read_csv_lines(abilities[c.cid+'1']),
                                  core.read_csv_lines(abilities[c.cid+'4']))
    for row in a1 + a4:
        if K.row_problems('ability', row):
            raise ValueError(K.row_problems('ability', row))
    c.splice(K.ABILITY, {c.cid+'1': a1, c.cid+'4': a4})
    c.splice(stock.UNIQUE, {str(stock.UID): stock.unique_row()})
    source = c.ws.root/'source/wind-stock-icon.png'
    if not source.is_file():
        raise ValueError('wind-stock icon has not been prepared')
    from wf_seasonal7_common import png_store_bytes
    from PIL import Image
    icon = Image.open(source).convert('RGBA')
    if icon.size != (48, 48):
        raise ValueError('wind-stock icon must match official 48x48')
    c.emit('common', stock.ICON+'.png', png_store_bytes(icon))
    rows = core.read_csv_lines(core.read_orderedmap_file_from_bytes(c.read('common', K.TEXT))[c.cid])
    for row in rows:
        for index in (5, 7):
            row[index] = stock.skill_description(skill_description(row[index]))
    c.splice(K.TEXT, {c.cid: rows})
    nested = core.load_nested_table_bytes(c.read('common', K.ACTION), K.ACTION)
    inner = nested.rows[c.code]
    for level, text in inner.text_rows().items():
        cells = core.read_csv_lines(text)
        cells[0][1] = stock.skill_description(skill_description(cells[0][1]))
        inner.set_text_rows({level: core.write_csv_lines(cells).rstrip('\n')})
    c.splice(K.ACTION, {c.code: core.build_orderedmap(inner)}, codec='action_nested')
    c.server_character_row('cdndata/character_text.json', rows)
    return c.finish(dict(skill_speed=[18, 12], skill_stop_frames=15, skill_interval_frames=[9, 24],
        skill_count=10, skill_range_unchanged=True, damage_multipliers_unchanged=True,
        skill_piercing=True, skill_homing=False, skill_direction='world_up_AB_0',
        stock=dict(unique_id=stock.UID, per_hit=2, cost_per_flip=1, combo_per_flip=15,
                   a4_old_boost_removed=True, active_skill_only=True, requires_a1_enhancement=True),
        pf_piercing=True, pf_homing=False, rain_anchor='each_blade_hit_position',
        reports=reports), apply=apply)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(apply_candidate(Path(__file__).resolve().parents[1], apply=args.apply), ensure_ascii=False))
