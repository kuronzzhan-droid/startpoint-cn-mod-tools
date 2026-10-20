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
