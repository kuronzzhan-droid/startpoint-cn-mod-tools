# -*- coding: utf-8 -*-
"""wf_rogue_season.py — 「这次改动到底算不算换了一座塔」的判据 + 换期回调。

背景(2026-08-28 作者裁定)
------------------------------------------------------------------
「每次重 roll 塔,排行榜结算,新塔是新榜不会有之前的排行。」

`wf_rogue_reroll.py` 那条路语义明确(整局重开 = 一定是新塔),直接回调服务端
「结算并开启新一期」就行。但 GUI 还有两条会**重建并发布整座塔**的入口:

  · ①「难度曲线 / 重摇」面板的「应用 + 发布」(`wf_rogue_build --write --publish`,
    `--seed` 缺省是当天日期 ⇒ 换一天点一次就是一座新塔);
  · ⑥ 面板的「📤 发布」(把 store 里已经改好的内容发上链)。

麻烦在于 ⑥ **也用来改单层 boss**。每次发布都换期会造出一串没人打过的空榜,
而换期不可逆(换掉之后上一期再也结算不了)。⇒ 必须先分清
「真的换了一座塔」和「只动了一层」。

判据(有实证)
------------------------------------------------------------------
拿 store 里 `rush_event_quest` 的**每一层内容**做指纹(场地 c98 / boss 属性 c69 /
敌等级 c95 / HP c86 / ATK c89 / 五个场地效果槽 c71-c80),和「当前这一期开张时那座塔」
的指纹逐层比,数**变了多少层**:

  · 层数本身变了(--rounds 改过)          ⇒ 真换塔
  · 变化层数 ≥ max(2, 总层数的一半)        ⇒ 真换塔
  · 变化层数 > 0 但没到一半                ⇒ 小修,不换期
  · 一层都没变                            ⇒ 什么都没发生

阈值不是拍脑袋:store 里有 92 份历史版本(`.bak-wfquest-*` 91 份 + live 1 份,
2026-07-13 → 08-23),其中 **90 份能解出楼层指纹**(2 份表体解不开,跳过),
于是 **89 次真实转换**,排除无尽层 0 之后 ——

    真换塔(整轮 build 重摇)   59 次,变化占比 **66.7% – 100%**
    小修(手改一到几层)        24 次,变化占比 **3.3% – 33.3%**
    一层没变                    6 次

两段之间 33.3%→66.7% 是**空的**,50% 这条线落在空带正中央。绝对层数上,小修最多
只到 6 层,而整轮重摇最少也换掉 2/3 的层。所以这条判据在作者的真实使用史上零误判。
(计数经 20260828 三轮复核实测复现:`versions 92 / digests 90 / new-tower 59 /
minor 24 / unchanged 6`。)

判不准的时候一律**不换期**:少换一次期只是「新塔上还挂着旧塔的榜」,
到后台点一下「结算并开启新一期」就补上了;错换一次期是不可逆的。

基线存哪 / 它凭什么可信
------------------------------------------------------------------
`mod-tools/work/rogue_tower_season.json`,记「当前这一期开张时那座塔」的逐层指纹
**和那一期的期号**。Python 侧每次换期(`wf_rogue_reroll.py` 的两条换期分支、
本文件 `sync()` 换期成功之后)都会刷新它。

⚠ **但服务端有五条换期通道一条都不碰这个文件**(20260828 三轮复核的 blocker):
游戏内重摇钩子(它给子进程传 `--keep-season`,换期在服务端进程里做)、后台
「结算并开启新一期」、后台「立即结算」(结算事务自带换期)、到点自动结算的调度器、
指纹兜底。走过其中任何一条,基线就停在**换期之前**那座塔上 —— 这时再用 ⑥ 改一层
boss 发布,判据会数出「30/30 层都变了」,判成真换塔,**主动发起一次不该发生的
结算 + 换期**:把仍在进行中的一期提前结算发奖、清空当期榜、作废所有进行中的 run。
漏判只是少换一期(后台点一下就补上),误判不可恢复,所以这个方向必须堵死。

⇒ 判成「真换塔」之后、**真要动手之前**先交叉核对期号:向服务端问一句「你现在第几期」
(`wf_rogue_reroll.current_season_via_server`),和基线里记的那个期号对不上,
就说明这份基线是别的通道换期之前记的 ⇒ 一律**不换期**,只把当前这座塔重记为基线。
问不到期号(服务端没起 / token 不对)同样不换期 —— 反正换期回调也发不出去。
这一道闸同时管住上面那五条通道,不必逐条去补基线刷新。
(刻意只拦「要动手」那一档:小修 / 一层没变本来就不换期,为它们多问一句只会在
 8001 没起时白添一行吓人的警告。)

没有基线时(第一次用 / 文件被删)判为 `unknown`:**不换期**,只把当前这座塔
记成基线,下一次就有得比了。

接线到哪些入口
------------------------------------------------------------------
`wf_gui.py` 里三条会把楼层改动**推上链**的路,发布成功之后各调一次 `sync()`:
  · `rogue_build_apply(publish=True)`  来源 `gui-build`
  · `rogue_publish()`(⑥「📤 发布」)  来源 `gui-publish`
  · `rogue_layout_apply(publish=True)`(⑥ 逐层编辑器的「写入并发布」)来源 `gui-layout`
`rogue_randomize()` 只写 store 不发布 ⇒ 刻意不调:塔还没对玩家生效,期不该动;
它写进去的整塔改动会在上面那次「📤 发布」里被一并算成「真换塔」。

**已知没接的一条**:直接在命令行跑 `python mod-tools/wf_rogue_build.py --write
--publish`。没接是因为 `wf_rogue_reroll.py` 内部正是用这条命令重建塔的
(`build_command()`),在 build 里换期会和 reroll 自己那次换期撞成「一次重摇跳两期」,
要避开就得再造一套 `--keep-season` 传递契约,收益不抵风险。
走那条路之后请到后台点一次「结算并开启新一期」;或者干脆用 GUI / `wf_rogue_reroll.py`。
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "mod-tools" / "work" / "rogue_tower_season.json"

ROGUE_EVENT_ID = "700099"
QUEST_LOGICAL = "master/quest/event/rush_event_quest.orderedmap"

# 进逐层指纹的列。挑的是「换一座塔就一定会变、手动微调也确实该算变了」的那些:
#   c98 场地(层的身份)/ c69 boss 属性 / c95 敌等级 / c86 HP / c89 ATK /
#   c71-c80 五个场地效果槽(kind + strength 交替)
# 刻意**不**收 c4 副标题:它是 build 按场地效果重渲的展示文本,跟着上面这些走,
# 收进来只会让同一个改动被数两遍。
DIGEST_COLUMNS = (98, 69, 95, 86, 89, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80)

# 无尽层(round 0)不属于爬塔:它有自己的官方排行榜,也有自己的重摇工具
# (`wf_rogue_save.py`),不该把它的改动算进「塔变了没有」。
ENDLESS_ROUND = "0"


def _cells(leaf) -> list[str]:
    line = leaf.decode("utf-8") if isinstance(leaf, (bytes, bytearray)) else leaf
    return next(csv.reader(io.StringIO(line)))


def tower_digest(event: str = ROGUE_EVENT_ID, path: Path | None = None) -> dict[str, str]:
    """读 store 里那座塔,算出 `{轮号: 该层内容指纹}`。

    :param event: rush 活动 id。
    :param path: 直接读某个文件(历史 `.bak` 版本用);缺省读 store 当前字节。
    :returns: 轮号 → 指纹;读不出来时返回空 dict(调用方据此判 `unknown`)。
    """
    import wf_quest_lib as qlib     # 惰性 import:它会拉起整个 mod 工具链

    try:
        tree = qlib.load_table(QUEST_LOGICAL, path)
    except Exception:
        return {}
    rows = tree.get(str(event)) or {}
    digest: dict[str, str] = {}
    for quest_no, leaf in rows.items():
        try:
            cells = _cells(leaf)
        except Exception:
            continue
        rnd = cells[2] if len(cells) > 2 else str(quest_no)
        if str(rnd) == ENDLESS_ROUND:
            continue
        digest[str(rnd)] = "|".join(
            cells[i] if len(cells) > i else "" for i in DIGEST_COLUMNS)
    return digest


def classify(baseline: dict[str, str] | None, current: dict[str, str]) -> dict:
    """纯判据:比两份逐层指纹,判「真换塔 / 小修 / 没变 / 判不准」。

    刻意不碰文件、不发 HTTP —— 阈值是要被单测钉住的东西。

    :param baseline: 当前这一期开张时那座塔;None/空 = 没有基线。
    :param current: 现在 store 里那座塔。
    :returns: {"verdict", "changed", "total", "threshold", "rounds"}
              verdict ∈ {"new-tower", "minor-edit", "unchanged", "unknown"}
    """
    if not current:
        return {"verdict": "unknown", "changed": 0, "total": 0,
                "threshold": 0, "rounds": [], "why": "读不出当前这座塔"}
    if not baseline:
        return {"verdict": "unknown", "changed": 0, "total": len(current),
                "threshold": 0, "rounds": [], "why": "还没有基线"}

    keys = set(baseline) | set(current)
    changed = sorted(
        (k for k in keys if baseline.get(k) != current.get(k)),
        key=lambda k: int(k) if k.isdigit() else 0)
    total = len(keys)
    # max(2, …) 是给小塔兜底:3 层塔的一半是 2,改一层不该算换塔。
    threshold = max(2, math.ceil(total / 2))

    if not changed:
        verdict, why = "unchanged", "一层都没变"
    elif set(baseline) != set(current):
        verdict, why = "new-tower", f"层数从 {len(baseline)} 变成 {len(current)}"
    elif len(changed) >= threshold:
        verdict, why = "new-tower", f"{len(changed)}/{total} 层变了(≥ {threshold})"
    else:
        verdict, why = "minor-edit", f"只有 {len(changed)}/{total} 层变了(< {threshold})"

    return {"verdict": verdict, "changed": len(changed), "total": total,
            "threshold": threshold, "rounds": changed, "why": why}


def load_state() -> dict:
    """读基线台账;文件不存在/坏了都当空。"""
    try:
        with open(STATE_PATH, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_baseline(event: str, digest: dict[str, str], season: int | None,
                  note: str = "") -> bool:
    """把 `digest` 记成「第 season 期开张时那座塔」。

    ⚠ 写失败**不是**「下次判 unknown」那么温柔(20260828 三轮复核纠正的一条错注释):
    文件会原封不动停在**上一次**的内容,`load_state()` 照样返回一份非空的旧 digest,
    `classify` 于是判 `new-tower` 而不是 `unknown` —— 正好是那次不可逆的误换期。
    只有文件从未存在过才会落到 `unknown`。

    真正兜住这件事的是 `sync()` 里的**期号交叉核对**:写失败意味着基线里那个期号
    也停在旧值上,和服务端一对就不符 ⇒ 那一次一律不换期。所以这里仍然吞异常
    (它只是本地缓存,不该让整条发布流程失败),但**要把失败喊出来**并返回给调用方。

    :returns: 真的落盘了吗。
    """
    state = load_state()
    state[str(event)] = {
        "season": season,
        "digest": digest,
        "note": note,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        os.makedirs(os.path.dirname(str(STATE_PATH)), exist_ok=True)
        tmp = Path(str(STATE_PATH) + ".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, STATE_PATH)
        return True
    except Exception as exc:
        print(f"[WARN] 换期判据基线没写进 {STATE_PATH}({type(exc).__name__}: {exc});"
              "基线停在上一次的内容 —— 下次发布会因期号对不上而判「基线不新鲜」,"
              "不换期(不会误清榜)。", flush=True)
        return False


def note_rollover(event: str = ROGUE_EVENT_ID, season: int | None = None,
                  note: str = "") -> None:
    """任何一次**成功换期**之后调它:把现在这座塔记成新一期的基线。

    `wf_rogue_reroll.py` 也要调 —— 不然「先一键重开换了期、再用 ⑥ 改一层」会拿
    重摇**之前**那座塔当基线,把一次单层小修误判成真换塔,白清一张榜。

    ⚠ 它管不到服务端那五条换期通道(后台按钮 / 调度器 / 指纹兜底根本不经过
    Python)。那些通道靠 `sync()` 里的期号交叉核对兜住:期号对不上就不换期。
    `season` 传 None 是允许的(重摇钩子那条路子进程问不到新期号),
    后果只是下次 `sync()` 判一次「基线不新鲜」⇒ 不换期、只重记基线。
    """
    save_baseline(event, tower_digest(event), season, note)


def sync(event: str = ROGUE_EVENT_ID, source: str = "gui",
         server: str | None = None) -> dict:
    """GUI 发布之后调一次:真换塔才「结算 + 换期」,小修不动。

    动手之前先过两道闸,任何一道不过都**不换期**(方向见模块头:漏判可恢复,
    误判不可恢复):
      ① 判据本身 —— 变化层数够不够半座塔;
      ② 判成「真换塔」之后,再核对**基线还新鲜吗** —— 基线里记的期号必须和服务端
         此刻的期号一致(服务端那五条换期通道都不会刷新本地基线,见模块头)。
         这道闸刻意只拦「要动手」那一档:小修/没变本来就不换期,没必要为了它们
         去问服务端一句(8001 没起时还会白白多一行吓人的警告)。

    :param event: rush 活动 id。
    :param source: 写进台账的来源(`gui-build` / `gui-publish` / `gui-layout`)。
    :param server: 服务端地址;缺省按 .env 解析。
    :returns: {"verdict", "rolled", "season", "message", "detail"}
              `rolled=True` 表示期号真的推进了。
              `verdict` 多一档 `stale-baseline`(基线不新鲜/核对不了 ⇒ 不换期)。
    """
    import wf_rogue_reroll as reroll   # 复用它的 rollover_via_server(唯一实现)

    current = tower_digest(event)
    state = load_state().get(str(event)) or {}
    baseline = state.get("digest") if isinstance(state.get("digest"), dict) else None
    detail = classify(baseline, current)
    verdict = detail["verdict"]

    if verdict == "unknown":
        # 顺手把服务端此刻的期号一起记下:基线里没有期号的话,下一次真换塔会被
        # 下面那道新鲜度闸拦一次(少换一期)。问不到就先留着原值,不影响安全性。
        live = reroll.current_season_via_server(str(event), server)
        # 读不出当前这座塔时**不许拿空 digest 覆盖基线** —— 那会把一份好基线冲掉,
        # 下一次真换塔就只能判 unknown(少换一期)。
        if current:
            save_baseline(event, current,
                          live["season"] if live["ok"] else state.get("season"),
                          f"bootstrap:{source}")
        return {"verdict": verdict, "rolled": False, "season": state.get("season"),
                "detail": detail,
                "message": "⚠ 没有可比的基线(第一次用 / 台账被删 / 读不出当前这座塔),"
                           "这次**不换期**,已把当前这座塔记为基线。真要开新一期请到"
                           "后台排行榜页点「结算并开启新一期」;下次再发布就能自动判了。"}

    if verdict == "unchanged":
        return {"verdict": verdict, "rolled": False, "season": state.get("season"),
                "detail": detail,
                "message": "楼层内容一层都没变(多半只是补发链上缺的文件),排行榜期号不动。"}

    if verdict == "minor-edit":
        return {"verdict": verdict, "rolled": False, "season": state.get("season"),
                "detail": detail,
                "message": f"只有 {detail['changed']}/{detail['total']} 层变了"
                           f"(层 {','.join(detail['rounds'][:8])}),判为单层微调,"
                           "**不换期** —— 每发一次就换一期会造一串没人打过的空榜,"
                           "而换期不可逆。真的是新塔请到后台点「结算并开启新一期」。"}

    # ── 判成真换塔了。动手之前先核对基线新鲜度 ────────────────────────────
    # 基线只有 Python 侧会写,而服务端那五条换期通道一条都不碰它(模块头有清单)。
    # 基线一旦落后,「只改了一层 boss」会被数成「30/30 层都变了」⇒ 落到这里 ⇒
    # 把仍在进行中的一期提前结算发奖、清空当期榜、作废所有进行中的 run,而换期不可逆。
    # 所以这一档必须先确认「基线记的那一期 == 服务端此刻这一期」。
    live = reroll.current_season_via_server(str(event), server)
    if not live["ok"]:
        return {"verdict": "stale-baseline", "rolled": False, "season": state.get("season"),
                "detail": detail,
                "message": f"⚠ 判据说这是**真换塔**({detail['why']}),但核对不了排行榜"
                           f"期号({live['error']}) ⇒ 无法确认这份基线还新不新鲜,"
                           "这次**不换期**(基线也没动)。服务端没起的话换期回调本来也"
                           "发不出去;起好 8001 再发布一次,或到后台点「结算并开启新一期」。"}
    if state.get("season") != live["season"]:
        save_baseline(event, current, live["season"], f"rebase:{source}")
        return {"verdict": "stale-baseline", "rolled": False, "season": live["season"],
                "detail": detail,
                "message": f"⚠ 判据基线记的是第 {state.get('season')} 期,而服务端现在是第 "
                           f"{live['season']} 期 —— 期间有别的通道换过期(游戏内整段重置 / "
                           "后台按钮 / 到点结算 / 指纹兜底),这份基线已经不能用来判"
                           f"「换没换塔」了(拿它比会数出 {detail['changed']}/"
                           f"{detail['total']} 层变了,而其中多少是那次换期带来的已经"
                           "分不清)。这次**不换期**,已把当前这座塔重记为第 "
                           f"{live['season']} 期的基线;下次发布就能正常判了。"
                           "这一次确实是新塔的话,到后台点一次「结算并开启新一期」。"}

    # 真换塔:回调服务端「结算并开启新一期」(先冻结名次发奖,再把期号 +1)
    result = reroll.rollover_via_server(str(event), source, server)
    if not result["ok"]:
        return {"verdict": verdict, "rolled": False, "season": state.get("season"),
                "detail": detail,
                "message": f"⚠ 判定为**真换塔**({detail['why']}),但换期回调失败:"
                           f"{result['error']}。期号一格没动 —— 只换期不结算的话,"
                           "上一期的名次和奖励永远补不回来。塔已经发上链了,"
                           "请到后台排行榜页点「结算并开启新一期」补上。"}

    body = result["body"] or {}
    season = body.get("season")
    save_baseline(event, current, season, f"rollover:{source}")
    mails = ((body.get("settlement") or {}) or {}).get("mailCount")
    settled = "已结算发奖" if body.get("settled") else \
        f"未结算({body.get('settleReason') or '原因未知'})"
    # 服务端的 `rolled=false` = 这一期一条完整成绩都没有,于是原地复用了它
    # (空期 +1 只会在台账里留下一段没人打过的空榜,而期号不可逆)。
    # 老版本服务端不发这个字段 ⇒ 缺省当成「推进了」,和过去的措辞一致。
    rolled = body.get("rolled", True)
    where = f"排行榜进入第 {season} 期" if rolled else \
        f"排行榜仍是第 {season} 期(这一期还没人打过,原地复用,不白烧一个期号)"
    return {"verdict": verdict, "rolled": True, "season": season, "detail": detail,
            "message": f"判定为**真换塔**({detail['why']})⇒ {where};"
                       f"{settled}" + (f",发出 {mails} 封奖励邮件" if mails else "")
                       + "。当期榜已清空。"}
