# -*- coding: utf-8 -*-
"""季节换装七角色：规格驱动角色包构建 CLI。

    python mod-tools/wf_seasonal7_build.py --char regis --step init
    python mod-tools/wf_seasonal7_build.py --char regis --step tables
    python mod-tools/wf_seasonal7_build.py --char regis --step kit        # 调 wf_seasonal7_kit_<key>.build(ctx)
    python mod-tools/wf_seasonal7_build.py --char regis --step assets
    python mod-tools/wf_seasonal7_build.py --char regis --step manifest
    python mod-tools/wf_seasonal7_build.py --char regis --step art [--dry-run]
    python mod-tools/wf_seasonal7_build.py --char regis --step status
    python mod-tools/wf_seasonal7_build.py --char regis --step inspect     # 草稿包：在临时副本上跑 flow preflight，不封存
    python mod-tools/wf_seasonal7_build.py --char regis --step preflight   # 仅 kit-report status=ready-for-review：会封存 manifest
    python mod-tools/wf_seasonal7_build.py --char all --step init,tables,kit,assets,manifest,art,manifest,status

写入边界：只写 work/character_packs/s7-<key>/ 与 work/character_packs/seasonal7-20260916/；
不发布、不重锚、不启停服务、不写 live store / assets / .cdn / src。
"""
from __future__ import annotations

from wf.paths import root_path

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_seasonal7_common as C  # noqa: E402
import wf_seasonal7_specs as S  # noqa: E402

STEPS = ("init", "tables", "kit", "assets", "manifest", "art", "status", "inspect", "preflight")
READY_KIT_STATUS = "ready-for-review"
INSPECT_DIR = "_inspect"
OCCUPANCY_STEPS = {"init", "tables", "kit", "assets"}


# ---------------------------------------------------------------- kit 上下文

class KitContext:
    """暴露给 ``wf_seasonal7_kit_<key>.build(ctx)`` 的 API（详见 framework_api.md）。"""

    def __init__(self, pack: C.S7Pack) -> None:
        self.pack = pack
        self.spec = pack.spec
        self.root = pack.root
        self.workspace = pack.workspace
        self.package = pack.package
        self.evidence = pack.evidence
        self.store = pack.store
        # 纯函数
        self.replace_strings = C.replace_strings
        self.walk = C.walk
        self.commands = C.commands
        self.csv_split = C.csv_split
        self.csv_join = C.csv_join
        self.amf_parse = C.amf_parse
        self.amf_bytes = C.amf_bytes
        self.png_open = C.png_open
        self.png_store_bytes = C.png_store_bytes
        self.flip_ability_row = C.flip_ability_row
        self.flip_dsl_elements = C.flip_dsl_elements

    # 读
    def official_read(self, logical: str, root: str | None = None) -> bytes | None:
        return self.pack.official_read(logical, root)

    def official_flat(self, logical: str) -> dict[str, str]:
        raw = self.pack.official_read(logical, "common")
        if raw is None:
            raise FileNotFoundError(f"official baseline lacks {logical}")
        return C.core.read_orderedmap_file_from_bytes(raw)

    def official_rows(self, table: str, key: str) -> list[list[str]]:
        logical = table if "/" in table else f"master/ability/{table}.orderedmap"
        return C.csv_split(self.official_flat(logical)[key])

    def live_read(self, logical: str) -> bytes:
        return self.pack.live_read(logical)

    def live_flat(self, logical: str) -> dict[str, str]:
        return self.pack.live_flat(logical)

    def template_flat(self, logical: str) -> dict[str, str]:
        return self.pack.template_flat(logical)

    def template_dsl(self, program_or_logical: str):
        return self.pack.template_dsl(program_or_logical)

    def pkg_flat(self, logical: str, root: str = "common") -> dict[str, str]:
        return self.pack.pkg_flat(logical, root)

    def pkg_nested(self, outer_key: str, logical: str = C.core.ACTION_SKILL_LOGICAL) -> dict[str, list[str]]:
        """包内嵌套表某外键的内层行：{inner_key: cells}（不存在返回 {}）。"""
        if not self.pack.pkg_has("common", logical):
            return {}
        table = C.core.load_nested_table_bytes(self.pack.pkg_path("common", logical).read_bytes(), logical)
        if outer_key not in table.rows:
            return {}
        return {k: C.csv_split(v)[0] for k, v in table.rows[outer_key].text_rows().items()}

    def program_path(self, level: str) -> str:
        import wf_seasonal7_tables as T
        return T.program_path(self.spec, level)

    # 写（包副本优先 + 认领合并）
    def write_flat(self, logical: str, rows, root: str = "common", **kw):
        return self.pack.write_flat(logical, rows, root, **kw)

    def write_raw_outer(self, logical: str, blobs, root: str = "common", **kw):
        return self.pack.write_raw_outer(logical, blobs, root, **kw)

    def write_nested(self, logical: str, outer_key: str, inner_rows, **kw):
        return self.pack.write_nested(logical, outer_key, inner_rows, **kw)

    def write_server(self, logical: str, rows, **kw):
        return self.pack.write_server(logical, rows, **kw)

    def write_dsl(self, program_or_logical: str, tree, **kw):
        kw.setdefault("owner", "kit")
        return self.pack.write_dsl(program_or_logical, tree, **kw)

    def write_asset(self, root: str, logical: str, data: bytes, **kw):
        kw.setdefault("owner", "kit")
        return self.pack.write_asset(root, logical, data, **kw)

    def claim(self, logical: str, keys, codec: str = "flat", root: str = "common", inner=None, *,
              replace_inner: bool = False):
        return self.pack.claim(logical, keys, codec, root, inner, replace_inner=replace_inner)

    def unclaim(self, logical: str, keys=(), **kw):
        """撤销认领并把包内行还原为底表（见 ``S7Pack.unclaim``）。"""
        return self.pack.unclaim(logical, keys, **kw)

    def register_outputs(self, owner: str, entries) -> None:
        """登记非表产物归属（记录 sha256；assets 重跑不会覆盖）。直接写盘的工具必须调用。"""
        self.pack.register_outputs(owner, entries)

    def clone_effect_family(self, src_dir: str, dst_subdir: str, fx_names=None, **kw):
        return C.clone_effect_family(self.pack, src_dir, dst_subdir, fx_names, **kw)

    def rewrite_effect_refs(self, tree, family, *, strict: bool = False):
        return C.rewrite_effect_refs(tree, family, strict=strict)

    def sync_character_mirrors(self):
        return self.pack.sync_character_mirrors()

    def evidence_write(self, name: str, value: Any):
        return self.pack.write_evidence(name, value)

    def report(self, value: dict[str, Any]) -> None:
        """写 evidence/kit-report.json（manifest 整合器读取 skills/unique_condition/
        required_capabilities/summary/panel/notes/status）。"""
        self.pack.write_evidence("kit-report.json", value)


# ---------------------------------------------------------------- 步骤实现

def step_init(pack: C.S7Pack) -> dict[str, Any]:
    """直接建 workspace 壳（目录名 s7-<key> ≠ package_id，flow init 会以 package_id 作目录名）。"""
    import wf_character_workspace as ws
    spec = pack.spec
    marker = pack.workspace / "workspace.json"
    payload = ws._workspace_payload(spec.template_id, spec.cid, spec.code, spec.pkg_id)
    if marker.is_file():
        current = json.loads(marker.read_text(encoding="utf-8"))
        if current != payload:
            raise C.S7Error(f"existing workspace.json differs from spec: {current}")
        created = False
    else:
        if pack.workspace.exists() and any(pack.workspace.iterdir()):
            raise C.S7Error(f"workspace destination is non-empty without workspace.json: {pack.workspace}")
        for root_name in C.ROOT_NAMES:
            (pack.package / "roots" / root_name).mkdir(parents=True, exist_ok=True)
        pack.evidence.mkdir(parents=True, exist_ok=True)
        ws._atomic_json(marker, payload)
        ws._atomic_json(pack.package / "manifest.json",
                        ws._draft_manifest(spec.cid, spec.code, spec.pkg_id))
        created = True
    for root_name in C.ROOT_NAMES:
        (pack.package / "roots" / root_name).mkdir(parents=True, exist_ok=True)
    pack.evidence.mkdir(parents=True, exist_ok=True)
    loaded = ws.load_workspace(pack.workspace)
    pack.write_evidence("spec.json", spec.to_dict())
    return {"workspace": str(loaded.root), "created": created, "package_id": loaded.package_id,
            "character_id": loaded.character_id, "code_name": loaded.code_name}


def step_kit(pack: C.S7Pack) -> dict[str, Any]:
    module = S.load_kit_module(pack.spec.key)
    if module is None:
        return {"skipped": True,
                "reason": f"mod-tools/{S.kit_module_name(pack.spec.key)}.py 不存在；词条/技能保持母本占位"}
    if not hasattr(module, "build"):
        raise C.S7Error(f"{S.kit_module_name(pack.spec.key)} has no build(ctx)")
    result = module.build(KitContext(pack))
    return {"skipped": False, "result": result}


def _flow(command: str, workspace: Path, root: Path, extra: list[str] | None = None) -> tuple[int, dict]:
    """子进程跑 flow CLI。强制 UTF-8：Windows 管道默认 cp936，会把中文证据替换成 U+FFFD，
    遇到非 GBK 字符（・♪ emoji）子进程还会直接崩。"""
    cmd = [sys.executable, str(HERE / "wf_character_flow.py"), command,
           "--workspace", str(workspace), *(extra or [])]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True,
                          encoding="utf-8", errors="strict", env=env)
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    if not lines:
        raise C.S7Error(f"flow {command} produced no output (rc={proc.returncode}): {proc.stderr[-800:]}")
    return proc.returncode, json.loads(lines[-1])


def _fix_next_command(value: Any, pack: C.S7Pack, workspace: Path | None = None) -> Any:
    """flow 按 package_id 拼 ``work/character_packs/<package_id>``；本批目录名是 ``s7-<key>``。"""
    if not isinstance(value, str):
        return value
    actual = workspace if workspace is not None else pack.workspace
    try:
        shown = actual.resolve().relative_to(pack.root.resolve()).as_posix()
    except ValueError:
        shown = str(actual)
    value = value.replace(str(actual), shown)
    return re.sub(r"work/character_packs/" + re.escape(pack.spec.pkg_id) + r"(?![A-Za-z0-9_.-])",
                  lambda _m: shown, value)


def summarize_status(payload: dict, pack: C.S7Pack | None = None) -> dict[str, Any]:
    status = payload.get("status") or {}
    req = status.get("requirement_report") or {}
    next_command = payload.get("next_command")
    if pack is not None:
        next_command = _fix_next_command(next_command, pack)
    return {"ok": payload.get("ok"), "errors": payload.get("errors"),
            "release_ready": payload.get("release_ready"),
            "required_present": req.get("required_present"),
            "required_total": req.get("required_total"),
            "missing_required": req.get("missing_required"),
            "three_layer_claim_status": status.get("three_layer_claim_status"),
            "manifest_errors": status.get("manifest_errors"),
            "input_digest": status.get("input_digest"),
            "next_command": next_command}


def step_status(pack: C.S7Pack) -> dict[str, Any]:
    rc, payload = _flow("status", pack.workspace, pack.root)
    pack.write_evidence("flow-status.json", payload)
    result = {"returncode": rc, **summarize_status(payload, pack)}
    if rc != 0 or payload.get("ok") is False:
        raise C.S7Error(f"flow status failed rc={rc}: {payload.get('errors')}")
    return result


def chain_tails(root: Path) -> dict[str, Any]:
    """legacy wf_publish 链尾（archive-common-diff 最大落点）与 flow 账本 base_version。"""
    from wf_enhancement_policy import DIFF_RE, vkey
    diff_dir = root / ".cdn" / "cn" / "archive-common-diff"
    versions = [m.group(2) for p in (diff_dir.glob("*.zip") if diff_dir.is_dir() else [])
                for m in [DIFF_RE.match(p.name)] if m]
    legacy = max(versions, key=vkey) if versions else None
    active = root / ".cdn" / "cn" / "character-releases" / "active.json"
    try:
        ledger = json.loads(active.read_text(encoding="utf-8")).get("base_version") if active.is_file() else None
    except (OSError, ValueError):
        ledger = None
    warning = None
    if legacy and ledger and legacy != ledger:
        warning = (f"flow 账本 base {ledger} != legacy 链尾 {legacy}：首个 flow publish 前须经作者授权 "
                   "reanchor，否则铸中段边、投递为零（记忆卡 wf-flow-ledger-dual-tail）")
    return {"legacy_chain_tail": legacy, "ledger_base_version": ledger, "warning": warning}


def _preflight_summary(rc: int, payload: dict, pack: C.S7Pack, workspace: Path | None = None) -> dict[str, Any]:
    pre = payload.get("preflight") or {}
    master = payload.get("master_reference_report") or {}
    summary = {"returncode": rc, **summarize_status(payload, pack),
               "preflight": {k: pre.get(k) for k in ("can_prepare", "release_ready", "writes_live",
                                                     "validated_chain_tail", "conflicts",
                                                     "delivery_mode")} if pre else None,
               "charpkg_strand": (pre.get("charpkg_strand") or {}).get("stranded_edges") if pre else None,
               "master_reference": {k: master.get(k) for k in ("release_ready", "missing", "problems")},
               "chain": chain_tails(pack.root)}
    if workspace is not None:
        summary["next_command"] = _fix_next_command(payload.get("next_command"), pack, workspace)
    return summary


def kit_readiness(pack: C.S7Pack) -> tuple[bool, str]:
    report = pack.read_evidence("kit-report.json", None)
    if not isinstance(report, dict):
        return False, "evidence/kit-report.json 不存在（kit 未写，词条/技能仍是母本占位）"
    if report.get("status") != READY_KIT_STATUS:
        return False, f"kit-report status={report.get('status')!r}，需要 {READY_KIT_STATUS!r}"
    return True, "kit ready-for-review"


def step_preflight(pack: C.S7Pack) -> dict[str, Any]:
    """真 flow preflight：满足条件时会把 workspace manifest 封存为 release_ready=true。
    只允许 kit-report status=ready-for-review 的包；草稿包请用 ``--step inspect``。"""
    ready, reason = kit_readiness(pack)
    if not ready:
        raise C.S7Error(f"refusing sealing preflight on a draft package: {reason}; "
                        "use --step inspect (runs flow preflight on a temporary copy, no sealing)")
    rc, payload = _flow("preflight", pack.workspace, pack.root, ["--profile", "cn"])
    pack.write_evidence("flow-preflight.json", payload)
    result = _preflight_summary(rc, payload, pack)
    if rc != 0:
        raise C.S7Error(f"flow preflight not ready rc={rc}: {payload.get('errors')}; chain={result['chain']}")
    return result


def step_inspect(pack: C.S7Pack, installed_package_dir: Path | None = None) -> dict[str, Any]:
    '草稿检查：把 workspace 复制到批目录 ``_inspect/`` 下跑 flow preflight（只在副本里封存），\n    结果写 ``evidence/flow-inspect.json``；真实 workspace 的 manifest/status/hash-cache 字节不变。\n\n    ``installed_package_dir``：角色**已经发布过**时必须给（归档包目录，如\n    ``${WF_ROOT}/pkgarchive/s7-tekuto-20260916-1.4.897``）。不给的话 flow 会以\n    ``active ownership hash exists but installed manifest was not supplied`` 报 rc=2 ——\n    那不是包有问题，是缺了「上一版是谁」这份证据。给了以后 inspect 对已发布角色照样可用，\n    改版轮的 gates.py 才不会因为 inspect 过期而报假红。'
    pack.check_identity()
    guarded = [pack.package / "manifest.json", pack.evidence / "status.json",
               pack.evidence / "hash-cache.json"]
    before = {str(p): (p.read_bytes() if p.is_file() else None) for p in guarded}
    base = pack.batch_dir / INSPECT_DIR
    copy_root = base / f"{pack.spec.key}-{os.getpid()}"
    if copy_root.exists():
        shutil.rmtree(copy_root)
    try:
        copy_root.mkdir(parents=True)
        workspace_copy = copy_root / pack.workspace.name
        shutil.copytree(pack.workspace, workspace_copy)
        extra = ["--profile", "cn"]
        if installed_package_dir is not None:
            installed = Path(installed_package_dir)
            if not (installed / "manifest.json").is_file():
                raise C.S7Error(f"installed package dir has no manifest.json: {installed}")
            extra += ["--installed-package-dir", str(installed)]
        rc, payload = _flow("preflight", workspace_copy, pack.root, extra)
    finally:
        shutil.rmtree(copy_root, ignore_errors=True)
        try:
            base.rmdir()
        except OSError:
            pass
    after = {str(p): (p.read_bytes() if p.is_file() else None) for p in guarded}
    if after != before:
        raise C.S7Error("inspect modified the real workspace")
    ready, reason = kit_readiness(pack)
    text = json.dumps(payload, ensure_ascii=False)
    for old, new in ((workspace_copy, pack.workspace), (workspace_copy.resolve(), pack.workspace.resolve())):
        text = text.replace(json.dumps(str(old))[1:-1], json.dumps(str(new))[1:-1])
    payload = json.loads(text)                  # 副本路径 → 真实 workspace 路径
    result = _preflight_summary(rc, payload, pack, pack.workspace)
    result.update({"sealed_real_workspace": False, "sealed_copy_only": True, "kit_ready": ready,
                   "kit_reason": reason, "structurally_ready": rc == 0,
                   "flow_next_command": result["next_command"]})
    if not ready:                               # 草稿包：flow 给的 publish 提示不适用
        result["next_command"] = (f"草稿包（{reason}）：先写 mod-tools/{S.kit_module_name(pack.spec.key)}.py 并 "
                                  "report status=ready-for-review，再跑 --step tables,kit,assets,manifest,status,preflight")
    pack.write_evidence("flow-inspect.json", {"summary": result, "payload": payload})
    if rc == 2:
        raise C.S7Error(f"flow preflight (inspect copy) errored: {payload.get('errors')}")
    return result


def run_step(step: str, pack: C.S7Pack, args: argparse.Namespace) -> dict[str, Any]:
    if step == "init":
        return step_init(pack)
    if step == "tables":
        import wf_seasonal7_tables as T
        return T.build(pack)
    if step == "kit":
        return step_kit(pack)
    if step == "assets":
        import wf_seasonal7_assets as A
        return A.build(pack)
    if step == "manifest":
        import wf_seasonal7_manifest as M
        return M.build(pack)
    if step == "art":
        import wf_seasonal7_art as ART
        landmarks_path = args.landmarks or ART.default_landmarks(pack.root)
        landmarks = ART.load_landmarks(landmarks_path, pack.spec.key)
        result = ART.build(pack, landmarks, source_dir=args.source_dir, apply=not args.dry_run,
                           headshots=args.headshots)
        return {"applied": result["applied"], "gates": result["gates"],
                "changed": sum(r["changed"] for r in result["files"]),
                "geometry": [{k: g[k] for k in ("x", "y", "width", "height", "scale")}
                             for g in result["geometry"]],
                "contact": [str(ART.default_output(pack) / "icons-contact.png"),
                            str(ART.default_output(pack) / "art-contact.png")]}
    if step == "status":
        return step_status(pack)
    if step == "inspect":
        return step_inspect(pack, args.installed_package_dir)
    if step == "preflight":
        return step_preflight(pack)
    raise C.S7Error(f"unknown step {step}")


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--char", required=True, help="角色 key 或 all")
    parser.add_argument("--step", required=True, help="逗号分隔：" + "|".join(STEPS))
    parser.add_argument("--landmarks", type=Path)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--headshots", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="art 只预览不写包")
    parser.add_argument("--skip-occupancy-check", action="store_true",
                        help="已发布后重建包时跳过未占用断言（live 已有自身键）")
    parser.add_argument("--installed-package-dir", type=Path,
                        help=('inspect：角色已发布过时必须给上一版归档包目录（如 ${WF_ROOT}/pkgarchive/s7-tekuto-20260916-1.4.897）'.replace("${WF_ROOT}", str(root_path()))))
    args = parser.parse_args(argv)
    keys = S.all_keys() if args.char == "all" else [k.strip() for k in args.char.split(",")]
    steps = [s.strip() for s in args.step.split(",") if s.strip()]
    for step in steps:
        if step not in STEPS:
            parser.error(f"unknown step {step}")
    specs = [S.get_spec(k) for k in keys]
    results: dict[str, Any] = {}
    code = 0
    if not args.skip_occupancy_check and OCCUPANCY_STEPS & set(steps):
        probe = C.S7Pack(specs[0])
        S.assert_unoccupied(specs, repo_root=probe.root, store=probe.store,
                            cache_path=probe.batch_dir / "occupancy-cache.json")
    for spec in specs:
        pack = C.S7Pack(spec)
        results[spec.key] = {}
        for step in steps:
            try:
                results[spec.key][step] = run_step(step, pack, args)
            except Exception as exc:          # 报告后停止该角色后续步骤
                results[spec.key][step] = {"error": f"{type(exc).__name__}: {exc}",
                                           "traceback": traceback.format_exc()[-2000:]}
                code = 2
                break
    print(json.dumps(results, ensure_ascii=False, indent=1, default=str))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
