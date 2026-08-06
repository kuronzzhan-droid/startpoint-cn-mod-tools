#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WF mod 发布器:把改动的数据表打成客户端增量包(diff zip),经服务端 CDN 下发。

原理(与官方增量更新同构):
  客户端 POST /get_path 报当前 res_ver → 服务端返回 archive-*-diff 里的
  pinball-<from>-<to>-N-<tag>.zip 列表 → 客户端下载高于自己版本的包,
  解包 production/upload/<xx>/<hash> 覆盖本地 → res_ver 升级。
  因此:把改好的表按同样结构打包、版本号 +0.0.1,客户端重启即自动拉取。
  (服务端 buildDiffList 每次请求动态扫描,放入 zip 即生效,无需重启服务端。)

用法:
  python mod-tools/wf_publish.py                 # 发布 pending 列表里的文件
  python mod-tools/wf_publish.py --tables ability,character_status
  python mod-tools/wf_publish.py --list          # 只看将发布什么/版本推进
注意:CN 表含觉醒列(col3/4 awake_kind),打包为原样字节复制,不做重编码。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wf_mod_tool as core  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# CDN 发布根:WF_CDN_DIR 显式优先(原样使用);否则走 core 四级解析链
# (profile.cdn_dir > 服务端识别 > 嵌套遗留 <repo>/.cdn/cn),见 T2 两仓独立。
CDN_ROOT = (
    Path(os.environ["WF_CDN_DIR"]) if os.environ.get("WF_CDN_DIR")
    else core.resolve_cdn_root_lax()
)
CDN_DIFF = CDN_ROOT / "archive-common-diff"
WORK = Path(__file__).resolve().parent / "work"
PENDING = WORK / "sync_pending.json"
CHANGELOG = WORK / "changelog.jsonl"
CHANGELOG_MD = WORK / "changelog.md"


def stamp_changelog(version: str) -> int:
    """把日志里所有未发布(version=None)的条目标记为本次版本,并渲染 changelog.md。"""
    if not CHANGELOG.exists():
        return 0
    entries, n = [], 0
    for line in CHANGELOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("version") is None:
            e["version"] = version
            n += 1
        entries.append(e)
    CHANGELOG.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n", encoding="utf-8")
    md = ["# WF Mod 改动日志", "",
          "| 时间 | 表 | 键 | 改动 | 发布版本 | 备份(回溯用) |",
          "|---|---|---|---|---|---|"]
    for e in reversed(entries):
        keys = ",".join(e.get("keys") or []) or "-"
        summ = (e.get("summary") or "").replace("\n", " / ").replace("|", "/")
        bak = Path(e["backup"]).name if e.get("backup") else "-"
        md.append(f"| {e.get('ts','')} | {e.get('table','')} | {keys} | {summ} | {e.get('version') or '(未发布)'} | {bak} |")
    CHANGELOG_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    return n

TABLE_ALIASES = {
    "ability": core.ABILITY_LOGICAL,
    "character": core.CHARACTER_LOGICAL,
    "character_status": core.STATUS_LOGICAL,
    "leader_ability": "master/ability/leader_ability.orderedmap",
    "ability_soul": "master/ability/ability_soul.orderedmap",
    "character_awake_status": "master/character/character_awake_status.orderedmap",
    "action_skill": "master/skill/action_skill.orderedmap",
    "power_flip_action": "master/skill/power_flip_action.orderedmap",
    "weapon_ability": "master/equipment_enhancement/equipment_enhancement_ability.orderedmap",
    "character_text": "master/character/character_text.orderedmap",
    "character_speech": "master/character/character_speech.orderedmap",
    "skill_preview_character": "master/skill_preview/skill_preview_character.orderedmap",
    "mana_board2_open_condition": "master/mana_board/mana_board2_open_condition.orderedmap",
    "upskill": "master/mana_board/upskill.orderedmap",
    "character_stance_detail": "master/stance_detail/character_stance_detail.orderedmap",
    "character_image": "master/generated/character_image.orderedmap",
    "full_shot_image_attribute": "master/character/full_shot_image_attribute.orderedmap",
    "mana_board": "master/generated/mana_board.orderedmap",
    "mana_node": "master/mana_board/mana_node.orderedmap",
    "character_gacha_sound": "master/character/character_gacha_sound.orderedmap",
    # --- 特殊效果(固有状态)+ 商店 ---
    "unique_condition": "master/character/unique_condition.orderedmap",
    "custom_ability_string": "master/string/custom_ability_string.orderedmap",
    "boss_coin_shop": "master/shop/boss_coin_shop.orderedmap",
    "boss_coin_shop_category": "master/shop/boss_coin_shop_category.orderedmap",
    "trimmed_image": "master/generated/trimmed_image.orderedmap",
    # --- boss 战 / 副本 / 连战(roguelike boss rush 方案用,见 docs/boss连战roguelike方案.md) ---
    "general_boss": "master/battle/boss/general_boss.orderedmap",
    "general_boss_state": "master/battle/boss/general_boss_state.orderedmap",
    "general_boss_variable": "master/battle/boss/general_boss_variable.orderedmap",
    "boss_level": "master/battle/boss/boss_level.orderedmap",
    "standard_boss": "master/battle/boss/standard_boss.orderedmap",
    "general_zako": "master/battle/zako/general_zako.orderedmap",
    "zako_level": "master/battle/zako/zako_level.orderedmap",
    "zone": "master/battle/zone.orderedmap",
    "field_data": "master/battle/field_data.orderedmap",
    "field": "master/battle/field.orderedmap",
    "boss_battle_quest": "master/quest/boss_battle_quest.orderedmap",
    "boss_battle_stage_node": "master/quest/boss_battle_stage_node.orderedmap",
    "rush_event": "master/quest/event/rush_event.orderedmap",
    "rush_event_quest": "master/quest/event/rush_event_quest.orderedmap",
    "rush_event_quest_folder": "master/quest/event/rush_event_quest_folder.orderedmap",
    "rush_event_correction": "master/quest/event/rush_event_battle_quest_correction.orderedmap",
    "event_list": "master/quest/event/event_list.orderedmap",
    "floor": "master/battle/floor.orderedmap",
    "challenge_dungeon_event": "master/quest/event/challenge_dungeon_event.orderedmap",
    "challenge_dungeon_event_quest": "master/quest/event/challenge_dungeon_event_quest.orderedmap",
    "tower_dungeon_event": "master/quest/event/tower_dungeon_event.orderedmap",
    "tower_dungeon_event_quest": "master/quest/event/tower_dungeon_event_quest.orderedmap",
    "switched_action_skill": "master/skill/switched_action_skill.orderedmap",
    # --- EX Boost(EX词条效果/EX强化数值/EX素材定义) ---
    "ex_ability": "master/ex_boost/ex_ability.orderedmap",
    "ex_status": "master/ex_boost/ex_status.orderedmap",
    "ex_boost": "master/ex_boost/ex_boost.orderedmap",
}

VER_RE = re.compile(r"pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-\d+-")


def current_max_version(default: str = "1.4.54") -> str:
    # 三个 diff 目录都要扫:medium:/android: 分包发布也会推进版本号,
    # 只看 common 会把已存在的目标版本再发一遍(客户端已在该版本则不再拉取)。
    best = default
    for sub in ("archive-common-diff", "archive-medium-diff", "archive-android-diff"):
        for f in (CDN_ROOT / sub).glob("*.zip"):
            m = VER_RE.match(f.name)
            if m and _cmp(m.group(2), best) > 0:
                best = m.group(2)
    # 上游服务端(2026-07 起)另有 assets/asset-patch 补丁机制:getEffectiveVersion()
    # 取 max(CDN, 启用的 patch 版本)。若某启用 patch 版本高于 CDN,我们不越过它,
    # 客户端 res_ver 会停在 patch 版,新发的低版本 diff 拉取不到 —— 一并纳入 max。
    # 路径按服务端仓解析(T2 两仓独立;嵌套布局下与旧 ROOT 相同)。
    manifest = core.resolve_server_dir() / "assets" / "asset-patch" / "manifest.json"
    try:
        for p in json.loads(manifest.read_text(encoding="utf-8")).get("patches", []):
            v = str(p.get("version", ""))
            if p.get("enabled") and re.fullmatch(r"\d+\.\d+\.\d+", v) and _cmp(v, best) > 0:
                best = v
    except Exception:
        pass
    return best


def _cmp(a: str, b: str) -> int:
    av = [int(x) for x in a.split(".")]
    bv = [int(x) for x in b.split(".")]
    for x, y in zip(av, bv):
        if x != y:
            return x - y
    return 0


def bump(v: str) -> str:
    p = v.split(".")
    return f"{p[0]}.{p[1]}.{int(p[2]) + 1}"


def collect_files(args) -> list[str]:
    """返回相对 upload 的 'xx/hash' 列表。"""
    rels: list[str] = []
    if args.tables:
        for t in args.tables.split(","):
            t = t.strip()
            logical = TABLE_ALIASES.get(t, t)
            digest = core.sha1_path(logical)
            rels.append(f"{digest[:2]}/{digest[2:]}")
    else:
        try:
            rels = json.loads(PENDING.read_text(encoding="utf-8"))
        except Exception:
            rels = []
    return rels


@dataclass(frozen=True)
class PreparedFile:
    archive_name: str
    payload: bytes
    prefix: str


def _explicit_logicals(tables: str) -> list[str]:
    logicals = [
        TABLE_ALIASES.get(value.strip(), value.strip())
        for value in tables.split(",")
        if value.strip()
    ]
    if not logicals:
        raise ValueError("--tables is empty")
    return logicals


def _relative_for_logical(logical: str) -> str:
    digest = core.sha1_path(logical)
    return f"{digest[:2]}/{digest[2:]}"


def _load_snapshot(
    path: Path,
    logicals: list[str],
    store: Path,
    profile_id: str | None,
) -> dict[str, dict[str, object]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"snapshot cannot be read: {type(exc).__name__}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("snapshot root must be an object")
    if set(data) != {"schema_version", "profile_id", "store", "entries"}:
        raise ValueError("snapshot root has an invalid shape")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ValueError("snapshot schema_version must be integer 1")
    snapshot_profile_id = data.get("profile_id")
    if not isinstance(snapshot_profile_id, str) or snapshot_profile_id != profile_id:
        raise ValueError(
            "snapshot profile mismatch: "
            f"expected={profile_id!r}, actual={snapshot_profile_id!r}"
        )
    snapshot_store = data.get("store")
    if not isinstance(snapshot_store, str):
        raise ValueError("snapshot store must be a path string")
    if Path(snapshot_store).resolve() != store.resolve():
        raise ValueError(
            f"snapshot store mismatch: expected={store.resolve()}, actual={snapshot_store}"
        )
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise ValueError("snapshot entries must be an array")
    if len(set(logicals)) != len(logicals):
        raise ValueError("snapshot --tables allowlist contains duplicates")
    if len(entries) != len(logicals):
        raise ValueError(
            f"snapshot allowlist length mismatch: expected={len(logicals)}, "
            f"actual={len(entries)}"
        )

    expected_keys = {"logical", "relative", "sha256", "size"}
    records: dict[str, dict[str, object]] = {}
    for index, (logical, entry) in enumerate(zip(logicals, entries)):
        if not isinstance(entry, dict) or set(entry) != expected_keys:
            raise ValueError(f"snapshot entry[{index}] has an invalid shape")
        if entry.get("logical") != logical:
            raise ValueError(
                f"snapshot allowlist order mismatch at {index}: "
                f"expected={logical!r}, actual={entry.get('logical')!r}"
            )
        relative = _relative_for_logical(logical)
        if entry.get("relative") != relative:
            raise ValueError(
                f"snapshot relative mismatch for {logical}: "
                f"expected={relative!r}, actual={entry.get('relative')!r}"
            )
        digest = entry.get("sha256")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError(f"snapshot sha256 is invalid for {logical}")
        size = entry.get("size")
        if type(size) is not int or size < 0:
            raise ValueError(f"snapshot size is invalid for {logical}")
        records[relative] = entry
    return records


def _prepare_files(
    rels: list[str],
    store: Path,
    *,
    strict_explicit: bool,
    snapshot_records: dict[str, dict[str, object]] | None,
) -> tuple[list[PreparedFile], list[str]]:
    group_defs = {
        "": (store, "production/upload"),
        "medium:": (store.parent / "medium_upload", "production/medium_upload"),
        "android:": (store.parent / "android_upload", "production/android_upload"),
    }
    prepared: list[PreparedFile] = []
    skipped: list[str] = []
    for rel in rels:
        prefix = next(
            (value for value in ("medium:", "android:") if rel.startswith(value)),
            "",
        )
        relative = rel[len(prefix):]
        source_root, archive_root = group_defs[prefix]
        source = source_root / relative
        if not source.is_file():
            if strict_explicit:
                raise FileNotFoundError(f"missing explicit publish entry: {rel}")
            skipped.append(rel)
            continue
        payload = source.read_bytes()
        if snapshot_records is not None:
            if prefix:
                raise ValueError("snapshot entries may only target production/upload")
            record = snapshot_records.get(relative)
            if record is None:
                raise ValueError(f"snapshot has no record for {relative}")
            actual_digest = hashlib.sha256(payload).hexdigest()
            if len(payload) != record["size"] or actual_digest != record["sha256"]:
                raise ValueError(
                    f"snapshot bytes mismatch for {relative}: "
                    f"expected size={record['size']} sha256={record['sha256']}, "
                    f"actual size={len(payload)} sha256={actual_digest}"
                )
        prepared.append(
            PreparedFile(
                archive_name=f"{archive_root}/{relative}",
                payload=payload,
                prefix=prefix,
            )
        )
    return prepared, skipped


def _build_archives(
    prepared: list[PreparedFile],
    from_ver: str,
    to_ver: str,
    *,
    layer_placeholders: bool = True,
) -> list[Path]:
    outdirs = {
        "": CDN_DIFF,
        "medium:": CDN_ROOT / "archive-medium-diff",
        "android:": CDN_ROOT / "archive-android-diff",
    }
    # dev content:sync 的扫描器只认纯 hex 后缀(pinball-<from>-<to>-<n>-<hex>.zip),
    # 旧 "mod%m%d%H%M" 带字母 m/o/d 会被 dev 硬拒;%m%d%H%M 全数字即合法 hex。
    # 同分钟重发同边=同名,走既有的备份+原子替换路径,语义为幂等覆盖。
    tag = time.strftime("%m%d%H%M")
    staged: list[tuple[Path, Path]] = []
    backups: list[tuple[Path, Path]] = []
    published: list[Path] = []
    try:
        for prefix, outdir in outdirs.items():
            files = [entry for entry in prepared if entry.prefix == prefix]
            if not files and not layer_placeholders:
                continue
            outdir.mkdir(parents=True, exist_ok=True)
            final = outdir / f"pinball-{from_ver}-{to_ver}-1-{tag}.zip"
            handle, temporary_name = tempfile.mkstemp(
                prefix=f".{final.name}.", suffix=".tmp", dir=outdir
            )
            os.close(handle)
            temporary = Path(temporary_name)
            staged.append((temporary, final))
            if files:
                with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
                    for entry in files:
                        archive.writestr(entry.archive_name, entry.payload)
            else:
                # dev catalog 要求每条边 common/quality/platform 三层齐全;
                # 与官方 diff 同构:无内容层写 1 字节 .empty 占位包(STORED)。
                with zipfile.ZipFile(temporary, "w", zipfile.ZIP_STORED) as archive:
                    archive.writestr(".empty", b"\n")
        for _temporary, final in staged:
            if not final.exists():
                continue
            handle, backup_name = tempfile.mkstemp(
                prefix=f".{final.name}.", suffix=".rollback", dir=final.parent
            )
            os.close(handle)
            backup = Path(backup_name)
            backup.unlink()
            os.replace(final, backup)
            backups.append((backup, final))
        for temporary, final in staged:
            os.replace(temporary, final)
            published.append(final)
        for backup, _final in backups:
            try:
                backup.unlink(missing_ok=True)
            except OSError:
                # Publication is already committed. A leftover hidden backup is
                # safer than entering rollback after earlier backups were removed.
                pass
        return list(published)
    except Exception as exc:
        rollback_errors: list[str] = []
        for final in reversed(published):
            try:
                final.unlink(missing_ok=True)
            except OSError as rollback_exc:
                rollback_errors.append(f"remove {final}: {rollback_exc}")
        for backup, final in reversed(backups):
            try:
                os.replace(backup, final)
            except OSError as rollback_exc:
                rollback_errors.append(f"restore {final}: {rollback_exc}")
        for temporary, _final in staged:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        if rollback_errors:
            raise RuntimeError(
                f"archive publish failed ({exc}); rollback failed: "
                + "; ".join(rollback_errors)
            ) from exc
        raise


def committed_archive_size(output: Path) -> int:
    """已提交产物的字节数;独立成函数供测试注入 stat 失败(仅告警路径)。"""
    return output.stat().st_size


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="WF mod diff 发布器")
    ap.add_argument("--tables", help="逗号分隔的表别名/逻辑路径(默认用 pending 列表)")
    ap.add_argument(
        "--allow-key-deletion",
        action="store_true",
        help="放行「线上已有的键会消失」的发布(默认硬阻断;删角色/删词条时才用)",
    )
    ap.add_argument(
        "--snapshot",
        type=Path,
        help="校验器生成的严格发布快照(必须与 --tables 同时使用)",
    )
    ap.add_argument("--list", action="store_true", help="只显示将发布的内容,不打包")
    ap.add_argument("--from-ver", help="覆盖起始版本(默认=CDN 现有最高版本)")
    ap.add_argument(
        "--no-layer-placeholders", action="store_true",
        help="不为无内容的 medium/android 层补 .empty 占位包(新边将不满足 dev 三层契约)",
    )
    ap.add_argument(
        "--no-dev-catalog", action="store_true",
        help="发布后不重新产出 dev 格式 catalog/EntityLists(启动前编译路径的输入)",
    )
    args = ap.parse_args(argv)

    try:
        if args.snapshot is not None and not args.tables:
            raise ValueError("--snapshot must be used with --tables")
        profile = core.resolve_profile()
        # 标准链:WF_TARGET_STORE > profiles.json 激活档案 > 自动探测。
        # (旧版只读 profiles.json,CHECKLIST 里"纯环境变量"的用法必报未找到 store。)
        store_value = core.resolve_active_store(ROOT, profile=profile)
        if not store_value:
            raise ValueError("未找到数据包 store。" + core.TARGET_STORE_HINT)
        store = Path(store_value).resolve()

        logicals = _explicit_logicals(args.tables) if args.tables else None
        rels = (
            [_relative_for_logical(logical) for logical in logicals]
            if logicals is not None
            else collect_files(args)
        )
        if not rels:
            raise ValueError("没有待发布文件(pending 为空且未指定 --tables)")
        snapshot_records = None
        if args.snapshot is not None:
            snapshot_records = _load_snapshot(
                args.snapshot,
                logicals or [],
                store,
                profile.id if profile else None,
            )

        prepared, skipped = _prepare_files(
            rels,
            store,
            strict_explicit=logicals is not None,
            snapshot_records=snapshot_records,
        )
        if not prepared:
            raise ValueError("没有可发布的文件")

        from_ver = args.from_ver or current_max_version()
        to_ver = bump(from_ver)
        print(f"数据源 store : {store}")
        print(f"版本推进     : {from_ver} -> {to_ver}")
        print("将发布文件   :")
        for relative in skipped:
            print(f"  [跳过] {relative} (本地不存在)")
        for entry in prepared:
            print(f"  {entry.archive_name}  ({len(entry.payload)} B)")

        # 键不许消失闸门:投递单位是整个文件,本地这份比线上少键 = 发布即删角色。
        # 历史事故 1.4.278(顶掉基诺维)与杰拉德包(删三个 PF 键)都是漏了这一步。
        print("键闸门     :")
        try:
            import wf_publish_guard

            guard_problems = wf_publish_guard.check(
                [(entry.archive_name, entry.payload) for entry in prepared]
            )
        except Exception as exc:  # 闸门自身出错不该卡住发布,但必须喊出来
            print(f"  [警告] 闸门未能运行({exc!r}),本次发布未经键检查")
            guard_problems = []
        if guard_problems:
            print("  [阻断] 这次发布会删掉线上已有的键:")
            for problem in guard_problems:
                print("    !! " + problem)
            if not args.allow_key_deletion:
                raise ValueError(
                    "发布被键闸门阻断(线上已有的键会消失)。"
                    "确认这就是你要的效果,再加 --allow-key-deletion 重跑。"
                )
            print("  [放行] --allow-key-deletion 已指定,明知故犯继续发布。")

        if args.list:
            return 0

        if snapshot_records is not None:
            current_profile = core.resolve_profile()
            current_store_value = core.resolve_active_store(
                ROOT, profile=current_profile
            )
            if (
                current_profile is None
                or profile is None
                or current_profile.id != profile.id
                or not current_store_value
                or Path(current_store_value).resolve() != store
            ):
                raise ValueError(
                    "profile/store changed after snapshot preflight: "
                    f"expected profile={profile.id if profile else None!r} "
                    f"store={store}, actual profile="
                    f"{current_profile.id if current_profile else None!r} "
                    f"store={current_store_value}"
                )

        outputs = _build_archives(
            prepared, from_ver, to_ver,
            layer_placeholders=not args.no_layer_placeholders,
        )
    except Exception as exc:
        print(f"[ERR] publish preflight failed: {exc}", file=sys.stderr)
        return 1

    for output in outputs:
        try:
            size_text = f"{committed_archive_size(output)} B"
        except Exception as exc:
            size_text = "size unavailable"
            print(
                "[WARN] publish committed; archive stat failed for "
                f"{output}: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
        print(
            f"\n[OK] 已发布: {output.parent.name}/{output.name}  "
            f"({size_text})"
        )
    print("客户端重启游戏即会自动下载更新(服务端动态扫描,无需重启)。")
    print(f"提示: .env 的 CN_RES_VERSION 可保持不变(/load 跟随客户端 res_ver)。")

    # 自动公布改动日志:回填版本号 + 把 changelog.md 发到 CDN 目录
    try:
        stamped = stamp_changelog(to_ver)
        if CHANGELOG_MD.exists():
            shutil.copy2(CHANGELOG_MD, CDN_DIFF / "changelog.md")
    except Exception as exc:
        print(
            "[WARN] publish committed; changelog update failed: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
    else:
        print(
            f"改动日志: {stamped} 条标记为 {to_ver},"
            "已公布 changelog.md (work/ + CDN)。"
        )

    # 双路径产出:发布已提交(运行时接收路径生效)后,追加重产 dev 启动前编译
    # 路径的输入(catalog manifest + 合并 EntityLists)。失败仅告警,不回滚发布。
    if not args.no_dev_catalog:
        try:
            import wf_dev_catalog as devcat

            manifest_path, dev_issues, dev_summary = devcat.emit_dev_catalog(
                CDN_ROOT,
                # asset-patch 覆盖层是本仓库相对路径,只在发布目标就是本仓库
                # 默认 CDN 根时纳入;外部 WF_CDN_DIR 部署/测试临时根不适用。
                devcat.ASSET_PATCH_ACTIVE if CDN_ROOT == devcat.CDN_ROOT else None,
                digest_mode="cache",
                allow_issues=True,
            )
            blocking = len(dev_issues)
            print(
                f"dev catalog: {manifest_path}"
                f" (存量问题 {blocking} 项,详见 report.json;新边本身已 dev 合规)"
            )
        except Exception as exc:
            print(
                "[WARN] publish committed; dev catalog emit failed: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )

    # 发布来源=pending 时自动清空(与 GUI run_publish 语义对齐;CLI 直跑曾留残留,
    # 下次发布会把已发文件重复打进 diff——无害但包变大、日志变噪)。
    # 必须留在 main 末尾:所有失败路径都在此之前 return 1,走到这里=发布已提交。
    if not args.tables and PENDING.exists():
        PENDING.write_text("[]", encoding="utf-8")
        print("pending 列表已清空。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
