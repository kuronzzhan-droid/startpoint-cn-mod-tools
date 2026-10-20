"""服务端 JSON 的保守三方合并；纯函数，不读写外部路径。"""
import copy

MISSING = object()
GM_IDS = {str(i) for i in range(5990001, 5990007)}
DUMMY_IDS = {str(i) for i in range(1103, 1124)}


def serial(value):
    return {'__missing__': True} if value is MISSING else value


def clean(node, file, path, excluded):
    """剔除精确 GM ID 及其引用行，保留同文件的正常商品。"""
    if isinstance(node, dict):
        if any(not isinstance(v, (list, dict)) and str(v) in GM_IDS for v in node.values()):
            excluded.append({'file': file, 'path': list(path), 'reason': 'GM 武器引用', 'value': node})
            return MISSING
        result = {}
        for k, v in node.items():
            if k in GM_IDS or (file == 'assets/practice_quest.json' and not path and k in DUMMY_IDS):
                excluded.append({'file': file, 'path': list(path + (k,)),
                                 'reason': 'GM 武器' if k in GM_IDS else '训练假人', 'value': v})
                continue
            value = clean(v, file, path + (k,), excluded)
            if value is not MISSING:
                result[k] = value
        if node.get('rewards') and not result.get('rewards'):
            excluded.append({'file': file, 'path': list(path), 'reason': 'GM 武器商品', 'value': node})
            return MISSING
        return result
    if isinstance(node, list):
        result = []
        for i, v in enumerate(node):
            if not isinstance(v, (dict, list)) and str(v) in GM_IDS:
                excluded.append({'file': file, 'path': list(path + (i,)), 'reason': 'GM 武器 ID 列表项', 'value': v})
                continue
            value = clean(v, file, path + (i,), excluded)
            if value is not MISSING:
                result.append(value)
        return result
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
