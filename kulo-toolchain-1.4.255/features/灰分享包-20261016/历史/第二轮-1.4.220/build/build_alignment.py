"""按叶表行比较灰 131–136 增量，构建测试服 219→220 对齐边。"""
import copy
import json
import zipfile

import common as c


ABSENT = object()
NAME = 'pinball-1.4.219-1.4.220-1-align-live-local.zip'


def visible(value):
    return {'absent': True} if value is ABSENT else value


def table(raw):
    if raw is None:
        return {}
    try:
        value = c.q.parse_node(raw)
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def assign(tree, path, value):
    target = tree
    for key in path[:-1]:
        target = target.setdefault(key, {})
    if value is ABSENT:
        target.pop(path[-1], None)
    else:
        target[path[-1]] = copy.deepcopy(value)


def main():
    hui, ours = c.View('hui'), c.View('ours')
    logical = c.logical_index()
    stats, kept, changes, output = {}, [], [], {}
    for member in sorted(hui.index):
        raw_base, raw_hui, raw_ours = c.base_raw(member), hui.raw(member), ours.raw(member)
        if raw_hui == raw_base:
            continue
        name = logical.get(member, member)
        base, gray, test = map(table, (raw_base, raw_hui, raw_ours))
        if all(isinstance(node, dict) for node in (base, gray, test)):
            lookup = [dict(c.leaves(node)) for node in (base, gray, test)]
            result = copy.deepcopy(test)
            member_changes = []
            for path in sorted(set(lookup[0]) | set(lookup[1])):
                b, h, o = (node.get(path, ABSENT) for node in lookup)
                if h == b:
                    continue
                record = {'member': member, 'logical': name, 'path': list(path),
                          'base': visible(b), 'hui': visible(h), 'ours': visible(o)}
                if h == o:
                    outcome = 'row_same'
                elif o == b:
                    outcome = 'row_incoming'
                    assign(result, path, h)
                    member_changes.append(record)
                else:
                    outcome = 'row_keep_ours'
                    record['resolution'] = 'ours'
                    record['reason'] = '测试219已有独立或后续修改；不以灰旧行覆盖'
                    kept.append(record)
                stats[outcome] = stats.get(outcome, 0) + 1
            if member_changes:
                output[member] = c.q.build_node(result)
                assert c.q.parse_node(output[member]) == result
                changes.extend(member_changes)
        else:
            if raw_hui == raw_ours:
                outcome = 'binary_same'
            elif raw_ours == raw_base:
                outcome = 'binary_incoming'
                output[member] = raw_hui
                changes.append({'member': member, 'logical': name, 'kind': 'binary'})
            else:
                outcome = 'binary_keep_ours'
                kept.append({'member': member, 'logical': name, 'kind': 'binary',
                             'base_sha256': c.sha(raw_base) if raw_base else None,
                             'hui_sha256': c.sha(raw_hui),
                             'ours_sha256': c.sha(raw_ours) if raw_ours else None,
                             'resolution': 'ours', 'reason': '保留测试219资源终态及C8004修复'})
            stats[outcome] = stats.get(outcome, 0) + 1

    path = c.OUT / NAME
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for member in sorted(output):
            info = zipfile.ZipInfo(member, date_time=(2026, 10, 16, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, output[member], compresslevel=6)
    raw = path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert archive.namelist() == sorted(output)
    integrity = {'name': NAME, 'size': len(raw), 'sha256': c.sha(raw),
                 'members': len(output), 'files': sorted(output),
                 'member_sha256': {m: c.sha(v) for m, v in sorted(output.items())},
                 'applies_on': '1.4.219', 'version': '1.4.220',
                 'merged_rows': changes, 'hui_ref': hui.ref,
                 'ancestor': '1.4.130', 'ours_tip': '1.4.219'}
    c.write_json(path.with_suffix('.integrity.json'), integrity)
    item = {k: integrity[k] for k in ('name', 'size', 'sha256', 'members', 'files')}
    entry = {'id': 'align-live-local-20261016-1.4.220', 'type': 'patch',
             'name': '测试服与正式服版本对齐',
             'description': '灰131–136逐叶行及独立资源比对：测试219均已包含或已有后续修复；空边仅升版本。',
             'version': '1.4.220', 'depends_on': '1.4.219', 'enabled': True,
             'archive': NAME, 'archive_size': len(raw), 'chain': [NAME],
             'archive_integrity': [item], 'files': sorted(output), 'created_at': '2026-10-16'}
    c.write_json(c.OUT / 'manifest-entry-align-1.4.220.json', entry)
    audit = {'anchor': {'from': '1.4.219', 'to': '1.4.220'},
             'comparison': '灰131–136相对共同130，按叶表行逐键比对测试219；双方修改的行/资源保留测试219',
             'hui_ref': hui.ref, 'stats': stats, 'members': len(output), 'empty_edge': not output,
             'kept_ours': kept, 'imported_changes': changes, 'archive_integrity': item,
             'test_existing_gm_and_helpers': '不修改测试219既有GM武器及测试辅助数据',
             'source_lock_sha256': c.sha((c.OUT / 'build/source-lock.json').read_bytes())}
    c.write_json(c.ROOT / 'audit/alignment-220.json', audit)
    lines = ['# 测试服 1.4.219→1.4.220 对齐审计', '',
             '逐键比较灰 1.4.131–1.4.136 相对共同祖先 1.4.130 的增量。',
             '测试219已包含全部可导入灰增量，因此本边为合法空ZIP（22字节），仅升版本号。',
             '保留测试219后续修复，包括五重增益、凉月能力/队长技和碧C8004资源。',
             '测试219既有GM及测试辅助不因正式包剔除策略而删除。', '',
             f'统计：{json.dumps(stats, ensure_ascii=False)}', '',
             '## 已有后续改动，保留测试219', '']
    for record in kept:
        key = '/'.join(record.get('path', [])) or '完整资源'
        lines.append(f"- `{record['logical']}` / `{key}`：{record['reason']}。完整双方值和SHA见JSON。")
    lines.extend(['', '## 产物', '', f'- `{NAME}`，{len(raw)}字节，SHA256 `{c.sha(raw)}`。',
                  '- `manifest-entry-align-1.4.220.json`：version=1.4.220，depends_on=1.4.219。', ''])
    (c.ROOT / 'audit/alignment-220.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'stats': stats, 'members': len(output), 'size': len(raw), 'sha256': c.sha(raw)},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
