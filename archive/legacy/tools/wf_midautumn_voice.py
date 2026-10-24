# -*- coding: utf-8 -*-
"""中秋批次语音管线：:mod:`wf_seasonal7_voice` 的批次包装壳。

    python mod-tools/wf_midautumn_voice.py refs     --roles mia nicola
    python mod-tools/wf_midautumn_voice.py plan     --roles mia --run take1
    python mod-tools/wf_midautumn_voice.py generate --roles mia --run take1      # 付费
    python mod-tools/wf_midautumn_voice.py process  --roles mia --run take1
    python mod-tools/wf_midautumn_voice.py pack     --roles mia --run take1      # 一步装完

路径全部改指本批：design = ``B/design/<key>.json``、输出 = ``B/voice/…``；
``ROLES`` 由 :mod:`wf_midautumn_specs` 生成。

密钥：从 ``work/character_packs/seasonal7-20260916/.secrets/seed_audio.key`` 读进
进程环境 ``WF_SEED_AUDIO_KEY``，**不打印、不落盘、不进回执**；也不用 ``--key-file``
（那个分支会 subprocess 重新拉起原脚本，本壳的全局改写会全部丢掉，01 报告 §3.3 坑 2）。

另外两个坑（01 报告 §3.3）：
- ``load_refs_index`` / ``build_references`` / ``run_smoke`` 的默认参数在 def 时就绑死了，
  改模块全局不生效 ⇒ 这里直接改它们的 ``__defaults__`` / ``__kwdefaults__``。
- 凯尔、索恩没有官方母本语音 ⇒ ``refs`` 默认跳过它们，design 的 ``references``
  必须写显式 ``{path, sha256}``。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_midautumn_common as MC  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402
import wf_seasonal7_voice as V  # noqa: E402

ROOT = V.ROOT
BATCH = ROOT / MS.BATCH_DIR
REWORK2 = BATCH / "rework2" / "voice"
KEY_FILE = ROOT / "work" / "character_packs" / "seasonal7-20260916" / ".secrets" / "seed_audio.key"
# 无官方母本语音：凯尔（原创）、索恩（十天众原声随包）——design 里写显式 references。
NO_OFFICIAL_REFS = ("kyle", "thorn")
BATTLE_REF_SLOTS = ("battle/skill_ready", "battle/battle_start_0", "battle/battle_start_1",
                    "battle/win_0", "battle/win_1")
SPEECH = "master/character/character_speech.orderedmap"
# 第二轮（rework2）的固定落点：台词稿、配方、合成 design、参考音索引全在 rework2/voice 下。
SCRIPT_DIR = REWORK2 / "scripts"
RECIPE_FILE = REWORK2 / "recipe.json"
SYNTH_DESIGN_DIR = REWORK2 / "scratch" / "design"
# 凯尔：技能发动 6 条（序号池 skill_0..5）＋技能准备引擎硬上限 2 条，
# 多出的两条改投开战池 battle_start_2/3（同为序号随机池，零表行零补丁）。
ROLE_SLOTS = {"kyle": V.SLOTS_26}


def roles() -> dict[str, dict[str, str]]:
    out = {}
    for key in MS.all_keys():
        spec = MS.SPECS[key]
        out[key] = dict(cid=spec.cid_s, code=spec.code,
                        template_id=spec.template_id_s, template_code=spec.template_code)
        if key in ROLE_SLOTS:
            out[key]["slots"] = list(ROLE_SLOTS[key])
    return out


def install_paths(*, rework2: bool = False) -> None:
    """把 wf_seasonal7_voice 的模块级路径全部改指本批（函数体运行时读全局）。

    `rework2=True` 时整条产物链改指 `rework2/voice/`：prompt 模板一改，
    `request_fingerprint` 全部失效，必须用全新 run 树，不能沿用第一轮目录。
    """
    V.PACK = BATCH
    V.DESIGN_DIR = BATCH / "design"
    V.VOICE_DIR = REWORK2 if rework2 else BATCH / "voice"
    V.REFS_DIR = V.VOICE_DIR / "refs"
    V.REFS_INDEX = V.REFS_DIR / ("refs-v2.json" if rework2 else "refs.json")
    V.GENERATION_DIR = V.VOICE_DIR / "generation"
    V.SMOKE_DIR = V.VOICE_DIR / "smoke"
    V.KEY_FILE = KEY_FILE
    V.ROLES = roles()
    # 默认参数在 def 时绑死，改全局不生效（01 报告 §3.3 坑 1）。
    V.load_refs_index.__defaults__ = (V.REFS_INDEX,)
    for func, name, value in ((V.build_references, "out_dir", V.REFS_DIR),
                              (V.build_references_v2, "out_dir", V.REFS_DIR),
                              (V.run_smoke, "out_dir", V.SMOKE_DIR)):
        defaults = dict(func.__kwdefaults__ or {})
        defaults[name] = value
        func.__kwdefaults__ = defaults


# ---------------------------------------------------------------- 第二轮：台词稿与参考音

def load_recipe(path=None) -> dict:
    return json.loads(Path(path or RECIPE_FILE).read_text(encoding="utf-8"))


def reference_specs(recipe: dict, role_keys: list[str]) -> dict[str, dict]:
    """recipe.reference_policy.per_role → :func:`V.build_references_v2` 的 specs。

    两种源形状：``groups``（官方原声/GBF 原声，逐族一条）与 ``derive``
    （作者自带样本，带自定义 ffmpeg 滤镜；产物名取 out 的文件名）。
    """
    policy = recipe["reference_policy"]["per_role"]
    specs = {}
    for role in role_keys:
        item = policy.get(role)
        if item is None:
            raise SystemExit(f"recipe has no reference policy for {role}")
        # derive 的 from 只写文件名，全路径在 source_measurements 里。
        measured = {Path(m["file"]).name: m["file"] for m in item.get("source_measurements") or []}
        groups = {}
        for name, entry in (item.get("groups") or {}).items():
            groups[name] = dict(source=entry["source"], range=V.REF_RANGES_V2.get(name))
        for entry in item.get("derive") or []:
            name = Path(entry["out"]).stem
            source = entry["from"]
            if not Path(source).is_absolute():
                source = measured.get(Path(source).name, source)
            groups[name] = dict(source=source, filters=_derive_filters(entry, item),
                                range=V.REF_RANGES_V2.get(name))
        default = (V.REF_FILTERS_V2_KEEP_LEVEL if item.get("kind") == "gbf_original"
                   else V.REF_FILTERS_V2)
        # `exemptions: {group: 理由}` = 角色参考音策略里对区间/电平闸门的显式豁免。
        # 只有写了理由的 group 才允许带缺陷进请求（见 V.group_references）。
        specs[role] = dict(kind=item.get("kind", ""), note=item.get("note", ""), filters=default,
                           groups=groups, slot_to_group=item.get("slot_to_group") or {},
                           exemptions=item.get("exemptions") or {})
    return specs


def _derive_filters(entry: dict, item: dict) -> str | None:
    """`ffmpeg_af` 里可能写的是中文注记（如「同 long.wav」）而不是滤镜链。

    非 ASCII 即当注记处理：能认出它指向哪个派生件就复用那条链，否则回落到默认配方。
    直接把中文串当滤镜送给 ffmpeg 会报错，更糟的是可能被当成另一个滤镜名。
    """
    def usable(text):
        # 本机 ffmpeg 的 silenceremove 只让 stop_periods 取负值（start_periods 限 [0,9000]）；
        # 去掉内部停顿的惯用写法就是 start_periods=1 + stop_periods=-1。
        return text.replace("start_periods=-1", "start_periods=1")

    text = entry.get("ffmpeg_af")
    if not text:
        return None
    if text.isascii():
        return usable(text)
    match = re.search(r"([A-Za-z0-9_.-]+)\.wav", text)
    if match:
        target = match.group(1)
        for other in item.get("derive") or []:
            if Path(other["out"]).stem == target and str(other.get("ffmpeg_af") or "").isascii():
                return usable(other["ffmpeg_af"])
    return None


def script_path(role: str, folder=None) -> Path:
    return Path(folder or SCRIPT_DIR) / f"{role}.json"


def synthesize_design(role: str, *, folder=None, out_dir=None, route=None) -> Path:
    """外置台词稿 → `{"voice": {...}}` 形状的 design，落到 scratch/design/<role>.json。

    台词稿只写 persona 与 lines；`load_design_voice` 硬要顶层 voice 对象，
    `references`/`route` 也不在稿里（route 沿用本批既有 design）。
    稿里的 `seconds`、`continuity`、`grammar`、`bible` 等字段不进管线（时长目标由
    `slot_targets` 的官方 p25–p75 决定，写进 performance 文本）。
    """
    source = script_path(role, folder)
    if not source.is_file():
        raise SystemExit(f"script missing for {role}: {source}")
    script = json.loads(source.read_text(encoding="utf-8"))
    lines = script.get("lines")
    if not isinstance(lines, list) or not lines:
        raise SystemExit(f"{source}: lines must be a non-empty list")
    keep = ("slot", "ja", "tts_text", "zh", "direction", "tone", "quote_policy")
    if route is None:
        design = V.DESIGN_DIR / f"{role}.json"
        route = (json.loads(design.read_text(encoding="utf-8")).get("voice") or {}).get("route") \
            if design.is_file() else None
    voice = dict(prompt_version=2, persona=script["persona"], references="groups", route=route,
                 lines=[{k: item[k] for k in keep if item.get(k)} for item in lines])
    for name in ("persona_short", "voice_tag"):
        if script.get(name):
            voice[name] = script[name]
    target = Path(out_dir or SYNTH_DESIGN_DIR) / f"{role}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(key=role, source=str(source), voice=voice),
                                 ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return target


def load_key() -> None:
    """密钥只进进程环境；读不到就明确报错（绝不打印内容）。"""
    if os.environ.get(V.KEY_ENV):
        return
    if not KEY_FILE.is_file():
        raise SystemExit(f"credential file missing: {KEY_FILE}")
    key = KEY_FILE.read_text(encoding="utf-8").strip()
    if not key or any(ch.isspace() for ch in key):
        raise SystemExit("credential file is empty or malformed")
    os.environ[V.KEY_ENV] = key


# ---------------------------------------------------------------- 参考音候选

def _official_speech_home_slots(pack, template_code: str, template_id: str) -> list[str]:
    """母本 character_speech 里的 home 语音槽（官方自定义名，如 ``home/otto_mitsukatte``）。"""
    raw = pack.official_read(SPEECH, "common")
    if raw is None:
        return []
    rows = C.core.read_orderedmap_file_from_bytes(raw)
    if template_id not in rows:
        return []
    prefix = f"character/{template_code}/voice/"
    slots = []
    for cells in C.csv_split(rows[template_id]):
        if len(cells) != 5:
            continue
        # c4 官方写法是相对 character/<code>/voice/ 的槽名（``home/nn_lightno``）；
        # 少数行写全路径，两种都认。
        slot = cells[4][len(prefix):] if cells[4].startswith(prefix) else cells[4]
        if slot.startswith("home/"):
            slots.append(slot)
    return slots


def ref_candidates(role: str) -> dict[str, list[tuple[str, str]]]:
    """按母本自动生成 battle/home 候选，并且只留官方归档里真有的那些。"""
    spec = MS.SPECS[role]
    pack = MC.MAPack(spec)
    code, tid = spec.template_code, spec.template_id_s
    home = _official_speech_home_slots(pack, code, tid) or [f"home/home_{i}" for i in range(6)]
    candidates = {"battle": [(code, slot) for slot in BATTLE_REF_SLOTS],
                  "home": [(code, slot) for slot in home]}
    out = {}
    for kind, items in candidates.items():
        keep = [(c, s) for c, s in items
                if pack.official_identity(f"character/{c}/voice/{s}.mp3") is not None]
        if not keep:
            raise SystemExit(f"{role}: no official {kind} reference voice under character/{code}/voice/")
        out[kind] = keep
    return out


def prepare_refs(role_keys: list[str]) -> None:
    """给 ``wf_seasonal7_voice.build_references`` 喂本批的候选表（它按 role 现查这两个全局）。"""
    V.REF_CANDIDATES = {role: ref_candidates(role) for role in role_keys}
    V.REF_NOTES = {role: f"参考音取母本 {MS.SPECS[role].template_code} 的官方原声；仅本机自用。"
                   for role in role_keys}


# ---------------------------------------------------------------- 装包后处理

def finish_pack(role: str, run: str) -> dict[str, Any]:
    """并入 claims、登记 voice 产物、刷新三层镜像（01 报告 §2.4 的三件必做）。"""
    spec = MS.get_spec(role)
    pack = MC.MAPack(spec)
    record = json.loads((V.GENERATION_DIR / run / role / "pack-result.json").read_text(encoding="utf-8"))
    claims = record.get("claims") or []
    merged = C.merge_claims(pack.load_claims(), claims)
    pack.write_evidence(C.CLAIMS_FILE, merged)
    entries = [(a["root"], a["logical_path"]) for a in record.get("assets") or []]
    pack.register_outputs("voice", entries)
    mirrors = pack.sync_character_mirrors()
    return {"claims_merged": len(claims), "voice_assets_registered": len(entries),
            "character_row_c9_16": mirrors["character"][9:17],
            "server_character": mirrors["server_character"]}


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("refs", "refs2", "plan", "generate", "process", "select", "pack"))
    parser.add_argument("--roles", nargs="*", default=[])
    parser.add_argument("--run", default=None, help="generation/<run>；v2 默认 v2take1")
    parser.add_argument("--design", help="单角色时覆盖 design json 路径")
    parser.add_argument("--only", action="append", default=[], help="generate：role:slot，可重复")
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    parser.add_argument("--no-retry", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="pack：不写文件（只跑校验）")
    parser.add_argument("--replace", action="store_true", help="pack：允许覆盖包内已有语音")
    parser.add_argument("--force-refs", action="store_true",
                        help="refs：连无官方母本语音的角色也一起跑（默认跳过 %s）" % (NO_OFFICIAL_REFS,))
    parser.add_argument("--script", action="store_true",
                        help="读 rework2/voice/scripts/<role>.json 合成 design（隐含 v2）")
    parser.add_argument("--script-dir", default=None, help="台词稿目录（默认 rework2/voice/scripts）")
    parser.add_argument("--recipe", default=None, help="配方 json（默认 rework2/voice/recipe.json）")
    parser.add_argument("--prompt-version", type=int, choices=(1, 2), default=None)
    parser.add_argument("--take", type=int, default=None, help="只作用于 takes/NN")
    parser.add_argument("--takes", type=int, default=None, help="抽卡次数 takes/01..NN")
    parser.add_argument("--selected", action="store_true", help="pack：标准态取自 selected.json")
    parser.add_argument("--remaster", action="store_true",
                        help="process：允许用新策略覆盖旧的 qc/standard（不给就照旧抛 QC drift）；"
                             "raw 与 receipts 一个字节不动，也不会重新生成")
    parser.add_argument("--role-lock", action=argparse.BooleanOptionalAction, default=True,
                        help="generate：角色级跨进程锁，默认开（防同一角色被两个进程重复计费）；"
                             "--no-role-lock 是逃生口")
    parser.add_argument("--lock-timeout", type=float, default=0.0)
    parser.add_argument("--quota-slots", type=int, choices=(0, 1, 2), default=V.MAX_WORKERS,
                        help="generate：全局并发生成槽（与 --workers 同语义）；0=关")
    args = parser.parse_args(argv)

    rework2 = args.command == "refs2" or args.script or args.prompt_version == 2 or args.selected
    # select 以前不在 rework2 的触发条件里：不带 --script 时 rework2 判假，会**静默**落回
    # 第一轮的 voice/generation/take1 —— 指着另一棵树选优，还一声不吭。
    # 触发条件里加 "select" 是死代码（--script/--prompt-version/--selected 已经各自触发，
    # 剩下的情况正是「拿不准」），所以这里直接要求说清是哪一轮。
    if args.command == "select" and not rework2 and args.prompt_version is None:
        parser.error("select 必须显式指定轮次：第二轮用 --script（或 --prompt-version 2），"
                     "第一轮用 --prompt-version 1")
    install_paths(rework2=rework2)
    run = args.run or ("v2take1" if rework2 else "take1")
    role_keys = args.roles or MS.all_keys()
    unknown = [r for r in role_keys if r not in MS.SPECS]
    if unknown:
        parser.error(f"unknown roles: {unknown}")

    version = args.prompt_version or (2 if args.script or rework2 else None)
    passthrough = []
    if version:
        passthrough += ["--prompt-version", str(version)]
    if args.take:
        passthrough += ["--take", str(args.take)]
    if args.takes:
        passthrough += ["--takes", str(args.takes)]

    if args.command == "refs2":
        specs = reference_specs(load_recipe(args.recipe), role_keys)
        index = V.build_references_v2(specs, out_dir=V.REFS_DIR, index_path=V.REFS_INDEX)
        print(json.dumps({role: {name: [group.get("seconds"), group.get("lufs_i"),
                                        group.get("loudness_method"), group.get("rms_dbfs"),
                                        "+2nd" if group.get("second") else ""]
                                 for name, group in item["groups"].items()}
                          for role, item in index["roles"].items() if role in role_keys},
                         ensure_ascii=False, indent=1))
        warnings = {r: index["roles"][r]["warnings"] for r in role_keys if index["roles"][r]["warnings"]}
        if warnings:
            print(json.dumps({"range_warnings": warnings}, ensure_ascii=False))
        exempted = {r: [v for v in index["roles"][r]["violations"] if v["exempted"]] for r in role_keys}
        exempted = {r: v for r, v in exempted.items() if v}
        if exempted:
            print(json.dumps({"exempted": exempted}, ensure_ascii=False))
        # 区间外 / 电平测不出且没换尺的参考音 = plan 会拒的那些；这里就要以非零退出码说清楚，
        # 别再只打一行 warning 然后让 158 条请求带着它们出发。
        blocking = {r: index["roles"][r]["blocking"] for r in role_keys if index["roles"][r]["blocking"]}
        if blocking:
            print(json.dumps({"blocking": blocking,
                              "action": "换同族的另一条官方原声后重跑 refs2，或在 recipe."
                                        "reference_policy.per_role.<role>.exemptions 里写明豁免理由"},
                             ensure_ascii=False, indent=1))
            return 1
        return 0

    if args.command == "pack" and args.script and not args.design and len(role_keys) == 1:
        source = json.loads(script_path(role_keys[0], args.script_dir).read_bytes())
        if source.get("accepted_delivery"):
            from wf_magnus_hibiki_voice_revision import install_accepted
            result = install_accepted(role_keys[0], source, apply=not args.dry_run)
            print(json.dumps(result, ensure_ascii=False))
            return 0

    if args.script:
        if args.design:
            parser.error("--script and --design are mutually exclusive")
        made = [synthesize_design(role, folder=args.script_dir) for role in role_keys]
        V.DESIGN_DIR = Path(SYNTH_DESIGN_DIR)
        print(json.dumps({"synthesized_designs": [str(p) for p in made]}, ensure_ascii=False))

    if args.command == "refs":
        usable = role_keys if args.force_refs else [r for r in role_keys if r not in NO_OFFICIAL_REFS]
        skipped = [r for r in role_keys if r not in usable]
        if not usable:
            print(json.dumps({"skipped_no_official_reference": skipped,
                              "reason": "design 里写显式 references {path, sha256}"},
                             ensure_ascii=False))
            return 0
        prepare_refs(usable)
        rc = V.main(["refs", "--roles", *usable])
        if skipped:
            print(json.dumps({"skipped_no_official_reference": skipped}, ensure_ascii=False))
        return rc

    if args.command in ("plan", "process", "select"):
        extra = ["--design", args.design] if args.design else []
        # --remaster 只有 process 认；别的子命令带上它会被 argparse 直接顶回来。
        if args.remaster and args.command == "process":
            extra.append("--remaster")
        return V.main([args.command, "--roles", *role_keys, "--run", run, *extra, *passthrough])

    if args.command == "generate":
        load_key()
        extra = ["--design", args.design] if args.design else []
        for only in args.only:
            extra += ["--only", only]
        if args.no_retry:
            extra.append("--no-retry")
        extra += ["--role-lock" if args.role_lock else "--no-role-lock",
                  "--lock-timeout", str(args.lock_timeout),
                  "--quota-slots", str(args.quota_slots)]
        return V.main(["generate", "--roles", *role_keys, "--run", run,
                       "--workers", str(args.workers), *extra, *passthrough])

    # pack：装包（--write --apply-tables）+ 并 claims + 登记产物 + 刷三层镜像
    if len(role_keys) != 1:
        parser.error("pack one role at a time")
    role = role_keys[0]
    spec = MS.get_spec(role)
    package = MC.MAPack(spec).package
    extra = ["--design", args.design] if args.design else []
    if args.replace:
        extra.append("--replace")
    if args.selected:
        extra.append("--selected")
    if not args.dry_run:
        extra += ["--write", "--apply-tables"]
    rc = V.main(["pack", "--roles", role, "--run", run, "--package", str(package), *extra, *passthrough])
    if rc != 0 or args.dry_run:
        return rc
    print(json.dumps({"role": role, "post_pack": finish_pack(role, run)},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
