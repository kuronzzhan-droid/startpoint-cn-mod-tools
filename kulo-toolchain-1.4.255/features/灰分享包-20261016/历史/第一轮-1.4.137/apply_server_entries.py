"""按键应用分享包服务端行。默认仅核对；加 --apply 才写入指定 assets。

全部文件先验证，任一目标键与预期基线不符则拒绝整个批次。
原有 JSON 非目标区域原样保留，包含换行、缩进、键序和 UTF-8 BOM。
"""
import argparse
import codecs
import json
from pathlib import Path
import re


DECODER = json.JSONDecoder()


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'重复 JSON 键 {key}')
        result[key] = value
    return result


def skip(text, i):
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def spans(text):
    """返回顶层对象值的字符区间；JSON 合法性由 json.loads 先保证。"""
    i = skip(text, 0)
    opener = text[i]
    i = skip(text, i + 1)
    values = {}
    while text[i] not in '}]':
        if opener == '{':
            key, i = DECODER.raw_decode(text, i)
            i = skip(text, i)
            if text[i] != ':':
                raise ValueError('JSON 冒号缺失')
            i = skip(text, i + 1)
        else:
            key = len(values)
        start = i
        _, i = DECODER.raw_decode(text, i)
        values[key] = (start, i)
        i = skip(text, i)
        if text[i] == ',':
            i = skip(text, i + 1)
        else:
            break
    return values, skip(text, i)


def render(value, indent, prefix, newline):
    result = json.dumps(value, ensure_ascii=False, indent=indent)
    return result.replace('\n', newline + prefix)


def patch_text(raw, spec):
    bom = raw.startswith(codecs.BOM_UTF8)
    text = raw.decode('utf-8-sig')
    data = json.loads(text, object_pairs_hook=strict_object)
    newline = '\r\n' if '\r\n' in text else '\n'
    match = re.search(r'(?:\r?\n)([ \t]+)["\[{0-9-]', text)
    prefix = match.group(1) if match else '  '
    indent = '\t' if '\t' in prefix else len(prefix)
    positions, closing = spans(text)
    replacements = []
    additions = []
    expected_after = json.loads(text)
    if spec['kind'] == 'object':
        if not isinstance(data, dict):
            raise ValueError('应为对象')
        for entry in spec['entries']:
            key, exp = entry['key'], entry['expected']
            exists = key in data
            if exists != exp['exists'] or (exists and data[key] != exp.get('value')):
                raise ValueError(f'键 {key} 的原值不等于预期基线')
            value = entry['value']
            if exists:
                begin, end = positions[key]
                replacements.append((begin, end, render(value, indent, prefix, newline)))
            else:
                additions.append(json.dumps(key, ensure_ascii=False) + ': ' + render(value, indent, prefix, newline))
            expected_after[key] = value
    elif spec['kind'] == 'id-list':
        if not isinstance(data, list):
            raise ValueError('应为 ID 数组')
        for entry in spec['entries']:
            value = entry['value']
            if value in data:
                raise ValueError(f'ID {value} 已存在，预期原本不存在')
            additions.append(json.dumps(value, ensure_ascii=False))
            expected_after.append(value)
    else:
        raise ValueError(f"不支持 kind={spec['kind']}")
    if additions:
        # 只替换关闭括号前的空白，现有最后一项前后的字节保持原样。
        last_end = max((end for _, end in positions.values()), default=text.index('{' if isinstance(data, dict) else '[') + 1)
        insert = (',' if data else '') + newline + prefix
        insert += (',' + newline + prefix).join(additions) + newline
        replacements.append((last_end, closing, insert))
    for begin, end, value in sorted(replacements, reverse=True):
        text = text[:begin] + value + text[end:]
    if json.loads(text) != expected_after:
        raise AssertionError('格式拼接后的 JSON 与按键应用结果不一致')
    encoded = text.encode('utf-8')
    return (codecs.BOM_UTF8 + encoded) if bom else encoded


def prepare(assets, document):
    prepared = []
    for spec in document['files']:
        rel = Path(spec['file'])
        if rel.is_absolute() or '..' in rel.parts or rel.parts[0] != 'assets':
            raise ValueError(f'非法相对路径 {rel}')
        target = (assets / Path(*rel.parts[1:])).resolve()
        if not target.is_relative_to(assets):
            raise ValueError(f'目标越界 {target}')
        raw = target.read_bytes() if target.exists() else b'{}\n'
        if not target.exists() and spec['kind'] != 'object':
            raise ValueError(f'ID 列表基线缺失 {target}')
        try:
            after = patch_text(raw, spec)
        except (ValueError, AssertionError) as exc:
            raise ValueError(f'{spec["file"]}: {exc}') from exc
        prepared.append((target, after, len(spec['entries'])))
    return prepared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', required=True, type=Path, help='灰的 assets 目录')
    parser.add_argument('--entries', type=Path, default=Path(__file__).with_name('server-entries.json'))
    parser.add_argument('--apply', action='store_true', help='全部断言通过后按键写入；默认只核对')
    args = parser.parse_args()
    document = json.loads(args.entries.read_text('utf-8-sig'))
    prepared = prepare(args.assets.resolve(), document)
    if args.apply:
        for target, _, _ in prepared:
            temporary = target.with_name(target.name + '.hui-share.tmp')
            if temporary.exists():
                raise ValueError(f'临时文件已存在，拒绝覆盖 {temporary}')
        for target, after, _ in prepared:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + '.hui-share.tmp')
            temporary.write_bytes(after)
            temporary.replace(target)
    print(json.dumps({'mode': 'applied' if args.apply else 'dry-run', 'files': len(prepared),
                      'entries': sum(count for _, _, count in prepared),
                      'assets': str(args.assets.resolve())}, ensure_ascii=False))


if __name__ == '__main__':
    main()
