"""客户端技能描述检查。"""
from __future__ import annotations

from .prepush_base import *

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


