from pathlib import Path
here = Path(__file__).resolve().parent
s = Path(r"D:/WF/out/角色超限-120/device/wf.ps1").read_text("utf-8-sig")
old = "$out='D:\\WF\\out\\角色超限-120\\device\\shots'"
assert old in s
s = s.replace(old, "$out='" + str(here / "shots") + "'")
(here / "wf.ps1").write_text(s, "utf-8-sig")
print("ok")
