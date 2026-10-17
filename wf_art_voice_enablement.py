"""原生配音面板元数据与禁播规则修订；纯函数，不写游戏目录。"""
from copy import deepcopy

from wf_art_voice_lines import ROLES

TEXT_TABLE = 'master/character/character_text.orderedmap'
UI_TABLE = 'master/string/ui_string.orderedmap'
EXCLUDE_KEY = 'character_voice_exclude'
VOICE_ACTOR = 'AI 合成配音'
COL_VOICE_ACTOR = 11
# noPlayVoice also gates production SE and arbitrary scenario sound paths.
# Keep these known non-character audio families covered by the old broad token.
NON_CHARACTER_RULES = ('bgm/character_unique/ruin_girl',
                       'sound_effect/unique/se_ruin_girl_special_attack')


def native_excluded(path, rules):
    """GlobalLogic.noPlayVoice 的已加载状态分支：空 token 也会匹配所有路径。"""
    return any(token in path for token in rules.split('|'))


def narrow_exclusions(rules, character_codes):
    """仅收窄误伤本轮配音的宽规则，保留所有现有非目标角色的禁播状态。

    原生不支持白名单/否定匹配。把宽 token 展开为实际角色的完整 voice
    路径，避免删掉 ruin_girl 后同时放开尚无配音的官方版本。
    """
    codes = set(character_codes)
    targets = {code for _, code, _ in ROLES.values()}
    if not targets <= codes or any(not c or '/' in c or '|' in c for c in codes):
        raise ValueError('missing or unsafe character code')
    tokens = rules.split('|')
    if any(not token for token in tokens):
        raise ValueError('empty exclusion token blocks every native voice')
    paths = {code: f'character/{code}/voice/' for code in codes}
    result = []
    for token in tokens:
        if not any(token in paths[code] for code in targets):
            result.append(token)
            continue
        # This revision reviews only Nephtim's exact broad family rule.
        if token != 'ruin_girl':
            raise ValueError('unreviewed exclusion rule matches a generated voice: '+token)
        result.extend(paths[code] for code in sorted(codes - targets) if token in paths[code])
        result.extend(NON_CHARACTER_RULES)
    if not result:
        raise ValueError('refuse empty native exclusion string')
    output = '|'.join(result)
    for code, path in paths.items():
        expected = False if code in targets else native_excluded(path, rules)
        if native_excluded(path, output) != expected:
            raise ValueError('exclusion revision changes an unrelated character: '+code)
    return output


def text_rows(original):
    """本轮五套生成音频明确标示 AI，不冒用原演员署名。"""
    output = {}
    for cid, _code, _persona in ROLES.values():
        rows = deepcopy(original[cid])
        if len(rows) != 1 or len(rows[0]) != 12:
            raise ValueError('unreviewed CharacterTextValues schema')
        rows[0][COL_VOICE_ACTOR] = VOICE_ACTOR
        output[cid] = rows
    return output


def rows(character_rows, original_text_rows, ui_rows):
    """返回两张 flat 表的精确键补丁，供录音构建器/窄维护接入。"""
    codes = [value[0][0] for value in character_rows.values()]
    source = ui_rows[EXCLUDE_KEY]
    if len(source) != 1 or len(source[0]) != 1:
        raise ValueError('unreviewed UiStringValues schema')
    return {
        TEXT_TABLE: text_rows(original_text_rows),
        UI_TABLE: {EXCLUDE_KEY: [[narrow_exclusions(source[0][0], codes)]]},
    }
