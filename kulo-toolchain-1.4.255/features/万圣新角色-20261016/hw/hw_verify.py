import sys, json, hw_env
import wf_midautumn_verify as V
for name in dir(V):
    obj = getattr(V, name)
    if isinstance(obj, type) and isinstance(getattr(obj, "store", None), property):
        setattr(obj, "store", property(lambda self: hw_env.STORE))
rc = {}
for k in ("ludi", "momiya", "seriol", "recital"):
    ws = hw_env.ROOT / "work" / "character_packs" / f"hw-{k}"
    out = hw_env.OUT / "patch" / f"verify-{k}.json"
    try:
        rc[k] = V.main(["--workspace", str(ws), "--skip-atlas", "--out", str(out), "--root", str(hw_env.ROOT)])
    except SystemExit as e:
        rc[k] = e.code
    except Exception as e:
        rc[k] = repr(e)[:300]
print(rc)
