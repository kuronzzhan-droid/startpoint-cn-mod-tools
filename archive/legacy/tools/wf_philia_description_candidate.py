"""只同步菲莉亚技能/能力说明，不写技能树或数值。"""
import json
from pathlib import Path

import wf_mod_tool as core
from wf_character_revision import RevisionCandidate
import wf_philia_combo_stock as stock
import wf_seasonal7_kit_philia as K


def apply_candidate(repo, *, apply=False):
    c = RevisionCandidate(repo, repo/'work/character_packs/s7-philia',
        character_id='159996', code_name=K.CODE, package_version='1.0.5',
        snapshot_key='description_20260917', evidence_name='description-20260917.json')
    c.splice(K.CAS, {K.CAS_CHANGE_SKILL: [[stock.DESCRIPTION]]})
    rows = core.read_csv_lines(core.read_orderedmap_file_from_bytes(c.read('common', K.TEXT))[c.cid])
    for row in rows:
        for i in (5, 7):
            row[i] = stock.skill_description(row[i])
    c.splice(K.TEXT, {c.cid: rows})
    inner = core.load_nested_table_bytes(c.read('common', K.ACTION), K.ACTION).rows[c.code]
    for level, text in inner.text_rows().items():
        cells = core.read_csv_lines(text)
        cells[0][1] = stock.skill_description(cells[0][1])
        inner.set_text_rows({level: core.write_csv_lines(cells).rstrip('\n')})
    c.splice(K.ACTION, {c.code: core.build_orderedmap(inner)}, codec='action_nested')
    c.server_character_row('cdndata/character_text.json', rows)
    return c.finish(dict(description_only=True, enhancement_in_ability_only=True), apply=apply)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true')
    print(json.dumps(apply_candidate(Path(__file__).resolve().parents[1], apply=p.parse_args().apply), ensure_ascii=False))
