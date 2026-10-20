"""finddonor.py <ability|leader_ability> <i|d> <kind> [trigger] : 列出 instant/during 内容 kind 的行(可选 trigger kind)。"""
import sys, hw_env, rowx
import wf_mod_tool as core, wf_describe as D
t, mode, kind = sys.argv[1], sys.argv[2], sys.argv[3]
trig = sys.argv[4] if len(sys.argv) > 4 else None
lay = D.layout(t)
EM = D.enum_map()
def c(block, name):
    fb = EM["block_fields"][block]
    return int(lay["blocks"][block]) + next(int(o) for o, n, _ in fb if n == name)
kc = c("instant_content" if mode == "i" else "during_content", "kind")
tc = c("instant_trigger" if mode == "i" else "during_trigger", "kind")
n = 0
for k, v in rowx.table(t).items():
    for i, r in enumerate([r for r in core.read_csv_lines(v) if r]):
        if len(r) > kc and r[kc] == kind and (trig is None or r[tc] == trig):
            print(f"{k}#{i}\t{r[0]}\t{D.describe_rows([r], t)[0]}"); n += 1
            if n > 25: raise SystemExit
