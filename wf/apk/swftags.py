import struct, zlib, sys, io

def load_swf(path):
    raw = open(path,'rb').read()
    sig = raw[:3]
    ver = raw[3]
    filelen = struct.unpack_from('<I', raw, 4)[0]
    if sig == b'FWS':
        body = raw[8:]
    elif sig == b'CWS':
        body = zlib.decompress(raw[8:])
    else:
        raise SystemExit('unsupported sig %r' % sig)
    return sig, ver, filelen, body

def skip_rect(body):
    nbits = body[0] >> 3
    total = 5 + 4*nbits
    return (total + 7)//8

def iter_tags(body):
    off = skip_rect(body)
    off += 4  # framerate(2) + framecount(2)
    while off < len(body):
        if off+2 > len(body): break
        th = struct.unpack_from('<H', body, off)[0]
        code = th >> 6
        length = th & 0x3f
        hdr = 2
        if length == 0x3f:
            length = struct.unpack_from('<I', body, off+2)[0]
            hdr = 6
        yield code, off, hdr, length
        off += hdr + length
        if code == 0:
            break

if __name__ == '__main__':
    path = sys.argv[1]
    sig, ver, filelen, body = load_swf(path)
    print(f'{path}: sig={sig.decode()} ver={ver} declared={filelen} bodylen={len(body)+8}')
    counts = {}
    for code, off, hdr, length in iter_tags(body):
        counts[code] = counts.get(code, (0,0))
        c,s = counts[code]
        counts[code] = (c+1, s+length)
        if code in (72, 82):
            data = body[off+hdr:off+hdr+length]
            if code == 82:
                flags = struct.unpack_from('<I', data, 0)[0]
                nul = data.index(b'\x00', 4)
                name = data[4:nul].decode('utf-8','replace')
                abclen = len(data) - (nul+1)
                print(f'  DoABC2 @0x{off:x} len={length} flags={flags} name={name!r} abc={abclen}')
            else:
                print(f'  DoABC  @0x{off:x} len={length}')
    print('tag histogram (code: count, totalbytes):')
    for k in sorted(counts, key=lambda k:-counts[k][1])[:15]:
        print(f'   {k}: {counts[k]}')
