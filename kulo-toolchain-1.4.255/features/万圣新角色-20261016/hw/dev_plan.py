"""设备备份/还原计划：1.4.212→1.4.221 链上所有成员。生成 backup.sh / restore.sh 到共享目录 hw/。"""
import json, re, zipfile
from pathlib import Path
import hw_env
ACT = hw_env.OUT / "localsrv" / "assets" / "asset-patch" / "active"
S = Path(r"D:/WF/MuMuPlayer/vms/MuMuPlayer-15.0-1/private_shared/hw")
names = set()
for z in sorted(ACT.glob("pinball-1.4.*.zip")):
    m = re.match(r"pinball-1\.4\.(\d+)-1\.4\.(\d+)-", z.name)
    if m and int(m.group(1)) >= 212:
        for n in zipfile.ZipFile(z).namelist():
            if not n.endswith("/"):
                names.add(n)
names = sorted(names)
D = "/data/data/com.leiting.wf/com.leiting.wf/Local Store/asset/asset_download/dummy"
B = "/mnt/shared/private_shared/hw/backup212"
bk = ["set -u", f'mkdir -p {B}', f'cd "{D}"', f'cp info.json {B}/info.json', f': > {B}/existed.txt']
rs = ["set -u", f'cd "{D}"']
for n in names:
    flat = n.replace("/", "_")
    bk.append(f'if [ -f "download/{n}" ]; then cp "download/{n}" {B}/{flat}; echo {n} >> {B}/existed.txt; fi')
bk.append(f'wc -l {B}/existed.txt; echo done')
rs.append(f'while read n; do f=$(echo $n | tr / _); cp {B}/$f "download/$n"; done < {B}/existed.txt')
rs.append("for n in " + " ".join(names) + f'; do grep -qx $n {B}/existed.txt || rm -f "download/$n"; done')
rs.append(f'cp {B}/info.json info.json; chown -R $(stat -c %u:%g info.json) download info.json; cat info.json; echo; echo restored')
(S / "backup212.sh").write_text("\n".join(bk) + "\n", "utf-8", newline="\n")
(S / "restore212.sh").write_text("\n".join(rs) + "\n", "utf-8", newline="\n")
print(len(names))
