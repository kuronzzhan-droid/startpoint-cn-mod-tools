"""Validate flatomo per-image pools used by fetchDisplayObject (native F1125).

PartsAnimationSource.a is the number of simultaneous DisplayObjects allocated
for EACH image, not a texture count. Include transparent instances as native
moveImage fetches the object before setting its alpha.
"""
from functools import lru_cache


def image_capacities(parts):
    if parts.get('m'):
        raise ValueError('movie clips require a separate capacity model')
    groups=parts['g'];size=len(parts['i']);compiled=[]
    for group in groups:
        strips=[]
        for strip in group['s']:
            bits=int(strip['s'])&0xffffffff;kind=bits>>30
            cursor=bits&0x3fffffff;keys=[]
            if kind not in (0,2):raise ValueError('unsupported strip kind')
            target=int(strip['i'])
            if not 0<=target<(size if kind==0 else len(groups)):
                raise ValueError('strip target outside native pool')
            for key in strip['l']:
                duration=1 if key.get('t') is None else int(key['t'])&0xffff
                end=cursor+duration
                if end>group['t']:raise ValueError('strip frame overflow')
                keys.append((cursor,end,int(key.get('r') or 0)&0xffffffff))
                cursor=end
            strips.append((kind,target,keys))
        compiled.append(strips)
    active=set()

    @lru_cache(None)
    def count(gid,frame):
        if gid in active:raise ValueError('graphics reference cycle')
        active.add(gid);counts=[0]*size
        try:
            for kind,target,keys in compiled[gid]:
                for start,end,ref in keys:
                    if not start<=frame<end:continue
                    if kind==0:counts[target]+=1
                    else:
                        loop,base=ref>>30,ref&0x3fffffff;total=groups[target]['t']
                        if loop==0:future=base
                        elif loop==1:future=min(base+frame-start,total-1)
                        elif loop==2:future=(base+frame-start)%total
                        else:raise ValueError('invalid graphics loop kind')
                        if 0<=future<total:
                            for i,n in enumerate(count(target,future)):counts[i]+=n
                    break
        finally:active.remove(gid)
        return tuple(counts)

    peak=[0]*size
    for frame in range(groups[0]['t']):
        peak=[max(a,b) for a,b in zip(peak,count(0,frame))]
    return peak


def validate_image_capacities(parts):
    need=image_capacities(parts);available=parts['a']
    if len(available)!=len(need) or any(a<n for a,n in zip(available,need)):
        raise ValueError(f'native image capacity exceeded: allocated={available}, required={need}')
    return need
