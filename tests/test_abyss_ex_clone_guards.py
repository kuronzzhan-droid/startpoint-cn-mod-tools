"""EX audits and final output must use the same stripped private donors."""
import copy
import hashlib
import zlib

import pytest

from wf.tools.rogue import abyss_ex as ex
from wf.tools.rogue import rogue_build as b


CURSE = 'battle/action/enemy/action/mod/five_boss/five_boss_curse$'
BUFF = 'battle/action/enemy/action/mod/five_boss_v3/fb3_buff$'
NATIVE = 'battle/action/enemy/action/native$main'


def row(**columns):
    result = [''] * 162
    result[111] = NATIVE
    for column, value in columns.items():
        result[int(column[1:])] = value
    return b.join(result, False)


@pytest.mark.parametrize('as_bytes', [False, True])
def test_strip_both_prefixes_per_item_in_all_action_columns(as_bytes):
    source = row(c108=BUFF+'keep', c109=CURSE+'s1,'+BUFF+'entrance',
                 c111=NATIVE+','+BUFF+'entrance_self,'+CURSE+'s1',
                 c160=BUFF+'entrance', c161=CURSE+'keep')
    if as_bytes:
        source = source.encode()
    tree = {'80': source, '100': {'1': source}}
    original = copy.deepcopy(tree)
    stripped = ex.without_five_curse(tree, b.cells, b.join)
    assert tree == original
    for leaf in (stripped['80'], stripped['100']['1']):
        cells = b.cells(leaf)
        assert isinstance(leaf, bytes) == as_bytes
        assert cells[108] == BUFF+'keep' and cells[161] == CURSE+'keep'
        assert cells[109] == cells[160] == ''  # (None) is an invalid action (8100).
        assert cells[111] == NATIVE


def auditor(tree):
    reads = []
    def read(logical):
        reads.append(logical)
        assert logical == NATIVE+'.action.dsl.amf3.deflate'
        return zlib.compress(b'native')[2:-4]
    return ex.NativeLaneAudit(read, lambda _: {'tree': tree}, b.cells, b.join), reads


def test_audit_hash_and_bounds_match_stripped_clone_and_filter_recursive_refs():
    source = row(c109=CURSE+'s1,'+BUFF+'entrance')
    clone = ex.without_five_curse(source, b.cells, b.join)
    audit, reads = auditor([['ACToleranceOfElement', [600], 254, [.2], [1]],
                            [BUFF+'entrance_self', CURSE+'s1']])
    lanes, proof = audit.audit(['source'], 100, {'source': {'100': source}}, b.select_surjective_level)
    clone_lanes, clone_proof = audit.audit(['clone'], 100, {'clone': {'100': clone}}, b.select_surjective_level)
    assert lanes == clone_lanes
    assert proof[0]['row_sha256'] == clone_proof[0]['row_sha256'] == hashlib.sha256(str(clone).encode()).hexdigest()
    assert proof[0]['element_bound'] == [0, .2, .2, .2, .2, .2, .2]
    assert set(reads) == {NATIVE+'.action.dsl.amf3.deflate'}


def test_three_argument_auditor_uses_the_same_csv_encoding():
    audit, _ = auditor([])
    legacy = ex.NativeLaneAudit(audit.read_raw, audit.parse_dsl, b.cells)
    source = {'100': row(c109=CURSE+'s1,'+BUFF+'entrance')}
    assert legacy.audit(['boss'], 100, {'boss': source}, b.select_surjective_level) == audit.audit(
        ['boss'], 100, {'boss': source}, b.select_surjective_level)


@pytest.mark.parametrize('strength,accepted', [(98.9999, True), (99, False), (99.0001, False)])
def test_native_selection_uses_strict_99_exit_before_curse_roll(strength, accepted):
    audit, _ = auditor([['ACToleranceOfElement', [600], 254, [strength], [1]]])
    if accepted:
        lanes, _ = audit.audit(['boss'], 100, {'boss': {'100': row()}}, b.select_surjective_level)
        assert lanes
    else:
        with pytest.raises(ValueError, match='no common verified output lane'):
            audit.audit(['boss'], 100, {'boss': {'100': row()}}, b.select_surjective_level)


def test_remaining_native_invincibility_is_still_rejected():
    audit, _ = auditor([['ACInvincible', [600]]])
    with pytest.raises(ValueError, match='ACInvincible'):
        audit.audit(['boss'], 100, {'boss': {'100': row(c109=BUFF+'entrance')}}, b.select_surjective_level)


def final_tables():
    zone = [''] * 35
    zone[22:27] = ['1', '1', 'private_boss30', '1', 'private_boss30']
    zone[27:31] = ['1', 'private_boss30_2', '1', 'private_boss30_2']
    return ({'field': 'name,terrain,zone'}, {'zone': {'0': b.join(zone, False)}},
            {'private_boss30': {'100': row()}, 'private_boss30_2': {'100': row()}})


def check_final(fd, zones, gb):
    ex.assert_final_clones('field', fd, zones, gb,
                          ['private_boss30', 'private_boss30_2'], 'private_',
                          b.cells, b.zone_boss_slots)


def test_final_zone_requires_two_actual_stripped_clones():
    fd, zones, gb = final_tables()
    check_final(fd, zones, gb)
    gb['private_boss30_2']['100'] = row(c109=BUFF+'entrance')
    with pytest.raises(ValueError, match='mode action'):
        check_final(fd, zones, gb)


def test_final_zone_cannot_reference_uncloned_donor_or_another_pair():
    fd, zones, gb = final_tables()
    zones['zone']['0'] = zones['zone']['0'].replace('private_boss30_2', 'mod_fb_water_s1')
    with pytest.raises(ValueError, match='clone'):
        check_final(fd, zones, gb)


def test_final_check_covers_every_clone_level_and_action_column():
    fd, zones, gb = final_tables()
    gb['private_boss30']['80'] = row(c160=CURSE+'s1')
    with pytest.raises(ValueError, match='mode action'):
        check_final(fd, zones, gb)


def test_final_zone_checks_multiplayer_aliases_too():
    fd, zones, gb = final_tables()
    cells = b.cells(zones['zone']['0'])
    cells[26] = 'mod_fb_water_s1'
    zones['zone']['0'] = b.join(cells, False)
    with pytest.raises(ValueError, match='clone slots'):
        check_final(fd, zones, gb)


def test_final_zone_rejects_extra_multiplayer_only_slot():
    fd, zones, gb = final_tables()
    cells = b.cells(zones['zone']['0'])
    cells[33:35] = ['1', 'mod_fb_thunder_s1']
    zones['zone']['0'] = b.join(cells, False)
    with pytest.raises(ValueError, match='clone slots'):
        check_final(fd, zones, gb)
