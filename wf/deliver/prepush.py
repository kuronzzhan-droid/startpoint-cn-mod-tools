# -*- coding: utf-8 -*-
"""推送前数据自检:客户端补丁链在上测试服之前的四项检查。

把这个月踩过的坑做成一次命令,出包后、推送前跑一遍:

  chain     补丁链与清单。版本顺序/seq 断档/重复/缺文件交给服务端 kulo#35 的
            ``checkPatchChainIntegrity``(node 调 ``out/routes/cn/asset.js``,不在这里重写);
            这里只补 #35 不管的:清单条目 version/depends_on 与包名一致、
            archive_integrity 的 size/sha256/成员与磁盘一致、ZIP CRC、成员路径格式、
            cdn_version = 链尾、active 里没登记的 zip、包内 master 表能否解码。
  text      改错表。游戏内技能描述只来自客户端 ``master/skill/action_skill`` 每档的 c0/c1;
            服务端 ``assets/cdndata/character_text*.json`` 和客户端 ``character_text`` 表
            都不进角色详情页。改了它们却没改 action_skill = 游戏里看不到(1.4.200 事故)。
            另查 action_skill 只改了部分档位(低档残留旧文)。
  companion 伴随表。新道具必须进服务端 ``assets/item_ids.json`` 与客户端
            ``master/search/item_quest_search``;``executable_instant_item`` 每个键
            必须有 ``executable_instant_item_level`` 行(C8601)。
  level     等级缺口(U_3be147)。客户端 ``GeneralEnemySourceHelper.getSurjectivity``
            取首个 key>=敌等级的行,找不到就抛。沿 quest -> field_data -> zone ->
            boss/zako -> 行内引用 / action DSL / esdl -> SpawnFunnel/SpawnAlterEgo
            做可达闭包,查等级表与 general_{boss,funnel,zako}_variable。
            逻辑移植自 builder 的 level_gap_check.py + bh_vargap.py。

视图 = 基础 store(可选) + active 里的 zip 按 (from,to,seq) 数字序叠加(后者覆盖)
+ --extra-zip。没给基础 store 时,链里从未出现过的表视为「不在视图」,相关检查跳过并注明。

``--since 1.4.N``:再建一份只叠到 1.4.N 的视图,两者之差 = 本次新增/改动。
新增条目上的问题记 ERROR,历史遗留记 WARN。不给 --since 时一律按 ERROR/WARN 原级别。

用法(Windows,builder 的 Python):
  python wf_prepush_check.py --server-dir <服务端仓根> ^
      --base-store <官方 store 的 production 目录或 upload 目录> --since 1.4.202
退出码:0 = 无 ERROR;1 = 有 ERROR;2 = 参数/环境错误。
"""
from __future__ import annotations

from wf.paths import path as configured_path
from .prepush_base import *
from .prepush_chain import *
from .prepush_text import *
from .prepush_companion import *
from .prepush_level import *
from .prepush_text import _empty, _git_show, _skill_tiers
from .prepush_level import _strings, _lists, _pieces, _numeric_keys

def load_pathlist(filename: Path | None = None) -> dict[str, str]:
    p = Path(filename) if filename is not None else configured_path("pathlist")
    if filename is not None and not p.is_file():
        raise FileNotFoundError(f"--pathlist does not exist: {p}")
    out = {}
    if p.is_file():
        for line in p.read_text("utf-8").splitlines():
            line = line.strip()
            if line:
                out[digest(line)] = line
    for lp in [ACTION_SKILL, CHARACTER, CHARACTER_TEXT, ITEM, ITEM_QUEST_SEARCH, EII, EII_LEVEL,
               *LEVEL_TABLES.values(), *VARIABLE_TABLES.values(), *CURVE_TABLES.values(),
               *(x for x, _ in QUEST_TABLES)]:
        out.setdefault(digest(lp), lp)
    return out


def build_parser():
    ap = argparse.ArgumentParser(description="推送前数据自检(补丁链/改错表/伴随表/等级缺口)")
    ap.add_argument("--server-dir", type=Path, required=True,
                    help="服务端仓根:读 assets/、out/routes/cn/asset.js")
    ap.add_argument("--active", type=Path, help="补丁目录,默认 <server-dir>/assets/asset-patch/active")
    ap.add_argument("--manifest", type=Path, help="清单,默认 <server-dir>/assets/asset-patch/manifest.json")
    ap.add_argument("--base-store", type=Path,
                    help="基础 store:production 目录(含 upload/medium_upload/...)或 upload 目录本身")
    ap.add_argument("--extra-zip", type=Path, action="append", default=[],
                    help="叠在链尾的候选包(可多次),按给出顺序覆盖")
    ap.add_argument("--pathlist", type=Path,
                    help="逻辑路径表(默认 WF_PATHLIST / profiles 路径配置 / 仓内 WF_PATHLIST_recovered.txt)")
    ap.add_argument("--since", help="对比基线版本 1.4.N:之后的包算本次新增,新问题记 ERROR、旧问题记 WARN")
    ap.add_argument("--git-since", help="服务端仓的 git 基线(如 HEAD~1 或 origin/main),判断服务端文本是否本次改动")
    ap.add_argument("--custom-item-min", type=int, default=10000300,
                    help="没给 --since 时,id ≥ 此值的道具按自制道具查 item_quest_search(默认 10000300)")
    ap.add_argument("--allowlist", type=Path,
                    help="JSON: {\"ids\": [发现 id...], \"item_quest_search_exempt\": [道具 id...]}")
    ap.add_argument("--only", help="只跑部分检查,逗号分隔:chain,text,companion,level")
    ap.add_argument("--json", type=Path, help="把全部发现写到 JSON")
    ap.add_argument("--verbose", action="store_true", help="WARN/INFO 也打印细节")
    return ap


def main(argv=None, *, archive_paths=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    args = build_parser().parse_args(argv)
    args.server_dir = args.server_dir.resolve()
    active = (args.active or args.server_dir / "assets" / "asset-patch" / "active").resolve()
    manifest_path = (args.manifest or args.server_dir / "assets" / "asset-patch" / "manifest.json").resolve()
    if not active.is_dir():
        print(f"补丁目录不存在: {active}")
        return 2
    manifest = json.loads(manifest_path.read_text("utf-8")) if manifest_path.is_file() else {"patches": []}
    if args.base_store is not None and not args.base_store.is_dir():
        print(f"--base-store 不存在: {args.base_store}")
        return 2
    if args.pathlist is not None and not args.pathlist.is_file():
        print(f"--pathlist 不存在: {args.pathlist}")
        return 2
    allow_doc = json.loads(args.allowlist.read_text("utf-8")) if args.allowlist else {}
    rep = Report(set(allow_doc.get("ids", [])))
    allow_iqs = {str(x) for x in allow_doc.get("item_quest_search_exempt", [])}
    only = set((args.only or "chain,text,companion,level").split(","))

    chain = (list_chain(active) if archive_paths is None else list(archive_paths)) + [p.resolve() for p in args.extra_zip]
    view = View(chain, args.base_store)
    old = None
    if args.since:
        old = View([p for p in chain if archive_key(p.name) and archive_key(p.name)[1] <= vkey(args.since)], args.base_store)
        new_zips = {p.name for p in chain if p not in set(old.zips)}
    else:
        new_zips = {p.name for p in chain}
    tail = max((archive_key(p.name)[1] for p in chain if archive_key(p.name)), default=None)
    print(f"视图: 基础 store={args.base_store or '(无,只看链)'}; 链 {len(chain)} 个包,"
          f"链尾 {'.'.join(map(str, tail)) if tail else '?'}"
          + (f"; 候选 {', '.join(p.name for p in args.extra_zip)}" if args.extra_zip else "")
          + (f"; --since {args.since}(新包 {len(new_zips)} 个)" if args.since else ""))

    if "chain" in only:
        check_chain(args, manifest, active, new_zips, rep, load_pathlist(args.pathlist), archive_paths=chain)
    if "text" in only:
        check_text(args, view, old, rep)
    if "companion" in only:
        check_companion(args, view, old, rep, allow_iqs)
    if "level" in only:
        check_level(args, view, old, rep)

    for v in (view, old):
        if v is None:
            continue
        for lp, err in sorted(v.broken.items()):
            fid = f"view.broken:{lp}"
            if fid not in {f.fid for f in rep.items}:
                rep.add("WARN", "chain", fid, f"{lp} 在视图里解不开,依赖它的检查按「不在视图」处理: {err}")
    if view.stubs:
        rep.notes.append("APK 内置表(store 里是 16 字节桩,按不在视图处理): "
                         + ", ".join(Path(x).stem for x in sorted(view.stubs)))

    labels = {"chain": "补丁链/清单", "text": "改错表", "companion": "伴随表", "level": "等级缺口"}
    for chk in ("chain", "text", "companion", "level"):
        if chk not in only:
            continue
        order = {"ERROR": 0, "WARN": 1, "INFO": 2}
        fs = sorted((f for f in rep.items if f.check == chk), key=lambda f: order[f.level])
        e = sum(f.level == "ERROR" for f in fs)
        w = sum(f.level == "WARN" for f in fs)
        print(f"\n[{labels[chk]}] ERROR {e}  WARN {w}  INFO {sum(f.level == 'INFO' for f in fs)}")
        shown_warn = 0
        for f in fs:
            if f.level == "INFO" and not args.verbose:
                continue
            if f.level == "WARN" and not args.verbose:
                shown_warn += 1
                if shown_warn > 12:
                    continue
            print(f"  {f.level:5} {f.msg}")
            if f.level == "ERROR" or args.verbose:
                for d in f.detail:
                    print(f"        {d}")
            if args.verbose:
                print(f"        id={f.fid}")
        if shown_warn > 12:
            print(f"  ……另有 {shown_warn - 12} 条 WARN(--verbose 或 --json 看全部)")
    if rep.notes:
        print("\n说明:")
        for n in rep.notes:
            print(f"  - {n}")
    print(f"\n合计: ERROR {rep.count('ERROR')}  WARN {rep.count('WARN')}  INFO {rep.count('INFO')}"
          f"  => {'不要推送' if rep.count('ERROR') else '可以推送'}")
    if args.json:
        args.json.write_text(json.dumps({
            "findings": [f.__dict__ for f in rep.items], "notes": rep.notes,
            "chain": [p.name for p in chain], "since": args.since,
        }, ensure_ascii=False, indent=1), "utf-8")
    return 1 if rep.count("ERROR") else 0


if __name__ == "__main__":
    sys.exit(main())
