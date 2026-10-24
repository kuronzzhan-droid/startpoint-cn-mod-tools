"""Audit incomplete GBF native drafts without replacing installable gameplay.

Only evidence is emitted. The donor-based package remains blocked by its
required client capability until the compatibility decisions and integration land.
Structural validation here is deliberately not gameplay acceptance.
"""
from pathlib import Path

import wf_client_legality as L
import wf_dsl
import wf_seasonal7_common as C
from wf_seasonal7_kit_philia import signature_problems, scope_problems

# 冈达葛萨的机制已在 ``wf_gbf_kit_ghandagoza`` 落地（固有状态、629 开场树、421 等价乘区、
# 面板文案全部进包），不再是被阻断的草稿，所以这里没有它的条目。
# 两个 GBF 角色的机制都已装进各自的包（wf_gbf_kit_ghandagoza / wf_gbf_kit_soriz），
# 这里不再留任何发布阻断项；本模块只剩老草稿的静态校验工具。
BLOCKERS: dict[str, list[str]] = {}


def draft_subject_problems(tree):
    """Check target slots absent from the legacy generic binding checker."""
    slots = {name:1 for name in ('CreateBarrier', 'CreateCondition', 'DeleteCondition',
             'CreateRatioAttack', 'CreateRatioHeal', 'CreateNormalAttack', 'StopBall',
             'ConditionalsHealthPointRatioOf')}
    slots['ShowEffect'] = 3
    errors = []
    def visit(node, bound):
        if not isinstance(node, list) or not node:
            return
        tag = node[0] if isinstance(node[0], str) else ''
        if tag == 'FindAllSubjects':
            visit(node[-1], bound | {node[1]})
            return
        if tag == 'CreateHitArea' and len(node) == 27:
            visit(node[20], bound | {node[21]})
            visit(node[23], bound | {node[21], node[22]})
            return
        if tag in slots and len(node) > slots[tag]:
            subject = node[slots[tag]]
            if isinstance(subject, int) and subject >= 0 and subject not in bound:
                errors.append(f'{tag}: unbound subject {subject}')
        for child in node:
            visit(child, bound)
    visit(tree, set())
    return errors


def check_draft(leader, abilities, programs):
    errors = []
    for table, groups in [('leader_ability', [leader]), ('ability', abilities.values())]:
        for rows in groups:
            for row in rows:
                errors.extend(L.client_legality_problems(table, row))
                errors.extend(L.declared_block_field_problems(table, row))
                errors.extend(L.ability_element_column_problems(table, row, 1))
    for path, tree in programs.items():
        problems = (signature_problems(tree) + scope_problems(tree) + draft_subject_problems(tree)
                    + L.action_dsl_subject_binding_problems(tree)
                    + L.action_dsl_hit_area_target_problems(tree)
                    + L.action_dsl_element_problems(tree, character_element=1)
                    + wf_dsl.player_side_dsl_problems(tree))
        errors.extend(f'{path}: {p}' for p in problems)
        C.amf_bytes(tree)  # Lossless encode/decode check, including delayed blocks.
    return errors


def build(pack, source):
    code = pack.spec.code
    import wf_gbf_duo_dsl as D
    if code == 'ghandagoza':
        import wf_gbf_ghandagoza as module
        skill = D.ghandagoza_skill()
    else:
        import wf_gbf_soriz as module
        skill = D.soriz_skill(pack)
    leader, abilities, programs = module.build_rows(pack)
    programs = {**programs, f'battle/action/skill/action/rare5/{code}${code}_draft': skill}
    errors = check_draft(leader, abilities, programs)
    draft = {'status': 'incomplete-not-installable', 'code': code, 'element': 'water',
             'leader': leader, 'abilities': abilities, 'programs': programs,
             'blockers': BLOCKERS.get(code, []), 'structural_errors': errors,
             'unique_conditions_not_integrated': True, 'runtime_verified': False}
    pack.write_evidence('native-gameplay-draft.json', draft)
    result = {'status': 'blocked-gameplay-incomplete', 'gameplay_complete': False,
              'runtime_verified': False, 'release_ready': False,
              'summary': '资源齐备；机制草稿只写证据，安装包仍为不可发布的模板框架。',
              'blockers': BLOCKERS.get(code, []), 'structural_errors': errors,
              'row_counts': {'leader': len(leader), 'abilities': {k:len(v) for k,v in abilities.items()}},
              'program_count': len(programs), 'source_directory': str(Path(source))}
    pack.write_evidence('kit-report.json', result)
    # Refresh manifests to retain the unresolved-capability publication gate.
    import wf_seasonal7_manifest as manifest
    manifest.build(pack)
    if errors:
        raise ValueError(errors)
    return result
