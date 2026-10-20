"""识别五重专属叶行，固定我方 219 终态；不把整张共享表设为我方优先。"""
import json
from pathlib import Path
import re
import sys
import zipfile

sys.dont_write_bytecode = True
from common import ROOT, OUT, View, base_raw, logical_index, member, q, sha, write_json
from merge_core import MISSING, changed_rows, merge as client_merge

ABSENT = {'absent': True}
ITEM_IDS = {'10000143', '10000144', '10000145', '10000146', '10000147', '10000310'}
REWARD_IDS = {'590010000'}
TOKENS = ('five_boss', 'mod_fb_', 'mod_fb2_', 'mod_fb3_', 'fb3_buff')


def semantic(value):
    if not isinstance(value, str):
        return False
    return (any(token in value for token in TOKENS)
            or value.startswith(('五重决战', '五王连战'))
            or re.match(r'^1099\d+,\d+,五重决战', value) is not None)


def get(node, path):
    for key in path:
        if isinstance(node, dict) and key in node:
            node = node[key]
        elif isinstance(node, list) and isinstance(key, int) and key < len(node):
            node = node[key]
        else:
            return ABSENT
    return node


def leaves(node, path=()):
    if isinstance(node, dict) and node:
        for key, value in node.items():
            yield from leaves(value, path + (key,))
    elif isinstance(node, list) and node:
        for key, value in enumerate(node):
            yield from leaves(value, path + (key,))
    else:
        yield path, node


def has_exact_id(node, ids):
    return any(not isinstance(v, (dict, list)) and str(v) in ids for _, v in leaves(node))


def rule_fields(base, hui, ours, path, reason):
    b, h, o = (get(n, path) for n in (base, hui, ours))
    values = [MISSING if v == ABSENT else v for v in (b, h, o)]
    default = client_merge(*values, list(path), [], [])
    return {'path': list(path), 'base': b, 'hui': h, 'ours': o,
            'reason': reason, 'resolution': 'ours', 'is_difference': h != o,
            'row_level_conflict_risk': h != o and (b == o or (h != b and o != b)),
            'would_default_choose_hui': h != o and default == values[1],
            'would_override_default': default != values[2]}


def client_audit(hui, ours, paths):
    tables = {}
    for m in sorted(set(hui.index) | set(ours.index)):
        logical = paths.get(m, '')
        if not logical.endswith('.orderedmap'):
            continue
        try:
            o = q.parse_node(ours.raw(m))
            h = q.parse_node(hui.raw(m))
            b = q.parse_node(base_raw(m)) if base_raw(m) is not None else {}
        except (ValueError, TypeError):
            continue
        if isinstance(o, dict):
            tables[m] = (logical, b, h, o)
    quests = set()
    for logical, _, _, o in tables.values():
        if logical == 'master/quest/boss_battle_quest.orderedmap':
            for _, value in leaves(o):
                if semantic(value) and re.match(r'^1099\d+,', value):
                    match = re.match(r'(\d+),', value)
                    if match:
                        quests.add(match.group(1))
    specific = ITEM_IDS | REWARD_IDS | quests
    rules = []
    for m, (logical, b, h, o) in tables.items():
        for path, value in leaves(o):
            # 魂珠商店复用了五重缩略图/背景；这不使魂珠行成为五重修复。
            if isinstance(value, str) and (value.startswith(('魂珠兑换', 'mod_soul_exchange'))
                                          or value.startswith('1098001,')):
                continue
            reason = None
            if any(semantic(str(k)) for k in path) or semantic(value):
                reason = '五重专属命名空间/文本叶行，固定我方 1.4.219 终态'
            elif any(str(k) in specific for k in path):
                reason = '五重副本、门票、奖励或兑换对象的精确 ID 叶行'
            elif isinstance(value, str) and specific.intersection(re.split(r'[,\s]+', value)):
                reason = '精确引用五重门票/奖励/副本 ID 的配套叶行'
            if reason:
                rules.append({'member': m, 'logical': logical, **rule_fields(b, h, o, path, reason)})
    return rules, quests, tables


def source_edge_audit(ours, paths):
    previous = {}
    records, binary = [], []
    for source in ours.sources:
        with zipfile.ZipFile(source['path']) as archive:
            for m in archive.namelist():
                raw = archive.read(m)
                if 'five-boss' in source['name']:
                    before = previous.get(m, base_raw(m))
                    try:
                        old = q.parse_node(before) if before is not None else {}
                        new = q.parse_node(raw)
                        changes = changed_rows(old, new)
                        records.append({'archive': source['name'], 'version': source['version'],
                                        'member': m, 'logical': paths.get(m), 'changed_leaf_count': len(changes),
                                        'changed_paths': [row['path'] for row in changes]})
                    except ValueError:
                        # 此成员为 ActionDsl 的 raw-deflate AMF，不能按 orderedmap 伪造行值。
                        binary.append({'archive': source['name'], 'member': m,
                                       'logical': paths.get(m, '未核实'), 'sha256': sha(raw),
                                       'terminal_sha256': sha(ours.raw(m)),
                                       'terminal_matches_hui': ours.raw(m) == View('hui').raw(m)})
                previous[m] = raw
    return records, binary


def server_roots(node, ids, path=()):
    """选实体根；绝不因深层出现五重词而把整文件/整商店分类选中。"""
    if isinstance(node, dict):
        direct_semantic = any(semantic(v) for v in node.values() if not isinstance(v, (dict, list)))
        shop = ('costs' in node or 'rewards' in node) and has_exact_id(node, ITEM_IDS)
        if path and (str(path[-1]) in ids or direct_semantic or shop):
            yield path, node
            return
        for k, v in node.items():
            if str(k) in ids:
                yield path + (k,), v
            else:
                yield from server_roots(v, ids, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, (dict, list)):
                yield from server_roots(v, ids, path + (i,))
    elif path and semantic(node):
        yield path, node


def server_audit(quests, hui_ref):
    import server_merge as sm
    rules, roots, membership = [], [], []
    tree = sm.tree(sm.ANCESTOR)
    hui_tree = sm.tree(hui_ref)
    ids = ITEM_IDS | REWARD_IDS | quests
    for source in sorted(sm.OURS.rglob('*.json')):
        file = 'assets/' + source.relative_to(sm.OURS).as_posix()
        if any(file.startswith(d) for d in sm.IGNORE_DIRS):
            continue
        o = json.loads(source.read_text('utf-8-sig'))
        if isinstance(o, list):
            found = [v for v in o if not isinstance(v, (dict, list)) and str(v) in ITEM_IDS]
            if found:
                membership.append({'file': file, 'required_ids': found, 'policy': '保留五重 ID 并保留灰其它 ID'})
            continue
        selected = list(server_roots(o, ids))
        if not selected:
            continue
        b = json.loads(sm.git('show', f'{sm.ANCESTOR}:{file}')) if file in tree else {}
        h = json.loads(sm.git('show', f'{hui_ref}:{file}')) if file in hui_tree else {}
        seen = set()
        for path, entity in selected:
            roots.append({'file': file, 'path': list(path)})
            for tail, _ in leaves(entity):
                full = path + tail
                if full in seen:
                    continue
                seen.add(full)
                rules.append({'file': file, **rule_fields(b, h, o, full, '五重副本/门票/奖励专属实体的精确叶值')})
    return rules, roots, membership


def main():
    hui, ours = View('hui'), View('ours')
    paths = logical_index()
    # 来源以 wf_dsl.dsl_logical(PROG) 补 ActionDsl 固定后缀后加盐寻址。
    for logical in ('battle/action/enemy/action/mod/five_boss_v3/fb3_buff$entrance.action.dsl.amf3.deflate',):
        paths.setdefault(member(logical), logical)
    client, quests, tables = client_audit(hui, ours, paths)
    sources, binary = source_edge_audit(ours, paths)
    server, roots, membership = server_audit(quests, hui.ref)
    differing = [r for r in client + server if r['is_difference']]
    result = {'format': 'hui-share-five-priority-v1', 'from': '1.4.136', 'to': '1.4.220',
              'our_terminal': '1.4.219', 'policy': '五重相关精确叶行一律取我方终态；共享表的灰独立行仍保留',
              'client_rules': client, 'server_rules': server, 'server_roots': roots,
              'server_membership_rules': membership, 'quest_ids': sorted(quests),
              'item_ids': sorted(ITEM_IDS), 'reward_ids': sorted(REWARD_IDS),
              'source_edge_changes': sources, 'binary_dependencies': binary,
              'client_rule_count': len(client), 'server_rule_count': len(server),
              'client_difference_count': sum(r['is_difference'] for r in client),
              'server_difference_count': sum(r['is_difference'] for r in server),
              'row_level_conflict_risk_count': sum(r['row_level_conflict_risk'] for r in client + server),
              'overrides_vs_default': sum(r['would_override_default'] for r in client + server),
              'binary_evidence': [
                  {'file': 'D:/WF/out/kulo-patch-toolkit/cursed_abyss/build/five_boss_buffs.py', 'line': 23},
                  {'file': 'D:/WF/out/kulo-patch-toolkit/cursed_abyss/build/five_boss_tune.py', 'line': 15},
                  {'file': 'D:/WF/startpoint-cn-kulo/tools/fantasy-gauntlet-mod-tools/wf_dsl.py', 'line': 35}]}
    write_json(ROOT/'audit/five-priority-220.json', result)
    lines = ['# 五重行保留我方值', '', '所有表行均按叶路径单独锁定我方 1.4.219 终态；没有整张共享表覆盖。', '',
             f'客户端保护 {len(client)} 叶行（灰/我方不同 {result["client_difference_count"]}）；服务端保护 {len(server)} 叶值（不同 {result["server_difference_count"]}）。', '',
             '下列仅列灰/我方不同值；完整同值保护清单见 `five-priority-220.json`。', '']
    for r in differing:
        lines += [f'## {r.get("logical", r.get("file"))} :: {"/".join(map(str,r["path"]))}', '',
                  '灰值：', '```json', json.dumps(r['hui'], ensure_ascii=False), '```', '我方值（保留）：',
                  '```json', json.dumps(r['ours'], ensure_ascii=False), '```', '']
    lines += ['## 来源与灰预载兼容', '',
              '163 边降低五重副本 HP 倍率；186 边加入五重 buff、专属 Boss 和场景引用；187 边继续调攻击及 buff。完整每边改行路径见 JSON 的 source_edge_changes。', '',
              '灰 136 的 evil 绿炮弹预载与我方 buff 为同一 CSV 行不同列。我方 216 的 build/merge.py 逐列合并，fb136_verify.py 检查列 109 的 fb3_buff$entrance 仍存在；本轮保留 219 完整五重终态，灰的独立预载资源沿普通三方规则保留。', '',
              f'以整行判断会出现 {result["row_level_conflict_risk_count"]} 行冲突风险；本任务第一轮已用 CSV 列级合并，原包中 evil/100 的三行同时保留我方 buff 与灰 preload。新增强制保护相对现有列级合并实际改变 {result["overrides_vs_default"]} 行；不把该风险误报成第一轮真实丢失修复。', '',
              '五重 buff 程序引用为 `battle/action/enemy/action/mod/five_boss_v3/fb3_buff$entrance`；wf_dsl.dsl_logical（wf_dsl.py:35–36）补 `.action.dsl.amf3.deflate` 后寻址到 77/d395…，来源 five_boss_buffs.py:23、five_boss_tune.py:15 及 187 integrity 的 logical_paths。187 边终态 SHA256 为 aee642dce651159ae4ba367d9afdcc700482270b66047df4f11afdbd68171ee7；本轮构建必须保留。', '',
              '门票、奖励早于 163 的五重专属 ID 也逐键保护：' + '、'.join(sorted(ITEM_IDS)) + '；专属奖励组 590010000。通用奖励组 10055/1 不因五重引用而整组覆盖。', '']
    (ROOT/'audit/five-priority-220.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('client_rule_count', 'server_rule_count', 'client_difference_count', 'server_difference_count', 'overrides_vs_default')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
