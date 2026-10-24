# -*- coding: utf-8 -*-
# 2026-09-27 由会话临时校验器 panel_merge/check_merge.py 移入仓库，供面板合并模块与测试共用（原先测试按临时路径加载，会话结束后会静默跳过）。
"""面板文案合并校验器（只读，不碰 store）。

用法（import）：
    from wf_panel_merge_check import check
    res = check(orig, merged, prefix_drops=[...])
    # orig / merged：str（单列）或 list[str]（多列：词条等级低 / 满，逐列比对）
    # prefix_drops：允许删掉「X属性共鸣时，」的原文行，元素可以是
    #     int（原文行号，1 起）、str（原文整行）或 dict(line=int|str, resonance='Red'|'火'|'White,Black'…)
    # 返回 dict(ok, errors, warnings, columns=[{mapping, ...}])

命令行：
    python mod-tools/wf_panel_merge_check.py --orig a.txt --merged b.txt [--drops 3,5] [--drops-json d.json]
    python mod-tools/wf_panel_merge_check.py --scan scan.json [--id 119990] [--panel leader]
        （逐个校验 scan.json 里 proposed 与 original 两列；--proposed-key 可换字段名）
    退出码：0 全部通过，1 有错误。

检查项：
  1. 带符号的数值记号（＋20%、－6、＋7层、提升8％、「 80%」机器体等效果值）多重集合不变；
     不带符号的记号（每发动3次、5秒、最多10层等条件/后缀）每个仍在，合并行里出现次数
     介于各来源行的最大值与总和之间（相同条件/后缀只写一次是允许的）。
  2. 每条原文行的效果名（记号前、去掉对象名后的名词短语）都出现在它被并入的新行里。
  3. 主位图标：原文行与它所在新行的图标状态一致；图标行数 = 原图标行数 − 被并掉的图标行数。
  4. 禁用：新改动行里不得出现「／」「自身为队长时」「觉醒后」「生命值100%以下」，
     共鸣只能写「X属性共鸣时，」（不能是「：」）；未改动行里已有的记为 warning。
  5. 「X属性共鸣时，」只允许在 prefix_drops 列出的行里删掉（允许删，不强制删）；未授权的删除报错；
     仅删前缀、未合并的行其余字面必须逐字相同。
  6. 未合并的行逐字保留，行序不变；合并行放在其来源第一行的位置。
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

ICON_RE = re.compile(r"^\s*<icon id='main'>\s*")
EL_CN = {'Red': '火', 'Blue': '水', 'Yellow': '雷', 'Green': '风', 'White': '光', 'Black': '暗'}
RES_RE = re.compile(r"([火水雷风光暗](?:或[火水雷风光暗])*)属性共鸣时[，：:,]\s*")
FORBIDDEN = ('／', '自身为队长时', '觉醒后', '生命值100%以下', '生命值100％以下')
NUM = r"\d+(?:\.\d+)?"
UNIT = r"(?:%|％|层|倍|秒|次|点|个|盏|连击|帧)?"
# 效果值：带正负号，或「提升/增加/…」后（「每提升1层」这类条件除外），或机器体「名词 80%」（空格后）
SIGNED_RE = re.compile(r"(?:[＋+－\-−]\s*|(?<!每)(?:提升|增加|降低|减少|上升|延长|缩短)\s*|(?<=[一-鿿\)）A-Za-z]) )(" + NUM + UNIT + ")")
ANY_RE = re.compile(r"(?<![\d.])(" + NUM + UNIT + ")")
DELIMS = '，、；。：,;:（）()'
# 对象/动词标记：效果名取最后一个标记之后的部分
OBJ_MARKERS = re.compile(r"(?:赋予全队\([^)]*\)\s*|全队\([^)]*\)\s*|自身\s*|[火水雷风光暗]属性角色的?|角色的?|队长的?|全体队员|全队|协力球|使|赋予|获得)")


def _split(text: str) -> list[str]:
    return [ln.rstrip() for ln in (text or '').split('\n')]


def _icon(line: str) -> bool:
    return bool(ICON_RE.match(line))


def _core(line: str) -> str:
    return ICON_RE.sub('', line).strip()


def _res_cn(res: str | None) -> str | None:
    if not res:
        return None
    if all(c in '火水雷风光暗或' for c in res):
        return res
    return '或'.join(EL_CN.get(x, x) for x in res.split(','))


def _drop_prefix(core: str, res_cn: str | None) -> str:
    """删掉行首（条件链里）的「X属性共鸣时，/：」。res_cn=None 时任何属性都认。"""
    m = RES_RE.search(core)
    if not m:
        return core
    if res_cn and m.group(1) != res_cn:
        return core
    return core[:m.start()] + core[m.end():]


def _norm_res_punct(core: str) -> str:
    return re.sub(r"(属性共鸣时)[：:,]", r"\1，", core)


def _signed(core: str) -> Counter:
    return Counter(re.sub(r"\s+", '', m.group(1)).replace('％', '%') for m in SIGNED_RE.finditer(core))


def _all_tokens(core: str) -> Counter:
    return Counter(m.group(1).replace('％', '%') for m in ANY_RE.finditer(core))


def _unsigned(core: str) -> Counter:
    return _all_tokens(core) - _signed(core)


def _names(core: str) -> list[str]:
    out = []
    for m in SIGNED_RE.finditer(core):
        seg_end = m.start()
        i = seg_end
        while i > 0 and core[i - 1] not in DELIMS:
            i -= 1
        seg = core[i:seg_end].strip()
        last = None
        for mm in OBJ_MARKERS.finditer(seg):
            last = mm
        name = seg[last.end():] if last else seg
        name = name.strip().rstrip('为').strip()
        if len(name) >= 2:
            out.append(name)
    return out


def _as_drop_set(prefix_drops, orig_lines):
    """→ {原文行下标(0 起): res_cn 或 None}"""
    out = {}
    for d in prefix_drops or ():
        res = None
        if isinstance(d, dict):
            res = _res_cn(d.get('resonance'))
            d = d.get('line')
        if isinstance(d, int):
            out[d - 1] = res
        elif isinstance(d, str):
            for i, ln in enumerate(orig_lines):
                if ln.strip() == d.strip() or _core(ln) == _core(d):
                    out[i] = res
    return out


def _check_column(orig: str, merged: str, prefix_drops) -> dict:
    errors, warnings = [], []
    O = _split(orig)
    M = _split(merged)
    drops = _as_drop_set(prefix_drops, O)
    for i in drops:
        if not (0 <= i < len(O)):
            errors.append(f'prefix_drops 行号越界：{i + 1}')
        elif not RES_RE.search(_core(O[i])):
            errors.append(f'prefix_drops 第{i + 1}行原文没有「X属性共鸣时，」：{O[i]}')
    # 原文「有效」形态：授权删前缀的行先删
    E = []
    for i, ln in enumerate(O):
        c = _core(ln)
        if i in drops:
            c = _drop_prefix(c, drops[i])
        E.append(c)

    mapping = {}          # 原文下标 -> 新行下标
    kinds = {}            # 新行下标 -> 'verbatim' | 'prefix_drop' | 'merge'
    used_orig = set()
    # 1) 逐字/仅删前缀
    j0 = 0
    for j, ln in enumerate(M):
        mc = _core(ln)
        for i in range(len(O)):
            if i in used_orig:
                continue
            if ln == O[i]:  # 逐字保留（prefix_drops 是「允许删」，不是必须删）
                mapping[i] = j; kinds[j] = 'verbatim'; used_orig.add(i); break
            if i in drops and _icon(ln) == _icon(O[i]) and \
                    (_norm_res_punct(mc) == _norm_res_punct(E[i])):
                mapping[i] = j; kinds[j] = 'prefix_drop'; used_orig.add(i); break
    # 2) 其余原文行指派到合并行
    rest_new = [j for j in range(len(M)) if j not in kinds]
    for i in range(len(O)):
        if i in used_orig:
            continue
        cands = []
        for j in rest_new:
            mc = _core(M[j])
            if _icon(M[j]) != _icon(O[i]):
                continue
            if _signed(E[i]) - _signed(mc):
                continue
            if any(n not in mc for n in _names(E[i])):
                continue
            if set(_unsigned(E[i])) - set(_unsigned(mc)):
                continue
            cands.append(j)
        if not cands:
            errors.append(f'原文第{i + 1}行找不到归属（数值/效果名/图标对不上）：{O[i]}')
            continue
        # 优先已有来源的合并行，其次位置最近
        prev = [mapping[k] for k in mapping if k < i]
        pick = min(cands, key=lambda j: (0 if j in mapping.values() else 1, abs(j - (max(prev) + 1 if prev else 0))))
        mapping[i] = pick
        kinds[pick] = 'merge'
        used_orig.add(i)
    for j in range(len(M)):
        if j not in kinds:
            errors.append(f'新文案第{j + 1}行没有来源：{M[j]}')

    # 3) 合并行逐个核对
    icon_absorbed = 0
    for j, kind in kinds.items():
        src = sorted(i for i, jj in mapping.items() if jj == j)
        mc = _core(M[j])
        changed = kind != 'verbatim'
        if kind == 'merge':
            if len(src) < 2:
                errors.append(f'新文案第{j + 1}行只有 1 个来源却被改写：{M[j]}（原：{O[src[0]] if src else "?"}）')
            want_signed = sum((_signed(E[i]) for i in src), Counter())
            got_signed = _signed(mc)
            if want_signed != got_signed:
                errors.append(f'新文案第{j + 1}行效果数值多重集合不一致：应 {dict(want_signed)} 实 {dict(got_signed)}')
            un_src = [_unsigned(E[i]) for i in src]
            got_un = _unsigned(mc)
            for t in set().union(*un_src) | set(got_un):
                lo = max(c[t] for c in un_src)
                hi = sum(c[t] for c in un_src)
                if not (lo <= got_un[t] <= hi):
                    errors.append(f'新文案第{j + 1}行条件/后缀记号「{t}」次数 {got_un[t]} 不在 [{lo},{hi}]')
            for i in src:
                for n in _names(E[i]):
                    if n not in mc:
                        errors.append(f'新文案第{j + 1}行缺效果名「{n}」（来自原文第{i + 1}行）')
                if _icon(O[i]) != _icon(M[j]):
                    errors.append(f'原文第{i + 1}行与新文案第{j + 1}行主位图标不一致')
            # 前缀：来源里有授权删除的，合并行不得再写；没授权的不得删
            src_drop = [i for i in src if i in drops]
            if src_drop and RES_RE.search(mc):
                m = RES_RE.search(mc)
                if any(drops[i] in (None, m.group(1)) for i in src_drop):
                    warnings.append(f'新文案第{j + 1}行仍写着「{m.group(0).strip()}」，来源行在 prefix_drops 里（允许删、未删）')
            for i in src:
                m = RES_RE.search(_core(O[i]))
                if m and i not in drops and m.group(1) + '属性共鸣时' not in mc:
                    errors.append(f'新文案第{j + 1}行删掉了原文第{i + 1}行的「{m.group(0).strip()}」，未列入 prefix_drops')
            if _icon(M[j]):
                icon_absorbed += len(src) - 1
        if changed:
            for w in FORBIDDEN:
                if w in mc:
                    errors.append(f'新文案第{j + 1}行含禁用写法「{w}」')
            if re.search(r"属性共鸣时[：:,]", mc):
                errors.append(f'新文案第{j + 1}行共鸣写法须为「X属性共鸣时，」')
        else:
            for w in FORBIDDEN:
                if w in mc:
                    warnings.append(f'未改动的第{j + 1}行原本就含「{w}」（既有问题，未计为错误）')
    # 4) 行序：各新行的「首个来源」须单调
    firsts = []
    for j in range(len(M)):
        src = sorted(i for i, jj in mapping.items() if jj == j)
        if src:
            firsts.append(src[0])
    if firsts != sorted(firsts):
        errors.append(f'行序改变：新行首来源顺序 {[x + 1 for x in firsts]}')
    # 5) 图标行数
    icon_o = sum(_icon(x) for x in O)
    icon_m = sum(_icon(x) for x in M)
    if icon_m != icon_o - icon_absorbed:
        errors.append(f'主位图标行数 {icon_m} ≠ 原 {icon_o} − 被并掉 {icon_absorbed}')
    # 6) 总体效果数值多重集合
    if sum((_signed(e) for e in E), Counter()) != sum((_signed(_core(x)) for x in M), Counter()):
        errors.append('全文效果数值多重集合改变')
    return dict(ok=not errors, errors=errors, warnings=warnings,
                mapping={i + 1: j + 1 for i, j in sorted(mapping.items())},
                kinds={j + 1: k for j, k in sorted(kinds.items())})


def check(orig, merged, prefix_drops=()) -> dict:
    """orig/merged：str 或 list[str]（多列逐列核对）。"""
    if isinstance(orig, str):
        orig = [orig]
    if isinstance(merged, str):
        merged = [merged]
    if len(orig) != len(merged):
        return dict(ok=False, errors=[f'列数不同：原 {len(orig)} 新 {len(merged)}'], warnings=[], columns=[])
    cols = [_check_column(o, m, prefix_drops) for o, m in zip(orig, merged)]
    errors = [f'[列{k + 1}] {e}' for k, c in enumerate(cols) for e in c['errors']]
    warnings = [f'[列{k + 1}] {w}' for k, c in enumerate(cols) for w in c['warnings']]
    if len(cols) > 1:
        shapes = {tuple(sorted(c['kinds'].items())) for c in cols}
        if len(shapes) > 1:
            errors.append('各列改法不一致（合并/删前缀的行位不同）')
    return dict(ok=not errors, errors=errors, warnings=warnings, columns=cols)


def _main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--orig')
    ap.add_argument('--merged')
    ap.add_argument('--drops', default='', help='逗号分隔的原文行号（1 起）')
    ap.add_argument('--drops-json')
    ap.add_argument('--scan')
    ap.add_argument('--id')
    ap.add_argument('--panel')
    ap.add_argument('--proposed-key', default='proposed')
    a = ap.parse_args()
    if a.scan:
        scan = json.loads(Path(a.scan).read_text(encoding='utf-8'))
        chars = scan['characters'] if isinstance(scan, dict) else scan
        bad = 0
        n = 0
        for ch in chars:
            if a.id and ch['id'] != a.id:
                continue
            for p in ch['panels']:
                if a.panel and p['panel'] != a.panel:
                    continue
                if p.get('source') != 'override' or not p.get(a.proposed_key):
                    continue
                n += 1
                drops = [dict(line=d['line_no'], resonance=d['resonance']) for d in p.get('prefix_drops', [])]
                r = check(p['columns'], p[a.proposed_key], drops)
                tag = 'OK ' if r['ok'] else 'ERR'
                print(f"{tag} {ch['id']} {ch.get('name', '')} {p['panel']}")
                for e in r['errors']:
                    print('    E', e)
                for w in r['warnings']:
                    print('    W', w)
                bad += not r['ok']
        print(f'checked {n} panels, {bad} failed')
        sys.exit(1 if bad else 0)
    if not (a.orig and a.merged):
        ap.error('需要 --orig 和 --merged，或 --scan')
    orig = Path(a.orig).read_text(encoding='utf-8')
    merged = Path(a.merged).read_text(encoding='utf-8')
    drops = [int(x) for x in a.drops.split(',') if x.strip()]
    if a.drops_json:
        drops += json.loads(Path(a.drops_json).read_text(encoding='utf-8'))
    r = check(orig.rstrip('\n'), merged.rstrip('\n'), drops)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    sys.exit(0 if r['ok'] else 1)


if __name__ == '__main__':
    _main()
