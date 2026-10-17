"""从现行罗尔夫PF制作可重放修订，仅回写自身候选资产与队长说明。"""
import json
from pathlib import Path
import zlib

import wf_dsl
import wf_mod_tool as core
from wf_character_revision import RevisionCandidate, encode_tree, digest
import wf_rolf_tracking_pf as R

LEADER = 'master/ability/leader_ability.orderedmap'
CAS = 'master/string/custom_ability_string.orderedmap'


def apply_candidate(repo, *, apply=False):
    c = RevisionCandidate(repo, repo/f'work/character_packs/{R.CODE}',
        character_id='179999', code_name=R.CODE, package_version='0.1.1',
        snapshot_key='tracking_pf_20260917', evidence_name='tracking-pf-20260917.json')
    gates, inputs = [], {}
    # This legacy workspace predates live art/balance. Only import exact current
    # PF assets and the owned leader key; never replay the stale whole package.
    for level in (1,2,3):
        logical = R.logical(level)
        raw = core.table_path(c.store, logical).read_bytes()
        inputs[logical] = digest(raw)
        tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']
        revised = R.revise(tree, level)
        gates.append(R.validate(revised, level))
        c.emit('common', logical, encode_tree(revised))
    assets = set()
    for gate in gates:
        for effect in gate['fx_paths']:
            if '/wt26_beam_lv' not in effect:
                continue
            folder = effect.rsplit('/', 1)[0]
            sheet = folder+'/'+folder.rsplit('/', 1)[1]
            assets.update((effect+'.parts.amf3.deflate', effect+'.timeline.amf3.deflate',
                           sheet+'.png', sheet+'.atlas.amf3.deflate'))
    for logical in sorted(assets):
        raw = core.table_path(c.store, logical).read_bytes()
        if logical.endswith('.deflate'):
            wf_dsl.parse_dsl(zlib.decompress(raw, -15))
        inputs[logical] = digest(raw)
        c.emit('common', logical, raw)
    live = core.table_path(c.store, LEADER).read_bytes()
    rows = core.read_csv_lines(core.read_orderedmap_file_from_bytes(live)['179999'])
    override = [r for r in rows if r[45] == '722']
    if len(override) != 1 or override[0][80] != R.PF:
        raise ValueError('Rolf leader override identity changed')
    override[0][82] = R.DESCRIPTION_KEY
    c.splice(LEADER, {'179999': rows})
    c.splice(CAS, {R.DESCRIPTION_KEY: [[R.DESCRIPTION]]})
    return c.finish(dict(inputs=inputs, gates=gates, tracking_step_frames=R.STEP,
        ball_tracking=True, beam_aimed=True, flying=False,
        support_and_damage_preserved=True, existing_beam_art_reused=True), apply=apply)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true')
    print(json.dumps(apply_candidate(Path(__file__).resolve().parents[1], apply=p.parse_args().apply), ensure_ascii=False))
