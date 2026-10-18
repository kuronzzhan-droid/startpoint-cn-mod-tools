"""Final run5 evidence is cumulative, digest-bound, and preserves v34 support."""
from copy import deepcopy
import hashlib
import json

from wf.apk.evidence import v34_evidence, v35e_evidence
from wf.apk.provides import derive_provides
from wf.caps.registry import load_registry
from wf.paths import REPOSITORY


def test_final_evidence_covers_every_new_patch_and_semantic_capability():
    registry = load_registry()
    old = derive_provides(v34_evidence(), registry=registry)
    new = derive_provides(v35e_evidence(), registry=registry)
    old_ids, new_ids = ({c['id'] for c in p['provides']} for p in (old, new))
    assert old_ids < new_ids
    assert len(old_ids) == 142 and len(new_ids - old_ids) == 37
    assert {p['number'] for p in new['patches']} == set(range(1, 132))
    assert new['unresolved'] == new['warnings'] == []
    catalog = json.loads((REPOSITORY / 'wfx_registry.json').read_text('utf-8'))
    semantic = {c['capability_id'] for c in catalog['capabilities'].values()
                if c['status'] == 'local_candidate'}
    assert len(semantic) == 17
    assert semantic <= new_ids - old_ids
    for cid in semantic:
        cap = registry[cid]
        assert cap['data_surface']['allowed_tables']
        assert cap['form']['fields']
        assert cap['golden'] and cap['rules'] and cap['provided_by']['methods']
        assert all(m['sha256'] for m in cap['provided_by']['methods'])


def test_inherited_method_updates_require_final_swf_and_final_method():
    original = v35e_evidence()
    key = 'client.unique.hidden@1'
    assert key in {c['id'] for c in derive_provides(original)['provides']}
    unknown_swf = deepcopy(original)
    unknown_swf['swf_sha256'] = '0' * 64
    assert key not in {c['id'] for c in derive_provides(unknown_swf)['provides']}
    stale_method = deepcopy(original)
    old_patch = next(p for p in v34_evidence()['patches'] if p['number'] == 58)
    next(p for p in stale_method['patches'] if p['number'] == 58)['methods'] = old_patch['methods']
    assert key not in {c['id'] for c in derive_provides(stale_method)['provides']}


def test_hidden_icons_require_both_final_filter_and_original_filtered_count():
    record = v35e_evidence()
    key = 'client.wfx.hidden_unique_icons@1'
    cap = load_registry()[key]
    assert cap['provided_by']['patches'] == [58, 131]
    assert any(m['label'] == 'MemberImpl/getTotalConditions' for m in cap['provided_by']['methods'])
    record['patches'] = [p for p in record['patches'] if p['number'] != 58]
    assert key not in {c['id'] for c in derive_provides(record)['provides']}


def test_fallbacks_are_bound_to_profile_and_actual_signed_package_hashes():
    config = json.loads((REPOSITORY / 'client_profiles.json').read_text('utf-8'))
    assert config['default_client_profile'] == 'test-v34'
    for name in ('test-v34', 'test-v35e'):
        profile = config['profiles'][name]
        path = REPOSITORY / profile['provides_fallback']
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == profile['provides_fallback_sha256']
        document = json.loads(data)
        assert document['source']['sha256'] == profile['evidence']['apk_sha256']
        assert document['source']['swf_sha256'] == profile['evidence']['swf_sha256']
        assert document['source']['kind'] == 'apk'
        assert document['unresolved'] == []
        assert 'D:' not in document['source']['path']
