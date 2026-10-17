# -*- coding: utf-8 -*-
"""中秋批次（midautumn-20260920）：规格驱动角色包构建 CLI。

    python mod-tools/wf_midautumn_build.py --char all  --step check
    python mod-tools/wf_midautumn_build.py --char mia  --step init,tables,kit,assets,manifest
    python mod-tools/wf_midautumn_build.py --char mia  --step art --dry-run
    python mod-tools/wf_midautumn_build.py --char mia  --step art,manifest,status,inspect
    python mod-tools/wf_midautumn_build.py --char mia  --step preflight     # 仅 kit ready-for-review

步骤全部复用 :mod:`wf_seasonal7_build` 的实现，只换三处：名册（:mod:`wf_midautumn_specs`）、
包上下文（:class:`wf_midautumn_common.MAPack`）、art 的默认路径。

写入边界：只写 ``work/character_packs/ma-<key>/`` 与 ``work/character_packs/midautumn-20260920/``；
不发布、不重锚、不启停服务，不写 live store / assets / .cdn / src / 设备 / 存档。
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import shutil
import sys
import traceback
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_midautumn_common as MC  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_seasonal7_build as B  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402

STEPS = ("check", "init", "tables", "kit", "assets", "manifest", "art", "status", "inspect", "preflight")
OCCUPANCY_STEPS = {"init", "tables", "kit", "assets"}
PREV_BATCH = "work/character_packs/seasonal7-20260916"
INSPECT_DIR = B.INSPECT_DIR


# ---------------------------------------------------------------- 默认路径

def default_masters(root: Path) -> Path:
    return MS.batch_dir(root) / "art" / "masters"


def default_landmarks(root: Path, key: str) -> Path:
    """本批按角色一份：``B/art/landmarks/<key>.json``；没有时退回合批 ``B/art/landmarks.json``。"""
    per_key = MS.batch_dir(root) / "art" / "landmarks" / f"{key}.json"
    combined = MS.batch_dir(root) / "art" / "landmarks.json"
    return per_key if per_key.is_file() or not combined.is_file() else combined


def default_mask_cache(root: Path) -> Path:
    """形状蒙版与母本无关（官方统计中位数）⇒ 直接复用上批缓存，省几分钟。"""
    previous = root / PREV_BATCH / "art" / "official-shape-masks.npz"
    return previous if previous.is_file() else MS.batch_dir(root) / "art" / "official-shape-masks.npz"


def load_landmarks(path: Path, key: str) -> list[dict]:
    """接受两种形状：``{key: [槽0, 槽1]}``（上批 landmarks.json）或裸的 ``[槽0, 槽1]``。"""
    path = Path(path)
    if path.is_dir():
        path = path / f"{key}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if key not in data:
            raise C.S7Error(f"landmarks file has no entry for {key}: {path}")
        data = data[key]
    if not isinstance(data, list) or len(data) != 2:
        raise C.S7Error(f"landmarks for {key} must be two entries: {path}")
    return data


def resolve_masters(pack: MC.MAPack, source_dir: Path) -> Path:
    """art 要 ``<key>-<level>.png``；阶段产物契约写的是 ``<key>_<level>.png``。
    两种命名都接受：下划线版按字节复制到 workspace 证据目录下的连字符名（sha 不变）。"""
    spec = pack.spec
    source_dir = Path(source_dir)
    missing = [lv for lv in (0, 1) if not (source_dir / f"{spec.key}-{lv}.png").is_file()]
    if not missing:
        return source_dir
    staged = pack.evidence / "art" / "_masters"
    resolved = True
    for level in (0, 1):
        want = source_dir / f"{spec.key}-{level}.png"
        alt = source_dir / f"{spec.key}_{level}.png"
        if want.is_file():
            data = want.read_bytes()
        elif alt.is_file():
            data = alt.read_bytes()
        else:
            resolved = False
            continue
        staged.mkdir(parents=True, exist_ok=True)
        target = staged / f"{spec.key}-{level}.png"
        if not target.is_file() or target.read_bytes() != data:
            target.write_bytes(data)
    if not resolved:
        raise C.S7Error(f"master art missing for {spec.key}: expected "
                        f"{source_dir}/{spec.key}-<0|1>.png (或 {spec.key}_<0|1>.png)")
    return staged


# ---------------------------------------------------------------- 步骤

def step_check(pack: MC.MAPack) -> dict[str, Any]:
    """只读体检：身份占用、母本稀有度补洞、元素翻转 SE 缺口、文案占位、workspace 状态。

    用 ``record_sources=False`` 的探针包，避免在 ``init`` 之前把 workspace 目录写出来。
    """
    spec = pack.spec
    probe = MC.MAPack(spec, root=pack.root, store=pack.store, workspace=pack.workspace,
                      server_base=pack.server_base, record_sources=False)
    problems = MS.occupancy_problems([spec], repo_root=pack.root, store=pack.store)
    return {"occupancy": problems[spec.key],
            "rarity": MC.rarity_problems(probe),
            "gacha_flip_gaps": MC.gacha_flip_gaps(probe),
            "spec_warnings": MS.spec_warnings(spec.key, pack.root),
            "text_placeholders": MS.text_placeholders(spec),
            "chain": B.chain_tails(pack.root),
            "requires_client_base": spec.requires_client_base,
            "design_json": str(MS.design_path(pack.root, spec.key))
                           if MS.design_path(pack.root, spec.key).is_file() else None,
            "kit_module": MS.kit_module_name(spec.key)
                          if MS.load_kit_module(spec.key) is not None else None,
            "workspace_initialised": (pack.workspace / "workspace.json").is_file(),
            "template": {"id": spec.template_id, "code": spec.template_code,
                         "element": spec.template_element, "identity": spec.template_identity},
            "element_flip": spec.element_flip}


def step_kit(pack: MC.MAPack) -> dict[str, Any]:
    module = MS.load_kit_module(pack.spec.key)
    if module is None:
        return {"skipped": True,
                "reason": f"mod-tools/{MS.kit_module_name(pack.spec.key)}.py 不存在；词条/技能保持母本占位"}
    if not hasattr(module, "build"):
        raise C.S7Error(f"{MS.kit_module_name(pack.spec.key)} has no build(ctx)")
    return {"skipped": False, "result": module.build(B.KitContext(pack))}


def step_art(pack: MC.MAPack, args: argparse.Namespace) -> dict[str, Any]:
    import wf_seasonal7_art as ART
    spec = pack.spec
    landmarks = load_landmarks(args.landmarks or default_landmarks(pack.root, spec.key), spec.key)
    source_dir = resolve_masters(pack, args.source_dir or default_masters(pack.root))
    mask_cache = args.mask_cache or default_mask_cache(pack.root)
    result = ART.build(pack, landmarks, source_dir=source_dir, apply=not args.dry_run,
                       headshots=args.headshots, mask_cache=Path(mask_cache))
    return {"applied": result["applied"], "gates": result["gates"],
            "changed": sum(r["changed"] for r in result["files"]),
            "mask_cache": str(mask_cache), "source_dir": str(source_dir),
            "geometry": [{k: g[k] for k in ("x", "y", "width", "height", "scale")}
                         for g in result["geometry"]],
            "contact": [str(ART.default_output(pack) / "icons-contact.png"),
                        str(ART.default_output(pack) / "art-contact.png")]}


def _fix_kit_hint(result: dict[str, Any], key: str) -> dict[str, Any]:
    """B.step_inspect 的草稿提示写的是上批模块名。"""
    hint = result.get("next_command")
    if isinstance(hint, str):
        result["next_command"] = hint.replace(f"wf_seasonal7_kit_{key}", MS.kit_module_name(key))
    return result


UNREACHABLE_BASE = "cannot reach validated tail"


def ledger_tail(root: Path) -> str | None:
    """flow 账本的 validated tail：有 release 取最后一条的 version，否则 base_version。"""
    active = Path(root) / ".cdn" / "cn" / "character-releases" / "active.json"
    try:
        data = json.loads(active.read_text(encoding="utf-8")) if active.is_file() else {}
    except (OSError, ValueError):
        return None
    releases = data.get("releases") or []
    if releases and isinstance(releases[-1], dict) and releases[-1].get("version"):
        return str(releases[-1]["version"])
    return data.get("base_version")


def _inspect_at_base(pack: MC.MAPack, base: str,
                     installed_package_dir: Path | None) -> tuple[int, dict]:
    """在副本上把 ``requires_client_base`` 换成 ``base`` 重建 manifest 再跑 flow preflight。

    真 workspace 一个字节都不动（copytree → 跑 → 删）。只用于 ``inspect`` 的退路，
    ``preflight``（真封存）永远按 spec 的值来。
    """
    import wf_seasonal7_manifest as M
    copy_root = pack.batch_dir / INSPECT_DIR / f"{pack.spec.key}-{os.getpid()}-rebase"
    shutil.rmtree(copy_root, ignore_errors=True)
    copy_root.mkdir(parents=True)
    try:
        workspace_copy = copy_root / pack.workspace.name
        shutil.copytree(pack.workspace, workspace_copy)
        copy_pack = MC.MAPack(dataclasses.replace(pack.spec, requires_client_base=base),
                              root=pack.root, store=pack.store, workspace=workspace_copy,
                              server_base=pack.server_base)
        M.build(copy_pack)
        extra = ["--profile", "cn"]
        if installed_package_dir is not None:
            extra += ["--installed-package-dir", str(installed_package_dir)]
        return B._flow("preflight", workspace_copy, pack.root, extra)
    finally:
        shutil.rmtree(copy_root, ignore_errors=True)
        try:
            (pack.batch_dir / INSPECT_DIR).rmdir()
        except OSError:
            pass


def step_inspect(pack: MC.MAPack, args: argparse.Namespace) -> dict[str, Any]:
    """草稿检查。遇到「账本双尾」这一个已知的批次级前置时自动改用账本尾复验结构。

    ``requires_client_base 1.4.9xx cannot reach validated tail 1.4.9yy`` 不是包的问题：
    是 flow 账本还没 reanchor 到 legacy 链尾（记忆卡 wf-flow-ledger-dual-tail）。
    reanchor 属于发布动作，由主控统一做；在那之前用账本尾复验，结论照样可信。
    """
    before = {p: (p.read_bytes() if p.is_file() else None)
              for p in (pack.package / "manifest.json", pack.evidence / "status.json",
                        pack.evidence / "hash-cache.json")}
    try:
        return _fix_kit_hint(B.step_inspect(pack, args.installed_package_dir), pack.spec.key)
    except C.S7Error as exc:
        chain = B.chain_tails(pack.root)
        tail = ledger_tail(pack.root)
        if UNREACHABLE_BASE not in str(exc) or not tail:
            raise
        rc, payload = _inspect_at_base(pack, tail, args.installed_package_dir)
        after = {p: (p.read_bytes() if p.is_file() else None) for p in before}
        if after != before:
            raise C.S7Error("inspect fallback modified the real workspace") from exc
        result = B._preflight_summary(rc, payload, pack, pack.workspace)
        ready, reason = B.kit_readiness(pack)
        result.update({"sealed_real_workspace": False, "kit_ready": ready, "kit_reason": reason,
                       "structurally_ready": rc == 0, "chain_blocked": True,
                       "configured_requires_client_base": pack.spec.requires_client_base,
                       "verified_at_requires_client_base": tail,
                       "chain_note": f"flow 账本尾 {tail} < legacy 链尾 {chain.get('legacy_chain_tail')}；"
                                     f"spec 的 {pack.spec.requires_client_base} 在 reanchor 之后才可达。"
                                     "本次结构校验按账本尾复跑，真 workspace 未改。"})
        result["next_command"] = ("先由主控 reanchor 到 legacy 链尾，再按 spec 的 "
                                  f"requires_client_base {pack.spec.requires_client_base} 复跑 inspect")
        pack.write_evidence("flow-inspect.json", {"summary": result, "payload": payload})
        if rc == 2:
            raise C.S7Error(f"flow preflight (inspect copy @ {tail}) errored: {payload.get('errors')}") from exc
        return result


def run_step(step: str, pack: MC.MAPack, args: argparse.Namespace) -> dict[str, Any]:
    if step == "check":
        return step_check(pack)
    if step == "kit":
        return step_kit(pack)
    if step == "art":
        return step_art(pack, args)
    if step == "inspect":
        return step_inspect(pack, args)
    return B.run_step(step, pack, args)          # init/tables/assets/manifest/status/preflight


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--char", required=True, help="角色 key、逗号分隔的多个 key，或 all")
    parser.add_argument("--step", required=True, help="逗号分隔：" + "|".join(STEPS))
    parser.add_argument("--landmarks", type=Path, help="landmarks JSON 或目录（默认 B/art/landmarks/<key>.json）")
    parser.add_argument("--source-dir", type=Path, help="立绘母图目录（默认 B/art/masters）")
    parser.add_argument("--mask-cache", type=Path, help="形状蒙版 npz（默认复用上批）")
    parser.add_argument("--headshots", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="art 只预览不写包")
    parser.add_argument("--skip-occupancy-check", action="store_true",
                        help="已发布后重建包时跳过未占用断言（live 已有自身键）")
    parser.add_argument("--installed-package-dir", type=Path,
                        help="inspect：角色已发布过时必须给上一版归档包目录")
    parser.add_argument("--no-kit", action="store_true", help="忽略 kit 模块的 SPEC/TEXTS 覆盖（调试用）")
    parser.add_argument("--requires-client-base", default=os.environ.get("WF_MA_REQUIRES_CLIENT_BASE"),
                        help="临时覆盖 requires_client_base（默认 %s）。reanchor 之前 flow 会拒绝"
                             "「链尾之上」的 base，用账本尾复跑 manifest,inspect 才能验结构；"
                             "验完记得用默认值重跑 manifest" % MS.REQUIRES_CLIENT_BASE)
    args = parser.parse_args(argv)

    try:
        keys = MS.resolve_keys(args.char)
    except KeyError as exc:
        parser.error(str(exc))
    steps = [s.strip() for s in args.step.split(",") if s.strip()]
    for step in steps:
        if step not in STEPS:
            parser.error(f"unknown step {step}")
    specs = [MS.get_spec(k, with_kit=not args.no_kit) for k in keys]
    if args.requires_client_base:
        specs = [dataclasses.replace(s, requires_client_base=args.requires_client_base)
                 for s in specs]

    results: dict[str, Any] = {}
    code = 0
    if not args.skip_occupancy_check and OCCUPANCY_STEPS & set(steps):
        probe = MC.MAPack(specs[0])
        MS.assert_unoccupied(specs, repo_root=probe.root, store=probe.store,
                             cache_path=probe.batch_dir / "occupancy-cache.json")
    for spec in specs:
        pack = MC.MAPack(spec)
        results[spec.key] = {}
        for step in steps:
            try:
                results[spec.key][step] = run_step(step, pack, args)
            except Exception as exc:              # 报告后停止该角色后续步骤
                results[spec.key][step] = {"error": f"{type(exc).__name__}: {exc}",
                                           "traceback": traceback.format_exc()[-2000:]}
                code = 2
                break
    if "check" in steps:
        bad = {k: v["check"] for k, v in results.items()
               if isinstance(v.get("check"), dict)
               and (v["check"].get("occupancy") or v["check"].get("rarity")
                    or v["check"].get("gacha_flip_gaps"))}
        if bad:
            code = 2
    print(json.dumps(results, ensure_ascii=False, indent=1, default=str))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
