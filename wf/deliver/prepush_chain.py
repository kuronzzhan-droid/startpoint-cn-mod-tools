"""补丁链和清单检查。"""
from __future__ import annotations

from .prepush_base import *

def enabled_names(manifest: dict) -> list[str]:
    names = []
    for p in manifest.get("patches", []):
        if p.get("type") != "patch" or p.get("enabled") is not True:
            continue
        chain = p.get("chain") if isinstance(p.get("chain"), list) else [p.get("archive")]
        names += [n for n in chain if isinstance(n, str) and n]
    return names


def run_kulo35(server_dir: Path, published: list[str], on_disk: list[str], rep: Report):
    """复用 kulo#35 的 checkPatchChainIntegrity;拿不到就注明跳过,不在这里重写。"""
    js = server_dir / "out" / "routes" / "cn" / "asset.js"
    node = shutil.which("node")
    if not js.is_file() or node is None:
        why = "没有 node" if node is None else f"没有 {js}(先在服务端仓 npx tsc)"
        rep.add("WARN", "chain", "chain.kulo35.skipped",
                f"版本顺序/seq/重复/缺文件检查(kulo#35)未执行:{why}")
        return
    script = (
        "const a=require(process.argv[1]);"
        "if(typeof a.checkPatchChainIntegrity!=='function'){"
        f"console.log('{NODE_MARK}'+JSON.stringify(null));process.exit(0)}}"
        "const d=JSON.parse(require('fs').readFileSync(0,'utf8'));"
        f"console.log('{NODE_MARK}'+JSON.stringify(a.checkPatchChainIntegrity(d.published,d.onDisk)));"
    )
    try:
        cp = subprocess.run([node, "-e", script, str(js)], input=json.dumps(
            {"published": published, "onDisk": on_disk}), capture_output=True,
            text=True, encoding="utf-8", timeout=120)
    except Exception as exc:  # noqa: BLE001
        rep.add("WARN", "chain", "chain.kulo35.failed", f"kulo#35 检查调用失败:{exc}")
        return
    line = next((ln for ln in cp.stdout.splitlines() if ln.startswith(NODE_MARK)), None)
    if line is None:
        rep.add("WARN", "chain", "chain.kulo35.failed",
                f"kulo#35 检查没有返回结果(exit {cp.returncode})", cp.stderr.strip().splitlines()[-5:])
        return
    warnings = json.loads(line[len(NODE_MARK):])
    if warnings is None:
        rep.add("WARN", "chain", "chain.kulo35.missing",
                "服务端 asset.js 没有 checkPatchChainIntegrity(该服务端还没合 #35)")
        return
    rep.notes.append(f"kulo#35 checkPatchChainIntegrity: {len(warnings)} 条")
    for w in warnings:
        rep.add("ERROR", "chain", f"chain.kulo35:{w}", f"[#35] {w}")


def check_chain(args, manifest: dict, active: Path, new_zips: set[str], rep: Report, pathlist):
    published = enabled_names(manifest)
    on_disk = sorted(p.name for p in active.glob("*.zip"))
    run_kulo35(args.server_dir, published, on_disk, rep)

    # 未登记:active 里有、清单启用项里没有。服务端会照样扫描 active 下发它。
    for name in sorted(set(on_disk) - set(published)):
        if archive_key(name) is None:
            continue
        rep.add("WARN", "chain", f"chain.unlisted:{name}",
                f"active 里的 {name} 不在清单启用项里(服务端仍会扫描下发,清单与目录不同步)")

    tail = None
    for p in manifest.get("patches", []):
        if p.get("type") != "patch" or p.get("enabled") is not True:
            continue
        pid = p.get("id", "?")
        chain = p.get("chain") if isinstance(p.get("chain"), list) else [p.get("archive")]
        for name in chain:
            k = archive_key(name or "")
            if k is None:
                continue
            frm, to = ".".join(map(str, k[0])), ".".join(map(str, k[1]))
            if p.get("version") != to or p.get("depends_on") != frm:
                rep.add("ERROR", "chain", f"chain.entry_version:{name}",
                        f"清单条目 {pid}: version={p.get('version')} depends_on={p.get('depends_on')},"
                        f"但包名是 {frm}->{to}")
        if p.get("version"):
            tail = max(tail or p["version"], p["version"], key=vkey)
        for ent in p.get("archive_integrity") or []:
            name = ent.get("name")
            path = active / name if name else None
            if not path or not path.is_file():
                continue          # 缺文件由 #35 报
            blob = path.read_bytes()
            if ent.get("size") is not None and ent["size"] != len(blob):
                rep.add("ERROR", "chain", f"chain.size:{name}",
                        f"{name} 大小 {len(blob)} ≠ 清单 {ent['size']}")
            if ent.get("sha256") and ent["sha256"] != hashlib.sha256(blob).hexdigest():
                rep.add("ERROR", "chain", f"chain.sha256:{name}", f"{name} sha256 与清单不符")
            with zipfile.ZipFile(path) as zf:
                names = sorted(n for n in zf.namelist() if not n.endswith("/"))
            if ent.get("files") is not None and sorted(ent["files"]) != names:
                rep.add("ERROR", "chain", f"chain.files:{name}", f"{name} 成员列表与清单 files 不一致",
                        [f"清单多: {sorted(set(ent['files']) - set(names))[:5]}",
                         f"包里多: {sorted(set(names) - set(ent['files']))[:5]}"])
            mem = ent.get("members")
            if isinstance(mem, list) and sorted(mem) != names:
                rep.add("ERROR", "chain", f"chain.members:{name}", f"{name} 成员列表与清单 members 不一致")
            elif isinstance(mem, int) and mem != len(names):
                rep.add("ERROR", "chain", f"chain.members:{name}",
                        f"{name} 成员数 {len(names)} ≠ 清单 {mem}")
    if tail and manifest.get("cdn_version") and manifest["cdn_version"] != tail:
        rep.add("ERROR", "chain", "chain.cdn_version",
                f"清单 cdn_version={manifest['cdn_version']},启用链尾是 {tail}")

    # 新包逐个:CRC、成员路径、master 表可解码(平表新增行没压缩时这里会炸)
    for path in list_chain(active):
        if path.name not in new_zips:
            continue
        with zipfile.ZipFile(path) as zf:
            bad = zf.testzip()
            if bad:
                rep.add("ERROR", "chain", f"chain.crc:{path.name}", f"{path.name} CRC 损坏: {bad}")
            for n in zf.namelist():
                if n.endswith("/") or n == ".empty":     # .empty = 刻意的空版本占位包
                    continue
                if not MEMBER_RE.match(n):
                    rep.add("ERROR", "chain", f"chain.member_path:{path.name}:{n}",
                            f"{path.name} 成员路径不是 production/<root>/xx/<38hex>: {n}")
                    continue
                parts = n.split("/")
                if len(parts) == 4 and parts[1] != "upload":
                    continue
                logical = pathlist.get(parts[-2] + parts[-1])
                if not (logical and logical.startswith("master/")):
                    continue
                data = zf.read(n)
                if is_stub(data):
                    continue
                try:
                    q.parse_node(data)      # 少数 master 文件是整块 zlib 文本,返回 str 也算能解
                except Exception as exc:  # noqa: BLE001
                    rep.add("ERROR", "chain", f"chain.decode:{path.name}:{logical}",
                            f"{path.name} 里的 {logical} 解不开: {exc}")


