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

import argparse
import csv
import functools
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path

MOD_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MOD_DIR))
import wf_quest_lib as q  # noqa: E402  (parse_node / SALT,无 store 副作用)

ROOTS = ("upload", "medium_upload", "android_upload")
ARCHIVE_RE = re.compile(r"^pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-(\d+)-.*\.zip$")
# 早期包(如 1.4.70 mode15final70)成员不带 production/<root>/ 前缀,按 upload 根落地,照样合法
MEMBER_RE = re.compile(
    r"^(production/(upload|medium_upload|android_upload|ios_upload|small_upload)/)?[0-9a-f]{2}/[0-9a-f]{38}$")
NODE_MARK = "@@WF_PREPUSH_CHAIN@@"


def vkey(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def archive_key(name: str):
    m = ARCHIVE_RE.match(name)
    if not m:
        return None
    return vkey(m.group(1)), vkey(m.group(2)), int(m.group(3))


def digest(logical: str) -> str:
    return hashlib.sha1((logical + q.SALT).encode("utf-8")).hexdigest()


def member(root: str, logical: str) -> str:
    d = digest(logical)
    return f"production/{root}/{d[:2]}/{d[2:]}"


def row(text: str) -> list[str]:
    return next(csv.reader([text]), [])


def rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text, newline="")))


def is_stub(raw: bytes) -> bool:
    """store 里的 16 字节桩:键数为 0 的空 orderedmap,真表打包在 APK 里(曲线表等)。"""
    if len(raw) > 64 or len(raw) < 8:
        return False
    ilen = struct.unpack_from("<I", raw, 0)[0]
    if ilen <= 0 or 4 + ilen != len(raw):
        return False
    try:
        index = zlib.decompress(raw[4:])
    except zlib.error:
        return False
    return len(index) >= 4 and struct.unpack_from("<I", index, 0)[0] == 0


# ---------------------------------------------------------------- 发现

@dataclass
class Finding:
    level: str          # ERROR / WARN / INFO
    check: str          # chain / text / companion / level
    fid: str            # 稳定 id,allowlist 用
    msg: str
    detail: list[str] = field(default_factory=list)


class Report:
    def __init__(self, allow: set[str]):
        self.items: list[Finding] = []
        self.allow = allow
        self.notes: list[str] = []

    def add(self, level, check, fid, msg, detail=None):
        if fid in self.allow and level == "ERROR":
            level = "WARN"
            msg += "(allowlist 降级)"
        self.items.append(Finding(level, check, fid, msg, list(detail or [])))

    def count(self, level):
        return sum(1 for f in self.items if f.level == level)


# ---------------------------------------------------------------- 视图

class View:
    """基础 store + zip 链(后者覆盖),按逻辑路径读字节/解析表。"""

    def __init__(self, zips: list[Path], base: Path | None):
        self.zips = list(zips)
        self.base = base
        self.index: dict[str, Path] = {}
        for z in self.zips:
            with zipfile.ZipFile(z) as zf:
                for n in zf.namelist():
                    self.index[n] = z
        self._zf: dict[Path, zipfile.ZipFile] = {}
        self.stubs: set[str] = set()
        self.broken: dict[str, str] = {}

    def _open(self, z: Path) -> zipfile.ZipFile:
        if z not in self._zf:
            self._zf[z] = zipfile.ZipFile(z)
        return self._zf[z]

    def _base_file(self, m: str) -> Path | None:
        if self.base is None:
            return None
        _, root, a, b = m.split("/")
        if (self.base / "upload").is_dir():          # 给的是 production 目录
            p = self.base / root / a / b
        elif root == "upload":                        # 给的是 upload 目录本身
            p = self.base / a / b
        else:
            return None
        return p if p.is_file() else None

    def raw(self, logical: str, roots=ROOTS) -> bytes | None:
        for r in roots:
            m = member(r, logical)
            if m in self.index:
                return self._open(self.index[m]).read(m)
            p = self._base_file(m)
            if p is not None:
                return p.read_bytes()
        return None

    def source(self, logical: str) -> str | None:
        m = member("upload", logical)
        if m in self.index:
            return self.index[m].name
        return "base" if self._base_file(m) else None

    @functools.lru_cache(maxsize=None)
    def table(self, logical: str):
        """解析好的表;不在视图、APK 内置桩、解不开时返回 None(后两种记进 stubs/broken)。"""
        raw = self.raw(logical, ("upload",))
        if raw is None:
            return None
        if is_stub(raw):
            self.stubs.add(logical)
            return None
        try:
            node = q.parse_node(raw)
        except Exception as exc:  # noqa: BLE001
            self.broken[logical] = str(exc)
            return None
        return node if isinstance(node, dict) else None


def list_chain(active: Path, upto: tuple[int, ...] | None = None) -> list[Path]:
    out = []
    for p in active.glob("*.zip"):
        k = archive_key(p.name)
        if k is None:
            continue
        if upto is not None and k[1] > upto:
            continue
        out.append((k, p.name, p))
    return [p for _, _, p in sorted(out)]


# ---------------------------------------------------------------- chain

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


# ---------------------------------------------------------------- text

ACTION_SKILL = "master/skill/action_skill.orderedmap"
CHARACTER = "master/character/character.orderedmap"
CHARACTER_TEXT = "master/character/character_text.orderedmap"
# character_text 列:4/6/8 = 各档技能名,5/7/9 = 各档技能描述(与服务端 json 同序)
TEXT_TIERS = ((1, 4, 5), (2, 6, 7), (3, 8, 9))


def _skill_tiers(view: View, cid: str):
    ch = view.table(CHARACTER) or {}
    ask = view.table(ACTION_SKILL) or {}
    if cid not in ch or not isinstance(ch[cid], str):
        return None
    sk = row(ch[cid])[8] if len(row(ch[cid])) > 8 else ""
    ent = ask.get(sk)
    if not isinstance(ent, dict):
        return None
    out = {}
    for t, v in ent.items():
        if isinstance(v, str) and v:
            r = row(v)
            out[t] = (r[0] if r else "", r[1] if len(r) > 1 else "")
    return sk, out


def _empty(s) -> bool:
    return s in (None, "", "(None)")


def _git_show(server_dir: Path, ref: str, rel: str):
    try:
        cp = subprocess.run(["git", "-C", str(server_dir), "show", f"{ref}:{rel}"],
                            capture_output=True, timeout=60)
    except Exception:  # noqa: BLE001
        return None
    if cp.returncode != 0:
        return None
    return json.loads(cp.stdout.decode("utf-8"))


def check_text(args, view: View, old: View | None, rep: Report):
    if view.table(ACTION_SKILL) is None or view.table(CHARACTER) is None:
        rep.add("WARN", "text", "text.skipped", "视图里没有 action_skill/character 表,文案检查跳过")
        return

    # 文本源:服务端 json(只服务端用)+ 客户端 character_text 表(不进详情页)
    sources = []
    for rel in ("assets/cdndata/character_text.json", "assets/cdndata/character_text_rank_p5b.json"):
        p = args.server_dir / rel
        if not p.is_file():
            continue
        cur = {k: v[0] for k, v in json.loads(p.read_text("utf-8")).items() if v}
        before = None
        if args.git_since:
            b = _git_show(args.server_dir, args.git_since, rel)
            before = {k: v[0] for k, v in b.items() if v} if b is not None else None
        sources.append((f"服务端 {rel}", cur, before))
    ct = view.table(CHARACTER_TEXT)
    if ct is not None:
        cur = {k: row(v) for k, v in ct.items() if isinstance(v, str)}
        before = None
        if old is not None and old.table(CHARACTER_TEXT) is not None:
            before = {k: row(v) for k, v in old.table(CHARACTER_TEXT).items() if isinstance(v, str)}
        sources.append(("客户端 character_text 表", cur, before))

    for label, cur, before in sources:
        stale = []
        for cid, r in cur.items():
            st = _skill_tiers(view, cid)
            if st is None:
                continue
            sk, tiers = st
            for t, ncol, dcol in TEXT_TIERS:
                if t not in {int(x) for x in tiers if x.isdigit()}:
                    continue          # 该档客户端不存在(如无觉醒档),服务端多出的文字无害
                name, desc = tiers[str(t)]
                for col, game, what in ((dcol, desc, "技能描述"), (ncol, name, "技能名")):
                    mine = r[col] if col < len(r) else None
                    if _empty(mine) or mine == game:
                        continue
                    changed = before is not None and (before.get(cid) or [None] * 12)[col:col + 1] != [mine]
                    fid = f"text.drift:{label}:{cid}:{t}:{what}"
                    msg = (f"{label} 角色 {cid} 第{t}档{what}与游戏内不一致;"
                           f"游戏只读 action_skill[{sk}][{t}] c{0 if what == '技能名' else 1}")
                    det = [f"此处: {mine[:120]}", f"游戏: {game[:120]}"]
                    if changed:
                        rep.add("ERROR", "text", fid, "本次改了 " + msg + " —— 这处改动游戏里看不到", det)
                    else:
                        stale.append((fid, msg, det))
        if stale:
            for fid, msg, det in stale:
                rep.add("WARN", "text", fid, msg, det)

    # action_skill 只改了部分档位
    if old is not None and old.table(ACTION_SKILL) is not None:
        a0, a1 = old.table(ACTION_SKILL), view.table(ACTION_SKILL)
        for sk, ent in a1.items():
            prev = a0.get(sk)
            if not isinstance(ent, dict) or not isinstance(prev, dict):
                continue
            desc = {t: row(v)[1] if len(row(v)) > 1 else "" for t, v in ent.items() if isinstance(v, str) and v}
            pdesc = {t: row(v)[1] if len(row(v)) > 1 else "" for t, v in prev.items() if isinstance(v, str) and v}
            changed = [t for t in desc if t in pdesc and desc[t] != pdesc[t]]
            same = [t for t in desc if t in pdesc and desc[t] == pdesc[t]]
            if changed and same and len(desc) > 1:
                rep.add("WARN", "text", f"text.partial_tier:{sk}",
                        f"action_skill[{sk}] 只改了第 {','.join(changed)} 档描述,第 {','.join(same)} 档还是旧文"
                        "(每一档都要改,否则低档显示旧文)")


# ---------------------------------------------------------------- companion

ITEM = "master/item/item.orderedmap"
ITEM_QUEST_SEARCH = "master/search/item_quest_search.orderedmap"
EII = "master/battle/item/executable_instant_item.orderedmap"
EII_LEVEL = "master/battle/item/executable_instant_item_level.orderedmap"


def check_companion(args, view: View, old: View | None, rep: Report, allow_iqs: set[str]):
    items = view.table(ITEM)
    if items is None:
        rep.add("WARN", "companion", "companion.item.skipped", "视图里没有 item 表,道具伴随检查跳过")
    else:
        old_items = set(old.table(ITEM) or {}) if old is not None else None
        def is_new(k):
            return old_items is not None and k not in old_items
        ids_path = args.server_dir / "assets" / "item_ids.json"
        if ids_path.is_file():
            ids = {str(x) for x in json.loads(ids_path.read_text("utf-8"))}
            for k in sorted(set(items) - ids, key=lambda s: (len(s), s)):
                name = row(items[k])[2] if isinstance(items[k], str) and len(row(items[k])) > 2 else ""
                rep.add("ERROR" if (is_new(k) or old_items is None) else "WARN", "companion",
                        f"companion.item_ids:{k}",
                        f"道具 {k}({name})在客户端 item 表里,但不在服务端 assets/item_ids.json")
        iqs = view.table(ITEM_QUEST_SEARCH)
        if iqs is not None and old_items is not None:
            for k in sorted(set(items) - set(iqs) - old_items - allow_iqs, key=lambda s: (len(s), s)):
                name = row(items[k])[2] if isinstance(items[k], str) and len(row(items[k])) > 2 else ""
                rep.add("WARN", "companion", f"companion.item_quest_search:{k}",
                        f"新道具 {k}({name})没有 item_quest_search 行(获取途径页空白)")
        elif iqs is not None and args.custom_item_min is not None:
            for k in sorted(set(items) - set(iqs) - allow_iqs, key=lambda s: (len(s), s)):
                if k.isdigit() and int(k) >= args.custom_item_min:
                    name = row(items[k])[2] if isinstance(items[k], str) and len(row(items[k])) > 2 else ""
                    rep.add("WARN", "companion", f"companion.item_quest_search:{k}",
                            f"自制道具 {k}({name})没有 item_quest_search 行(获取途径页空白)")
    eii, lvl = view.table(EII), view.table(EII_LEVEL)
    if eii is None or lvl is None:
        rep.notes.append("executable_instant_item(_level) 不在视图里,C8601 检查跳过")
    else:
        for k in sorted(set(eii) - set(lvl)):
            rep.add("ERROR", "companion", f"companion.eii_level:{k}",
                    f"即时道具 {k} 没有 executable_instant_item_level 行(C8601)")


# ---------------------------------------------------------------- level(移植 level_gap_check.py)

LEVEL_TABLES = {
    "standard_boss": "master/battle/boss/standard_boss.orderedmap",
    "general_boss": "master/battle/boss/general_boss.orderedmap",
    "general_zako": "master/battle/zako/general_zako.orderedmap",
    "general_funnel": "master/battle/boss/funnel/general_funnel.orderedmap",
    "standard_funnel": "master/battle/boss/funnel/standard_funnel.orderedmap",
    "tentacle": "master/battle/boss/funnel/tentacle.orderedmap",
    "kraken": "master/battle/boss/kraken.orderedmap",
    "orochi": "master/battle/boss/orochi.orderedmap",
    "orochi_ex": "master/battle/boss/orochi_ex.orderedmap",
    "orochi_ex_head": "master/battle/boss/orochi_ex_head.orderedmap",
    "conductor": "master/battle/boss/conductor.orderedmap",
    "touyakiren_ceo": "master/battle/boss/touyakiren_ceo.orderedmap",
    "water_sphere": "master/battle/boss/water_sphere.orderedmap",
    "holy_sphere": "master/battle/boss/holy_sphere.orderedmap",
    "wind_sphere": "master/battle/boss/wind_sphere.orderedmap",
    "thunder_sphere": "master/battle/boss/thunder_sphere.orderedmap",
    "fire_sphere": "master/battle/boss/fire_sphere.orderedmap",
}
# general_* 键在客户端还会按同一等级再查 *_variable(FunnelSource.as:89-92 空表即抛)
VARIABLE_TABLES = {
    "general_boss": "master/battle/boss/general_boss_variable.orderedmap",
    "general_funnel": "master/battle/boss/funnel/general_funnel_variable.orderedmap",
    "general_zako": "master/battle/zako/general_zako_variable.orderedmap",
}
CURVE_TABLES = {
    "party_atk_curve": "master/battle/enemy/party/party_atk_curve.orderedmap",
    "party_hp_curve": "master/battle/enemy/party/party_hp_curve.orderedmap",
    "hit_hp_basic_curve": "master/battle/enemy/hp/hit_hp_basic_curve.orderedmap",
    "hit_hp_correction_curve": "master/battle/enemy/hp/hit_hp_correction_curve.orderedmap",
    "fix_hp_basic_curve": "master/battle/enemy/hp/fix_hp_basic_curve.orderedmap",
    "atk_basic_curve": "master/battle/enemy/atk/atk_basic_curve.orderedmap",
    "atk_correction_curve": "master/battle/enemy/atk/atk_correction_curve.orderedmap",
    "tp_basic_curve": "master/battle/enemy/tp/tp_basic_curve.orderedmap",
}
# (logical, battle_enemy_level 列) — 列号取自客户端 *QuestValues.as
QUEST_TABLES = [
    ("master/quest/event/advent_event_quest.orderedmap", 112),
    ("master/quest/boss_battle_quest.orderedmap", 106),
    ("master/quest/event/carnival_event_quest.orderedmap", 95),
    ("master/quest/event/challenge_dungeon_event_quest.orderedmap", 107),
    ("master/quest/character_quest.orderedmap", 108),
    ("master/quest/event/daily_exp_mana_event_quest_odds.orderedmap", 11),
    ("master/quest/event/daily_week_event_quest_odds.orderedmap", 11),
    ("master/quest/ex_quest.orderedmap", 106),
    ("master/quest/event/expert_single_event_quest.orderedmap", 109),
    ("master/quest/event/hard_multi_event_quest.orderedmap", 107),
    ("master/quest/main_quest.orderedmap", 106),
    ("master/quest/practice/practice_quest.orderedmap", 107),
    ("master/quest/event/raid_event_quest.orderedmap", 96),
    ("master/quest/event/ranking_event_single_quest.orderedmap", 89),
    ("master/quest/event/rush_event_quest.orderedmap", 95),
    ("master/quest/event/score_attack_event_quest.orderedmap", 99),
    ("master/skill_preview/skill_preview_quest.orderedmap", 27),
    ("master/quest/event/solo_time_attack_event_quest.orderedmap", 98),
    ("master/quest/event/story_event_single_quest.orderedmap", 108),
    ("master/quest/event/tower_dungeon_event_quest.orderedmap", 96),
    ("master/tutorial/tutorial_quest.orderedmap", 47),
    ("master/quest/event/world_story_event_boss_battle_quest.orderedmap", 106),
    ("master/quest/event/world_story_event_quest.orderedmap", 107),
]
BOSS_KIND = {"0": "standard_boss", "1": "general_boss", "2": "kraken", "3": "orochi", "4": "orochi_ex",
             "5": "orochi_ex_head", "6": "conductor", "7": "touyakiren_ceo", "8": "general_boss",
             "9": "water_sphere", "10": "holy_sphere", "11": "wind_sphere", "12": "thunder_sphere",
             "13": "fire_sphere"}
SPAWN_KIND = {"Funnel": "general_funnel", "Zako": "general_zako", "StandardFunnel": "standard_funnel"}
GENERIC = {"general_boss", "general_zako", "general_funnel", "standard_boss", "standard_funnel"}
TIER = {"zone": 0, "spawn": 0, "alter_ego": 0, "row": 0, "dslweak": 1, "esdlweak": 1, "rowweak": 2}


def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)


def _lists(x):
    if isinstance(x, list):
        yield x
        for v in x:
            yield from _lists(v)
    elif isinstance(x, dict):
        for v in x.values():
            yield from _lists(v)


def _pieces(cell):
    out = {cell.strip()}
    for p in re.split(r"[,\s]", cell):
        out.add(p.strip())
    for p in re.findall(r'"([^"]+)"', cell):
        out.add(p.strip())
    out.discard("")
    return out


def _numeric_keys(entry) -> list[int]:
    return [int(k) for k in entry if str(k).lstrip("-").isdigit()]


class LevelScan:
    def __init__(self, view: View):
        import wf_dsl  # 延迟导入:只有 level 检查需要 AMF3 解析
        self.wf_dsl = wf_dsl
        self.view = view
        self.T = {n: view.table(lp) or {} for n, lp in LEVEL_TABLES.items()}
        self.missing_tables = [lp for n, lp in LEVEL_TABLES.items() if view.table(lp) is None]
        self.KEY_INDEX: dict[str, list[str]] = {}
        for n, t in self.T.items():
            for k in t:
                self.KEY_INDEX.setdefault(k, []).append(n)
        self.FD = view.table("master/battle/field_data.orderedmap") or {}
        self.Z = view.table("master/battle/zone.orderedmap") or {}
        self.W = view.table("master/battle/boss/general_enemy_watch.orderedmap") or {}
        self.FD_ZONE = {}
        for k, v in self.FD.items():
            if isinstance(v, str) and v:
                r = row(v)
                if len(r) > 2 and r[2] in self.Z:
                    self.FD_ZONE[k] = r[2]
        self.dsl_tree = functools.lru_cache(maxsize=None)(self._dsl_tree)
        self.esdl_tree = functools.lru_cache(maxsize=None)(self._esdl_tree)
        self.dsl_refs = functools.lru_cache(maxsize=None)(self._dsl_refs)
        self.esdl_refs = functools.lru_cache(maxsize=None)(self._esdl_refs)
        self.watch_refs = functools.lru_cache(maxsize=None)(self._watch_refs)
        self.row_refs = functools.lru_cache(maxsize=None)(self._row_refs)

    def _parse_amf(self, logical):
        raw = self.view.raw(logical)
        if raw is None:
            return None
        try:
            return self.wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
        except Exception:  # noqa: BLE001
            return None

    def _dsl_tree(self, path):
        return self._parse_amf(path + ".action.dsl.amf3.deflate")

    def _esdl_tree(self, path):
        p = path if path.endswith(".esdl.amf3.deflate") else path + ".esdl.amf3.deflate"
        return self._parse_amf(p)

    def classify(self, s, refs, how, self_ref=None):
        if s in self.KEY_INDEX and how:
            for tn in self.KEY_INDEX[s]:
                if (tn, s) != self_ref:
                    refs.add(("key", tn, s, how))
        if "/" in s:
            if self.dsl_tree(s) is not None:
                refs.add(("dsl", s))
            elif self.esdl_tree(s) is not None:
                refs.add(("esdl", s))

    @staticmethod
    def _dedupe(refs):
        best = {}
        for r in refs:
            if r[0] == "key":
                k = r[1:3]
                if k not in best or TIER[r[3]] < TIER[best[k][3]]:
                    best[k] = r
        return frozenset([r for r in refs if r[0] != "key"] + list(best.values()))

    def _dsl_refs(self, path):
        refs = set()
        t = self.dsl_tree(path)
        if t is None:
            return frozenset()
        for lst in _lists(t):
            if len(lst) >= 2 and lst[0] == "SpawnFunnel" and isinstance(lst[1], list) \
                    and len(lst[1]) >= 2 and lst[1][0] in SPAWN_KIND:
                refs.add(("key", SPAWN_KIND[lst[1][0]], lst[1][1], "spawn"))
            if len(lst) >= 2 and lst[0] == "SpawnAlterEgo" and isinstance(lst[1], str):
                refs.add(("key", "general_boss", lst[1], "alter_ego"))
        for s in set(_strings(t)):
            self.classify(s, refs, "dslweak")
        refs.discard(("dsl", path))
        return self._dedupe(refs)

    def _esdl_refs(self, path):
        refs = set()
        t = self.esdl_tree(path)
        if t is None:
            return frozenset()
        pre = t.get("bH") if isinstance(t, dict) and isinstance(t.get("bH"), str) else ""
        for s in set(_strings(t)):
            self.classify(s, refs, "esdlweak")
            if pre and "/" not in s and self.dsl_tree(pre + s) is not None:
                refs.add(("dsl", pre + s))
        return self._dedupe(refs)

    def _watch_refs(self, key):
        refs = set()
        for sub in self.W.values():
            if isinstance(sub, dict) and key in sub:
                for s in set(_strings(sub[key])):
                    for p in _pieces(s):
                        if "/" in p:
                            self.classify(p, refs, None)
        return frozenset(refs)

    @staticmethod
    def select_row(entry, lv):
        for k in entry:            # 客户端:按键序取首个 >= lv
            if str(k).lstrip("-").isdigit() and int(k) >= lv:
                return k
        nums = [k for k in entry if str(k).lstrip("-").isdigit()]
        return max(nums, key=int) if nums else None

    def _row_refs(self, tn, key, lk):
        refs = set()
        txt = self.T[tn][key].get(lk) if isinstance(self.T[tn][key], dict) else None
        if not isinstance(txt, str):
            return frozenset()
        for r in rows(txt):
            for cell in r:
                for p in _pieces(cell):
                    self.classify(p, refs, "rowweak" if tn in GENERIC else "row", self_ref=(tn, key))
        return self._dedupe(refs)

    def closure(self, roots, lv, parents=None, tier=1):
        seen_k, seen_a = set(), set()
        todo = [(("key", tn, k, "zone"), None) for tn, k in roots]
        miss = set()
        while todo:
            n, par = todo.pop()
            if n[0] == "key":
                tn, k = n[1], n[2]
                if TIER[n[3]] > tier or (tn, k) in seen_k:
                    continue
                seen_k.add((tn, k))
                if parents is not None:
                    parents[("key", tn, k)] = (par, n[3])
                if k not in self.T.get(tn, {}) or not isinstance(self.T[tn][k], dict):
                    miss.add((tn, k))
                    continue
                lk = self.select_row(self.T[tn][k], lv)
                me = ("key", tn, k)
                if lk is not None:
                    todo.extend((x, me) for x in self.row_refs(tn, k, lk))
                todo.extend((x, me) for x in self.watch_refs(k))
            else:
                if n[:2] in seen_a:
                    continue
                seen_a.add(n[:2])
                if parents is not None:
                    parents[n[:2]] = (par, n[0])
                todo.extend((x, n[:2]) for x in (self.dsl_refs(n[1]) if n[0] == "dsl" else self.esdl_refs(n[1])))
        return seen_k, miss

    def chain(self, qid, tk, tier=0):
        roots, lv = self.quest_roots[qid]
        par = {}
        self.closure(roots, lv, par, tier)
        node, out = ("key",) + tuple(tk), []
        guard = 0
        while node is not None and guard < 64:
            guard += 1
            p, how = par.get(node, (None, "?"))
            out.append(f"{node[1] if node[0] == 'key' else node[0]}:{node[-1]}"
                       + (f"({how})" if node[0] == "key" else ""))
            node = p
        return " <- ".join(out)

    def zone_roots(self, zone):
        out = []
        zt_all = self.Z.get(zone, {})
        items = zt_all.items() if isinstance(zt_all, dict) else [("0", zt_all)]
        for _, zt in items:
            if not isinstance(zt, str) or not zt:
                continue
            zr = row(zt)
            for c in range(2, 21, 2):
                if c < len(zr) and zr[c] not in ("(None)", ""):
                    out.append(("general_zako", zr[c]))
            for c in range(23, 35, 2):
                if c + 1 < len(zr) and zr[c] not in ("(None)", ""):
                    tn = BOSS_KIND.get(zr[c])
                    if tn:
                        out.append((tn, zr[c + 1]))
                    else:
                        self.notes.add(f"zone {zone}: boss kind {zr[c]} id {zr[c + 1]} 未建模")
        return out

    def run(self):
        self.notes = set()
        self.quest_levels, self.quest_roots, self.lookups, self.missing = {}, {}, {}, {}
        self.quest_tables_seen = 0
        for lp, lc in QUEST_TABLES:
            Q = self.view.table(lp)
            if Q is None:
                continue
            self.quest_tables_seen += 1
            name = lp.split("/")[-1].replace(".orderedmap", "")

            def walk(node, path):
                if isinstance(node, dict):
                    for k, v in node.items():
                        yield from walk(v, path + (k,))
                elif isinstance(node, str) and node:
                    for i, r in enumerate(rows(node)):
                        if r:
                            yield path + ((str(i),) if i else ()), r
            for path, r in walk(Q, ()):
                if lc >= len(r) or not r[lc].lstrip("-").isdigit():
                    continue
                lv = int(r[lc])
                qid = name + ":" + "/".join(path)
                zones = {self.FD_ZONE[c] for c in r if c in self.FD_ZONE}
                if not zones:
                    continue
                self.quest_levels[qid] = lv
                roots = [x for z in sorted(zones) for x in self.zone_roots(z)]
                self.quest_roots[qid] = (roots, lv)
                prev = set()
                for tier in (0, 1, 2):
                    nodes, miss = self.closure(roots, lv, tier=tier)
                    for tk in nodes - prev:
                        if tk[1] in self.T.get(tk[0], {}):
                            self.lookups.setdefault(tk, {}).setdefault(lv, {}).setdefault(qid, tier)
                    for m in miss:
                        self.missing.setdefault(m, {}).setdefault(qid, tier)
                    prev = nodes
        self.gaps = {}
        for (tn, k), byl in self.lookups.items():
            nums = _numeric_keys(self.T[tn][k])
            if not nums:
                continue
            mx = max(nums)
            hit = {qq: t for lv, qs in byl.items() if lv > mx for qq, t in qs.items()}
            if hit:
                tmin = min(hit.values())
                self.gaps[(tn, k)] = {
                    "max": mx, "tier": tmin,
                    "need": max(lv for lv, qs in byl.items() if lv > mx and min(qs.values()) == tmin),
                    "quests": sorted(qq for qq, t in hit.items() if t == tmin)}
        # *_variable:tier0 查到的 general_* 键,variable 表里有该键时同等级也必须有行
        self.var_gaps = {}
        for tn, lp in VARIABLE_TABLES.items():
            V = self.view.table(lp)
            if V is None:
                self.notes.add(f"{lp} 不在视图里,variable 缺口未检查")
                continue
            for (t, k), byl in self.lookups.items():
                if t != tn or not isinstance(V.get(k), dict):
                    continue
                nums = _numeric_keys(V[k])
                vmax = max(nums) if nums else -1
                for lv, qs in byl.items():
                    t0 = [qq for qq, tier in qs.items() if tier == 0]
                    if t0 and lv > vmax:
                        g = self.var_gaps.setdefault((lp, k), {"max": vmax, "need": lv, "quests": set()})
                        g["need"] = max(g["need"], lv)
                        g["quests"].update(t0)
        top = max(self.quest_levels.values()) if self.quest_levels else 0
        self.curve_gaps = {}
        for cn, lp in CURVE_TABLES.items():
            c = self.view.table(lp)
            if not c:
                self.notes.add(f"{cn} 不在视图里(多为 APK 内置表),未检查")
                continue
            if all(str(k).lstrip("-").isdigit() for k in c):
                if max(map(int, c)) < top:
                    self.curve_gaps[(cn, "")] = {"max": max(map(int, c)), "need": top}
            else:
                for k, v in c.items():
                    nums = _numeric_keys(v) if isinstance(v, dict) else []
                    if nums and max(nums) < top:
                        self.curve_gaps[(cn, k)] = {"max": max(nums), "need": top}
        return self


def check_level(args, view: View, old: View | None, rep: Report):
    s = LevelScan(view).run()
    if s.quest_tables_seen == 0 or not s.FD or not s.Z:
        rep.add("WARN", "level", "level.skipped", "视图里缺 quest/field_data/zone 表,等级缺口检查跳过")
        return
    rep.notes.append(f"等级检查: {s.quest_tables_seen} 张 quest 表, {len(s.quest_levels)} 个关卡, "
                     f"等级 {min(s.quest_levels.values(), default=0)}..{max(s.quest_levels.values(), default=0)}, "
                     f"{len(s.lookups)} 个等级表条目被引用")
    if s.missing_tables:
        rep.notes.append("不在视图里的等级表(相关引用按缺键处理): " + ", ".join(
            Path(x).stem for x in s.missing_tables))
    old_gaps = None
    if old is not None:
        try:
            o = LevelScan(old).run()
            old_gaps = set(o.gaps) | {("var",) + k for k in o.var_gaps}
        except Exception as exc:  # noqa: BLE001
            rep.notes.append(f"--since 视图的等级扫描失败,不区分新旧: {exc}")
    for (tn, k), g in sorted(s.gaps.items()):
        if g["tier"] == 0:
            pre = old_gaps is not None and (tn, k) in old_gaps
            rep.add("WARN" if pre else "ERROR", "level", f"level.gap:{tn}:{k}",
                    f"等级缺口 {tn}[{k}] 最高 {g['max']} < 关卡等级 {g['need']}(U_3be147 必崩)"
                    + (",--since 之前就有" if pre else ""),
                    [f"关卡({len(g['quests'])}): {', '.join(g['quests'][:6])}",
                     "路径: " + s.chain(g["quests"][0], (tn, k), 0)])
        else:
            rep.add("INFO", "level", f"level.nameonly:{tn}:{k}",
                    f"仅按名引用(tier{g['tier']},客户端不按等级查) {tn}[{k}] 最高 {g['max']} < {g['need']}",
                    [f"关卡: {', '.join(g['quests'][:4])}"])
    # variable 表走 getSurjectivityWithDefault:没有 >=lv 的键时给空表,不立刻抛;
    # 状态机按变量取值(GeneralEnemy.as resolveVariable,如「指定回数再生(变数)」)时才崩
    # (1.4.202 funnel_discarded_dragon_fire_RE)。官方数据里也有不崩的此类缺口,
    # 所以只有本次推送新引入的(需 --since)记 ERROR,其余记 WARN。
    for (lp, k), g in sorted(s.var_gaps.items()):
        new = old_gaps is not None and ("var", lp, k) not in old_gaps
        qs = sorted(g["quests"])
        rep.add("ERROR" if new else "WARN", "level", f"level.var_gap:{Path(lp).stem}:{k}",
                f"variable 缺口 {Path(lp).stem}[{k}] 最高 {g['max']} < 关卡等级 {g['need']}"
                f"(变量表取空,状态机用到变量时崩)" + (",本次新引入" if new else ""),
                [f"关卡({len(qs)}): {', '.join(qs[:6])}"])
    for (cn, k), g in sorted(s.curve_gaps.items()):
        rep.add("ERROR", "level", f"level.curve:{cn}:{k}",
                f"曲线表 {cn}{'[' + k + ']' if k else ''} 最高 {g['max']} < 最高关卡等级 {g['need']}")
    for (tn, k), qs in sorted(s.missing.items()):
        if min(qs.values()) != 0 or view.table(LEVEL_TABLES[tn]) is None:
            continue
        rep.add("WARN", "level", f"level.missing_key:{tn}:{k}",
                f"zone/DSL 引用了不存在的 {tn}[{k}]", [f"关卡: {', '.join(sorted(qs)[:4])}"])
    for n in sorted(s.notes):
        rep.notes.append(n)


# ---------------------------------------------------------------- main

def load_pathlist() -> dict[str, str]:
    p = MOD_DIR / "WF_PATHLIST_recovered.txt"
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


def main(argv=None) -> int:
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
    allow_doc = json.loads(args.allowlist.read_text("utf-8")) if args.allowlist else {}
    rep = Report(set(allow_doc.get("ids", [])))
    allow_iqs = {str(x) for x in allow_doc.get("item_quest_search_exempt", [])}
    only = set((args.only or "chain,text,companion,level").split(","))

    chain = list_chain(active) + [p.resolve() for p in args.extra_zip]
    view = View(chain, args.base_store)
    old = None
    if args.since:
        old = View(list_chain(active, vkey(args.since)), args.base_store)
        new_zips = {p.name for p in chain if p not in set(old.zips)}
    else:
        new_zips = {p.name for p in chain}
    tail = max((archive_key(p.name)[1] for p in list_chain(active)), default=None)
    print(f"视图: 基础 store={args.base_store or '(无,只看链)'}; 链 {len(chain)} 个包,"
          f"链尾 {'.'.join(map(str, tail)) if tail else '?'}"
          + (f"; 候选 {', '.join(p.name for p in args.extra_zip)}" if args.extra_zip else "")
          + (f"; --since {args.since}(新包 {len(new_zips)} 个)" if args.since else ""))

    if "chain" in only:
        check_chain(args, manifest, active, new_zips, rep, load_pathlist())
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
