# -*- coding: utf-8 -*-
"""发布前的「键不许消失」硬闸门。

## 为什么需要它

CDN 的投递单位是**整个文件**:store 里的文件名 = 逻辑路径的 sha1(`2/38` 布局),
而一张 master 表就是一个 orderedmap 二进制块(`ability` 一块装 3020 个键)。
客户端没有「取某一行」的协议 ⇒ 改一行就要重发整块 ⇒ **发布 = 用本地这一份整体替换线上那一份**。

于是任何「本地这份比线上少了几个键」的情况,发布出去就是**删角色**。历史事故:

- 1.4.278 整表发布共享表,把只在设备上的基诺维 169999 顶掉 → 进主城 C8601;
- 杰拉德包里的 `power_flip_action.orderedmap` 只有 7 键而 live 有 10 键,
  发布即删掉赛瑞斯人形/龙形 PF + 风巨蜥 PF 三个键(见 `DO-NOT-PUBLISH-20260804.md`)。

两次的共同点:**没人在打包前比过键集合**。这个模块就干这一件事。

## 判据

对每个待发文件,取链上最新版本的同路径文件:
  链上有的键,新版必须一个不少。少一个 = 硬失败。
新增键、内容变化都放行(那才是发布的目的)。

键的读取走 `core.parse_index`,只解 orderedmap 的键索引,**与行编解码器无关**,
所以对 ability/character/action_skill/power_flip_action 这些不同 codec 的表一视同仁;
解不出来的(DSL、图片、mp3)自动跳过,只做存在性报告。

## 内容体检(`content_notes`,只告警不阻断)

上面那条判据只看键集合,所以它**比不出**「键一个没少、但整表内容被换成了另一个
来源的版本」。1.4.307 就是这么过闸的:直发 store 原字节的 ability_soul,451 键
原封不动,而 409 个键的内容变了、108 个键的记录条数变少,把 1.4.164 以来在线的
整套官方魂珠增强一次性回退。对照 1.4.164→1.4.301 只动 15 个键(15 把深渊武器)
——那才是正常改动的形状。

于是补两条**提示**(永远不进 problems、永远不拦发布):
  ① 改动面过大(>20 个键且占比 >25%);
  ② 键内**记录条数变少** —— 一键多记录的表里,行没了和键没了是同一类损失,
     这条噪声低,不设占比门槛。
30 条历史 ability_soul 边回放:只有 6 条被标,且全是真的整表大改。

用法:
    python mod-tools/wf_publish_guard.py              # 检查当前 pending 列表
    python mod-tools/wf_publish_guard.py --tables ability,leader_ability
被 wf_publish 在打包前自动调用;要强行放行用 --allow-key-deletion(会在输出里大声说明)。
"""
from __future__ import annotations

import io
import json
import re
import sys
import zipfile
import zlib
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
ROOT = TOOL_DIR.parent
sys.path.insert(0, str(TOOL_DIR))
import wf_mod_tool as core  # noqa: E402

CDN_ROOT = core.resolve_cdn_root_lax()
CDN_COMMON_DIFF = CDN_ROOT / "archive-common-diff"
CDN_COMMON_FULL = CDN_ROOT / "archive-common-full"
PACKS = core.project_root() / "work" / "character_packs"

_EDGE = re.compile(r"^pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-(\d+)-")

# 每次重摇整批重建的**临时命名空间**,不是"内容"。
#
# 深渊连战塔每建一次就把上一座塔的 mod_rogue_f* / mod_rogue_z* / mod_rogue_boss*
# 全部删掉重写(wf_rogue_build 开头的 stale 清理),键集合本来就随塔形变化。
# 2026-08-07 之前每层都强制克隆一个法阵/HP 载体,键数只增不减,所以从没撞过这道闸;
# 改成"血量按不动就保留原 boss、不强行克隆"之后,一座塔少 12 个克隆是**正常结果**。
#
# 放行它安全的理由:这些键只被同一批一起发布的 quest→field_data→zone 链引用,
# 而那条链有更强也更具体的门禁(wf_rogue_build 的「31 关解析链复核」逐关验证
# quest→field→zone→boss/zako 全可解析),漏发会在那里就被拦住,轮不到这里。
# 角色包 claims 检查不受影响(没有任何角色包 claim 过 mod_rogue_* 键)。
EPHEMERAL_KEY_PREFIXES = ("mod_rogue_",)


def _is_ephemeral(key: str) -> bool:
    return str(key).startswith(EPHEMERAL_KEY_PREFIXES)


def _vkey(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def chain_latest_index() -> dict[str, tuple[str, Path, str]]:
    """store 相对路径 -> (落点版本, zip 路径, zip 内条目名);按版本序后来居上。"""
    index: dict[str, tuple[str, Path, str]] = {}
    edges = []
    for path in CDN_COMMON_DIFF.glob("*.zip"):
        matched = _EDGE.match(path.name)
        if matched:
            edges.append(((_vkey(matched.group(2)), int(matched.group(3))),
                          matched.group(2), path))
    for _, to_version, path in sorted(edges, key=lambda item: item[0]):
        try:
            names = zipfile.ZipFile(path).namelist()
        except Exception:
            continue
        for name in names:
            index[name.replace("production/upload/", "")] = (to_version, path, name)
    for path in sorted(CDN_COMMON_FULL.glob("*.zip")):
        try:
            names = zipfile.ZipFile(path).namelist()
        except Exception:
            continue
        for name in names:
            index.setdefault(name.replace("production/upload/", ""),
                             ("full基包", path, name))
    return index


def _keys_of(blob: bytes) -> list[str] | None:
    """orderedmap 的键索引;不是 orderedmap 就返回 None。"""
    try:
        return list(core.parse_index(blob)[0])
    except Exception:
        return None


def _rows_of(blob: bytes) -> dict[str, bytes] | None:
    """orderedmap 的 {键: 解压后的整行字节};不是 orderedmap 就返回 None。

    索引里的 row_offset 是该行的**结束**位置,row_i = data[offset_{i-1}:offset_i]
    (见 core.read_orderedmap_file 的注释,曾有版本误当起始位置用而全表错位一格)。
    这里不解 CSV,只比字节 + 数行数,所以与行编解码器无关。"""
    try:
        keys, pairs, index_len = core.parse_index(blob)
    except Exception:
        return None
    data = blob[4 + index_len:]
    out: dict[str, bytes] = {}
    prev = 0
    for key, (_, row_end) in zip(keys, pairs):
        chunk = data[prev:row_end]
        prev = row_end
        if not chunk:
            out[key] = b""
            continue
        try:
            out[key] = zlib.decompress(chunk)
        except zlib.error:
            # 未压缩行的 orderedmap(core.build_orderedmap_raw_rows 造的就是)
            # 直接用原字节;逐块降级,不因为一块解不开就放弃整表。
            out[key] = chunk
    return out


def _row_lines(payload: bytes) -> int | None:
    """一个键里装了几条 CSV 记录(一键多记录是常态,ability 最多 9~10 条)。

    **只对 flat 表有意义**。nested 表(rush_event_quest / general_boss / zone /
    boss_level / general_funnel …)的外层行本身就是一个 orderedmap 二进制块,
    数里面的 \\n 纯属噪声——`rush_event_quest[700099]` 就这样被误报成
    「57→47 条」,而它其实是压缩字节里恰好有多少个 0x0A。
    读不出文本就返回 None,调用方跳过这条判据。"""
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return None
    # CSV 行里不会有控制字符(制表符除外);有就说明这是二进制块。
    if any(ch < " " and ch not in "\t\r\n" for ch in text):
        return None
    return len([ln for ln in text.splitlines() if ln.strip()])


def content_notes(label: str, version: str,
                  old: bytes, new: bytes) -> list[str]:
    """键集合合规**之后**的内容体检。只告警,永不阻断。

    键闸门只比键集合,比不出「键数一个没变、但 409 行内容全换了」。
    实例:1.4.307 直发 store 原字节的 ability_soul,451 键里 409 个键的内容变了,
    把 1.4.164 以来在线的整套官方魂珠增强一次性回退(5085000 由 8 行掉到 6 行、
    kind 468 Guts 强度 227273→100000 …),而键数 451→451,闸门必然放行。
    对照:1.4.164→1.4.301 只动了 15 个键(15 把深渊武器)——这才是正常改动的形状。

    两条判据:
      ① 改动面过大(既看绝对数也看占比,避免小表误报)
      ② **键内行数变少** —— 一键多记录的表里,行没了和键没了是同一类损失,
         而现有闸门对它完全失明。这条噪声低,不设占比门槛。
    """
    old_rows, new_rows = _rows_of(old), _rows_of(new)
    if not old_rows or not new_rows:
        return []
    common = [k for k in old_rows if k in new_rows]
    if not common:
        return []
    changed = [k for k in common if old_rows[k] != new_rows[k]]
    shrunk = []
    for key in changed:
        before, after = _row_lines(old_rows[key]), _row_lines(new_rows[key])
        if before is not None and after is not None and after < before:
            shrunk.append(key)
    notes: list[str] = []
    if changed and len(changed) > 20 and len(changed) / len(common) > 0.25:
        notes.append(
            f"{label}: 相对链上 {version} 有 {len(changed)}/{len(common)} 个键"
            f"内容变了({len(changed) / len(common):.0%})。确认这是你要发的改动面,"
            f"不是把整表换成了另一个来源的版本 -> {changed[:8]}"
            + (" ..." if len(changed) > 8 else ""))
    if shrunk:
        notes.append(
            f"{label}: {len(shrunk)} 个键的**记录条数变少**(一键多记录的表里"
            f"这和丢键是同一类损失) -> "
            + ", ".join(f"{k}({_row_lines(old_rows[k])}→{_row_lines(new_rows[k])}条)"
                        for k in shrunk[:6])
            + (" ..." if len(shrunk) > 6 else ""))
    return notes


def protected_keys() -> dict[str, set[str]]:
    """各角色包 claims 的 (逻辑路径 -> 键集合)。这是「谁的行不许丢」的权威清单。"""
    out: dict[str, set[str]] = {}
    for manifest in sorted(PACKS.glob("*/package/manifest.json")):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            continue
        for table in data.get("tables") or []:
            logical = table.get("logical_path")
            if not logical:
                continue
            out.setdefault(logical, set()).update(str(k) for k in table["outer_keys"])
    return out


def check(entries: list[tuple[str, bytes]], *, verbose: bool = True) -> list[str]:
    """entries: [(store 相对路径, 待发布字节)]。返回问题列表(空 = 通过)。"""
    index = chain_latest_index()
    guarded = protected_keys()
    # 逻辑路径 -> 相对路径,用来把 claims 清单对到具体文件
    logical_by_rel = {}
    for logical in guarded:
        digest = core.sha1_path(logical)
        logical_by_rel[f"{digest[:2]}/{digest[2:]}"] = logical

    problems: list[str] = []
    for relative, payload in entries:
        relative = relative.replace("production/upload/", "")
        logical = logical_by_rel.get(relative)
        label = logical or relative
        if relative not in index:
            if verbose:
                print(f"  [新增] {label} (链上没有,纯新增)")
            continue
        version, zip_path, name = index[relative]
        try:
            old = zipfile.ZipFile(zip_path).read(name)
        except Exception as exc:
            problems.append(f"{label}: 读不出链上版本 {version} ({exc})")
            continue
        if old == payload:
            if verbose:
                print(f"  [不变] {label} (与链上 {version} 逐字节相同)")
            continue

        old_keys, new_keys = _keys_of(old), _keys_of(payload)
        if old_keys is None or new_keys is None:
            if verbose:
                print(f"  [资产] {label} (非 orderedmap,整文件替换链上 {version})")
            continue

        lost_all = [k for k in old_keys if k not in set(new_keys)]
        lost = [k for k in lost_all if not _is_ephemeral(k)]
        ephemeral_lost = [k for k in lost_all if _is_ephemeral(k)]
        added = [k for k in new_keys if k not in set(old_keys)]
        if ephemeral_lost and verbose:
            # 放行但必须留痕:这是"这座塔比上座塔少几个克隆",不是删内容。
            print(f"  [临时] {label} 少了 {len(ephemeral_lost)} 个重摇临时键"
                  f"(整批重建,放行) -> {ephemeral_lost[:6]}"
                  + (" ..." if len(ephemeral_lost) > 6 else ""))
        if lost:
            problems.append(
                f"{label}: 相对链上 {version} 丢了 {len(lost)} 个键 -> {lost[:12]}"
                + (" ..." if len(lost) > 12 else ""))
        elif verbose:
            print(f"  [表  ] {label} 链上{version} {len(old_keys)}键 -> {len(new_keys)}键"
                  f"{(',新增 ' + str(added[:6])) if added else ''}")

        # 内容体检:键集合合规不代表内容没被整表换掉。只告警,不进 problems。
        if verbose:
            for note in content_notes(label, version, old, payload):
                # 字样必须是 GBK 可编码的:这段会被 wf_publish 的发布预检子进程
                # 打印,那里的 stdout 是 Windows 活动代码页(cp936)。
                # 曾用「⚠」(U+26A0)导致 `'gbk' codec can't encode` 直接中止发布。
                print(f"  [内容告警] {note}")

        # 角色包 claims 的行必须还在(链上已有的前提下)
        must = guarded.get(logical or "", set()) & set(old_keys)
        gone = sorted(must - set(new_keys))
        if gone:
            problems.append(f"{label}: **角色包 claims 的行不见了** -> {gone}")
    return problems


def _pending_relatives() -> list[str]:
    pending = TOOL_DIR / "work" / "sync_pending.json"
    if not pending.is_file():
        return []
    return [str(x) for x in json.loads(pending.read_text(encoding="utf-8"))
            if not str(x).startswith(("medium:", "android:"))]


def main(argv: list[str] | None = None) -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    import argparse
    import wf_gui

    parser = argparse.ArgumentParser(description="发布前的键不许消失闸门")
    parser.add_argument("--tables", help="逗号分隔的表别名/逻辑路径(默认用 pending 列表)")
    args = parser.parse_args(argv)

    store = wf_gui.TARGET_STORE
    if args.tables:
        import wf_publish
        relatives = [wf_publish._relative_for_logical(x)
                     for x in wf_publish._explicit_logicals(args.tables)]
    else:
        relatives = _pending_relatives()
    if not relatives:
        print("没有待检查的文件(pending 为空且未指定 --tables)")
        return 0

    entries = []
    for relative in relatives:
        path = store / relative
        if path.is_file():
            entries.append((relative, path.read_bytes()))
        else:
            print(f"  [跳过] {relative} (本地不存在)")
    print(f"检查 {len(entries)} 个文件:")
    problems = check(entries)
    if problems:
        print("\n[阻断] 发布会删掉线上已有的键:")
        for problem in problems:
            print("  !! " + problem)
        return 1
    print("\n[OK] 链上已有的键一个没少。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
