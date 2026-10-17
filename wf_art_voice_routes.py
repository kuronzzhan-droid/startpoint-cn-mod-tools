"""五角色原生双准备音：按已有强化/永恒之火状态分场景，技能程序不变。"""
from __future__ import annotations

from copy import deepcopy

from wf_art_voice_lines import ROLES

CHARACTER_TABLE = 'master/character/character.orderedmap'
SWITCH_TABLE = 'master/skill/switched_action_skill.orderedmap'
FLAME_ID = '119996'


def switch_key(code):
    return code + '_voice_ready'


def build_routes(character_rows, action_rows, unique_rows):
    """输入解码后的三个 master 行映射；返回两张表的自有替换行与证据。

    character_rows: {cid: [[CSV columns]]}
    action_rows: {code: {'1': [[CSV columns]], '2': [[CSV columns]]}}
    unique_rows: {unique_id: [[CSV columns]]}
    不读写任何文件，不改 action_skill 或任何 DSL。
    """
    if unique_rows[FLAME_ID][0][1] != '永恒之火':
        raise ValueError('lion flame identity mismatch')
    characters, switched, evidence = {}, {}, {}
    for role, (cid, code, _persona) in ROLES.items():
        original = character_rows[cid]
        if len(original) != 1 or original[0][0] != code or original[0][8] != code:
            raise ValueError('character/action identity mismatch')
        row = deepcopy(original[0])
        key = switch_key(code)
        if len(row) < 17 or row[9] not in ('(None)', '1' if role == 'lion' else '3'):
            raise ValueError('unreviewed existing character skill switch')
        desired = ['1', '28', FLAME_ID, '', '', key, 'false', 'false'] if role == 'lion' else [
            '3', '', '', '', '', key, 'false', 'false']
        if row[9] != '(None)' and row[9:17] != desired:
            raise ValueError('refuse to replace an existing unrelated skill switch')
        row[9:17] = desired
        characters[cid] = [row]
        programs = {}
        levels = action_rows[code]
        if set(levels) != {'1', '2'}:
            raise ValueError('expected both native evolution levels')
        switched[key] = {}
        for level in ('1', '2'):
            source = levels[level]
            if len(source) != 1 or len(source[0]) != 24:
                raise ValueError('unreviewed ActionSkillValues schema')
            action = source[0]
            # Native SwitchedActionSkillValues is exactly ActionSkillValues
            # program_path + autoplay + changed-by-flag autoplay (columns7:24).
            # Name, icon, description, weights and chain strength continue to
            # come from the unchanged original ActionSkillValues object.
            switched[key][level] = [deepcopy(action[7:24])]
            programs[level] = dict(original_program=action[7], switched_program=action[7],
                min_skill_weight=action[4], max_skill_weight=action[5],
                autoplay_equal=True, same_cached_program_object=True)
        evidence[role] = dict(character_id=cid, code=code, switched_key=key,
            condition='existing_self_unique_119996' if role == 'lion' else 'existing_origin_skill_flag_1',
            normal_slot='battle/skill_ready', switched_slot='battle/matched_skill_ready',
            matched_skill_array_falls_back_to_original=True, levels=programs,
            added_gameplay_conditions=False, added_status_or_ability_rows=False,
            new_client_patch_required=False)
    return dict(character_rows=characters, switched_rows=switched, metadata=evidence)


def metadata():
    return dict(character_table=CHARACTER_TABLE, switched_table=SWITCH_TABLE,
        character_columns=list(range(9, 17)), ready_selection='native condition-based; not random',
        ready_trigger='HUD self skill-point cycle rising edge',
        existing_conditions={role: 'Unique119996' if role == 'lion' else 'ChangeSkillFlag1' for role in ROLES},
        unchanged=['action_skill', 'skill weights', 'skill names and icons', 'skill descriptions',
                   'all DSL bytes', 'abilities', 'status grants'], new_client_capabilities=[])
