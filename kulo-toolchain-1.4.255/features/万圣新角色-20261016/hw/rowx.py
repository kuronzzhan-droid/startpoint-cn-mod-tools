"""rowx.py <table:ability|leader_ability> <key#idx> ... : 打印 donor 行的「列号 名称=值」(非空)+describe。"""
import sys, hw_env
import wf_mod_tool as core, wf_describe as D
EM = D.enum_map()
def names(table):
    lay = D.layout(table)
    m = {}
    for block, start in lay["blocks"].items():
        fb = EM["block_fields"]["precondition" if block.startswith("precondition") else block]
        for o, name, _ in fb:
            m[int(start) + int(o)] = f"{block}.{name}"
    return m
T = {}
def table(t):
    if t not in T:
        lg = f"master/ability/{t}.orderedmap"
        T[t] = core.read_orderedmap_file_from_bytes(core.table_path(hw_env.STORE, lg).read_bytes())
    return T[t]
if __name__ == "__main__":
    t = sys.argv[1]
    nm = names(t)
    for spec in sys.argv[2:]:
        k, _, i = spec.partition("#")
        rs = [r for r in core.read_csv_lines(table(t)[k]) if r]
        r = rs[int(i or 0)]
        print("=====", spec, len(r), D.describe_rows([r], t)[0])
        print("  ", "  ".join(f"{c}:{nm.get(c,'?')}={v}" for c, v in enumerate(r) if v not in ("",)))
