"""第三轮服务端 GM 使用配套和训练副本审计；只读来源，只写分享包。"""
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from server_merge_core import DUMMY_IDS, GM_IDS, GM_PATTERN, GM_SUPPORT_FILES, clean

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path('D:/WF/out/角色超限-120/localsrv219/assets')
IGNORED = {'asset-patch', 'asset_lists', 'gacha-movie-variants'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path):
    return json.loads(path.read_text('utf-8-sig'))


def references(value, path=()):
    """精确 ID 或内嵌十进制 ID；GM 顶层键记录为整行，便于人工审阅。"""
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if GM_PATTERN.search(str(key)):
                found.append({'path': list(path + (key,)), 'value': item, 'kind': 'key'})
            else:
                found += references(item, path + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found += references(item, path + (index,))
    elif GM_PATTERN.search(str(value)):
        found.append({'path': list(path), 'value': value, 'kind': 'value'})
    return found


def scan(root):
    result, scanned = [], []
    for path in sorted(root.rglob('*.json')):
        relative = path.relative_to(root)
        if set(relative.parts) & IGNORED:
            continue
        value = parse(path)
        file = 'assets/' + relative.as_posix()
        # 任何未知 GM 配置都会在生成交付前中止；训练内容全部保留。
        assert clean(value, file, (), []) == value
        scanned.append({'file': file, 'sha256': digest(path)})
        for hit in references(value):
            assert file in GM_SUPPORT_FILES, ('未知 GM 服务端引用', file, hit)
            result.append({'file': file, **hit, 'classification': '收入：GM 本体/使用配套',
                           'reason': GM_SUPPORT_FILES[file]})
    return result, scanned


def lookup(row, root):
    value = parse(root / row['file'].removeprefix('assets/'))
    for key in row['path']:
        value = value[key]
    return value


def build_audit(document):
    merged = ROOT / 'cache/server-merged-assets'
    original = ROOT / 'cache/server-origin-assets'
    ours, scanned = scan(SOURCE)
    baseline, baseline_scanned = scan(original)
    final, final_scanned = scan(merged)
    assert len(ours) == 48, ('我方已审计 GM 配套行数变化', len(ours))
    by_file = {}
    for row in ours:
        by_file.setdefault(row['file'], []).append(row)
    assert set(by_file) == set(GM_SUPPORT_FILES)
    assert all(len(rows) == 6 for rows in by_file.values())
    # ID 数组追加位置不同，按值验证；对象表按键验证。
    operation_index = {file['file']: {row['key']: row for row in file['entries']}
                       for file in document['files']}
    for row in ours:
        source_file = row['file']
        value = parse(merged / source_file.removeprefix('assets/'))
        gm_id = str(row['value']) if row['kind'] == 'value' else row['path'][0]
        actual = value.get(gm_id) if isinstance(value, dict) else next((v for v in value if str(v) == gm_id), None)
        assert actual == row['value'], ('GM 配套未进入合并终态', source_file, gm_id)
        assert operation_index[source_file][gm_id]['value'] == row['value'], (source_file, gm_id)
        row['key'] = gm_id
        row['delivered_action'] = operation_index[source_file][gm_id]['action']
    practice_source = parse(SOURCE / 'practice_quest.json')
    practice_final = parse(merged / 'practice_quest.json')
    restored = []
    for key in sorted(DUMMY_IDS, key=int):
        expected = practice_source[key]
        assert practice_final[key] == expected, ('训练副本未按我方终态恢复', key)
        assert operation_index['assets/practice_quest.json'][key]['value'] == expected
        restored.append({'file': 'assets/practice_quest.json', 'key': key, 'value': expected})
    report = {
        'format': 'hui-share-gm-server-r3-v1', 'from': '1.4.136', 'to': '1.4.220',
        'hui_ref': document['hui_ref'], 'our_terminal': '1.4.219',
        'policy': '收入GM武器5990001-5990006本体及使用配套；不收入任何获取途径；训练副本1103-1123恢复。',
        'included_count': len(ours), 'included': ours,
        'intentionally_excluded_acquisition_count': 0,
        'intentionally_excluded_acquisition': [],
        'acquisition_note': '我方服务端JSON终态没有直接引用GM ID的商品/掉落/奖励/任务/兑换/邮件礼包行；客户端商品和通用服务端目录另行审计。',
        'restored_practice_count': len(restored), 'restored_practice': restored,
        'baseline_gm_reference_count': len(baseline), 'merged_gm_reference_count': len(final),
        'source_json_scan': scanned, 'baseline_json_scan': baseline_scanned,
        'merged_json_scan': final_scanned,
        'checks': {'unknown_gm_reference_refused': True, 'gm_support_matches_219': True,
                   'practice_21_matches_219': True, 'all_delivered_keys_present': True},
        'runtime': '未核实：本审计为离线数据及源码静态证据，不运行服务端。',
    }
    audit = ROOT / 'audit'
    (audit / 'gm-server-r3.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# 第三轮服务端 GM 与训练副本审计', '',
             'GM 武器只带本体与已有武器的使用配套；正式服不开放获取。', '',
             f'逐个解析我方 {len(scanned)} 个服务端 JSON、灰基线 {len(baseline_scanned)} 个 JSON 与合并视图 {len(final_scanned)} 个 JSON。',
             f'精确 GM 引用：灰基线 {len(baseline)} 条；我方 48 条；合并视图 {len(final)} 条。未知 GM 引用将中止构建。', '',
             '## 收入的 GM 行', '', '| 文件 | 键/ID | 分类依据 | 我方与交付值 |', '|---|---|---|---|']
    for row in ours:
        value = json.dumps(row['value'], ensure_ascii=False, separators=(',', ':'))
        lines.append(f"| `{row['file']}` | `{row['key']}` | {row['reason']} | `{value}` |")
    lines += ['', '## 刻意不收的服务端获取途径行', '', report['acquisition_note'], '',
              '本项服务端直接行计数为 0；这不代表客户端商品行也为 0。详见第三轮客户端排除明细和通用目录源码审计。', '',
              '`equipment_dissolve` 消耗玩家已有武器生成其魂珠；`item_sale` 消耗玩家已有魂珠获得玛纳。两者不凭空发放 GM 武器。', '',
              '## 恢复的训练副本', '', '| 文件 | quest id | 名称 | 我方与交付值 |', '|---|---|---|---|']
    for row in restored:
        value = json.dumps(row['value'], ensure_ascii=False, separators=(',', ':'))
        lines.append(f"| `{row['file']}` | `{row['key']}` | {row['value']['name']} | `{value}` |")
    lines += ['', '## 验证边界', '', report['runtime'], '']
    (audit / 'gm-server-r3.md').write_text('\n'.join(lines), encoding='utf-8')
    return report


def main():
    document = parse(ROOT / '交付/server-entries.json')
    report = build_audit(document)
    print(json.dumps({key: report[key] for key in ('included_count', 'intentionally_excluded_acquisition_count',
                                                 'restored_practice_count', 'merged_gm_reference_count')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
