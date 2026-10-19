"""Extract the reachable EnemyDsl TypePacker definitions from client source."""
import hashlib
import json
from pathlib import Path
import re
import sys


def split_args(text):
    out, start, depth, quoted = [], 0, 0, False
    for index, char in enumerate(text):
        if char == '"': quoted = not quoted
        if not quoted:
            if char in '([': depth += 1
            elif char in ')]': depth -= 1
            elif char == ',' and depth == 0:
                out.append(text[start:index]); start = index + 1
    return [part.strip() for part in [*out, text[start:]]]


def extract(source):
    maps = {}
    for match in re.finditer(r'public function resolveMap(\d+)\(\) : IMap\s*\{(.*?)\n      \}', source, re.S):
        maps[match[1]] = {str(json.loads(key)): json.loads(value)
            for key, value in re.findall(r'_loc1_\.h\[("[^"]*"|\d+)\] = ("[^"\n]*"|\[[^;]*\]|-?\d+|true|false|null);', match[2])}
    types = {}
    for match in re.finditer(r'_loc2_ = TypeInformation\.(\w+)(?:\(([^\n]*)\))?;\s*if\("([^"]+)"', source):
        kind, args, name = match.groups(); vals = split_args(args) if args else []
        def mapping(value):
            if value.startswith('new '): return {}
            return maps[re.fullmatch(r'(?:this\.)?resolveMap(\d+)\(\)', value)[1]] if value != 'null' else {}
        if kind == 'ANONYMOUS':
            definition = {'kind': kind, 'fields': mapping(vals[0]), 'aliases': mapping(vals[2]), 'array': vals[3] == 'true', 'order': json.loads(vals[1])}
        elif kind == 'ENUM':
            definition = {'kind': kind, 'constructors': mapping(vals[2]), 'arguments': mapping(vals[3]), 'aliases': mapping(vals[4])}
        elif kind in ('ABSTRACT','COLLECTION','DYNAMIC_ACCESS'):
            definition = {'kind': kind, 'item': json.loads(vals[0])}
        elif kind == 'MAP':
            definition = {'kind': kind, 'item': json.loads(vals[1])}
        else:
            definition = {'kind': kind}
        types[name] = definition
    found = {}
    def visit(name):
        if name in found: return
        if name not in types: raise ValueError('missing type '+name)
        node=types[name]; found[name]=node
        children = [node['item']] if 'item' in node else list(node.get('fields',{}).values())
        children += [arg for args in node.get('arguments',{}).values() for arg in args]
        for child in children: visit(child)
    visit('pinball.scene.battle.battle.enemy.standard.EnemyDsl')
    return {'source':'TypePackerResource2.as','source_sha256':hashlib.sha256(source.encode()).hexdigest(),'types':found}

if __name__ == '__main__':
    source_file = Path(sys.argv[1])
    result = extract(source_file.read_text(encoding='utf-8-sig'))
    result['source_sha256'] = hashlib.sha256(source_file.read_bytes()).hexdigest()
    Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('reachable types:',len(result['types']))
