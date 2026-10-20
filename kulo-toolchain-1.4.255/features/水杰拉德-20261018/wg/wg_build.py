# -*- coding: utf-8 -*-
"""水杰拉德构建 CLI(薄壳复用 wf_seasonal7_build 的步骤，结构照万圣四角色 hw/)。
    python wg_build.py --char aqua --step init,tables,kit,assets
"""
from __future__ import annotations
import argparse, importlib, json, sys, traceback
import wg_env
import wg_common as HC
import wg_specs as HS
import wf_seasonal7_build as B
import wf_midautumn_common as MC

STEPS = ("donors", "pixel", "init", "tables", "kit", "extras", "assets", "art")


def step_donors(pack):
    out = {}
    for el, pf in ((pack.spec.element, pack.spec.pf_type),):
        cands = MC.donor_candidates(pack, el, pf)
        out = {"n": len(cands), "median": cands[(len(cands) - 1) // 2] if cands else None,
               "cands": cands}
    return out


def step_kit(pack):
    name = f"wg_kit_{pack.spec.key}"
    try:
        mod = importlib.import_module(name)
    except ModuleNotFoundError:
        return {"skipped": True, "reason": f"{name}.py 不存在"}
    return {"result": mod.build(B.KitContext(pack))}


def run_step(step, pack, args):
    if step == "donors":
        return step_donors(pack)
    if step == "kit":
        return step_kit(pack)
    if step == "pixel":
        import wg_pixel
        return wg_pixel.build(pack)
    if step == "extras":
        import wg_extras
        return wg_extras.build(pack)
    return B.run_step(step, pack, args)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", required=True)
    ap.add_argument("--step", required=True)
    ap.add_argument("--landmarks"); ap.add_argument("--source-dir"); ap.add_argument("--headshots", action="store_true")
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--installed-package-dir")
    ap.add_argument("--brief", action="store_true")
    args = ap.parse_args(argv)
    keys = HS.all_keys() if args.char == "all" else args.char.split(",")
    steps = args.step.split(",")
    res, code = {}, 0
    for k in keys:
        pack = HC.pack_for(k)
        res[k] = {}
        for s in steps:
            try:
                r = run_step(s, pack, args)
                res[k][s] = r if not args.brief else str(r)[:600]
            except Exception as e:
                res[k][s] = {"error": f"{type(e).__name__}: {e}", "tb": traceback.format_exc()[-2500:]}
                code = 2
                break
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
