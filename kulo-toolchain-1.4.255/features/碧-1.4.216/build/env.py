import os, glob
LS = r"D:/WF/out/十项收尾-20261015/localsrv/assets/asset-patch/active"
EXTRA_DIRS = [LS] + [d for d in os.environ.get("WF_EXTRA_DIRS","").split(";") if d]
def setup(tip=212):
    zs=[]
    for v in range(206, tip):
        for d in EXTRA_DIRS:
            got=sorted(glob.glob(os.path.join(d, f"pinball-1.4.{v}-1.4.{v+1}-*.zip")))
            if got: zs+=got; break
        else: raise SystemExit(f"missing edge {v}->{v+1}")
    os.environ["WF_TIP"]="206"; os.environ["WF_EXTRA_ZIPS"]=";".join(zs)
    import sys; sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
