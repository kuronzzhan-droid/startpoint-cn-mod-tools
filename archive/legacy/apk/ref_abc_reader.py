"""Minimal read-only ABC reader for method-body provenance, using stdlib only."""
from pathlib import Path
import struct
import zlib


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, count):
        result = self.data[self.pos:self.pos + count]
        if len(result) != count:
            raise ValueError('Unexpected EOF')
        self.pos += count
        return result

    def byte(self):
        return self.take(1)[0]

    def u30(self):
        result = 0
        for shift in range(0, 35, 7):
            value = self.byte()
            result |= (value & 127) << shift
            if value < 128:
                return result
        raise ValueError('Invalid encoded integer')

    def many(self):
        return [self.u30() for _ in range(self.u30())]


def abc_blocks(path):
    original = Path(path).read_bytes()
    if original[:3] == b'CWS':
        data = original[:8] + zlib.decompress(original[8:])
    elif original[:3] == b'FWS':
        data = original
    else:
        raise ValueError('Unsupported SWF compression')
    rect_bits = data[8] >> 3
    pos = 8 + (5 + 4 * rect_bits + 7) // 8 + 4
    while pos < len(data):
        tag = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        kind, size = tag >> 6, tag & 63
        if size == 63:
            size = struct.unpack_from('<I', data, pos)[0]
            pos += 4
        content = data[pos:pos + size]
        if kind == 82:
            end = content.index(b'\0', 4)
            yield content[4:end].decode('utf-8'), content[end + 1:]
        pos += size
        if kind == 0:
            break


class ABC:
    def __init__(self, data):
        self.reader = r = Reader(data)
        self.version = struct.unpack('<HH', r.take(4))
        for _ in range(2):
            for i in range(max(0, r.u30() - 1)):
                r.u30()
        r.take(max(0, r.u30() - 1) * 8)
        self.strings = ['']
        for _ in range(max(0, r.u30() - 1)):
            self.strings.append(r.take(r.u30()).decode('utf-8', errors='replace'))
        self.namespaces = [(0, 0)]
        for _ in range(max(0, r.u30() - 1)):
            self.namespaces.append((r.byte(), r.u30()))
        self.nssets = [[]]
        for _ in range(max(0, r.u30() - 1)):
            self.nssets.append(r.many())
        self.names = [(0, ())]
        for _ in range(max(0, r.u30() - 1)):
            kind = r.byte()
            if kind in (7, 13, 9, 14):
                values = (r.u30(), r.u30())
            elif kind in (15, 16, 27, 28):
                values = (r.u30(),)
            elif kind in (17, 18):
                values = ()
            elif kind == 29:
                values = (r.u30(), tuple(r.many()))
            else:
                raise ValueError(f'Multiname kind {kind}')
            self.names.append((kind, values))
        self.methods = []
        for _ in range(r.u30()):
            count, returns = r.u30(), r.u30()
            params = [r.u30() for _ in range(count)]
            name, flags = r.u30(), r.byte()
            if flags & 8:
                for _ in range(r.u30()):
                    r.u30(); r.byte()
            if flags & 128:
                for _ in range(count):
                    r.u30()
            self.methods.append({'params': params, 'returns': returns, 'name': name, 'flags': flags})
        for _ in range(r.u30()):
            r.u30()
            count = r.u30()
            for _ in range(2 * count):
                r.u30()
        class_count = r.u30()
        self.instances = []
        for _ in range(class_count):
            name, base, flags = r.u30(), r.u30(), r.byte()
            if flags & 8:
                r.u30()
            interfaces, constructor = r.many(), r.u30()
            self.instances.append({'name': name, 'base': base, 'constructor': constructor,
                                   'traits': self.traits()})
        self.classes = []
        for _ in range(class_count):
            self.classes.append({'initializer': r.u30(), 'traits': self.traits()})
        self.scripts = []
        for _ in range(r.u30()):
            self.scripts.append({'initializer': r.u30(), 'traits': self.traits()})
        self.bodies = {}
        for _ in range(r.u30()):
            method = r.u30()
            info = dict(zip(('max_stack', 'locals', 'scope_in', 'scope_max'), [r.u30() for _ in range(4)]))
            info['offset'] = r.pos
            info['code'] = r.take(r.u30())
            info['exceptions'] = [tuple(r.u30() for _ in range(5)) for _ in range(r.u30())]
            info['traits'] = self.traits()
            self.bodies[method] = info
        if r.pos != len(data):
            raise ValueError(f'Unparsed ABC tail: {len(data) - r.pos}')

    def traits(self):
        r = self.reader
        result = []
        for _ in range(r.u30()):
            name, tag = r.u30(), r.byte()
            kind = tag & 15
            if kind in (0, 6):
                values = [r.u30(), r.u30(), r.u30()]
                if values[2]:
                    values.append(r.byte())
            elif kind in (1, 2, 3, 4, 5):
                values = [r.u30(), r.u30()]
            else:
                raise ValueError(f'Trait kind {kind}')
            if tag & 64:
                r.many()
            result.append({'name': name, 'kind': kind, 'values': values})
        return result

    def qname(self, index):
        kind, values = self.names[index]
        if kind in (7, 13):
            namespace = self.strings[self.namespaces[values[0]][1]]
            name = self.strings[values[1]]
            return namespace + '.' + name if namespace else name
        return repr((kind, values))


if __name__ == '__main__':
    for name, data in abc_blocks(Path(__file__).resolve().parents[1] / 'apk/worldflipper_android_release.swf'):
        if name != 'boot_ffc6':
            continue
        abc = ABC(data)
        print(name, abc.version, len(abc.methods), 'methods', len(abc.instances), 'classes')
        for method in (63, 64):
            print(method, abc.methods[method], abc.bodies[method]['code'].hex())
