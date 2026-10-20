"""dsl_dump.py <program> : 打印 DSL 树(紧凑 JSON,每个顶层语句一行)。"""
import sys, json, zlib, hw_env
import wf_dsl, wf_assets
def load(program):
    lg = program if program.endswith(".deflate") else wf_dsl.dsl_logical(program)
    loc = wf_assets.locate(hw_env.STORE, lg)
    if loc is None:
        raise SystemExit(f"missing {lg}")
    return wf_dsl.parse_dsl(zlib.decompress(loc[1].read_bytes(), -15))["tree"]
def show(node, depth=0, out=None):
    out = out if out is not None else []
    s = json.dumps(node, ensure_ascii=False)
    if len(s) < 220 or not isinstance(node, list):
        out.append("  " * depth + s)
    else:
        out.append("  " * depth + "[")
        for x in node:
            show(x, depth + 1, out)
        out.append("  " * depth + "]")
    return out
if __name__ == "__main__":
    for p in sys.argv[1:]:
        print("######", p)
        print("\n".join(show(load(p))))
