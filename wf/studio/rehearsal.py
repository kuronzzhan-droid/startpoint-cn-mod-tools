"""Offline delivery rehearsal. Server paths are inputs only; no deployment API."""
from __future__ import annotations

import zipfile
from datetime import datetime, timezone

from wf.view.chain import version

from .drafts import DraftError
from .rehearsal_inputs import digest, inspect_archives, load_inputs
from .rehearsal_io import (apply_enabled, configured_server, delivery_folder, inside, json_bytes,
                           read_json, save_reports, server_name, server_root)
from .rehearsal_server import chain_tail, server_preview


def _check(result, rule, passed, message):
    result["checks"].append({"rule": "rehearsal." + rule, "status": "满足" if passed else "问题",
                             "blocking": not passed, "message": message})


def rehearse(delivery_dir, server="local", *, zips=None, write=True):
    """Accept a build root or delivery directory; ZIP lists are optional overrides.

    write=False supports a fully read-only inspection of archived deliveries.
    Paths come solely from machine configuration, never an HTTP request root.
    """
    server_name(server)
    folder = delivery_folder(delivery_dir)
    result = {"schema": "wf-studio-rehearsal/1", "server": server, "ok": False,
              "status": "blocked", "createdAt": datetime.now(timezone.utc).isoformat(),
              "serverReadOnly": True, "deliveryDir": str(folder), "serverRoot": None,
              "currentVersion": None, "from": None, "to": None, "checks": [],
              "manifestEntry": None, "manifestEntryJson": None, "archives": [],
              "serverChanges": [], "restartRequired": None, "restartReason": "输入尚未完整检查",
              "manifestFormat": {"encoding": "UTF-8", "bom": False, "newline": "CRLF", "indent": 2},
              "manualSteps": [], "serverSnapshot": {}, "runtime": "未执行"}
    root = None
    try:
        root = server_root(server)
        result["serverRoot"] = str(root)
        manifest_path = inside(root, "assets/asset-patch/manifest.json")
        manifest_hash = digest(manifest_path)
        result["serverSnapshot"]["assets/asset-patch/manifest.json"] = manifest_hash
        manifest = read_json(manifest_path)
        tail = chain_tail(manifest)
        result["currentVersion"] = tail
        active = inside(root, "assets/asset-patch/active")
        if not active.is_dir():
            raise DraftError("服务端 active 目录不存在")
        paths, start, end, entry, metadata = load_inputs(folder, zips)
        result.update({"from": start, "to": end})
        _check(result, "from", start == tail, f"交付 from={start}；当前启用链尾={tail}")
        _check(result, "to", version(end) > version(tail) and version(end) > version(start),
               f"交付 to={end} 必须高于链尾及 from")
        records = inspect_archives(paths, metadata)
        local_only = any("local_test_only" in d for d in [*metadata, *records])
        _check(result, "local-test-only", not local_only or apply_enabled(server),
               ("可应用到本地服，不可直接推 175；仅 apply_enabled=true 的目标允许本地候选；原交付保持不变"
                if local_only and apply_enabled(server) else
                "共用条目禁止携带 local_test_only（包括 false）；原交付保持不变"))
        result["archives"] = records
        _check(result, "archives", True, "分包版本、命名、连续序号、ZIP CRC 与摘要已核对")
        for record in records:
            dest = inside(active, record["name"])
            current = digest(dest) if dest.is_file() else None
            result["serverSnapshot"]["assets/asset-patch/active/" + record["name"]] = current
            _check(result, "active-collision", current is None or current == record["sha256"],
                   record["name"] + ("：active 无同名文件" if current is None else "：比较 active 同名文件 SHA-256"))
        portable = {"id": entry.get("id") or metadata[0].get("id") or f"rehearsal-{end}", "type": "patch",
                    "name": entry.get("name") or metadata[0].get("name") or f"资源补丁 {start} → {end}", "version": end,
                    "depends_on": start, "enabled": True, "archive": records[0]["name"],
                    "archive_size": records[0]["size"], "chain": [r["name"] for r in records],
                    "files": sorted(n for r in records for n in r["files"]),
                    "archive_integrity": [{k: v for k, v in r.items() if k != "local_test_only"} for r in records],
                    "created_at": entry.get("created_at", result["createdAt"][:10])}
        _check(result, "manifest-identity", not any(
            e.get("id") == portable["id"] or e.get("version") == end for e in manifest["patches"]),
            "追加条目的 id 与 version 不得已存在（包含停用条目）")
        result.update(manifestEntry=portable, manifestEntryJson=json_bytes(portable).decode("utf-8"))
        changes, snapshots = server_preview(folder, root)
        result["serverChanges"] = changes
        result["serverSnapshot"].update(snapshots)
        for item in changes:
            if item.get("existingClaimedKeys"):
                _check(result, "server-collision", False,
                       item["target"] + "：声明新增的键已经存在：" + str(item["existingClaimedKeys"]))
            if item["baselineMatches"] is not None:
                _check(result, "server-baseline", item["baselineMatches"],
                       item["target"] + "：核对交付 before_sha256，漂移需重新基于当前数据生成")
        # A candidate containing JSON/code requires restart even if its keys already match.
        result["restartRequired"] = bool(changes)
        result["restartReason"] = "包含服务端 JSON/代码，手工合入后需重启" if changes else "只有客户端资源，manifest 热加载，无需重启"
        for relative, expected in result["serverSnapshot"].items():
            current = inside(root, relative)
            actual = digest(current) if current.is_file() else None
            if actual != expected:
                raise DraftError(f"预演期间服务端输入变化：{relative}")
        _check(result, "snapshot", True, "实际读取的服务端文件在预演前后 SHA-256 不变；未读取数据库")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, zipfile.BadZipFile, RuntimeError) as exc:
        _check(result, "inputs", False, f"预演输入检查失败：{exc}")
    result["ok"] = bool(result["checks"]) and not any(c["blocking"] for c in result["checks"])
    result["status"] = "ready" if result["ok"] else "blocked"
    if not result["ok"]:
        result.update(manifestEntry=None, manifestEntryJson=None)
    result["manualSteps"] = manual_steps(result)
    if write:
        # Invalid/unconfigured roots may produce a blocked report; configured roots remain protected.
        try:
            save_reports(folder, result, markdown(result), root or folder / "__unconfigured_server__")
        except OSError as exc:
            raise DraftError(f"预演报告写入失败：{exc}") from exc
    return result


def manual_steps(result):
    root = result["serverRoot"] or "<未配置服务端目录>"
    local_only = any(c["rule"] == "rehearsal.local-test-only" and "不可直接推 175" in c["message"]
                     for c in result["checks"])
    return [
        "先确认本报告 status=ready；blocked 时停止，修复问题并重新预演。",
        f"重新读取 {root}/assets/asset-patch/manifest.json，确认启用链尾 {result['currentVersion']} 与交付 from={result['from']} 一致，并复核报告中的输入摘要。",
        f"手工备份 manifest 和本次服务端目标文件；将同一批 ZIP 放入 {root}/assets/asset-patch/active/，逐个核对 size/SHA-256，同名不同内容必须停止。",
        f"有 serverChanges 时，按 addedKeys/replacedKeys 将候选键合入 {root} 下对应目标；保留 omittedKeys，数组逐项核对，禁止整文件覆盖。",
        f"在 {root}/assets/asset-patch/manifest.json 的 patches 末尾追加本报告 manifestEntryJson，同步 cdn_version=to；保存 UTF-8 无 BOM、CRLF、2 空格缩进及结尾换行。",
        result["restartReason"] + "；需要重启时由操作者按本机既有流程停启主进程和联机子进程，预演不会执行。",
        "手工核对启用链、ZIP 摘要与 get_path；由操作者完成设备验证，预演结果不代表游戏通过。",
        ("本交付为本地候选：可应用到本地服，不可直接推 175；正式发布需独立验收与授权。" if local_only else
         "本地验证后，向测试服 175 复制同一批 ZIP、追加完全相同的 manifestEntryJson，并按相同键变更合入服务端；先核对测试服链尾，保持同一版本号。"),
    ]


def markdown(result):
    lines = ["# 交付前只读预演", "", f"结果：{'通过' if result['ok'] else '阻断'}；目标：{result['server']}；时间：{result['createdAt']}",
             f"版本：{result['from']} → {result['to']}；启用链尾：{result['currentVersion']}",
             "服务端只读；未部署、未停启服务、未读写数据库、未操作模拟器。", "", "## 检查", ""]
    lines.extend(f"- {c['status']} · {c['rule']}：{c['message']}" for c in result["checks"])
    lines.extend(["", "## 服务端键级预览", "", result["restartReason"], ""])
    for item in result["serverChanges"]:
        lines.extend([f"### {item['target']}", "", f"整文件覆盖风险：{item['wholeFileOverwriteRisk']}",
                      f"新增键：{item['addedKeys']}", f"替换键：{item['replacedKeys']}",
                      f"已存在同值键：{item.get('unchangedKeys', [])}",
                      f"待追加列表值：{item.get('appendValues', [])}；必须保留列表值：{item.get('omittedValues', [])}",
                      f"候选未包含、必须保留的旧键：{item['omittedKeys']}", ""])
    lines.extend(["## 手工上边清单", ""])
    lines.extend(f"{i}. {step}" for i, step in enumerate(result["manualSteps"], 1))
    lines.extend(["", "## manifest 条目候选（适用范围见检查结果）", "",
                  "仅 status=ready 且人工复核通过后可使用；blocked 时禁止追加。", "", "```json",
                  result["manifestEntryJson"] or "null", "```", ""])
    return "\n".join(lines)


def auto_rehearse(directory):
    name = configured_server()
    return rehearse(directory, name) if name is not None else None
