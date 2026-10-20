# -*- coding: utf-8 -*-
"""Regenerate the auto-generated codemap pages (gen-*.md). Read-only on every source tree.

    python D:\\WF\\startpoint-cn\\out\\codemap\\gen_codemap.py

Hand-written pages (README.md, data-tables.md, client.md, server-notes.md, tools.md) are not touched.
"""
import os, re, sys, collections, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
AS3 = r"D:\WF\decompile-complete-20261014\scripts"
KULO = r"D:\WF\ghmain"  # 测试服在用的服务端树(编辑台 8790 同源);startpoint-cn-kulo 停在 10-05
BUILDER = r"D:\WF\bughunt-20261014\builder"
PATCH_ACTIVE = os.path.join(KULO, r"assets\asset-patch\active")
# 重构后的 MOD 工具单一真源(wf 包 + 编辑台);分支 refactor/m4-studio-deliver,8790 编辑台从这里起
WFTOOLS = r"D:\WF\wf-mod-tools-worktrees\m4-integrate"
STAMP = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def rd(p):
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def rel(p, base):
    return os.path.relpath(p, base).replace("\\", "/")


def write(name, lines):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote", name, len(lines), "lines")


# ---------------------------------------------------------------- client
def walk_as():
    for root, _, files in os.walk(AS3):
        for fn in files:
            if fn.endswith(".as"):
                yield os.path.join(root, fn)


SUBSYSTEMS = [  # (title, path-substring regex, class-name regex)
    ("战斗伤害 battle damage", r"online/battle/impact", r"Calculator|Damage"),
    ("敌人等级/敌人数据 enemy level", r"common/data/battle/enemy", r"."),
    ("分数/战斗种类 score & battle kind", r"common/data/quest/id|scene/battle/battle/Battle\.as|[Ss]core", r"Score|BattleKind|^Battle$"),
    ("联机 lockstep/socket", r"pinball/online/(?!battle/impact)|context/socket|context/remote", r"Socket|Remote|Lockstep|Sync|Room|Online|Relay|Command"),
    ("加载与图集 loading & atlas", r"pinball/loading|asset/logic|asset/view|assetDownloader", r"Loading|Production|Atlas|Texture|Download|Cache"),
    ("技能/能力文案 skill & ability text", r"abilityDescription|ability/description|skill|dialog/general/variation", r"Description|Skill|Text|Summer"),
    ("master 表运行时 master runtime", r"pinball/master/(runtime|builder|structure)", r"."),
]


def gen_client():
    files = list(walk_as())
    out = [f"# 客户端 AS3 类索引(自动生成 {STAMP})", "",
           f"源:`{AS3}`(只读,{len(files)} 个 .as)。补全版(gpt-6.1-sol, 2026-10-14,§§ 412→24);旧档在 `D:\\WF\\_archive\\kept`。",
           "手写要点见 [client.md](client.md)。", ""]
    for title, pre, cre in SUBSYSTEMS:
        hits = []
        for p in files:
            r = rel(p, AS3)
            cls = os.path.basename(p)[:-3]
            if re.search(pre, r) and re.search(cre, cls) and "/master/generated/" not in r:
                hits.append(r)
        hits.sort()
        out += [f"## {title}  ({len(hits)})", ""]
        cap = 120
        for r in hits[:cap]:
            out.append(f"- `{os.path.basename(r)[:-3]}` — {r}")
        if len(hits) > cap:
            out.append(f"- …另 {len(hits) - cap} 个,用 `rg --files {AS3} | rg '<关键词>'` 查")
        out.append("")
    write("gen-client-classes.md", out)

    # master table -> client consumers
    gen = os.path.join(AS3, r"pinball\master\generated")
    tables = sorted(fn[:-8] for fn in os.listdir(gen) if fn.endswith("Table.as"))
    tset = set(tables)
    tok = re.compile(r"\b([A-Z][A-Za-z0-9]*?)(Table|Values)\b")
    users = collections.defaultdict(set)
    for p in files:
        r = rel(p, AS3)
        if "/master/generated/" in r:
            continue
        for m in set(tok.findall(rd(p))):
            if m[0] in tset:
                users[m[0]].add(r)
    snake = lambda s: re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()
    out = [f"# master 表 → 客户端读取类(自动生成 {STAMP})", "",
           "表名由 `pinball/master/generated/<Camel>Table.as` 反推 snake_case(近似,数字/缩写可能不准)。",
           "列解析在同目录 `<Camel>Values.as` 的 `parseAtN`(N=列号)。只列 generated 以外引用 Table/Values 的类,最多 8 个。", "",
           "| 表(推断) | Camel | 读取类数 | 主要读取类 |", "|---|---|---|---|"]
    for t in tables:
        u = sorted(users.get(t, ()))
        shown = ", ".join(f"`{x.split('/')[-1][:-3]}`" for x in u[:8])
        out.append(f"| {snake(t)} | {t} | {len(u)} | {shown} |")
    write("gen-client-master-tables.md", out)


# ---------------------------------------------------------------- server
def resolve_ts(from_file, spec):
    base = os.path.normpath(os.path.join(os.path.dirname(from_file), spec))
    for c in (base + ".ts", os.path.join(base, "index.ts"), base):
        if os.path.isfile(c):
            return c
    return None


ROUTE_RE = re.compile(r"\b(?:fastify|app|server|instance|f)\.(get|post|put|delete|all)\s*(?:<[^(]*?>)?\(\s*[\"'`]([^\"'`]+)")
REG_RE = re.compile(r"\.register\(\s*(\w+)\s*(?:,\s*\{[^}]*?prefix:\s*([\"'`])(.*?)\2)?")


def gen_server():
    src = os.path.join(KULO, "src")
    out = [f"# 服务端路由 → handler 文件(自动生成 {STAMP})", "",
           f"源:`{KULO}`(只读)。前缀来自 register(…, {{prefix}});`${{apiPrefix}}` = `/api/index.php`。",
           "「写库线索」= 该文件 import 的 data/updaters、lib/persistence、data/domains 模块。手写说明见 [server-notes.md](server-notes.md)。", ""]
    seen = set()

    def routes_in(path):
        txt = rd(path)
        res = []
        for i, line in enumerate(txt.splitlines(), 1):
            m = ROUTE_RE.search(line)
            if m:
                res.append((m.group(1).upper(), m.group(2), i))
        return txt, res

    def persist_hints(txt):
        mods = re.findall(r"from\s+[\"']([^\"']*(?:updaters|persistence|domains)[^\"']*)[\"']", txt)
        return sorted({m.split("/data/")[-1].split("/lib/")[-1] for m in mods})

    def emit(entry, prefix_label, depth=0):
        txt = rd(entry)
        imports = dict(re.findall(r"import\s+(\w+)(?:\s*,\s*\{[^}]*\})?\s+from\s+[\"']([^\"']+)[\"']", txt))
        for line in txt.splitlines():
            m = REG_RE.search(line)
            if not m or m.group(1) not in imports:
                continue
            f = resolve_ts(entry, imports[m.group(1)])
            if not f or f in seen:
                continue
            seen.add(f)
            prefix = (prefix_label + (m.group(3) or "")).replace("${apiPrefix}", "/api/index.php")
            ftxt, rs = routes_in(f)
            hints = persist_hints(ftxt)
            out.append(f"### `{prefix or '/'}` — {rel(f, KULO)}")
            if hints:
                out.append("写库线索: " + ", ".join(f"`{h}`" for h in hints[:10]))
            for meth, pth, ln in rs:
                out.append(f"- {meth} `{prefix}{pth}` — {rel(f, KULO)}:{ln}")
            out.append("")
            if depth < 2:
                emit(f, prefix, depth + 1)

    for entry in ("cn-server.ts", "server.ts"):
        out.append(f"## 入口 src/{entry}")
        out.append("")
        emit(os.path.join(src, entry), "", 0)
    # stragglers: route files never reached via register
    out += ["## 未经 register 链解析到的路由文件", ""]
    for root, _, fs in os.walk(src):
        for fn in fs:
            p = os.path.join(root, fn)
            if fn.endswith(".ts") and p not in seen:
                _, rs = routes_in(p)
                if rs:
                    out.append(f"- {rel(p, KULO)}: " + ", ".join(f"{m} `{x}`:{l}" for m, x, l in rs[:12]))
    write("gen-server-routes.md", out)

    # env flags
    env = collections.defaultdict(list)
    for root, _, fs in os.walk(src):
        for fn in fs:
            if not fn.endswith(".ts"):
                continue
            p = os.path.join(root, fn)
            for i, line in enumerate(rd(p).splitlines(), 1):
                for m in re.finditer(r"process\.env\.([A-Z0-9_]+)(.{0,60})", line):
                    d = re.search(r"(\?\?|\|\|)\s*([^,;)]+)", m.group(2))
                    env[m.group(1)].append((rel(p, KULO), i, d.group(2).strip() if d else ""))
    out = [f"# 服务端环境变量(自动生成 {STAMP})", "", "默认值是同一行 `??`/`||` 右侧的粗略抓取,不保证准确。", "",
           "| 变量 | 默认(粗) | 位置 |", "|---|---|---|"]
    for k in sorted(env):
        locs = env[k]
        dflt = next((d for _, _, d in locs if d), "")
        out.append(f"| {k} | `{dflt}` | " + "<br>".join(f"{p}:{l}" for p, l, _ in locs[:4]) + " |")
    write("gen-server-env.md", out)

    # server asset json -> importers
    imp = collections.defaultdict(set)
    for root, _, fs in os.walk(src):
        for fn in fs:
            if fn.endswith(".ts"):
                p = os.path.join(root, fn)
                for j in re.findall(r"[\"'/]([A-Za-z0-9_\-]+\.json)[\"']", rd(p)):
                    imp[j].add(rel(p, KULO))
    out = [f"# 服务端 JSON 数据文件 → 读取它的 src 文件(自动生成 {STAMP})", "",
           "按文件名匹配 import / joinPath 字面量。服务端不读 master 表,读的是 `assets/*.json` 等派生 JSON。", "",
           "| json | 读取文件 |", "|---|---|"]
    for j in sorted(imp):
        out.append(f"| {j} | " + "<br>".join(sorted(imp[j])[:6]) + " |")
    write("gen-server-json.md", out)


# ---------------------------------------------------------------- tools
def first_doc(p):
    try:
        txt = rd(p)
    except OSError:
        return ""
    lines = [l for l in txt.splitlines()[:40] if l.strip() and not re.match(r"#!|#.*coding[:=]", l.strip())]
    body = "\n".join(lines).lstrip()
    m = re.match(r'(?:"""|\'\'\')\s*(.*?)\s*$', body, re.M)  # module docstring, first non-empty line
    if m:
        for cand in [m.group(1)] + lines[1:8]:
            t = cand.strip().strip("\"'=-* ")
            if t:
                return t[:140]
    for l in lines:
        if not l.lstrip().startswith("#"):
            break
        t = l.strip().lstrip("#").strip("=-* ")
        if t:
            return t[:140]
    return "(无说明)"


def gen_tools():
    out = [f"# 工具脚本清单(自动生成 {STAMP})", "", "手写说明见 [tools.md](tools.md)。", "",
           f"## builder 脚本 `{BUILDER}`", ""]
    for fn in sorted(os.listdir(BUILDER)):
        if fn.endswith(".py"):
            out.append(f"- `{fn}` — {first_doc(os.path.join(BUILDER, fn))}")
    out += ["", f"## 补丁包 active `{PATCH_ACTIVE}`", ""]
    if os.path.isdir(PATCH_ACTIVE):
        for fn in sorted(os.listdir(PATCH_ACTIVE)):
            p = os.path.join(PATCH_ACTIVE, fn)
            sz = os.path.getsize(p) if os.path.isfile(p) else 0
            out.append(f"- `{fn}`" + (f" ({sz // 1024} KiB)" if sz else " (dir)"))
    write("gen-tools.md", out)


# ---------------------------------------------------------------- wf 包 / 编辑台
def gen_wf():
    base = WFTOOLS
    out = [f"# wf 工具包与编辑台(自动生成 {STAMP})", "",
           f"源:`{base}`(只读;分支 refactor/m4-studio-deliver)。命令入口 `python -m wf <子命令>`、"
           "`python -m wf.studio`(编辑台 8790)、`python -m wf.studio.draft <子命令>`(agent 用)。", ""]
    if not os.path.isdir(base):
        out.append("(源目录不存在)")
        write("gen-wf.md", out)
        return
    # 1) 包内模块
    out += ["## wf 包模块", ""]
    pkg = os.path.join(base, "wf")
    for root, dirs, files in os.walk(pkg):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for fn in sorted(files):
            if fn.endswith(".py"):
                path = os.path.join(root, fn)
                out.append(f"- `{rel(path, base)}` — {first_doc(path)}")
    # 2) 编辑台 HTTP 路由
    out += ["", "## 编辑台 HTTP 路由(wf/studio)", ""]
    route = re.compile(r'\(\s*"(GET|POST|PUT|DELETE)"\s*,\s*re\.compile\(\s*r?"([^"]+)"')
    for root, dirs, files in os.walk(os.path.join(pkg, "studio")):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for fn in sorted(files):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            for i, line in enumerate(rd(path).splitlines(), 1):
                for m in route.finditer(line):
                    out.append(f"- {m.group(1)} `{m.group(2)}` — {rel(path, base)}:{i}")
    # 3) CLI 子命令
    out += ["", "## CLI 子命令", ""]
    sub = re.compile(r'add_parser\(\s*"([\w-]+)"')
    for root, dirs, files in os.walk(pkg):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for fn in sorted(files):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            names = [(m.group(1), i) for i, line in enumerate(rd(path).splitlines(), 1) for m in sub.finditer(line)]
            if names:
                out.append(f"- {rel(path, base)}: " + ", ".join(f"`{n}`:{i}" for n, i in names[:30]))
    # 4) schema 与能力注册表
    out += ["", "## JSON Schema", ""]
    sch = os.path.join(base, "schemas")
    if os.path.isdir(sch):
        for fn in sorted(os.listdir(sch)):
            out.append(f"- `schemas/{fn}`")
    caps = os.path.join(pkg, "caps")
    if os.path.isdir(caps):
        ymls = sorted(f for f in os.listdir(caps) if f.endswith(".yml"))
        out += ["", f"## 能力注册表 wf/caps({len(ymls)} 项)", ""]
        out += [f"- `{f[:-4]}`" for f in ymls]
    # 5) 前端视图
    views = os.path.join(base, "studio", "src")
    if os.path.isdir(views):
        out += ["", "## 前端(studio/src,Vite + TS + Preact)", ""]
        for root, dirs, files in os.walk(views):
            dirs[:] = sorted(dirs)
            for fn in sorted(files):
                if fn.endswith((".ts", ".tsx")):
                    out.append(f"- `{rel(os.path.join(root, fn), base)}`")
    write("gen-wf.md", out)


if __name__ == "__main__":
    which = sys.argv[1:] or ["client", "server", "tools", "wf"]
    for w in which:
        {"client": gen_client, "server": gen_server, "tools": gen_tools, "wf": gen_wf}[w]()
