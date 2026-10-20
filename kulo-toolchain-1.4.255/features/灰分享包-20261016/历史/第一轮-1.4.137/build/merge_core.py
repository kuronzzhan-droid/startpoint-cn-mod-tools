"""逐嵌套行、逐 CSV 列的三方合并；同列冲突一律保留灰。"""
import copy
from common import cells, join

MISSING = object()

def visible(x):
    return {'absent': True} if x is MISSING else x

def merge(base, hui, ours, path, conflicts, changes):
    if ours == base or hui == ours:
        return copy.deepcopy(hui) if hui is not MISSING else MISSING
    if hui == base:
        changes.append({'path': path, 'action': 'delete' if ours is MISSING else 'add' if base is MISSING else 'modify'})
        return copy.deepcopy(ours) if ours is not MISSING else MISSING
    if all(isinstance(x, dict) for x in (base, hui, ours)):
        result = copy.deepcopy(hui)
        for key in list(base) + [k for k in ours if k not in base]:
            b, h, o = (x.get(key, MISSING) for x in (base, hui, ours))
            if b == o:
                continue
            value = merge(b, h, o, path + [key], conflicts, changes)
            if value is MISSING:
                result.pop(key, None)
            else:
                result[key] = value
        return result
    if all(isinstance(x, str) for x in (base, hui, ours)):
        try:
            bb, hh, oo = map(cells, (base, hui, ours))
        except Exception:
            bb = hh = oo = []
        if len(bb) == len(hh) == len(oo) and len(bb) > 1:
            result = list(hh)
            for col, (b, h, o) in enumerate(zip(bb, hh, oo)):
                if o == b or o == h:
                    continue
                if h == b:
                    result[col] = o
                    changes.append({'path': path, 'column': col, 'action': 'modify'})
                else:
                    conflicts.append({'path': path, 'column': col, 'base': b, 'hui': h, 'ours': o, 'resolution': 'hui'})
            return join(result) if result != hh else hui
    conflicts.append({'path': path, 'base': visible(base), 'hui': visible(hui), 'ours': visible(ours), 'resolution': 'hui'})
    return copy.deepcopy(hui) if hui is not MISSING else MISSING

def neutralize(node, baseline, path):
    """让被排除项等于共同祖先，合并时不携带这部分我方增量。"""
    if not path:
        return copy.deepcopy(baseline)
    cur = node
    old = baseline
    for k in path[:-1]:
        if not isinstance(cur, dict) or k not in cur:
            return node
        cur = cur[k]
        old = old.get(k, {}) if isinstance(old, dict) else {}
    if isinstance(cur, dict):
        key = path[-1]
        if isinstance(old, dict) and key in old:
            cur[key] = copy.deepcopy(old[key])
        else:
            cur.pop(key, None)
    return node

def changed_rows(before, after, path=()):
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for key in list(before) + [k for k in after if k not in before]:
            result.extend(changed_rows(before.get(key, MISSING), after.get(key, MISSING), path + (key,)))
        return result
    if isinstance(after, dict):
        return [r for k,v in after.items() for r in changed_rows(MISSING, v, path+(k,))]
    if isinstance(before, dict):
        return [r for k,v in before.items() for r in changed_rows(v, MISSING, path+(k,))]
    return [{'path':list(path),'action':'delete' if after is MISSING else 'add' if before is MISSING else 'modify',
             'before':visible(before), 'after':visible(after)}]
