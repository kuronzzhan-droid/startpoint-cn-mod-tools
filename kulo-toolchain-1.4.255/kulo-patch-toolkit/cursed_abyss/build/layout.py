import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_describe as D
EM = D.enum_map()
OFF = {b: {name: int(o) for o, name, _ in f} for b, f in EM["block_fields"].items()}
CASES = EM["cases"]
def col(table, block, name):
    lay = D.layout(table)
    fb = OFF["precondition" if block.startswith("precondition") else block]
    return int(lay["blocks"][block]) + fb[name]
def mode_col(table):
    return int(D.layout(table)["blocks"]["precondition1"]) - 1
def name_of(enum, k):
    v = EM["enums"][enum]; 
    return v.get(str(k)) if isinstance(v, dict) else (v[int(k)] if str(k).isdigit() and int(k) < len(v) else None)
