# -*- coding: utf-8 -*-
"""五重决战 v2：把 wf_five_boss_v2.py --stage 的暂存结果写入 live 并本地发布（铸一条裸表边）。

流程与诅咒武器批次的 apply_fix 同构（${WF_ROOT}/out/诅咒武器-20260927/apply_fix.py）：
  pending 必须为空、链尾等于 <from>、每个暂存对象的 live 哈希与暂存时一致（防并发改表）
  → 备份 → 写 live → pending=本批逻辑路径 → wf_publish --list 预检 → 发布 → flow 账本重锚
  → 清 pending → 核验（live==暂存、未触及顶层键逐字节不变、get_path 三档 HTTP==本地归档且 CRC 通过）。

用法：python mod-tools/wf_five_boss_v2_publish.py <workdir> <from_version> <to_version> "<摘要>"
本脚本只做本地发布；公开链/分享包/灰服投递不在这里。
"""
from __future__ import annotations

import contextlib
import datetime
import hashlib
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[3]  # 仓库根（本文件在 wf/tools/<组>/ 下）
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_mod_tool as C  # noqa: E402
import wf_publish as P  # noqa: E402
import wf_release as Release  # noqa: E402
import wf_share_update_codec as X  # noqa: E402


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf8")


def store_file(logical: str) -> Path:
    return C.table_path(Path(C.resolve_active_store()), logical)


def main(argv: list[str]) -> int:
    work, frm, to, summary = Path(argv[0]), argv[1], argv[2], argv[3]
    plan = json.loads((work / "plan.json").read_bytes())
    if (work / "published.json").exists():
        raise SystemExit("already published")
    if P.current_max_version() != frm:
        raise SystemExit(f"chain tail is {P.current_max_version()}, expected {frm}")
    if json.loads(P.PENDING.read_bytes() or b"[]") != []:
        raise SystemExit("pending not empty (another session is mid-publish)")
    items = [(lg, info["live_sha256"]) for lg, info in plan["tables"].items()] + \
            [(lg, info["live_sha256"]) for lg, info in plan["files"].items()]
    if not items:
        raise SystemExit("nothing to publish")
    writes, entries = [], []
    for logical, live_sha in items:
        target = store_file(logical)
        current = sha(target.read_bytes()) if target.exists() else None
        if current != live_sha:
            raise SystemExit(f"concurrent edit: {logical}")
        raw = (work / "stage/common" / logical).read_bytes()
        if target.exists():
            backup = work / "before/live/common" / logical
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                backup.write_bytes(target.read_bytes())
        writes.append((target, raw))
        entries.append(dict(logical=logical, relative=P._relative_for_logical(logical), sha256=sha(raw),  # noqa: SLF001
                            size=len(raw)))
    profile = C.resolve_profile()
    save(work / "publish-snapshot.json", dict(schema_version=1, profile_id=profile.id,
                                              store=str(Path(C.resolve_active_store()).resolve()), entries=entries))
    activepath = ROOT / ".cdn/cn/character-releases/active.json"
    active = activepath.read_bytes()
    save(work / "before/active.json", json.loads(active))
    for target, raw in writes:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        assert target.read_bytes() == raw
    names = [e["logical"] for e in entries]
    save(P.PENDING, names)
    now = datetime.datetime.now().isoformat()
    with P.CHANGELOG.open("a", encoding="utf8", newline="\n") as f:
        for logical, info in plan["tables"].items():
            f.write(json.dumps(dict(ts=now, table=logical, keys=info["changed"], summary=summary, version=None,
                                    backup=str(work / "before/live/common" / logical)), ensure_ascii=False) + "\n")
    args = ["--tables", ",".join(names), "--snapshot", str(work / "publish-snapshot.json")]
    with (work / "publish-list.log").open("w", encoding="utf8") as log, contextlib.redirect_stdout(log), \
            contextlib.redirect_stderr(log):
        if P.main(args + ["--list"]) != 0:
            raise SystemExit("publisher preflight failed (see publish-list.log); live already written — restore from before/")
    with (work / "publish.log").open("w", encoding="utf8") as log, contextlib.redirect_stdout(log), \
            contextlib.redirect_stderr(log):
        if P.main(args) != 0 or P.current_max_version() != to:
            raise SystemExit("publisher failed (see publish.log)")
    if activepath.read_bytes() != active:
        raise SystemExit("active ledger concurrently changed")
    save(work / "reanchor.json", Release.reanchor_active_ledger("cn", target_base=to, dry_run=False))
    after = json.loads(activepath.read_bytes())
    assert after["base_package_owners"] == json.loads(active)["base_package_owners"]
    save(P.PENDING, [])

    # 核验
    expected = {}
    for entry in entries:
        assert sha(store_file(entry["logical"]).read_bytes()) == entry["sha256"], entry["logical"]
        expected["production/upload/" + entry["relative"]] = entry["sha256"]
    for logical, info in plan["tables"].items():
        before = X.unpack((work / "before/live/common" / logical).read_bytes())
        now_rows = X.unpack(store_file(logical).read_bytes())
        untouched = [k for k in before if k not in info["changed"]]
        assert all(now_rows[k] == before[k] for k in untouched), logical
    env = (ROOT / ".env").read_text("utf8")
    host = re.search(r'^CN_LISTEN_HOST="?([^"\r\n]+)', env, re.M)[1]
    port = re.search(r'^CN_LISTEN_PORT="?([^"\r\n]+)', env, re.M)[1]
    request = urllib.request.Request(f"http://{host}:{port}/api/index.php/asset/get_path", data=b"{}",
                                     headers={"res_ver": frm, "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)["data"]
    assert data["info"]["target_asset_version"] == to and len(data["diff"]) == 1, data["info"]
    archives = [p for layer in ("common", "medium", "android")
                for p in (P.CDN_ROOT / f"archive-{layer}-diff").glob(f"pinball-{frm}-{to}-*.zip")]
    seen, checks = {}, []
    for entry in data["diff"][0]["archive"]:
        with urllib.request.urlopen(entry["location"], timeout=60) as response:
            raw = response.read()
        layer = re.search(r"archive-(common|medium|android)-diff", entry["location"])[1]
        matched = [p for p in archives if p.parent.name == f"archive-{layer}-diff" and p.read_bytes() == raw]
        assert len(matched) == 1 and len(raw) == entry["size"]
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            assert z.testzip() is None
            for name in z.namelist():
                if name != ".empty":
                    seen[name] = sha(z.read(name))
        checks.append(dict(layer=layer, archive=matched[0].name, size=len(raw), sha256=sha(raw)))
    assert seen == expected, set(seen) ^ set(expected)
    result = dict(version=to, from_version=frm, files=len(writes),
                  tables={k: v["changed"] for k, v in plan["tables"].items()}, other_files=list(plan["files"]),
                  owners=len(after["base_package_owners"]), pending=[], archives=checks, http_target=to,
                  runtime_verified=False)
    save(work / "published.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
