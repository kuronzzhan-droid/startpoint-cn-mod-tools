"""Client-derived EnemyDsl field/constructor codec, with an exact wire image."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .behavior_wire import decode_wire, encode_wire

ROOT_TYPE = 'pinball.scene.battle.battle.enemy.standard.EnemyDsl'
_TYPES = json.loads(Path(__file__).with_name('enemy_types.json').read_text(encoding='utf-8'))['types']


def transform(value, typename=ROOT_TYPE, *, encode=False):
    if value is None:
        return None
    info = _TYPES[typename]
    kind = info['kind']
    if kind == 'ABSTRACT':
        return transform(value, info['item'], encode=encode)
    if kind == 'COLLECTION':
        if not isinstance(value, list):
            raise ValueError(f'{typename} requires array')
        return [transform(v, info['item'], encode=encode) for v in value]
    if kind in ('MAP', 'DYNAMIC_ACCESS'):
        return {k: transform(v, info['item'], encode=encode) for k, v in value.items()}
    if kind == 'ANONYMOUS':
        if info['array']:
            return [transform(v, info['fields'][info['order'][i]], encode=encode) for i, v in enumerate(value)]
        aliases = info['aliases']
        reverse = {v: k for k, v in aliases.items()}
        output = {}
        for key, item in value.items():
            name = key if encode else reverse.get(key, key)
            if name not in info['fields']:
                raise ValueError(f'unknown {typename} field: {key}')
            target = aliases.get(name, name) if encode else name
            output[target] = transform(item, info['fields'][name], encode=encode)
        return output
    if kind == 'ENUM':
        if not isinstance(value, list) or not value:
            raise ValueError(f'{typename} requires constructor array')
        aliases = info['aliases']
        reverse = {v: k for k, v in aliases.items()}
        name = value[0] if encode else reverse.get(value[0], value[0])
        if name not in info['constructors']:
            raise ValueError(f'unknown {typename} constructor: {name}')
        arguments = info['arguments'][str(info['constructors'][name])]
        if len(arguments) != len(value) - 1:
            raise ValueError(f'{typename}/{name}: incorrect argument count')
        return [aliases.get(name, name) if encode else name,
                *[transform(item, arg, encode=encode) for item, arg in zip(value[1:], arguments)]]
    return copy.deepcopy(value)


def decode_esdl(raw):
    document = decode_wire(raw)
    document['tree'] = transform(document['tree'])
    return {'schema': 'wf-esdl/1', **document}


def encode_esdl(document):
    if document.get('schema') != 'wf-esdl/1':
        raise ValueError('unknown esdl document schema')
    original = decode_wire(__import__('base64').b64decode(document['wire'], validate=True))['tree']
    # Preserve long/short key choices as well as absent/default optional fields.
    if transform(original) == document['tree']:
        return encode_wire(document, original)
    return encode_wire(document, transform(document['tree'], encode=True))
