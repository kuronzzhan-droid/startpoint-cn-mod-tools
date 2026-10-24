"""Minimal-but-complete AVM2 ABC reader/writer (survey + slice builder)."""
import struct

class R:
    def __init__(self, d):
        self.d = d; self.p = 0
    def u8(self):
        v = self.d[self.p]; self.p += 1; return v
    def u16(self):
        v = struct.unpack_from('<H', self.d, self.p)[0]; self.p += 2; return v
    def u30(self):
        v = 0; sh = 0
        for _ in range(5):
            b = self.u8(); v |= (b & 0x7f) << sh
            if not (b & 0x80): return v
            sh += 7
        return v
    def s32(self):
        v = 0; sh = 0
        for _ in range(5):
            b = self.u8(); v |= (b & 0x7f) << sh; sh += 7
            if not (b & 0x80): break
        return v
    def u32(self): return self.s32()
    def d64(self):
        v = struct.unpack_from('<d', self.d, self.p)[0]; self.p += 8; return v
    def raw(self, n):
        v = self.d[self.p:self.p+n]; self.p += n; return v

class W:
    def __init__(self): self.b = bytearray()
    def u8(self, v): self.b.append(v & 0xff)
    def u16(self, v): self.b += struct.pack('<H', v)
    def u30(self, v):
        while True:
            b = v & 0x7f; v >>= 7
            if v: self.b.append(b | 0x80)
            else: self.b.append(b); break
    def s32(self, v): self.u30(v)
    def d64(self, v): self.b += struct.pack('<d', v)
    def raw(self, v): self.b += v
    def out(self): return bytes(self.b)

MN_QName = 0x07; MN_QNameA = 0x0D; MN_RTQName = 0x0F; MN_RTQNameA = 0x10
MN_RTQNameL = 0x11; MN_RTQNameLA = 0x12; MN_Multiname = 0x09; MN_MultinameA = 0x0E
MN_MultinameL = 0x1B; MN_MultinameLA = 0x1C; MN_TypeName = 0x1D


class Trait:
    __slots__ = ('name', 'kind', 'attr', 'data', 'metadata')


def read_trait(r):
    t = Trait()
    t.name = r.u30()
    kb = r.u8()
    t.kind = kb & 0x0f; t.attr = kb >> 4
    k = t.kind
    if k in (0, 6):
        slot_id = r.u30(); type_name = r.u30(); vindex = r.u30()
        vkind = r.u8() if vindex else None
        t.data = ['slot', slot_id, type_name, vindex, vkind]
    elif k == 4:
        t.data = ['class', r.u30(), r.u30()]
    elif k == 5:
        t.data = ['function', r.u30(), r.u30()]
    elif k in (1, 2, 3):
        t.data = ['method', r.u30(), r.u30()]
    else:
        raise ValueError('trait kind %d' % k)
    t.metadata = []
    if t.attr & 0x4:
        n = r.u30()
        t.metadata = [r.u30() for _ in range(n)]
    return t


def write_trait(w, t):
    w.u30(t.name); w.u8(t.kind | (t.attr << 4))
    d = t.data
    if d[0] == 'slot':
        w.u30(d[1]); w.u30(d[2]); w.u30(d[3])
        if d[3]: w.u8(d[4])
    else:
        w.u30(d[1]); w.u30(d[2])
    if t.attr & 0x4:
        w.u30(len(t.metadata))
        for m in t.metadata: w.u30(m)


class ABC:
    def __init__(self, data):
        r = R(data)
        self.minor = r.u16(); self.major = r.u16()
        n = r.u30(); self.ints = [0] + [r.s32() for _ in range(max(0, n - 1))]
        n = r.u30(); self.uints = [0] + [r.u32() for _ in range(max(0, n - 1))]
        n = r.u30(); self.doubles = [0.0] + [r.d64() for _ in range(max(0, n - 1))]
        n = r.u30(); self.strings = [b'']
        for _ in range(max(0, n - 1)):
            self.strings.append(r.raw(r.u30()))
        n = r.u30(); self.namespaces = [(0, 0)]
        for _ in range(max(0, n - 1)):
            self.namespaces.append((r.u8(), r.u30()))
        n = r.u30(); self.ns_sets = [()]
        for _ in range(max(0, n - 1)):
            c = r.u30(); self.ns_sets.append(tuple(r.u30() for _ in range(c)))
        n = r.u30(); self.multinames = [(0,)]
        for _ in range(max(0, n - 1)):
            k = r.u8()
            if k in (MN_QName, MN_QNameA, MN_Multiname, MN_MultinameA):
                self.multinames.append((k, r.u30(), r.u30()))
            elif k in (MN_RTQName, MN_RTQNameA, MN_MultinameL, MN_MultinameLA):
                self.multinames.append((k, r.u30()))
            elif k in (MN_RTQNameL, MN_RTQNameLA):
                self.multinames.append((k,))
            elif k == MN_TypeName:
                base = r.u30(); c = r.u30()
                self.multinames.append((k, base, tuple(r.u30() for _ in range(c))))
            else:
                raise ValueError('multiname kind 0x%x at %d' % (k, len(self.multinames)))
        n = r.u30(); self.methods = []
        for _ in range(n):
            pc = r.u30(); ret = r.u30()
            ptypes = [r.u30() for _ in range(pc)]
            name = r.u30(); flags = r.u8()
            options = None; pnames = None
            if flags & 0x08:
                c = r.u30(); options = [(r.u30(), r.u8()) for _ in range(c)]
            if flags & 0x80:
                pnames = [r.u30() for _ in range(pc)]
            self.methods.append([ret, ptypes, name, flags, options, pnames])
        n = r.u30(); self.metadata = []
        for _ in range(n):
            nm = r.u30(); c = r.u30()
            items = [(r.u30(), r.u30()) for _ in range(c)]
            self.metadata.append((nm, items))
        n = r.u30(); self.instances = []
        for _ in range(n):
            name = r.u30(); sup = r.u30(); flags = r.u8()
            pns = r.u30() if flags & 0x08 else None
            ic = r.u30(); ifaces = [r.u30() for _ in range(ic)]
            iinit = r.u30(); tc = r.u30()
            traits = [read_trait(r) for _ in range(tc)]
            self.instances.append([name, sup, flags, pns, ifaces, iinit, traits])
        self.classes = []
        for _ in range(n):
            cinit = r.u30(); tc = r.u30()
            self.classes.append([cinit, [read_trait(r) for _ in range(tc)]])
        n = r.u30(); self.scripts = []
        for _ in range(n):
            init = r.u30(); tc = r.u30()
            self.scripts.append([init, [read_trait(r) for _ in range(tc)]])
        n = r.u30(); self.bodies = []
        for _ in range(n):
            m = r.u30(); ms = r.u30(); lc = r.u30(); isd = r.u30(); msd = r.u30()
            cl = r.u30(); code = r.raw(cl)
            ec = r.u30()
            exc = [(r.u30(), r.u30(), r.u30(), r.u30(), r.u30()) for _ in range(ec)]
            tc = r.u30()
            traits = [read_trait(r) for _ in range(tc)]
            self.bodies.append([m, ms, lc, isd, msd, code, exc, traits])
        assert r.p == len(data), (r.p, len(data))

    def s(self, i):
        return self.strings[i].decode('utf-8', 'replace')

    def ns_name(self, i):
        k, ni = self.namespaces[i]
        return self.s(ni)

    def mn_name(self, i):
        if i == 0: return '*'
        m = self.multinames[i]
        if m[0] in (MN_QName, MN_QNameA):
            ns = self.ns_name(m[1]); nm = self.s(m[2])
            return (ns + '::' + nm) if ns else nm
        if m[0] == MN_TypeName:
            return self.mn_name(m[1]) + '.<' + ','.join(self.mn_name(x) for x in m[2]) + '>'
        if m[0] in (MN_Multiname, MN_MultinameA):
            return self.s(m[1])
        if m[0] in (MN_RTQName, MN_RTQNameA):
            return self.s(m[1])
        return '<mn kind 0x%x>' % m[0]

    def serialize(self):
        w = W()
        w.u16(self.minor); w.u16(self.major)
        w.u30(len(self.ints))
        for v in self.ints[1:]: w.s32(v)
        w.u30(len(self.uints))
        for v in self.uints[1:]: w.u30(v)
        w.u30(len(self.doubles))
        for v in self.doubles[1:]: w.d64(v)
        w.u30(len(self.strings))
        for s in self.strings[1:]:
            w.u30(len(s)); w.raw(s)
        w.u30(len(self.namespaces))
        for k, ni in self.namespaces[1:]:
            w.u8(k); w.u30(ni)
        w.u30(len(self.ns_sets))
        for st in self.ns_sets[1:]:
            w.u30(len(st))
            for x in st: w.u30(x)
        w.u30(len(self.multinames))
        for m in self.multinames[1:]:
            k = m[0]; w.u8(k)
            if k in (MN_QName, MN_QNameA, MN_Multiname, MN_MultinameA):
                w.u30(m[1]); w.u30(m[2])
            elif k in (MN_RTQName, MN_RTQNameA, MN_MultinameL, MN_MultinameLA):
                w.u30(m[1])
            elif k in (MN_RTQNameL, MN_RTQNameLA):
                pass
            elif k == MN_TypeName:
                w.u30(m[1]); w.u30(len(m[2]))
                for x in m[2]: w.u30(x)
        w.u30(len(self.methods))
        for ret, ptypes, name, flags, options, pnames in self.methods:
            w.u30(len(ptypes)); w.u30(ret)
            for x in ptypes: w.u30(x)
            w.u30(name); w.u8(flags)
            if flags & 0x08:
                w.u30(len(options))
                for vi, vk in options: w.u30(vi); w.u8(vk)
            if flags & 0x80:
                for x in pnames: w.u30(x)
        w.u30(len(self.metadata))
        for nm, items in self.metadata:
            w.u30(nm); w.u30(len(items))
            for k, v in items: w.u30(k); w.u30(v)
        w.u30(len(self.instances))
        for name, sup, flags, pns, ifaces, iinit, traits in self.instances:
            w.u30(name); w.u30(sup); w.u8(flags)
            if flags & 0x08: w.u30(pns)
            w.u30(len(ifaces))
            for x in ifaces: w.u30(x)
            w.u30(iinit); w.u30(len(traits))
            for t in traits: write_trait(w, t)
        for cinit, traits in self.classes:
            w.u30(cinit); w.u30(len(traits))
            for t in traits: write_trait(w, t)
        w.u30(len(self.scripts))
        for init, traits in self.scripts:
            w.u30(init); w.u30(len(traits))
            for t in traits: write_trait(w, t)
        w.u30(len(self.bodies))
        for m, ms, lc, isd, msd, code, exc, traits in self.bodies:
            w.u30(m); w.u30(ms); w.u30(lc); w.u30(isd); w.u30(msd)
            w.u30(len(code)); w.raw(code)
            w.u30(len(exc))
            for e in exc:
                for x in e: w.u30(x)
            w.u30(len(traits))
            for t in traits: write_trait(w, t)
        return w.out()
