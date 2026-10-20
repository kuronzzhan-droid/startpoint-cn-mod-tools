"""只读锁定源链，核查凉月/碧五处冲突；仅在本工作区输出审计证据。"""
import io
import json
from pathlib import Path
import sys
import zipfile
import zlib

import common as c
import wf_assets
import wf_dsl
from PIL import Image


AB = 'master/ability/ability.orderedmap'
LA = 'master/ability/leader_ability.orderedmap'
PREFIX = 'character/cnmod_vyrn_dark/ui/'
ATLAS = PREFIX + 'illustration_setting_sprite_sheet.atlas.amf3.deflate'
PNG = PREFIX + 'illustration_setting_sprite_sheet.png'
SOURCES = {
    'liangyue_builder': Path('D:/WF/out/凉月修复-20261016/build_213.py'),
    'liangyue_handoff': Path('D:/WF/out/凉月修复-20261016/handoff-213/CHANGES.md'),
    'vyrn_builder': Path('D:/WF/out/碧-1.4.216/build/build_217.py'),
    'six_char_builder': Path('D:/WF/out/碧-1.4.216/build/build_218.py'),
    'layout': c.TOOL / 'ability_enum_map.json',
}


def source_proof(path, needles):
    text = path.read_text('utf-8-sig')
    lines = text.splitlines()
    excerpts = [{'line': i, 'text': line} for i, line in enumerate(lines, 1)
                if any(n in line for n in needles)]
    assert excerpts, path
    return {'file': str(path), 'sha256': c.sha(path.read_bytes()), 'excerpts': excerpts}


def history(view, member, key=None, row_ix=None, columns=None, atlas=False):
    result = []
    for src in view.sources:
        with zipfile.ZipFile(src['path']) as z:
            if member not in z.namelist():
                continue
            raw = z.read(member)
        rec = {'version': src['version'], 'archive': src['name'], 'member_sha256': c.sha(raw)}
        if key is not None:
            tree = c.q.parse_node(raw)
            if key not in tree:
                rec['key_absent'] = True
            else:
                rows = [c.cells(line) for line in tree[key].splitlines()]
                rec.update({'key': key, 'row_lengths': list(map(len, rows)),
                            'values': {str(i): rows[row_ix][i] for i in columns},
                            'row_sha256': c.sha(tree[key].encode())})
        if atlas:
            frames = wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']
            rec['frames'] = [f['n'] for f in frames]
        result.append(rec)
    return result


def all_differences(hui, ours):
    a = [c.cells(x) for x in hui.splitlines()]
    b = [c.cells(x) for x in ours.splitlines()]
    assert len(a) == len(b)
    result = []
    for i, (ar, br) in enumerate(zip(a, b)):
        assert len(ar) == len(br)
        result.extend({'row_index_zero_based': i, 'column_zero_based': j, 'hui': x, 'ours': y}
                      for j, (x, y) in enumerate(zip(ar, br)) if x != y)
    return result


def main():
    h, o = c.View('hui'), c.View('ours')
    proof = {
        'liangyue_builder': source_proof(SOURCES['liangyue_builder'],
            ['c74', 'cancelable 空串', 'fix(AB_LP', 'fix(LA_LP']),
        'liangyue_handoff': source_proof(SOURCES['liangyue_handoff'],
            ['只有 c74', '真机 A/B', '1.4.212:', '1.4.213:', '对比图']),
        'vyrn_builder': source_proof(SOURCES['vyrn_builder'],
            ['C8004', '根因:', '修法:', 'full_shot_illustration_setting_{i}']),
        'six_char_builder': source_proof(SOURCES['six_char_builder'],
            ['CHARS =', '修 119998/179982']),
        'layout': {'file': str(SOURCES['layout']), 'sha256': c.sha(SOURCES['layout'].read_bytes()),
                   'columns_are_zero_based': True},
    }
    rules = []
    targets = [(AB, '1599921', 2, [(67, '', '0'), (74, '', '1')]),
               (AB, '1599922', 2, [(67, '', '0')]),
               (LA, '159992', 5, [(65, '', '0')])]
    for logical, key, row_ix, sets in targets:
        member = c.member(logical)
        hv, ov = h.load(logical)[key], o.load(logical)[key]
        diff = all_differences(hv, ov)
        expected = [{'row_index_zero_based': row_ix, 'column_zero_based': col,
                     'hui': old, 'ours': new} for col, old, new in sets]
        assert diff == expected, (key, diff)
        hh = history(h, member, key, row_ix, [x[0] for x in sets])
        # 灰链尾仍保留缺陷列；所有携带目标键的灰边均未补入修复值。
        assert hh and all(x.get('key_absent') or all(v == '' for v in x['values'].values()) for x in hh)
        reason = ('灰链尾仍将初始倍率c74留空，使累计攻击效果倍率为0；取我方213补1，'
                  '并将cancelable明确为0。' if key == '1599921' else
                  '灰链尾仍将声明字段cancelable留空；取我方213明确为0。此项是数据合法性修复，'
                  '旧空串也按0读取，单独补0不改变战斗效果。')
        rules.append({'member': member, 'logical': logical, 'path': [key], 'resolution': 'ours',
                      'reason': reason, 'hui': hv, 'ours': ov,
                      'evidence': {'hui_history': hh, 'changed_cells': diff,
                          'ours_219_source': o.index[member].name,
                          'source_proof_refs': ['liangyue_builder', 'liangyue_handoff', 'layout'],
                          'verification': '本轮只读静态核对；历史CHANGES.md记载的真机A/B没有在本轮重跑。'}})

    atlas_member, png_member = c.member(ATLAS), c.member(PNG, 'medium_upload')
    hf = wf_dsl.parse_dsl(zlib.decompress(h.raw(atlas_member), -15))['tree']
    of = wf_dsl.parse_dsl(zlib.decompress(o.raw(atlas_member), -15))['tree']
    required = {PREFIX + 'full_shot_illustration_setting_' + str(i) for i in range(2)}
    assert len(hf) == 20 and not required.intersection(f['n'] for f in hf)
    assert {f['n'] for f in of} == required and len(of) == 2
    pngs = {}
    for kind, v in [('hui', h), ('ours', o)]:
        raw = v.raw(png_member)
        decoded = wf_assets.png_decode_stored(raw)
        with Image.open(io.BytesIO(decoded)) as im:
            im.load()
            pngs[kind] = {'size': list(im.size), 'mode': im.mode, 'stored_sha256': c.sha(raw),
                          'decoded_png_sha256': c.sha(decoded)}
    for f in of:
        assert 0 <= f['x'] < f['x'] + f['w'] <= pngs['ours']['size'][0]
        assert 0 <= f['y'] < f['y'] + f['h'] <= pngs['ours']['size'][1]
    hh = history(h, atlas_member, atlas=True)
    assert all(not required.intersection(x['frames']) for x in hh)
    # 218修六角色，不含碧；确认二成员由217而非218提供，避免错误归因。
    assert o.index[atlas_member].name == 'pinball-1.4.216-1.4.217-1-vyrn-illustration-sheet-local.zip'
    assert o.index[png_member].name == o.index[atlas_member].name
    source218 = next(s for s in o.sources if s['version'] == '1.4.218')
    with zipfile.ZipFile(source218['path']) as z:
        assert atlas_member not in z.namelist() and png_member not in z.namelist()
    shared = {'hui_atlas_frames': hf, 'ours_atlas_frames': of, 'png': pngs,
              'hui_atlas_history': hh, 'ours_source': o.index[atlas_member].name,
              '218_does_not_contain_either_vyrn_member': True,
              'source_proof_refs': ['vyrn_builder', 'six_char_builder'],
              'verification': 'AMF3帧名和PNG解码/帧边界本轮静态验证；本轮未启动客户端，C8004运行状态未核实。'}
    for member, logical in [(atlas_member, ATLAS), (png_member, PNG)]:
        rules.append({'member': member, 'logical': logical, 'path': [], 'resolution': 'ours',
            'reason': '灰131–136未另修：立绘设置图集仍是20条通用UI帧，缺full_shot_illustration_setting_0/1。'
                      '取我方217的两帧专用atlas及配对PNG，修复构建器记载的切换立绘C8004。',
            'hui': c.sha(h.raw(member)), 'ours': c.sha(o.raw(member)), 'evidence': shared})
    report = {'schema': 1, 'hui_ref': h.ref, 'hui_tip': '1.4.136', 'ours_tip': '1.4.219',
              'rules': rules, 'source_proofs': proof,
              'summary': {'rules_ours': len(rules), 'rules_hui': 0,
                          'liangyue_rows': 3, 'liangyue_changed_cells': 4, 'vyrn_members': 2}}
    c.write_json(c.ROOT / 'audit/defect-resolutions-220.json', report)
    lines = ['# 五处缺陷修复冲突核对（本轮静态）', '',
        f'灰来源固定为 `{h.ref}` 的1.4.131–1.4.136八个包；我方为锁定1.4.219终态。五处均取我方。', '',
        '## 凉月159992：三行、四列', '',
        '以下行号、列号均从0计数。逐包检查灰131–136携带目标表的版本，目标列一直为空；未发现灰另行修复。', '',
        '| 表 | 键/子行 | 列 | 灰值 | 我方值 | 结论 |', '|---|---|---|---|---|---|']
    for r in rules[:3]:
        for d in r['evidence']['changed_cells']:
            lines.append(f"| {r['logical']} | {r['path'][0]} / #{d['row_index_zero_based']} | c{d['column_zero_based']} | `{d['hui']}`（空串） | `{d['ours']}` | 取我方213修复 |")
    lines += ['', 'ability行均126列、leader_ability行均124列；除上列四个字段，三行全部内容相同。'
        '1599921的c74是initial_multiply，空串导致倍率0，补1恢复叠层。三处cancelable空串补0是声明字段合法性修复，'
        '历史构建器记载其旧读取行为已为0，因此不要将这三列宣传成独立战斗加强。', '',
        '证据：`D:/WF/out/凉月修复-20261016/build_213.py` 的fix调用和字段说明；'
        '`handoff-213/CHANGES.md` 第12–18行说明修复范围，第43–46行记载旧版缺自身叠层、213出现自身攻击×12的历史真机A/B。'
        '本轮只核对历史记录和当前源字节，没有重跑真机。', '',
        '## 碧169978：PNG与atlas必须配对', '',
        '灰链尾仍携带20条square/thumb等通用UI帧，完全缺少立绘设置页所需的'
        '`full_shot_illustration_setting_0/1`。灰131–136携带此atlas的各个包均未补入这两帧。'
        '我方217终态atlas恰好包含两条正确帧，PNG解码成功，两个裁剪框均在PNG边界内。', '',
        f"灰PNG尺寸 `{pngs['hui']['size']}`；我方PNG尺寸 `{pngs['ours']['size']}`。"
        '两成员均取我方217，完整SHA和两边AMF帧结构见同名JSON。', '',
        '逻辑路径：', '', f'- `{PNG}`（medium_upload）', f'- `{ATLAS}`（upload）', '',
        '证据：`D:/WF/out/碧-1.4.216/build/build_217.py` 第2–5行写明C8004和缺失帧根因，'
        '本轮直接解码灰/我方源atlas证实这一结构差异。218针对119998及179982–179986；'
        '本轮检查218 ZIP不包含上述碧两成员，故这两处应归因217而非218。'
        '本轮未启动客户端，C8004是否在目标APK消失仍为未核实。', '',
        '## 可重跑与证据', '',
        '运行 `python 交付/build/audit_defects_220.py`。JSON含逐包历史、灰/我方完整行值、逐列差异、'
        'atlas全部帧结构、PNG尺寸/SHA、源脚本SHA与行号摘录。审计不修改源目录。', '']
    path = c.ROOT / 'audit/defect-resolutions-220.md'
    path.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(report['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
