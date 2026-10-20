"""建官方 DSL 索引:构造名 → 程序列表(技能 action_skill 全部 + 629 能力 DSL)。"""
import json, zlib, collections, hw_env
import wf_mod_tool as core, wf_dsl, wf_assets
ACTION = core.ACTION_SKILL_LOGICAL
nested = core.load_nested_table_bytes(core.table_path(hw_env.STORE, ACTION).read_bytes(), ACTION)
progs = set()
for code, om in nested.rows.items():
    for lv, text in om.text_rows().items():
        cells = core.read_csv_lines(text)[0]
        if len(cells) > 7 and cells[7]:
            progs.add(cells[7])
ab = core.read_orderedmap_file_from_bytes(core.table_path(hw_env.STORE, "master/ability/ability.orderedmap").read_bytes())
for k, v in ab.items():
    for r in core.read_csv_lines(v):
        for c in r:
            if c.startswith("battle/action/") and "$" in c:
                progs.add(c)
idx = collections.defaultdict(set)
trees = {}
def walk(n, p):
    if isinstance(n, list):
        if n and isinstance(n[0], str) and n[0][:1].isupper():
            idx[n[0]].add(p)
        for x in n:
            walk(x, p)
    elif isinstance(n, dict):
        for x in n.values():
            walk(x, p)
ok = 0
for p in sorted(progs):
    lg = wf_dsl.dsl_logical(p)
    loc = wf_assets.locate(hw_env.STORE, lg)
    if not loc:
        continue
    try:
        t = wf_dsl.parse_dsl(zlib.decompress(loc[1].read_bytes(), -15))["tree"]
    except Exception:
        continue
    ok += 1
    walk(t, p)
out = {k: sorted(v) for k, v in sorted(idx.items())}
(hw_env.OUT / "research" / "dsl_index.json").write_text(json.dumps(out, ensure_ascii=False, indent=0), "utf-8")
print("programs", len(progs), "parsed", ok, "names", len(out))
