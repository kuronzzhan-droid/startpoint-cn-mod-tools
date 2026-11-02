"""Opening desk: local/175 snapshot checklists only; no deployment operations."""
from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone

from wf.paths import REPOSITORY, profile_data

from .drafts import DraftError
from .opening_caps import client_capabilities
from .opening_chain import check, compare_manifest, source_edges, verify_archives
from .rehearsal_io import read_json, server_root

TARGETS = {"local": "本地服（本机目录）", "test175": "175（只读本机快照）"}
ROLLBACK = "客户端资源版本只往前走。发现问题后保留当前链，制作从当前链尾到更高版本的修正边，重新检查和预演；不得降 cdn_version、删除已分发边或把旧资源覆盖回去。服务端独立恢复步骤须另行核对并授权。"


def opening_plan(source, *, server="local", client_profile=None):
    if server not in TARGETS:
        raise DraftError("开服台只接受 local 或 test175；不提供正式服目标")
    if client_profile is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", client_profile):
        raise DraftError("客户端档案名称无效")
    config_error = False
    try:
        config, _ = profile_data()
    except (OSError, ValueError, TypeError):
        config, config_error = {}, True
    servers = config.get("servers", {})
    servers = servers if isinstance(servers, dict) else {}
    configured = lambda name: isinstance(servers.get(name), dict) and bool(servers[name].get("root"))
    view = source.view
    result = {"schema": "wf-studio-opening/1", "createdAt": datetime.now(timezone.utc).isoformat(),
              "server": server, "targets": [{"id": name, "label": label, "configured": configured(name)}
                                              for name, label in TARGETS.items()],
              "readOnly": True, "runtime": "未执行", "ok": False, "status": "pending",
              "source": {"version": source.version, "baseVersion": getattr(view, "base_version", None),
                         "view": getattr(view, "view_name", None), "edgeCount": 0},
              "target": {"version": None, "manifestSha256": None, "configured": configured(server)},
              "missingEdges": [], "checks": [], "rollback": ROLLBACK,
              "entryLinks": [{"id": "rehearsal", "label": "只读预演说明", "href": "/api/studio/opening/docs/rehearsal"},
                             {"id": "apply-local", "label": "本地应用入口说明（本页不执行）", "href": "/api/studio/opening/docs/apply-local"},
                             {"id": "deliveries", "label": "打开场景 BOSS 交付页", "href": "#/content/boss/q/scene-spec/delivery"},
                             {"id": "patches", "label": "查看补丁管理", "href": "#/patches"},
                             {"id": "doctor", "label": "编辑台只读体检", "href": "/api/studio/doctor"}],
              "note": "只读取当前已加载视图及本机配置快照，未连接目标服；清单不是部署授权、远端实时状态或设备验收。"}
    edges, paths = [], {}
    if config_error:
        result["checks"].append(check("profile", "问题", "本机路径配置无法读取；请检查 profiles/local.json 或 WF_PATHS_PROFILE", blocking=True))
    try:
        edges, paths = source_edges(source)
        result["source"]["edgeCount"] = len(edges)
        result["checks"].append(check("source-chain", "满足", "已加载视图资源链连续，归档摘要来自启动校验"))
    except DraftError as exc:
        result["checks"].append(check("source-chain", "问题", str(exc), blocking=True))
    except (OSError, ValueError, TypeError, KeyError):
        result["checks"].append(check("source-chain", "问题", "当前视图资源链或归档证据不完整；请检查命名视图并重启", blocking=True))
    try:
        if not configured(server):
            raise DraftError("未配置目标本机快照")
        for raw in (servers[server]["root"], os.environ.get("WF_ROOT", config.get("wf_root", ""))):
            if not isinstance(raw, str):
                raise DraftError("目标必须是本机快照目录")
            expanded = os.path.expandvars(raw)
            if expanded.startswith(("\\\\", "//")) or "://" in expanded:
                raise DraftError("目标必须是本机快照目录")
        root = server_root(server)
        if str(root).startswith(("\\\\", "//")):
            raise DraftError("不读取网络共享目标")
        filename = root / "assets/asset-patch/manifest.json"
        before = filename.read_bytes()
        manifest = read_json(filename)
        if before != filename.read_bytes():
            raise DraftError("目标快照读取期间发生变化")
        result["target"]["manifestSha256"] = hashlib.sha256(before).hexdigest()
        tail, missing, checks = compare_manifest(edges, manifest, result["source"]["baseVersion"])
        result["target"]["version"] = tail
        result["checks"].extend(checks)
        verify_archives(missing, paths)
        result["missingEdges"] = [{"from": edge["from"], "to": edge["to"], "archives": edge["archives"],
                                    "localTestOnly": edge["localTestOnly"]} for edge in missing]
        if server == "test175" and any(edge["localTestOnly"] for edge in missing):
            result["checks"].append(check("local-test-only", "问题", "待补边含 local_test_only 标记；不可直接推 175", blocking=True))
    except (OSError, ValueError, TypeError, KeyError, DraftError):
        result["checks"].append(check("target-inputs", "问题", "目标本机 manifest 未配置、不可读或链/归档校验失败；检查 profiles/local.json 中对应快照", blocking=True))
    result["clientCapabilities"] = client_capabilities(edges, paths, client_profile)
    caps = result["clientCapabilities"]
    result["checks"].append(check("client-match", "满足" if caps["status"] == "matched" else
        "问题" if caps["status"] == "mismatch" else "待验证",
        "资源依赖与客户端 provides 匹配" if caps["status"] == "matched" else
        "资源依赖与客户端 provides 不匹配" if caps["status"] == "mismatch" else "客户端依赖覆盖或方法证据待验证",
        blocking=caps["status"] == "mismatch" or not caps["available"]))
    blocked = any(item["blocking"] for item in result["checks"])
    pending = any(item["status"] == "待验证" for item in result["checks"])
    result["status"] = "blocked" if blocked else "pending" if pending else "ready"
    result["ok"] = result["status"] == "ready"
    result["manualSteps"] = [
        "先消除清单中的问题项并补齐待验证证据；重新取得目标本机快照，核对 manifest SHA-256 和实际链尾。",
        "按列出的依赖顺序准备每条缺失边，核对 ZIP 名称、大小、SHA-256；不要覆盖同名不同内容。",
        "在交付页检查 check、key-diff、requires/provides 和只读 rehearsal；local_test_only 候选不可直接推 175。",
        "取得当次目标和交付的明确授权后，由操作者另行备份与执行；本页不会复制归档、合并服务端表、写 manifest 或重启。",
        "服务端 JSON/代码是否需要重启，以该交付 rehearsal 结果为准；本页未执行设备或联机验收。",
        ROLLBACK,
    ]
    return result


class OpeningRoutes:
    def __init__(self, app):
        self.app = app

    def routes(self):
        return [("GET", re.compile(r"^/api/studio/opening$"), self.preview),
                ("GET", re.compile(r"^/api/studio/opening/docs/(?P<document>rehearsal|apply-local)$"), self.document)]

    def preview(self, query):
        from .server import json_response
        if set(query) - {"server", "clientProfile"} or any(len(values) != 1 for values in query.values()):
            raise DraftError("开服台只接受单个 server 和 clientProfile 参数")
        return json_response(opening_plan(self.app.source, server=query.get("server", ["local"])[0],
                                         client_profile=query.get("clientProfile", [None])[0]))

    def document(self, query, document):
        from .server import Response
        if query or document not in {"rehearsal", "apply-local"}:
            raise DraftError("无效文档请求")
        return Response(200, (REPOSITORY / "docs/studio" / (document + ".md")).read_bytes(),
                        "text/plain; charset=utf-8")
