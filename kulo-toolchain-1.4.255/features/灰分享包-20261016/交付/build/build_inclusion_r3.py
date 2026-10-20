"""第三轮客户端准入审计：恢复木桩及 GM 本体，只排除 GM 获取途径。"""
import copy
import json
import re
import zlib

import common as c


GM_IDS = [str(n) for n in range(5990001, 5990007)]
GM_PATTERN = re.compile(r'(?<!\d)599000[1-6](?!\d)|mod_gm_599000[1-6]|gm_direct_hits')
BODY_TABLES = {
    'master/ability/ability_soul.orderedmap',
    'master/item/equipment.orderedmap',
    'master/item/equipment_status.orderedmap',
    'master/item/item.orderedmap',
    'master/string/custom_ability_string.orderedmap',
}
ACQUISITION_PATTERN = re.compile(
    r'/(?:shop|reward|mission|active_mission|mail|box_gacha|gacha_odds|gacha|quest|campaign|pass_card|test)/'
    r'|exchange|lottery|present|gift|drop|pack_shop|equipment_enhancement_shop'
)
EMPTY_PLACEHOLDER = bytes.fromhex('0c00000078da63606060000000040001')


def decode(raw):
    if raw is None:
        return None, 'absent'
    if raw == EMPTY_PLACEHOLDER:
        assert zlib.decompress(raw[4:]) == b'\0' * 4
        return {}, 'empty_placeholder'
    try:
        node = c.q.parse_node(raw)
        return node, 'map' if isinstance(node, dict) else 'scalar'
    except (ValueError, UnicodeError, zlib.error, IndexError) as exc:
        return None, type(exc).__name__


def get(node, path):
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return {'absent': True}
        node = node[key]
    return copy.deepcopy(node)


def enrich_row(rule, ours, hui):
    row = copy.deepcopy(rule)
    m, path = row['member'], row['key_path']
    node, status = decode(ours.raw(m))
    assert status in ('map', 'empty_placeholder'), (m, status)
    row.update(value=get(node, path), source_archive=ours.index[m].name,
               source_sha256=c.sha(ours.index[m].read_bytes()),
               hui_value=get(decode(hui.raw(m))[0], path),
               decision='include_ours_final', previous_reason=row['reason'])
    row['action'] = 'include_ours_terminal'
    row['reason'] = 'GM 武器本体与配套' if row['reason'].startswith('GM') else '作者授权恢复训练木桩及配套'
    return row


def enrich_member(rule, ours):
    item = copy.deepcopy(rule)
    raw = ours.raw(item['member'])
    assert raw is not None, item
    item.update(sha256=c.sha(raw), bytes=len(raw),
                source_archive=ours.index[item['member']].name,
                decision='include_ours_final', previous_reason=item['reason'])
    item['action'] = 'include_ours_terminal'
    item['reason'] = 'GM 直击功能 DSL' if item['reason'].startswith('GM') else '作者授权恢复训练木桩及配套'
    return item


def scan_tables(view, logical):
    candidates = {c.member(lp): lp for lp in set(logical.values())
                  if lp.startswith('master/') and lp.endswith('.orderedmap')}
    # 补扫所有链中实际变过的可解码成员，避免只靠路径表漏掉新表。
    for m in view.index:
        candidates.setdefault(m, logical.get(m, '未核实'))
    counts = {'candidates': len(candidates), 'available': 0, 'map_tables': 0,
              'scalar_tables': 0, 'empty_placeholders': 0, 'leaves': 0}
    hits, absent, opaque, acquisition_tables = [], [], [], []
    for m, lp in sorted(candidates.items()):
        raw = view.raw(m)
        if raw is None:
            absent.append(lp)
            continue
        counts['available'] += 1
        node, status = decode(raw)
        if status == 'empty_placeholder':
            counts['empty_placeholders'] += 1
        elif status == 'map':
            counts['map_tables'] += 1
        elif status == 'scalar':
            counts['scalar_tables'] += 1
        else:
            if lp.startswith('master/') and lp.endswith('.orderedmap'):
                opaque.append({'member': m, 'logical_path': lp, 'bytes': len(raw),
                               'sha256': c.sha(raw), 'decode_status': status})
            continue
        if ACQUISITION_PATTERN.search(lp):
            acquisition_tables.append({'member': m, 'logical_path': lp, 'decode_status': status})
        for path, value in c.leaves(node):
            counts['leaves'] += 1
            if not GM_PATTERN.search('/'.join(path) + ' ' + str(value)):
                continue
            classification = 'body' if lp in BODY_TABLES else 'acquisition' if ACQUISITION_PATTERN.search(lp) else 'unclassified'
            hits.append({'member': m, 'logical_path': lp, 'key_path': list(path),
                         'value': value, 'classification': classification,
                         'source_archive': view.index[m].name if m in view.index else '共同祖先 store131',
                         'view': view.kind})
    return {'view': view.kind, 'counts': counts, 'hits': hits,
            'unavailable_logical_paths': absent, 'opaque_master_tables': opaque,
            'acquisition_tables': acquisition_tables}


def icons(ours, hui):
    import wf_dsl
    atlas_lp = 'item/sprite_sheet.atlas.amf3.deflate'
    png_lp = 'item/sprite_sheet.png'
    atlas_raw = ours.raw(c.member(atlas_lp))
    assert atlas_raw is not None
    atlas = wf_dsl.parse_dsl(zlib.decompress(atlas_raw, -15))['tree']
    eq = ours.load('master/item/equipment.orderedmap')
    dependencies = []
    for wid in GM_IDS:
        path = c.cells(eq[wid])[6]
        entries = [r for r in atlas if r.get('n') == path]
        assert len(entries) == 1, (wid, path)
        dependencies.append({'weapon_id': wid, 'icon': path, 'atlas_entry': entries[0],
                             'resolution': '复用公共 item/sprite_sheet，主构建保留其终态 PNG 与 atlas'})
    members = []
    for lp in [atlas_lp, png_lp]:
        m = c.member(lp)
        raw = ours.raw(m)
        assert raw is not None
        members.append({'member': m, 'logical_path': lp, 'sha256': c.sha(raw),
                        'bytes': len(raw), 'shared': True,
                        'already_in_hui': raw == hui.raw(m),
                        'source_archive': ours.index[m].name if m in ours.index else '共同祖先 store131'})
    return dependencies, members


def markdown(policy):
    lines = ['# 第三轮客户端准入审计', '',
             '作者 2026-10-16 17:14：新木桩和武器收入，正式服不开放 GM 武器获取。', '',
             '## 决策', '',
             '恢复第一轮排除的全部 21 个训练副本（1103–1123）及 131 个顶层表键、62 个独立资源。',
             'GM 5990001–5990006 恢复 25 个顶层表键（展开 31 个叶行）和 1 个直击 DSL；',
             '图标复用公共 item/sprite_sheet 的 6 个已有条目，PNG/atlas 随公共配套保留。',
             'GM 原脚本注明“觉醒 0 起满额，不需要强化”；保留 equipment_status 等级 1、5 终态。',
             '没有新增独立强化/觉醒表键；不凭空创造数据。', '',
             '## 刻意不收的 GM 获取途径行（客户端）', '',
             f"客户端获取途径行命中 {len(policy['acquisition_rows'])} 个；本轮 excluded_rows={len(policy['excluded_rows'])}，excluded_members=0。",
             '源客户端链没有 GM 商店/掉落/奖励/任务/兑换/邮件/礼包行可剔除；未编造不存在的排除行。',
             '服务端获取途径另见服务端准入明细；客户端本体中 item 是魂珠定义，equipment 是武器定义，均不构成发放入口。',
             '所有可读表的精确武器 ID、mod_gm_* 和 gm_direct_hits 引用均落在本体表；',
             '没有以 GM 为终点的奖励包装行，因此没有需要继续反向追踪的间接包装链。',
             '如未来输入出现未分类引用或无法安全拆分的混合获取行，构建会报 blocker 并停止。', '',
             '## 全表扫描范围', '',
             '| 视图 | 候选成员 | 字典表 | 纯文本表 | 空占位 | 叶值 | GM 命中 |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for scan in policy['scans']:
        n = scan['counts']
        lines.append(f"| {scan['view']} | {n['candidates']} | {n['map_tables']} | {n['scalar_tables']} | {n['empty_placeholders']} | {n['leaves']} | {len(scan['hits'])} |")
    lines += ['', '已知 master 路径加上两条链实际变动成员一并扫描。缺失逻辑路径逐项保存在 JSON；',
              '空占位均校验固定 16 字节编码、解压内容为四个零字节。没有无法解码的非空 master 表。',
              '这属于本地静态数据审计，服务器实际开关及客户端运行效果未核实。', '',
              '## 恢复收入的 GM 表键（完整值见同名 JSON 的 gm_body_rows）', '',
              '| 表 | 键 | 最终来源 |', '|---|---|---|']
    for r in policy['gm_body_rows']:
        lines.append(f"| {r['logical_path']} | {'/'.join(r['key_path'])} | {r['source_archive']} |")
    lines += ['', '## 恢复收入的训练副本', '', '| quest id | 名称 |', '|---|---|']
    for r in policy['restored_quests']:
        lines.append(f"| {r['quest_id']} | {r['name']} |")
    lines += ['', '131 个恢复表键和 62 个独立资源的完整值、路径及来源均列在 inclusion-policy-r3.json。', '',
              '## 图标与本体来源', '',
              r'- D:\WF\out\kulo-patch-toolkit\cursed_abyss\build\gm_weapons.py：本体能力、共享图标模板及状态行。',
              r'- D:\WF\out\kulo-patch-toolkit\cursed_abyss\build\gm_weapon6.py：5990006 能力、状态与弓图标复用。',
              '- 所有收入数据取固定我方 1.4.219 终态，不执行以上源构建脚本。', '']
    return '\n'.join(lines)


def main():
    original_path = c.OUT / 'build/original-exclusions.json'
    original = json.loads(original_path.read_text('utf-8'))
    ours, hui = c.View('ours'), c.View('hui')
    logical = c.logical_index()
    logical.update({r['member']: r['logical_path'] for r in original['excluded_rows'] + original['excluded_members']})
    gm_rows = [enrich_row(r, ours, hui) for r in original['excluded_rows'] if r['reason'].startswith('GM')]
    dummy_rows = [enrich_row(r, ours, hui) for r in original['excluded_rows'] if r['reason'].startswith('训练')]
    gm_members = [enrich_member(r, ours) for r in original['excluded_members'] if r['reason'].startswith('GM')]
    dummy_members = [enrich_member(r, ours) for r in original['excluded_members'] if r['reason'].startswith('训练')]
    assert (len(gm_rows), len(dummy_rows), len(gm_members), len(dummy_members)) == (25, 131, 1, 62)
    scans = [scan_tables(ours, logical), scan_tables(hui, logical)]
    acquisitions = [r for s in scans for r in s['hits'] if r['classification'] == 'acquisition']
    blockers = [r for s in scans for r in s['hits'] if r['classification'] == 'unclassified']
    blockers += [r for s in scans for r in s['opaque_master_tables']]
    # 固定输入无客户端 GM 获取行；若日后出现，先审语义和混合奖励，禁止粗暴删整行。
    blockers += [{'reason': '新增获取行需人工确认能否安全逐行剔除', **r} for r in acquisitions]
    icon_dependencies, icon_members = icons(ours, hui)
    practice = ours.load('master/quest/practice/practice_quest.orderedmap')
    quests = [{'quest_id': str(qid), 'name': c.cells(practice[str(qid)])[2], 'value': practice[str(qid)]}
              for qid in range(1103, 1124)]
    policy = {
        'policy': '第三轮：收入全部训练木桩和GM本体，只排除GM获取途径；五重和缺陷修复优先级沿用第二轮。',
        'author_decision': '2026-10-16 17:14 新木桩和武器带上，正式服不开放GM武器获取',
        'gm_weapon_ids': GM_IDS, 'test_quest_ids': original['test_quest_ids'],
        'excluded_rows': [], 'excluded_members': [],
        'gm_body_rows': gm_rows, 'gm_body_members': gm_members,
        'restored_dummy_rows': dummy_rows, 'restored_dummy_members': dummy_members,
        'restored_quests': quests, 'gm_icon_dependencies': icon_dependencies,
        'gm_shared_icon_members': icon_members, 'acquisition_rows': acquisitions,
        'gm_references': scans[0]['hits'], 'test_references': [],
        'retained_shared_fix': original['retained_shared_fix'],
        'scans': scans, 'blockers': blockers,
        'wrapper_audit': {'terminal_gm_acquisition_rows': len(acquisitions),
                          'indirect_wrappers': [],
                          'reason': '所有可读表的精确 GM ID/别名/DSL引用只有本体行，没有发放终点，间接包装闭包为空。'},
        'original_policy_sha256': c.sha(original_path.read_bytes()),
        'source_anchor': {'hui': hui.ref, 'ours': '1.4.219'},
    }
    c.write_json(c.ROOT / 'audit/inclusion-policy-r3.json', policy)
    c.write_json(c.OUT / '附录/inclusion-policy-r3.json', policy)
    if blockers:
        raise SystemExit('BLOCKER：获取行或未分类/不可解析master引用，见 audit/inclusion-policy-r3.json')
    c.write_json(c.OUT / '附录/exclusions.json', policy)
    note = markdown(policy)
    (c.ROOT / 'audit/gm-client-r3.md').write_text(note, encoding='utf-8')
    (c.OUT / '附录/客户端准入第三轮.md').write_text(note, encoding='utf-8')
    print(json.dumps({'restored_dummy_quests': len(quests), 'restored_dummy_rows': len(dummy_rows),
                      'restored_dummy_members': len(dummy_members), 'gm_body_rows': len(gm_rows),
                      'gm_body_members': len(gm_members), 'gm_acquisition_rows': len(acquisitions),
                      'blockers': len(blockers)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
