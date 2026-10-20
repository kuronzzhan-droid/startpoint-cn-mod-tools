import json,sys
def outline(n,d=0,out=None):
    out=[] if out is None else out
    if isinstance(n,list) and n and isinstance(n[0],str) and n[0] in ('Command','Event'):
        c=n[1]; out.append('  '*d+n[0][0]+' '+c[0]+' '+json.dumps([x for x in c[1:] if not (isinstance(x,list) and x and x[0]=='Block')],ensure_ascii=False)[:330])
        for x in c[1:]:
            if isinstance(x,list) and x and x[0]=='Block': [outline(y,d+1,out) for y in x[1]]
        return out
    if isinstance(n,list):
        for x in n: outline(x,d,out)
    return out
if __name__=='__main__':
    for f in sys.argv[1:]:
        t=json.load(open(f,encoding='utf8')); print('=====',f, json.dumps(t[:11]))
        for l in outline(t[11]): print(l)
