"""服务端 JSON 的保守三方合并；纯函数，不读写外部路径。"""
import copy
import re

MISSING = object()
GM_IDS = {str(i) for i in range(5990001, 5990007)}
DUMMY_IDS = {str(i) for i in range(1103, 1124)}
GM_PATTERN = re.compile(r'(?<!\d)599000[1-6](?!\d)')
# 第三轮逐文件审计：以下均为已有武器/魂珠的识别、显示、使用配套，
# 不构成商品、掉落或奖励。新增任何 GM 引用必须先补充分类，不能静默放行。
GM_SUPPORT_FILES = {
    'assets/equipment_dissolve.json': '已有武器熔炼产生同名魂珠，属于消耗已有武器的使用配套',
    'assets/equipment_element.json': '武器属性注册',
    'assets/equipment_ids.json': '合法装备 ID 注册，不发放装备',
    'assets/equipment_lookup.json': '武器名称、稀有度与种类显示',
    'assets/equipment_max_level.json': '武器强化上限',
    'assets/item_ids.json': '合法魂珠 ID 注册，不发放物品',
    'assets/item_lookup_cnmod.json': '已有魂珠名称显示',
    'assets/item_sale.json': '玩家出售已有魂珠所得玛纳，不是购买商品',
}


def serial(value):
    return {'__missing__': True} if value is MISSING else value


def clean(node, file, path, excluded):
    """第三轮恢复木桩与 GM 本体；只放行逐文件、逐键核实的使用配套。"""
    if isinstance(node, dict):
        result = {}
        for k, v in node.items():
            if GM_PATTERN.search(str(k)):
                assert file in GM_SUPPORT_FILES and len(path) == 0 and k in GM_IDS, (
                    '未分类 GM 引用，停止收入该文件', file, path + (k,))
            result[k] = clean(v, file, path + (k,), excluded)
        return result
    if isinstance(node, list):
        return [clean(v, file, path + (i,), excluded) for i, v in enumerate(node)]
    if GM_PATTERN.search(str(node)):
        allowed_list = file in ('assets/equipment_ids.json', 'assets/item_ids.json') and len(path) == 1
        allowed_dissolve = file == 'assets/equipment_dissolve.json' and len(path) == 2 and path[0] in GM_IDS and path[1] == 'ability_soul_id'
        assert str(node) in GM_IDS and (allowed_list or allowed_dissolve), (
            '未分类 GM 引用，停止收入该行', file, path, node)
    return node


def merge(base, hui, ours, file, path, conflicts, deletions):
    if ours is MISSING:
        if base is not MISSING:
            deletions.append({'file': file, 'path': list(path), 'base': base,
                              'hui': serial(hui), 'resolution': '保留灰版，不执行删除'})
        return hui
    if ours == base or ours == hui:
        return hui
    if isinstance(ours, dict) and isinstance(hui, dict) and (base is MISSING or isinstance(base, dict)):
        b = {} if base is MISSING else base
        result = copy.deepcopy(hui)
        for k in dict.fromkeys([*b, *ours]):
            value = merge(b.get(k, MISSING), hui.get(k, MISSING), ours.get(k, MISSING),
                          file, path + (k,), conflicts, deletions)
            if value is not MISSING:
                result[k] = value
        return result
    if isinstance(base, list) and isinstance(hui, list) and isinstance(ours, list):
        if all(not isinstance(v, (dict, list)) for v in base + hui + ours) and not path:
            result = list(hui)
            for v in ours:
                if v not in base and v not in result:
                    result.append(v)
            for v in base:
                if v not in ours:
                    deletions.append({'file': file, 'path': ['@' + str(v)], 'base': v,
                                      'hui': v if v in hui else {'__missing__': True},
                                      'resolution': '保留灰版，不执行删除'})
            return result
        # character_degree_rewards 等对象列表按稳定身份合并，避免把不同角色位置当成同一列。
        for key in ('character_id', 'id'):
            groups = (base, hui, ours)
            if all(all(isinstance(v, dict) and key in v for v in group)
                   and len({str(v[key]) for v in group}) == len(group) for group in groups):
                maps = [{str(v[key]): v for v in group} for group in groups]
                merged = merge(*maps, file, path, conflicts, deletions)
                order = list(dict.fromkeys([*[str(v[key]) for v in hui], *[str(v[key]) for v in ours]]))
                return [merged[k] for k in order if k in merged]
        if len(base) == len(hui) == len(ours):
            return [merge(b, h, o, file, path + (i,), conflicts, deletions)
                    for i, (b, h, o) in enumerate(zip(base, hui, ours))]
    if hui == base:
        return copy.deepcopy(ours)
    conflicts.append({'file': file, 'path': list(path), 'base': serial(base),
                      'hui': serial(hui), 'ours': serial(ours), 'resolution': '灰优先'})
    return hui


def changed_paths(before, after, path=()):
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for k in dict.fromkeys([*before, *after]):
            result += changed_paths(before.get(k, MISSING), after.get(k, MISSING), path + (k,))
        return result
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        result = []
        for i, (a, b) in enumerate(zip(before, after)):
            result += changed_paths(a, b, path + (i,))
        return result
    return [list(path)]


def path_value(node, path):
    """精确取叶值；路径不存在与 JSON null 分开。"""
    for key in path:
        if isinstance(node, dict) and key in node:
            node = node[key]
        elif isinstance(node, list) and isinstance(key, int) and key < len(node):
            node = node[key]
        else:
            return MISSING
    return node


def apply_five_priority(result, hui, ours, file, rules):
    """只写入已审计的五重叶路径，绝不整表/整商店覆盖。"""
    result = copy.deepcopy(result)
    decisions = []
    for rule in rules:
        path = rule['path']
        expected_hui = rule['hui']
        expected_ours = rule['ours']
        actual_hui, actual_ours = path_value(hui, path), path_value(ours, path)
        visible_hui = {'absent': True} if actual_hui is MISSING else actual_hui
        visible_ours = {'absent': True} if actual_ours is MISSING else actual_ours
        assert visible_hui == expected_hui, ('五重灰基线改变', file, path)
        assert visible_ours == expected_ours, ('五重我方终态改变', file, path)
        assert actual_ours is not MISSING, ('五重规则不得伪造删除', file, path)
        before = path_value(result, path)
        if before != actual_ours:
            current = result
            source = ours
            for index, key in enumerate(path[:-1]):
                source = source[key]
                if isinstance(current, dict):
                    if key not in current:
                        # 新分支按来源结构建立，随后仍逐叶断言；保留灰的旁支。
                        current[key] = [] if isinstance(source, list) else {}
                    current = current[key]
                else:
                    assert isinstance(key, int) and key < len(current), (file, path)
                    current = current[key]
            key = path[-1]
            if isinstance(current, list) and key == len(current):
                current.append(copy.deepcopy(actual_ours))
            else:
                current[key] = copy.deepcopy(actual_ours)
        assert path_value(result, path) == actual_ours, (file, path)
        if visible_hui != visible_ours:
            decisions.append({'file': file, 'path': path, 'hui': visible_hui, 'ours': visible_ours,
                              'default_result': serial(before), 'resolution': '五重行保留我方值',
                              'overrode_default': before != actual_ours})
    return result, decisions
