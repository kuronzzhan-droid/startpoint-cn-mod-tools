"""Assemble character tables using the shared row transformations."""
from __future__ import annotations
from .table_rows import *

def build(pack: C.S7Pack) -> dict[str, Any]:
    import wf_character_pack as character_pack
    spec = pack.spec
    pack.check_identity()
    remap = cell_remap(spec)
    flips: list[dict] = []
    notes: list[dict] = []
    placeholders: dict[str, str] = {}
    cloned: dict[str, Any] = {}

    # ---- character / character_text / action_skill 占位
    template_row = template_character_row(pack)
    if int(template_row[27]) != spec.template_identity:
        raise C.S7Error(f"spec.template_identity {spec.template_identity} != template row c27 {template_row[27]}")
    if spec.identity not in (spec.cid, int(template_row[27])):
        raise C.S7Error(f"identity {spec.identity} must be cid or template c27 {template_row[27]}")
    # 包内已有行时以包内行为底，只重写 spec 拥有的列（保留 kit/voice 改过的 c9-c16、c25 等）。
    existing_char = _existing_row(pack, CHAR, spec.cid_s)
    crow = character_row(pack, existing_char if existing_char is not None else template_row)
    action_template = core.load_nested_table_bytes(pack.template_table_bytes(ACTION), ACTION)
    if spec.template_code not in action_template.rows:
        raise C.S7Error(f"template action_skill missing: {spec.template_code}")
    template_inner = action_template.rows[spec.template_code].text_rows()
    skills = skill_texts(pack, template_inner)
    if spec.element_flip:
        for level, text in template_inner.items():
            cells = C.csv_split(text)[0]
            if skills[level][1] != cells[1]:
                flips.append({"table": f"{ACTION}#{spec.code}/{level} + {TEXT} desc", "col": 1,
                              "before": cells[1], "after": skills[level][1]})

    inner_rows = {}
    for level, text in template_inner.items():
        cells = C.csv_split(text)[0]
        cells[0], cells[1] = skills[level]
        cells[7] = program_path(spec, level)
        inner_rows[level] = [cells]
    written = pack.write_nested(ACTION, spec.code, inner_rows, only_missing=True)
    placeholders[ACTION] = "written" if written else "kept-existing"
    # 技能名/描述：spec(TEXTS) 显式给值时同步进包内 action_skill c0/c1；否则以包内（kit）行为准。
    package_inner = core.load_nested_table_bytes(pack.pkg_path("common", ACTION).read_bytes(),
                                                 ACTION).rows[spec.code].text_rows()
    resolved: dict[str, tuple[str, str]] = {}
    text_updates = {}
    for level, text in package_inner.items():
        cells = C.csv_split(text)[0]
        name = spec.texts.get(f"skill{level}") if level in ("1", "2") else None
        desc = spec.texts.get(f"desc{level}") if level in ("1", "2") else None
        new_cells = list(cells)
        if name is not None:
            new_cells[0] = name
        if desc is not None:
            new_cells[1] = desc
        if new_cells != cells:
            text_updates[level] = [new_cells]
        resolved[level] = (new_cells[0], new_cells[1])
    if text_updates:
        pack.write_nested(ACTION, spec.code, text_updates)
    for level in template_inner:
        tree = pack.template_dsl(C.csv_split(template_inner[level])[0][7])
        tree, dsl_flips = C.flip_dsl_elements(tree, spec.template_element, spec.element)
        dsl_logical = C.wf_dsl.dsl_logical(program_path(spec, level))
        existed = pack.pkg_has("common", dsl_logical)
        pack.write_dsl(program_path(spec, level), tree, only_missing=True)
        placeholders[dsl_logical] = "kept-existing" if existed else "written"
        flips.extend({"table": dsl_logical, **f, "placeholder_written": not existed} for f in dsl_flips)

    template_text = C.csv_split(pack.template_flat(TEXT)[spec.template_id_s])[0]
    existing_text = _existing_row(pack, TEXT, spec.cid_s)
    trow = character_text_row(pack, template_text, resolved, existing_text)
    pack.write_flat(CHAR, {spec.cid_s: [crow]})
    pack.write_flat(TEXT, {spec.cid_s: [trow]})
    cloned["character"] = crow
    cloned["character_text"] = trow

    # ---- 可选 flat 克隆（母本有才克隆）
    for logical, kit_owned in ((AWAKE, False), (UPSKILL, True), (MANA_OPEN, False),
                               (SKILL_PREVIEW, False), (STANCE_DETAIL, False)):
        rows = pack.template_flat(logical)
        if spec.template_id_s not in rows:
            notes.append({"table": logical, "skipped": "template has no row"})
            continue
        cells = [[remap(c) for c in row] for row in C.csv_split(rows[spec.template_id_s])]
        if logical == STANCE_DETAIL:
            cells = stance_detail_rows(cells, template_row[26], spec.stance, notes)
        text = C.csv_join(cells)
        if logical == MANA_OPEN:
            text = open_condition_row(text, notes)
        written = pack.write_flat(logical, {spec.cid_s: text}, only_missing=kit_owned)
        if kit_owned:
            placeholders[logical] = "written" if written else "kept-existing"
        cloned[logical.rsplit("/", 1)[-1]] = C.csv_split(text)

    # ---- speech：母本行，voice_path 只改写 character/<母本>/ 全路径
    speech_rows = C.csv_split(pack.template_flat(SPEECH)[spec.template_id_s])
    for cells in speech_rows:
        if len(cells) != 5:
            raise C.S7Error(f"speech row must have 5 cells: {cells}")
        cells[4] = remap(cells[4])
    if not any(r[1] in ("0", "2") for r in speech_rows) or not any(r[1] in ("1", "2") for r in speech_rows):
        raise C.S7Error("speech visibility invariant broken ({0,2} and {1,2} each need one row)")
    written = pack.write_flat(SPEECH, {spec.cid_s: speech_rows}, only_missing=True)   # 之后归语音步骤
    placeholders[SPEECH] = "written" if written else "kept-existing"

    # ---- raw_outer 克隆
    raw_templates = {}
    for logical in (STATUS, GACHA_SOUND, CHAR_IMAGE, FULL_SHOT_ATTR, MANA_BOARD, MANA_NODE):
        table = pack.template_raw(logical)
        if spec.template_id_s not in table:
            raise C.S7Error(f"template row missing: {logical}")
        raw_templates[logical] = table[spec.template_id_s]
    gacha_changes: list[dict] = []
    pack.write_raw_outer(STATUS, {spec.cid_s: raw_templates[STATUS]})
    pack.write_raw_outer(GACHA_SOUND, {spec.cid_s: clone_blob(raw_templates[GACHA_SOUND],
                                                              _gacha_transform(pack, gacha_changes))})
    flips.extend(gacha_changes)
    for logical in (CHAR_IMAGE, FULL_SHOT_ATTR):          # 美术步骤拥有，已存在不覆盖
        written = pack.write_raw_outer(logical, {spec.cid_s: raw_templates[logical]}, only_missing=True)
        placeholders[logical] = "written" if written else "kept-existing"
    materials = element_material_items(pack.template_flat(ITEM))
    material_map = element_material_map(pack.template_flat(ITEM), spec.template_element, spec.element) \
        if spec.element_flip else {}
    for logical in (MANA_BOARD, MANA_NODE):
        blob = clone_blob(raw_templates[logical], remap)
        if logical == MANA_NODE and material_map:
            material_changes: list[dict] = []
            blob = remap_mana_node_items(blob, material_map, material_changes)
            flips.extend(material_changes)
        if logical == MANA_NODE:
            used = mana_node_item_elements(blob, materials)
            foreign = {el: sorted(ids, key=int) for el, ids in used.items() if el != str(spec.element)}
            if foreign:
                raise C.S7Error(f"mana_node materials belong to other elements {foreign}; element {spec.element}")
            notes.append({"table": MANA_NODE, "material_elements": sorted(used),
                          "material_map": material_map or None})
        pack.write_raw_outer(logical, {spec.cid_s: blob})
        cloned[logical.rsplit("/", 1)[-1]] = decode_blob(blob)

    trimmed = pack.template_flat(TRIMMED)
    stems = ("full_shot_1440_1920_0", "full_shot_1440_1920_1", "skill_cutin_0", "skill_cutin_1")
    rows = {}
    for stem in stems:
        src = f"character/{spec.template_code}/ui/{stem}"
        if src not in trimmed:
            raise C.S7Error(f"template trimmed_image key missing: {src}")
        rows[f"character/{spec.code}/ui/{stem}"] = trimmed[src]
    written = pack.write_flat(TRIMMED, rows, only_missing=True)
    placeholders[TRIMMED] = f"written {len(written)}/4"

    # ---- 词条 6 键 / 队长占位（kit 拥有）
    ability_rows = pack.template_flat(ABILITY)
    leader_rows = pack.template_flat(LEADER)
    exact_code = re.compile(r"^" + re.escape(spec.template_code) + r"(_\d+)?$")
    cas_key = custom_string_key_map(spec)
    template_cas = pack.template_flat(CAS)
    new_cas: dict[str, str] = {}
    cas_notes: list[dict] = []
    new_abilities: dict[str, list[list[str]]] = {}
    legacy_abilities: dict[str, list[list[str]]] = {}      # 修复前框架写出的占位（c70 仍指母本键）
    ability_flips: dict[str, list[dict]] = {}
    for slot, src_key in enumerate(template_row[19:25], start=1):
        if src_key not in ability_rows:
            raise C.S7Error(f"template ability row missing: {src_key}")
        key = f"{spec.cid}{slot}"
        lines, legacy = [], []
        for li, row in enumerate(C.csv_split(ability_rows[src_key])):
            row = list(row)
            if exact_code.match(row[0]):
                row[0] = f"{spec.code}_{slot}"
            row, changes = C.flip_ability_row(row, "ability", spec.template_element, spec.element,
                                              label=f"{key}#L{li}")
            ability_flips.setdefault(key, []).extend({"table": ABILITY, **c} for c in changes)
            legacy.append(list(row))
            for ci, cell in enumerate(row):
                target = cas_key(cell)
                if target is None or cell not in template_cas:
                    continue
                row[ci] = target
                new_cas[target] = template_cas[cell]
                cas_notes.append({"table": ABILITY, "cell": f"{key}#L{li}", "col": ci,
                                  "before": cell, "after": target})
            lines.append(row)
        new_abilities[key] = lines
        legacy_abilities[key] = legacy
    existing_abilities = pack.pkg_flat(ABILITY) if pack.pkg_has("common", ABILITY) else {}
    upgrades = {k: v for k, v in new_abilities.items()
                if k in existing_abilities and v != legacy_abilities[k]
                and existing_abilities[k] == C.as_text(legacy_abilities[k])}
    written = pack.write_flat(ABILITY, new_abilities, only_missing=True)
    if upgrades:                               # 未经 kit 改动的旧占位：补上 custom_ability_string 重定向
        pack.write_flat(ABILITY, upgrades)
        written = [*written, *upgrades]
    placeholders[ABILITY] = f"written {len(written)}/6" + (f" (upgraded {sorted(upgrades)})" if upgrades else "")
    if new_cas:
        # 技能名随 spec/kit：『母本技能名』→『新技能名』；元素翻转时「风属性」→「光属性」
        name_map = {}
        for level, text in template_inner.items():
            old_name = C.csv_split(text)[0][0]
            if level in resolved and resolved[level][0] != old_name:
                name_map[f"『{old_name}』"] = f"『{resolved[level][0]}』"
        package_abilities = pack.pkg_flat(ABILITY)
        referenced = {cell for key in new_abilities for row in C.csv_split(package_abilities[key])
                      for cell in row if cell in new_cas}
        live_cas = pack.live_flat(CAS)
        package_cas = pack.pkg_flat(CAS) if pack.pkg_has("common", CAS) else {}
        cas_rows = {}
        for key in sorted(referenced):
            if key in live_cas and key not in package_cas:
                raise C.S7Error(f"custom_ability_string key already occupied in live: {key}")
            text = new_cas[key]
            for old, new in name_map.items():
                text = text.replace(old, new)
            cas_rows[key] = C.replace_element_words(text, spec.template_element, spec.element)
        if cas_rows:
            cas_written = pack.write_flat(CAS, cas_rows, only_missing=True)
            placeholders[CAS] = f"written {len(cas_written)}/{len(cas_rows)}"
        notes.extend(cas_notes)
    for key in new_abilities:                 # kit 已写过的键：翻转仅记录，不落盘
        flips.extend({**f, "placeholder_written": key in written} for f in ability_flips.get(key, []))
    leader_lines, leader_flips = [], []
    src_leader = template_row[17]
    if src_leader not in leader_rows:
        raise C.S7Error(f"template leader row missing: {src_leader}")
    for li, row in enumerate(C.csv_split(leader_rows[src_leader])):
        row = list(row)
        if row[0] == spec.template_code:
            row[0] = spec.code
        row, changes = C.flip_ability_row(row, "leader_ability", spec.template_element, spec.element,
                                          label=f"{spec.cid}#L{li}")
        leader_flips.extend({"table": LEADER, **c} for c in changes)
        leader_lines.append(row)
    written = pack.write_flat(LEADER, {spec.cid_s: leader_lines}, only_missing=True)
    placeholders[LEADER] = "written" if written else "kept-existing"
    flips.extend({**f, "placeholder_written": bool(written)} for f in leader_flips)

    # ---- server 五表
    mirrors = pack.sync_character_mirrors()
    node_rows = server_mana_node(pack)
    pack.write_server("mana_node.json", {spec.cid_s: node_rows})
    board_rows = character_pack.package_server_mana_board_rows(pack.package, spec.cid_s)
    if not board_rows or spec.cid_s not in board_rows:
        raise C.S7Error("cannot derive server mana_board row from package client table")
    pack.write_server("mana_board.json", {spec.cid_s: board_rows[spec.cid_s]})
    # 交叉核对：母本服务端镜像按前缀重映射后应与客户端派生一致
    cross = {}
    for logical, derived in (("mana_node.json", node_rows), ("mana_board.json", board_rows[spec.cid_s])):
        base = json.loads((pack.server_base / logical).read_text(encoding="utf-8"))
        tmpl = base.get(spec.template_id_s)
        if tmpl is None:
            cross[logical] = "template missing in server mirror"
            continue
        remapped = json.loads(re.sub(r'"' + re.escape(spec.template_mana_prefix) + r'(\d{3})"',
                                     lambda m: '"' + spec.mana_prefix + m.group(1) + '"',
                                     json.dumps(tmpl, ensure_ascii=False)))
        if logical == "mana_node.json" and material_map:
            for board in remapped.values():
                for node in board.values():
                    node["items"] = {material_map.get(k, k): v for k, v in node["items"].items()}
        cross[logical] = "match" if remapped == derived else "differs (client-table derivation used)"

    report = {
        "character": spec.key, "cid": spec.cid, "code": spec.code,
        "template": {"id": spec.template_id, "code": spec.template_code},
        "claims": len(pack.load_claims()),
        "tables": [f"{c['root']}:{c['logical_path']}" for c in pack.load_claims()],
        "placeholders": placeholders,
        "element_flip": {"from": spec.template_element, "to": spec.element,
                         "cells": flips} if spec.element_flip else None,
        "notes": notes,
        "server_mana_crosscheck": cross,
        "mirrors": {"server_character": mirrors["server_character"]},
    }
    pack.write_evidence("tables-report.json", report)
    pack.write_evidence("cloned_cells.json", cloned)
    if spec.element_flip:
        pack.write_evidence("element_flip.json", report["element_flip"])
    return report
