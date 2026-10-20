import hw_env
import wf_mod_tool as core, wf_describe
from pathlib import Path
import zlib
OUT = hw_env.OUT / "research"
OUT.mkdir(exist_ok=True)
for logical, kind, fn in (("master/ability/ability.orderedmap", "ability", "ability_desc.txt"),
                          ("master/ability/leader_ability.orderedmap", "leader_ability", "leader_desc.txt")):
    raw = core.table_path(hw_env.STORE, logical).read_bytes()
    t = core.read_orderedmap_file_from_bytes(raw)
    lines = []
    for k, v in t.items():
        rs = [r for r in core.read_csv_lines(v) if r]
        for i, r in enumerate(rs):
            try:
                d = wf_describe.describe_rows([r], kind)[0]
            except Exception as e:
                d = f"!!{e}"
            lines.append(f"{k}#{i}\t{r[0]}\t{d}")
    (OUT / fn).write_text("\n".join(lines), "utf-8")
    print(fn, len(lines))
