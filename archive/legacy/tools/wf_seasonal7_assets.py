# -*- coding: utf-8 -*-
"""复制母本原生资产到新 code（泛化 wf_campus_nephtim_assets）。

- 清单 = ``wf_assets.char_asset_manifest(母本)``：37 项必需 + 原生语音（排除 excluded、
  story/episode/words/login）**∪ 包内 character_speech 行 voice_path 引用的语音**
  （char_asset_manifest 认不出自定义 home 文件名，如 meteor23 的 ``home/a_ano_shibuyaniwa``；
  引用的文件在 live 与官方基线都找不到时硬失败）；
- AMF3 内嵌 ``character/<母本>/`` 路径改写为 ``character/<新 code>/``（树不变则保留原字节）；
- live 与官方基线 (crc,size) 不一致时取官方字节（母本资产被自制改过）；
- 已被其他步骤（art/pixel/kit/voice）登记的产物不覆盖；
- 语音只是占位：包里已有的语音文件**永不覆盖**（语音步骤可能直接写盘而未登记）；
- 非语音产物：若盘上字节已不同于 assets 上次写入/登记的字节（= 被他人改过但未登记），
  整步在写入任何文件前报错，不静默回滚。特效族复制见 ``wf_seasonal7_common.clone_effect_family``。
"""
from __future__ import annotations

from typing import Any

import wf_assets
import wf_seasonal7_common as C

STEP = "assets"
SKIP_SEGMENTS = ("/story/", "/episode_", "/words", "/login")
SPEECH = "master/character/character_speech.orderedmap"
NO_VOICE = ("", "(None)")


def speech_voice_logicals(pack: C.S7Pack) -> list[str]:
    """包内 character_speech 行（c4 voice_path）引用的语音，映射回母本 logical path。"""
    spec = pack.spec
    if not pack.pkg_has("common", SPEECH):
        return []
    rows = pack.pkg_flat(SPEECH)
    if spec.cid_s not in rows:
        return []
    out = []
    for cells in C.csv_split(rows[spec.cid_s]):
        if len(cells) != 5:
            raise C.S7Error(f"speech row must have 5 cells: {cells}")
        voice = cells[4]
        if voice in NO_VOICE:
            continue
        if voice.startswith("/") or ".." in voice.split("/") or voice.endswith(".mp3"):
            raise C.S7Error(f"speech voice_path must be relative without suffix: {voice!r}")
        out.append(voice)
    return out


def _planned_items(pack: C.S7Pack) -> tuple[list[dict], list[dict]]:
    """(复制清单, speech 引用核对明细)。"""
    spec = pack.spec
    items = [item for item in wf_assets.char_asset_manifest(pack.store, spec.template_code)
             if item["exists"] and item["category"] != "excluded"
             and not any(seg in item["logical"] for seg in SKIP_SEGMENTS)]
    listed = {item["logical"] for item in items}
    speech_report = []
    missing = []
    for voice in speech_voice_logicals(pack):
        new_logical = f"character/{spec.code}/voice/{voice}.mp3"
        tpl_logical = f"character/{spec.template_code}/voice/{voice}.mp3"
        owner = pack.owner_of("common", new_logical)
        entry = {"voice_path": voice, "target": new_logical, "template": tpl_logical}
        if pack.pkg_has("common", new_logical) and owner not in (None, STEP):
            entry["resolved_by"] = f"package ({owner})"
        elif tpl_logical in listed:
            entry["resolved_by"] = "char_asset_manifest"
        else:
            try:
                pack.template_asset(tpl_logical)
            except FileNotFoundError:
                if pack.pkg_has("common", new_logical):
                    entry["resolved_by"] = "package (unregistered)"
                else:
                    missing.append(voice)
                    entry["resolved_by"] = None
            else:
                entry["resolved_by"] = "speech voice_path"
                items.append({"logical": tpl_logical, "category": "voice", "text": "",
                              "exists": True, "from_speech": True})
                listed.add(tpl_logical)
        speech_report.append(entry)
    if missing:
        raise C.S7Error(f"speech voice_path not found in package, live or official baseline: {missing}")
    return items, speech_report


def build(pack: C.S7Pack) -> dict[str, Any]:
    spec = pack.spec
    pack.check_identity()
    substitutions = C.dir_prefix_map(spec.template_code, spec.code)
    items, speech_report = _planned_items(pack)
    prior_inventory = pack.read_evidence("asset-inventory.json", []) or []
    last_written = {(e["root"], e["target"]): e["sha256"] for e in prior_inventory
                    if isinstance(e, dict) and e.get("written")}

    # ---- 先算全部候选字节，再做「被他人改过」检查，最后才写（出错时不留半截）
    planned = []
    for item in items:
        logical = item["logical"]
        root, raw, source = pack.template_asset(logical)
        if root not in C.CLIENT_ROOTS:
            raise C.S7Error(f"unknown asset root {root} for {logical}")
        target = logical.replace(f"character/{spec.template_code}/", f"character/{spec.code}/", 1)
        if not target.startswith(f"character/{spec.code}/"):
            raise C.S7Error(f"asset outside template character dir: {logical}")
        data = raw
        rewritten = False
        if logical.endswith(".amf3.deflate"):
            tree = C.amf_parse(raw)
            new_tree = C.replace_strings(tree, substitutions)
            if new_tree != tree:
                data = C.amf_bytes(new_tree)
                rewritten = True
            if f"character/{spec.template_code}/" in repr(new_tree):
                raise C.S7Error(f"template path survived rewrite: {logical}")
        planned.append((item, logical, root, target, raw, data, source, rewritten))

    foreign_modified = []
    for item, logical, root, target, raw, data, source, rewritten in planned:
        if "/voice/" in target or not pack.pkg_has(root, target):
            continue
        owner = pack.owner_of(root, target)
        if owner not in (None, STEP):
            continue                                   # 他人登记的产物：下面跳过
        if pack.pkg_path(root, target).read_bytes() == data:
            continue
        changed = pack.modified_since_registration(root, target, last_written.get((root, target)))
        if changed or (changed is None and owner is None):
            foreign_modified.append(f"{root}:{target}")
    if foreign_modified:
        raise C.S7Error(
            "package files differ from what assets last wrote (modified by another step without "
            "register_outputs); refusing to overwrite: " + ", ".join(foreign_modified[:10])
            + " — register the real owner via pack.register_outputs(<owner>, …) or delete the file to "
              "restore the template copy")

    inventory, voices, skipped_owned, kept_voices, provenance = [], [], [], [], {}
    mine: list[tuple[str, str]] = []
    for item, logical, root, target, raw, data, source, rewritten in planned:
        is_voice = "/voice/" in target
        existed = pack.pkg_has(root, target)
        if is_voice:
            wrote = pack.write_asset(root, target, data, respect_owner=STEP, only_missing=True)
            if not wrote and pack.pkg_path(root, target).read_bytes() != data:
                kept_voices.append({"root": root, "target": target, "owner": pack.owner_of(root, target)})
        else:
            wrote = pack.write_asset(root, target, data, respect_owner=STEP)
        if not wrote and existed and pack.owner_of(root, target) not in (None, STEP):
            skipped_owned.append({"root": root, "target": target, "owner": pack.owner_of(root, target)})
        if wrote or pack.owner_of(root, target) in (None, STEP) and \
                pack.pkg_path(root, target).read_bytes() == data:
            mine.append((root, target))
        provenance[source] = provenance.get(source, 0) + 1
        entry = {"source": logical, "root": root, "target": target, "category": item["category"],
                 "source_sha256": C.sha256(raw), "sha256": C.sha256(data),
                 "provenance": source, "amf3_rewritten": rewritten,
                 "written": pack.pkg_path(root, target).read_bytes() == data}
        if item.get("from_speech"):
            entry["from_speech"] = True
        inventory.append(entry)
        if logical.endswith(".mp3"):
            voices.append({**entry, "subtitle": item.get("text", ""), "mode": "native-inherited-placeholder"})
    pack.register_outputs(STEP, mine)

    # speech 引用最终核对：每条 voice_path 必须落在包内
    unresolved = [e["voice_path"] for e in speech_report if not pack.pkg_has("common", e["target"])]
    if unresolved:
        raise C.S7Error(f"speech voice_path still missing from package after assets: {unresolved}")

    required = [e for e in inventory if e["category"] == "required"]
    for name in ("sprite_sheet.png", "special_sprite_sheet.png"):
        logical = f"character/{spec.code}/pixelart/{name}"
        path = pack.pkg_path("common", logical)
        if path.is_file() and pack.owner_of("common", logical) in (None, STEP):
            native = pack.evidence_path("native-" + name)
            decoded = wf_assets.png_decode(path.read_bytes())
            if not native.is_file() or native.read_bytes() != decoded:
                native.parent.mkdir(parents=True, exist_ok=True)
                native.write_bytes(decoded)
    report = {"character": spec.key, "template_code": spec.template_code,
              "assets": len(inventory), "required": len(required),
              "inherited_voices": len(voices),
              "speech_voice_refs": speech_report,
              "speech_voices_added": sum(1 for e in inventory if e.get("from_speech")),
              "provenance": provenance,
              "skipped_owned_by_other_steps": skipped_owned,
              "kept_existing_voices": kept_voices}
    pack.write_evidence("asset-inventory.json", inventory)
    pack.write_evidence("voice-inventory.json", voices)
    pack.write_evidence("assets-report.json", report)
    return report
