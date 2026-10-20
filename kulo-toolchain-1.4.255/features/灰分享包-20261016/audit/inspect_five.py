import sys, json, zipfile
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '交付/build'))
from common import *
from merge_core import changed_rows, MISSING

def main():
    inp=json.loads((ROOT/'audit/inputs.json').read_text('utf-8'))
    paths=logical_index()
    state={}
    for e in inp['ours']:
        with zipfile.ZipFile(e['path']) as z:
            for m in z.namelist():
                raw=z.read(m)
                if 'five-boss' in e['name']:
                    b=state.get(m,base_raw(m))
                    try:
                        old=q.parse_node(b) if b is not None else {}
                        new=q.parse_node(raw)
                        delta=changed_rows(old,new)
                        print(e['name'],paths.get(m,m),len(delta))
                        for r in delta[:7]: print(str(r)[:1500])
                    except ValueError: print('binary',m,len(raw))
                state[m]=raw
    hv=View('hui')
    print('gray preload members')
    with zipfile.ZipFile(inp['hui'][-1]['path']) as z:
        for m in z.namelist():
            n=q.parse_node(z.read(m))
            b=q.parse_node(base_raw(m)) if base_raw(m) else {}
            ds=changed_rows(b,n)
            print(m,paths.get(m),len(ds)); print(json.dumps(ds,ensure_ascii=False)[:14000])

if __name__ == '__main__': main()
